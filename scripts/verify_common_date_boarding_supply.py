"""Same-date raw schema/key validation only. No main EDA or indicator calculation."""
from pathlib import Path
import hashlib,json,zipfile
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'data/raw';OUT=ROOT/'output/verification/supply_and_route_structure';OUT.mkdir(parents=True,exist_ok=True)
zipname='tpss_sta_route_hpasngr_2026.09.21-09.27.zip';csvname=zipname[:-4]+'.csv'
with zipfile.ZipFile(RAW/zipname) as z:
 members=[{'name':i.filename,'bytes':i.file_size} for i in z.infolist()]
 with z.open(csvname) as src,(RAW/csvname).open('wb') as dst:
  while block:=src.read(1024*1024):dst.write(block)
body=(RAW/csvname).read_bytes();body.decode('cp949',errors='strict')
b=pd.read_csv(RAW/csvname,encoding='cp949',dtype=str,keep_default_na=False)
s=pd.read_csv(RAW/'tpss_sta_route_hturn_2026.09.21-09.27.csv',encoding='cp949',dtype=str,keep_default_na=False)
key=['기준_날짜','노선_ID','정류장_ID','정류장_순서']
bcounts=b.groupby(key,dropna=False).size();scounts=s.groupby(key,dropna=False).size()
bi=pd.MultiIndex.from_frame(b[key]);si=pd.MultiIndex.from_frame(s[key]);bm=pd.Series(bi.isin(si),index=b.index);sm=pd.Series(si.isin(bi),index=s.index)
common=set(bcounts.index)&set(scounts.index)
joined_rows=int((bcounts*scounts.reindex(bcounts.index,fill_value=0)).sum())
dates=[]
for date in sorted(set(b['기준_날짜'])|set(s['기준_날짜'])):
 mask=b['기준_날짜'].eq(date);s_mask=s['기준_날짜'].eq(date)
 dates.append({'date':date,'boarding_rows':int(mask.sum()),'supply_rows':int(s_mask.sum()),'matched_boarding_rows':int((mask&bm).sum()),'unmatched_boarding_rows':int((mask&~bm).sum()),'match_rate':float((mask&bm).sum()/mask.sum()) if mask.sum() else None})
pd.DataFrame(dates).to_csv(OUT/'same_date_boarding_supply_by_date.csv',index=False,encoding='utf-8-sig')
b.loc[~bm].to_csv(OUT/'same_date_boarding_without_supply.csv',index=False,encoding='utf-8-sig');s.loc[~sm].to_csv(OUT/'same_date_supply_without_boarding.csv',index=False,encoding='utf-8-sig')
# Real joined sample, preserving source fields. Only unique key joins are used here.
assert not (bcounts>1).any() and not (scounts>1).any()
sample=b.loc[bm].head(100).merge(s,on=key,how='inner',validate='one_to_one')
sample.to_csv(OUT/'same_date_boarding_supply_matched_sample.csv',index=False,encoding='utf-8-sig')
boardcols=[c for c in b.columns if c.startswith('승차_승객_수')]
quality=[]
for c in boardcols:
 n=pd.to_numeric(b[c],errors='coerce');quality.append({'column':c,'empty':int(b[c].eq('').sum()),'numeric_zero':int(n.eq(0).sum()),'positive':int(n.gt(0).sum()),'invalid_nonempty':int((n.isna()&b[c].ne('')).sum())})
pd.DataFrame(quality).to_csv(OUT/'separate_boarding_numeric_quality.csv',index=False,encoding='utf-8-sig')
# Same-row/same-hour counterexamples using only matched one-to-one keys.
aligned_supply=s.set_index(key).reindex(bi)
blank_cases=[]
for hour in range(24):
 hh=f'{hour:02d}';positive=pd.to_numeric(b[f'승차_승객_수_{hh}시'],errors='coerce').gt(0).to_numpy();blank=aligned_supply[f'버스운행횟수_{hh}시'].eq('').to_numpy();mask=positive & blank & bm.to_numpy()
 blank_cases.append({'hour':hh,'supply_blank_boarding_positive_rows':int(mask.sum())})
pd.DataFrame(blank_cases).to_csv(OUT/'same_date_supply_blank_positive_boarding.csv',index=False,encoding='utf-8-sig')
r={'zip':zipname,'zip_sha256':hashlib.sha256((RAW/zipname).read_bytes()).hexdigest(),'members':members,'csv_sha256':hashlib.sha256(body).hexdigest(),'encoding':'CP949 strict full-file decode succeeded','boarding_rows':len(b),'column_count':len(b.columns),'columns':list(b.columns),'alighting_columns_present':any('하차' in c for c in b.columns),'date_counts':b['기준_날짜'].value_counts().sort_index().to_dict(),'original_key':key,'boarding_duplicate_key_count':int((bcounts>1).sum()),'supply_duplicate_key_count':int((scounts>1).sum()),'matched_boarding_rows':int(bm.sum()),'unmatched_boarding_rows':int((~bm).sum()),'matched_supply_rows':int(sm.sum()),'unmatched_supply_rows':int((~sm).sum()),'boarding_match_rate':float(bm.mean()),'inner_join_output_rows':joined_rows,'cardinality_key_counts':{'1:1':len(common),'1:N':0,'N:1':0,'N:M':0},'date_tests':dates,'boarding_quality':quality,'supply_blank_with_positive_boarding_row_hour_cases':sum(x['supply_blank_boarding_positive_rows'] for x in blank_cases),'living_mobility_20260921_present':(RAW/'seoul_trans_admdong4_in_20260921.zip').exists(),'ids_modified':False,'supply_null_semantics_confirmed':False,'eda_ready':False}
(OUT/'same_date_boarding_supply_results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in r.items() if k not in ['columns','boarding_quality']},ensure_ascii=False,indent=2))
