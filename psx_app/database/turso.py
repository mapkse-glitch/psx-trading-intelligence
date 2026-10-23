"""Direct libSQL HTTP connections. No embedded replica, snapshot, or SQLite fallback."""
import os
import re
import sqlite3
import uuid
from urllib.parse import urlsplit


def enabled():
    backend = os.getenv('PSX_DATABASE_BACKEND', 'turso' if os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME') else 'sqlite').strip().lower()
    if backend not in ('sqlite', 'turso'):
        raise RuntimeError('PSX_DATABASE_BACKEND must be sqlite or turso.')
    if backend == 'sqlite' and (os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME')):
        raise RuntimeError('Serverless deployments require PSX_DATABASE_BACKEND=turso. Local SQLite fallback is disabled.')
    return backend == 'turso'


def credentials():
    url = os.getenv('TURSO_DATABASE_URL', '').strip()
    token = os.getenv('TURSO_AUTH_TOKEN', '').strip()
    parsed = urlsplit(url)
    if parsed.scheme not in ('libsql', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise RuntimeError('Set a valid libsql:// or https:// TURSO_DATABASE_URL in server environment settings.')
    if not token:
        raise RuntimeError('TURSO_AUTH_TOKEN is required. No local fallback is allowed.')
    return url, token


class Row(tuple):
    def __new__(cls, values, names):
        obj = super().__new__(cls, values)
        obj.names = names
        return obj

    def keys(self):
        return self.names

    def __getitem__(self, key):
        return super().__getitem__([n.casefold() for n in self.names].index(key.casefold()) if isinstance(key, str) else key)


class Cursor:
    def __init__(self, raw):
        self.raw = raw
        self.names = [c[0] for c in (raw.description or ())]
        self.lastrowid = raw.lastrowid
        self.rowcount = raw.rowcount
        self.description = raw.description

    def fetchone(self):
        row = self.raw.fetchone()
        return None if row is None else Row(row, self.names)

    def fetchall(self):
        return [Row(r, self.names) for r in self.raw.fetchall()]

    def __iter__(self):
        while (row := self.fetchone()) is not None:
            yield row


class Connection:
    def __init__(self, raw):
        self.raw = raw
        self.dirty = False
        self.closed = False

    def execute(self, sql, parameters=()):
        # Read-only cache writes and temporary upload data must not trigger browser refresh loops.
        change = re.match(r'\s*(?:INSERT(?:\s+OR\s+\w+)?\s+INTO|UPDATE|DELETE\s+FROM)\s+["`\[]?(\w+)', sql, re.I)
        if change and change[1].lower() not in ('indicator_cache', 'psx_blob_parts', 'psx_runtime', 'forecast_ledger', 'forecast_observations', 'learning_runs', 'reference_previews'):
            self.dirty = True
        try:
            return Cursor(self.raw.execute(sql, parameters))
        except Exception as exc:
            # Do not reflect connection strings, authorization headers, or driver diagnostics.
            raise sqlite3.DatabaseError('Turso database operation failed; transaction was not confirmed. Check server logs and retry status before resubmitting.') from None

    def executemany(self, sql, parameters):
        rows = list(parameters)
        if not rows:
            return
        # Bound multi-row INSERTs reduce remote round trips without changing transaction boundaries.
        match = re.match(r'(?is)^(\s*INSERT\b.*?\bVALUES\s*)(\([^()]*\))(.*)$', sql.strip().rstrip(';'))
        if match and '?' in match[2]:
            width = len(rows[0])
            batch = []
            size = 0
            for row in rows:
                estimate = sum(len(str(x)) for x in row)
                if batch and (len(batch) * width + width > 900 or size + estimate > 300_000):
                    self.execute(match[1] + ','.join([match[2]] * len(batch)) + match[3], tuple(x for r in batch for x in r))
                    batch, size = [], 0
                batch.append(row)
                size += estimate
            if batch:
                self.execute(match[1] + ','.join([match[2]] * len(batch)) + match[3], tuple(x for r in batch for x in r))
        else:
            for row in rows:
                self.execute(sql, row)

    def commit(self):
        if self.dirty:
            self.raw.execute("UPDATE psx_runtime SET value=? WHERE key='revision'", (uuid.uuid4().hex,))
        try:
            self.raw.commit()
        except Exception:
            raise sqlite3.DatabaseError('Turso commit acknowledgement unavailable. Recheck batch status before retrying; do not assume failure or success.') from None
        self.dirty = False

    def rollback(self):
        self.raw.rollback()
        self.dirty = False

    def close(self):
        if not self.closed:
            self.raw.close()
            self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, kind, value, tb):
        try:
            if kind:
                self.rollback()
            else:
                self.commit()
        finally:
            self.close()


def connect():
    url, token = credentials()
    try:
        import libsql
        raw = libsql.connect(database=url, auth_token=token)
        raw.execute('PRAGMA foreign_keys=ON')
        return Connection(raw)
    except Exception:
        raise RuntimeError('Turso connection failed. Check the private database token and URL; no local fallback was used.') from None


def initialize():
    # The existing imported database is required. Never create an empty canonical replacement.
    with connect() as c:
        required = {'equity_ohlcv', 'futures_ohlcv', 'top5_volume_records', 'trade_executions',
                    'account_daily_symbol_summary', 'accounts', 'app_settings', 'import_batches', 'audit_events'}
        found = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required <= found:
            raise RuntimeError('Imported PSX schema is missing. Check the Turso database URL; startup stopped without seeding data.')
        c.execute('CREATE TABLE IF NOT EXISTS psx_runtime (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        c.execute("INSERT OR IGNORE INTO psx_runtime VALUES ('revision', 'initial')")
        c.execute('''CREATE TABLE IF NOT EXISTS psx_blob_parts (
            scope TEXT NOT NULL, part INTEGER NOT NULL, data BLOB NOT NULL,
            updated_at INTEGER NOT NULL, PRIMARY KEY(scope, part))''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_psx_blob_age ON psx_blob_parts(updated_at)')
        from psx_app.database.schema import DDL_STATEMENTS
        # Only new additive tables; never recreate/drop imported canonical price/account tables.
        for statement in DDL_STATEMENTS.split('CREATE TABLE IF NOT EXISTS source_files',1)[0].split(';'):
            if 'CREATE TABLE' in statement or 'CREATE INDEX' in statement:
                c.execute(statement.strip())
        c.commit()



def revision():
    with connect() as c:
        return c.execute("SELECT value FROM psx_runtime WHERE key='revision'").fetchone()[0]


_READY = False
import threading
_READY_LOCK = threading.Lock()

def ensure_ready():
    global _READY
    if not _READY:
        with _READY_LOCK:
            if not _READY:
                initialize()
                _READY = True
