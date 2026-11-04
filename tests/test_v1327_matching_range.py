"""Inclusive price-range matches, exact index dates, pagination and validation."""
from datetime import date,timedelta
import pytest
from test_v1321_market_panels import panels_db
from psx_app.database.schema import get_connection
from psx_app.services.market_panels import MarketPanels

def test_range_inclusive_and_stored_session_gaps(panels_db):
 p=MarketPanels(panels_db)
 r=p.matching_range('aaa', 110,112,include_recent=True)
 assert r['total']==3 and [x['close'] for x in r['rows']]==[112,111,110]
 assert [x['sessions_ago'] for x in r['rows']]==[87,88,89]
 assert r['rows'][0]['index_difference']==870 and r['rows'][0]['index_date']==r['rows'][0]['trade_date']
 assert p.matching_range('AAA',195,199,include_recent=False)['total']==0
 assert p.matching_range('AAA',195,199,include_recent=True)['total']==5
 assert p.matching_range('AAA',111,111,include_recent=True)['total']==1
 assert p.matching_range('NOPE',0,100)['status']=='NO_DATA'

def test_exact_index_only_and_difference_signs(panels_db):
 with get_connection(panels_db) as c:
  c.execute("UPDATE equity_ohlcv SET close=200 WHERE symbol='AAA' AND trade_date='2025-01-01'")
  c.execute("DELETE FROM index_ohlcv WHERE trade_date='2025-01-01'")
 r=MarketPanels(panels_db).matching_range('AAA',200,200,include_recent=True)
 assert r['rows'][0]['close_difference']==-1 and r['rows'][0]['index_close'] is None
 assert r['rows'][0]['index_difference'] is None

def test_pagination_covers_all_without_duplicates(panels_db):
 with get_connection(panels_db) as c:
  for i in range(145):
   dt=(date(2024,1,1)+timedelta(days=i)).isoformat()
   c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,close) VALUES(?,?,?)',(dt,'AAA',150))
 p=MarketPanels(panels_db);pages=[p.matching_range('AAA',0,300,i,True) for i in (1,2,3)]
 assert all(x['total']==245 for x in pages)
 rows=[r for x in pages for r in x['rows']]
 assert len(rows)==245 and len({r['trade_date'] for r in rows})==245
 assert [len(x['rows']) for x in pages]==[100,100,45]
 assert all(abs(rows[i]['close']-199)<=abs(rows[i+1]['close']-199) for i in range(244))

def test_invalid_ranges_and_api_validation(panels_db,monkeypatch):
 p=MarketPanels(panels_db)
 for lo,hi in [(-1,5),(2,1),(float('nan'),5),(0,float('inf'))]:
  with pytest.raises(ValueError):p.matching_range('AAA',lo,hi)
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 import psx_app.upgrade_routes as route
 monkeypatch.setattr(route,'DB_PATH',panels_db)
 app=FastAPI();app.include_router(route.router)
 with TestClient(app) as c:
  path='/api/v139/market/matching-range/AAA'
  assert c.get(path,params={'low':110,'high':112,'include_recent':'true'}).json()['total']==3
  for params in [{'low':4,'high':2},{'low':-1,'high':3},{'low':'NaN','high':3},{'low':0,'high':'inf'},{'low':0,'high':3,'page':0}]:
   assert c.get(path,params=params).status_code==422
