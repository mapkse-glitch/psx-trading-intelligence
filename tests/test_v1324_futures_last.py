"""Last imported snapshot, exact cash joins and per-contract calendar horizons."""
from datetime import date,timedelta
from contextlib import contextmanager
import json,subprocess
from pathlib import Path
import pytest
from psx_app.database.schema import init_db,get_connection
from psx_app.services.futures_service import FuturesService,contract_last_friday
ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('anchor,month,expected,days',[
 ('2026-10-16','OCT','2026-10-30',14),('2026-10-16','OCTB','2026-10-30',14),
 ('2026-10-16','NOV','2026-11-27',42),('2026-10-16','DEC','2026-12-25',70),
 ('2026-12-16','JAN','2027-01-29',44),('2026-12-16','FEB','2027-02-26',72),
 ('2024-02-01','FEB24','2024-02-23',22),('2025-01-01','JAN2025','2025-01-31',30),
 ('2026-10-30','OCT','2026-10-30',0),('2026-10-31','OCT','2026-10-30',0),
 ('2026-10-16','SEP2026','2026-09-25',0),('2026-10-16','JAN27B','2027-01-29',105),
 ('2026-10-16','NOVB2026','2026-11-27',42),('2026-10-16','NOV-2026','2026-11-27',42),
])
def test_calendar_days_to_requested_last_friday(anchor,month,expected,days):
 r=contract_last_friday(month,anchor)
 assert r['rule_date']==expected and r['days']==days
 assert date.fromisoformat(r['rule_date']).weekday()==4
 assert (date.fromisoformat(r['rule_date'])+timedelta(days=7)).month!=date.fromisoformat(r['rule_date']).month

@pytest.mark.parametrize('month',['UNKNOWN','',None,'NOV123','DEC0000','JAX','2027-01'])
def test_unknown_month_year_never_uses_thirty_day_fallback(month):
 r=contract_last_friday(month,'2026-10-16')
 assert r['rule_date'] is None and r['days'] is None

def seed(c):
 c.executemany('INSERT INTO equity_ohlcv(trade_date,symbol,close,volume) VALUES (?,?,?,?)',[
  ('2026-10-16','AAA',100,1200),('2026-10-16','ZZZ',50,0),
  ('2026-10-15','MISSING',70,999),('2026-10-17','AAA',999,999999)])
 c.executemany('INSERT INTO futures_ohlcv(trade_date,contract_symbol,base_symbol,contract_month,close,volume,high,low) VALUES (?,?,?,?,?,?,?,?)',[
  ('2026-10-16','ZZZ-DEC','ZZZ','DEC',45,30,48,44),
  ('2026-10-16','AAA-NOV','AAA','NOV',110,200,112,108),
  ('2026-10-16','AAA-OCTB','AAA','OCTB',101,0,103,99),
  ('2026-10-16','MISSING-NOV','MISSING','NOV',72,10,73,71),
  ('2026-10-16','AAA-UNKNOWN','AAA','UNKNOWN',102,15,104,100),
  ('2026-10-15','OLD-OCT','OLD','OCT',25,3,27,24)])

@pytest.fixture
def last_db(tmp_path):
 p=tmp_path/'last.db';init_db(p)
 with get_connection(p) as c:seed(c)
 return p

def test_latest_futures_only_alphabetic_contract_rows_and_exact_cash(last_db):
 r=FuturesService(last_db).get_last_data()
 assert r['latest_date']=='2026-10-16' and r['rows_count']==5
 assert [x['symbol'] for x in r['rows']]==['AAA','AAA','AAA','MISSING','ZZZ']
 assert [x['contract'] for x in r['rows'][:3]]==['OCTB','NOV','UNKNOWN']
 assert all(x['trade_date']=='2026-10-16' for x in r['rows'])
 aaa=r['rows'][0];assert aaa['current_value']==100 and aaa['current_volume']==1200 and aaa['future_volume']==0
 missing=next(x for x in r['rows'] if x['symbol']=='MISSING')
 assert missing['current_value'] is None and missing['current_volume'] is None and missing['annualized_pct'] is None
 assert r['missing_same_date_spot_count']==1
 assert r['rows'][-1]['current_volume']==0

def test_ann_uses_each_contract_days_and_actual_source_volumes(last_db):
 rows={x['contract_symbol']:x for x in FuturesService(last_db).get_last_data()['rows']}
 for name,days,diff,pct in [('AAA-OCTB',14,1,1),('AAA-NOV',42,10,10),('ZZZ-DEC',70,-5,-10)]:
  row=rows[name];assert row['days']==days and row['difference']==diff
  assert row['difference_pct']==pytest.approx(pct)
  assert row['annualized_pct']==pytest.approx(pct*365/days)
 assert rows['AAA-NOV']['current_volume']==1200 and rows['AAA-NOV']['future_volume']==200
 assert rows['AAA-NOV']['high']==112 and rows['AAA-NOV']['low']==108
 assert rows['AAA-UNKNOWN']['difference']==2 and rows['AAA-UNKNOWN']['days'] is None and rows['AAA-UNKNOWN']['annualized_pct'] is None

