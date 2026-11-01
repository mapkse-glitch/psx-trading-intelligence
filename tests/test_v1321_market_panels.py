"""Synthetic reference membership, matching history and selected-session calculations."""
from datetime import date,timedelta
from contextlib import contextmanager
import pytest
from psx_app.database.schema import init_db,get_connection
from psx_app.services.market_panels import MarketPanels,month_before

@pytest.fixture
def panels_db(tmp_path):
 p=tmp_path/'panels.db';init_db(p)
 with get_connection(p) as c:
  c.executemany('INSERT INTO company_reference(list_name,symbol,company,sector) VALUES (?,?,?,?)',[
   ('SEL_COMP_LIST','AAA','Alpha Authentic','CEMENT'),('SEL_COMP_LIST','BBB','Beta Authentic','CEMENT'),
   ('SEL_COMP_LIST','EMPTY','No Prices Limited','CEMENT'),('COMP_LIST','EXCLUDED','Not Selected','CEMENT'),
   ('SEL_COMP_LIST','CCC','Cee Authentic','REFINERY')])
  for i in range(100):
   dt=(date(2025,1,1)+timedelta(days=i)).isoformat()
   # Synthetic stored sessions include weekends deliberately: count records, never guess calendar.
   c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,close,pr_close,high,low,avg_price,volume) VALUES (?,?,?,?,?,?,?,?)',(dt,'AAA',100+i,99+i,102+i,98+i,101+i,1000+i))
   c.execute('INSERT INTO index_ohlcv(trade_date,close,pr_close,high,low) VALUES (?,?,?,?,?)',(dt,1000+10*i,990+10*i,1010+10*i,980+10*i))
  for i in range(2):
   dt=(date(2025,4,9)+timedelta(days=i)).isoformat()
   c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,close,pr_close,high,low,volume) VALUES (?,?,?,?,?,?,?)',(dt,'BBB',5+i,4+i,7+i,3+i,0))
 return p

@pytest.mark.parametrize('value,expected',[('2025-03-31','2025-02-28'),('2024-03-31','2024-02-29'),('2025-01-15','2024-12-15'),('2025-04-10','2025-03-10')])
def test_calendar_month_cutoff_handles_short_months(value,expected):assert month_before(value)==expected

def test_matching_excludes_recent_month_and_counts_all_stored_sessions(panels_db):
 r=MarketPanels(panels_db).matching('aaa')
 assert r['latest']['trade_date']=='2025-04-10' and r['cutoff']=='2025-03-10'
 assert len(r['rows'])==10
 assert all(x['trade_date']<'2025-03-10' for x in r['rows'])
 assert r['rows'][0]['trade_date']=='2025-03-09' and r['rows'][0]['sessions_ago']==32
 assert r['rows'][0]['close_difference']==32
 assert r['rows'][0]['index_difference']==320
 assert r['rows'][0]['index_date']==r['rows'][0]['trade_date']

def test_matching_signed_difference_ties_and_exact_index_dates(panels_db):
 with get_connection(panels_db) as c:
  c.execute("UPDATE equity_ohlcv SET close=100 WHERE symbol='AAA' AND trade_date='2025-04-10'")
  c.execute("UPDATE equity_ohlcv SET close=98 WHERE symbol='AAA' AND trade_date='2025-03-08'")
  c.execute("UPDATE equity_ohlcv SET close=102 WHERE symbol='AAA' AND trade_date='2025-03-09'")
  # Remove other near prices so the ±2 tie is the nearest pair.
  c.execute("UPDATE equity_ohlcv SET close=500 WHERE symbol='AAA' AND trade_date<'2025-03-08'")
  c.execute("DELETE FROM index_ohlcv WHERE trade_date='2025-03-09'")
 r=MarketPanels(panels_db).matching('AAA')
 assert [x['trade_date'] for x in r['rows'][:2]]==['2025-03-09','2025-03-08']
 assert [x['close_difference'] for x in r['rows'][:2]]==[-2,2]
 assert r['rows'][0]['index_date'] is None and r['rows'][0]['index_close'] is None and r['rows'][0]['index_difference'] is None
 assert r['rows'][1]['index_date']=='2025-03-08'

def test_matching_no_data_and_short_history_never_fabricate(panels_db):
 assert MarketPanels(panels_db).matching('NOPE')['status']=='NO_DATA'
 assert MarketPanels(panels_db).matching('BBB')['rows']==[]

def test_reference_membership_counts_and_no_bundled_fallback(panels_db):
 r=MarketPanels(panels_db).sectors();assert r['source']=='SEL_COMP_LIST'
 assert r['sectors']==[{'sector':'CEMENT','symbols':3},{'sector':'REFINERY','symbols':1}]
 with get_connection(panels_db) as c:c.execute("DELETE FROM company_reference WHERE list_name='SEL_COMP_LIST'")
 assert MarketPanels(panels_db).sectors()['status']=='NO_REFERENCE'
 assert MarketPanels(panels_db).small_cards('CEMENT')['status']=='NO_REFERENCE'

