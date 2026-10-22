# 백진우 | 같은 서울, 다른 이동권

서울 427개 동의 고령비율과 버스 시설 접근 공백을 비교하는 실제 분석 코드와 입력자료입니다.
보고서의 결과는 현장검토 후보이며, 주민 단위 접근률·실제 취약 확률·탄소감축량이 아닙니다.

## 실행
Python 3.11 이상 환경에 requirements.txt의 패키지를 설치한 뒤 프로젝트 루트에서 순서대로 실행합니다.

```
python -m pip install -r requirements.txt
python scripts/prepare_inputs.py
python scripts/analyze_elderly_access.py
python scripts/verify_common_date_boarding_supply.py
python scripts/verify_final_analysis.py
python scripts/simulate_stop_locations.py
python scripts/build_submission_report.py
```

버스 입력 CSV가 없으면 함께 제공한 공식 ZIP에서 필요한 CSV 하나씩만 풉니다. 기존 CSV는 덮어쓰지 않습니다.
공식 표 양식 DOCX는 build_submission_report.py → build_official_form_report.py로 생성합니다. PDF는 한글 글꼴을 설정한 LibreOffice/Word에서 내보냅니다. macOS에서는 Arial Unicode MS를 사용했습니다. 다른 환경에서는 문서 글꼴을 사용 가능한 한글 글꼴로 바꾸고 5쪽 배치를 확인해야 합니다. 폰트는 라이선스 때문에 재배포하지 않습니다.
지도·통계는 폰트와 무관하게 계산되지만 한글 폰트가 없으면 시각화 글자가 깨질 수 있습니다.

보고서에 실제 코드 열람 링크를 추가할 때는 SUBMISSION_CODE_URL 환경변수에 공개 또는 열람 가능한 URL을 넣고 build_submission_report.py만 다시 실행합니다.
키·로그인 정보는 필요하지 않습니다. 데이터 내려받기는 이미 완료된 입력자료를 재사용합니다.

## 데이터 수집 경위
- 버스 위치·경유정류소 XLSX와 승차·공급 ZIP은 사용자가 공식 사이트에서 받은 원본입니다.
- 행정동 경계는 vuski/admdongkor의 20260701 공개 raw 파일을 브라우저 다운로드로 확보했습니다. SGIS 경계 기반 가공본이며 공식 SGIS 직접 다운로드라고 표현하지 않습니다.
- 인구는 서울통계 DT_201004_O020003의 2026년 2분기 공개 HTML 표에서 읽었습니다. XLSX 내보내기는 작동하지 않아 다운로드했다고 표현하지 않습니다.
- 인구의 화면 전사에는 신설동·용두동 주석번호 뒤 줄바꿈을 공백으로 표시했습니다. 전처리에서 주석번호만 제거한 뒤 화면 원본과 정규화된 427행의 UTF16 코드단위 FNV1a 체크섬 4c6b423d를 대조했고, 모든 25개 자치구와 서울 전체의 인구·고령인구 합계도 대조했습니다.
- 지하철역_GEOM CSV는 T Data 공식 다운로드 버튼으로 확보했습니다. 개별 행의 기준일과 역 출입구 정보는 제공되지 않습니다.
- 입력 파일의 SHA256과 크기는 output/final_analysis/raw_manifest.json에 있습니다.

## 주요 결과와 해석
인구·경계 427개가 1:1로 연결되었습니다. 도로 정류소 11,228개 중 경계 내부 11,211개를 공간 집계했습니다.
기준 정류소 11,176개에 기간 내 공급 기록이 있어 존재 여부 연결률은 99.69%입니다. 시간별 완전성과 다른 지표입니다.
운행횟수 빈칸은 0으로 바꾸지 않습니다. 같은 행·시간 승차가 양수인데 공급이 빈칸인 사례는 14,509건입니다.
정류소 서비스 사건 합은 고유 차량 수가 아닙니다. 관측 공급은 불완전하여 주요 검토지수에 포함하지 않았습니다.
지수는 고령비율과 접근 공백의 백분위 순위를 동일 가중으로 결합했습니다. 반경·가중치 9개 조건으로 점검했습니다.
면적 연산은 EPSG:5179, 경계 저장 출력 GeoJSON은 EPSG:4326입니다. 버스 원문 좌표계 문구의 충돌은 해소되지 않았고 작업상 경위도로 해석한 가정입니다.

## 출력
- dong_screening_all.csv: 전체 427개 동의 지표·순위·관측률
- top10_review_candidates.csv: 현장검토 우선후보 10개 동
- population_boundary_crosswalk.csv: 원본 명칭과 경계 코드의 명시적 대응표
- observed_service_by_dong_date_hour.csv: 기록된 공급 합과 관측·전체 셀 수
- index_sensitivity.csv: 9개 조건의 상위10 중첩과 실제 동 코드
- analysis_results.json, verification_checks.json: 실제 통계와 재계산 검사
- figures/: 결과 지도·사분면·민감도·공급 관측 그림

## 출처와 이용조건
상세한 데이터명·제공기관·플랫폼·URL은 output/final_analysis/sources.json을 참고하세요.
서울시 원본의 공공누리 제1유형 및 T Data의 저작자표시 조건을 보존합니다.
경계 출처: 본 데이터는 통계청 통계지리정보서비스(SGIS, https://sgis.kostat.go.kr)에서 공공누리 제1유형으로 개방한 행정동 경계를 가공한 것이며(가공: vuski/admdongkor, https://github.com/vuski/admdongkor), CC BY 4.0으로 배포됩니다.
공식 제출 양식의 개인정보·서명·동의 입력이나 이메일 접수는 이 코드에서 수행하지 않습니다.

## 추가 조건부 시나리오
output/location_simulation의 결과는 기존 노선 연속 정류소 중점의 가상 300m 범위 계산이다. 후보 1개여서 여러 설치 조합의 최적화 효과를 검증하지 못했다. 도로·주거지·정차 안전을 확인하지 않았으며 설치 추천이나 승객 증가 예측이 아니다. 세부 후보 생성·면적 대조·동별 전후 결과는 해당 폴더에 보존했다.

## 공식 양식 보고서 작성
원본 HWP의 내장 미리보기와 실제 로고를 기준으로 좌우 항목 표, 출처 병합 표, 필수 이미지 칸을 재구성했습니다. HWP 직접 편집이나 변환본이라고 표현하지 않습니다. 제출용 PDF는 전체 5쪽이며 별도 표지를 두지 않았습니다. data/template_assets의 원본 로고는 해당 공모전 제공 양식의 일부이며 일반 이용용으로 제공하는 것이 아닙니다. 원본 HWP는 변경하지 않았습니다.

## 저장소와 입력 준비
https://github.com/BeakJW/seoul-elderly-transit-access
웹 업로드를 위해 33MB 경계 원본만 ZIP으로 무손실 압축했습니다. prepare_inputs.py가 원본을 복원하고 SHA256을 확인합니다. 신청서·연락처·서명은 포함하지 않습니다.
