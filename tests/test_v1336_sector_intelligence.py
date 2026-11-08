import pytest
from datetime import date,timedelta
from psx_app.database.schema import init_db,get_connection
from psx_app.services.sector_intelligence1336 import SectorIntelligence1336,percentile,score,bounds,volume_change
from test_v1314_postgres import remote

def seed(c):
 c.executemany('INSERT INTO company_reference(list_name,symbol,company,sector) VALUES (?,?,?,?)',[('COMP_LIST','AAA','Alpha','SECTOR'),('COMP_LIST','BBB','Beta','SECTOR'),('COMP_LIST','CCC','Gamma','SECTOR'),('COMP_LIST','DDD','Other','OTHER')])
 days=['2026-04-03','2026-04-06','2026-04-07','2026-04-08','2026-04-09','2026-04-10','2026-04-13','2026-04-14','2026-04-15','2026-04-16','2026-04-17','2026-04-20','2026-04-21','2026-04-22']
 rows=[]
 for i,d in enumerate(days):
  rows += [(d,'AAA',100+i,100+i*10),(d,'BBB',200-i,200+i*5)]
  if d!='2026-04-21':rows.append((d,'CCC',50+i,50))
  rows.append((d,'DDD',30+i,20))
 c.executemany('INSERT INTO equity_ohlcv(trade_date,symbol,close,volume) VALUES (?,?,?,?)',rows)
@pytest.fixture
def svc(tmp_path):
 p=tmp_path/'test.db';init_db(p)
 with get_connection(p) as c:seed(c)
 return SectorIntelligence1336(p)

def test_weekly_comparable_and_rank(svc):
 r=svc.report('SECTOR','weekly');a,b,c=r['rows'];assert r['as_of']=='2026-04-22' and r['partial'];assert r['periods'][0]['dates']==['2026-04-20','2026-04-21','2026-04-22']
 assert a['current']['start']==110 and a['current']['end']==113 and a['current']['return_pct']==pytest.approx((113/110-1)*100)
 assert a['previous']['start']==105 and a['previous']['end']==110
 assert a['current']['volume']==(210+220+230);assert a['previous']['volume']==sum(range(160,201,10))
 assert a['equivalent']['volume']==160+170+180 and a['equivalent_volume_pct']==pytest.approx((660/510-1)*100)
 assert a['equivalent_return_difference']==pytest.approx((113/110-108/105)*100)
 assert a['current']['rank']==1 and a['previous']['rank']==1 and a['rank_movement']==0
 assert b['current']['return_pct']<0 and b['current']['score']<80 and c['current']['rating']=='Insufficient data'
 assert r['overview']['listed']==3 and r['overview']['active']==3 and r['overview']['advancing']==2 and r['overview']['declining']==1
 assert r['overview']['volume_complete'] is False and r['overview']['value'] is None

def test_daily_previous_session_and_missing(svc):
 r=svc.report('SECTOR','daily');a,b,c=r['rows'];assert r['periods'][1]['start']=='2026-04-21';assert a['current']['return_pct']==pytest.approx((113/112-1)*100);assert c['current']['baseline_date']=='2026-04-20';assert c['current']['rating']=='Insufficient data';assert c['current']['volume_pct'] is None

def test_calendar_boundaries_and_empty_period(svc):
 assert bounds(date(2026,7,2),'quarterly')==(date(2026,7,1),date(2026,9,30));assert bounds(date(2026,7,2),'yearly')==(date(2026,1,1),date(2026,12,31))
 for kind in ['monthly','quarterly','yearly']:
  r=svc.report('SECTOR',kind);assert r['partial'] and r['rows'][0]['current']['rating']=='Insufficient data'
 assert svc.report('SECTOR','yearly',2025)['status']=='NO_DATA'
 with pytest.raises(ValueError):svc.report('MISSING','daily')

