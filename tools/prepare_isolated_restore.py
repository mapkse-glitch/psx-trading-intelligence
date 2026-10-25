"""Prepare and verify a separate PostgreSQL restore; never switch or overwrite live DB."""
import hashlib
import json
import os
import re
import ssl
import tempfile
from pathlib import Path

KEYS = {
    'accounts': ['account_id'], 'app_settings': ['key'], 'sync_state': ['key'],
    'import_batches': ['batch_uuid'],
    'top5_volume_records': ['trade_date','ticker','rank'],
    'trade_executions': ['account_id','unique_trade_key'],
    'account_daily_symbol_summary': ['account_id','trade_date','symbol'],
    'equity_ohlcv': ['trade_date','symbol'],
    'futures_ohlcv': ['trade_date','contract_symbol'], 'index_ohlcv': ['trade_date'],
    'company_reference': ['list_name','symbol'], 'forecast_ledger': ['forecast_id'],
    'forecast_observations': ['forecast_id','digest'], 'learning_runs': ['run_id'],
}


def connection_check():
    """Only SELECT statements; all reported errors use fixed strings."""
    import psycopg
    from psx_app.database.postgres import settings
    try:
        cfg = settings()
        ssl.create_default_context(cafile=cfg['sslrootcert']) if cfg.get('sslmode') != 'disable' else None
    except Exception:
        raise ValueError('CA_OR_URI_CONFIGURATION_INVALID') from None
    try:
        with psycopg.connect(**cfg,autocommit=True,options='-c client_encoding=UTF8') as c:
            c.execute('SELECT 1').fetchone()
            return {'status':'VERIFIED_CONNECTION','live_database':c.execute('SELECT current_database()').fetchone()[0],
                    'live_database_bytes':c.execute('SELECT pg_database_size(current_database())').fetchone()[0]}
    except Exception as exc:
        text=str(exc).lower()
        choices=[('hostname','TLS_HOSTNAME_MISMATCH'),('certificate verify failed','TLS_CA_NOT_TRUSTED'),
                 ('root certificate file','TLS_CA_FILE_INVALID'),('password authentication failed','AUTHENTICATION_REJECTED'),
                 ('timeout','NETWORK_TIMEOUT'),('could not translate host','DNS_FAILED')]
        code=next((code for term,code in choices if term in text),'CONNECTION_FAILED')
        raise ValueError(code) from None


