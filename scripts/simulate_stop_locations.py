"""Conditional hypothetical stop-location MCLP, exact polygon-area evaluation.

Candidates are synthetic midpoints of observed consecutive route-stop pairs,
NOT verified roadside stopping sites. No ridership, population exposure or
carbon effect is predicted. All figures are conditional geometric scenarios.
"""
from pathlib import Path
import json,os,hashlib
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import lil_matrix
from shapely.geometry import Point
from shapely.ops import unary_union,polygonize
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw';OUT=ROOT/'output/location_simulation';OUT.mkdir(parents=True,exist_ok=True)
FONT=os.environ.get('KOREAN_FONT','/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
if Path(FONT).exists():
    matplotlib.font_manager.fontManager.addfont(FONT)
    plt.rcParams['font.family']=FontProperties(fname=FONT).get_name()
plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'savefig.dpi':200})
def export(df,name):df.to_csv(OUT/name,index=False,encoding='utf-8-sig')

g=gpd.read_file(ROOT/'output/final_analysis/dong_screening.geojson').to_crs(5179)
top=g.sort_values('screen_index',ascending=False).head(10).copy()
target=top.geometry.union_all()
st=pd.read_excel(RAW/'서울시버스정류소위치정보(20260902).xlsx',dtype=str,keep_default_na=False)
st=st.loc[st['정류소타입'].ne('한강선착장')].copy()
bus=gpd.GeoDataFrame(st,geometry=gpd.points_from_xy(st['X좌표'].astype(float),st['Y좌표'].astype(float)),crs=4326).to_crs(5179)
assert not bus.NODE_ID.duplicated().any()
coords={n:np.array([p.x,p.y]) for n,p in zip(bus.NODE_ID,bus.geometry)}
assignment=pd.read_csv(ROOT/'output/final_analysis/bus_stop_boundary_assignment.csv',dtype=str,keep_default_na=False)
node_adm=assignment.set_index('NODE_ID')['adm_cd2'].to_dict()
node_name=bus.set_index('NODE_ID')['정류소명'].to_dict()
bridge=pd.read_excel(RAW/'서울시버스노선별정류소정보(20260902).xlsx',dtype=str,keep_default_na=False)
bridge['sequence_number']=pd.to_numeric(bridge['순번'],errors='raise')
assert not bridge.duplicated(['ROUTE_ID','sequence_number']).any()
bridge=bridge.sort_values(['ROUTE_ID','sequence_number'])
bridge['next_route']=bridge.ROUTE_ID.shift(-1)
bridge['next_node']=bridge.NODE_ID.shift(-1)
bridge['next_seq']=bridge.sequence_number.shift(-1)
bridge['next_name']=bridge['정류소명'].shift(-1)
adjacent=bridge.ROUTE_ID.eq(bridge.next_route)&bridge.next_seq.eq(bridge.sequence_number+1)
counts={'raw_route_stop_rows':len(bridge),'consecutive_same_route_pairs':int(adjacent.sum())}
pairs=bridge.loc[adjacent].copy()
pairs=pairs.loc[pairs.NODE_ID.isin(coords)&pairs.next_node.isin(coords)].copy()
counts['pairs_both_nodes_in_road_stop_master']=len(pairs)
pairs['gap_m']=[float(np.linalg.norm(coords[a]-coords[b])) for a,b in zip(pairs.NODE_ID,pairs.next_node)]
pairs=pairs.loc[pairs.gap_m.between(600,1200)].copy()
counts['pairs_gap_600_to_1200m']=len(pairs)
pairs['from_adm']=pairs.NODE_ID.map(node_adm)
pairs['to_adm']=pairs.next_node.map(node_adm)
pairs=pairs.loc[pairs.from_adm.eq(pairs.to_adm)&pairs.from_adm.isin(set(top.adm_cd2))].copy()
counts['pairs_both_endpoints_same_target_dong']=len(pairs)
tree=cKDTree(np.array(list(coords.values())))
records=[]
for _,r in pairs.iterrows():
    xy=(coords[r.NODE_ID]+coords[r.next_node])/2
    point=Point(xy)
    if not target.covers(point):continue
    near=float(tree.query(xy)[0])
    if near<=300:continue
    records.append({'route_id':r.ROUTE_ID,'route_name':r['노선명'],'from_node_id':r.NODE_ID,'to_node_id':r.next_node,'from_stop':r['정류소명'],'to_stop':r.next_name,'from_sequence':int(r.sequence_number),'to_sequence':int(r.next_seq),'gap_m':r.gap_m,'adm_cd2':r.from_adm,'x_5179':float(xy[0]),'y_5179':float(xy[1]),'nearest_existing_stop_m':near,'pair_key':'|'.join(sorted([r.NODE_ID,r.next_node]))})
