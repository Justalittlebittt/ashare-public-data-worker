import csv,hashlib,io,json, tempfile,unittest,zipfile
from pathlib import Path
from risk_diagnostic import assess

def make_zip(path,prices_a,prices_b):
    from datetime import date,timedelta
    t=date(2025,1,1)
    ds=[]
    while len(ds)<len(prices_a):
        if t.weekday()<5:ds.append(t.isoformat())
        t+=timedelta(days=1)
    out=io.StringIO()
    writer=csv.DictWriter(out,fieldnames=['index_id','date','close','source_id','retrieved_at_utc'])
    writer.writeheader()
    for name,prices in [('000300.SH',prices_a),('000688.SH',prices_b)]:
        for d,p in zip(ds,prices):writer.writerow(dict(index_id=name,date=d,close=p,source_id='DIRECT_EASTMONEY_CANDIDATE_NOT_ADMITTED',retrieved_at_utc='2026-10-17T03:01:28Z'))
    raw=out.getvalue().encode()
    manifest=dict(snapshot_sha256=hashlib.sha256(raw).hexdigest(),admitted_to_ai_core_evid=False,rows_per_index={'000300.SH':len(prices_a),'000688.SH':len(prices_b)})
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('candidate.csv',raw)
        z.writestr('candidate.csv.manifest.json',json.dumps(manifest))

class DiagnosticTests(unittest.TestCase):
    def test_future_label_perturbation_does_not_alter_first_prediction(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.zip';q=Path(d)/'b.zip';base=[100+i*.1 for i in range(440)]
            make_zip(p,base,base)
            changed=base.copy();changed[350:]=[x*1.8 for x in changed[350:]]
            make_zip(q,changed,changed)
            a=assess(p);b=assess(q)
            for s in ('000300.SH','000688.SH'):
                oa=a['indices'][s]['observations'];ob=b['indices'][s]['observations']
                for x,y in zip(oa,ob):
                    if x['date']<'2026-04-01':continue
                    # Predictions with only untouched history must remain unchanged.
                    if x['date'] < '2026-05-01':self.assertEqual(x['persistence_prediction'],y['persistence_prediction'])
    def test_no_future_end_outside_sample(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.zip';arr=[100+i*.2 for i in range(440)];make_zip(p,arr,arr)
            r=assess(p)
            for v in r['indices'].values():
                self.assertTrue(all(x['date']<x['forward_end_date'] for x in v['observations']))
                self.assertFalse(r['forecast_verified'])
    def test_hash_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.zip';make_zip(p,[100+i for i in range(440)],[100+i for i in range(440)])
            with zipfile.ZipFile(p,'a') as z:z.writestr('candidate.csv','changed')
            with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):assess(p)
if __name__=='__main__':unittest.main()
