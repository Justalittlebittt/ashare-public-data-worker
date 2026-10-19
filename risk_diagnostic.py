"""Candidate-only, deterministic, chronological holdout diagnostics. Not PIT or trading approval."""
import argparse,csv,hashlib,io,json,math,statistics,zipfile
from pathlib import Path
SPLIT='2026-04-01'
HORIZON=20
INDICES=('000300.SH','000688.SH')

def assess(data_zip, split=SPLIT, horizon=HORIZON):
    with zipfile.ZipFile(data_zip) as z:
        raw=z.read('candidate.csv')
        manifest=json.loads(z.read('candidate.csv.manifest.json'))
    digest=hashlib.sha256(raw).hexdigest()
    if digest != manifest['snapshot_sha256']:
        raise ValueError('SNAPSHOT_HASH_MISMATCH')
    if manifest.get('admitted_to_ai_core_evid') is not False:raise ValueError('CANDIDATE_STATUS_REQUIRED')
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
    if len(rows)!=sum(manifest['rows_per_index'].values()):raise ValueError('ROW_COUNT_MISMATCH')
    result={'schema':'AI_CORE_EVID_CANDIDATE_RISK_DIAGNOSTIC_V2','source_snapshot_sha256':digest,'split_date':split,'horizon_sessions':horizon,'split_selection':'RETROSPECTIVE_NOT_PRE_REGISTERED','data_status':'CANDIDATE_ONLY_NOT_SOURCE_ADMITTED','forecast_verified':False,'trading_authorized':False,'indices':{}}
    calendars=[]
    for symbol in INDICES:
        series=sorted([x for x in rows if x['index_id']==symbol],key=lambda x:x['date'])
        if len(series)!=manifest['rows_per_index'][symbol]:raise ValueError('PER_INDEX_COUNT_MISMATCH')
        ds=[x['date'] for x in series]
        if len(set(ds))!=len(ds):raise ValueError('DUPLICATE_DATE')
        calendars.append(ds)
        p=[float(x['close']) for x in series]
        if any(not math.isfinite(v) or v<=0 for v in p):raise ValueError('INVALID_PRICE')
        ret=[math.log(p[i]/p[i-1]) for i in range(1,len(p))]
        rv=lambda v:statistics.stdev(v)*math.sqrt(252)
        rv20=[None]*len(p)
        for t in range(horizon,len(p)):rv20[t]=rv(ret[t-horizon:t])
        # Keep original design: minimum 252 trailing observations for RV20 history.
        valid=[t for t in range(271,len(p)-horizon) if ds[t]>=split]
        selected=valid[::horizon];obs=[]
        for t in selected:
            # Strictly chronological: estimates use returns through t; label uses t+1..t+horizon.
            hist=[x for x in rv20[20:t+1] if x is not None]
            prediction=rv20[t];baseline=statistics.mean(hist);actual=rv(ret[t:t+horizon])
            obs.append({'date':ds[t],'forward_end_date':ds[t+horizon],'observed_forward_rv20':actual,'persistence_prediction':prediction,'expanding_mean_baseline':baseline,'persistence_abs_error':abs(prediction-actual),'baseline_abs_error':abs(baseline-actual)})
        mae=lambda k:statistics.mean(x[k] for x in obs) if obs else None
        result['indices'][symbol]={'close_count':len(p),'evaluation_windows':len(obs),'persistence_MAE':mae('persistence_abs_error'),'baseline_MAE':mae('baseline_abs_error'),'persistence_win_count':sum(x['persistence_abs_error']<x['baseline_abs_error'] for x in obs),'assessment':'INSUFFICIENT_INDEPENDENT_WINDOWS' if len(obs)<20 else 'RETROSPECTIVE_DIAGNOSTIC_ONLY','observations':obs}
    if calendars[0]!=calendars[1]:raise ValueError('CALENDAR_MISMATCH')
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('candidate_zip',type=Path)
    parser.add_argument('--output',type=Path,default=Path('candidate_risk_diagnostic.json'))
    args=parser.parse_args()
    result=assess(args.candidate_zip)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(json.dumps({s:{k:v for k,v in r.items() if k!='observations'} for s,r in result['indices'].items()}))
if __name__=='__main__':main()
