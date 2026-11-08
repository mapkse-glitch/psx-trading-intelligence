import pytest
from psx_app.database.schema import init_db,get_connection
from psx_app.services.performance_comparison import PerformanceComparison,compare
from test_v1314_postgres import remote


def populate(db=None):
    with get_connection(db) as c:
        c.executemany('INSERT INTO equity_ohlcv(trade_date,symbol,close,volume) VALUES (?,?,?,?)',[
          ('2026-01-02','A',90,1),('2026-01-05','A',100,1),('2026-01-06','A',110,1),('2026-01-07','A',105,1),('2026-01-08','A',120,1),
          ('2026-01-05','B',20,1),('2026-01-07','B',22,1),('2026-01-08','B',18,1),('2026-01-06','C',30,1)])
        c.executemany('INSERT INTO index_ohlcv(trade_date,close) VALUES (?,?)',[('2026-01-05',1000),('2026-01-06',1050),('2026-01-08',1100)])

def verify(db=None):
    r=PerformanceComparison(db).report('2026-01-02','2026-01-08','A','B','A');p=r['stock_pair'];q=r['index_pair']
    assert p['start']=='2026-01-05' and p['end']=='2026-01-08' and p['rows'][0]['percent']==[0,0]
    assert next(x for x in p['rows'] if x['date']=='2026-01-06')['values']==[110,None]
    assert p['stats'][0]['pct']==pytest.approx(20) and p['stats'][1]['pct']==pytest.approx(-10)
    assert p['difference_pp']==pytest.approx(30) and p['stats'][1]['max_drawdown_pct']==pytest.approx((18/22-1)*100)
    assert q['start']=='2026-01-05' and q['end']=='2026-01-08' and q['stats'][1]['pct']==pytest.approx(10)
    assert next(x for x in q['rows'] if x['date']=='2026-01-07')['values']==[105,None]
    with pytest.raises(ValueError):PerformanceComparison(db).report('2026-01-09','2026-01-01','A','B','A')
    assert PerformanceComparison(db).report('2026-01-02','2026-01-08','A','C','C')['index_pair']['start']=='2026-01-06'
    assert PerformanceComparison(db).report('2026-01-02','2026-01-08','B','C','C')['stock_pair']['status']=='NO_OVERLAP'

def test_sqlite(tmp_path):
    p=tmp_path/'x.db';init_db(p);populate(p);verify(p)

def test_postgres(remote):
    populate();verify()

def test_insights_index_all(tmp_path):
    from psx_app.services.symbol_insights import SymbolInsights
    p=tmp_path/'x.db';init_db(p);populate(p);r=SymbolInsights(p).report('A',2)
    assert r['symbol_all']['count']==5 and r['symbol_all']['metrics']['max_close']['value']==120
    assert r['index_all']['count']==3 and r['index_all']['metrics']['max_close']['value']==1100
    assert r['index_all']['metrics']['max_volume']['value'] is None

def test_endpoint(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import psx_app.upgrade_routes as route
    p=tmp_path/'x.db';init_db(p);populate(p);monkeypatch.setattr(route,'DB_PATH',p);app=FastAPI();app.include_router(route.router)
    with TestClient(app) as c:
        url='/api/v139/market/performance-comparison?start=2026-01-02&end=2026-01-08&first=A&second=B&stock=A'
        assert c.get(url).json()['stock_pair']['difference_pp']==pytest.approx(30)
        assert c.get(url.replace('2026-01-08','2026-02-30')).status_code==422
