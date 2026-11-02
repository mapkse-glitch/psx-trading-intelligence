import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def frontend(expression):
 source=(ROOT/'psx_app/static/upgrade139.js').read_text()+'\n'+(ROOT/'psx_app/static/market1321.js').read_text()
 setup='''const vm=require('node:vm');const context={state:{technical:{}},VIEW_TITLES:{},
 escapeHtml:x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),
 fmtDate:x=>String(x),fmtNum:x=>x==null?'Not available':Number(x).toFixed(2),fmtInt:x=>String(x),fmtPct:x=>x==null?'Not available':Number(x).toFixed(2)+'%',pnlClass:x=>x>0?'pos':x<0?'neg':'',
 document:{addEventListener:()=>{},querySelectorAll:()=>[],getElementById:()=>null,body:{}},MutationObserver:class{observe(){}}};vm.createContext(context);'''
 code=setup+'vm.runInContext('+json.dumps(source)+',context);console.log(JSON.stringify(vm.runInContext('+json.dumps(expression)+',context)));'
 return json.loads(subprocess.check_output(['node','-e',code],text=True))
def test_four_ordered_market_tabs_and_six_heading_preserving_bars():
 html=frontend("marketTabs1321('matching')")
 assert html.index('Market volume')<html.index('Symbol vs Index')<html.index('Matching Rate')<html.index('Small Cards')
 assert html.count('aria-pressed="true"')==1
 js=(ROOT/'psx_app/static/upgrade139.js').read_text()
 assert '${rangeBar1321(x)}' in js and '<h3>${h(x.label)}</h3>' in js
 bar=frontend('rangeBar1321({high:110,low:90})')
 assert 'range-window-bar1321' in bar and 'indicator' not in bar and 'marker' not in bar
 assert 'High 110.00 at left to Low 90.00 at right' in bar
 assert 'range-window-empty1321' in frontend('rangeBar1321({high:null,low:null})')
def test_symbol_card_signs_session_headings_and_safe_names():
 card={'symbol':'<TEST>','company':'<img src=x>','trade_date':'2025-04-10','status':'OK','close':100,'change':-1,'pct':-1,'high':110,'low':90,'avg_price':101,'volume':0,'session_count':2,'session_first':'2025-04-09','session_high':111,'session_low':89,'week':{'change':2,'pct':2},'month':{'change':-2,'pct':-2}}
 html=frontend('smallSymbolCard1321('+json.dumps(card)+', {requested:14,index:null})')
 assert '<h3 class="neg">&lt;TEST&gt;</h3>' in html and '&lt;img src=x&gt;' in html
 for label in ['Latest close','DoD change','Latest high','Latest low','Average','Volume','Week to date','Month to date','Based on Selected Sessions (14)']:assert label in html
 assert '2 of 14 sessions available' in html
 assert html.count('small-metric1321')==11
 assert 'Current index' not in html
 index=frontend('smallIndexCards1322({requested:14,index:null})')
 assert 'Current index' in index and 'No imported index data' in index
 assert '<strong class="">0</strong>' in html  # real zero volume is not missing

def test_no_price_reference_symbol_still_has_one_card():
 html=frontend('smallSymbolCard1321({symbol:"EMPTY",company:"Authentic",status:"NO_DATA"},{requested:14,index:null})')
 assert html.count('<article ')==1 and 'No imported price records' in html
 assert 'Latest close' not in html

def test_assets_scoped_css_and_no_changed_cache_namespace():
 html=(ROOT/'psx_app/static/index.html').read_text();css=(ROOT/'psx_app/static/styles.css').read_text()
 assert '/market1321.js?v=1.3.26' in html
 assert '.sector-cards1321,.index-rail1322{display:flex;flex-wrap:nowrap;overflow-x:auto' in css
 assert '--pos-green: #03D815' in css and '--neg-red: #F63131' in css
 assert 'range-window-bar1321' in css and 'var(--pos-green)' in css and 'var(--neg-red)' in css
 assert "values,'1.3.17'" in (ROOT/'psx_app/services/result_cache.py').read_text()
