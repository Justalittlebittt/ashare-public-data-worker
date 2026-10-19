"""Public candidate-only A-share index daily collector; never a formal admission receipt."""
import argparse,csv,hashlib,json,math,tempfile,time
from datetime import date,datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError
from http.client import RemoteDisconnected
INDEXES={'000300.SH':'1.000300','000688.SH':'1.000688'}
ENDPOINT='https://push2his.eastmoney.com/api/qt/stock/kline/get'
FIELDS=['index_id','date','close','source_id','retrieved_at_utc']
SOURCE='DIRECT_EASTMONEY_CANDIDATE_NOT_ADMITTED'

def fetch_index(secid,start,end,opener=urlopen):
    params={'secid':secid,'ut':'7eea3edcaed734bea9cbfc24409ed989','fields1':'f1,f2,f3,f4,f5,f6','fields2':'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61','klt':'101','fqt':'0','beg':start.replace('-',''),'end':end.replace('-','')}
    for attempt in range(3):
        try:
            with opener(ENDPOINT+'?'+urlencode(params),timeout=20) as f: payload=json.load(f)
            break
        except (URLError, RemoteDisconnected, TimeoutError, ConnectionError, OSError):
            if attempt==2:raise
            time.sleep(attempt+1)
    data=payload.get('data') or {}
    if str(data.get('code'))!=secid.split('.',1)[1]:raise ValueError('PROVIDER_INDEX_IDENTITY_MISMATCH:'+secid)
    lines=data.get('klines') or []
    if not lines:raise RuntimeError('EMPTY_PROVIDER_RESULT:'+secid)
    out=[]
    for line in lines:
        cells=line.split(',');d=cells[0];date.fromisoformat(d);price=float(cells[2])
        if not(start<=d<=end and price>0 and math.isfinite(price)):raise ValueError('INVALID_ROW')
        out.append((d,price))
    if len({d for d,_ in out})!=len(out):raise ValueError('DUPLICATE_DATES')
    return sorted(out)

def build(start,end,output,fetch=fetch_index,minimum_sessions=272):
    date.fromisoformat(start);date.fromisoformat(end)
    if start>end:raise ValueError('START_AFTER_END')
    manifest=output.with_suffix(output.suffix+'.manifest.json')
    if output.exists() or manifest.exists():raise FileExistsError('OUTPUT_EXISTS')
    series={idx:fetch(secid,start,end) for idx,secid in INDEXES.items()}
    if any(len(v)<minimum_sessions for v in series.values()):raise ValueError('INSUFFICIENT_HISTORY')
    if [d for d,_ in series['000300.SH']]!=[d for d,_ in series['000688.SH']]:raise ValueError('CANDIDATE_INDEX_CALENDAR_MISMATCH')
    captured=datetime.now(timezone.utc).isoformat()
    output.parent.mkdir(parents=True,exist_ok=True)
    tmp=None;mtmp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf8',newline='',dir=output.parent,delete=False) as f:
            tmp=Path(f.name);w=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');w.writeheader()
            for idx,rows in series.items():
                for d,p in rows:w.writerow({'index_id':idx,'date':d,'close':format(p,'.10g'),'source_id':SOURCE,'retrieved_at_utc':captured})
        manifest_obj={'schema':'ASHARE_PUBLIC_CANDIDATE_V1','source':'Eastmoney direct HTTP - independent candidate only','snapshot_sha256':hashlib.sha256(tmp.read_bytes()).hexdigest(),'capture_time_utc':captured,'rows_per_index':{k:len(v) for k,v in series.items()},'requested_range':[start,end],'admitted_to_ai_core_evid':False,'historical_point_in_time_verified':False,'trading_authorized':False}
        with tempfile.NamedTemporaryFile('w',encoding='utf8',dir=output.parent,delete=False) as f:
            mtmp=Path(f.name);json.dump(manifest_obj,f,indent=2)
        tmp.rename(output)
        try:mtmp.rename(manifest)
        except BaseException:output.unlink(missing_ok=True);raise
        return manifest_obj
    finally:
        if tmp:tmp.unlink(missing_ok=True)
        if mtmp:mtmp.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--start',default='2025-01-01');p.add_argument('--end',default=date.today().isoformat());p.add_argument('--min-sessions',type=int,default=272);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(build(a.start,a.end,a.output,minimum_sessions=a.min_sessions)))
if __name__=='__main__':main()
