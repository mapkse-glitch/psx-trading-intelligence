"""Date-scoped, read-only symbol and index comparisons using synthetic data."""
from pathlib import Path
from test_v1321_market_panels import panels_db
from psx_app.database.schema import get_connection
from psx_app.services.symbol_insights import SymbolInsights
from test_v1318_market_highlights import run_js
from test_v1325_performance import perf_node
import json,re

def populate(db):
 rows=[
 ('2023-09-30',50,300,40,60,55,100),
 ('2023-10-01',60,90,50,70,65,0),
 ('2026-02-26',75,100,60,80,75,200),
 ('2026-02-27',90,120,70,100,95,300),
 ('2026-03-01',110,140,65,115,105,400),
 ('2026-03-02',105,140,60,105,95,400),
 ('2026-03-03',110,130,80,110,None,150)]
 with get_connection(db) as c:
  for dt,op,hi,lo,close,avg,vol in rows:
   c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,open,high,low,close,pr_close,avg_price,volume) VALUES (?,?,?,?,?,?,?,?,?)',(dt,'XYZ',op,hi,lo,close,100,avg,vol))
  c.execute('INSERT INTO company_reference(list_name,symbol,company,sector) VALUES (?,?,?,?)',('COMP_LIST','XYZ','Example Co','TEST'))
  c.executemany('INSERT INTO index_ohlcv(trade_date,open,high,low,close,pr_close) VALUES (?,?,?,?,?,?)',[
   ('2026-02-27',1000,1200,900,1100,1000),('2026-03-01',1100,1300,800,1150,1100),('2026-03-02',1150,1400,950,1200,1150)])

def test_windows_dates_ties_baselines_and_signs(panels_db):
 populate(panels_db);r=SymbolInsights(panels_db).report('xyz',2)
 assert r['latest']['trade_date']=='2026-03-03' and r['company']['name']=='Example Co'
 assert [r['windows'][x]['count'] for x in ['session','all','since_2023','since_2026','after_anchor']]==[2,7,6,4,3]
 assert r['windows']['all']['metrics']['max_high']['value']==300
 assert r['windows']['since_2023']['metrics']['max_high']=={'value':140,'date':'2026-03-02','ties':2}
 assert r['windows']['session']['metrics']['min_volume']['value']==150
 c=r['symbol_comparison'];assert c['anchor']['trade_date']=='2026-02-27'
 assert c['max_high_vs_anchor']=={'value':20,'pct':20/120*100}
 assert c['min_low_vs_anchor']=={'value':-10,'pct':-10/70*100}
 assert c['current_high_vs_max']=={'value':-10,'pct':-10/140*100}
 assert c['current_close_vs_max']=={'value':-5,'pct':-5/115*100}
 idx=r['index_comparison'];assert idx['latest']['trade_date']=='2026-03-02' and idx['anchor']['trade_date']=='2026-02-27'
 assert idx['after']['count']==2 and idx['max_high_vs_anchor']['value']==200
 assert idx['after']['metrics']['max_average']['value'] is None and idx['after']['metrics']['max_volume']['value'] is None

def test_missing_anchor_empty_windows_zero_baseline(panels_db):
 populate(panels_db)
 with get_connection(panels_db) as c:
  c.execute("DELETE FROM equity_ohlcv WHERE symbol='XYZ' AND trade_date='2026-02-27'")
  c.execute("UPDATE index_ohlcv SET high=0 WHERE trade_date='2026-02-27'")
 r=SymbolInsights(panels_db).report('XYZ',6000)
 assert r['symbol_comparison']['anchor'] is None and r['symbol_comparison']['max_high_vs_anchor']['value'] is None
 assert r['index_comparison']['max_high_vs_anchor']=={'value':1400,'pct':None}
 assert SymbolInsights(panels_db).report('missing')['status']=='NO_DATA'

def test_endpoint_and_bounds(panels_db,monkeypatch):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 import psx_app.upgrade_routes as route
 populate(panels_db);monkeypatch.setattr(route,'DB_PATH',panels_db);app=FastAPI();app.include_router(route.router)
 with TestClient(app) as c:
  assert c.get('/api/v139/market/symbol-insights/XYZ?sessions=2').json()['windows']['session']['count']==2
  assert c.get('/api/v139/market/symbol-insights/XYZ?sessions=0').status_code==422

