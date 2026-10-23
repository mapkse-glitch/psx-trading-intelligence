"""Real HTTP integration against an explicitly supplied LOOPBACK libSQL test server.
Run: PSX_TEST_LIBSQL_SERVER=http://127.0.0.1:8176 pytest tests/test_turso_remote.py
Never point this at a real database: the fixture recreates every application table.
"""
import io
import json
import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import openpyxl
import pytest


def test_turso_configuration_is_fail_closed(monkeypatch):
    from psx_app.database.turso import credentials, enabled
    monkeypatch.setenv('PSX_DATABASE_BACKEND', 'turso')
    monkeypatch.delenv('TURSO_AUTH_TOKEN', raising=False)
    monkeypatch.setenv('TURSO_DATABASE_URL', 'libsql://example.turso.io')
    assert enabled()
    with pytest.raises(RuntimeError, match='AUTH_TOKEN'):
        credentials()
    monkeypatch.setenv('TURSO_AUTH_TOKEN', 'synthetic-test-only')
    monkeypatch.setenv('TURSO_DATABASE_URL', 'http://example.com')
    with pytest.raises(RuntimeError, match='valid'):
        credentials()


@pytest.fixture
def remote(monkeypatch, tmp_path):
    url = os.getenv('PSX_TEST_LIBSQL_SERVER')
    if not url:
        pytest.skip('Explicit isolated loopback libSQL server not supplied')
    assert urlsplit(url).hostname in ('127.0.0.1', 'localhost'), 'Only loopback disposable test servers allowed'
    import libsql
    from psx_app.database import turso
    from psx_app.database.schema import DDL_STATEMENTS
    from psx_app.config import DEFAULT_SETTINGS
    raw = libsql.connect(url, auth_token='')
    raw.execute('BEGIN IMMEDIATE')
    raw.execute('PRAGMA defer_foreign_keys=ON')
    for (name,) in raw.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        raw.execute('DROP TABLE "' + name.replace('"', '""') + '"')
    raw.commit()
    raw.executescript(DDL_STATEMENTS.replace('PRAGMA journal_mode = WAL;', ''))
    for account in ('91404', '91269'):
        raw.execute("INSERT INTO accounts VALUES (?, 'THM00601', ?, 'PKR', 1, '2026-01-01')", (account, account))
    for key, value in DEFAULT_SETTINGS.items():
        raw.execute("INSERT INTO app_settings(key,value_json,updated_at) VALUES (?,?,?)", (key, json.dumps(value), '2026-01-01'))
    raw.commit()
    raw.close()
    monkeypatch.setenv('PSX_DATABASE_BACKEND', 'turso')
    monkeypatch.setattr(turso, 'credentials', lambda: (url, ''))
    monkeypatch.setattr(turso, '_READY', False)
    turso.ensure_ready()
    yield tmp_path


def workbook(rows=20, close=100):
    book = openpyxl.Workbook()
    book.active.append(['DATE','SYMBOL','VOLUME','PR-CLOSE','HIGH','LOW','OPEN','CLOSE','AVG'])
    for i in range(rows):
        book.active.append([datetime(2025,1,1)+timedelta(days=i),'ATRL',1000,99,103,98,99,close,100])
    data = io.BytesIO()
    book.save(data)
    return data.getvalue()


def test_remote_commit_rollback_mapping_and_revision(remote):
    from psx_app.database.schema import get_connection
    from psx_app.database.turso import revision
    before = revision()
    with get_connection() as c:
        row = c.execute('SELECT 12 AS n, ? AS label', ('test',)).fetchone()
        assert row[0] == row['n'] == 12 and dict(row)['label'] == 'test'
        c.execute("INSERT INTO audit_events(event_type,details_json,created_at) VALUES ('TEST','{}','2025')")
    assert revision() != before
    before = revision()
    with pytest.raises(ValueError):
        with get_connection() as c:
            c.execute("INSERT INTO audit_events(event_type,details_json,created_at) VALUES ('ROLLBACK','{}','2025')")
            raise ValueError('test rollback')
    with get_connection() as c:
        assert c.execute("SELECT COUNT(*) FROM audit_events WHERE event_type='ROLLBACK'").fetchone()[0] == 0
    assert revision() == before


def test_remote_bulk_insert_and_cache_does_not_change_revision(remote):
    from psx_app.database.schema import get_connection
    from psx_app.database.turso import revision
    before = revision()
    with get_connection() as c:
        c.executemany('INSERT INTO indicator_cache(symbol,trade_date,payload_json,updated_at) VALUES (?,?,?,?)',
                      [('T'+str(i),'2025-01-01','{}','2025') for i in range(2000)])
    with get_connection() as c:
        assert c.execute('SELECT COUNT(*) FROM indicator_cache').fetchone()[0] == 2000
    assert revision() == before