def merge_live(source, target, tables):
    """Bulk-copy live business keys into candidate; never mutate source.
    One temporary table and bounded SQL statements per canonical table, not per row.
    """
    from psycopg import sql
    from psycopg.rows import dict_row
    maps={'source_files':{},'import_batches':{}}
    result={}
    for table in tables:
        cols=[r[0] for r in source.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=\'public\' AND table_name=%s ORDER BY ordinal_position',(table,))]
        if not cols:continue
        target_cols={r[0] for r in target.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=\'public\' AND table_name=%s',(table,))}
        if not set(cols)<=target_cols:raise ValueError('RESTORE_SCHEMA_MISMATCH')
        count=source.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
        if count>50000:raise ValueError('LIVE_RECONCILIATION_TOO_LARGE_REVIEW_REQUIRED')
        with source.cursor(row_factory=dict_row) as cursor:
            rows=cursor.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(table))).fetchall()
        before=target.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
        if not rows:
            result[table]={'live_rows_checked':0,'added':0,'final_rows':before,'all_live_values_matched':True};continue
        stage=sql.Identifier('psx_restore_live_stage')
        target.execute(sql.SQL('CREATE TEMP TABLE {} (LIKE {}) ON COMMIT DROP').format(stage,sql.Identifier(table)))
        with target.cursor().copy(sql.SQL('COPY {} ({}) FROM STDIN').format(stage,sql.SQL(',').join(map(sql.Identifier,cols)))) as copy:
            for row in rows:
                for col,parent in [('batch_id','import_batches'),('source_file_id','source_files')]:
                    if row.get(col) is not None:
                        if row[col] not in maps[parent]:raise ValueError('UNRESOLVED_LIVE_PROVENANCE_REFERENCE')
                        row[col]=maps[parent][row[col]]
                copy.write_row(tuple(row[k] for k in cols))
        keys=KEYS.get(table,[])
        match=sql.SQL(' AND ').join(sql.SQL('t.{}=s.{}').format(sql.Identifier(k),sql.Identifier(k)) for k in keys)
        if keys:
            overlap=target.execute(sql.SQL('SELECT COUNT(*) FROM {} s WHERE EXISTS (SELECT 1 FROM {} t WHERE {})').format(stage,sql.Identifier(table),match)).fetchone()[0]
        else:overlap=0
        if 'id' in cols:
            target.execute(sql.SQL('ALTER TABLE {} ADD COLUMN restore_source_id BIGINT').format(stage))
            target.execute(sql.SQL('UPDATE {} SET restore_source_id=id').format(stage))
            seq=target.execute('SELECT pg_get_serial_sequence(%s,%s)',(table,'id')).fetchone()[0]
            if not seq:raise ValueError('MISSING_CANDIDATE_ID_SEQUENCE')
            if keys:
                target.execute(sql.SQL('UPDATE {} s SET id=COALESCE((SELECT t.id FROM {} t WHERE {}),nextval(%s))').format(stage,sql.Identifier(table),match),(seq,))
            else:target.execute(sql.SQL('UPDATE {} SET id=nextval(%s)').format(stage),(seq,))
            if table in maps:maps[table]=dict(target.execute(sql.SQL('SELECT restore_source_id,id FROM {}').format(stage)).fetchall())
        names=sql.SQL(',').join(map(sql.Identifier,cols))
        statement=sql.SQL('INSERT INTO {} ({}) SELECT {} FROM {} WHERE TRUE').format(sql.Identifier(table),names,names,stage)
        if keys:
            updates=[k for k in cols if k not in keys and k!='id']
            if updates:
                statement+=sql.SQL(' ON CONFLICT ({}) DO UPDATE SET {}').format(sql.SQL(',').join(map(sql.Identifier,keys)),sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(k),sql.Identifier(k)) for k in updates))
            else:statement+=sql.SQL(' ON CONFLICT ({}) DO NOTHING').format(sql.SQL(',').join(map(sql.Identifier,keys)))
        target.execute(statement)
        identity=sql.SQL('t.id=s.id') if 'id' in cols else match
        equal=sql.SQL(' AND ').join(sql.SQL('t.{} IS NOT DISTINCT FROM s.{}').format(sql.Identifier(k),sql.Identifier(k)) for k in cols)
        mismatches=target.execute(sql.SQL('SELECT COUNT(*) FROM {} s WHERE NOT EXISTS (SELECT 1 FROM {} t WHERE {} AND {})').format(stage,sql.Identifier(table),identity,equal)).fetchone()[0]
        after=target.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
        if mismatches or after!=before+len(rows)-overlap:raise ValueError('LIVE_RECONCILIATION_FAILED')
        result[table]={'live_rows_checked':len(rows),'added':len(rows)-overlap,'final_rows':after,'all_live_values_matched':True}
        target.execute(sql.SQL('DROP TABLE {}').format(stage))
    return result


