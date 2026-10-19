"""Public candidate-only A-share index daily collector; never a formal admission receipt."""
import argparse,csv,hashlib,json,math,tempfile,time
from urllib.request import Request
from datetime import date,datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError
from http.client import RemoteDisconnected
INDEXES={'000300.SH':'1.000300','000688.SH':'1.000688'}
ENDPOINT='https://push2his.eastmoney.com/api/qt/stock/kline/get'
FIELDS=['index_id','date','close','source_id','retrieved_at_utc']
SOURCE='DIRECT_EASTMONEY_CANDIDATE_NOT_ADMITTED'
TENCENT_SOURCE='DIRECT_TENCENT_CANDIDATE_NOT_ADMITTED'

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


def fetch_tencent(symbol,start,end,opener=urlopen):
    from urllib.parse import urlencode
    from datetime import date
    url='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urlencode({'_var':'kline_day','param':f'{symbol},day,,,600,'})
    req=Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.qq.com/'})
    with opener(req,timeout=20) as response: raw=response.read().decode('utf-8')
    if raw.strip().startswith('kline_day='):raw=raw.split('=',1)[1].rstrip(';')
    data=(json.loads(raw).get('data') or {}).get(symbol) or {}
    bars=data.get('day') or []
    out=[]
    for row in bars:
        if len(row)<3:raise ValueError('INVALID_TENCENT_BAR')
        d=row[0];date.fromisoformat(d);p=float(row[2])
        if start<=d<=end:
            if not math.isfinite(p) or p<=0:raise ValueError('INVALID_TENCENT_CLOSE')
            out.append((d,p))
    if len({d for d,_ in out})!=len(out):raise ValueError('DUPLICATE_TENCENT_DATES')
    if not out:raise RuntimeError('EMPTY_TENCENT_RESULT')
    return sorted(out)

def get_atomic_provider_series(start,end,primary=fetch_index,backup=fetch_tencent):
    try:
        series={idx:primary(secid,start,end) for idx,secid in INDEXES.items()}
        return series,SOURCE,'Eastmoney direct HTTP - independent candidate only'
    except (URLError,RemoteDisconnected,TimeoutError,ConnectionError,OSError,RuntimeError) as exc:
        print('PRIMARY_PROVIDER_UNAVAILABLE:'+type(exc).__name__,flush=True)
        # Both indices fetched from Tencent afresh; never merge vendors.
        series={idx:backup('sh'+idx[:6],start,end) for idx in INDEXES}
        return series,TENCENT_SOURCE,'Tencent direct HTTP - independent candidate only'

def build(start,end,output,fetch=fetch_index,minimum_sessions=272):
    date.fromisoformat(start);date.fromisoformat(end)
    if start>end:raise ValueError('START_AFTER_END')
    manifest=output.with_suffix(output.suffix+'.manifest.json')
    if output.exists() or manifest.exists():raise FileExistsError('OUTPUT_EXISTS')
    if fetch is fetch_index:
        series,source_id,source_name=get_atomic_provider_series(start,end)
    else:
        series={idx:fetch(secid,start,end) for idx,secid in INDEXES.items()}
        source_id,source_name=SOURCE,'Eastmoney direct HTTP - independent candidate only'
    if any(len(v)<minimum_sessions for v in series.values()):raise ValueError('INSUFFICIENT_HISTORY')
    if [d for d,_ in series['000300.SH']]!=[d for d,_ in series['000688.SH']]:raise ValueError('CANDIDATE_INDEX_CALENDAR_MISMATCH')
    captured=datetime.now(timezone.utc).isoformat()
    output.parent.mkdir(parents=True,exist_ok=True)
    tmp=None;mtmp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf8',newline='',dir=output.parent,delete=False) as f:
            tmp=Path(f.name);w=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');w.writeheader()
            for idx,rows in series.items():
                for d,p in rows:w.writerow({'index_id':idx,'date':d,'close':format(p,'.10g'),'source_id':source_id,'retrieved_at_utc':captured})
        manifest_obj={'schema':'ASHARE_PUBLIC_CANDIDATE_V1','source':source_name,'source_id':source_id,'snapshot_sha256':hashlib.sha256(tmp.read_bytes()).hexdigest(),'capture_time_utc':captured,'rows_per_index':{k:len(v) for k,v in series.items()},'requested_range':[start,end],'admitted_to_ai_core_evid':False,'historical_point_in_time_verified':False,'trading_authorized':False}
        with tempfile.NamedTemporaryFile('w',encoding='utf8',dir=output.parent,delete=False) as f:
            mtmp=Path(f.name);json.dump(manifest_obj,f,indent=2)
        tmp.rename(output)
        try:mtmp.rename(manifest)
        except BaseException:output.unlink(missing_ok=True);raise
        return manifest_obj
    finally:
        if tmp:tmp.unlink(missing_ok=True)
        if mtmp:mtmp.unlink(missing_ok=True)

def safe_latest_date(now=None):
    from datetime import time
    from zoneinfo import ZoneInfo
    now=now or datetime.now(timezone.utc)
    shanghai=now.astimezone(ZoneInfo('Asia/Shanghai'))
    # 17:00 CST is a conservative post-close buffer. Never record a live-session daily candle.
    return (shanghai.date() if shanghai.time()>=time(17,0) else shanghai.date()-timedelta(days=1)).isoformat()

def main():
    p=argparse.ArgumentParser();p.add_argument('--start',default='2025-01-01');p.add_argument('--end',default=None);p.add_argument('--min-sessions',type=int,default=272);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    end=a.end or safe_latest_date()
    if end>safe_latest_date():raise ValueError('END_DATE_NOT_POST_CLOSE_FINAL')
    print(json.dumps(build(a.start,end,a.output,minimum_sessions=a.min_sessions)))
if __name__=='__main__':main()
