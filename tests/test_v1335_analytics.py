import pytest
from psx_app.database.schema import init_db,get_connection
from psx_app.services.market_analytics1335 import MarketAnalytics1335

@pytest.fixture
def svc(tmp_path):
 p=tmp_path/'test.db';init_db(p)
 with get_connection(p) as c:
  c.executemany('INSERT INTO company_reference(list_name,symbol,company,sector) VALUES (?,?,?,?)',[('COMP_LIST','ABC','ABC Co','SECTOR'),('COMP_LIST','XYZ','XYZ Co','SECTOR')])
  c.executemany('INSERT INTO equity_ohlcv(trade_date,symbol,close,high,low,volume) VALUES (?,?,?,?,?,?)',[
  ('2025-12-31','ABC',100,105,95,100),('2026-01-02','ABC',110,112,101,120),('2026-01-30','ABC',121,125,109,125),('2026-03-02','ABC',99,101,90,140),('2026-03-30','ABC',110,113,98,150),('2026-01-02','XYZ',20,22,19,200),('2026-02-02','XYZ',22,24,20,300)])
  c.executemany('INSERT INTO index_ohlcv(trade_date,close,high,low) VALUES (?,?,?,?)',[('2025-12-31',1000,1010,990),('2026-01-02',1100,1110,1090),('2026-01-30',1200,1210,1190),('2026-03-02',1080,1090,1070),('2026-03-30',1100,1110,1090)])
 return MarketAnalytics1335(p)

def test_chart(svc):
 r=svc.symbol_chart('ABC',3);assert [x['trade_date'] for x in r['rows']]==['2026-01-30','2026-03-02','2026-03-30'];assert r['rows'][0]['pct']==pytest.approx(10);assert r['stock']['pct']==pytest.approx((110/121-1)*100);assert r['index']['start']==1200 and r['index']['end']==1100;assert r['company']['name']=='ABC Co'

def test_highlow(svc):
 r=svc.high_low('ABC');assert r['first']=='2025-12-31' and r['last']=='2026-03-30';assert r['years'][1]['high']==125 and r['years'][1]['low']==90;assert r['months'][1]['high']==125

def test_sector_monthly_gaps(svc):
 r=svc.sector_monthly('SECTOR',2026);abc=r['rows'][0];xyz=r['rows'][1];assert r['months']==[1,2,3];assert abc['months'][1]['pct']==pytest.approx(21);assert abc['months'][3]['pct'] is None;assert xyz['months'][1]['pct'] is None;assert xyz['months'][2]['pct']==pytest.approx(10)

def test_index_year_and_months(svc):
 r=svc.index_monthly(2026);assert r['baseline']['close']==1000 and r['latest']['close']==1100 and r['pct']==pytest.approx(10);assert r['months'][1]['change']==200 and r['months'][3]['pct'] is None;assert 2 not in r['months']

def test_missing_index_endpoint(svc):
 r=svc.symbol_chart('XYZ',2);assert r['index']['end'] is None and r['index']['pct'] is None

from test_v1314_postgres import remote

def test_postgres_parity_and_cache(remote):
 with get_connection() as c:
  c.execute('INSERT INTO company_reference(list_name,symbol,company,sector) VALUES (?,?,?,?)',('COMP_LIST','ABC','ABC Co','SECTOR'))
  c.executemany('INSERT INTO equity_ohlcv(trade_date,symbol,close,high,low,volume) VALUES (?,?,?,?,?,?)',[('2025-12-31','ABC',100,103,98,100),('2026-01-30','ABC',120,121,110,120)])
  c.executemany('INSERT INTO index_ohlcv(trade_date,close,high,low) VALUES (?,?,?,?)',[('2025-12-31',1000,1010,990),('2026-01-30',1100,1120,1080)])
 s=MarketAnalytics1335();assert s.metadata()['sectors']==['SECTOR'];assert s.symbol_chart('ABC',2)['stock']['pct']==pytest.approx(20);assert s.high_low('ABC')['years'][-1]['high']==121;assert s.sector_monthly('SECTOR',2026)['rows'][0]['months'][1]['pct']==pytest.approx(20);assert s.index_monthly(2026)['pct']==pytest.approx(10)
 with get_connection() as c:c.execute('UPDATE index_ohlcv SET close=? WHERE trade_date=?',(1200,'2026-01-30'))
 assert s.index_monthly(2026)['pct']==pytest.approx(20)

def test_first_index_month_uses_previous_year_end_when_gap(svc):
 with get_connection(svc.db_path) as c:c.execute("DELETE FROM index_ohlcv WHERE trade_date>=? AND trade_date<?",('2026-01-01','2026-03-01'))
 r=svc.index_monthly(2026);assert list(r['months'])==[3];assert r['months'][3]['baseline_date']=='2025-12-31' and r['months'][3]['pct']==pytest.approx(10)

def test_api_routes(svc,monkeypatch):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 import psx_app.upgrade_routes as routes
 monkeypatch.setattr(routes,'DB_PATH',svc.db_path);app=FastAPI();app.include_router(routes.router)
 with TestClient(app) as c:
  assert c.get('/api/v139/analytics/metadata').json()['sectors']==['SECTOR']
  assert c.get('/api/v139/analytics/symbol-chart?symbol=ABC&sessions=3').status_code==200
  assert c.get('/api/v139/analytics/symbol-chart?symbol=ABC&sessions=0').status_code==422
  assert c.get('/api/v139/analytics/high-low?symbol=ABC').json()['years'][1]['high']==125
  assert c.get('/api/v139/analytics/sector-monthly?sector=SECTOR&year=2026').json()['rows'][0]['symbol']=='ABC'
  assert c.get('/api/v139/analytics/index-monthly?year=100').status_code==422