def test_historical_lock_is_same_rule_including_unavailable():
 lower=run_js('priceLockCell1328({pr_close:25.41,close:22.87})')
 upper=run_js('priceLockCell1328({pr_close:66.58,close:73.24})')
 within=run_js('priceLockCell1328({pr_close:100,close:95})')
 missing=run_js('priceLockCell1328({close:95})')
 assert 'history-lock-lower1328' in lower and 'Lower lock reached' in lower
 assert 'history-lock-upper1328' in upper and 'Upper lock reached' in upper
 assert 'history-lock-within1328' in within and 'Within range' in within
 assert 'history-lock-unavailable1328' in missing and 'Lock check unavailable' in missing

def test_bars_escape_names_and_combo_line_has_gaps_and_weekly_unchanged():
 chart={'rows':[{'name':'<LONG>','value':-2},{'name':'B','value':-1}], 'title':'Losers','tone':'neg','unit':'%','id':'test'}
 html=perf_node('perfChart1325('+json.dumps(chart)+')')
 assert '&lt;LONG&gt;' in html and 'perf-hnegative1328' in html and 'width:100%' in html and 'width:50%' in html
 combo={'sectors':['<SECTOR>'],'volume_source':'Cash shares','buckets':[{'date':'2026-03-01','volume':10,'sectors':{'<SECTOR>':10},'index_change':10,'index_date':'2026-03-01','baseline_date':'2026-02-28'}, {'date':'2026-03-02','volume':None,'sectors':None,'index_change':None},{'date':'2026-03-03','volume':0,'sectors':{'<SECTOR>':0},'index_change':-3,'index_date':'2026-03-03','baseline_date':'2026-03-02'}]}
 h=perf_node('perfCombo1325('+json.dumps(combo)+',"monthly")');path=re.search(r'<path d="([^"]*)"',h)[1]
 assert path.count('M')==2 and 'L' not in path and '&lt;SECTOR&gt;' in h
 assert 'perf-combo-grid1328' in h and 'Volume unavailable' in h
 weekly=perf_node('perfCombo1325('+json.dumps(combo)+',"weekly")')
 assert 'performance-line1325' in weekly and 'perf-combo-grid1328' not in weekly

def test_supplied_sindm_examples_use_historical_previous_close():
 for previous,close,status in [(73.24,65.92,'LOWER'),(66.58,73.24,'UPPER'),(86.37,82.20,'WITHIN'),(81.15,89.27,'UPPER')]:
  r=run_js(f'priceLimit1318({{pr_close:{previous},close:{close}}})')
  assert r['status']==status

def test_anchor_without_later_data_never_fabricates_extrema(panels_db):
 with get_connection(panels_db) as c:
  c.execute("INSERT INTO equity_ohlcv(trade_date,symbol,close,high,low,pr_close) VALUES ('2026-02-27','ONLY',10,11,9,10)")
  c.execute("INSERT INTO index_ohlcv(trade_date,close,high,low) VALUES ('2026-02-27',100,110,90)")
 r=SymbolInsights(panels_db).report('ONLY',14)
 assert r['symbol_comparison']['anchor']['trade_date']=='2026-02-27'
 assert r['symbol_comparison']['after']['count']==0
 assert r['symbol_comparison']['max_high_vs_anchor']['value'] is None
 assert r['index_comparison']['max_close_vs_anchor']['pct'] is None

def test_frontend_tab_and_assets_are_wired():
 from test_v1321_frontend import frontend
 root=Path(__file__).resolve().parents[1];html=frontend("marketTabs1321('insights')")
 assert html.index('Symbol vs Index')<html.index('Symbol Insights')<html.index('Matching Rate')
 assert 'insights1328.js?v=1.3.32' in (root/'psx_app/static/index.html').read_text()
 js=(root/'psx_app/static/upgrade139.js').read_text()
 assert "['Date','High','Low','Average','Close','Change','Change %','Lock'" in js and 'priceLockCell1328(x)' in js
 assert 'renderSymbolInsights1328(container,ticket)' in js