provenance=pd.DataFrame(records)
counts['route_pairs_midpoint_outside_all_bus300_buffers']=len(provenance)
if provenance.empty:raise RuntimeError('No candidates pass declared rules. Do not loosen rules to create a result.')
unique=provenance.sort_values(['pair_key','route_id','from_sequence']).drop_duplicates('pair_key').copy()
unique=unique.sort_values(['adm_cd2','pair_key']).reset_index(drop=True)
unique['candidate_id']=[f'HYP_{i+1:03d}' for i in range(len(unique))]
unique['source_route_ids']=unique.pair_key.map(provenance.groupby('pair_key')['route_id'].agg(lambda a:'|'.join(sorted(set(a)))))
provenance=provenance.merge(unique[['pair_key','candidate_id']],on='pair_key',validate='many_to_one')
export(provenance,'candidate_source_route_pairs.csv')
candidates=gpd.GeoDataFrame(unique,geometry=gpd.points_from_xy(unique.x_5179,unique.y_5179),crs=5179)
counts['unique_unordered_endpoint_pairs']=len(candidates)
baseline_union=bus.buffer(300,resolution=16).union_all()
baseline=target.intersection(baseline_union)
uncovered=target.difference(baseline_union)
gain_polygons=[p.buffer(300,resolution=16).intersection(uncovered) for p in candidates.geometry]
assert all(p.area>0 for p in gain_polygons)

# Partition candidate gains into non-overlapping polygon atoms. An atom's full
# area shares the same candidate-membership set, so no raster approximation is used.
faces=[];members=[]
for face in polygonize(unary_union([p.boundary for p in gain_polygons])):
    point=face.representative_point()
    indices=[i for i,p in enumerate(gain_polygons) if p.covers(point)]
    if indices and face.area>0:
        faces.append(face);members.append(indices)
gain_union=unary_union(gain_polygons)
partition_union=unary_union(faces)
partition_error=partition_union.symmetric_difference(gain_union).area
assert partition_error<max(1e-4,gain_union.area*1e-8),partition_error
assert abs(sum(p.area for p in faces)-partition_union.area)<max(1e-4,gain_union.area*1e-8)
N=len(candidates);M=len(faces)
xy=np.array(list(zip(candidates.x_5179,candidates.y_5179)))
conflicts=[(i,j) for i in range(N) for j in range(i+1,N) if np.linalg.norm(xy[i]-xy[j])<300]
objective=np.r_[np.zeros(N),-np.array([p.area/1e6 for p in faces])]
rows=M+1+len(conflicts)
A=lil_matrix((rows,N+M),dtype=float)
upper=np.zeros(rows)
for j,ids in enumerate(members):
    A[j,N+j]=1
    for i in ids:A[j,i]=-1
