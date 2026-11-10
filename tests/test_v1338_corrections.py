import pytest
from psx_app.database.schema import init_db,get_connection
from psx_app.services.market_explorer import MarketExplorer
from psx_app.services.symbol_insights import SymbolInsights
from psx_app.services.market_analytics1335 import MarketAnalytics1335

@pytest.fixture
def db(tmp_path):
 p=tmp_path/'t.db';init_db(p)
 with get_connection(p) as c:
  c.executemany('INSERT INTO company_reference(list_name,symbol,company,sector) VALUES (?,?,?,?)',[('COMP_LIST','UP','Up','S'),('COMP_LIST','TIE','Tie','S'),('COMP_LIST','ONE','One','S'),('COMP_LIST','DOWN','Down','S'),('COMP_LIST','NOB','No baseline','S')])
  c.executemany('INSERT INTO equity_ohlcv(trade_date,symbol,close,pr_close,high,low,volume) VALUES (?,?,?,?,?,?,?)',[
   ('2025-12-30','UP',100,99,102,98,200),('2026-01-02','UP',120,100,121,99,220),('2026-02-02','UP',125,120,126,119,220),
   ('2025-12-30','TIE',80,79,81,78,100),('2026-02-02','TIE',80,80,81,79,100),
   ('2026-02-02','ONE',44,43,45,43,100),('2025-12-30','DOWN',100,100,101,99,100),('2026-02-02','DOWN',90,100,101,89,100),('2026-02-02','NOB',20,19,22,18,100)])
 return p

def test_record_high_agrees_for_both_reports(db):
 for symbol,expected in [('UP',True),('TIE',False),('ONE',False),('DOWN',False)]:
  assert MarketExplorer(db).symbol(symbol,1)['latest_symbol']['new_closing_high'] is expected
  assert SymbolInsights(db).report(symbol)['latest']['new_closing_high'] is expected
 assert MarketExplorer(db).symbol('UP',1,end='2026-01-02')['latest_symbol']['new_closing_high'] is True

def test_sector_ytd_uses_prior_year_close_and_latest(db):
 rows={r['symbol']:r for r in MarketAnalytics1335(db).sector_monthly('S',2026)['rows']}
 assert rows['UP']['ytd']['change']==pytest.approx(25)
 assert rows['UP']['ytd']['pct']==pytest.approx(25)
 assert rows['UP']['ytd']['baseline_date']=='2025-12-30'
 assert rows['UP']['ytd']['date']=='2026-02-02'
 assert rows['DOWN']['ytd']['change']==pytest.approx(-10)
 assert rows['NOB']['ytd']['change'] is None and rows['NOB']['ytd']['pct'] is None

from test_v1314_postgres import remote

def test_postgres_new_high_and_ytd(remote):
 with get_connection() as c:
  c.execute('INSERT INTO company_reference(list_name,symbol,company,sector) VALUES (?,?,?,?)',('COMP_LIST','ABC','ABC Co','S'))
  c.executemany('INSERT INTO equity_ohlcv(trade_date,symbol,close,pr_close,high,low,volume) VALUES (?,?,?,?,?,?,?)',[
   ('2025-12-31','ABC',100,99,101,98,100),('2026-02-02','ABC',120,100,121,99,100)])
 # Simulate a prior-release cache at the same revision and Karachi date.
 import base64,gzip,hashlib,json
 from datetime import datetime,timezone
 from zoneinfo import ZoneInfo
 day=datetime.now(ZoneInfo('Asia/Karachi')).date().isoformat()
 old=[('psx_app.services.market_explorer','MarketExplorer.symbol',{'symbol':'ABC','n':1,'end':None}),('psx_app.services.symbol_insights','SymbolInsights.report_v1333',{'symbol':'ABC','sessions':14}),('psx_app.services.market_analytics1335','MarketAnalytics1335.sector_monthly',{'sector':'S','year':2026})]
 with get_connection() as c:
  rev=c.execute("SELECT value FROM psx_runtime WHERE key='revision'").fetchone()[0]
  for module,name,args in old:
   key=hashlib.sha256(json.dumps([module,name,args,'1.3.17',day],sort_keys=True,default=str).encode()).hexdigest()
   payload=base64.b64encode(gzip.compress(b'{"status":"STALE"}')).decode()
   c.execute('INSERT INTO analysis_cache(cache_key,revision,payload_json,updated_at) VALUES (?,?,?,?)',(key,rev,payload,datetime.now(timezone.utc).isoformat()))
 assert MarketExplorer().symbol('ABC',1)['latest_symbol']['new_closing_high'] is True
 assert SymbolInsights().report('ABC')['latest']['new_closing_high'] is True
 row=MarketAnalytics1335().sector_monthly('S',2026)['rows'][0]
 assert row['ytd']['change']==pytest.approx(20) and row['ytd']['pct']==pytest.approx(20)
