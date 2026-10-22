"""Reproducible descriptive screening; no causal or individual-level claims.

Run with Python 3.11+, pandas, numpy, geopandas, shapely, pyproj,
scipy, matplotlib and openpyxl. Raw sources are documented in sources.json.
"""
from pathlib import Path
import hashlib, json, re, platform, os, zipfile, shutil
from collections import Counter
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from shapely import affinity
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'
OUT = ROOT / 'output/final_analysis'
FIG = OUT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)
for stem in ['tpss_sta_route_hturn_2026.09.21-09.27','tpss_sta_route_hpasngr_2026.09.21-09.27']:
    csv_path=RAW/(stem+'.csv')
    if not csv_path.exists():
        with zipfile.ZipFile(RAW/(stem+'.zip')) as z, z.open(stem+'.csv') as src, csv_path.open('wb') as dst:
            shutil.copyfileobj(src,dst)
FONT = os.environ.get('KOREAN_FONT','/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
if Path(FONT).exists():
    matplotlib.font_manager.fontManager.addfont(FONT)
    plt.rcParams['font.family'] = FontProperties(fname=FONT).get_name()
plt.rcParams.update({'axes.unicode_minus': False, 'font.size': 10,
                     'figure.dpi': 150, 'savefig.dpi': 220})

def export(df, name):
    pd.DataFrame(df).to_csv(OUT / name, index=False, encoding='utf-8-sig')

def read_book(name):
    return pd.read_excel(RAW / name, dtype=str, keep_default_na=False)

# Population is a captured public DOM table, not a downloaded XLSX.
records, subtotals, district = [], {}, ''
canonical = []
for line in (RAW / 'seoul_population_2026Q2_DOM_capture.txt').read_text().splitlines():
    gu, dong_raw, pop, old = line.split('|')
    pop, old = int(pop.replace(',', '')), int(old.replace(',', ''))
    if gu:
        district = gu
        subtotals[gu] = (pop, old)
        continue
    dong = re.sub(r'^\d+\)\s*', '', dong_raw)
    canonical.append(f'{district}|{dong}|{pop}|{old}')
    records.append({'district': district, 'dong_original': dong_raw,
                    'dong': dong, 'population': pop, 'elderly': old})
h = 2166136261
for c in '\n'.join(canonical):
    h = ((h ^ ord(c)) * 16777619) & 0xffffffff
assert h == 0x4c6b423d, 'Captured values differ from source DOM checksum.'
pop = pd.DataFrame(records)
assert len(pop) == 427
for gu, grp in pop.groupby('district'):
    assert tuple(grp[['population', 'elderly']].sum()) == subtotals[gu]
assert tuple(pop[['population', 'elderly']].sum()) == subtotals['소계']
# Explicit, recorded name crosswalk only. No fuzzy matching.
pop['name_key'] = pop['district'] + ' ' + pop['dong'].str.replace('.', '·', regex=False)
pop.loc[pop['district'].eq('강동구'), 'name_key'] = pop.loc[pop['district'].eq('강동구'), 'name_key'].str.replace(r'상일([12])동', r'상일제\1동', regex=True)
boundary = gpd.read_file(RAW / 'HangJeongDong_ver20260701.geojson')
boundary = boundary.loc[boundary['sido'].eq('11')].copy()
boundary['name_key'] = boundary['adm_nm'].str.removeprefix('서울특별시 ')
assert len(boundary) == 427 and not boundary['name_key'].duplicated().any()
assert set(pop['name_key']) == set(boundary['name_key'])
g = boundary.merge(pop, on='name_key', validate='one_to_one')
export(g[['adm_cd', 'adm_cd2', 'adm_nm', 'district', 'dong_original', 'dong', 'name_key']], 'population_boundary_crosswalk.csv')
invalid_before = int((~g.geometry.is_valid).sum())
if invalid_before:
    g.geometry = g.geometry.make_valid()
# Boundary publisher declares WGS84. Bus source says WGS84 but has contradictory EPSG text.
# Adopt longitude/latitude working interpretation, document rather than claiming datum proof.
assert g.crs.to_epsg() == 4326
g = g.to_crs(5179)
seoul = g.geometry.union_all()
g['area_km2'] = g.area / 1e6
g['elderly_share'] = g.elderly / g.population

stops = read_book('서울시버스정류소위치정보(20260902).xlsx')
assert not stops['NODE_ID'].duplicated().any()
stops['x'] = pd.to_numeric(stops['X좌표'], errors='raise')
stops['y'] = pd.to_numeric(stops['Y좌표'], errors='raise')
assert stops.x.between(124, 132).all() and stops.y.between(33, 39).all()
ferry = stops['정류소타입'].eq('한강선착장')
bus = gpd.GeoDataFrame(stops.loc[~ferry].copy(), geometry=gpd.points_from_xy(stops.loc[~ferry, 'x'], stops.loc[~ferry, 'y']), crs=4326).to_crs(5179)
bus['inside_seoul'] = bus.geometry.intersects(seoul)
# Keep border-external points for accessibility; assign events only by point location.
hits = gpd.sjoin(bus, g[['adm_cd2', 'geometry']], how='left', predicate='intersects')
multi_ids = hits.loc[hits.index.duplicated(keep=False), 'NODE_ID'].unique().tolist()
hits = hits.reset_index(names='raw_stop_index').sort_values(['raw_stop_index', 'adm_cd2']).drop_duplicates('raw_stop_index')
export(hits.drop(columns=['geometry']), 'bus_stop_boundary_assignment.csv')
outside = hits['adm_cd2'].isna()
export(hits.loc[outside].drop(columns='geometry'), 'bus_stops_outside_boundary.csv')

bridge = read_book('서울시버스노선별정류소정보(20260902).xlsx')
route_station = bridge[['ROUTE_ID', 'NODE_ID']].drop_duplicates()
node_route_n = route_station.groupby('NODE_ID')['ROUTE_ID'].nunique()
hits['listed_route_count'] = hits['NODE_ID'].map(node_route_n)
inside_hits = hits.loc[~outside]
stop_counts = inside_hits.groupby('adm_cd2')['NODE_ID'].nunique()
g['bus_stop_count'] = g.adm_cd2.map(stop_counts).fillna(0).astype(int)
regional_routes = route_station.merge(inside_hits[['NODE_ID', 'adm_cd2']], on='NODE_ID', validate='many_to_one').groupby('adm_cd2')['ROUTE_ID'].nunique()
g['listed_route_count'] = g.adm_cd2.map(regional_routes).fillna(0).astype(int)
g['bus_stops_per_1000_elderly'] = 1000 * g.bus_stop_count / g.elderly

metro = pd.read_csv(RAW / '지하철역_GEOM (역사마스터).csv', dtype=str, keep_default_na=False, encoding='utf-8-sig')
metro['x'] = pd.to_numeric(metro['환승역X좌표'], errors='coerce')
metro['y'] = pd.to_numeric(metro['환승역Y좌표'], errors='coerce')
valid_metro = metro.x.between(124, 132) & metro.y.between(33, 39)
mg = gpd.GeoDataFrame(metro.loc[valid_metro].copy(), geometry=gpd.points_from_xy(metro.loc[valid_metro, 'x'], metro.loc[valid_metro, 'y']), crs=4326).to_crs(5179)
near_metro = mg.loc[mg.intersects(seoul.buffer(1000))].copy()
metro_cover = near_metro.buffer(500, resolution=16).union_all()
g['metro500_area_coverage'] = np.clip(g.intersection(metro_cover).area / g.area, 0, 1).round(12)

print('Computing buffer union and intersections...', flush=True)
for radius in [200, 300, 400]:
    union = bus.buffer(radius, resolution=16).union_all()
    g[f'bus{radius}_area_coverage'] = np.clip(g.intersection(union).area / g.area, 0, 1).round(12)
    g[f'combined_bus{radius}_metro500_coverage'] = np.clip(g.intersection(union.union(metro_cover)).area / g.area, 0, 1).round(12)
# Numeric geometry precision: round coverage at 12 decimal places before percentile ties.
g['uncovered300'] = (1 - g.bus300_area_coverage).round(12)
g['age_rank'] = g.elderly_share.rank(pct=True)
g['gap_rank'] = g.uncovered300.rank(pct=True)
# Descriptive screen, not learned weights and not probability of individual disadvantage.
g['screen_index'] = 100 * (g.age_rank + g.gap_rank) / 2
g['screen_rank'] = g.screen_index.rank(ascending=False, method='min').astype(int)
age_median = float(g.elderly_share.median())
gap_median = float(g.uncovered300.median())
g['high_age_high_gap'] = g.elderly_share.ge(age_median) & g.uncovered300.ge(gap_median)
g['policy_class'] = np.select([
    g.high_age_high_gap,
    g.elderly_share.ge(age_median) & g.uncovered300.lt(gap_median),
    g.elderly_share.lt(age_median) & g.uncovered300.ge(gap_median),
], ['고령비율·버스 접근공백 모두 높음', '고령비율 높음·접근공백 낮음', '고령비율 낮음·접근공백 높음'], default='두 지표 모두 낮음')

# Sensitivity, specified alternative weights/radii, no tuning to desired locations.
base_top = set(g.nlargest(10, 'screen_index').adm_cd2)
sens = []
for radius in [200, 300, 400]:
    gap_r = (1-g[f'bus{radius}_area_coverage']).round(12).rank(pct=True)
    for age_weight in [.3, .5, .7]:
        score = 100 * (age_weight*g.age_rank + (1-age_weight)*gap_r)
        top = set(g.loc[score.nlargest(10).index, 'adm_cd2'])
        sens.append({'radius_m': radius, 'age_weight': age_weight, 'base_top10_overlap': len(top & base_top), 'top10_ids': '|'.join(sorted(top))})
export(sens, 'index_sensitivity.csv')
g['top10_scenario_count'] = [sum(x in t['top10_ids'].split('|') for t in sens) for x in g.adm_cd2]
# Alternative includes observed metro stations only, not a claim of complete metro coverage.
cgap = (1-g.combined_bus300_metro500_coverage).round(12)
g['combined_screen_index'] = 50*(g.age_rank + cgap.rank(pct=True))
combined_top = set(g.nlargest(10, 'combined_screen_index').adm_cd2)

# Known-positive service events are lower bounds. A blank is never converted to 0.
supply = pd.read_csv(RAW / 'tpss_sta_route_hturn_2026.09.21-09.27.csv', encoding='cp949', dtype=str, keep_default_na=False)
boarding = pd.read_csv(RAW / 'tpss_sta_route_hpasngr_2026.09.21-09.27.csv', encoding='cp949', dtype=str, keep_default_na=False)
keys = ['기준_날짜', '노선_ID', '정류장_ID', '정류장_순서']
assert not supply.duplicated(keys).any() and not boarding.duplicated(keys).any()
loc = inside_hits[['NODE_ID', 'adm_cd2']]
assert not loc.NODE_ID.duplicated().any()
s = supply.merge(loc, left_on='정류장_ID', right_on='NODE_ID', how='inner', validate='many_to_one')
b = boarding.merge(loc, left_on='정류장_ID', right_on='NODE_ID', how='inner', validate='many_to_one')
hour_rows = []
for hour in range(24):
    col = f'버스운행횟수_{hour:02d}시'
    vals = pd.to_numeric(s[col], errors='coerce')
    temp = s[['adm_cd2', '기준_날짜']].copy()
    temp['known_events'] = vals
    temp['known_cells'] = vals.notna().astype(int)
    temp['raw_cells'] = 1
    ag = temp.groupby(['adm_cd2', '기준_날짜']).agg(known_events=('known_events', lambda x:x.sum(min_count=1)), known_cells=('known_cells', 'sum'), raw_cells=('raw_cells', 'sum')).reset_index()
    ag['hour'] = hour
    hour_rows.append(ag)
hourly = pd.concat(hour_rows, ignore_index=True)
export(hourly, 'observed_service_by_dong_date_hour.csv')
day_hours = hourly.loc[hourly.hour.between(6,21)]
daily = day_hours.groupby(['adm_cd2','기준_날짜']).agg(known_events=('known_events', lambda x:x.sum(min_count=1)),known_cells=('known_cells','sum'),raw_cells=('raw_cells','sum')).reset_index()
means = daily.groupby('adm_cd2').agg(observed_daily_06_21_service_events=('known_events','mean'),known_supply_cells=('known_cells','sum'),all_supply_cells=('raw_cells','sum'))
g = g.merge(means, on='adm_cd2', how='left', validate='one_to_one')
g['known_supply_cell_share'] = g.known_supply_cells / g.all_supply_cells
g['observed_events_per_1000_elderly'] = 1000*g.observed_daily_06_21_service_events/g.elderly
available_nodes = set(s.NODE_ID)
g['stop_with_supply_record_share'] = [len(set(inside_hits.loc[inside_hits.adm_cd2.eq(code),'NODE_ID']) & available_nodes)/n if n else np.nan for code,n in zip(g.adm_cd2,g.bus_stop_count)]
daily_board = pd.to_numeric(b['승차_승객_수'], errors='coerce')

# Global rank association and spatial permutation as exploratory descriptive diagnostics.
rho, naive_p = spearmanr(g.elderly_share, g.uncovered300)
pairs = g.sindex.query(g.geometry, predicate='intersects')
keep = pairs[0] != pairs[1]
a, c = pairs[:, keep]
W = np.zeros((len(g),len(g)))
W[a,c] = 1
deg = W.sum(axis=1)
Wr = np.divide(W,deg[:,None],out=np.zeros_like(W),where=deg[:,None]>0)
z = g.uncovered300.to_numpy()-g.uncovered300.mean()
def moran(v): return float(len(v)/Wr.sum() * (v @ Wr @ v)/(v @ v))
obs_moran = moran(z)
rng = np.random.default_rng(20261022)
perms = np.array([moran(rng.permutation(z)) for _ in range(999)])
moran_p = float((1+(perms>=obs_moran).sum())/1000)
export(pd.DataFrame({'moran_permutation': perms}), 'moran_permutation_reference.csv')
stats = {
    'analysis_date_kst': '2026-10-22', 'population_period': '2026 Q2',
    'population_source_method': 'Public rendered HTML table, 427 rows captured. UI download did not open. UTF16-code-unit FNV1a checksum verified against DOM and all 25 district subtotals reconciled.',
    'population_source_checksum': '4c6b423d', 'dong_count': len(g),
    'total_population': int(g.population.sum()), 'elderly_population': int(g.elderly.sum()),
    'city_elderly_share': float(g.elderly.sum()/g.population.sum()),
    'raw_bus_stops': len(stops), 'excluded_ferry_points': int(ferry.sum()),
    'road_bus_stops': len(bus), 'road_stops_outside_boundary': int(outside.sum()),
    'road_stops_outside_fraction': float(outside.mean()), 'boundary_multiple_assignment_stop_ids': multi_ids,
    'boundary_multiple_assignment_rule': 'intersects then ascending adm_cd2, first only; no duplicate event assignment',
    'boundary_invalid_before': invalid_before, 'population_name_crosswalk_match': 427,
    'metro_raw_rows': len(metro), 'metro_invalid_coordinate_rows': int((~valid_metro).sum()),
    'metro_near_seoul_rows': len(near_metro), 'metro_lines': metro['호선명칭'].value_counts().to_dict(),
    'metro_exact_coordinate_duplicates': int(near_metro.duplicated(['x','y']).sum()),
    'bus_coordinate_datum': 'Working assumption EPSG:4326 (source WGS84 wording + actual degree values); contradictory EPSG-5179 wording remains a metadata limitation.',
    'metric_working_crs': 'EPSG:5179', 'median_elderly_share': age_median,
    'median_uncovered_bus300_area': gap_median, 'high_age_high_gap_count': int(g.high_age_high_gap.sum()),
    'area_weighted_bus300_coverage': float((g.bus300_area_coverage*g.area_km2).sum()/g.area_km2.sum()),
    'median_bus300_coverage': float(g.bus300_area_coverage.median()),
    'bus300_coverage_min': float(g.bus300_area_coverage.min()), 'bus300_coverage_max': float(g.bus300_area_coverage.max()),
    'median_combined300_500_coverage': float(g.combined_bus300_metro500_coverage.median()),
    'combined_top10_overlap_bus_only': len(base_top & combined_top),
    'sensitivity_min_overlap_top10': min(t['base_top10_overlap'] for t in sens),
    'sensitivity_max_overlap_top10': max(t['base_top10_overlap'] for t in sens),
    'spearman_age_gap_rho': float(rho), 'spearman_naive_p_not_spatially_adjusted': float(naive_p),
    'queen_islands': int((deg==0).sum()), 'moran_I_gap300': obs_moran,
    'moran_upper_tail_permutation_p_999': moran_p,
    'supply_raw_rows': len(supply), 'supply_spatial_assigned_rows': len(s),
    'boarding_raw_rows': len(boarding), 'boarding_spatial_assigned_rows': len(b),
    'known_daily_boarding_cells_spatial_subset': int(daily_board.notna().sum()),
    'inside_stop_nodes': int(inside_hits.NODE_ID.nunique()),
    'inside_stop_nodes_with_supply': int(inside_hits.NODE_ID.isin(available_nodes).sum()),
    'all_hour_recorded_cell_share': float(hourly.known_cells.sum()/hourly.raw_cells.sum()),
    'day_06_21_recorded_cell_share': float(day_hours.known_cells.sum()/day_hours.raw_cells.sum()),
    'high_age_high_gap_elderly_population': int(g.loc[g.high_age_high_gap,'elderly'].sum()),
    'top10_elderly_population': int(g.nlargest(10,'screen_index').elderly.sum()),
    'top10_sensitivity_always_included': g.loc[g.top10_scenario_count.eq(9)].sort_values('screen_index',ascending=False)['adm_nm'].tolist(),
    'main_rank_uses_incomplete_supply': False, 'carbon_reduction_estimated': False,
    'no_individual_population_coverage_claim': True,
    'top10': json.loads(g.nlargest(10,'screen_index').drop(columns='geometry').to_json(orient='records')),
}
(OUT/'analysis_results.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n')
export(g.drop(columns='geometry').sort_values('screen_rank'), 'dong_screening_all.csv')
export(g.nlargest(10,'screen_index').drop(columns='geometry'), 'top10_review_candidates.csv')
g.to_crs(4326).to_file(OUT/'dong_screening.geojson',driver='GeoJSON')

def foot(fig, text):
    fig.text(.02,.01,text,ha='left',va='bottom',fontsize=8,color='#4b5563')

fig, axs = plt.subplots(1,3,figsize=(15,6))
for ax,col,title,cmap in zip(axs,['bus300_area_coverage','elderly_share','screen_index'],['버스 300m 면적 커버리지','65세 이상 인구 비율','고령·접근공백 검토지수'],['Blues','YlOrBr','YlOrRd']):
    g.plot(column=col,ax=ax,cmap=cmap,edgecolor='white',linewidth=.12,legend=True,legend_kwds={'shrink':.6})
    ax.set_title(title,fontsize=13,pad=12);ax.set_axis_off()
fig.suptitle('같은 서울, 다른 이동권 | 427개 동 비교',fontsize=17,y=.96)
foot(fig,'자료: 서울시 2026년 2분기 인구·2026.09.02 정류소 / SGIS 기반 vuski/admdongkor 2026.07.01 경계. 면적 커버리지는 주민 커버리지가 아님.')
fig.subplots_adjust(bottom=.13,top=.86,wspace=.2)
fig.savefig(FIG/'01_three_maps.png',bbox_inches='tight');plt.close(fig)

fig,ax=plt.subplots(figsize=(9,6))
ax.scatter(100*g.uncovered300,100*g.elderly_share,s=np.clip(g.elderly/100,8,100),alpha=.5,c=np.where(g.high_age_high_gap,'#d45735','#3e7d9c'),edgecolor='white',linewidth=.3)
ax.axvline(100*gap_median,color='#777',ls='--',lw=.8);ax.axhline(100*age_median,color='#777',ls='--',lw=.8)
for _,r in g.nlargest(7,'screen_index').iterrows():
    offset,ha = ((-6,6),'right') if r.uncovered300>.7 else ((5,6),'left')
    if r.dong == '인수동': offset=(5,-12)
    ax.annotate(f'{r.district} {r.dong}',(100*r.uncovered300,100*r.elderly_share),xytext=offset,ha=ha,textcoords='offset points',fontsize=8)
ax.set(xlabel='버스 300m 범위 밖 면적 비율 (%)',ylabel='65세 이상 인구 비율 (%)',title='시설 접근공백과 고령인구 비율은 같은 문제인가?')
ax.grid(alpha=.15);foot(fig,'점 크기: 고령인구 규모 / 점선: 동별 중앙값 / 붉은 점: 두 지표 모두 중앙값 이상. 상대적 검토 기준이며 법적 기준이 아님.')
fig.tight_layout(rect=[0,.06,1,1]);fig.savefig(FIG/'02_quadrants.png',bbox_inches='tight');plt.close(fig)

fig,axs=plt.subplots(1,2,figsize=(12,5))
top=g.nlargest(10,'screen_index').sort_values('screen_index')
labels=top.district+' '+top.dong
axs[0].barh(labels,top.screen_index,color='#be563e');axs[0].set(xlim=(0,100),xlabel='지수 (0~100, 상대 순위 결합)',title='우선 현장검토 후보 10개 동')
mat=np.array([t['base_top10_overlap'] for t in sens]).reshape(3,3)
axs[1].imshow(mat,vmin=0,vmax=10,cmap='Blues')
for i in range(3):
    for j in range(3):axs[1].text(j,i,str(mat[i,j]),ha='center',va='center',color='white' if mat[i,j]>6 else 'black')
axs[1].set(xticks=[0,1,2],xticklabels=['0.3','0.5','0.7'],yticks=[0,1,2],yticklabels=['200m','300m','400m'],xlabel='고령비율 가중치',title='기준 상위 10개와 중첩한 동 수')
foot(fig,'지수 = 100 × [고령비율 백분위 × 0.5 + 버스 접근공백 백분위 × 0.5]. 지수는 탄소배출량·개인 이동불편 확률이 아님.')
fig.tight_layout(rect=[0,.07,1,1]);fig.savefig(FIG/'03_candidates_sensitivity.png',bbox_inches='tight');plt.close(fig)

fig,ax=plt.subplots(figsize=(10,4.8))
means=hourly.groupby('hour').agg(events=('known_events',lambda x:x.sum(min_count=1)),known=('known_cells','sum'),all_cells=('raw_cells','sum'))
ax.bar(means.index,means.events/7,color='#427e9a',alpha=.85)
ax2=ax.twinx();ax2.plot(means.index,100*means.known/means.all_cells,'o-',color='#c65b3d',ms=3)
ax.set(xlabel='시간대 (파일 00시~23시)',ylabel='하루 평균 확인된 정류소 서비스 사건',title='관측된 공급과 빈칸을 구분해야 한다',xticks=range(0,24,2))
ax2.set(ylabel='값이 기록된 공급 셀 비율 (%)',ylim=(0,105))
foot(fig,'서울 경계 내부 위치가 연결된 정류소 표본, 2026.09.21~27. 파란 막대는 알려진 값의 합(하한); 빈칸은 0으로 대체하지 않음.')
fig.tight_layout(rect=[0,.06,1,1]);fig.savefig(FIG/'04_supply_observation.png',bbox_inches='tight');plt.close(fig)

sources = [
 {'name':'서울시 등록인구 통계','provider':'서울특별시','platform':'서울통계·서울열린데이터광장','url':'https://stat.eseoul.go.kr/statHtml/statHtml.do?orgId=201&tblId=DT_201004_O020003&conn_path=I2','period':'2026년 2분기','method':'공개 화면 표 427개 동 값 캡처, 체크섬·자치구/서울 합계 대조','license':'공공누리 제1유형(서울열린데이터광장 메타정보)'},
 {'name':'서울시 버스정류소 위치정보','provider':'서울특별시','platform':'서울열린데이터광장','url':'https://data.seoul.go.kr/dataList/OA-15067/F/1/datasetView.do','period':'20260902','method':'사용자 다운로드 원본 XLSX','license':'공공누리 제1유형'},
 {'name':'서울시 버스노선별 정류소 정보','provider':'서울특별시','platform':'서울열린데이터광장','url':'https://data.seoul.go.kr/dataList/OA-1095/S/1/datasetView.do','period':'20260902','method':'사용자 다운로드 원본 XLSX','license':'공공누리 제1유형, 20261022 실제 페이지 확인'},
 {'name':'노선별 정류장별 총 버스 운행횟수 정보','provider':'서울특별시','platform':'서울열린데이터광장','url':'https://data.seoul.go.kr/dataList/OA-21220/S/1/datasetView.do','period':'20260921~27','method':'사용자 다운로드 ZIP/CSV','license':'공공누리 제1유형, 20261022 실제 페이지 확인'},
 {'name':'노선별 정류장별 승차 인원 정보','provider':'서울특별시','platform':'서울열린데이터광장','url':'https://data.seoul.go.kr/dataList/OA-21219/S/1/datasetView.do','period':'20260921~27','method':'사용자 다운로드 ZIP/CSV','license':'공공누리 제1유형, 20261022 실제 페이지 확인'},
 {'name':'지하철역_GEOM (역사마스터)','provider':'서울특별시 TAIMS','platform':'T Data 서울교통빅데이터플랫폼','url':'https://t-data.seoul.go.kr/dataprovide/trafficdataviewfile.do?data_id=36','period':'다운로드 20261022, 개별 레코드 기준일 없음','method':'공식 다운로드 버튼 CSV','license':'저작권자표시(BY), 변경·2차저작물 허용'},
 {'name':'대한민국 행정동 경계 가공본','provider':'SGIS 원자료 / vuski 가공','platform':'GitHub vuski/admdongkor','url':'https://github.com/vuski/admdongkor/blob/master/ver20260701/HangJeongDong_ver20260701.geojson','period':'20260701','method':'공개 raw 다운로드, 서울 427개 추출','license':'SGIS 공공누리 제1유형 + 가공물 CC BY 4.0'},
]
(OUT/'sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
manifest = []
for name in ['seoul_population_2026Q2_DOM_capture.txt','HangJeongDong_ver20260701.geojson','서울시버스정류소위치정보(20260902).xlsx','서울시버스노선별정류소정보(20260902).xlsx','tpss_sta_route_hturn_2026.09.21-09.27.csv','tpss_sta_route_hpasngr_2026.09.21-09.27.csv','지하철역_GEOM (역사마스터).csv']:
    p=RAW/name;manifest.append({'file':name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(OUT/'raw_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in stats.items() if k not in ['top10','metro_lines']},ensure_ascii=False,indent=2))
print(g.nlargest(10,'screen_index')[['adm_nm','elderly_share','bus300_area_coverage','screen_index','top10_scenario_count']].to_string(index=False))
