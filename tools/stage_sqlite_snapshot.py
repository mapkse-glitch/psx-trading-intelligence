"""Upload a trusted initial snapshot into private database staging; not a localhost server."""
import argparse
import hashlib
import json
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, urlopen


def stage(source, dashboard):
    p = urlsplit(dashboard)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise ValueError('Use the HTTPS dashboard origin without credentials, query or fragment.')
    source = Path(source)
    if not source.is_file() or not source.name.endswith(('.db.gz','.sqlite.gz')):
        raise ValueError('Use a trusted compressed SQLite .db.gz snapshot.')
    if not 0 < source.stat().st_size <= 160*1024*1024:
        raise ValueError('Compressed snapshot must be between 1 byte and 160 MiB.')
    origin = p.scheme+'://'+p.netloc
    upload_id = 'migration-'+uuid.uuid4().hex
    total = (source.stat().st_size+1024*1024-1)//(1024*1024)
    digest = hashlib.sha256()
    with source.open('rb') as src:
        for i in range(total):
            block = src.read(1024*1024)
            digest.update(block)
            query = urlencode(dict(upload_id=upload_id,name=source.name,idx=i,total=total))
            request = Request(origin+'/api/imports/upload-chunk?'+query,data=block,
                              headers={'Content-Type':'application/octet-stream','Origin':origin},method='POST')
            with urlopen(request,timeout=120) as response:
                result = json.load(response)
            if result.get('storage')!='remote' or result.get('idx')!=i:
                raise ValueError('Expected a remote-staging acknowledgement; stop and inspect.')
    return dict(upload_id=upload_id,total_chunks=total,expected_sha256=digest.hexdigest(),
                note='Not imported yet. Run the guarded GitHub migration workflow within 24 hours. No canonical records were changed.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source');p.add_argument('--dashboard',required=True);a=p.parse_args()
    try: print(json.dumps(stage(a.source,a.dashboard)))
    except Exception:
        raise SystemExit('Upload did not complete. No import was attempted. Inspect stored upload status before restarting; credentials are not printed.') from None


if __name__=='__main__':main()