def test_remote_stage_commit_on_different_worker_and_idempotency(remote):
    from psx_app.services.import_orchestrator import ImportOrchestrator
    from psx_app.database.schema import get_connection
    first = ImportOrchestrator(data_root=remote/'worker-a')
    stage = first.stage_uploaded_files([('2025.xlsx', workbook())])
    shutil.rmtree(remote/'worker-a', ignore_errors=True)
    second = ImportOrchestrator(data_root=remote/'worker-b')
    committed = second.commit_staged_batch(stage['batch_uuid'])
    assert committed['new_records'] == 20
    assert second.commit_staged_batch(stage['batch_uuid'])['status'] == 'ALREADY_COMMITTED'
    with get_connection() as c:
        assert c.execute('SELECT COUNT(*) FROM equity_ohlcv').fetchone()[0] == 20
        assert c.execute('SELECT COUNT(*) FROM psx_blob_parts').fetchone()[0] == 0
        assert c.execute('SELECT archive_path FROM source_files').fetchone()[0].startswith('turso:metadata-only/')
    again = first.stage_uploaded_files([('2025.xlsx', workbook())])
    assert again['duplicates_ignored'] == 20
    assert first.commit_staged_batch(again['batch_uuid'])['new_records'] == 0
    revised = first.stage_uploaded_files([('2025.xlsx', workbook(close=101))])
    assert revised['revisions_count'] == 20
    result = first.commit_staged_batch(revised['batch_uuid'])
    assert result['revisions_count'] == 20


def test_remote_blob_cross_worker_parts_and_expiry(remote):
    from psx_app.services.remote_staging import put, get, delete, sweep
    from psx_app.database.schema import get_connection
    data = bytes(range(256)) * 6000
    put('chunk:test:0', data)
    assert get('chunk:test:0') == data
    with get_connection() as c:
        c.execute('UPDATE psx_blob_parts SET updated_at=0 WHERE scope=?', ('chunk:test:0',))
    sweep()
    with pytest.raises(FileNotFoundError):
        get('chunk:test:0')


def test_remote_http_endpoints_and_no_snapshot_fallback(remote, monkeypatch):
    import psx_app.main as main
    from fastapi.testclient import TestClient
    from psx_app.services.backup_service import BackupService
    from psx_app.services.cloud_sync_service import LegacyCloudSyncService
    monkeypatch.setattr(main, 'DATA_ROOT', remote)
    monkeypatch.setattr(LegacyCloudSyncService, '_gh_request', lambda *a, **kw: pytest.fail('GitHub must not be contacted'))
    main._API_CACHE.clear()
    main._READ_FRESHNESS.clear()
    with TestClient(main.app) as client:
        for path in ('/api/health','/api/overview','/api/settings','/api/data-dates','/api/accounts/91404','/api/futures/comparison'):
            response = client.get(path)
            assert response.status_code == 200, (path, response.text[:300])
        status = client.get('/api/settings').json()
        assert status['cloud_sync']['backend'] == 'turso'
        assert status['db_integrity']['check_type'] == 'connectivity'
        assert client.get('/api/cloud-sync/download-snapshot').status_code == 409
        assert client.post('/api/backups/create', json={}).status_code == 409
        assert client.post('/api/admin/date-normalization/plan').status_code == 409
        result = client.post('/api/settings', json={'updates': {'futures_default_days': 20}})
        assert result.status_code == 200 and result.json()['cloud_sync']['saved']
        assert client.post('/api/cloud-sync/reload', json={'confirm':True}).status_code == 200
    with pytest.raises(ValueError, match='NEW Turso'):
        BackupService().restore_backup('anything.zip')
    assert not list(remote.rglob('app.db'))


def test_remote_account_rollups_are_atomic_and_separate(remote, monkeypatch):
    from psx_app.services.import_orchestrator import ImportOrchestrator
    from psx_app.services.account_service import AccountService
    from psx_app.database.schema import get_connection
    header = 'Date,Time,Terminal,Market,Symbol,Transaction Type,Order ID,Execution ID,Account,Status,Quantity,Remaining Quantity,Order Quantity,Trade Price,Trade Value\n'
    data = (header + '16/10/2025,10:00:01,THM00601,REG,OGDC,Buy,O1,E1,91404,FILLED,1000,0,1000,200,200000\n' +
            '16/10/2025,11:00:01,THM00601,REG,OGDC,Sell,O2,E2,91404,FILLED,1000,0,1000,202,202000\n').encode()
    orch = ImportOrchestrator(data_root=remote)
    stage = orch.stage_uploaded_files([('TradeLog.csv', data)])
    assert stage['rows_accepted'] == 2
    original = AccountService.recalculate_account_date_from_executions
    def fail(*a, **kw):
        raise ValueError('synthetic account rollup failure')
    monkeypatch.setattr(AccountService, 'recalculate_account_date_from_executions', fail)
    with pytest.raises(ValueError, match='rollup failure'):
        orch.commit_staged_batch(stage['batch_uuid'])
    with get_connection() as c:
        assert c.execute('SELECT COUNT(*) FROM trade_executions').fetchone()[0] == 0
        assert c.execute('SELECT COUNT(*) FROM account_daily_symbol_summary').fetchone()[0] == 0
        assert c.execute('SELECT status FROM import_batches').fetchone()[0] == 'FAILED'
    monkeypatch.setattr(AccountService, 'recalculate_account_date_from_executions', original)
    assert orch.commit_staged_batch(stage['batch_uuid'])['new_records'] == 2
    with get_connection() as c:
        row = c.execute('SELECT account_id,net_pnl FROM account_daily_symbol_summary').fetchone()
        assert row['account_id'] == '91404'
        assert row['net_pnl'] == pytest.approx(2000 - 202000 * 0.000325 * 1.13)
        assert c.execute("SELECT COUNT(*) FROM account_daily_symbol_summary WHERE account_id='91269'").fetchone()[0] == 0


