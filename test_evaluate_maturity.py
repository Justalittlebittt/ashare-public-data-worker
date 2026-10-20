"""Regression tests for candidate forecast maturity; synthetic only."""
import csv,hashlib,io,json,math,tempfile,unittest
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from evaluate_maturity import evaluate

def make_snapshot(root,run,prices,asof_idx,registered="2026-10-20T09:00:00+00:00",capture="2026-10-20T08:30:00+00:00",prediction=0.2):
    d=root/f"run-{run}-attempt-1";d.mkdir()
    origin=date(2025,1,1);dates=[];cursor=origin
    while len(dates)<len(prices):
        if cursor.weekday()<5:dates.append(cursor.isoformat())
        cursor+=timedelta(days=1)
    end=dates[asof_idx]
    # Archive only candles available on forecast date, even though synthetic fixture supplies more.
    csvout=io.StringIO();w=csv.DictWriter(csvout,fieldnames=['index_id','date','close','source_id','retrieved_at_utc']);w.writeheader()
    for idx in ('000300.SH','000688.SH'):
        for day,price in zip(dates[:asof_idx+1],prices[:asof_idx+1]):
            w.writerow(dict(index_id=idx,date=day,close=price,source_id='CANDIDATE',retrieved_at_utc=capture))
    raw=csvout.getvalue().encode();(d/'candidate.csv').write_bytes(raw)
    sha=hashlib.sha256(raw).hexdigest()
    manifest={'snapshot_sha256':sha,'capture_time_utc':capture,'admitted_to_ai_core_evid':False,'rows_per_index':{'000300.SH':asof_idx+1,'000688.SH':asof_idx+1}}
    (d/'candidate.csv.manifest.json').write_text(json.dumps(manifest))
    registration={'snapshot_sha256':sha,'source_admitted':False,'trading_authorized':False,'forecast_asof_date':end,'forecast_horizon_sessions':20,'registered_at_utc':registered,'captured_at_utc':capture,'predictions':{idx:{'asof_date':end,'future_target_available_at_registration':False,'persistence_rv20':prediction,'expanding_rv20_mean':prediction} for idx in ('000300.SH','000688.SH')}}
    (d/'candidate_forecast_registration.json').write_text(json.dumps(registration))
    return d,dates

class MaturityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.prices=[100+i*.1+(i%3)*.03 for i in range(350)]
    def test_pending_until_20_sessions(self):
        make_snapshot(self.root,1,self.prices,300)
        r=evaluate(self.root)
        self.assertEqual(r['matured_count'],0);self.assertEqual(r['pending_count'],1)
    def test_duplicate_date_deduplicated(self):
        make_snapshot(self.root,1,self.prices,300)
        make_snapshot(self.root,2,self.prices,300,registered="2026-10-20T09:02:00+00:00")
        r=evaluate(self.root)
        self.assertEqual(r['unique_forecast_dates'],1)
        self.assertEqual(r['pending_count'],1)
    def test_matures_exactly_on_twentieth_later_session(self):
        make_snapshot(self.root,1,self.prices,300)
        make_snapshot(self.root,2,self.prices,320,registered='2026-10-21T09:00:00+00:00',capture='2026-10-21T08:30:00+00:00')
        r=evaluate(self.root)
        self.assertEqual(r['matured_count'],1);self.assertEqual(r['pending_count'],1)
    def test_preclose_forecast_quarantined_from_canonical(self):
        # Build an as-of-day captured before 17:00 Shanghai time.\n        from datetime import date,timedelta\n        d=date(2025,1,1);n=-1\n        while n<300:\n            if d.weekday()<5:n+=1\n            if n==300:break\n            d+=timedelta(days=1)\n        stamp=d.isoformat()\n        make_snapshot(self.root,1,self.prices,300,registered=stamp+'T04:01:00+00:00',capture=stamp+'T04:00:00+00:00')
        r=evaluate(self.root)
        self.assertEqual(r['unique_forecast_dates'],0)
    def test_revised_asof_close_quarantines(self):
        make_snapshot(self.root,1,self.prices,300)
        changed=self.prices.copy();changed[300]+=10
        make_snapshot(self.root,2,changed,325,registered='2026-10-21T09:00:00+00:00',capture='2026-10-21T08:30:00+00:00')
        r=evaluate(self.root)
        self.assertEqual(r['matured_count'],0);self.assertEqual(r['quarantined_count'],1)
    def test_snapshot_hash_corruption_rejected(self):
        d,_=make_snapshot(self.root,1,self.prices,300)
        (d/'candidate.csv').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):evaluate(self.root)

if __name__=='__main__':unittest.main()
