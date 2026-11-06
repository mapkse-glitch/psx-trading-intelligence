from test_v1314_postgres import remote
from psx_app.database.schema import get_connection
from psx_app.services.symbol_insights import SymbolInsights

def test_postgres_insights_date_anchor_and_cache(remote):
 from psx_app.database.turso import revision
 with get_connection() as c:
  c.executemany('INSERT INTO equity_ohlcv(trade_date,symbol,high,low,close,pr_close,volume) VALUES (?,?,?,?,?,?,?)',[
   ('2026-02-27','AAA',120,80,100,99,100),('2026-02-28','AAA',140,70,120,100,200)])
  c.executemany('INSERT INTO index_ohlcv(trade_date,high,low,close) VALUES (?,?,?,?)',[
   ('2026-02-27',1100,900,1000),('2026-02-28',1200,800,1100)])
 before=revision();r=SymbolInsights().report('AAA',1)
 assert r['windows']['session']['count']==1 and r['symbol_comparison']['max_high_vs_anchor']['value']==20
 assert r['index_comparison']['min_low_vs_anchor']['value']==-100
 assert SymbolInsights().report('AAA',1)==r and revision()==before
