"""Candidate-only 20-session forecast maturity and evaluation; no lookahead or trade approval."""
import csv,hashlib,json,math,statistics
from datetime import datetime
from pathlib import Path

def load_snapshot(directory):
    raw=(directory/'candidate.csv').read_bytes()
    manifest=json.loads((directory/'candidate.csv.manifest.json').read_text())
    if hashlib.sha256(raw).hexdigest()!=manifest['snapshot_sha256']:raise ValueError('HASH_MISMATCH')
    if manifest.get('admitted_to_ai_core_evid') is not False:raise ValueError('NON_CANDIDATE')
    rows=list(csv.DictReader(raw.decode('utf8').splitlines()))
    data={}
    for idx in ('000300.SH','000688.SH'):
        entries=sorted((x for x in rows if x['index_id']==idx),key=lambda x:x['date'])
        dates=[x['date'] for x in entries]
        if len(dates)!=len(set(dates)) or len(dates)!=manifest['rows_per_index'][idx]:raise ValueError('CALENDAR_OR_COUNT')
        data[idx]={x['date']:float(x['close']) for x in entries}
    if set(data['000300.SH'])!=set(data['000688.SH']):raise ValueError('CROSS_INDEX_CALENDAR')
    return manifest,data

def evaluate(root=Path('snapshots')):
    dirs=sorted(p for p in root.glob('run-*-attempt-*') if (p/'candidate_forecast_registration.json').is_file())
    indexed=[]
    for p in dirs:
        manifest,data=load_snapshot(p)
        registration=json.loads((p/'candidate_forecast_registration.json').read_text())
        if registration['snapshot_sha256']!=manifest['snapshot_sha256'] or registration['source_admitted'] is not False or registration['trading_authorized'] is not False:raise ValueError('REGISTRATION_PROVENANCE')
        captured=datetime.fromisoformat(registration['registered_at_utc'].replace('Z','+00:00'))
        if captured.tzinfo is None:raise ValueError('NAIVE_REGISTRATION')
        asof=registration['forecast_asof_date']
        if asof!=max(data['000300.SH']):raise ValueError('FORECAST_ASOF_NOT_LATEST')
        if registration['forecast_horizon_sessions']!=20:raise ValueError('HORIZON_CHANGED')
        indexed.append((asof,captured,p.name,registration,manifest,data))
    # First submitted forecast per date is canonical; retries do not add independent samples.
    canonical={}
    for x in sorted(indexed,key=lambda v:(v[1],v[2])):
        canonical.setdefault(x[0],x)
    # Latest available snapshot is strictly a source of future outcomes, not forecasts.
    latest=max(indexed,key=lambda v:(max(v[5]['000300.SH']),v[1])) if indexed else None
    out={'schema':'CANDIDATE_FORWARD_EVALUATION_V1','independent_forecast_dates':len(canonical),
        'status':'CANDIDATE_ONLY_NOT_PIT_VERIFIED','trading_authorized':False,'evaluations':[]}
    if not latest:return out
    latest_manifest,latest_data=latest[4],latest[5]
    out['latest_outcome_snapshot_sha256']=latest_manifest['snapshot_sha256']
    for asof,(_,registration_time,archive,receipt,_,_) in sorted(canonical.items()):
        item={'asof_date':asof,'source_archive':archive,'registered_at_utc':receipt['registered_at_utc'],'status':'PENDING_20_SESSIONS'}
        per={}
        for index in ('000300.SH','000688.SH'):
            calendar=sorted(latest_data[index])
            if asof not in latest_data[index]:
                item['status']='QUARANTINED_ASOF_NOT_IN_LATEST_HISTORY'
                per={}
                break
            pos=calendar.index(asof)
            if len(calendar)-pos-1<20:continue
            prices=[latest_data[index][d] for d in calendar[pos:pos+21]]
            returns=[math.log(prices[i]/prices[i-1]) for i in range(1,len(prices))]
            realized=statistics.stdev(returns)*math.sqrt(252)
            pred=receipt['predictions'][index]
            if pred['asof_date']!=asof or pred['future_target_available_at_registration'] is not False:raise ValueError('INVALID_PREDICTION')
            per[index]={'outcome_end_date':calendar[pos+20],'realized_rv20':realized,
                'persistence_abs_error':abs(realized-pred['persistence_rv20']),
                'expanding_mean_abs_error':abs(realized-pred['expanding_rv20_mean'])}
        if len(per)==2:
            item['status']='MATURED_CANDIDATE_ONLY'
            item['outcomes']=per
        out['evaluations'].append(item)
    out['matured_count']=sum(x['status']=='MATURED_CANDIDATE_ONLY' for x in out['evaluations'])
    out['pending_count']=len(out['evaluations'])-out['matured_count']
    out['forecast_validated']=False
    return out

if __name__=='__main__':
    result=evaluate()
    Path('candidate_maturity_evaluation.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'registered_dates':result['independent_forecast_dates'],'matured':result.get('matured_count',0),'pending':result.get('pending_count',0)}))
