"""Regression tests for live-audited scanner accounting and normal sector uploads."""
import io, json, math, zipfile
from datetime import date, timedelta
import openpyxl
import pytest
from psx_app.database.schema import init_db, get_connection
from psx_app.services.intelligence_service import IntelligenceService
from psx_app.services.import_orchestrator import ImportOrchestrator
from psx_app.services.data_coverage import DataCoverage
from psx_app.parsers.detector import detect_file_type

@pytest.fixture
def db(tmp_path):
    p=tmp_path/'database/app.db';p.parent.mkdir();init_db(p)
    with get_connection(p) as c:
        for i in range(240):
            d=(date(2025,1,1)+timedelta(days=i)).isoformat();px=160-i*.2+math.sin(i/4)
            c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,volume,pr_close,open,high,low,close,avg_price) VALUES (?,?,?,?,?,?,?,?,?)',(d,'TRG',10000,px+.1,px+.1,px+1,px-1,px,px))
        for sym in ['SHORTNEW','CENIR']:
            c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,volume,pr_close,open,high,low,close,avg_price) VALUES (?,?,?,?,?,?,?,?,?)',(d,sym,10000,100,100,101,99,100,100))
        c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,volume,pr_close,open,high,low,close,avg_price) VALUES (?,?,?,?,?,?,?,?,?)',('2025-01-01','OLD',0,100,100,101,99,100,100))
        c.commit()
    return p

def workbook(symbol='TRG',company='TRG Pakistan',sector='TECHNOLOGY & COMMUNICATION'):
    w=openpyxl.Workbook();s=w.active;s.title='COMP_LIST';s.append(['SYMBOL','COMPANY NAME','SECTOR']);s.append([symbol,company,sector]);b=io.BytesIO();w.save(b);return b.getvalue()

def test_direction_filtered_symbol_is_examined_and_explained(db):
    r=IntelligenceService(db).generate_trading_ideas('CORE36','LONG','trg')
    assert r['candidates_scanned']==1 and r['scan_counts']['analyzed']==1
    assert r['scan_counts']['direction_eligible']==0
    assert r['diagnostics'][0]['bars_count']==240
    assert 'DIRECTION_FILTER' in [x['code'] for x in r['diagnostics'][0]['reasons']]
    assert r['setups_count']==0 and r['rejected'][0]['symbol']=='TRG'

def test_all_scanned_symbols_accounted_no_silent_early_drops(db):
    r=IntelligenceService(db).generate_trading_ideas('ALL_MARKET')
    assert r['candidates_scanned']==4
    assert len(r['diagnostics'])==4
    assert r['scan_counts']['structurally_qualified']+len(r['rejected'])==4
    old=next(x for x in r['diagnostics'] if x['symbol']=='OLD')
    assert {'STALE_DATA','ZERO_VOLUME','INSUFFICIENT_HISTORY'} <= {x['code'] for x in old['reasons']}

def test_scope_and_query_intersection_and_missing(db):
    r=IntelligenceService(db).generate_trading_ideas('FUTURES','ALL','TRG')
    assert r['candidates_scanned']==0 and r['outside_scope'][0]['symbol']=='TRG'
    r=IntelligenceService(db).generate_trading_ideas('ALL_MARKET','ALL','NOTAREALTICKER')
    assert r['scan_counts']['query_matches']==0 and r['diagnostics']==[]
    r=IntelligenceService(db).generate_trading_ideas('ALL_MARKET','ALL','CENIR')
    assert [x['symbol'] for x in r['diagnostics']]==['CENIR']  # Exact symbol, not broad text.

def test_short_history_not_zero_indicator_commentary(db):
    r=IntelligenceService(db).run_automated_technical_analyst('SHORTNEW')
    assert r['status']=='INSUFFICIENT_DATA' and r['latest']['bars_count']==1
    assert 'step_by_step_analysis' not in r and 'not zero' in r['message']

def test_coverage_reports_actual_engine_and_missing_references(db):
    with get_connection(db) as c:
        c.execute("INSERT INTO company_reference VALUES ('COMP_LIST','NOHISTORY','No History','CUSTOM')");c.commit()
    r=DataCoverage(db).report('trg');assert r['count']==1
    a=r['items'][0];assert a['cash_rows']==a['engine_bars']==240
    assert r['summary']['cash_missing_in_engine']==[]
    missing=DataCoverage(db).report('NOHISTORY')['items'][0]
    assert missing['cash_rows']==0 and missing['freshness']=='NO_CASH_DATA'
    assert 'cannot replace' in missing['notes'][0]

def test_standard_upload_reference_detect_stage_commit_reimport(db,tmp_path):
    raw=workbook();p=tmp_path/'arbitrary-name.xlsx';p.write_bytes(raw)
    assert detect_file_type(p)['file_type']=='SECTOR_REFERENCE'
    service=ImportOrchestrator(db_path=db,data_root=tmp_path/'data')
    with get_connection(db) as c:before=c.execute('SELECT COUNT(*),SUM(close) FROM equity_ohlcv').fetchone()
    m=service.stage_uploaded_files([('SECTOR_WISE.xlsx',raw)])
    assert m['rows_accepted']==1 and m['files'][0]['module']=='REFERENCE'
    result=service.commit_staged_batch(m['batch_uuid']);assert result['new_records']==1
    assert service.commit_staged_batch(m['batch_uuid'])['status']=='ALREADY_COMMITTED'
    again=service.stage_uploaded_files([('SECTOR_WISE.xlsx',raw)])
    assert again['duplicates_ignored']==1
    assert service.commit_staged_batch(again['batch_uuid'])['duplicates_ignored']==1
    with get_connection(db) as c:
        assert tuple(before)==tuple(c.execute('SELECT COUNT(*),SUM(close) FROM equity_ohlcv').fetchone())
        assert c.execute('SELECT company FROM company_reference WHERE symbol=?',('TRG',)).fetchone()[0]=='TRG Pakistan'

