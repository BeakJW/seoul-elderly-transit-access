"""Independent saved-output checks, meaningful invariants and index recomputation."""
from pathlib import Path
import json
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'output/final_analysis'
g=pd.read_csv(p/'dong_screening_all.csv')
recalculated=50*(g.elderly_share.rank(pct=True)+(1-g.bus300_area_coverage).round(12).rank(pct=True))
checks={
 'all_427_regions':len(g)==427,
 'unique_administrative_codes':not g.adm_cd2.duplicated().any(),
 'population_positive':bool(g.population.gt(0).all()),
 'elderly_within_population':bool(g.elderly.between(0,g.population).all()),
 'coverage_in_unit_interval':bool(g.filter(regex='coverage$').apply(lambda s:s.between(0,1).all()).all()),
 'index_recomputed':bool((g.screen_index-recalculated).abs().lt(1e-8).all()),
 'top10_has_10_unique':len(g.nlargest(10,'screen_index').adm_cd2.unique())==10,
 'all_regions_have_supply_records':bool(g.observed_daily_06_21_service_events.notna().all()),
 'known_supply_share_in_range':bool(g.known_supply_cell_share.between(0,1).all()),
 'city_population_sum':int(g.population.sum())==9560471,
 'city_elderly_sum':int(g.elderly.sum())==1962133,
}
assert all(checks.values()),checks
(p/'verification_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))
