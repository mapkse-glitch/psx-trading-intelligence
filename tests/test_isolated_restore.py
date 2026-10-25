"""Restore checks use only explicitly selected disposable loopback *_test databases."""
import os
from urllib.parse import urlsplit
import pytest

@pytest.fixture
def pair(monkeypatch):
    import psycopg
    from psx_app.database import postgres
    from psx_app.database.postgres import schema_sql
    url=os.getenv('PSX_TEST_POSTGRES_URL')
    if not url:pytest.skip('Disposable loopback test server required')
    p=urlsplit(url)
    assert p.hostname in ('localhost','127.0.0.1') and p.path.endswith('_test')
    with psycopg.connect(url,autocommit=True,options='-c client_encoding=UTF8') as c:
        c.execute('DROP SCHEMA public CASCADE');c.execute('CREATE SCHEMA public')
        for statement in schema_sql():c.execute(statement)
    second='psx_restore_candidate_test'
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    with psycopg.connect(url,autocommit=True,options='-c client_encoding=UTF8') as c:
        if not c.execute('SELECT 1 FROM pg_database WHERE datname=%s',(second,)).fetchone():c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(second)))
    with psycopg.connect(make_conninfo(url,dbname=second),autocommit=True,options='-c client_encoding=UTF8') as c:
        c.execute('DROP SCHEMA public CASCADE');c.execute('CREATE SCHEMA public')
        for statement in schema_sql():c.execute(statement)
    with psycopg.connect(url,autocommit=True,options='-c client_encoding=UTF8') as source,psycopg.connect(make_conninfo(url,dbname=second),autocommit=True,options='-c client_encoding=UTF8') as target:
        yield source,target


def test_live_business_keys_win_without_deleting_snapshot_history(pair):
    from tools.prepare_isolated_restore import merge_live
    s,t=pair
    t.execute("INSERT INTO equity_ohlcv(trade_date,symbol,close,volume) VALUES ('2026-10-21','ATRL',90,20),('2026-10-22','ATRL',100,30)")
    s.execute("INSERT INTO equity_ohlcv(trade_date,symbol,close,volume) VALUES ('2026-10-22','ATRL',101,35),('2026-10-23','ATRL',102,40)")
    with s.transaction(),t.transaction():result=merge_live(s,t,['equity_ohlcv'])
    assert result['equity_ohlcv']=={'live_rows_checked':2,'added':1,'final_rows':3,'all_live_values_matched':True}
    assert t.execute('SELECT close FROM equity_ohlcv ORDER BY trade_date').fetchall()==[(90,),(101,),(102,)]
    assert s.execute('SELECT COUNT(*) FROM equity_ohlcv').fetchone()[0]==2


def test_live_provenance_ids_remapped_and_monetary_values_preserved(pair):
    from tools.prepare_isolated_restore import merge_live
    s,t=pair
    for c,filename in [(s,'live'),(t,'snapshot')]:
        c.execute("INSERT INTO source_files(id,filename,file_type,sha256_hash,file_size,archive_path,uploaded_at) VALUES (1,%s,'TEST','hash',1,'not-a-file','2026')",(filename,))
        c.execute("INSERT INTO import_batches(id,batch_uuid,created_at) VALUES (1,%s,'2026')",(filename,))
        c.execute("SELECT setval(pg_get_serial_sequence('source_files','id'),1,true)")
        c.execute("SELECT setval(pg_get_serial_sequence('import_batches','id'),1,true)")
    s.execute("INSERT INTO import_issues(batch_id,source_file_id,module,severity,issue_type,message,created_at) VALUES (1,1,'TEST','WARNING','TEST','kept','2026')")
    s.execute("INSERT INTO account_daily_symbol_summary(account_id,trade_date,symbol,batch_id,gross_pnl,net_pnl,updated_at) VALUES ('91404','2026-10-23','ATRL',1,123.45,120.35,'2026')")
    with s.transaction(),t.transaction():result=merge_live(s,t,['source_files','import_batches','import_issues','account_daily_symbol_summary'])
    assert t.execute('SELECT batch_id,source_file_id FROM import_issues').fetchone()==(2,2)
    assert t.execute('SELECT batch_id,gross_pnl,net_pnl FROM account_daily_symbol_summary').fetchone()==(2,123.45,120.35)
    assert s.execute('SELECT batch_id,source_file_id FROM import_issues').fetchone()==(1,1)
    assert t.execute('SELECT COUNT(*) FROM source_files').fetchone()[0]==2


def test_failed_candidate_merge_rolls_back_without_mutating_live(pair):
    from tools.prepare_isolated_restore import merge_live
    s,t=pair
    s.execute("INSERT INTO equity_ohlcv(trade_date,symbol,close,batch_id) VALUES ('2026-10-23','ATRL',100,999)")
    with pytest.raises(ValueError,match='UNRESOLVED_LIVE_PROVENANCE_REFERENCE'):
        with s.transaction(),t.transaction():merge_live(s,t,['equity_ohlcv'])
    assert t.execute('SELECT COUNT(*) FROM equity_ohlcv').fetchone()[0]==0
    assert s.execute('SELECT COUNT(*) FROM equity_ohlcv').fetchone()[0]==1


def test_explicit_database_override_is_validated_without_weakening_tls(monkeypatch):
    from psx_app.database.postgres import settings
    monkeypatch.setenv('DATABASE_URL','postgresql://user:synthetic@127.0.0.1:55433/original_test')
    monkeypatch.setenv('PSX_PG_LOOPBACK_TEST','1')
    monkeypatch.setenv('PSX_POSTGRES_DATABASE','psx_restore_candidate_test')
    assert settings()['dbname']=='psx_restore_candidate_test'
    monkeypatch.setenv('PSX_POSTGRES_DATABASE','bad; DROP DATABASE')
    with pytest.raises(RuntimeError,match='valid lowercase'):settings()
