import json,math
from datetime import date,timedelta
from pathlib import Path
import pytest
from psx_app.database.schema import init_db,get_connection
from psx_app.services.market_explorer import MarketExplorer
from psx_app.services.forecast_ledger import ForecastLedger,evaluate,execution_contract
from psx_app.services.sector_reference import SectorReference
from psx_app.services.learning_research import research_model,train_symbol

@pytest.fixture
def db139(tmp_path):
    p=tmp_path/'database/app.db';p.parent.mkdir();init_db(p)
    with get_connection(p) as c:
        for i in range(420):
            d=(date(2024,1,1)+timedelta(days=i)).isoformat();px=100+i*.1+math.sin(i/5)*3
            for sym,mult in [('ATRL',1),('PRL',.5),('MLCF',.8)]:
                c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,volume,pr_close,open,high,low,close,avg_price) VALUES (?,?,?,?,?,?,?,?,?)',(d,sym,1000+i,px*mult-.1,px*mult,px*mult+1,px*mult-1,px*mult,px*mult+.1))
            c.execute('INSERT INTO index_ohlcv(trade_date,pr_close,open,high,low,close) VALUES (?,?,?,?,?,?)',(d,1000+i-1,1000+i,1002+i,999+i,1000+i))
        c.commit()
    return p

def test_market_extrema_and_exact_baselines(db139):
    s=MarketExplorer(db139);r=s.symbol('ATRL',5)
    assert len(r['rows'])==5 and r['rows'][0]['trade_date']>r['rows'][-1]['trade_date']
    assert r['baseline_date']<r['first']
    assert all(x['volume'] is None for x in r['index_rows'])
    assert len(r['extrema'])==7
    v=s.volume(top_n=1);assert abs(sum(x['pct'] for x in v['parts'])-100)<1e-9
    assert v['parts'][-1]['symbol']=='Others'

def payload139(horizon=1):
    return {'as_of':'2026-01-01','reference_close':100,'score':5,'horizon':horizon,'contract':{'status':'CONDITIONAL','side':'LONG','entry_low':99.75,'entry_high':100.25,'stop':98,'target_1':105}}
def bar139(d='2026-01-02',**kw):return dict(trade_date=d,open=100,high=104,low=99,close=102,volume=1000,**kw)
def test_forecast_ambiguity_gaps_and_expiry():
    b=bar139();b.update(high=106,low=97)
    assert evaluate(payload139(),[b],['2026-01-02'])['status']=='AMBIGUOUS'
    b.update(open=110)
    assert evaluate(payload139(),[b],['2026-01-02'])['status']=='NOT_TRIGGERED'
    r=evaluate(payload139(),[bar139()],['2026-01-02']);assert r['status']=='HORIZON_CLOSED' and r['directional_result']=='CORRECT'
    assert evaluate(payload139(),[],['2026-01-02'])['status']=='INSUFFICIENT_DATA'
    assert evaluate(payload139(),[],[])['status']=='PENDING'

def test_short_and_swing_horizon():
    p=payload139(10);p['score']=-6;p['contract'].update(side='SHORT',stop=102,target_1=95)
    b=bar139();b.update(high=101,low=96,close=98)
    r=evaluate(p,[b],['2026-01-02']);assert r['status']=='OPEN' and r['directional_result']=='CORRECT'
    b.update(low=94);assert evaluate(p,[b],['2026-01-02'])['status']=='TARGET_REACHED'

def test_record_idempotence_and_immutable_snapshot(db139):
    s=ForecastLedger(db139);s.record('ATRL');s.record('ATRL');r=s.list()['items'];assert len(r)==2
    old=[x['recorded_at'] for x in r]
    s.record('ATRL');assert old==[x['recorded_at'] for x in s.list()['items']]
    assert s.reconcile()['evaluated']==2
    with get_connection(db139) as c:assert c.execute('SELECT COUNT(*) FROM forecast_observations').fetchone()[0]==2

def test_sector_bundled_counts_and_actual_ticker(db139):
    s=SectorReference(db139);lists=s.lists()
    assert len(lists['COMP_LIST'])==671 and len(lists['KSE100'])==101 and len(lists['KSE30'])==30
    assert s.directory()['MLCF']['sector']=='CEMENT' and 'MLF' not in s.directory()

def test_reference_preview_commit_no_price_mutation(db139):
    import io,openpyxl
    w=openpyxl.Workbook();ws=w.active;ws.title='COMP_LIST';ws.append(['SYMBOL','COMPANY NAME','SECTOR']);ws.append(['ATRL','Refinery','REFINERY']);b=io.BytesIO();w.save(b)
    s=SectorReference(db139);r=s.preview(b.getvalue());assert r['counts']['COMP_LIST']==1
    assert len(s.directory())==671
    s.commit(r['token']);assert list(s.directory())==['ATRL']
    with get_connection(db139) as c:assert c.execute('SELECT COUNT(*) FROM equity_ohlcv').fetchone()[0]==1260

def test_learning_chronological_and_reusable(db139):
    r=train_symbol('ATRL',db139);assert r['status']=='RESEARCH_ONLY'
    assert r['training_end']<r['test_start'] and r['validation_end']<r['test_start']
    assert r['run_id']==train_symbol('ATRL',db139)['run_id']
    assert 0<=r['test']['brier']<=1

def test_learning_insufficient():assert research_model([])['status']=='INSUFFICIENT_DATA'