def test_sector_cards_exact_members_missing_data_and_session_windows(panels_db):
 r=MarketPanels(panels_db).small_cards('CEMENT',14)
 assert len(r['cards'])==3 and [c['symbol'] for c in r['cards']]==['AAA','BBB','EMPTY']
 a,b,e=r['cards'];assert e['status']=='NO_DATA'
 assert a['close']==199 and a['change']==1 and a['pct']==pytest.approx(100/198)
 assert a['avg_price']==200 and a['volume']==1099
 assert a['session_count']==14 and a['session_first']=='2025-03-28'
 assert a['session_high']==201 and a['session_low']==184
 assert b['session_count']==2 and b['session_high']==8 and b['session_low']==3
 assert b['avg_price'] is None and b['volume']==0
 assert a['week_baseline_date']=='2025-04-06' and a['week']['change']==4
 assert a['month_baseline_date']=='2025-03-31' and a['month']['change']==10
 assert b['week']['change'] is None and b['month']['change'] is None
 index=r['index'];assert index['latest']['trade_date']=='2025-04-10'
 assert index['window']['count']==14 and index['window']['baseline_date']=='2025-03-27'
 assert index['window']['change']==140 and index['window']['high']==2000 and index['window']['low']==1840
 assert index['window']['pct']==pytest.approx(140/1850*100)

def test_index_window_own_sessions_stale_dates_and_missing_baseline(panels_db):
 with get_connection(panels_db) as c:
  c.execute("DELETE FROM index_ohlcv WHERE trade_date>'2025-04-08'")
 r=MarketPanels(panels_db).small_cards('CEMENT',6000)
 assert r['index']['latest']['trade_date']=='2025-04-08'
 assert r['index']['window']['count']==98 and r['index']['window']['change'] is None
 assert r['index']['window']['baseline_date'] is None
 assert r['cards'][0]['session_count']==100

def test_stale_symbol_does_not_claim_week_or_month_activity(panels_db):
 with get_connection(panels_db) as c:c.execute("DELETE FROM equity_ohlcv WHERE symbol='AAA' AND trade_date>='2025-04-01'")
 r=MarketPanels(panels_db).small_cards('CEMENT',1);a=r['cards'][0]
 assert a['stale'] and a['week']['change'] is None and a['month']['change'] is None
 assert a['session_count']==1 and a['session_high']==191 and a['session_low']==187

def test_no_prices_still_returns_all_reference_cards(panels_db):
 with get_connection(panels_db) as c:c.execute('DELETE FROM equity_ohlcv');c.execute('DELETE FROM index_ohlcv')
 r=MarketPanels(panels_db).small_cards('CEMENT',14)
 assert r['as_of'] is None and r['index'] is None and len(r['cards'])==3
 assert all(c['status']=='NO_DATA' for c in r['cards'])
 assert MarketPanels(panels_db).small_cards('NOPE')['status']=='NO_SECTOR'

def test_selected_reference_normalized_name_supported_but_not_comp_list(panels_db):
 with get_connection(panels_db) as c:c.execute("UPDATE company_reference SET list_name='sel comp list' WHERE list_name='SEL_COMP_LIST'")
 assert MarketPanels(panels_db).sectors()['source']=='sel comp list'

def test_sector_database_reads_are_batched_not_per_card(panels_db,monkeypatch):
 import psx_app.services.market_panels as module
 count=[];original=module.get_connection
 class Proxy:
  def __init__(self,c):self.c=c
  def execute(self,sql,*args):count.append(sql);return self.c.execute(sql,*args)
 @contextmanager
 def counted(path):
  with original(path) as c:yield Proxy(c)
 monkeypatch.setattr(module,'get_connection',counted)
 MarketPanels(panels_db).small_cards('CEMENT',14)
 assert len(count)==6  # names, members, anchor, one aggregate batch, one baseline batch, index window
 assert sum('WITH ranked' in sql for sql in count)==1

def test_many_members_stay_in_bounded_batches(panels_db):
 with get_connection(panels_db) as c:
  for i in range(105):
   s=f'X{i:03d}'
   c.execute('INSERT INTO company_reference(list_name,symbol,company,sector) VALUES (?,?,?,?)',('SEL_COMP_LIST',s,s,'LARGE'))
   c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,close,pr_close,high,low) VALUES (?,?,?,?,?,?)',('2025-04-10',s,10,9,11,8))
 r=MarketPanels(panels_db).small_cards('LARGE',14)
 assert len(r['cards'])==105 and all(c['session_count']==1 and c['week']['change'] is None for c in r['cards'])

def test_matching_does_not_use_future_index_or_hide_real_zero_prices(panels_db):
 with get_connection(panels_db) as c:
  c.execute('DELETE FROM index_ohlcv')
  c.execute("INSERT INTO index_ohlcv(trade_date,close,pr_close) VALUES ('2030-01-01',9999,9000)")
  c.execute("UPDATE equity_ohlcv SET close=0 WHERE symbol='AAA' AND trade_date IN ('2025-04-10','2025-03-09')")
 r=MarketPanels(panels_db).matching('AAA')
 assert r['latest_index'] is None
 assert r['rows'][0]['close']==0 and r['rows'][0]['close_difference']==0
 assert all(x['index_close'] is None and x['latest_index_close'] is None for x in r['rows'])

def test_index_one_session_uses_the_immediately_preceding_stored_close(panels_db):
 r=MarketPanels(panels_db).small_cards('CEMENT',1)
 assert r['index']['window']['count']==1
 assert r['index']['window']['baseline_date']=='2025-04-09'
 assert r['index']['window']['change']==10
 assert r['cards'][0]['session_high']==201 and r['cards'][0]['session_low']==197
