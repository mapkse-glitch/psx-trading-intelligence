"""UI polish and navigation changes retain report meaning and refresh isolation."""
import json,subprocess
from pathlib import Path
from test_v1321_frontend import frontend
from test_v1321_market_panels import panels_db
ROOT=Path(__file__).resolve().parents[1]
def node(s):return json.loads(subprocess.check_output(['node','-e',s],text=True))
def test_quote_units_correct_for_equity_and_index():
 args='{close:100,change:-1,pct:-1,trade_date:"2026-10-30"}'
 share=frontend("latestMarketCard1317('Latest Close',"+args+",'PRL')")
 index=frontend("latestMarketCard1317('Latest Index Close',"+args+",'Imported index')")
 assert 'PKR per share' in share and 'DoD Change (PKR)' in share
 assert 'Index points' in index and 'DoD Change (points)' in index and 'PKR' not in index
 assert 'latest-close1317 neg' in share and 'latest-close1317 neg' in index
 assert 'Not available' in frontend("latestMarketCard1317('Latest Index Close',null,'Imported index')")

def test_opaque_range_gradient_and_useful_reduced_motion_hover():
 s=(ROOT/'psx_app/static/styles.css').read_text()
 rule=s[s.index('.range-window-bar1321{'):s.index('.range-window-empty1321')]
 assert 'var(--pos-green) 0%,#D4C83F 50%,var(--neg-red) 100%' in rule
 assert 'var(--bg-card)' not in rule and 'color-mix' not in rule
 assert '@media(hover:hover) and (pointer:fine)' in s
 assert '.btn:not(:disabled):hover' in s
 assert '.quick-pill,select,input{transition:none!important}' in s
 assert '.matching-table1321 table.data-table th' in s and 'font-family:var(--font-sans);font-size:13px' in s

def test_average_rename_and_parallel_metadata_loading():
 s=(ROOT/'psx_app/static/market1321.js').read_text()
 assert "metric1321('Average'" in s and "metric1321('Source average'" not in s
 assert 'const [meta,prepared]=await Promise.all' in s
 assert 'candidate===m.match_symbol&&prepared?prepared:' in s
 u=(ROOT/'psx_app/static/upgrade139.js').read_text()
 assert "await panelGet1322('/api/v139/market/meta')" in u
 assert 'container.dataset.marketTab!==m.tab' in u

def api_source():
 s=(ROOT/'psx_app/static/app.js').read_text()
 return s[s.index('const apiFlights1323'):s.index('function clearClientCache()')]

def test_global_get_dedup_keeps_false_uncached_and_refresh_isolated():
 out=node('''const state={apiCache:{}};let calls=0;const databaseNotice1313=()=>{};
 const fetch=async()=>({ok:true,json:async()=>({call:++calls})});'''+api_source()+'''
 (async()=>{const first=await Promise.all([apiGet('/a',false),apiGet('/a',false)]);const once=calls;await apiGet('/a',false);const twice=calls;await apiGet('/a');await apiGet('/a');const cached=calls;state.apiCache={};await apiGet('/a');console.log(JSON.stringify({first,once,twice,cached,final:calls}));})().catch(e=>{console.error(e);process.exit(1)});''')
 assert out=={'first':[{'call':1},{'call':1}],'once':1,'twice':2,'cached':3,'final':4}

def test_late_old_get_cannot_poison_refreshed_cache():
 out=node('''const state={apiCache:{}};const resolvers=[];const databaseNotice1313=()=>{};
 const fetch=()=>new Promise(resolve=>resolvers.push(value=>resolve({ok:true,json:async()=>value})));'''+api_source()+'''
 (async()=>{const old=apiGet('/a');state.apiCache={};const fresh=apiGet('/a');resolvers[1]({new:true});await fresh;resolvers[0]({old:true});await old;console.log(JSON.stringify(state.apiCache['/a']));})().catch(e=>{console.error(e);process.exit(1)});''')
 assert out=={'new':True}

def test_failed_gets_are_not_retained():
 out=node('''const state={apiCache:{}};let calls=0;const databaseNotice1313=()=>{};
 const fetch=async()=>({ok:++calls>1,status:500,json:async()=>({detail:'synthetic failure'})});'''+api_source()+'''
 (async()=>{await Promise.allSettled([apiGet('/a'),apiGet('/a')]);await apiGet('/a');console.log(JSON.stringify({calls,cached:!!state.apiCache['/a']}));})().catch(e=>{console.error(e);process.exit(1)});''')
 assert out=={'calls':2,'cached':True}

def test_matching_optimized_query_equals_independent_reference(panels_db):
 from psx_app.services.market_panels import MarketPanels,month_before
 from psx_app.database.schema import get_connection
 service=MarketPanels(panels_db)
 with get_connection(panels_db) as c:
  rows=[dict(r) for r in c.execute("SELECT trade_date,close FROM equity_ohlcv WHERE symbol='AAA' ORDER BY trade_date DESC")]
 latest=rows[0];cutoff=month_before(latest['trade_date'])
 eligible=sorted([r for r in rows if r['trade_date']<cutoff],key=lambda r:(abs(r['close']-latest['close']),-int(r['trade_date'].replace('-',''))))[:10]
 actual=service.matching('AAA')['rows']
 assert [r['trade_date'] for r in actual]==[r['trade_date'] for r in eligible]
 assert [r['sessions_ago'] for r in actual]==[sum(x['trade_date']>r['trade_date'] for x in rows) for r in eligible]
 s=(ROOT/'psx_app/services/market_panels.py').read_text()
 matching=s[s.index('def matching('):s.index('def sectors(')]
 assert 'ROW_NUMBER()' not in matching and 'later.trade_date>n.trade_date' in matching

def test_panel_cache_has_a_response_count_cap():
 s=(ROOT/'psx_app/static/market1321.js').read_text();s=s[s.index('const panelCaches1322'):s.index('function number1321')]
 out=node('''const state={apiCache:{}};let calls=0;const apiGet=async()=>({call:++calls});'''+s+'''
 (async()=>{for(let i=0;i<60;i++)await panelGet1322('/'+i);const before=calls;await panelGet1322('/59');const warm=calls;await panelGet1322('/0');console.log(JSON.stringify({before,warm,final:calls}));})().catch(e=>{console.error(e);process.exit(1)});''')
 assert out=={'before':60,'warm':60,'final':61}
