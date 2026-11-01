"""Display-only corrections, bounded fetch cache and shared index rendering."""
import json,subprocess
from pathlib import Path
from test_v1321_frontend import frontend
ROOT=Path(__file__).resolve().parents[1]
def node(source):return json.loads(subprocess.check_output(['node','-e',source],text=True))
def test_universal_display_dates_validate_and_preserve_time_zone():
 s=(ROOT/'psx_app/static/app.js').read_text();s=s[s.index('function fmtDate('):s.index('function escapeHtml(')]
 out=node(s+'''console.log(JSON.stringify(['2019-09-06','06-09-2019','2024-02-29','2025-02-29','2026-10-30T22:30:00Z',null,'raw'].map(fmtDate)));''')
 assert out==['6 Sept 2019','6 Sept 2019','29 Feb 2024','2025-02-29','31 Oct 2026 03:30 PKT','—','raw']
def test_endpoint_labels_are_above_bar_without_old_duplicate_rows():
 html=frontend('rangeBar1321({high:110,low:90})')
 assert html.index('High')<html.index('110.00')<html.index('Low')<html.index('90.00')<html.index('range-window-bar1321')
 assert 'marker' not in html
 s=(ROOT/'psx_app/static/upgrade139.js').read_text()
 assert '<h3>${h(x.label)}</h3>${rangeBar1321(x)}' in s
 assert '<div><span>High</span><strong class="pos">${x.high' not in s

def test_shared_index_high_low_semantics_ignore_negative_direction():
 report={'requested':7,'index':{'latest':{'close':100,'high':110,'low':90,'change':-1,'pct':-1,'trade_date':'2026-10-30'},'window':{'high':120,'low':80,'change':2,'pct':2,'count':7,'first':'2026-10-22','last':'2026-10-30'}}}
 html=frontend('smallIndexCards1322('+json.dumps(report)+')')
 assert html.count('<article ')==2
 for label,value,tone in [('High','110.00','pos'),('Low','90.00','neg'),('High','120.00','pos'),('Low','80.00','neg')]:
  assert f'<span>{label}</span><strong class="{tone}">{value}</strong>' in html

def test_semantic_range_headers_do_not_override_changes_or_combined_labels():
 s=(ROOT/'psx_app/static/display1311.js').read_text();s=s[s.index('function semanticRangeTone1322'):s.index('function markRangeTone1322')]
 assert node(s+'''console.log(JSON.stringify(['High','Session low','Low change (%)','High / Low','Highlight','Close'].map(semanticRangeTone1322)))''')==['pos','neg','neg','','','']

def test_fetch_cache_deduplicates_expires_and_respects_refresh_scope():
 s=(ROOT/'psx_app/static/market1321.js').read_text();s=s[s.index('const panelCaches1322'):s.index('function number1321')]
 out=node('''let calls=0,now=0;Date.now=()=>now;const state={apiCache:{}};
 const apiGet=async()=>({n:++calls});'''+s+'''
 (async()=>{const first=await Promise.all([panelGet1322('/a'),panelGet1322('/a')]);await panelGet1322('/a');const warm=calls;now=30001;await panelGet1322('/a');const expired=calls;state.apiCache={};await panelGet1322('/a');console.log(JSON.stringify({first,warm,expired,calls}));})().catch(e=>{console.error(e);process.exit(1)});''')
 assert out=={'first':[{'n':1},{'n':1}],'warm':1,'expired':2,'calls':3}

def test_small_cards_single_report_fetch_and_bounded_sql():
 s=(ROOT/'psx_app/static/market1321.js').read_text()
 assert "api/v139/market/selected-sectors" not in s
 assert "const meta={sectors:r.sectors||[],source:r.source}" in s
 sql=(ROOT/'psx_app/services/market_panels.py').read_text()
 assert 'ORDER BY trade_date DESC LIMIT ?) AS limited) AS ranked' in sql
 assert 'range(0,len(members),50)' in sql
 assert 'def small_cards_v1322' in sql

def test_default_sector_one_response(panels_db):
 from psx_app.services.market_panels import MarketPanels
 r=MarketPanels(panels_db).small_cards(None,7)
 assert r['sector']=='CEMENT' and len(r['sectors'])==2
 assert len(r['cards'])==3 and r['requested']==7

from test_v1321_market_panels import panels_db
