"""Portable regressions: real XLSX dates, OHLCV revisions, safe cleanup and CAS."""
from datetime import datetime
from io import BytesIO
import json
import openpyxl
from psx_app.database.schema import init_db, get_connection
from psx_app.services.import_orchestrator import ImportOrchestrator
from psx_app.services.futures_service import FuturesService
from psx_app.services.cloud_sync_service import CloudSyncService
from test_release_safety import FakeGit


def book(date=datetime(2026,10,12), volume=1000, close=101):
    wb=openpyxl.Workbook();wb.active.title='2026'
    wb.active.append(['DATE','SYMBOL','VOLUME','PR-CLOSE','HIGH','LOW','OPEN','CLOSE','AVG'])
    wb.active.append([date,'OGDC-OCT',volume,100,103,99,100,close,101])
    out=BytesIO();wb.save(out);return out.getvalue()


def orch_at(tmp_path):
    db=tmp_path/'database'/'app.db';db.parent.mkdir();init_db(db)
    return db,ImportOrchestrator(db,tmp_path)


def apply(orch,data,allow=True):
    stage=orch.stage_uploaded_files([('2026F.xlsx',data)])
    return orch.commit_staged_batch(stage['batch_uuid'],allow_revisions=allow)


def test_volume_revision_without_close_change_is_not_duplicate(tmp_path):
    db,orch=orch_at(tmp_path);apply(orch,book())
    res=apply(orch,book(volume=2500));assert res['revisions_count']==1
    with get_connection(db) as c: assert c.execute('SELECT volume FROM futures_ohlcv').fetchone()[0]==2500
    res2=apply(orch,book(volume=3500),False);assert res2['revisions_count']==0
    with get_connection(db) as c: assert c.execute('SELECT volume FROM futures_ohlcv').fetchone()[0]==2500


def test_typed_source_repairs_only_identical_outside_date_rows(tmp_path):
    db,orch=orch_at(tmp_path);apply(orch,book())
    with get_connection(db) as c:
        for sym,vol in [('OGDC-OCT',1000),('OTHER-OCT',777)]:
            c.execute('''INSERT INTO futures_ohlcv(trade_date,contract_symbol,base_symbol,contract_month,volume,pr_close,high,low,open,close,avg_price)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',('2026-12-10',sym,sym.split('-')[0],'OCT',vol,100,103,99,100,101,101))
        c.commit()
    res=apply(orch,book());assert res['verified_date_repairs']==1
    with get_connection(db) as c:
        assert c.execute("SELECT COUNT(*) FROM futures_ohlcv WHERE trade_date='2026-12-10'").fetchone()[0]==1
        raw=json.loads(c.execute("SELECT raw_payload FROM import_issues WHERE issue_type='SOURCE_VERIFIED_DATE_SWAP'").fetchone()[0])
        assert raw['original_row']['trade_date']=='2026-12-10';assert raw['verified_date']=='2026-10-12'
    assert apply(orch,book())['verified_date_repairs']==0


def test_text_dates_do_not_certify_automatic_cleanup(tmp_path):
    db,orch=orch_at(tmp_path);apply(orch,book(datetime(2026,12,10)))
    result=apply(orch,book('10/12/2026'))
    assert result['verified_date_repairs']==0
    with get_connection(db) as c: assert c.execute('SELECT COUNT(*) FROM futures_ohlcv').fetchone()[0]==2


def test_forward_contract_month_does_not_change_trade_date(tmp_path):
    db,orch=orch_at(tmp_path);apply(orch,book(datetime(2026,10,21)))
    with get_connection(db) as c:
        c.execute("UPDATE futures_ohlcv SET contract_symbol='OGDC-NOV',contract_month='NOV'");c.commit()
    meta=FuturesService(db).get_metadata();assert meta['latest_date']=='2026-10-21';assert meta['contracts']==['NOV']


def test_reused_verified_baseline_cas_rejects_concurrent_remote_change(tmp_path,monkeypatch):
    db,orch=orch_at(tmp_path);remote=FakeGit(db);svc=CloudSyncService(db)
    svc.repo='owner/repo';svc.token='test';monkeypatch.setattr(svc,'_gh_request',remote.request)
    svc._save_base(initialized=True,blob=remote.blob,repo=svc.repo,branch=svc.branch)
    checked=svc.assert_current_base();remote.head='someone-else-newer-commit'
    svc.mark_pending();out=svc.push_db_after_update('test',checked_base=checked)
    assert not out['pushed'];assert svc.base_state()['pending'];assert remote.head=='someone-else-newer-commit'


def test_normal_save_uses_seven_github_requests(tmp_path,monkeypatch):
    db,orch=orch_at(tmp_path);remote=FakeGit(db);svc=CloudSyncService(db)
    svc.repo='owner/repo';svc.token='test';calls=[]
    def request(method,endpoint,payload=None):
        calls.append((method,endpoint,payload));return remote.request(method,endpoint,payload)
    monkeypatch.setattr(svc,'_gh_request',request)
    svc._save_base(initialized=True,blob=remote.blob,repo=svc.repo,branch=svc.branch)
    checked=svc.assert_current_base();svc.mark_pending();assert svc.push_db_after_update('test',checked_base=checked)['pushed']
    assert len(calls)==7;assert calls[-1][2]['force'] is False


def test_staging_futures_does_not_scan_unrelated_cash_history(tmp_path,monkeypatch):
    db,orch=orch_at(tmp_path)
    import psx_app.services.import_orchestrator as module
    original=module.get_connection;queries=[]
    def traced(*args,**kwargs):
        connection=original(*args,**kwargs);connection.set_trace_callback(queries.append);return connection
    monkeypatch.setattr(module,'get_connection',traced)
    orch.stage_uploaded_files([('2026F.xlsx',book())])
    assert not any('FROM equity_ohlcv' in q or 'FROM trade_executions' in q or 'FROM top5_volume_records' in q for q in queries)


def test_staging_flags_volume_only_revisions(tmp_path):
    db,orch=orch_at(tmp_path);apply(orch,book())
    stage=orch.stage_uploaded_files([('2026F.xlsx',book(volume=2000))])
    assert stage['revisions_count']==1
