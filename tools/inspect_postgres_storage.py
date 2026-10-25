"""Read-only size audit: no account values, filenames, secrets, deletes or vacuum."""
import psycopg
from psycopg.rows import dict_row
from psx_app.database.postgres import settings

OPTIONS='-c client_encoding=UTF8 -c default_transaction_read_only=on -c statement_timeout=30000'

def audit_database(c):
    with c.cursor(row_factory=dict_row) as q:
        tables=q.execute("""SELECT s.relname AS table_name,s.n_live_tup AS estimated_live_rows,
          s.n_dead_tup AS estimated_dead_rows,pg_relation_size(s.relid) AS heap_bytes,
          pg_indexes_size(s.relid) AS index_bytes,pg_total_relation_size(s.relid) AS total_bytes
          FROM pg_stat_user_tables s WHERE s.schemaname='public'
          ORDER BY pg_total_relation_size(s.relid) DESC""").fetchall()
        indexes=q.execute("""SELECT t.relname AS table_name,i.relname AS index_name,
          pg_relation_size(i.oid) AS bytes,pg_get_indexdef(i.oid) AS definition
          FROM pg_index x JOIN pg_class i ON i.oid=x.indexrelid JOIN pg_class t ON t.oid=x.indrelid
          JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public'
          ORDER BY pg_relation_size(i.oid) DESC LIMIT 20""").fetchall()
        result={'tables':tables,'largest_indexes':indexes}
        names={t['table_name'] for t in tables}
        if 'psx_blob_parts' in names:
            result['temporary_uploads']=dict(q.execute("""SELECT COUNT(*) AS pieces,
              COALESCE(SUM(octet_length(data)),0) AS payload_bytes,
              COUNT(*) FILTER (WHERE updated_at < EXTRACT(EPOCH FROM NOW())-86400) AS expired_pieces,
              COALESCE(SUM(octet_length(data)) FILTER (WHERE updated_at < EXTRACT(EPOCH FROM NOW())-86400),0) AS expired_payload_bytes
              FROM psx_blob_parts""").fetchone())
        if 'equity_ohlcv' in names:
            result['recent_cash_sessions']=q.execute("""SELECT e.trade_date,COUNT(*) AS records,
              SUM(pg_column_size(e)) AS logical_row_bytes
              FROM equity_ohlcv e WHERE e.trade_date IN
              (SELECT DISTINCT trade_date FROM equity_ohlcv ORDER BY trade_date DESC LIMIT 10)
              GROUP BY e.trade_date ORDER BY e.trade_date DESC""").fetchall()
        return result


def inspect_storage():
    cfg=settings()
    with psycopg.connect(**cfg,autocommit=True,options=OPTIONS) as c:
        names=c.execute("""SELECT datname,pg_database_size(oid) FROM pg_database
          WHERE NOT datistemplate AND datallowconn AND has_database_privilege(oid,'CONNECT')
          ORDER BY datname LIMIT 12""").fetchall()
        source=c.execute('SELECT current_database()').fetchone()[0]
    result={'status':'READ_ONLY_STORAGE_AUDIT','connection_default_database':source,'databases':[],
      'note':'Database totals exclude shared WAL/system overhead. Dead-row counts are estimates. Logical row bytes exclude indexes and page overhead. No data or caches were deleted.'}
    for name,size in names:
        # Provider-owned administrative databases are reported by size only.
        item={'database':name,'database_bytes':size}
        if name==source or name.startswith('psx_restore_'):
            with psycopg.connect(**{**cfg,'dbname':name},autocommit=True,options=OPTIONS) as c:
                item.update(audit_database(c))
        result['databases'].append(item)
    return result
