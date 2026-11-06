"""Fiscal windows, comparable imported returns, exact volume stacks and frontend guards."""
from datetime import date
from pathlib import Path
import json
import subprocess
import pytest
from psx_app.database.schema import init_db,get_connection
from psx_app.services.market_performance import MarketPerformance,period_for
ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('day,kind,key,start,end',[
 ('2026-07-01','quarterly','FY2027-Q1','2026-07-01','2026-09-30'),
 ('2026-10-01','quarterly','FY2027-Q2','2026-10-01','2026-12-31'),
 ('2027-01-01','quarterly','FY2027-Q3','2027-01-01','2027-03-31'),
 ('2027-06-30','quarterly','FY2027-Q4','2027-04-01','2027-06-30'),
 ('2026-12-31','halfyear','FY2027-H1','2026-07-01','2026-12-31'),
 ('2027-01-01','halfyear','FY2027-H2','2027-01-01','2027-06-30'),
 ('2027-03-01','ninemonth','FY2027-9M','2026-07-01','2027-03-31'),
 ('2026-07-01','yearly','FY2027','2026-07-01','2027-06-30'),
 ('2026-06-30','yearly','FY2026','2025-07-01','2026-06-30'),
 ('2024-02-29','monthly','2024-02','2024-02-01','2024-02-29'),
 ('2027-01-01','weekly','2026-W53','2026-12-28','2027-01-01'),
 ('2026-10-30','weekly','2026-W44','2026-10-26','2026-10-30'),
])
def test_fiscal_and_weekday_windows(day,kind,key,start,end):
 p=period_for(day,kind);assert p[0]==key and p[1].isoformat()==start and p[2].isoformat()==end

def test_no_weekend_weeks_or_april_nine_month_fabrication():
 assert period_for('2026-10-31','weekly') is None
 assert period_for('2027-04-01','ninemonth') is None

def seed(c):
 refs=[('COMP_LIST','AAA','Alpha','BANKS'),('COMP_LIST','BBB','Beta','BANKS'),
       ('COMP_LIST','CCC','Gamma','CEMENT'),('COMP_LIST','OUT','Outsider','OIL')]
 refs += [('KSE100',s,s,sec) for s,sec in [('AAA','BANKS'),('BBB','BANKS'),('CCC','CEMENT'),('STALE','OIL'),('ZERO','CEMENT'),('NEW','CEMENT'),('ABSENT','CEMENT')]]
 c.executemany('INSERT INTO company_reference(list_name,symbol,company,sector) VALUES(?,?,?,?)',refs)
 # Friday baseline; Saturday deliberately must not leak into weekly comparisons.
 points=[('2026-10-23','AAA',100,1),('2026-10-24','AAA',9000,9000),
 ('2026-10-23','BBB',200,1),('2026-10-23','CCC',100,1),('2026-10-23','STALE',50,1),
 ('2026-10-23','ZERO',0,1),('2026-10-23','OUT',10,1),
 ('2026-10-26','AAA',105,10),('2026-10-26','BBB',190,20),('2026-10-26','STALE',60,5),
 ('2026-10-30','AAA',110,30),('2026-10-30','BBB',190,40),('2026-10-30','CCC',80,50),
 ('2026-10-30','ZERO',5,3),('2026-10-30','NEW',40,4),('2026-10-30','OUT',30,60),
 ('2026-10-30','UNMAPPED',8,8),('2026-10-31','AAA',99999,999999)]
 c.executemany('INSERT INTO equity_ohlcv(trade_date,symbol,close,volume) VALUES(?,?,?,?)',points)
 c.executemany('INSERT INTO index_ohlcv(trade_date,close) VALUES(?,?)',[
 ('2026-10-23',1000),('2026-10-24',9999),('2026-10-26',1010),('2026-10-30',1050),('2026-10-31',99999)])

@pytest.fixture
def market_db(tmp_path):
 p=tmp_path/'market.db';init_db(p)
 with get_connection(p) as c:seed(c)
 return p

def ch(r,id):return next(c for c in r['charts'] if c['id']==id)['rows']

