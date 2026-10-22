"""Fill the visual structure of the supplied official HWP report form.
Reconstructed from original table, labels and embedded logos; original HWP is preserved.
"""
from pathlib import Path
import json,csv,os
from copy import deepcopy
from docx import Document
from docx.shared import Mm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
R=Path(__file__).resolve().parents[1];O=R/'output/submission';D=R/'output/final_analysis'
r=json.loads((D/'analysis_results.json').read_text());sources=json.loads((D/'sources.json').read_text())
doc=Document();sec=doc.sections[0]
sec.page_width=Mm(210);sec.page_height=Mm(297)
sec.left_margin=sec.right_margin=Mm(30);sec.top_margin=Mm(22);sec.bottom_margin=Mm(20)
sec.footer_distance=Mm(10)
normal=doc.styles['Normal'];normal.font.name='Arial Unicode MS';normal.font.size=Pt(10)
normal.element.rPr.rFonts.set(qn('w:eastAsia'),'Arial Unicode MS')
normal.paragraph_format.space_after=Pt(3);normal.paragraph_format.line_spacing=1.08
footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
footer.add_run('- ');field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field);footer.add_run(' -')
for x in footer.runs:x.font.size=Pt(9)

def fmt(p,size=10,bold=False,align=None):
 if align is not None:p.alignment=align
 p.paragraph_format.space_after=Pt(3);p.paragraph_format.space_before=Pt(0);p.paragraph_format.line_spacing=1.08
 for rr in p.runs:
  rr.font.name='Arial Unicode MS';rr.font.size=Pt(size if size<=9 else size-.5);rr.font.bold=bold;rr.font.color.rgb=RGBColor(0,0,0)
  rr._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Arial Unicode MS')
 return p

def text(cell,t,size=10,bold=False):
 p=cell.paragraphs[0] if len(cell.paragraphs)==1 and not cell.paragraphs[0].text and not cell.paragraphs[0].runs else cell.add_paragraph()
 p.add_run(t);fmt(p,size,bold);return p

def borders(t,visible=True):
 pr=t._tbl.tblPr;b=OxmlElement('w:tblBorders')
 for edge in ['top','left','bottom','right','insideH','insideV']:
  e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single' if visible else 'nil');e.set(qn('w:sz'),'5');e.set(qn('w:color'),'000000');b.append(e)
 pr.append(b)
 margins=OxmlElement('w:tblCellMar')
 for edge in ['top','left','bottom','right']:
  e=OxmlElement('w:'+edge);e.set(qn('w:w'),'75' if visible else '0');e.set(qn('w:type'),'dxa');margins.append(e)
 pr.append(margins)

def outer():
 t=doc.add_table(rows=0,cols=2);t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False;t.columns[0].width=Mm(22);t.columns[1].width=Mm(128);borders(t);return t

def row(t,label):
 cs=t.add_row().cells;cs[0].width=Mm(22);cs[1].width=Mm(128)
 for c in cs:c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
 sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'F2F2F2');cs[0]._tc.get_or_add_tcPr().append(sh)
 p=cs[0].paragraphs[0];p.add_run(label);fmt(p,10,False,WD_ALIGN_PARAGRAPH.CENTER)
 # Source rows expand to hold completed content, never fixed-height clipping.
 return cs[1]

def nested(cell,rows,widths,size=8.7):
 if not cell.paragraphs[0].text:
  pp=cell.paragraphs[0];pp.paragraph_format.space_after=Pt(0);pp.paragraph_format.line_spacing=Pt(1);pp.add_run().font.size=Pt(1)
 t=cell.add_table(rows=len(rows),cols=len(rows[0]));t.autofit=False;t.alignment=WD_TABLE_ALIGNMENT.CENTER
 for j,w in enumerate(widths):t.columns[j].width=Mm(w)
 borders(t)
 for xx in t._tbl.tblPr.findall('.//'+qn('w:tblCellMar')+'/*'):
  xx.set(qn('w:w'),'35')
 for i,rr in enumerate(rows):
  for j,v in enumerate(rr):
   c=t.cell(i,j);c.width=Mm(widths[j]);p=c.paragraphs[0];p.add_run(str(v));fmt(p,size,i==0)
   c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   if i==0:
    sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'F2F2F2');c._tc.get_or_add_tcPr().append(sh)
 return t

