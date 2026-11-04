"""Range searches against an explicitly guarded disposable loopback PostgreSQL."""
from datetime import date,timedelta
from test_v1314_postgres import remote
from psx_app.database.schema import get_connection
from psx_app.services.market_panels import MarketPanels

def test_postgres_range_pagination_dates_and_no_cache_write(remote):
 from psx_app.database.turso import revision
 with get_connection() as c:
  data=[((date(2025,1,1)+timedelta(days=i)).isoformat(),'AAA',22.87 if i in (0,204) else 23.0) for i in range(205)]
  c.executemany('INSERT INTO equity_ohlcv(trade_date,symbol,close) VALUES (?,?,?)',data)
  c.execute('INSERT INTO index_ohlcv(trade_date,close) VALUES (?,?)',(data[0][0],1000))
 before=revision();p=MarketPanels();r=p.matching_range('AAA',22.87,22.87,include_recent=True)
 assert r['total']==2 and len(r['rows'])==2
 assert r['rows'][0]['sessions_ago']==0 and r['rows'][1]['sessions_ago']==204
 assert r['rows'][0]['index_close'] is None and r['rows'][1]['index_close']==1000
 pages=[p.matching_range('AAA',22,24,n,True) for n in (1,2,3)]
 assert [len(x['rows']) for x in pages]==[100,100,5] and all(x['total']==205 for x in pages)
 assert len({r['trade_date'] for x in pages for r in x['rows']})==205
 assert revision()==before
 with get_connection() as c:assert c.execute('SELECT COUNT(*) FROM analysis_cache').fetchone()[0]==0