def test_remote_chunked_upload_and_commit(remote, monkeypatch):
    import psx_app.main as main
    from fastapi.testclient import TestClient
    from psx_app.services.import_orchestrator import ImportOrchestrator
    monkeypatch.setattr(main, 'DATA_ROOT', remote/'worker')
    main._API_CACHE.clear(); main._READ_FRESHNESS.clear()
    data = workbook(2)
    upload_id = 'remote-chunk-test'
    pieces = [data[:len(data)//2], data[len(data)//2:]]
    with TestClient(main.app) as client:
        for i, part in enumerate(pieces):
            response = client.post(f'/api/imports/upload-chunk?upload_id={upload_id}&name=2025.xlsx&idx={i}&total=2', content=part)
            assert response.status_code == 200 and response.json()['storage'] == 'turso'
        shutil.rmtree(remote/'worker', ignore_errors=True)
        response = client.post('/api/imports/stage-chunked', json={'uploads':[{'upload_id':upload_id,'name':'2025.xlsx','total_chunks':2}]})
        assert response.status_code == 200, response.text
        batch = response.json()['batch_uuid']
        history = client.get('/api/imports/history').json()
        assert any(b['batch_uuid']==batch and b['staged_resumable'] for b in history['batches'])
        response = client.post('/api/imports/commit', json={'batch_uuid':batch})
        assert response.status_code == 200, response.text
        assert response.json()['cloud_sync']['saved']


def test_remote_freshness_invalidates_cached_dates(remote):
    import psx_app.main as main
    from fastapi.testclient import TestClient
    from psx_app.database.schema import get_connection
    main._API_CACHE.clear(); main._READ_FRESHNESS.clear()
    with TestClient(main.app) as client:
        assert client.get('/api/data-dates').json()['cash'] is None
        with get_connection() as c:
            c.execute("INSERT INTO equity_ohlcv(trade_date,symbol,close) VALUES ('2025-10-22','ATRL',100)")
        result = client.get('/api/system/freshness?force=true')
        assert result.status_code == 200 and result.json()['changed']
        assert client.get('/api/data-dates').json()['cash'] == '2025-10-22'


def test_remote_v139_reference_forecast_learning_tables_and_revision(remote):
    from psx_app.database.schema import get_connection
    from psx_app.database.turso import revision
    from psx_app.services.sector_reference import SectorReference
    from psx_app.services.forecast_ledger import ForecastLedger
    from psx_app.services.learning_research import train_symbol
    import math
    with get_connection() as c:
        c.executemany('INSERT INTO equity_ohlcv(symbol,trade_date,open,high,low,close,pr_close,volume) VALUES (?,?,?,?,?,?,?,?)',[
            ('ATRL',(datetime(2024,1,1)+timedelta(days=i)).date().isoformat(),100+i*.04,102+i*.04,99+i*.04,100+i*.04,99.96+i*.04,10000) for i in range(340)])
    before=revision()
    ledger=ForecastLedger();ledger.record('ATRL');ledger.record('ATRL')
    assert len(ledger.list()['items'])==2
    assert ledger.reconcile()['evaluated']==2
    model=train_symbol('ATRL');assert model['status']=='RESEARCH_ONLY'
    # Forecast/research metadata must not invalidate the canonical price revision on each view.
    assert revision()==before
    raw=io.BytesIO();wb=openpyxl.Workbook();ws=wb.active;ws.title='COMP_LIST';ws.append(['SYMBOL','COMPANY NAME','SECTOR']);ws.append(['ATRL','Attock Refinery','REFINERY']);wb.save(raw)
    service=SectorReference();p=service.preview(raw.getvalue());assert revision()==before
    service.commit(p['token']);assert revision()!=before
    assert service.directory()['ATRL']['sector']=='REFINERY'