def test_weekly_returns_membership_stale_and_exact_volumes(market_db):
 r=MarketPerformance(market_db).report('weekly','2026-W44')
 assert r['start']=='2026-10-26' and r['end']=='2026-10-30'
 assert r['index']['baseline_date']=='2026-10-23' and r['index']['change']==50 and r['index']['pct']==5
 assert r['cash_as_of']=='2026-10-30' and r['coverage']['eligible']==3
 assert r['coverage']['stale']==1 and r['coverage']['invalid_baseline_or_price']==2 and r['coverage']['missing']==1
 assert ch(r,'scrip_PKR_gainers')[0]['name']=='AAA' and ch(r,'scrip_PKR_gainers')[0]['value']==10
 assert [x['name'] for x in ch(r,'scrip_PKR_losers')]==['CCC','BBB']
 assert ch(r,'sector_gainers')[0]['value']==pytest.approx(2.5)
 assert ch(r,'sector_gainers')[0]['eligible']==2 and ch(r,'sector_gainers')[0]['members']==2
 assert ch(r,'sector_losers')[0]['value']==-20
 assert sum(x['value'] for x in ch(r,'scrip_volume'))==230
 assert sum(x['value'] for x in ch(r,'sector_volume'))==230
 assert not r['partial'] and len(r['charts'])==8
 for c in r['charts']:
  assert len(c['rows'])<=10
  if c['unit']!='shares':assert 'OUT' not in [x['name'] for x in c['rows']]

def test_combo_is_daily_index_change_not_level_and_missing_is_gap(market_db):
 r=MarketPerformance(market_db).report('weekly','2026-W44');b=r['combo']['buckets']
 assert len(b)==5 and b[0]['index_change']==10 and b[4]['index_change']==40
 assert b[1]['index_change'] is None and b[1]['volume'] is None
 assert b[0]['volume']==35 and b[4]['volume']==195
 for x in b:
  if x['sectors']:assert sum(x['sectors'].values())==x['volume']
 assert 'Unmapped' in r['combo']['sectors']

def test_no_future_leak_and_daily_closed_date_falls_back(market_db):
 r=MarketPerformance(market_db).report('daily','2026-10-29')
 assert r['selected']=='2026-10-26' and r['requested']=='2026-10-29'
 assert r['index']['close']==1010 and r['combo'] is None
 assert r['cash_as_of']=='2026-10-26'
 assert len(r['charts'])==8
 with pytest.raises(ValueError):MarketPerformance(market_db).report('daily','2010-01-01')

@pytest.mark.parametrize('kind',['monthly','quarterly','halfyear','ninemonth','yearly'])
def test_all_long_periods_have_bounded_chart_buckets_and_valid_json(market_db,kind):
 r=MarketPerformance(market_db).report(kind)
 assert r['status']=='OK' and len(r['charts'])==8
 if kind!='monthly':assert r['partial']
 assert len(r['combo']['buckets'])<=31
 if kind=='monthly': assert len(r['combo']['buckets'])==5 # actual imported dates incl weekend outside weekly view
 elif kind=='quarterly': assert len(r['combo']['buckets'])==3
 elif kind=='halfyear':assert len(r['combo']['buckets'])==6
 elif kind=='ninemonth':assert len(r['combo']['buckets'])==9
 else:assert len(r['combo']['buckets'])==12
 json.dumps(r,allow_nan=False)

def test_missing_membership_never_uses_bundled_reference(market_db):
 with get_connection(market_db) as c:c.execute("DELETE FROM company_reference WHERE list_name='KSE100'")
 r=MarketPerformance(market_db).report('weekly')
 assert r['coverage']['members']==0 and ch(r,'scrip_volume')
 assert all(c['unavailable'] and not c['rows'] for c in r['charts'][2:])

def test_empty_zero_volume_and_unknown_keys(tmp_path):
 p=tmp_path/'empty.db';init_db(p);s=MarketPerformance(p)
 assert s.report()['status']=='NO_DATA'
 with get_connection(p) as c:c.execute("INSERT INTO equity_ohlcv(trade_date,symbol,close,volume) VALUES('2026-10-30','EMPTY',10,0)")
 r=s.report();assert r['coverage']['volume']==0 and not ch(r,'scrip_volume') and r['index']['change'] is None
 for kind,key in [('bad',None),('weekly','2026-W99'),('daily',"x' OR 1=1"),('daily','2026-02-30')]:
  with pytest.raises(ValueError):s.report(kind,key)

