"""Durable bounded upload pieces; independent of a Vercel worker's temporary disk."""
import gzip
import json
import time
from psx_app.database.schema import get_connection

PART_SIZE = 192 * 1024
MAX_BLOB = 160 * 1024 * 1024
TTL = 24 * 3600


def put(scope, data, conn=None):
    if len(data) > MAX_BLOB:
        raise ValueError('Staged payload exceeds the 160 MB durable staging limit. Split the source upload.')
    def write(c):
        c.execute('DELETE FROM psx_blob_parts WHERE scope=?', (scope,))
        c.executemany('INSERT INTO psx_blob_parts(scope,part,data,updated_at) VALUES (?,?,?,?)',
                      [(scope, i, data[p:p+PART_SIZE], int(time.time())) for i, p in enumerate(range(0, len(data), PART_SIZE))])
    if conn is not None:
        write(conn)
    else:
        with get_connection() as c:
            write(c)


def get(scope):
    out = bytearray()
    with get_connection() as c:
        # One bounded response per piece, not an unbounded BLOB query.
        parts = [r[0] for r in c.execute('SELECT part FROM psx_blob_parts WHERE scope=? ORDER BY part', (scope,))]
        if not parts:
            raise FileNotFoundError('Durable staging expired or was not completed. Re-upload the source file.')
        if parts != list(range(len(parts))):
            raise ValueError('Staging is incomplete. Re-upload this file.')
        for start in range(0, len(parts), 8):
            rows = c.execute('SELECT part,data FROM psx_blob_parts WHERE scope=? AND part>=? AND part<? ORDER BY part', (scope, start, start+8)).fetchall()
            if [r[0] for r in rows] != parts[start:start+8]:
                raise ValueError('Staging changed during retrieval; re-upload the file.')
            for row in rows:
                out.extend(row[1])
            if len(out) > MAX_BLOB:
                raise ValueError('Staging size limit exceeded.')
    return bytes(out)


def delete(scope):
    with get_connection() as c:
        c.execute('DELETE FROM psx_blob_parts WHERE scope=?', (scope,))


def sweep():
    with get_connection() as c:
        c.execute('DELETE FROM psx_blob_parts WHERE updated_at<?', (int(time.time()) - TTL,))


def pack(bundle):
    return gzip.compress(json.dumps(bundle, separators=(',', ':')).encode(), compresslevel=1)


def unpack(data):
    # Bound inflated JSON as well as its compressed representation.
    import io
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
        raw = f.read(512 * 1024 * 1024 + 1)
    if len(raw) > 512 * 1024 * 1024:
        raise ValueError('Inflated staged JSON exceeds safe processing size.')
    return json.loads(raw)
