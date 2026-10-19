"""Register a candidate-only forecast BEFORE its 20-session outcome is available.

Archived JSON is immutable by run/attempt. This is prospective registration,
not independently verified PIT, source admission, or trading authorization.
"""
import argparse,csv,hashlib,json,io,math,statistics
from datetime import datetime,timezone
from pathlib import Path

def register(csv_path,manifest_path,output):
    raw=csv_path.read_bytes()
    m=json.loads(manifest_path.read_text(encoding='utf8'))
    sha=hashlib.sha256(raw).hexdigest()
    if sha!=m['snapshot_sha256']:raise ValueError('SNAPSHOT_HASH_MISMATCH')
    if m.get('admitted_to_ai_core_evid') is not False:raise ValueError('CANDIDATE_ONLY_REQUIRED')
    captured=datetime.fromisoformat(m['capture_time_utc'].replace('Z','+00:00'))
    if captured.tzinfo is None:raise ValueError('NAIVE_CAPTURE_TIME')
    records=list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
    if len(records)!=sum(m['rows_per_index'].values()):raise ValueError('ROW_COUNT_MISMATCH')
    predictions={}
    calendars=[]
    for symbol in ('000300.SH','000688.SH'):
        rows=sorted((x for x in records if x['index_id']==symbol),key=lambda x:x['date'])
        if len(rows)!=m['rows_per_index'][symbol]:raise ValueError('COUNT_MISMATCH')
        ds=[r['date'] for r in rows]
        if len(ds)!=len(set(ds)):raise ValueError('DUPLICATE_DATE')
        calendars.append(ds)
        closes=[float(r['close']) for r in rows]
        if any(not math.isfinite(p) or p<=0 for p in closes):raise ValueError('INVALID_CLOSE')
        if len(closes)<272:raise ValueError('INSUFFICIENT_HISTORY')
        returns=[math.log(closes[i]/closes[i-1]) for i in range(1,len(closes))]
        rv20=[statistics.stdev(returns[t-20:t])*math.sqrt(252) for t in range(20,len(closes))]
        predictions[symbol]={'asof_date':ds[-1],
          'target':'next_20_trading_sessions_realized_volatility',
          'persistence_rv20':rv20[-1],
          'expanding_rv20_mean':statistics.mean(rv20),
          'future_target_available_at_registration':False}
    if calendars[0]!=calendars[1]:raise ValueError('CALENDAR_MISMATCH')
    date=calendars[0][-1]
    # Ensure it is not possible to knowingly register a future closing date.
    if date>captured.date().isoformat():raise ValueError('FUTURE_MARKET_DATE')
    receipt={'schema':'CANDIDATE_PROSPECTIVE_RISK_FORECAST_V1',
      'snapshot_sha256':sha,'captured_at_utc':m['capture_time_utc'],
      'registered_at_utc':datetime.now(timezone.utc).isoformat(),
      'forecast_asof_date':date,'forecast_horizon_sessions':20,
      'model_specification':'RV20 persistence vs historical expanding RV20 mean; log close returns, annualized sqrt(252)',
      'predictions':predictions,'source_admitted':False,
      'historical_pit_verified':False,'forecast_validated':False,'trading_authorized':False}
    if output.exists():raise FileExistsError(output)
    output.write_text(json.dumps(receipt,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf8')
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--csv',type=Path,default=Path('candidate.csv'));p.add_argument('--manifest',type=Path,default=Path('candidate.csv.manifest.json'));p.add_argument('--output',type=Path,default=Path('candidate_forecast_registration.json'));a=p.parse_args()
    receipt=register(a.csv,a.manifest,a.output)
    print(json.dumps({'asof':receipt['forecast_asof_date'],'sha256':receipt['snapshot_sha256'],'trading_authorized':False}))
