import tempfile,unittest
from pathlib import Path
from urllib.error import URLError
from collect import get_atomic_provider_series,build,INDEXES,TENCENT_SOURCE,SOURCE

class AtomicFallbackTests(unittest.TestCase):
    def test_both_indices_retrieved_from_backup_after_primary_failure(self):
        calls=[]
        def primary(s,a,b):
            calls.append(('primary',s))
            if s=='1.000688':raise URLError('offline')
            return [('2026-10-16',100)]
        def backup(s,a,b):
            calls.append(('backup',s));return [('2026-10-16',200)]
        result,source,_=get_atomic_provider_series('2026-10-16','2026-10-16',primary,backup)
        self.assertEqual(source,TENCENT_SOURCE)
        self.assertEqual(result['000300.SH'][0][1],200)
        self.assertEqual(calls[-2:],[('backup','sh000300'),('backup','sh000688')])
    def test_primary_success_not_call_backup(self):
        def primary(s,a,b):return [('2026-10-16',100)]
        def backup(*args):raise AssertionError('unexpected backup')
        result,source,_=get_atomic_provider_series('2026-10-16','2026-10-16',primary,backup)
        self.assertEqual(source,SOURCE)
    def test_primary_semantic_failure_not_masked(self):
        def primary(s,a,b):raise ValueError('WRONG_PROVIDER_IDENTITY')
        with self.assertRaisesRegex(ValueError,'WRONG_PROVIDER_IDENTITY'):
            get_atomic_provider_series('2026-10-16','2026-10-16',primary,lambda *x:[])
if __name__=='__main__':unittest.main()
