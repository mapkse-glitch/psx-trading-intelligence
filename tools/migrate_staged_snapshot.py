"""Hosted one-time migration from private PostgreSQL upload staging, not GitHub data files."""
import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path


def migrate_staged(upload_id, total_chunks, expected_sha256):
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}', upload_id):
        raise ValueError('Invalid upload identifier.')
    if not 1 <= total_chunks <= 160:
        raise ValueError('Expected 1 to 160 upload chunks.')
    if not re.fullmatch(r'[a-f0-9]{64}', expected_sha256):
        raise ValueError('Expected SHA256 must be 64 lowercase hex characters.')
    from psx_app.database.turso import backend_name
    if backend_name() != 'postgres':
        raise ValueError('PostgreSQL configuration is required.')
    from psx_app.services.remote_staging import get, delete
    from tools.import_sqlite_to_postgres import migrate
    with tempfile.TemporaryDirectory(prefix='psx-private-migration-') as temp:
        source = Path(temp) / 'snapshot.db.gz'
        digest = hashlib.sha256()
        size = 0
        with source.open('wb') as out:
            for i in range(total_chunks):
                data = get(f'chunk:{upload_id}:{i}')
                size += len(data)
                if size > 160*1024*1024:
                    raise ValueError('Compressed snapshot exceeds the staging safety limit.')
                digest.update(data)
                out.write(data)
        if digest.hexdigest() != expected_sha256:
            raise ValueError('Snapshot checksum mismatch; no canonical data was changed.')
        result = migrate(source, confirm=True)
    # Copy committed and reconciled. Only this upload's pieces are expendable.
    cleanup = True
    try:
        for i in range(total_chunks):
            delete(f'chunk:{upload_id}:{i}')
    except Exception:
        cleanup = False
    return {**result, 'source_sha256': expected_sha256, 'source_bytes': size,
            'temporary_chunks_removed': cleanup,
            'cleanup_note': 'Only derived upload staging is removed; original and canonical data are retained.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--upload-id', required=True)
    p.add_argument('--total-chunks', type=int, required=True)
    p.add_argument('--expected-sha256', required=True)
    a = p.parse_args()
    try:
        print(json.dumps(migrate_staged(a.upload_id, a.total_chunks, a.expected_sha256)))
    except ValueError as exc:
        print(json.dumps({'status': 'REFUSED', 'detail': str(exc)}))
        raise SystemExit(1)
    except Exception:
        print(json.dumps({'status': 'FAILED', 'detail': 'Migration did not report success. Check target counts before retrying; credentials are not printed.'}))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