def test_rule_day_expired_and_nonpositive_cash_not_annualized(last_db):
 with get_connection(last_db) as c:
  c.execute("INSERT INTO equity_ohlcv(trade_date,symbol,close,volume) VALUES ('2026-10-30','AAA',0,0)")
  c.execute("INSERT INTO futures_ohlcv(trade_date,contract_symbol,base_symbol,contract_month,close) VALUES ('2026-10-30','AAA-OCT','AAA','OCT',100)")
 r=FuturesService(last_db).get_last_data()['rows'][0]
 assert r['days']==0 and r['days_status']=='RULE_DAY' and r['annualized_pct'] is None
 assert r['current_value']==0 and r['difference'] is None
 with get_connection(last_db) as c:
  c.execute("UPDATE equity_ohlcv SET trade_date='2026-10-31',close=100 WHERE trade_date='2026-10-30'")
  c.execute("UPDATE futures_ohlcv SET trade_date='2026-10-31' WHERE trade_date='2026-10-30'")
 r=FuturesService(last_db).get_last_data()['rows'][0]
 assert r['days_status']=='EXPIRED' and r['days']==0 and r['annualized_pct'] is None and r['difference']==0

def test_empty_snapshot_is_explicit(tmp_path):
 p=tmp_path/'empty.db';init_db(p);r=FuturesService(p).get_last_data()
 assert r['latest_date'] is None and r['rows']==[] and r['rows_count']==0

def test_new_date_is_picked_without_a_pin_or_clock_dependency(last_db):
 svc=FuturesService(last_db);assert svc.get_last_data()['latest_date']=='2026-10-16'
 with get_connection(last_db) as c:
  c.execute("INSERT INTO futures_ohlcv(trade_date,contract_symbol,base_symbol,contract_month,close) VALUES ('2026-11-02','NEW-NOV','NEW','NOV',10)")
 r=svc.get_last_data();assert r['latest_date']=='2026-11-02' and len(r['rows'])==1 and r['rows'][0]['days']==25

def test_single_bounded_latest_date_join_not_metadata_or_n_plus_one(last_db,monkeypatch):
 import psx_app.services.futures_service as module
 calls=[];original=module.get_connection
 @contextmanager
 def traced(path=None):
  with original(path) as conn:
   class Proxy:
    def execute(self,sql,*args):calls.append(sql);return conn.execute(sql,*args)
   yield Proxy()
 monkeypatch.setattr(module,'get_connection',traced)
 monkeypatch.setattr(FuturesService,'get_metadata',lambda *a,**k:pytest.fail('Last Data must skip metadata'))
 r=FuturesService(last_db).get_last_data();assert len(r['rows'])==5
 assert len(calls)==1 and 'MAX(trade_date)' in calls[0] and 'e.trade_date=f.trade_date' in calls[0]

def front(expression):
 s=(ROOT/'psx_app/static/app.js').read_text();a=s.index('function futuresTabs1324');b=s.index('async function renderFuturesView',a)
 code='const vm=require("node:vm");const ctx={escapeHtml:x=>String(x??"").replaceAll("<","&lt;"),fmtDate:x=>x||"—",fmtNum:x=>x==null?"Not available":Number(x).toFixed(2),fmtPct:x=>x==null?"Not available":Number(x).toFixed(2)+"%",fmtInt:x=>x==null?"Not available":String(x),pnlClass:x=>x>0?"pos":x<0?"neg":""};vm.createContext(ctx);vm.runInContext('+json.dumps(s[a:b])+',ctx);console.log(JSON.stringify(vm.runInContext('+json.dumps(expression)+',ctx)));'
 return json.loads(subprocess.check_output(['node','-e',code],text=True))

def test_tabs_order_no_retention_tab_and_twelve_columns(last_db):
 nav=front("futuresTabs1324('last_data')")
 assert '2-Month Rolling Retention' not in nav and nav.index('Date Summary')<nav.index('Last Data')
 assert nav.count('aria-pressed="true"')==1 and nav.count('<button')==8
 html=front('lastFuturesData1324('+json.dumps(FuturesService(last_db).get_last_data())+')')
 assert html.count('<th')==13 # thead plus twelve th cells
 for x in ['Current Value','Volume','Future Value','Future Volume','Annualized %','Same-date cash matches']:assert x in html
 assert '2026-10-16' in html and 'last-data-table1324' in html
 js=(ROOT/'psx_app/static/app.js').read_text()
 assert js.index("if(f.subtab==='last_data')")<js.index('const meta = await apiGet(`/api/futures/metadata')
 assert "apiGet('/api/futures/last-data',false)" in js
 assert '2-Month Rolling Retention' not in js and '2-Month Rolling Data Retention Policy Preview' not in js

def test_zero_spread_is_a_real_zero_not_unavailable(last_db):
 with get_connection(last_db) as c:c.execute("UPDATE futures_ohlcv SET close=100 WHERE contract_symbol='AAA-NOV'")
 row=next(x for x in FuturesService(last_db).get_last_data()['rows'] if x['contract_symbol']=='AAA-NOV')
 assert row['difference']==0 and row['difference_pct']==0 and row['annualized_pct']==0 and row['days']==42