A[M,:N]=1
for row,(i,j) in enumerate(conflicts,start=M+1):A[row,i]=A[row,j]=1;upper[row]=1
solver_results=[];selected_rows=[];dong_rows=[]
rng=np.random.default_rng(20261022)
for budget in [1,3,5]:
    upper[M]=budget
    opt=milp(objective,integrality=np.ones(N+M),bounds=Bounds(np.zeros(N+M),np.ones(N+M)),constraints=LinearConstraint(A.tocsr(),np.full(rows,-np.inf),upper),options={'time_limit':45,'mip_rel_gap':1e-8})
    if opt.x is None:raise RuntimeError(f'No feasible solver solution for budget {budget}: {opt.message}')
    selected=np.flatnonzero(opt.x[:N]>.5).tolist()
    exact=unary_union([gain_polygons[i] for i in selected])
    solver_area=float(-opt.fun*1e6)
    assert abs(solver_area-exact.area)<max(.01,exact.area*1e-6),(solver_area,exact.area)
    assert len(selected)<=budget
    assert all(np.linalg.norm(xy[i]-xy[j])>=300 for i in selected for j in selected if i<j)
    # Uniform random subsets conditioned on the same spacing constraint.
    random_gains=[];attempts=0
    while len(random_gains)<200 and attempts<50000:
        attempts+=1
        ids=rng.choice(N,size=min(budget,N),replace=False).tolist()
        if any(np.linalg.norm(xy[i]-xy[j])<300 for i in ids for j in ids if i<j):continue
        random_gains.append(unary_union([gain_polygons[i] for i in ids]).area)
    solver_results.append({'budget_max_sites':budget,'selected_site_count':len(selected),'selected_candidates':'|'.join(candidates.iloc[selected].candidate_id),'solver_status':int(opt.status),'solver_message':str(opt.message),'proven_optimal':bool(opt.status==0),'mip_gap':float(opt.mip_gap) if opt.mip_gap is not None else None,'baseline_coverage_pct':100*baseline.area/target.area,'after_coverage_pct':100*(baseline.area+exact.area)/target.area,'gain_percentage_points':100*exact.area/target.area,'gain_relative_to_baseline_pct':100*exact.area/baseline.area,'uncovered_area_reduction_pct':100*exact.area/uncovered.area,'additional_area_m2':float(exact.area),'objective_area_m2':solver_area,'random_valid_draws':len(random_gains),'random_median_gain_m2':float(np.median(random_gains)) if random_gains else None,'random_95pct_gain_m2':float(np.quantile(random_gains,.95)) if random_gains else None})
    for i in selected:selected_rows.append({'budget':budget,**candidates.drop(columns='geometry').iloc[i].to_dict()})
    for _,r in top.iterrows():
        delta=exact.intersection(r.geometry).area
        before=r.geometry.intersection(baseline_union).area
        dong_rows.append({'budget':budget,'adm_cd2':r.adm_cd2,'adm_nm':r.adm_nm,'baseline_coverage_pct':100*before/r.geometry.area,'after_coverage_pct':100*(before+delta)/r.geometry.area,'gain_percentage_points':100*delta/r.geometry.area,'additional_area_m2':delta})
    export(pd.DataFrame({'budget':budget,'draw':np.arange(len(random_gains))+1,'additional_area_m2':random_gains}),f'random_reference_budget{budget}.csv')
    if budget==5:best5=selected;new5=exact

single=[]
for i,r in candidates.iterrows():
    local=g.loc[g.adm_cd2.eq(r.adm_cd2)].iloc[0]
    local_gain=gain_polygons[i].intersection(local.geometry).area
    single.append({'candidate_id':r.candidate_id,'target_total_additional_area_m2':gain_polygons[i].area,'home_dong_additional_area_m2':local_gain,'home_dong_gain_percentage_points':100*local_gain/local.geometry.area})
candidates=candidates.merge(pd.DataFrame(single),on='candidate_id',validate='one_to_one')
candidates['road_alignment_verified']=False
candidates['stopping_safety_verified']=False
candidates['residential_land_verified']=False
candidates['new_bus_service_assumed']=True
lonlat=candidates.to_crs(4326)
candidates['longitude']=lonlat.geometry.x;candidates['latitude']=lonlat.geometry.y
export(candidates.drop(columns='geometry'),'hypothetical_candidates.csv')
lonlat.to_file(OUT/'hypothetical_candidates.geojson',driver='GeoJSON')
export(pd.DataFrame(solver_results),'installation_scenarios.csv')
export(pd.DataFrame(selected_rows),'selected_candidates_by_budget.csv')
export(pd.DataFrame(dong_rows),'dong_before_after.csv')

