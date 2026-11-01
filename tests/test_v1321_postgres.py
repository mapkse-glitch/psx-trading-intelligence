"""New endpoints on an explicit disposable loopback *_test PostgreSQL only."""
import pytest
from test_v1314_postgres import remote
from psx_app.database.schema import get_connection
from psx_app.services.market_panels import MarketPanels

def seed():
 with get_connection() as c:
  c.executemany('INSERT INTO company_reference(list_name,symbol,company,sector) VALUES (?,?,?,?)',[('SEL_COMP_LIST','AAA','Alpha','CEMENT'),('SEL_COMP_LIST','EMPTY','No price','CEMENT'),('COMP_LIST','OTHER','Excluded','CEMENT')])
  c.executemany('INSERT INTO equity_ohlcv(trade_date,symbol,close,pr_close,high,low,volume) VALUES (?,?,?,?,?,?,?)',[(d,'AAA',v,v-1,v+2,v-2,1000) for d,v in [('2025-01-01',99),('2025-01-02',101),('2025-03-30',98),('2025-04-01',100),('2025-04-02',103),('2025-04-10',100)]])
  c.executemany('INSERT INTO index_ohlcv(trade_date,close,pr_close,high,low) VALUES (?,?,?,?,?)',[('2025-01-02',1000,900,1100,800),('2025-04-01',1100,1000,1200,1000),('2025-04-10',1200,1100,1300,1100)])

def test_new_panels_read_only_results_and_shared_cache(remote):
 seed()
 from psx_app.database.turso import revision
 before=revision();p=MarketPanels();m=p.matching('AAA');s=p.small_cards('CEMENT',2)
 assert m['cutoff']=='2025-03-10' and len(m['rows'])==2
 assert [r['trade_date'] for r in m['rows']]==['2025-01-02','2025-01-01']
 assert [r['sessions_ago'] for r in m['rows']]==[4,5]
 assert m['rows'][0]['index_difference']==200 and m['rows'][1]['index_close'] is None
 assert len(s['cards'])==2 and s['cards'][1]['status']=='NO_DATA'
 assert s['cards'][0]['session_count']==2 and s['cards'][0]['session_high']==105 and s['cards'][0]['session_low']==98
 assert s['cards'][0]['month']['change']==2
 assert s['index']['window']['change']==200
 assert p.matching('AAA')==m and p.small_cards('CEMENT',2)==s
 assert revision()==before
 with get_connection() as c:
  assert c.execute('SELECT COUNT(*) FROM analysis_cache').fetchone()[0]>=2
  c.execute("INSERT INTO company_reference(list_name,symbol,company,sector) VALUES ('SEL_COMP_LIST','NEW','New Authentic','CEMENT')")
 assert len(p.small_cards('CEMENT',2)['cards'])==3

def test_panel_api_validation_and_no_reference_fallback(remote,monkeypatch):
 seed()
 from fastapi.testclient import TestClient
 import psx_app.main as main
 with TestClient(main.app) as client:
  for route in ['/api/v139/market/selected-sectors','/api/v139/market/matching/AAA','/api/v139/market/small-cards?sector=CEMENT&sessions=2']:
   r=client.get(route);assert r.status_code==200 and r.json()['status']=='OK'
  for n in [0,6001,'bad']:
   assert client.get('/api/v139/market/small-cards',params={'sector':'CEMENT','sessions':n}).status_code==422
  assert client.get('/api/v139/market/small-cards',params={'sector':"CEMENT' OR 1=1 --"}).json()['cards']==[]
  with get_connection() as c:c.execute("DELETE FROM company_reference WHERE list_name='SEL_COMP_LIST'")
  assert client.get('/api/v139/market/selected-sectors').json()['status']=='NO_REFERENCE'
