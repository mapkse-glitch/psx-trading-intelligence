"""Regression tests for source-key duplicates and stale server/browser copies."""
from datetime import datetime
from io import BytesIO
import sqlite3
import openpyxl
import pytest
from fastapi.testclient import TestClient
from psx_app.database.schema import init_db,get_connection
from psx_app.services.cloud_sync_service import CloudSyncService
from psx_app.services.freshness_service import check_cloud_freshness
from psx_app.services.import_orchestrator import ImportOrchestrator
from test_release_safety import FakeGit


def setup_clouds(tmp_path,monkeypatch):
    seed=tmp_path/'seed/database/app.db';seed.parent.mkdir(parents=True);init_db(seed);remote=FakeGit(seed)
    services=[]
    for name in ['a','b']:
        svc=CloudSyncService(tmp_path/name/'database/app.db');svc.repo='owner/repo';svc.token='test'
        monkeypatch.setattr(svc,'_gh_request',remote.request);assert svc.pull_latest_db_on_startup()['pulled'];services.append(svc)
    return remote,services


def test_clean_warm_worker_refreshes_after_another_worker_saved(tmp_path,monkeypatch):
    remote,(a,b)=setup_clouds(tmp_path,monkeypatch)
    with sqlite3.connect(a.db_path) as c:c.execute('CREATE TABLE test_marker(value TEXT)');c.execute("INSERT INTO test_marker VALUES ('newer cloud')")
    a.mark_pending();assert a.push_db_after_update('new update')['pushed']
    result=check_cloud_freshness(b.db_path,b);assert result['status']=='CURRENT';assert result['changed']
    with sqlite3.connect(b.db_path) as c:assert c.execute('SELECT value FROM test_marker').fetchone()[0]=='newer cloud'
    assert list((b.db_path.parent.parent/'backups').glob('*pre_cloud_pull*.zip'))


def test_pending_worker_never_overwrites_local_changes_on_refresh(tmp_path,monkeypatch):
    remote,(a,b)=setup_clouds(tmp_path,monkeypatch)
    with sqlite3.connect(b.db_path) as c:c.execute('CREATE TABLE pending_marker(value TEXT)');c.execute("INSERT INTO pending_marker VALUES ('keep me')")
    b.mark_pending()
    monkeypatch.setattr(b,'_gh_request',lambda *args,**kwargs:pytest.fail('Pending refresh must not fetch/overwrite data'))
    result=check_cloud_freshness(b.db_path,b);assert result['status']=='PENDING';assert not result['changed']
    with sqlite3.connect(b.db_path) as c:assert c.execute('SELECT value FROM pending_marker').fetchone()[0]=='keep me'


def test_unchanged_snapshot_not_downloaded_again(tmp_path,monkeypatch):
    remote,(a,b)=setup_clouds(tmp_path,monkeypatch);calls=[]
    def request(method,endpoint,payload=None):calls.append(endpoint);return remote.request(method,endpoint,payload)
    monkeypatch.setattr(b,'_gh_request',request)
    result=check_cloud_freshness(b.db_path,b);assert result['status']=='CURRENT';assert not result['changed'];assert len(calls)==3;assert not any('/git/blobs/' in e for e in calls)


def test_failed_verification_is_not_reported_as_current(tmp_path,monkeypatch):
    remote,(a,b)=setup_clouds(tmp_path,monkeypatch)
    def failure(*args,**kwargs):raise RuntimeError('network unavailable')
    monkeypatch.setattr(b,'_gh_request',failure)
    before=b.db_path.read_bytes();result=check_cloud_freshness(b.db_path,b)
    assert result['status']=='UNVERIFIED';assert not result['changed'];assert b.db_path.read_bytes()==before


def test_source_cleans_swapped_duplicate_inside_valid_overall_range(tmp_path):
    db=tmp_path/'database/app.db';db.parent.mkdir();init_db(db);orch=ImportOrchestrator(db,tmp_path)
    wb=openpyxl.Workbook();wb.active.title='2026';wb.active.append(['DATE','SYMBOL','VOLUME','PR-CLOSE','HIGH','LOW','OPEN','CLOSE','AVG'])
    for d in [datetime(2026,9,1),datetime(2026,10,9),datetime(2026,10,21)]:wb.active.append([d,'OGDC-OCT',1000,100,103,99,100,101,101])
    buffer=BytesIO();wb.save(buffer);payload=[('2026F.xlsx',buffer.getvalue())]
    stage=orch.stage_uploaded_files(payload);orch.commit_staged_batch(stage['batch_uuid'])
    with get_connection(db) as c:
        c.execute("INSERT INTO futures_ohlcv(trade_date,contract_symbol,base_symbol,contract_month,volume,pr_close,high,low,open,close,avg_price) VALUES ('2026-09-10','OGDC-OCT','OGDC','OCT',1000,100,103,99,100,101,101)");c.commit()
    stage=orch.stage_uploaded_files(payload);result=orch.commit_staged_batch(stage['batch_uuid']);assert result['verified_date_repairs']==1
    with get_connection(db) as c:
        assert c.execute('SELECT COUNT(*) FROM futures_ohlcv').fetchone()[0]==3
        assert c.execute("SELECT COUNT(*) FROM import_issues WHERE issue_type='SOURCE_VERIFIED_DATE_SWAP'").fetchone()[0]==1
    stage=orch.stage_uploaded_files(payload);assert orch.commit_staged_batch(stage['batch_uuid'])['verified_date_repairs']==0


def test_shell_and_assets_revalidate_and_download_page_removed():
    from psx_app.main import app
    with TestClient(app) as client:
        for path in ['/','/app.js','/styles.css']:
            response=client.get(path);assert response.status_code==200;assert 'no-store' in response.headers['cache-control']
        html=client.get('/').text;assert 'v=1.3.8' in html;assert 'data-view="exports"' not in html;assert 'data-view="reconciliation"' in html;assert 'data-view="settings"' in html
        fresh=client.get('/api/system/freshness?force=true');assert fresh.status_code==200;assert fresh.json()['status']=='LOCAL'


def test_data_read_verifies_its_own_worker_and_clears_cached_analytics(monkeypatch):
    import psx_app.main as main
    calls=[]
    def newer_snapshot(db_path):
        calls.append(db_path)
        return {'status':'CURRENT','changed':True,'snapshot_id':'new-remote-blob'}
    with TestClient(main.app) as client:
        main._READ_FRESHNESS.clear()
        main._API_CACHE['data-dates']={'cash':'2026-12-10'}
        monkeypatch.setattr(main,'check_cloud_freshness',newer_snapshot)
        monkeypatch.setattr(main.CloudSyncService,'base_state',lambda self: {'pending':False})
        response=client.get('/api/data-dates')
        assert response.status_code==200
        assert response.headers['X-PSX-Freshness']=='CURRENT'
        assert response.headers['Cache-Control']=='no-store'
        assert response.json().get('cash')!='2026-12-10'
        assert len(calls)==1
        client.get('/api/data-dates')
        assert len(calls)==1  # Same worker uses the shared metadata TTL.
        main._READ_FRESHNESS.clear()
