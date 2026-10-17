import io,json,tempfile,unittest
from pathlib import Path
from collect import build,fetch_index

class CollectorTests(unittest.TestCase):
    def test_mock_success(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.csv';m=build('2026-10-08','2026-10-09',p,lambda *x:[('2026-10-08',100),('2026-10-09',101)],minimum_sessions=2)
            self.assertTrue(p.exists());self.assertTrue(p.with_suffix('.csv.manifest.json').exists());self.assertFalse(m['admitted_to_ai_core_evid'])
    def test_calendar_disagreement(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'CALENDAR_MISMATCH'):
                build('2026-10-08','2026-10-09',Path(d)/'a.csv',lambda s,*x:[('2026-10-08',100)] if s.endswith('300') else [('2026-10-09',100)],minimum_sessions=1)
    def test_overwrite_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.csv';p.write_text('existing')
            with self.assertRaises(FileExistsError):build('2026-10-08','2026-10-09',p)
    def test_short_history_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'INSUFFICIENT_HISTORY'):build('2026-10-08','2026-10-09',Path(d)/'a.csv',lambda *x:[('2026-10-09',100)],minimum_sessions=272)
    def test_good_provider(self):
        def op(url,timeout):return io.BytesIO(json.dumps({'data':{'code':'000688','klines':['2026-10-09,1,100,2']}}).encode())
        self.assertEqual(fetch_index('1.000688','2026-10-09','2026-10-09',op),[('2026-10-09',100)])
    def test_wrong_provider(self):
        def op(url,timeout):return io.BytesIO(json.dumps({'data':{'code':'000300','klines':['2026-10-09,1,100,2']}}).encode())
        with self.assertRaisesRegex(ValueError,'IDENTITY_MISMATCH'):fetch_index('1.000688','2026-10-09','2026-10-09',op)
    def test_missing_provider(self):
        def op(url,timeout):return io.BytesIO(json.dumps({'data':{'klines':['2026-10-09,1,100,2']}}).encode())
        with self.assertRaisesRegex(ValueError,'IDENTITY_MISMATCH'):fetch_index('1.000688','2026-10-09','2026-10-09',op)
    def test_nan(self):
        def op(url,timeout):return io.BytesIO(json.dumps({'data':{'code':'000688','klines':['2026-10-09,1,NaN,2']}}).encode())
        with self.assertRaises(ValueError):fetch_index('1.000688','2026-10-09','2026-10-09',op)
    def test_invalid_date(self):
        def op(url,timeout):return io.BytesIO(json.dumps({'data':{'code':'000688','klines':['2026-02-30,1,100,2']}}).encode())
        with self.assertRaises(ValueError):fetch_index('1.000688','2026-02-01','2026-03-01',op)
    def test_invalid_query_date(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):build('2026-02-30','2026-10-09',Path(d)/'a.csv')
if __name__=='__main__':unittest.main()
