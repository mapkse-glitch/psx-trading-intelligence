"""Display-only layout, color and hover regressions."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[1]

def insight_js(expression):
 source=(ROOT/'psx_app/static/insights1328.js').read_text()
 setup='''const vm=require('node:vm');const c={h:x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),fmtNum:x=>x==null?'Not available':Number(x).toFixed(2),fmtInt:x=>String(x),fmtPct:x=>x==null?'Not available':String(x)+'%',fmtDate:x=>String(x??'—'),pnlClass:x=>x>0?'pos':x<0?'neg':''};vm.createContext(c);'''
 code=setup+'vm.runInContext('+json.dumps(source)+',c);console.log(JSON.stringify(vm.runInContext('+json.dumps(expression)+',c)));'
 return json.loads(subprocess.check_output(['node','-e',code],text=True))

def test_comparison_close_colors_follow_card_and_daily_change():
 # Both symbol and index use this same renderer; daily movement, not nominal positive price.
 data={'anchor':{'trade_date':'2026-02-27','high':210,'low':200,'close':205},'latest':{'trade_date':'2026-11-06','high':203,'close':200,'pr_close':210},'after':{'count':1,'metrics':{k:{'value':value,'date':'2026-11-06','ties':1} for k,value in [('max_high',220),('max_close',215),('min_low',190),('min_close',195)]}},**{k:{'value':0,'pct':0} for k in ['max_high_vs_anchor','max_close_vs_anchor','min_low_vs_anchor','min_close_vs_anchor','current_high_vs_anchor','current_close_vs_anchor','current_high_vs_max','current_close_vs_max']}}
 html=insight_js('insightCompare1328("Symbol",'+json.dumps(data)+',"PKR")')
 import re
 cards=re.findall(r'<article class="card insight-compare-card1328">(.*?)</article>',html)
 assert len(cards)==4
 assert 'Close on 27 Feb 2026</span><strong class="pos">205.00' in cards[0]
 assert 'Close on 27 Feb 2026</span><strong class="neg">205.00' in cards[1]
 for card in cards[2:]: assert 'Current close</span><strong class="neg">200.00' in card
 data['latest']['pr_close']=190
 html=insight_js('insightCompare1328("Index",'+json.dumps(data)+',"points")')
 assert html.count('Current close</span><strong class="pos">200.00')==2
 data['latest']['pr_close']=None
 html=insight_js('insightCompare1328("Index",'+json.dumps(data)+',"points")')
 assert html.count('Current close</span><strong class="">200.00')==2

def test_lock_order_single_rows_search_and_tooltip_assets():
 js=(ROOT/'psx_app/static/upgrade139.js').read_text();ins=(ROOT/'psx_app/static/insights1328.js').read_text();css=(ROOT/'psx_app/static/styles.css').read_text();idx=(ROOT/'psx_app/static/index.html').read_text()
 assert "'Change %','Lock','Volume'" in js and 'priceLockCell1328(x)' in js
 assert 'Upper cap' not in ins and 'Lower cap' not in ins and "insightMetric1328('Lock',priceLockCell1328(l)" in ins
 assert 'insight-strip1329' in ins and 'repeat(8,minmax(122px,1fr))' in css
 assert 'select-search-group1329' in (ROOT/'psx_app/static/search1327.js').read_text()
 assert 'charttips1329.js?v=1.3.32' in idx
 for name in ['insights1328.js','search1327.js','charttips1329.js','app.js','upgrade139.js']:
  subprocess.run(['node','--check',str(ROOT/'psx_app/static'/name)],check=True)