result={'method':'Maximal covering location problem over exact nonoverlapping improvement polygons; binary MILP via SciPy HiGHS. Conditional on finite hypothetical candidates, not an unconstrained site optimum.',
 'target_scope':'Previously selected top10 review-candidate dongs; not all Seoul, not resident-weighted.',
 'target_dongs':top.adm_nm.tolist(),'filters':counts,'candidate_generation_rules':{'consecutive_sequence':True,'both_endpoints_in_road_stop_master':True,'straight_line_gap_m':[600,1200],'both_endpoints_same_target_dong':True,'midpoint_inside_target_union':True,'midpoint_nearest_existing_stop_m_gt':300,'candidate_pair_dedup':'unordered original endpoint NODE_ID pair','minimum_selected_site_separation_m':300},
 'assumptions':['A hypothetical added stop is served by buses. Actual service provision, route time and ridership response are not estimated.','A 300m straight-line radius represents a geometric access zone, not walking-network reach.','Midpoint candidates are synthetic and may not lie on a real road. Road alignment, stopping safety, residential use and exclusion of parks/water have NOT been verified.'],
 'target_area_m2':float(target.area),'baseline_covered_area_m2':float(baseline.area),'uncovered_area_m2':float(uncovered.area),'coverage_atoms':M,'candidate_spacing_conflicts':len(conflicts),'partition_error_m2':float(partition_error),'scenarios':solver_results,'ridership_prediction_executed':False,'benefiting_population_estimated':False,'carbon_estimated':False,
 'checks':{'partition_matches_gain_union':True,'nonoverlapping_atoms':True,'solver_objective_matches_exact_union':True,'budget_and_spacing_satisfied':True,'all_budget_solutions_proven_optimal':all(x['proven_optimal'] for x in solver_results)},
 'source_files':['서울시버스정류소위치정보(20260902).xlsx','서울시버스노선별정류소정보(20260902).xlsx','output/final_analysis/dong_screening.geojson','output/final_analysis/bus_stop_boundary_assignment.csv']}
