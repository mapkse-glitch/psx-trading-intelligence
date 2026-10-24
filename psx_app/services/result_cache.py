"""Shared PostgreSQL result cache keyed by canonical revision and Karachi day.
Expendable derived results, never a source of truth. Maximum 200 entries, 512 KiB
compressed text / 2 MiB inflated per entry. Cache writes never advance revision.
"""
import base64
import functools
import gzip
import hashlib
import inspect
import io
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def persisted_result(fn):
    sig=inspect.signature(fn)
    @functools.wraps(fn)
    def wrapped(*args,**kwargs):
        from psx_app.database.turso import backend_name
        if backend_name()!='postgres': return fn(*args,**kwargs)
        from psx_app.database.schema import get_connection
        bound=sig.bind(*args,**kwargs);bound.apply_defaults()
        values={k:v for k,v in bound.arguments.items() if k!='self'}
        key=hashlib.sha256(json.dumps([fn.__module__,fn.__qualname__,values,'1.3.15',datetime.now(ZoneInfo('Asia/Karachi')).date().isoformat()],sort_keys=True,default=str).encode()).hexdigest()
        path=getattr(args[0],'db_path',None) if args else None
        with get_connection(path) as c:
            rev=c.execute("SELECT value FROM psx_runtime WHERE key='revision'").fetchone()[0]
            row=c.execute('SELECT payload_json FROM analysis_cache WHERE cache_key=? AND revision=?',(key,rev)).fetchone()
        if row:
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(base64.b64decode(row[0]))) as f: raw=f.read(2*1024*1024+1)
                if len(raw)<=2*1024*1024: return json.loads(raw)
            except (ValueError,OSError): pass
        result=fn(*args,**kwargs)
        raw=json.dumps(result,separators=(',',':'),allow_nan=False).encode()
        if len(raw)>2*1024*1024: return result
        packed=base64.b64encode(gzip.compress(raw,compresslevel=1)).decode()
        if len(packed)>512*1024: return result
        with get_connection(path) as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT value FROM psx_runtime WHERE key='revision'").fetchone()[0]==rev:
                c.execute('INSERT INTO analysis_cache(cache_key,revision,payload_json,updated_at) VALUES (?,?,?,?) ON CONFLICT(cache_key) DO UPDATE SET revision=excluded.revision,payload_json=excluded.payload_json,updated_at=excluded.updated_at',(key,rev,packed,datetime.now(timezone.utc).isoformat()))
                c.execute('DELETE FROM analysis_cache WHERE cache_key NOT IN (SELECT cache_key FROM analysis_cache ORDER BY updated_at DESC,cache_key LIMIT 200)')
        return result
    return wrapped