def test_top_ten_tie_order_and_other_volume_stack(market_db):
 with get_connection(market_db) as c:
  for n in range(15):
   sym=f'X{n:02}';c.execute('INSERT INTO company_reference(list_name,symbol,company,sector) VALUES(?,?,?,?)',('COMP_LIST',sym,sym,f'SECTOR {n}'))
   c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,close,volume) VALUES(?,?,?,?)',('2026-10-30',sym,10,100))
 r=MarketPerformance(market_db).report('weekly');leaders=ch(r,'scrip_volume')
 assert len(leaders)==10 and [x['name'] for x in leaders]==[f'X{n:02}' for n in range(10)]
 assert 'Other' in r['combo']['sectors']
 assert sum(x['volume'] or 0 for x in r['combo']['buckets'])==1730

def test_backend_read_only_and_single_batched_scan(market_db):
 with get_connection(market_db) as c:
  before=c.execute('SELECT COUNT(*) FROM equity_ohlcv').fetchone()[0]
  digest=[tuple(r) for r in c.execute("SELECT trade_date,symbol,close,volume FROM equity_ohlcv ORDER BY trade_date,symbol")]
 MarketPerformance(market_db).report('weekly')
 with get_connection(market_db) as c:
  assert before==c.execute('SELECT COUNT(*) FROM equity_ohlcv').fetchone()[0]
  assert digest==[tuple(r) for r in c.execute("SELECT trade_date,symbol,close,volume FROM equity_ohlcv ORDER BY trade_date,symbol")]
 source=(ROOT/'psx_app/services/market_performance.py').read_text()
 assert '@persisted_result' in source and 'WITH a AS' in source
 assert 'for r in rows:' in source and 'execute(' not in source[source.index('for r in rows:'):source.index('sector_returns=')]

def test_frontend_navigation_theme_race_guards_and_no_external_assets():
 js=(ROOT/'psx_app/static/performance1325.js').read_text();html=(ROOT/'psx_app/static/index.html').read_text();app=(ROOT/'psx_app/static/app.js').read_text()
 assert html.index('data-view="market"')<html.index('data-view="performance"')<html.index('data-view="settings"')
 assert 'performance1325.js?v=1.3.29' in html and 'renderPerformance1325(container)' in app
 for text in ['panelGet1322','currentViewRender','beginViewRender','prefers']:
  if text!='prefers':assert text in js
 assert 'https://' not in js and 'http://' not in js
 assert 'perfTabs1325' in js and "['yearly','Yearly']" in js
 assert 'ontoggle="perfData1325(this)"' in js and 'exportPerformance1325' in js
 css=(ROOT/'psx_app/static/styles.css').read_text().split('/* v1.3.25 —')[1]
 assert 'var(--separator-color)' in css and 'var(--pos-green)' in css and 'var(--neg-red)' in css
 assert 'prefers-reduced-motion' in css and '--text-primary' not in css
 subprocess.run(['node','--check',str(ROOT/'psx_app/static/performance1325.js')],check=True)

def test_endpoint_validation_and_imported_report(market_db,monkeypatch):
 import psx_app.upgrade_routes as routes
 monkeypatch.setattr(routes,'DB_PATH',market_db)
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 app=FastAPI();app.include_router(routes.router)
 with TestClient(app) as client:
  r=client.get('/api/v139/market-performance?period=weekly&key=2026-W44')
  assert r.status_code==200 and r.json()['index']['change']==50
  assert client.get('/api/v139/market-performance?period=invalid').status_code==422
  assert client.get('/api/v139/market-performance?key=bad').status_code==422
  assert client.get('/api/v139/market-performance?key='+'x'*40).status_code==422

def test_reference_list_normalization_and_sector_fallback(market_db):
 with get_connection(market_db) as c:
  c.execute("DELETE FROM company_reference WHERE list_name='COMP_LIST'")
  c.execute("UPDATE company_reference SET list_name='KSE 100'")
 r=MarketPerformance(market_db).report('weekly')
 assert r['coverage']['membership_source']=='KSE 100' and r['coverage']['eligible']==3
 assert ch(r,'sector_gainers')[0]['name']=='BANKS'
 assert 'Unmapped' in r['combo']['sectors']