def test_normalization_ties_and_zero_volume():
 assert percentile(4,[4,4,4])==50 and percentile(1,[1,2,3])==0 and percentile(3,[1,2,3])==100
 assert volume_change(0,100)==-100 and volume_change(10,0) is None

def test_endpoint(svc,monkeypatch):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 import psx_app.upgrade_routes as routes
 monkeypatch.setattr(routes,'DB_PATH',svc.db_path);app=FastAPI();app.include_router(routes.router)
 with TestClient(app) as c:
  assert c.get('/api/v139/sector-intelligence',params={'sector':'SECTOR','period':'weekly'}).json()['rows'][0]['current']['rank']==1
  assert c.get('/api/v139/sector-intelligence',params={'sector':'SECTOR','period':'nonsense'}).status_code==422
  assert c.get('/api/v139/sector-intelligence',params={'sector':'NOT FOUND'}).status_code==422

def test_postgres_parity_and_revision(remote):
 with get_connection() as c:seed(c)
 s=SectorIntelligence1336();r=s.report('SECTOR','weekly');assert r['rows'][0]['current']['rank']==1 and r['rows'][0]['equivalent']['volume']==510
 with get_connection() as c:c.execute('UPDATE equity_ohlcv SET close=? WHERE symbol=? AND trade_date=?',(150,'AAA','2026-04-22'))
 assert s.report('SECTOR','weekly')['rows'][0]['current']['end']==150

def test_weekend_quote_does_not_become_weekly_baseline(svc):
 with get_connection(svc.db_path) as c:c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,close,volume) VALUES (?,?,?,?)',('2026-04-04','AAA',999,100))
 r=svc.report('SECTOR','weekly');assert r['rows'][0]['older']['start']==100 and r['rows'][0]['older']['baseline_date']=='2026-04-03'

def test_missing_baselines_and_no_equivalent_sessions(svc):
 with get_connection(svc.db_path) as c:
  c.execute('DELETE FROM equity_ohlcv WHERE trade_date<?',('2026-04-13',))
 r=svc.report('SECTOR','weekly');a=r['rows'][0];assert a['current']['return_pct'] is not None and a['previous']['return_pct'] is None
 assert a['current']['rating']=='Insufficient data' and a['previous']['rank'] is None
 assert a['performance_difference'] is None and a['rank_movement'] is None

def test_negative_returns_cannot_receive_excellent_rating():
 def p(ret,vol,cons):return {'return_pct':ret,'volume':vol,'complete':True,'consistency':cons}
 rows=[{'now':p(-.1,200,1),'prev':p(-1,100,1)},{'now':p(-20,100,.1),'prev':p(-1,100,1)}]
 score(rows,'now','prev');assert rows[0]['now']['score']<=79 and rows[0]['now']['rating'] not in ('Excellent','Very Strong')

def test_year_selection_excludes_later_records(svc):
 with get_connection(svc.db_path) as c:c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,close,volume) VALUES (?,?,?,?)',('2027-01-05','AAA',999,999))
 r=svc.report('SECTOR','yearly',2026);assert r['as_of']=='2026-04-22' and r['rows'][0]['current']['end']==113

def test_relative_peer_mean_includes_valid_unscored_returns(svc):
 r=svc.report('SECTOR','weekly');returns=[x['current']['return_pct'] for x in r['rows'] if x['current']['return_pct'] is not None]
 assert r['peer_mean']==pytest.approx(sum(returns)/len(returns))
 c=r['rows'][2];assert c['current']['score'] is None and c['current']['relative_pct']==pytest.approx(c['current']['return_pct']-r['peer_mean'])

def test_true_zero_volume_is_not_missing(svc):
 with get_connection(svc.db_path) as c:c.execute('UPDATE equity_ohlcv SET volume=0 WHERE trade_date=?',('2026-04-22',))
 r=svc.report('SECTOR','daily');assert r['overview']['volume']==0 and r['overview']['active']==0
 assert r['rows'][0]['current']['volume_pct']==-100
