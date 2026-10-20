"""Export 600-session Tencent-only candidate snapshot. Not PIT verified or source admitted."""
import csv,hashlib,json,math
from datetime import datetime,timezone,date
from pathlib import Path
from collect import fetch_tencent,safe_latest_date,TENCENT_SOURCE
from urllib.request import urlopen

def export(output=Path('extended_tencent.csv'),start='2024-01-01',end=None,fetch=fetch_tencent):
    end=end or safe_latest_date()
    if end>safe_latest_date():raise ValueError('PRE_CLOSE_BLOCK')
    manifest=output.with_suffix(output.suffix+'.manifest.json')
    if output.exists() or manifest.exists():raise FileExistsError('IMMUTABLE_OUTPUT')
    rows={idx:fetch('sh'+idx[:6],start,end) for idx in ('000300.SH','000688.SH')}
    ds=[[d for d,p in v] for v in rows.values()]
    if ds[0]!=ds[1] or len(ds[0])<272:raise ValueError('HISTORY_OR_CALENDAR_BLOCK')
    captured=datetime.now(timezone.utc).isoformat()
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=['index_id','date','close','source_id','retrieved_at_utc'],lineterminator='\n')
        w.writeheader()
        for idx,series in rows.items():
            for d,p in series:
                date.fromisoformat(d)
                if not math.isfinite(p) or p<=0:raise ValueError('INVALID_CLOSE')
                w.writerow({'index_id':idx,'date':d,'close':format(p,'.10g'),'source_id':TENCENT_SOURCE,'retrieved_at_utc':captured})
    m={'schema':'EXTENDED_TENCENT_CANDIDATE_V1','source_id':TENCENT_SOURCE,
       'snapshot_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
       'capture_time_utc':captured,'rows_per_index':{idx:len(v) for idx,v in rows.items()},
       'earliest_date':ds[0][0],'latest_date':ds[0][-1],
       'admitted_to_ai_core_evid':False,'historical_point_in_time_verified':False,'trading_authorized':False}
    with manifest.open('x') as f:json.dump(m,f,indent=2)
    print(json.dumps(m))
if __name__=='__main__':export()