def test_nonfinite_invalid_and_real_zero_changes():
 from psx_app.services.market_performance import change
 for last,base in [(float('inf'),100),(100,float('nan')),(0,10),(10,0),(1e308,1e-308)]:
  assert change(last,base)==(None,None)
 assert change(100,100)==(0,0)

def perf_node(expression,extra=''):
 source=(ROOT/'psx_app/static/performance1325.js').read_text()
 code='''const vm=require('node:vm');const context={state:{apiCache:{}},
 h:x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),
 fmtDate:x=>String(x??'—'),fmtNum:(x,d=2)=>x==null?'Not available':Number(x).toFixed(d),fmtInt:x=>String(x),fmtPct:x=>String(x)+'%',
 pnlClass:x=>x>0?'pos':x<0?'neg':'',number1321:x=>String(x),clearCalendarNotice1311:()=>{},enhanceWorkspace:()=>{},
 URLSearchParams,console};vm.createContext(context);'''
 code+='vm.runInContext('+json.dumps(source+'\n'+extra)+',context);console.log(JSON.stringify(vm.runInContext('+json.dumps(expression)+',context)));'
 return json.loads(subprocess.check_output(['node','-e',code],text=True))

def test_chart_accessibility_safe_names_and_zero_axis():
 chart={'rows':[{'name':'<script>"','value':-1.234}],'title':'Losers','tone':'neg','unit':'%','id':'test'}
 html=perf_node('perfChart1325('+json.dumps(chart)+')')
 assert '&lt;script&gt;&quot;' in html and '<script>' not in html
 assert 'tabindex="0" role="img"' in html and '-1.23%' in html
 assert perf_node('perfCompact1325(-0)')=='0'
 assert 'ontoggle="perfData1325(this)"' in html

def test_combo_line_breaks_missing_points_instead_of_zero():
 combo={'sectors':['<SECTOR>'],'volume_source':'Imported cash','buckets':[
  {'date':'2026-10-26','volume':10,'sectors':{'<SECTOR>':10},'index_change':10},
  {'date':'2026-10-27','volume':None,'sectors':None,'index_change':None},
  {'date':'2026-10-28','volume':0,'sectors':{'<SECTOR>':0},'index_change':-3}]}
 html=perf_node('perfCombo1325('+json.dumps(combo)+',"weekly")')
 import re
 path=re.search('class="performance-line1325" d="([^"]*)"',html)[1]
 assert path.count('M')==2 and 'L' not in path
 assert '&lt;SECTOR&gt;' in html and '<SECTOR>' not in html
 assert 'Missing observations are gaps' in html

def test_late_period_response_does_not_replace_new_selection():
 source=(ROOT/'psx_app/static/performance1325.js').read_text()
 script='''let state={apiCache:{}},count=0,waiters=[];
 const h=x=>String(x),beginViewRender=c=>c.ticket=++count,currentViewRender=(c,t)=>c.ticket===t,
 enhanceWorkspace=()=>{},panelGet1322=()=>new Promise(resolve=>waiters.push(resolve));
 '''+source+'''
 (async()=>{const box={innerHTML:''};state.performance.kind='daily';const a=renderPerformance1325(box);state.performance.kind='weekly';const b=renderPerformance1325(box);
 waiters[1]({status:'NO_DATA',kind:'weekly'});await b;waiters[0]({status:'NO_DATA',kind:'daily'});await a;
 console.log(JSON.stringify({kind:state.performance.report.kind,active:box.innerHTML.includes('aria-pressed="true" onclick="changePerformance1325(\'weekly\')"')}));})().catch(e=>{console.error(e);process.exit(1)});
 '''
 # Verify stale-response protection without browser or network timing assumptions.
 script=script.replace("active:box.innerHTML.includes('aria-pressed=\"true\" onclick=\"changePerformance1325('weekly')\"')", "active:box.innerHTML.includes('No eligible period available')")
 result=json.loads(subprocess.check_output(['node','-e',script],text=True))
 assert result=={'kind':'weekly','active':True}