def newpage():
 p=doc.add_paragraph();p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0);p.paragraph_format.line_spacing=Pt(1);rr=p.add_run();rr.font.size=Pt(1)
 from docx.enum.text import WD_BREAK
 rr.add_break(WD_BREAK.PAGE)
# Original logos and title block.
t=doc.add_table(rows=1,cols=2);t.autofit=False;t.columns[0].width=Mm(75);t.columns[1].width=Mm(75);borders(t,False)
t.cell(0,0).paragraphs[0].add_run().add_picture(str(R/'data/template_assets/hankyoreh_logo.png'),width=Mm(22))
p=t.cell(0,1).paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.RIGHT;p.add_run().add_picture(str(R/'data/template_assets/foundation_logo.png'),width=Mm(43))
p=doc.add_paragraph();p.paragraph_format.space_after=Pt(11);p.paragraph_format.space_before=Pt(6)
p.add_run('- AI와 함께하는 교통문제 해결을 위한 데이터 분석 공모전 -\n');p.add_run('분석보고서')
fmt(p,12,True,WD_ALIGN_PARAGRAPH.CENTER)
b=OxmlElement('w:pBdr')
for e in ['top','bottom']:
 x=OxmlElement('w:'+e);x.set(qn('w:val'),'single');x.set(qn('w:sz'),'30');x.set(qn('w:color'),'85B77C');x.set(qn('w:space'),'5');b.append(x)
p._p.get_or_add_pPr().append(b)
t=outer();text(row(t,'이름/팀명'),'백진우')
text(row(t,'주제'),'같은 서울, 다른 이동권: 고령인구와 버스 접근 공백의 중첩을 통한 개선 우선지역 분석',10)
c=row(t,'분석 배경\n및 목적')
text(c,'고령자의 일상 이동을 지원하려면 정류소 수와 함께 주거지의 접근 여건을 살펴야 한다. 서울 427개 동의 고령비율과 버스 접근 공백이 중첩되는 지역을 찾아 현장검토 우선순위를 제시한다. 이동권 개선과 환경 부담을 함께 검토할 근거를 마련하는 것이 목적이다.',9.5)
text(c,'산지·공원도 포함된 면적 공백은 주민의 불편과 구분한다. 승용차 거리·전환율 자료가 없어 탄소감축량은 산출하지 않았다.',9.5)
c=row(t,'활용\n데이터')
text(c,'인구·시설·경계로 접근 격차를 비교하고, 운행·승차량으로 결측을 점검했다. 지하철역은 대체시설 보완 검토에 사용했다.',9)
# Preserve the original source header merge: 출처 → 플랫폼(명), URL.
rows=[['활용 데이터(명)','제공기관(명)','출처',''],['','','플랫폼(명)','URL']]
short=[source['name'] for source in sources]
providers=['서울특별시']*5+['서울특별시 TAIMS','SGIS 원자료 / vuski 가공']
platforms=['서울통계']+['서울 열린데이터광장']*4+['T Data','GitHub vuski/admdongkor']
for i,source in enumerate(sources):rows.append([short[i],providers[i],platforms[i],source['url']])
nt=nested(c,rows,[29,24,23,48],8)
nt.cell(0,2).merge(nt.cell(0,3));nt.cell(0,0).merge(nt.cell(1,0));nt.cell(0,1).merge(nt.cell(1,1))

