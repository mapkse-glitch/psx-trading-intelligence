"""Explicit, bounded maintenance: verified staging only; one catalog-checked duplicate index."""
import hashlib
import json
import os
import re
import time
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psx_app.database.postgres import settings

SHA='64b36a85534ed9e9b571ba8522046c2ccb5f0185631ee6e6fe52611734fc3333'
SIZE=42959798
MIN_PRICE_ROWS=731806
CANDIDATE='psx_restore_'+SHA[:12]
CONFIRM='CLEAN_MIGRATION_UPLOADS_AND_DUPLICATE_INDEX'
OPTIONS='-c client_encoding=UTF8 -c statement_timeout=120000 -c lock_timeout=5000'

def index_info(c,name):
    with c.cursor(row_factory=dict_row) as q:
        return q.execute("""SELECT i.indexrelid,i.indrelid,i.indisunique,i.indisprimary,
          i.indisvalid,i.indisready,i.indisreplident,i.indisclustered,i.indnkeyatts,i.indnatts,
          i.indkey::text AS keys,i.indcollation::text AS collations,
          i.indclass::text AS opclasses,i.indoption::text AS options,
          pg_get_expr(i.indexprs,i.indrelid) AS expressions,
          pg_get_expr(i.indpred,i.indrelid) AS predicate,k.relam,
          t.relname AS table_name,t.relnamespace='public'::regnamespace AS public_table,
          EXISTS(SELECT 1 FROM pg_constraint z WHERE z.conindid=i.indexrelid) AS constraint_backed,
          pg_relation_size(k.oid) AS bytes
          FROM pg_index i JOIN pg_class k ON k.oid=i.indexrelid
          JOIN pg_class t ON t.oid=i.indrelid
          WHERE i.indexrelid=to_regclass(%s)""",('public.'+name,)).fetchone()

def validate_duplicate(c):
    redundant=index_info(c,'idx_eq_date_sym')
    kept=index_info(c,'equity_ohlcv_trade_date_symbol_key')
    if not kept or not kept['indisunique'] or not kept['indisvalid'] or not kept['indisready'] or not kept['constraint_backed']:
        raise ValueError('UNIQUE_PRICE_CONSTRAINT_NOT_HEALTHY')
    if kept['table_name']!='equity_ohlcv' or not kept['public_table'] or kept['predicate'] is not None or kept['expressions'] is not None:
        raise ValueError('UNEXPECTED_UNIQUE_PRICE_INDEX')
    # Business-key columns, not just two coincidentally identical index definitions.
    cols=c.execute("""SELECT a.attname FROM pg_attribute a
      JOIN pg_index i ON i.indrelid=a.attrelid
      CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum,position)
      WHERE i.indexrelid=%s AND a.attnum=k.attnum ORDER BY k.position""",(kept['indexrelid'],)).fetchall()
    if [x[0] for x in cols]!=['trade_date','symbol']:
        raise ValueError('UNEXPECTED_PRICE_INDEX_COLUMNS')
    if redundant is None:return {'already_absent':True,'bytes':0}
    if redundant['indisunique'] or redundant['indisprimary'] or redundant['constraint_backed'] or redundant['indisreplident'] or redundant['indisclustered'] or not redundant['indisvalid'] or not redundant['indisready']:
        raise ValueError('INDEX_NOT_SAFE_TO_DROP')
    fields=['indrelid','indnkeyatts','indnatts','keys','collations','opclasses','options','expressions','predicate','relam']
    if any(redundant[x]!=kept[x] for x in fields):raise ValueError('INDEX_IS_NOT_AN_EXACT_DUPLICATE')
    return {'already_absent':False,'bytes':redundant['bytes']}

def verified_upload_scopes(c,expected_sha=SHA,expected_size=SIZE):
    rows=c.execute("SELECT scope,part,octet_length(data),updated_at FROM psx_blob_parts WHERE scope LIKE 'chunk:migration-%%' ORDER BY scope,part").fetchall()
    groups={}
    for scope,part,size,updated in rows:
        m=re.fullmatch(r'chunk:(migration-[A-Za-z0-9_-]{8,80}):(\d+)',scope)
        if m:groups.setdefault(m[1],{}).setdefault(int(m[2]),[]).append((scope,part,size,updated))
    verified=[];skipped=0;payload=0;matches=0
    for upload,chunks in groups.items():
        if sorted(chunks)!=list(range(len(chunks))) or len(chunks)>160:skipped+=1;continue
        if sum(p[2] for values in chunks.values() for p in values)!=expected_size:skipped+=1;continue
        if max(p[3] for values in chunks.values() for p in values)>time.time()-900:skipped+=1;continue
        digest=hashlib.sha256();scopes=[];valid=True
        for idx in range(len(chunks)):
            parts=chunks[idx]
            if [p[1] for p in parts]!=list(range(len(parts))):valid=False;break
            scope=parts[0][0];scopes.append(scope)
            for (data,) in c.execute('SELECT data FROM psx_blob_parts WHERE scope=%s ORDER BY part',(scope,)):
                digest.update(bytes(data))
        if valid and digest.hexdigest()==expected_sha:verified.extend(scopes);payload+=expected_size;matches+=1
        else:skipped+=1
    return {'scopes':verified,'matching_uploads':matches,
            'payload_bytes':payload,'unmatched_or_recent_uploads_preserved':skipped}

