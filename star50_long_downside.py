"""Long STAR50 single-vendor retrospective downside replication; never PIT/trade eligible."""
import csv,hashlib,json,math,statistics
from datetime import datetime,timezone
from pathlib import Path
from collect import fetch_index
def run():
    rows=fetch_index('1.000688','2019-12-31','2026-10-19')
    if len(rows)<600:raise ValueError('LONG_HISTORY_TOO_SHORT')
    raw=[];returns=[math.log(rows[i][1]/rows[i-1][1]) for i in range(1,len(rows))]
    rv={i:statistics.stdev(returns[i-20:i])*math.sqrt(252) for i in range(20,len(rows))}
    windows=[]
    for i in range(271,len(rows)-20,20):
        cutoff=statistics.median([rv[k] for k in range(20,i+1)])
        p=[v for d,v in rows[i:i+21]]
        peak=p[0];mdd=0.0
        for v in p[1:]:peak=max(peak,v);mdd=min(mdd,v/peak-1)
        windows.append({'asof':rows[i][0],'end':rows[i+20][0],
                        'high_rv':rv[i]>cutoff,'future_mdd':mdd,'risk_event_mdd_5pct':mdd<=-.05})
    def stats(part):
        high=[w['future_mdd'] for w in part if w['high_rv']]
        low=[w['future_mdd'] for w in part if not w['high_rv']]
        return {'n':len(part),'high_n':len(high),'low_n':len(low),
                'high_avg_mdd':statistics.mean(high) if high else None,
                'low_avg_mdd':statistics.mean(low) if low else None,
                'event_count':sum(w['risk_event_mdd_5pct'] for w in part),
                'correct_event_flags':sum(w['risk_event_mdd_5pct'] and w['high_rv'] for w in part),
                'false_alarms':sum(not w['risk_event_mdd_5pct'] and w['high_rv'] for w in part)}
    midpoint=len(windows)//2
    report={'schema':'STAR50_SINGLE_PROVIDER_LONG_HISTORY_DOWNSIDE_V1',
        'data_source':'DIRECT_EASTMONEY_CANDIDATE_NOT_ADMITTED','index_id':'000688.SH',
        'earliest':rows[0][0],'latest':rows[-1][0],'closes':len(rows),
        'horizon_sessions':20,'first_evaluation_index':271,'step_sessions':20,
        'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
        'candidate_only':True,'historical_pit_verified':False,
        'predictive_skill_verified':False,'trading_authorized':False,
        'overall':stats(windows),'earlier_half':stats(windows[:midpoint]),
        'later_half':stats(windows[midpoint:]),'windows':windows}
    Path('star50_long_downside.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:report[k] for k in ('closes','earliest','latest','overall','earlier_half','later_half')}))
if __name__=='__main__':run()
