"""The real technical renderer must initialize without Market Explorer state."""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def test_technical_initial_render_and_all_tabs():
    source = (ROOT / 'psx_app/static/upgrade139.js').read_text()
    script = r'''
const vm=require('node:vm'), assert=require('node:assert');
const context={
 state:{technical:{},ideas:{scope_or_sector:'all',direction:'all',query:''},analyst:{symbol:'TEST',action:'hold'}},
 VIEW_TITLES:{},escapeHtml:x=>String(x??''),URLSearchParams,
 beginViewRender:()=>1,currentViewRender:()=>true,enhanceWorkspace:()=>{},
 buildTradingIdeasCardHtml:()=>'IDEAS CONTENT',scanDiagnostics140:()=>'',
 coveragePanel140:()=>'<section>DIAGNOSTICS CONTENT</section>',filterCoverage140:()=>{},
 apiGet:async url=>url.includes('trading-ideas')?{setups:[]}:url.includes('filters')?{}:url.includes('coverage')?{}:url.includes('automated-analyst')?{status:'INSUFFICIENT_DATA',message:'Not enough records'}:url.includes('contract')?{}:url.includes('forecasts')?{items:[],note:''}:{},
 fmtDate:x=>String(x??''),fmtNum:x=>String(x??''),fmtInt:x=>String(x??''),fmtPct:x=>String(x??''),pnlClass:()=>'',
 renderTechnicalLegacy:async c=>{c.innerHTML='<div class="subtabs"></div>LEGACY CONTENT';},
 document:{getElementById:()=>null},
};
vm.createContext(context); vm.runInContext(SOURCE,context);
vm.runInContext("scanDiagnostics140=()=>''; coveragePanel140=()=>'<section>DIAGNOSTICS CONTENT</section>'; filterCoverage140=()=>{};",context);
const c={innerHTML:'<p class="loading">Loading workspace…</p>',dataset:{},isConnected:true,
 setAttribute(){},removeAttribute(){},classList:{add(){},remove(){}},
 querySelector(s){if(s==='.card')return this.innerHTML.includes('class="card')?{}:null;if(s==='.subtabs')return {set outerHTML(value){c.innerHTML=value+'LEGACY CONTENT'}};return null;}};
(async()=>{
 for(const [tab,expected] of [['ideas','IDEAS CONTENT'],['analyst','Price history is too short'],['forecasts','Saved predictions & results'],['coverage','DIAGNOSTICS CONTENT'],['core36','LEGACY CONTENT'],['deep_dive','LEGACY CONTENT']]){
  context.state.technical.subtab=tab; await context.renderTechnicalView(c);
  assert(c.innerHTML.includes(expected),tab+' failed: '+c.innerHTML);
  assert(c.innerHTML.includes('Trading Ideas Generator'),tab+' missing navigation');
  assert(!c.innerHTML.includes('Market Explorer pages'),tab+' used market navigation');
 }
 assert(!('marketTab' in c.dataset),'technical view used market-tab state');
 console.log('technical renderer: all six paths passed');
})().catch(e=>{console.error(e.stack);process.exit(1)});
'''.replace('SOURCE',json.dumps(source))
    result = subprocess.run(['node','-e',script], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert 'all six paths passed' in result.stdout
