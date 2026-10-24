"""One-time SQLite snapshot conversion into an EMPTY PostgreSQL application DB.
Not a web endpoint. Can run on a hosted GitHub Actions runner, without localhost.
No credentials in flags, output, repository or snapshot. All copies commit together.
"""
import argparse
import gzip
import json
import sqlite3
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote

TABLES = ['accounts','app_settings','sync_state','source_files','import_batches',
          'import_issues','source_revisions','audit_events','top5_volume_records',
          'trade_executions','account_daily_symbol_summary','equity_ohlcv',
          'futures_ohlcv','index_ohlcv','calculation_rules','company_reference',
          'forecast_ledger','forecast_observations','learning_runs']
EMPTY_REQUIRED = [t for t in TABLES if t not in ('accounts','app_settings','sync_state')]


def migrate(source, confirm=False):
    from psx_app.database.turso import backend_name
    if backend_name()!='postgres': raise ValueError('Set PSX_DATABASE_BACKEND=postgres.')
    source=Path(source).resolve()
    if not source.is_file(): raise ValueError('Snapshot file not found.')
    with tempfile.TemporaryDirectory(prefix='psx-migration-') as temp:
        if source.suffix=='.gz':
            dest=Path(temp)/'snapshot.db'
            total=0
            with gzip.open(source,'rb') as src,dest.open('wb') as out:
                while chunk:=src.read(1024*1024):
                    total+=len(chunk)
                    if total>512*1024*1024: raise ValueError('Snapshot exceeds the 512 MiB migration safety limit.')
                    out.write(chunk)
            source=dest
        if source.stat().st_size>512*1024*1024: raise ValueError('Snapshot exceeds the 512 MiB migration safety limit.')
        with sqlite3.connect('file:'+quote(str(source))+'?mode=ro',uri=True) as src:
            if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('SQLite integrity check failed.')
            available={r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'equity_ohlcv','accounts','app_settings'}<=available: raise ValueError('Not a recognized PSX database snapshot.')
            counts={t:src.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in TABLES if t in available}
            ranges={t:src.execute('SELECT MIN(trade_date),MAX(trade_date) FROM '+t).fetchone() for t in ('equity_ohlcv','futures_ohlcv','index_ohlcv') if t in available}
            if not confirm: return {'status':'DRY_RUN','source_counts':counts,'date_ranges':ranges,'note':'No database writes performed. Use --confirm-empty-target only after reviewing.'}
            from psx_app.database.postgres import ensure_ready,connect
            from psycopg import sql
            ensure_ready()
            with connect() as c:
                with c.raw.transaction():
                    c.raw.execute('SELECT pg_advisory_xact_lock(%s)',(731314,))
                    # Freeze application tables during the snapshot migration. Do
                    # not import files through the dashboard until it completes.
                    c.raw.execute(sql.SQL('LOCK TABLE {} IN ACCESS EXCLUSIVE MODE').format(sql.SQL(',').join(map(sql.Identifier,TABLES))))
                    if any(c.raw.execute(sql.SQL('SELECT EXISTS(SELECT 1 FROM {})').format(sql.Identifier(t))).fetchone()[0] for t in EMPTY_REQUIRED):
                        raise ValueError('Target already contains application data. Refusing to merge or overwrite a snapshot. Use normal source-file import instead.')
                    copied={}
                    for table in TABLES:
                        if table not in available: continue
                        cols=[r[1] for r in src.execute('PRAGMA table_info('+table+')')]
                        target={r[0] for r in c.raw.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s',(table,))}
                        cols=[col for col in cols if col in target]
                        if not cols: continue
                        # Only seeded configuration tables may contain rows.
                        if table in ('accounts','app_settings','sync_state'):
                            c.raw.execute(sql.SQL('DELETE FROM {}').format(sql.Identifier(table)))
                        statement=sql.SQL('COPY {} ({}) FROM STDIN').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,cols)))
                        select='SELECT '+','.join('"'+x.replace('"','""')+'"' for x in cols)+' FROM '+table
                        n=0
                        with c.raw.cursor().copy(statement) as copy:
                            for row in src.execute(select): copy.write_row(row);n+=1
                        got=c.raw.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
                        if got!=counts[table]: raise ValueError('Migration count mismatch; transaction aborted.')
                        copied[table]=n
                        if 'id' in cols:
                            seq=c.raw.execute('SELECT pg_get_serial_sequence(%s,%s)',(table,'id')).fetchone()[0]
                            if seq:
                                maximum=c.raw.execute(sql.SQL('SELECT MAX(id) FROM {}').format(sql.Identifier(table))).fetchone()[0]
                                c.raw.execute('SELECT setval(%s,%s,%s)',(seq,max(maximum or 0,1),bool(maximum)))
                    c.raw.execute('DELETE FROM indicator_cache');c.raw.execute('DELETE FROM analysis_cache')
                    c.raw.execute("UPDATE psx_runtime SET value=%s WHERE key='revision'",(uuid.uuid4().hex,))
                return {'status':'COMMITTED','copied':copied,'date_ranges':ranges,'note':'Counts verified. Compare key reports and latest dates before relying on this snapshot. Staging and derived caches were not migrated.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('--confirm-empty-target',action='store_true');args=p.parse_args()
    try: print(json.dumps(migrate(args.source,args.confirm_empty_target)))
    except (ValueError,FileNotFoundError) as exc: print(json.dumps({'status':'REFUSED','detail':str(exc)}));raise SystemExit(1)
    except Exception: print(json.dumps({'status':'FAILED','detail':'Migration failed; do not assume commit succeeded. Check target counts before retrying. No credential or source data is printed.'}));raise SystemExit(1) from None
if __name__=='__main__':main()