def test_zip_reference_revisions_and_no_deletions(db,tmp_path):
    service=ImportOrchestrator(db_path=db,data_root=tmp_path/'data')
    m=service.stage_uploaded_files([('sector.xlsx',workbook())]);service.commit_staged_batch(m['batch_uuid'])
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:z.writestr('sector.xlsx',workbook(company='Changed Name'))
    m=service.stage_uploaded_files([('sector.zip',b.getvalue())]);assert m['revisions_count']==1
    r=service.commit_staged_batch(m['batch_uuid']);assert r['revisions_count']==1
    with get_connection(db) as c:
        assert c.execute("SELECT company FROM company_reference WHERE symbol='TRG'").fetchone()[0]=='Changed Name'
        assert c.execute("SELECT COUNT(*) FROM source_revisions WHERE table_name='company_reference'").fetchone()[0]==1
    m=service.stage_uploaded_files([('small.xlsx',workbook(symbol='NEWREF'))]);service.commit_staged_batch(m['batch_uuid'])
    with get_connection(db) as c:
        assert c.execute("SELECT COUNT(*) FROM company_reference WHERE symbol IN ('TRG','NEWREF')").fetchone()[0]==2
        assert c.execute("SELECT COUNT(*) FROM company_reference WHERE symbol='MLCF'").fetchone()[0]==1

def test_invalid_reference_no_accepted_rows(db,tmp_path):
    service=ImportOrchestrator(db_path=db,data_root=tmp_path/'data')
    m=service.stage_uploaded_files([('bad.xlsx',workbook(symbol='!bad'))]);assert m['rows_accepted']==0
    with pytest.raises(ValueError):service.commit_staged_batch(m['batch_uuid'])


def test_symbol_targeted_scan_does_not_compute_unrelated_universe(db,monkeypatch):
    svc=IntelligenceService(db);original=svc.tech_service.get_universe_summary;requested=[]
    def capture(**kwargs):
        requested.extend(kwargs.get('symbols',[]));return original(**kwargs)
    monkeypatch.setattr(svc.tech_service,'get_universe_summary',capture)
    svc.generate_trading_ideas('CORE36','LONG','TRG')
    assert requested==['TRG']


def test_cached_futures_observation_refreshes_after_futures_only_change(db):
    from psx_app.services.technical_service import TechnicalService
    svc=TechnicalService(db);a=svc.get_universe_summary(scope='all',symbols=['TRG'])['items'][0]
    assert not a['is_futures_eligible']
    with get_connection(db) as c:
        c.execute('INSERT INTO futures_ohlcv(trade_date,contract_symbol,base_symbol,contract_month,close,open,high,low,pr_close,volume) VALUES (?,?,?,?,?,?,?,?,?,?)',(a['latest_date'],'TRG-AUG','TRG','AUG',100,100,101,99,100,500));c.commit()
    b=svc.get_universe_summary(scope='all',symbols=['TRG'])['items'][0]
    assert b['is_futures_eligible'] and b['signal']['combined_signal']=='SHORT SELL'
    with get_connection(db) as c:c.execute('DELETE FROM futures_ohlcv');c.commit()
    assert not svc.get_universe_summary(scope='all',symbols=['TRG'])['items'][0]['is_futures_eligible']


def test_build_detection_uses_html_build_metadata_not_old_literal():
    from pathlib import Path
    import re
    root=Path(__file__).resolve().parents[1]
    html=(root/'psx_app/static/index.html').read_text()
    js=(root/'psx_app/static/app.js').read_text()
    main=(root/'psx_app/main.py').read_text()
    build=re.search(r'name="psx-build-version" content="([^"]+)"',html)[1]
    assert build=='1.3.20' and f'version="{build}"' in main
    assert "document.querySelector('meta[name=\"psx-build-version\"]')?.content" in js
    assert "result.version !== '1.3.9'" not in js


def test_partially_initialized_analyst_indicators_are_unavailable_not_zero(db):
    with get_connection(db) as c:
        c.execute("DELETE FROM equity_ohlcv WHERE symbol='TRG' AND trade_date>(SELECT trade_date FROM equity_ohlcv WHERE symbol='TRG' ORDER BY trade_date LIMIT 1 OFFSET 25)");c.commit()
    r=IntelligenceService(db).run_automated_technical_analyst('TRG')
    assert r['latest']['bars_count']==26 and r.get('status')!='INSUFFICIENT_DATA'
    assert r['weekly_summary']['weekly_sma10'] is None
    detail=' '.join(x['detail'] for x in r['step_by_step_analysis'])
    assert 'EMA(50)=N/A' in detail and 'SMA(10)=N/A' in detail
    assert 'EMA(50)=0.00' not in detail