(OUT/'simulation_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

# Three local panels show original stops, hypothetical location and incremental area.
panel_count=min(3,len(best5))
fig,axs=plt.subplots(1,panel_count,figsize=(6*panel_count,5),squeeze=False)
axs=axs.ravel()
for ax,i in zip(axs,best5[:3]):
    r=candidates.iloc[i];point=r.geometry;window=point.buffer(850).envelope
    nearby=g.loc[g.intersects(window)]
    gpd.GeoSeries([baseline_union.intersection(window)],crs=5179).plot(ax=ax,color='#b8d9e8',edgecolor='none')
    gpd.GeoSeries([gain_polygons[i]],crs=5179).plot(ax=ax,color='#eea755',edgecolor='#bf6323',alpha=.85)
    nearby.boundary.plot(ax=ax,color='#77838b',linewidth=.7)
    bus.loc[bus.intersects(window)].plot(ax=ax,color='#326783',markersize=8)
    gpd.GeoSeries([point],crs=5179).plot(ax=ax,color='#c83f3f',marker='*',markersize=130)
    local=g.loc[g.adm_cd2.eq(r.adm_cd2)].iloc[0]
    ax.set_title(f'{r.candidate_id} | {local.district} {local.dong}',fontsize=11)
    ax.set_xlim(window.bounds[0],window.bounds[2]);ax.set_ylim(window.bounds[1],window.bounds[3]);ax.set_axis_off()
    ax.text(.02,.02,f'신규 커버 면적 {gain_polygons[i].area/1000:.1f}천 m²',transform=ax.transAxes,fontsize=9)
fig.suptitle('가상 정류소 추가 시나리오 | 도로·정차 가능 여부 미확인',fontsize=15)
fig.text(.02,.025,'파랑: 기존 300m 접근 범위 / 주황: 추가 범위 / 별: 노선 연속 정류소 사이의 가상 중점. 배경 도로가 아니며 설치 확정 위치가 아님.',fontsize=9)
fig.tight_layout(rect=[0,.08,1,.9]);fig.savefig(OUT/'01_hypothetical_locations.png',bbox_inches='tight');plt.close(fig)

fig,ax=plt.subplots(figsize=(8,4))
x=np.arange(3);optvals=np.array([r['additional_area_m2']/1000 for r in solver_results]);rand=np.array([r['random_median_gain_m2']/1000 for r in solver_results])
ax.bar(x-.18,rand,.36,label='같은 후보·간격 조건의 무작위 선택 중앙값',color='#9bb8c7')
ax.bar(x+.18,optvals,.36,label='면적 최대화 조합',color='#e69b46')
ax.set(xticks=x,xticklabels=['최대 1개','최대 3개','최대 5개'],ylabel='추가 커버 면적 (천 m²)',title='추가 개수별 기하학적 개선폭 | 기존 우선후보 10개 동 내')
ax.legend(fontsize=8);ax.grid(axis='y',alpha=.15)
fig.text(.02,.01,'주민 수·승객 증가율이 아님. 도로선형·정차 안전·주거지 검증 전의 조건부 모의실험.',fontsize=8)
fig.tight_layout(rect=[0,.06,1,1]);fig.savefig(OUT/'02_scenario_comparison.png',bbox_inches='tight');plt.close(fig)

lines=['# 가상 정류소 추가에 따른 접근 면적 변화', '', '## 분석 성격', '',result['method'], '', '**설치 확정안이 아니라 실제 노선 정류소 사이를 이용한 기하학적 가상 시나리오다. 도로·주거지·공원/수역·정차 가능성을 확인하지 못했다. 따라서 결과를 실제 설치효과·수혜 고령자 수·승객 증가 예측으로 제시하지 않는다.**', '',
 '## 후보 생성', '', f'연속 경유순번·정류소 내부ID를 확인하고, 양 끝이 같은 우선후보 동에 있으며 직선 간격이 600~1,200m인 쌍을 사용했다. 중점이 모든 기존 정류소의 300m 범위 밖인 경우만 남겼다. 원본 양 끝 ID의 무순서 쌍으로 중복 제거한 후보는 {N}개다. 합성 좌표에는 HYP 식별자를 부여했다. 이 거리 기준은 연구상 가정이며 공식 설치기준이 아니다.', '',
 '## 최적화와 검증', '', f'후보별 추가 면적을 {M}개의 겹치지 않는 영역으로 나눈 뒤 이진 혼합정수선형계획으로 커버 면적을 최대화했다. 최대 1·3·5개, 선택 후보 간 최소 300m를 적용했다. 목적함수와 실제 폴리곤 합집합 면적을 대조했다. “최적”은 이 유한한 후보·제약·면적 목적 내에서만 성립한다. 고령인구 가중 목적함수나 교통망 최적화가 아니다.', '',
 '|최대 추가 개수|기존 커버율|이후 커버율|개선폭(%p)|추가 면적(m²)|미커버 면적 감소율(%)|', '|---:|---:|---:|---:|---:|---:|']
for r in solver_results:lines.append(f"|{r['budget_max_sites']}|{r['baseline_coverage_pct']:.4f}|{r['after_coverage_pct']:.4f}|{r['gain_percentage_points']:.4f}|{r['additional_area_m2']:,.0f}|{r['uncovered_area_reduction_pct']:.4f}|")
lines+=['','## 해석','', '후보가 1개뿐이어서 최대 1·3·5개 조건에서 모두 같은 1개가 선택되었다. 무작위 참조도 동일 후보를 선택하므로 최적화의 우월성이나 다수 설치의 추가효과를 검증할 수 없다. 후보를 늘리기 위해 조건을 사후 완화하지 않았다.', '', '면적 커버리지 개선폭은 이후 비율−이전 비율(%p), 기존 대비 증가율은 추가 면적/기존 커버 면적×100, 공백 감소율은 추가 면적/기존 미커버 면적×100으로 구분한다. 동별 지표는 dong_before_after.csv에 있다. 여러 후보의 중복 범위는 한 번만 센다. 인접 동의 혜택은 목표 10개 동 내부만 계산한다.','', '## 정책 활용의 한계','', '정류소의 표지·시설을 추가하는 것만으로 실제 운행이 생기는 것은 아니다. 운행 제공을 가정했고, 정차·우회·운행시간 변화와 비용·수요를 산출하지 않았다. 현장 적용 전 실제 도로선형, 버스 통행 가능성, 정차 안전·보행 접근·주거지 여부를 확인하여 후보를 다시 구성해야 한다. 현재 가상 후보를 설치 추천 주소로 사용하지 않는다.','', '무작위 비교는 동일한 후보와 제약 내 200개 유효 조합의 참고값이며 실제 정책효과 검증이나 예측모형 성능평가가 아니다. 머신러닝을 추가한 것으로 표현하지 않는다.']
(OUT/'추가분석_설명.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'filters':counts,'candidates':N,'atoms':M,'checks':result['checks'],'scenarios':solver_results},ensure_ascii=False,indent=2))
