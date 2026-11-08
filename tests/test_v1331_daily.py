"""Synthetic daily-market data: trading sessions, reconciliation and limits."""
from datetime import date
import pytest
from psx_app.database.schema import init_db,get_connection
from psx_app.services.daily_summary import DailySummary,official_limit_flags,movement
from test_v1314_postgres import remote

@pytest.fixture
def daily_db(tmp_path):
    db=tmp_path/'daily.db';init_db(db);populate(db);return db

def populate(db=None):
    with get_connection(db) as c:
        c.executemany('INSERT INTO company_reference(list_name,symbol,company,sector) VALUES (?,?,?,?)',[
            ('COMP_LIST','UP','Up company','CEMENT'),('KSE100','UP','Duplicate reference','OTHER'),('COMP_LIST','DOWN','Down company','BANKS'),('COMP_LIST','EVEN','Even company','CEMENT')])
        c.executemany('INSERT INTO equity_ohlcv(trade_date,symbol,open,high,low,close,pr_close,avg_price,volume) VALUES (?,?,?,?,?,?,?,?,?)',[
            ('2026-10-30','UP',10,11,9,10,9,10,100),('2026-10-30','DOWN',20,21,19,20,21,20,200),('2026-10-30','EVEN',5,5,5,5,5,5,50),
            ('2026-11-02','UP',10,12,10,11,10,11,300),('2026-11-02','DOWN',20,20,17,18,20,19,100),('2026-11-02','EVEN',5,5,5,5,5,5,50),('2026-11-02','NEW',10,10,10,10,None,10,70),('2026-11-02','ZERO',1,1,1,1,1,1,0)])
        c.executemany('INSERT INTO index_ohlcv(trade_date,close) VALUES (?,?)',[('2026-10-30',1000),('2026-11-02',1050)])

def check(r):
    assert r['date']=='2026-11-02' and r['previous_cash_date']=='2026-10-30'
    assert r['index']=={'trade_date':'2026-11-02','close':1050.0,'change':50.0,'pct':5.0,'baseline_date':'2026-10-30'}
    assert r['volume']=={'current':520,'previous':350,'change':170.0,'pct':pytest.approx(170/350*100)}
    assert r['breadth']=={'total':4,'advancing':1,'declining':1,'unchanged':1,'unclassified':1}
    rows={x['symbol']:x for x in r['rows']};assert set(rows)=={'UP','DOWN','EVEN','NEW'}
    assert rows['UP']['sector']=='CEMENT' and rows['UP']['company']=='Up company'
    assert rows['UP']['volume_change']==200 and rows['UP']['volume_change_pct']==200
    assert rows['DOWN']['volume_change_pct']==-50 and rows['DOWN']['change']==-2
    assert rows['NEW']['volume_change_pct'] is None and rows['NEW']['sector']=='Unmapped'
    assert all(x['status']=='UNAVAILABLE' for x in rows.values())
    assert all(v=={'count':None,'checked':0,'total':4} for v in r['caps'].values())

def test_daily_report_reconciles_previous_session_and_unavailable_data(daily_db):
    check(DailySummary(daily_db).report('2026-11-02'))
    r=DailySummary(daily_db).report('2026-10-31');assert r['status']=='NO_DATA' and r['date']=='2026-10-31'
    assert DailySummary(daily_db).report()['date']=='2026-11-02'
    with pytest.raises(ValueError):DailySummary(daily_db).report('2026-02-30')

def test_verified_limit_math_separates_touch_and_close():
    f=official_limit_flags({'high':11,'low':9.1,'close':10},11,9)
    assert f=={'upper_touch':True,'upper_close':False,'lower_touch':False,'lower_close':False,'status':'NORMAL'}
    f=official_limit_flags({'high':11,'low':9,'close':9},11,9)
    assert f['upper_touch'] and not f['upper_close'] and f['lower_touch'] and f['lower_close'] and f['status']=='LOWER'
    assert official_limit_flags({'high':None,'low':9,'close':11},11,9)['upper_touch'] is None
    assert official_limit_flags({'high':11,'low':9,'close':10},None,None)['status']=='UNAVAILABLE'
    assert official_limit_flags({'high':11,'low':9,'close':10},9,11)['status']=='UNAVAILABLE'
    assert movement(100,0,positive_previous=False)==(100,None)
    assert movement(float('nan'),100)==(None,None)

def test_endpoint_validation_and_no_data(daily_db,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import psx_app.upgrade_routes as route
    monkeypatch.setattr(route,'DB_PATH',daily_db); app=FastAPI();app.include_router(route.router)
    with TestClient(app) as c:
        assert c.get('/api/v139/market/daily-summary?date=2026-11-02').json()['breadth']['total']==4
        assert c.get('/api/v139/market/daily-summary?date=2026-02-30').status_code==422
        assert c.get('/api/v139/market/daily-summary?date=2026-11-01').json()['status']=='NO_DATA'

def test_postgres_daily_parity_and_cache_invalidation(remote):
    from psx_app.database.turso import revision
    populate();before=revision();check(DailySummary().report('2026-11-02'));assert DailySummary().report('2026-11-02')['breadth']['total']==4 and revision()==before
    with get_connection() as c:c.execute("UPDATE equity_ohlcv SET volume=400 WHERE trade_date='2026-11-02' AND symbol='UP'")
    assert DailySummary().report('2026-11-02')['volume']['current']==620


def test_index_does_not_skip_missing_previous_cash_session(daily_db):
    with get_connection(daily_db) as c:
        c.execute("DELETE FROM index_ohlcv WHERE trade_date='2026-10-30'")
        c.execute("INSERT INTO index_ohlcv(trade_date,close) VALUES ('2026-10-29',900)")
    r=DailySummary(daily_db).report('2026-11-02')
    assert r['index']['close']==1050 and r['index']['baseline_date'] is None
    assert r['index']['change'] is None and r['index']['pct'] is None
