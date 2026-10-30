"""Pure client-side rule/highlight checks: no production database or writes."""
import json
import subprocess
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]

def run_js(expression):
    source=(ROOT/'psx_app/static/upgrade139.js').read_text()
    script='''const vm=require('node:vm');const context={state:{technical:{}},VIEW_TITLES:{},
    escapeHtml:x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),
    fmtDate:x=>String(x),fmtNum:x=>Number(x).toFixed(2),fmtPct:x=>Number(x).toFixed(2)+'%',
    pnlClass:x=>x>0?'pos':x<0?'neg':''};vm.createContext(context);\n'''
    script+='vm.runInContext('+json.dumps(source)+',context);console.log(JSON.stringify(vm.runInContext('+json.dumps(expression)+',context)));'
    return json.loads(subprocess.check_output(['node','-e',script],text=True))

@pytest.mark.parametrize('previous,close,status,upper,lower',[
    (100,110,'UPPER',110,90),(100,90,'LOWER',110,90),(100,109.99,'WITHIN',110,90),
    (100,90.01,'WITHIN',110,90),(100,120,'UPPER',110,90),(100,80,'LOWER',110,90),
    (5,6,'UPPER',6,4),(5,4,'LOWER',6,4),(5,5.5,'WITHIN',6,4),
    (10,11,'UPPER',11,9),(10,9,'LOWER',11,9),(100,100,'WITHIN',110,90),
    (.5,1.5,'UPPER',1.5,-.5),(.5,0,'WITHIN',1.5,-.5)])
def test_thresholds_use_higher_upper_price_and_lower_lower_price(previous,close,status,upper,lower):
    r=run_js('priceLimit1318('+json.dumps({'pr_close':previous,'close':close})+')')
    assert r['status']==status and r['upper']==pytest.approx(upper) and r['lower']==pytest.approx(lower)

@pytest.mark.parametrize('row',[None,{}, {'close':100}, {'close':100,'pr_close':None},
    {'close':100,'pr_close':0},{'close':100,'pr_close':-1},{'close':None,'pr_close':100},
    {'close':-1,'pr_close':100},{'close':'110','pr_close':100},{'close':float('inf'),'pr_close':100}])
def test_missing_invalid_prices_never_claim_a_lock(row):
    r=run_js('priceLimit1318('+json.dumps(row)+')')
    assert r['status']=='UNAVAILABLE' and r['upper'] is None and r['lower'] is None

def test_locked_card_is_explicitly_dated_close_based_and_escaped():
    r=run_js("({upper:priceLimitCard1318({close:110,pr_close:100,trade_date:'2026-10-30'},'<TEST>'),lower:priceLimitCard1318({close:90,pr_close:100},'TEST'),within:priceLimitCard1318({close:100,pr_close:100},'TEST'),missing:priceLimitCard1318(null,'TEST')})")
    assert 'limit-upper1318' in r['upper'] and 'Upper lock reached' in r['upper']
    assert 'limit-lower1318' in r['lower'] and 'Lower lock reached' in r['lower']
    assert '&lt;TEST&gt;' in r['upper'] and '2026-10-30' in r['upper']
    assert 'not an exchange-confirmed trading halt' not in r['upper']
    assert 'price-range-track1319' in r['upper']
    assert 'Within range' in r['within'] and 'Check unavailable' in r['missing']
    assert 'stroke="currentColor"' in r['upper'] and 'aria-hidden="true"' in r['upper']

def test_all_tied_high_and_low_rows_and_dual_extrema_are_marked():
    records=[{'high':114.5,'low':80},{'high':114.5,'low':74.74},{'high':100,'low':74.74},{'high':None,'low':None}]
    flags=run_js('tableRowFlags1318('+json.dumps(records)+')')
    assert flags==[{'maxHigh':True,'minLow':False},{'maxHigh':True,'minLow':True},{'maxHigh':False,'minLow':True},{'maxHigh':False,'minLow':False}]
    html=run_js("marketRecordsTable1318(['Date','High','Low'],[['A',114.5,80],['B',114.5,74.74],['C',100,74.74],['D','NA','NA']],"+json.dumps(records)+')')
    assert html.count('class="extrema-row1318')==3
    assert html.count('extreme-high-cell1318')==2 and html.count('extreme-low-cell1318')==2
    assert 'Max high</span>' not in html and 'Min low</span>' not in html
    assert 'row-max-high1318 row-min-low1318' in html

def test_extrema_are_local_to_each_displayed_table_not_other_symbol_or_index():
    r=run_js("({symbol:tableRowFlags1318([{high:100,low:10},{high:90,low:5}]),index:tableRowFlags1318([{high:10000,low:9000},{high:11000,low:9500}]),single:tableRowFlags1318([{high:7,low:3}]),none:tableRowFlags1318([]),zero:tableRowFlags1318([{high:0,low:0}])})")
    assert r['symbol']==[{'maxHigh':True,'minLow':False},{'maxHigh':False,'minLow':True}]
    assert r['index']==[{'maxHigh':False,'minLow':True},{'maxHigh':True,'minLow':False}]
    assert r['single']==r['zero']==[{'maxHigh':True,'minLow':True}]
    assert r['none']==[]

def test_other_small_tables_do_not_acquire_market_highlights():
    html=run_js("smallTable(['Stock','High','Low'],[['TEST',10,5]])")
    assert 'extrema-row' not in html and 'Max high' not in html
    assert '<th class="num">High</th>' in html and '<tr>' in html

def test_three_card_grid_highlight_theme_and_cached_api_unchanged():
    js=(ROOT/'psx_app/static/upgrade139.js').read_text();css=(ROOT/'psx_app/static/styles.css').read_text()
    assert "${priceLimitCard1318(r.latest_symbol,m.symbol)}" in js
    assert 'latest-market1317 latest-market1318' in js
    assert '.latest-market1318{grid-template-columns:repeat(3,minmax(0,1fr))' in css
    assert '@media(max-width:1050px){.latest-market1318{grid-template-columns:1fr}' in css
    assert ':root[data-theme="dark"]{--limit-up1318:' in css
    assert 'tr.row-max-high1318.row-min-low1318' in css and 'extreme-high-cell1318' in css
    assert 'background:var(--extreme-row-bg1318)!important' in css
    # This feature is presentational and must not invalidate old API results or add DB work.
    assert "values,'1.3.17'" in (ROOT/'psx_app/services/result_cache.py').read_text()