newpage();t=outer();c=row(t,'분석과정\n및 방법')
text(c,'1. 원본 확인과 데이터 연결',10,True)
text(c,'2026년 인구 2분기·경계 7/1·버스시설 9/2·운행/승차 9/21~27을 사용했다. 지하철역은 10/22 확보했으며 개별 기준일은 미제공이다.',9)
text(c,'인구와 경계 427개 동을 1:1 연결했다. 점·가운뎃점 등 11개 명칭 차이는 대응표에 남겼다. 공식 인구 표의 동·구·서울 합계를 대조했다. 인구 XLSX 내보내기가 작동하지 않아 공개 표로 확보했다고 기록했다.')
text(c,'버스 위치에서 선착장 8개를 제외한 11,228개를 사용했다. 서울 경계 안은 11,211개, 밖은 17개(0.15%)이며 이중 귀속은 없다. 경위도 값은 EPSG:4326으로 해석하고 면적은 EPSG:5179에서 계산했다. 공식 좌표계 설명 충돌은 미해결이다.')
text(c,'2. 접근 공백과 우선 검토지수',10,True)
text(c,'정류소별 300m 직선 반경의 합집합을 동 경계와 교차했다. 동 밖 가까운 정류소도 포함한다. 접근 공백 U = 1 − (반경 내 동 면적 / 전체 동 면적), 고령비율 E = 65세 이상 인구 / 전체 등록인구로 정의했다.')
text(c,'우선 검토지수 = 100 × [0.5 × E의 백분위 순위 + 0.5 × U의 백분위 순위]. 두 지표를 같은 비중으로 비교하기 위해 동일가중을 기준으로 삼았다. 반경 200/300/400m·고령비율 가중치 0.3/0.5/0.7의 9개 조건과 지하철역 500m 추가 조건을 검토했다. 수치오차로 인한 순위 차이를 줄이도록 면적 비율을 소수 12자리로 반올림했다.')
text(c,'3. 관측 공급과 통계 검토',10,True)
text(c,'날짜·노선·정류소·순번으로 승차 597,021행이 공급 자료에 100% 연결됐다. 그러나 운행횟수가 빈칸이면서 같은 시간 승차량이 양수인 사례는 14,509건이었다. 빈칸은 결측으로 유지하고 공급은 종합지수에서 제외했다. 정류소 서비스 횟수의 합은 고유 차량 수가 아니다.')
text(c,'고령비율과 접근 공백은 Spearman 상관으로, 접근 공백의 공간 패턴은 인접 동 기반 Moran’s I로 검토했다. 상방 단측 순열검정은 999회·시드 20261022를 사용했으며 인과효과나 개별 지역의 취약 판정으로 해석하지 않았다.')
text(c,'4. 조건부 정류소 보완 시나리오',10,True)
text(c,'상위 10개 동에서 같은 동의 연속 경유정류소 간 직선 간격이 600~1,200m이고 중점이 모든 기존 정류소의 300m 밖인 쌍을 추렸다. 원본 내부ID 쌍으로 중복을 제거했다. 거리 기준은 연구상 가정이다. 추가 면적의 중복을 한 번만 세는 MCLP를 이진 혼합정수계획으로 계산하고 합집합 면적과 대조했다. 도로·주거지·정차 안전은 확인하지 못했다.')
c=row(t,'AI 기술\n활용')
text(c,'사용 서비스: OpenAI Codex. 연구 질문, 데이터 결합·전처리·공간·통계·민감도 분석 코드 작성과 실행, 가상 후보·입지모형 구성, 시각화, 결과 해석·정책 초안·보고서 작성에 활용했다. AI 작성·실행 검사로 키 중복·집계·지수 재계산·기존 분석 재현성을 대조했다. 머신러닝 학습·승객 증가 예측은 하지 않았다.',9.5)
text(c,'주요 프롬프트 원문: “공식 설명이 아니라 실제 파일 헤더를 기준으로 보고해”, “ID를 임의로 정제해서 결합률을 높이지 마”, “빈칸의 공식 의미가 확인되지 않으면 결측값으로 유지한다.” 상세 AI 활용 기록은 별도 첨부했다.',9.5)
newpage();t=outer();c=row(t,'분석 내용\n및 결과')
text(c,'1. 서울 평균과 동별 차이',10,True)
text(c,f'서울 등록인구 9,560,471명 중 고령인구는 1,962,133명이다. 동별 버스 300m 면적 커버리지 중앙값은 {r["median_bus300_coverage"]*100:.2f}%, 서울 면적 가중값은 {r["area_weighted_bus300_coverage"]*100:.2f}%였다. 동별 고령비율·접근 공백이 모두 중앙값 이상인 곳은 {r["high_age_high_gap_count"]}개 동이다. 면적이 큰 비주거 공간의 영향이 있어 어느 값도 주민 접근률을 뜻하지 않는다.')
text(c,'2. 현장검토 우선후보',10,True)
rr=[['자치구·동','고령인구','고령비율','버스 면적\n커버리지','검토지수','상위10\n유지 조건']]
for x in r['top10']:rr.append([x['district']+' '+x['dong'],f"{x['elderly']:,}",f"{x['elderly_share']*100:.1f}%",f"{x['bus300_area_coverage']*100:.1f}%",f"{x['screen_index']:.1f}",f"{x['top10_scenario_count']}/9"])
nested(c,rr,[36,18,18,20,15,17],8.5)
text(c,'상위 10개 동의 고령인구 합계 59,961명은 해당 동의 전체 고령인구이며 접근 공백 거주자나 사업 수혜자 수가 아니다. 지수는 법정 취약 기준이 아닌 상대적 현장검토 지표다.',9)
text(c,'3. 조건 변경과 공간 검토',10,True)
text(c,'9개 거리·가중치 조건에서 기준 상위 10개와의 중첩은 8~10개였다. 도봉1동·우이동·방화3동·상계3·4동·관악구 삼성동은 모든 조건에 포함됐다. 지하철역 500m를 추가해도 상위 10개 집합은 유지됐다. 같은 면적 분모를 공유하므로 이 안정성이 비주거지 편향이나 실제 보행 제약을 해소하지는 않는다.')
text(c,f'고령비율과 접근 공백의 Spearman ρ={r["spearman_age_gap_rho"]:.3f}으로 관계는 약했다. 접근 공백 Moran’s I={r["moran_I_gap300"]:.3f}, 순열 p={r["moran_upper_tail_permutation_p_999"]:.3f}였다. 공간적 군집 가능성을 보였으나 인과관계나 개별 동의 유의한 취약성을 입증하지 않는다.')
text(c,'4. 공급 기록의 범위',10,True)
text(c,'서울 내부 위치에 연결된 승차·공급은 각각 305,961행이었다. 내부 정류소 11,211개 중 11,176개(99.69%)에서 기간 내 공급 기록이 있었으나, 시간별 셀 기록 비율은 전체 72.39%, 06~21시 89.66%였다. 기록 존재율과 시간별 완전성을 구분해야 한다.')
newpage();t=outer();c=row(t,'정책제안\n및 기대효과')
text(c,'1. 기존 노선 내 정류소 보완의 조건부 결과',10,True)
text(c,'간격 600~1,200m인 연속 경유 쌍 4,494개 중 양 끝이 같은 대상 동인 쌍은 16개, 기존 접근 범위 밖 중점은 2개였다. 내부ID 쌍 중복 제거 후 방화2동의 가상 중점 1개(HYP_001)가 남았다. 노선 6647의 개화동상사마을종점–부석마을.상사마을입구 사이 중점이며 설치 가능 위치로 확인한 것은 아니다.',9.5)
nested(c,[['범위','기존 커버율','가정 후 커버율','변화폭'],['방화2동','37.6465%','39.5508%','+1.9043%p'],['대상 10개 동 합계','30.6242%','30.8973%','+0.2731%p']],[37,28,31,28],9)
text(c,'추가 면적은 약 117,721m², 대상 전체 기존 미커버 면적 대비 감소율은 0.3937%다. 최대 1·3·5개 조건 모두 후보 1개가 선택되어 다수 입지의 조합 효과는 비교할 수 없었다. 실제 운행 제공을 가정한 면적 변화이며 승객 증가·수혜 고령인구·실제 보행 접근률이 아니다.',9.5)
text(c,'2. 주민 참여와 현장 확인을 통한 정책 구체화',10,True)
text(c,'반복 선정된 동부터 고령 주민과 함께 자주 가는 목적지, 통행 포기 경험, 경사·횡단 구간을 확인한다. 도봉1동·우이동은 비주거지와 주거지의 공백을 구분하고, 수서동은 정류소·역 출입구까지의 보행 제약을 우선 점검한다. 이를 바탕으로 보행환경 개선, 기존 노선·정류소 보완, 연결교통을 비용·운행시간·중복 측면에서 비교한다.',9.5)
text(c,'개선안은 현장 여건을 확인한 뒤 소규모로 시행하고 유사 비교지역과 함께 시행 전후의 보행·대기·환승시간, 통행 포기, 실제 이용 변화와 운영비를 평가한다. 기대효과는 이동 불편을 줄이는 데 있으며, 이번 자료로 사업 효과를 확정하지 않는다.',9.5)
text(c,'3. 환경 부담을 함께 평가하는 조건',10,True)
text(c,'탄소 순감축량 = 회피된 승용차 차량주행거리×배출계수 − 추가 버스 운행거리×배출계수. 수단전환·거리 자료가 없어 CO₂는 계산하지 않았다. 산지·하천의 면적 공백을 채우기 위한 시설 확충을 목표로 삼지 않고, 주민 이동의 개선과 추가 운행의 환경 부담을 함께 평가한다.',9.5)
text(c,'한계: 직선 반경은 경사·안전·보행시간을 반영하지 않는다. 인구·경계·시설·운행 시점 차이, 좌표 설명 충돌, 공급 결측, 지하철 개별 기준일·출입구 부재가 남아 있다. 활용 범위는 현장검토 우선순위와 조건부 면적 변화다.',9)
c=row(t,'분석도구\n및 참고문헌')
text(c,'도구: Python(pandas, NumPy, GeoPandas, Shapely, pyproj, SciPy, Matplotlib, openpyxl), DOCX 작성·PDF 변환 도구. 데이터 출처는 활용 데이터 표 참조. 원본 SHA256·대응표·전체 지표·검증 코드와 실행 순서는 재현 ZIP에 수록했다.',8.7)
text(c,'경계 저작자표시: 통계청 SGIS(https://sgis.kostat.go.kr) 공공누리 제1유형 행정동 경계 가공본. 가공·배포 vuski/admdongkor, CC BY 4.0. 원자료 직접 다운로드가 아닌 가공본이며 서울 영역을 추출·지표 결합했다. 서울시 원본의 공공누리 제1유형 및 T Data 저작자표시 조건을 보존한다.',8.7)
text(c,'문제 설정 참고: (재)숲과나눔 공식 소개 https://koreashe.org/donation/ (분석 효과의 근거와 구분). 코드 열람 URL: 미등록. 제출 전 GitHub 또는 클라우드 열람 링크를 추가해야 한다.',8.7)
newpage();t=outer();c=row(t,'분석결과\n이미지\n(필수)')
text(c,'그림 1. 서울 427개 동의 버스 면적 접근성·고령비율·우선 검토지수',9,True)
p=c.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.add_run().add_picture(str(D/'figures/01_three_maps.png'),width=Mm(123))
text(c,'면적 지표에는 산지·하천·공원 등이 포함된다. 경계는 SGIS 원자료 기반 vuski/admdongkor 가공본이며 주민 단위 접근률이나 확정 취약지역을 나타내지 않는다.',8.5)
text(c,'그림 2. 고령비율과 접근 공백의 관계',9,True)
p=c.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.add_run().add_picture(str(D/'figures/02_quadrants.png'),width=Mm(112))
text(c,'두 축의 동별 중앙값을 기준으로 구분했다. 점 크기는 고령인구수이며 법정·절대적 취약 기준이 아니다.',8.5)
text(c,'그림 3. 가상 정류소 추가 시나리오',9,True)
p=c.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.add_run().add_picture(str(R/'output/location_simulation/01_hypothetical_locations.png'),width=Mm(80))
text(c,'파랑: 기존 300m 범위, 주황: 추가 면적, 별: 합성 중점. 배경선은 행정동 경계다. 실제 도로선형·정차 안전·주거지 여부는 미확인이며 설치 추천 위치가 아니다.',8.5)
# Remove empty source/merged cell paragraphs without collapsing visible content.
for tt in doc.tables:
 for ce in [ce for rw in tt.rows for ce in rw.cells]:
  for pp in ce.paragraphs:
   if not pp.text and not pp._p.xpath('.//w:drawing'):
    pp.paragraph_format.space_after=Pt(0);pp.paragraph_format.line_spacing=Pt(1);pp.add_run().font.size=Pt(1)
# Keep data/body paragraphs inside cells flowing together without orphaned source labels.
for table in doc.tables:
 for rw in table.rows:
  for ce in rw.cells:
   for pp in ce.paragraphs:
    pp.paragraph_format.widow_control=True
# Exactly original form labels, content is completed and the original instruction rows omitted.
doc.core_properties.title='AI와 함께하는 교통문제 해결을 위한 데이터 분석 공모전 분석보고서'
doc.core_properties.author='백진우'
url=os.environ.get('SUBMISSION_CODE_URL','https://github.com/BeakJW/seoul-elderly-transit-access')
if url:
 for tt in doc.tables:
  for rr in tt.rows:
   for ce in rr.cells:
    for pp in ce.paragraphs:
     for run in pp.runs:
      if '코드 열람 URL: 미등록.' in run.text:
       run.text=run.text.replace('코드 열람 URL: 미등록. 제출 전 GitHub 또는 클라우드 열람 링크를 추가해야 한다.','코드 열람 URL: '+url)
out=O/'백진우_분석보고서.docx';doc.save(out)
print(out)