def fingerprint(c):
    # Returned only as a comparison boolean; financial aggregate values never logged.
    tables=['equity_ohlcv','futures_ohlcv','index_ohlcv','accounts','trade_executions',
            'account_daily_symbol_summary','top5_volume_records','source_files','import_batches']
    counts={t:c.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(t))).fetchone()[0] for t in tables}
    values=c.execute('SELECT COUNT(*),COALESCE(SUM(gross_pnl),0),COALESCE(SUM(net_pnl),0),COALESCE(SUM(total_charges),0) FROM account_daily_symbol_summary').fetchone()
    return counts,values

def db_size(c):return c.execute('SELECT pg_database_size(current_database())').fetchone()[0]

def maintain(apply=False,confirm=''):
    if apply and confirm!=CONFIRM:raise ValueError('EXPLICIT_CLEANUP_CONFIRMATION_REQUIRED')
    cfg=settings()
    with psycopg.connect(**cfg,autocommit=True,options=OPTIONS) as source:
        source_name=source.execute('SELECT current_database()').fetchone()[0]
        if source_name==CANDIDATE:raise ValueError('ACTIONS_MUST_SELECT_ORIGINAL_STAGING_DATABASE')
        with psycopg.connect(**{**cfg,'dbname':CANDIDATE},autocommit=True,options=OPTIONS) as active:
            if active.execute('SELECT COUNT(*) FROM equity_ohlcv').fetchone()[0]<MIN_PRICE_ROWS:
                raise ValueError('RESTORED_PRICE_HISTORY_NOT_CONFIRMED')
            before={'original_database_bytes':db_size(source),'active_database_bytes':db_size(active)}
            sf,af=fingerprint(source),fingerprint(active)
            index=validate_duplicate(active)
            # Lock ONLY staging in the old database, not the active price/account tables.
            with source.transaction():
                source.execute('LOCK TABLE public.psx_blob_parts IN SHARE ROW EXCLUSIVE MODE')
                uploads=verified_upload_scopes(source,expected_sha=SHA,expected_size=SIZE)
                deleted=0
                if apply and uploads['scopes']:
                    deleted=source.execute('DELETE FROM public.psx_blob_parts WHERE scope=ANY(%s)',(uploads['scopes'],)).rowcount
            if apply and not index['already_absent']:
                # Outside a transaction; the retained unique index handles the same lookups.
                validate_duplicate(active)
                active.execute('DROP INDEX CONCURRENTLY public.idx_eq_date_sym')
            if apply and deleted:
                source.execute('VACUUM (ANALYZE) public.psx_blob_parts')
            after={'original_database_bytes':db_size(source),'active_database_bytes':db_size(active)}
            unchanged=(sf==fingerprint(source) and af==fingerprint(active))
            if not unchanged:raise ValueError('CANONICAL_COUNTS_OR_ACCOUNT_TOTALS_CHANGED_REVIEW_IMPORT_ACTIVITY')
            if apply and index_info(active,'idx_eq_date_sym') is not None:raise ValueError('REDUNDANT_INDEX_STILL_PRESENT')
            validate_duplicate(active)
            return {'status':'CLEANUP_COMPLETED' if apply else 'CLEANUP_PREVIEW_ONLY',
              'before':before,'after':after,'database_size_reduction_bytes':sum(before.values())-sum(after.values()),
              'matching_completed_migration_uploads':uploads['matching_uploads'],
              'verified_staging_payload_bytes':uploads['payload_bytes'],'staging_pieces_deleted':deleted,
              'unmatched_or_recent_uploads_preserved':uploads['unmatched_or_recent_uploads_preserved'],
              'redundant_index_bytes':index['bytes'],'redundant_index_removed':apply and not index['already_absent'],
              'unique_price_constraint_preserved':True,'canonical_counts_and_account_totals_unchanged':True,
              'rollback_database_retained':True,'vacuum_full_used':False,
              'note':'Only verified migration staging and one exact duplicate index targeted. Service disk gauge also includes WAL/shared overhead; this is not a WAL measurement.'}

def main():
    try:
        mode=os.getenv('STORAGE_MODE','preview')
        if mode not in ('preview','cleanup'):raise ValueError('INVALID_MODE')
        print(json.dumps(maintain(mode=='cleanup',os.getenv('STORAGE_CONFIRM',''))))
    except ValueError as exc:
        code=str(exc)
        if not re.fullmatch('[A-Z_]+',code):code='CLEANUP_REFUSED'
        raise SystemExit('STORAGE_STATUS: '+code) from None
    except Exception:
        raise SystemExit('STORAGE_STATUS: STOPPED_INSPECT_BEFORE_RETRY. Raw errors and credentials are not logged. Already committed cleanup may be partial; no canonical-record deletion is used.') from None

if __name__=='__main__':main()