def verify_candidate_snapshot(raw, compressed, counts):
    """Resume only an unmerged candidate whose rows and totals still match the snapshot."""
    import gzip,sqlite3,math
    from psycopg import sql
    with tempfile.TemporaryDirectory(prefix='psx-resume-check-') as tmp:
        path=Path(tmp)/'snapshot.db'
        with gzip.open(compressed,'rb') as src,path.open('wb') as out:
            import shutil
            shutil.copyfileobj(src,out)
        with sqlite3.connect(path) as src:
            for table,n in counts.items():
                actual=raw.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
                if actual!=n:raise ValueError('RESUME_CANDIDATE_COUNTS_DIFFER_INSPECT_MANUALLY')
                available={r[1] for r in src.execute('PRAGMA table_info('+table+')')}
                candidates=['volume','gross_pnl','net_pnl','buy_value','sell_value','quantity','trade_value']
                metrics=[k for k in candidates if k in available]
                if metrics:
                    expr=','.join('COALESCE(SUM("'+k+'"),0)' for k in metrics)
                    before=src.execute('SELECT '+expr+' FROM '+table).fetchone()
                    after=raw.execute(sql.SQL('SELECT '+expr+' FROM {}').format(sql.Identifier(table))).fetchone()
                    if any((int(a)!=int(b) if k=='volume' else not math.isclose(float(a),float(b),rel_tol=1e-12,abs_tol=0.01)) for k,a,b in zip(metrics,before,after)):
                        raise ValueError('RESUME_CANDIDATE_AGGREGATES_DIFFER_INSPECT_MANUALLY')
    return {'counts_matched':True,'available_volume_and_financial_sums_matched':True}


