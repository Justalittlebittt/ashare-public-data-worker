"""Archive verified public candidate outputs under a unique run path; never overwrite."""
import argparse,hashlib,json,shutil
from pathlib import Path

FILES=('candidate.csv','candidate.csv.manifest.json','candidate_risk_diagnostic.json')
def archive(run_id,attempt,root=Path('.'),dst_root=Path('snapshots')):
    if not str(run_id).isdigit() or not str(attempt).isdigit():raise ValueError('INVALID_RUN_ID')
    manifest=json.loads((root/FILES[1]).read_text(encoding='utf8'))
    raw=(root/FILES[0]).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest.get('snapshot_sha256'):
        raise ValueError('HASH_MISMATCH')
    if manifest.get('admitted_to_ai_core_evid') is not False or manifest.get('trading_authorized') is not False:
        raise ValueError('CANDIDATE_ONLY_REQUIRED')
    diagnostic=json.loads((root/FILES[2]).read_text(encoding='utf8'))
    if diagnostic.get('source_snapshot_sha256')!=manifest['snapshot_sha256'] or diagnostic.get('forecast_verified') is not False:
        raise ValueError('DIAGNOSTIC_PROVENANCE_MISMATCH')
    dest=dst_root/f'run-{run_id}-attempt-{attempt}'
    if dest.exists():raise FileExistsError('IMMUTABLE_SNAPSHOT_ALREADY_EXISTS')
    dest.mkdir(parents=True)
    try:
        for filename in FILES:shutil.copyfile(root/filename,dest/filename)
        (dest/'archive_receipt.json').write_text(json.dumps({'run_id':str(run_id),'run_attempt':str(attempt),'source_sha256':manifest['snapshot_sha256'],'files_sha256':{name:hashlib.sha256((dest/name).read_bytes()).hexdigest() for name in FILES},'admitted':False,'trading_authorized':False},indent=2)+'\n',encoding='utf8')
    except BaseException:
        shutil.rmtree(dest)
        raise
    return dest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--attempt',required=True);args=p.parse_args()
    print(archive(args.run_id,args.attempt))
