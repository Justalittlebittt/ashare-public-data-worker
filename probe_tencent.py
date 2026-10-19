"""Isolated Tencent index source probe; never a production source fallback."""
import json,sys,urllib.parse,urllib.request
from datetime import date
SYMBOLS=('sh000300','sh000688')
def probe(symbol,opener=urllib.request.urlopen):
    url='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urllib.parse.urlencode({'_var':'kline_day','param':f'{symbol},day,,,600,'})
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.qq.com/'})
    with opener(req,timeout=15) as res: raw=res.read().decode('utf8')
    if raw.strip().startswith('kline_day='):raw=raw.split('=',1)[1].rstrip(';')
    obj=json.loads(raw)
    series=(obj.get('data') or {}).get(symbol) or {}
    bars=series.get('day') or []
    parsed=[]
    for row in bars:
        if len(row)<3:raise ValueError('BAD_BAR')
        d=row[0];date.fromisoformat(d);close=float(row[2])
        if close<=0:raise ValueError('BAD_CLOSE')
        parsed.append((d,close))
    return {'symbol':symbol,'count':len(parsed),'first':parsed[0][0] if parsed else None,'last':parsed[-1][0] if parsed else None,'reference_close_2026_10_09':next((p for d,p in parsed if d=='2026-10-09'),None),'status':'CANDIDATE_PROBE_ONLY'}
if __name__=='__main__':
    for symbol in SYMBOLS:
        try:print(json.dumps(probe(symbol)))
        except Exception as exc:print(json.dumps({'symbol':symbol,'status':'PROBE_FAILED','error':type(exc).__name__+': '+str(exc)[:180]}));sys.exit(1)