def prepare(upload_id,total_chunks,expected_sha256,resume=False):
    import psycopg
    from psycopg import sql
    from psx_app.database import postgres
    from psx_app.services.remote_staging import get
    from tools.import_sqlite_to_postgres import migrate,TABLES
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',upload_id) or not 1<=total_chunks<=160 or not re.fullmatch(r'[a-f0-9]{64}',expected_sha256):
        raise ValueError('INVALID_STAGED_UPLOAD_ARGUMENTS')
    cfg=postgres.settings()
    with tempfile.TemporaryDirectory(prefix='psx-isolated-restore-') as tmp:
        path=Path(tmp)/'source.db.gz';digest=hashlib.sha256();size=0
        with path.open('wb') as out:
            for i in range(total_chunks):
                data=get(f'chunk:{upload_id}:{i}');size+=len(data)
                if size>160*1024*1024:raise ValueError('STAGED_SNAPSHOT_TOO_LARGE')
                digest.update(data);out.write(data)
        if digest.hexdigest()!=expected_sha256:raise ValueError('SOURCE_CHECKSUM_MISMATCH')
        preview=migrate(path,False)
        candidate='psx_restore_'+expected_sha256[:12]
        with psycopg.connect(**cfg,autocommit=True,options='-c client_encoding=UTF8') as source:
            live_name=source.execute('SELECT current_database()').fetchone()[0]
            if live_name==candidate:raise ValueError('CANDIDATE_CANNOT_BE_LIVE_DATABASE')
            exists=bool(source.execute('SELECT 1 FROM pg_database WHERE datname=%s',(candidate,)).fetchone())
            if exists and not resume:
                raise ValueError('CANDIDATE_ALREADY_EXISTS_INSPECT_BEFORE_RETRY_NO_DATA_OVERWRITTEN')
            if resume and not exists:raise ValueError('NO_EXISTING_CANDIDATE_TO_RESUME')
            # Conservative service-level headroom estimate; no paid capacity is provisioned.
            current_bytes=source.execute('SELECT COALESCE(SUM(pg_database_size(oid)),0) FROM pg_database WHERE NOT datistemplate').fetchone()[0]
            if current_bytes+(50 if resume else 400)*1024*1024+200*1024*1024>950*1024*1024:
                raise ValueError('INSUFFICIENT_FREE_PLAN_STORAGE_HEADROOM')
            if not exists:source.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(candidate)))
        saved_uri=os.environ['DATABASE_URL'];old_ready=postgres._READY
        saved_override=os.environ.pop('PSX_POSTGRES_DATABASE',None)
        try:
            # settings() requires URI syntax, so use an encoded URI with only its database changed.
            from urllib.parse import urlsplit,urlunsplit,quote
            parsed=urlsplit(saved_uri)
            os.environ['DATABASE_URL']=urlunsplit((parsed.scheme,parsed.netloc,'/'+quote(candidate,safe=''),parsed.query,parsed.fragment))
            postgres._READY=False
            if resume:
                from tools.import_sqlite_to_postgres import EMPTY_REQUIRED
                with psycopg.connect(**postgres.settings(),autocommit=True,options='-c client_encoding=UTF8') as prior:
                    populated=any(prior.execute(sql.SQL('SELECT EXISTS(SELECT 1 FROM {})').format(sql.Identifier(t))).fetchone()[0] for t in EMPTY_REQUIRED)
                    verified=verify_candidate_snapshot(prior,path,preview['source_counts']) if populated else None
                migrated={'copied':preview['source_counts'],'aggregate_checks':{'resume_verification':verified}} if populated else migrate(path,True)
            else:migrated=migrate(path,True)
            with psycopg.connect(**cfg,autocommit=True,options='-c client_encoding=UTF8') as source, psycopg.connect(**postgres.settings(),autocommit=True,options='-c client_encoding=UTF8') as target:
                with source.transaction():
                    source.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                    source.execute('SELECT pg_advisory_xact_lock(%s)',(731314,))
                    revision=source.execute("SELECT value FROM psx_runtime WHERE key='revision'").fetchone()[0]
                    with target.transaction():
                        target.execute("SET LOCAL statement_timeout='10min'")
                        target.execute('SELECT pg_advisory_xact_lock(%s)',(731314,))
                        combined=merge_live(source,target,TABLES)
                        target.execute('DELETE FROM indicator_cache');target.execute('DELETE FROM analysis_cache')
                        import uuid
                        target.execute("UPDATE psx_runtime SET value=%s WHERE key='revision'",(uuid.uuid4().hex,))
                        for table in TABLES:target.execute(sql.SQL('ANALYZE {}').format(sql.Identifier(table)))
                final_bytes=target.execute('SELECT pg_database_size(current_database())').fetchone()[0]
        finally:
            os.environ['DATABASE_URL']=saved_uri;postgres._READY=old_ready
            if saved_override is not None:os.environ['PSX_POSTGRES_DATABASE']=saved_override
        # Keep private source chunks until the operator checks the candidate; TTL still applies.
        return {'status':'CANDIDATE_VERIFIED_NOT_ACTIVATED','candidate_database':candidate,'source_sha256':expected_sha256,
                'source_snapshot_counts':preview['source_counts'],'snapshot_copy':migrated['copied'],
                'snapshot_aggregate_checks':migrated['aggregate_checks'],'live_reconciliation':combined,
                'live_revision_at_reconciliation':revision,'candidate_bytes':final_bytes,
                'live_database_unchanged':True,'activation_required':True,
                'note':'Never rerun restore into this candidate. Compare live revision before activation; retain original live DB. No credentials or account values are logged.'}


def main():
    try:
        mode=os.getenv('RESTORE_MODE','check_connection')
        result=connection_check()
        if mode in ('restore_candidate','resume_candidate'):
            if os.getenv('RESTORE_CONFIRM')!='RESTORE_SEPARATE_DATABASE':raise ValueError('EXPLICIT_RESTORE_CONFIRMATION_REQUIRED')
            result=prepare(os.environ['UPLOAD_ID'],int(os.environ['TOTAL_CHUNKS']),os.environ['EXPECTED_SHA256'],resume=mode=='resume_candidate')
        elif mode=='inspect_storage':
            from tools.inspect_postgres_storage import inspect_storage
            result=inspect_storage()
        elif mode!='check_connection':raise ValueError('INVALID_MODE')
        print(json.dumps(result))
    except ValueError as exc:
        # Only fixed controlled codes are printed, never driver error text.
        code=str(exc)
        if not re.fullmatch('[A-Z_]+',code):code='RESTORE_REFUSED'
        raise SystemExit('RESTORE_STATUS: '+code) from None
    except Exception:
        raise SystemExit('RESTORE_STATUS: STOPPED. No activation was attempted. Inspect candidate and live counts before retrying; raw errors and credentials are not printed.') from None

if __name__=='__main__':main()
