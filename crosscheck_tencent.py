"""Independent historical cross-provider close comparison, candidate-only."""
import csv,io,json,math,hashlib
from pathlib import Path
from probe_tencent import probe,SYMBOLS
import urllib.parse,urllib.request
def fetch_tencent_series(symbol,opener=urllib.request.urlopen):
    url='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urllib.parse.urlencode({'_var':'kline_day','param':f'{symbol},day,,,600,'})
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.qq.com/'})
    with opener(req,timeout=15) as resp:text=resp.read().decode('utf8')
    if text.strip().startswith('kline_day='):text=text.split('=',1)[1].rstrip(';')
    data=(json.loads(text).get('data') or {}).get(symbol) or {}
    bars=data.get('day') or []
    out={}
    for row in bars:
        if len(row)<3:raise ValueError('INVALID_PROVIDER_ROW')
        d=row[0];p=float(row[2])
        if d in out or not math.isfinite(p) or p<=0:raise ValueError('INVALID_PROVIDER_PRICE_OR_DUPLICATE')
        out[d]=p
    if len(out)<272:raise ValueError('INSUFFICIENT_TENCENT_HISTORY')
    return out

def compare(archived_csv,archived_manifest):
    raw=Path(archived_csv).read_bytes();manifest=json.loads(Path(archived_manifest).read_text())
    if hashlib.sha256(raw).hexdigest()!=manifest.get('snapshot_sha256'):raise ValueError('ARCHIVE_SHA_MISMATCH')
    records=list(csv.DictReader(io.StringIO(raw.decode('utf8'))))
    result={'schema':'INDEPENDENT_PROVIDER_CROSSCHECK_V1','comparison':'Tencent direct vs archived Eastmoney direct','archived_sha256':manifest['snapshot_sha256'],'candidate_only':True,'formal_source_admitted':False,'results':{}}
    for symbol,idx in [('sh000300','000300.SH'),('sh000688','000688.SH')]:
        base={r['date']:float(r['close']) for r in records if r['index_id']==idx}
        alt=fetch_tencent_series(symbol)
        common=sorted(set(base)&set(alt))
        mismatches=[{'date':d,'eastmoney':base[d],'tencent':alt[d]} for d in common if abs(base[d]-alt[d])>.02]
        result['results'][idx]={'shared_days':len(common),'eastmoney_days':len(base),'tencent_days':len(alt),'mismatch_count':len(mismatches),'mismatch_samples':mismatches[:10],'latest_common_date':common[-1] if common else None,'status':'PASS_CANDIDATE_CROSSCHECK' if len(common)>=272 and not mismatches else 'FAIL_CANDIDATE_CROSSCHECK'}
    if len(set(records[i]['date'] for i in range(len(records)) if records[i]['index_id']=='000300.SH') ^ set(r['date'] for r in records if r['index_id']=='000688.SH')):raise ValueError('ARCHIVED_CALENDAR_MISMATCH')
    return result
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--archived-directory',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('tencent_crosscheck.json'));a=p.parse_args()
    r=compare(a.archived_directory/'candidate.csv',a.archived_directory/'candidate.csv.manifest.json')
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(r))
    if any(v['status']!='PASS_CANDIDATE_CROSSCHECK' for v in r['results'].values()):raise SystemExit(2)
