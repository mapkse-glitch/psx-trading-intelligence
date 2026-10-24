/* v1.3.9: accountable analysis and native market explorer. No external chart/CDN/API. */
state.technical.subtab='ideas';
state.market={tab:'volume',date:null,n:10,symbol:'PRL',days:50};
VIEW_TITLES.market='09 • Market Explorer — Volume & Symbol vs Index';
let analystTimer, analystGeneration=0, ideasGeneration=0;
const h=escapeHtml;
async function post139(path,data) {
 const res=await fetch('/api/v139/'+path,{method:'POST',headers:data instanceof FormData?{}:{'Content-Type':'application/json'},body:data instanceof FormData?data:JSON.stringify(data||{})});
 const out=await res.json();if(!res.ok)throw new Error(out.detail||'Request not confirmed');return out;
}
function smallTable(headers,rows){
 const numeric=headers.map(v=>/^(Rule score|Volume|Share|Cash sessions|Engine sessions|Symbol rows|Added\/changed|High|Low|Average|Close|Change|Net return|Test samples|Model accuracy|Baseline accuracy|Model Brier|Baseline Brier)/.test(v));
 const wrap=headers.map(v=>/Reason|Evidence|Decision|Accounts|Reference lists|Sector/.test(v));
 const cls=i=>[numeric[i]?'num':'',wrap[i]?'cell-wrap':''].filter(Boolean).join(' ');
 return `<div class="table-wrap"><table class="data-table"><thead><tr>${headers.map((v,i)=>`<th class="${cls(i)}">${h(v)}</th>`).join('')}</tr></thead><tbody>${rows.length?rows.map(row=>`<tr>${row.map((v,i)=>`<td class="${cls(i)}">${v}</td>`).join('')}</tr>`).join(''):`<tr><td colspan="${headers.length}">No matching data.</td></tr>`}</tbody></table></div>`;
}
function techNav139(tab){return `<div class="subtabs">${[['ideas','1. Trading Ideas Generator'],['analyst','2. Automated Technical Analyst'],['forecasts','Forecasts & Results'],['coverage','Data coverage & exclusions'],['core36','Core 36 watchlist'],['deep_dive','Detailed chart & historical audit'],['all531','All-symbol screener']].map(([id,label])=>`<button class="subtab-btn ${tab===id?'active':''}" onclick="state.technical.subtab='${id}';renderTechnicalView(document.getElementById('viewContainer')).catch(e=>showToast(e.message,true))">${label}</button>`).join('')}</div>`;}
function skeleton139(){return '<div class="card loading139" role="status"><span></span><span></span><span></span><p>Analysing imported data…</p></div>';}
function contractCard139(result){
 const p=result.contract,lat=result.latest;
 return `<section class="card"><h3>Decision & execution conditions — ${h(lat.symbol)}</h3><div class="grid-4"><div class="kpi-box"><div class="kpi-label">Opening decision</div><div class="kpi-value ${p.status==='CONDITIONAL'?'pos':'neg'}">${p.status==='CONDITIONAL'?'CONDITIONAL '+(p.side==='LONG'?'BUY':'SHORT CANDIDATE'):'NO OPENING TRADE'}</div><p>${h(p.reason)}</p></div><div class="kpi-box"><b>Next-session entry band</b><p>${fmtNum(p.entry_low)} – ${fmtNum(p.entry_high)} PKR</p><p>${h(p.entry_rule)}</p></div><div class="kpi-box"><b>Recorded levels</b><p>SL ${fmtNum(p.stop)} · T1 ${fmtNum(p.target_1)} · T2 ${fmtNum(p.target_2)}</p><p>Gross R/R ${fmtNum(p.gross_rr)} · Net reference R/R ${fmtNum(p.net_rr)}</p><small>10 bps fee + 10 bps slippage each side; illustrative.</small></div><div class="kpi-box"><b>Validity & fundamentals</b><p>${h(p.expiry)}</p><p>${h(p.fundamentals)}</p></div></div><details open><summary>When NOT to enter</summary><ul>${p.avoid.map(x=>`<li>${h(x)}</li>`).join('')}</ul></details><p>Reference levels are not executable quotes. No order is placed. Short scenarios are hypothetical until broker/instrument eligibility is independently confirmed.</p><p id="forecastSave139" role="status">Saving immutable as-of forecast…</p></section>${levelsChart139(result)}`;
}
function levelsChart139(res){
 const bars=res.series||[];if(bars.length<2)return '';
 const p=res.contract, vals=bars.map(r=>Number(r.close)).filter(Number.isFinite),levels=[['Entry',p.reference_entry,'#38bdf8'],['Stop',p.stop,'#f87171'],['T1',p.target_1,'#34d399'],['T2',p.target_2,'#a3e635']].filter(r=>Number.isFinite(r[1]));
 let lo=Math.min(...vals,...levels.map(r=>r[1])),hi=Math.max(...vals,...levels.map(r=>r[1]));const pad=(hi-lo)*.08||1;lo-=pad;hi+=pad;
 const y=v=>250-(v-lo)/(hi-lo)*220,x=i=>65+i/(bars.length-1)*710;
 const path=bars.map((b,i)=>`${i?'L':'M'}${x(i).toFixed(1)},${y(b.close).toFixed(1)}`).join(' ');
 return `<section class="card"><h3>Close & recorded execution levels</h3><p>Last ${bars.length} sessions; levels are current as-of references, not historical levels.</p><svg class="market-svg" viewBox="0 0 980 290" role="img" aria-label="Close price with entry, stop and targets"><rect width="980" height="290" fill="#080e1b"/>${[0,.25,.5,.75,1].map(v=>`<text x="4" y="${y(lo+(hi-lo)*v)}" fill="#cbd5e1" font-size="12">${fmtNum(lo+(hi-lo)*v)}</text>`).join('')}<path d="${path}" fill="none" stroke="#38bdf8" stroke-width="2"/>${levels.map(([label,v,color],i)=>`<line x1="65" x2="785" y1="${y(v)}" y2="${y(v)}" stroke="${color}" stroke-dasharray="5 4"/><text x="795" y="${28+i*24}" fill="${color}" font-size="14">${label}: ${fmtNum(v)}</text>`).join('')}<text x="65" y="280" fill="#cbd5e1" font-size="12">${fmtDate(bars[0].trade_date)}</text><text x="680" y="280" fill="#cbd5e1" font-size="12">${fmtDate(bars.at(-1).trade_date)}</text></svg></section>`;
}
async function saveForecast139(symbol){
 try {const r=await post139('forecasts/record',{symbol});const el=document.getElementById('forecastSave139');if(el&&state.analyst.symbol===symbol)el.textContent=`Forecast saved for data as of ${fmtDate(r.as_of)} — next-session and 10-session horizons. Existing snapshots are not overwritten.`;}
 catch(e){const el=document.getElementById('forecastSave139');if(el)el.textContent='Forecast NOT confirmed saved: '+e.message;}
}
async function renderTechnicalView(container){
 const tab=state.technical.subtab;
 if(!['ideas','analyst','forecasts','coverage','ideas_and_analyst'].includes(tab)){await renderTechnicalLegacy(container);if(container.isConnected){const nav=container.querySelector('.subtabs');if(nav)nav.outerHTML=techNav139(tab);}return;}
 const ticket=beginViewRender(container);container.setAttribute('aria-busy','true');
 if(!container.querySelector('.card'))container.innerHTML=techNav139(tab)+skeleton139();
 else container.classList.add('refreshing139');
 try {
 let body='';
 if(tab==='ideas'||tab==='ideas_and_analyst'){
   const gen=++ideasGeneration;const qs=new URLSearchParams({scope_or_sector:state.ideas.scope_or_sector,direction:state.ideas.direction,query:state.ideas.query,limit:5});
   const [r,meta]=await Promise.all([apiGet('/api/intelligence/trading-ideas?'+qs,false),apiGet('/api/intelligence/filters',false)]);
   if(gen!==ideasGeneration)return;
   body=buildTradingIdeasCardHtml(r,meta)+scanDiagnostics140(r);
   if(r.setups?.length){body+=`<section class="card"><h3>Entry timing & saved forecasts</h3><p>Conditional next-session OPEN within ±0.25% of the reference entry, subject to actual-fill gross R/R ≥ 1.5 and positive net reward. Entry expires after that session; swing horizon is at most 10 sessions. Short eligibility is unverified. Fundamentals unavailable.</p><p id="ideaSave139">Saving forecasts for the displayed candidates…</p></section>`;}
   if(!currentViewRender(container,ticket))return;
   container.innerHTML=techNav139('ideas')+body;
   // Candidate snapshots are saved only after the displayed scan is accepted as current.
   if(r.setups?.length)Promise.allSettled(r.setups.map(x=>post139('forecasts/record',{symbol:x.symbol}))).then(results=>{const el=document.getElementById('ideaSave139');if(el)el.textContent=`Forecast saves confirmed: ${results.filter(x=>x.status==='fulfilled').length}/${results.length}. ${results.some(x=>x.status==='rejected')?'Open Forecasts & Results to verify; failed saves are not claimed successful.':''}`;});
 } else if(tab==='coverage'){
   const r=await apiGet('/api/v139/coverage',false);
   if(!currentViewRender(container,ticket))return;
   coverage140=r;
   container.innerHTML=techNav139(tab)+coveragePanel140(r);
   filterCoverage140();
 } else if(tab==='analyst'){
   const sym=state.analyst.symbol;const gen=++analystGeneration;
   const [an,contract,learning]=await Promise.all([apiGet('/api/intelligence/automated-analyst/'+encodeURIComponent(sym)+'?action='+encodeURIComponent(state.analyst.action),false),apiGet('/api/v139/contract/'+encodeURIComponent(sym),false),apiGet('/api/v139/learning/'+encodeURIComponent(sym),false)]);
   if(gen!==analystGeneration||!currentViewRender(container,ticket))return;
   if(an.status==='INSUFFICIENT_DATA') {
     body=`<section class="card"><h3>Cash history exists — insufficient signal history</h3><p>${h(an.message)}</p><p>No opening trade or automatic forecast is produced from incomplete indicators.</p><label>Ticker <input id="analystTickerInput" value="${h(sym)}" oninput="scheduleAnalyst139()" onkeydown="if(event.key==='Enter')runAutomatedAnalyst()" /></label><button class="btn btn-primary" onclick="runAutomatedAnalyst()">Analyze selected ticker</button></section>`;
     container.innerHTML=techNav139(tab)+body;
   } else {
     body=buildAutomatedAnalystCardHtml(an)+contractCard139(contract)+weeklyChart139(an.weekly_summary)+learningCard139(learning);
     container.innerHTML=techNav139(tab)+body;saveForecast139(sym);
   }
 } else {
   const r=await apiGet('/api/v139/forecasts',false);if(!currentViewRender(container,ticket))return;
   body=`<section class="card"><h3>Forecasts & Results — immutable forward-recorded snapshots</h3><button class="btn btn-primary" onclick="evaluateForecasts139()">Evaluate saved forecasts</button><button class="btn btn-secondary" onclick="downloadForecasts139()">Download JSON</button><p>${h(r.note)}</p><p>Next-session direction and simulated trade outcome are different measures. No-trade is not a win. Daily-bar ambiguous cases receive no profit credit. Fees/slippage are assumptions, not verified broker charges.</p>${smallTable(['As of','Symbol','Horizon','Saved at','Expected','Next-session direction','Trade outcome','Net return','Evidence'],r.items.map(x=>[fmtDate(x.as_of),h(x.symbol),x.horizon===1?'Next session':'10 sessions',fmtDate(x.recorded_at),x.score>0?'UP':x.score<0?'DOWN':'NEUTRAL',h(x.outcome.directional_result||'PENDING'),h(x.outcome.status),fmtPct(x.outcome.net_return_pct,false),h(x.outcome.explanation||'Awaiting evaluation')]))}</section>`;
   container.innerHTML=techNav139(tab)+body;
 }
 enhanceWorkspace();
 } catch(e){if(currentViewRender(container,ticket))container.innerHTML=techNav139(tab)+`<section class="card"><h3>Could not complete analysis</h3><p>${h(e.message)}</p><label>Ticker <input id="analystTickerInput" value="${h(state.analyst.symbol)}" oninput="scheduleAnalyst139()" onkeydown="if(event.key==='Enter')runAutomatedAnalyst()"/></label><button class="btn btn-primary" onclick="renderTechnicalView(document.getElementById('viewContainer'))">Retry</button></section>`;}
 finally{if(currentViewRender(container,ticket)){container.classList.remove('refreshing139');container.removeAttribute('aria-busy');}}
}
function learningCard139(r){return `<section class="card"><h3>Learning research — separate from production rules</h3><p>${h(r.status)} ${r.stale?'— stale: new prices require a research refresh':''}</p>${r.test?smallTable(['Test samples','Model accuracy','Baseline accuracy','Model Brier','Baseline Brier'],[[fmtInt(r.test.n),fmtPct(r.test.accuracy),fmtPct(r.baseline.accuracy),fmtNum(r.test.brier,4),fmtNum(r.baseline.brier,4)]]):''}<p>${h(r.note||'')}</p><p>Research jobs run outside page requests. Existing trading rules are never silently replaced by an unvalidated model. See UPGRADE_1_3_9.md for the refresh command and optional scheduled workflow.</p></section>`;}
async function runAutomatedAnalyst(explicitSymbol=null){
 const symEl=document.getElementById('analystTickerInput'),actEl=document.getElementById('analystActionSelect');
 state.analyst.symbol=(explicitSymbol||symEl?.value||state.analyst.symbol).trim().toUpperCase();
 if(!state.analyst.symbol)return;if(actEl)state.analyst.action=actEl.value;
 recordSymbolSearch(state.analyst.symbol);state.technical.selectedSymbol=state.analyst.symbol;state.technical.subtab='analyst';await renderTechnicalView(document.getElementById('viewContainer'));
}
function scheduleAnalyst139(){clearTimeout(analystTimer);const input=document.getElementById('analystTickerInput');const requested=(input?.value||'').trim().toUpperCase();analystTimer=setTimeout(async()=>{try{const meta=await apiGet('/api/v139/market/meta');if(input?.isConnected&&input.value.trim().toUpperCase()===requested&&meta.symbols.includes(requested))await runAutomatedAnalyst(requested);}catch(e){showToast(e.message,true);}},650);}
async function triggerAnalystForTicker(sym){return runAutomatedAnalyst(sym);}
async function runTradingIdeasGenerator(){
 const a=document.getElementById('ideasScopeSelect'),b=document.getElementById('ideasQueryInput'),c=document.getElementById('ideasDirSelect');
 if(a)state.ideas.scope_or_sector=a.value;if(b)state.ideas.query=b.value;if(c)state.ideas.direction=c.value;
 state.technical.subtab='ideas';await renderTechnicalView(document.getElementById('viewContainer'));
}
async function evaluateForecasts139(){try{const r=await post139('forecasts/evaluate');showToast(`Evaluated ${r.evaluated} snapshots (up to ${r.limit} per request).`);await renderTechnicalView(document.getElementById('viewContainer'));}catch(e){showToast(e.message,true);}}
async function downloadForecasts139(){const r=await apiGet('/api/v139/forecasts',false);downloadJson139(r,'forecast-ledger.json');}
function downloadJson139(r,name){const url=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}

// Dedicated reference import has explicit preview/commit, never writes OHLC tables.
function referencePanel139(){return `<section class="card"><h3>Company, sector & constituent-list reference import</h3><p>Your supplied SECTOR_WISE lists are bundled as reference defaults. To replace them, upload a workbook with SYMBOL, COMPANY NAME and SECTOR headers. Extra unlabelled fields are ignored; aliases and historical prices are never rewritten.</p><input type="file" accept=".xlsx" aria-label="Sector reference workbook" onchange="previewReference139(this.files[0])"/><div id="referencePreview139"></div><details><summary>Custom file format</summary><p>Unknown formats are not guessed. Rename/map your reference columns to SYMBOL, COMPANY NAME, SECTOR; use COMP_LIST as the company directory sheet. The main staging centre also accepts reference workbooks by these headers (merge-only); this dedicated preview replaces the lists present in the workbook.</p></details></section>`;}
let referenceToken139=null;
async function previewReference139(file){if(!file)return;const el=document.getElementById('referencePreview139');el.innerHTML='<p role="status">Validating reference workbook…</p>';try{const fd=new FormData();fd.append('file',file);const r=await post139('reference/preview',fd);referenceToken139=r.token;el.innerHTML=`<h4>Preview — no company data changed yet</h4>${smallTable(['List','Symbol rows','Added/changed'],Object.entries(r.counts).map(([k,v])=>[h(k),fmtInt(v),fmtInt(r.changes[k])]))}<ul>${r.warnings.map(x=>`<li>${h(x)}</li>`).join('')}</ul><details><summary>Symbols without stored cash prices (${r.unmatched_symbols.length})</summary><p>${h(r.unmatched_symbols.join(', '))}</p></details><button class="btn btn-primary" onclick="commitReference139(this)">Confirm reference import</button>`;}catch(e){el.textContent=e.message;}}
async function commitReference139(button){if(!referenceToken139)return;button.disabled=true;try{const r=await post139('reference/commit',{token:referenceToken139});referenceToken139=null;clearClientCache();document.getElementById('referencePreview139').textContent='Reference import committed. '+r.warnings.join(' ');}catch(e){showToast(e.message,true);button.disabled=false;}}

async function renderMarketView(container){
 const ticket=beginViewRender(container);const m=state.market;container.setAttribute('aria-busy','true');
 if(!container.querySelector('.card'))container.innerHTML=skeleton139();else container.classList.add('refreshing139');
 try{
 const meta=await apiGet('/api/v139/market/meta',false);if(!currentViewRender(container,ticket))return;
 if(!meta.dates.includes(m.date))m.date=meta.dates[0]||null;
 if(!meta.symbols.includes(m.symbol))m.symbol=meta.symbols[0]||'PRL';
 let html=`<div class="subtabs"><button class="subtab-btn ${m.tab==='volume'?'active':''}" onclick="state.market.tab='volume';marketRefresh139()">Market volume</button><button class="subtab-btn ${m.tab==='symbol'?'active':''}" onclick="state.market.tab='symbol';marketRefresh139()">Symbol vs Index</button></div>`;
 if(!m.date){container.innerHTML=html+'<section class="card">No imported cash prices available.</section>';return;}
 if(m.tab==='volume'){
 const r=await apiGet('/api/v139/market/volume?'+new URLSearchParams({date:m.date,n:m.n}),false);if(!currentViewRender(container,ticket))return;
 const full=new Intl.DateTimeFormat('en-US',{weekday:'long',year:'numeric',month:'long',day:'numeric',timeZone:'UTC'}).format(new Date(m.date+'T12:00:00Z'));
 const years=[...new Set(meta.dates.map(d=>d.slice(0,4)))];const months=[...new Set(meta.dates.filter(d=>d.startsWith(m.date.slice(0,4))).map(d=>d.slice(5,7)))];const days=meta.dates.filter(d=>d.startsWith(m.date.slice(0,7)));
 const select=(label,values,value,handler)=>`<label>${label}<select onchange="${handler}">${values.map(v=>`<option value="${v}" ${v===value?'selected':''}>${label==='Day'?fmtDate(v):v}</option>`).join('')}</select></label>`;
 html+=`<div class="explorer-layout"><aside class="card date-hierarchy"><h3>Trading date hierarchy</h3>${select('Year',years,m.date.slice(0,4),"marketDate139(this.value,4)")}${select('Month',months,m.date.slice(5,7),"marketDate139(this.value,2)")}${select('Day',days,m.date,"state.market.date=this.value;marketRefresh139()")}</aside><div><section class="card"><h3>${h(full)}</h3><div class="top-n139" role="group" aria-label="Top volume count">${Array.from({length:10},(_,i)=>`<button class="subtab-btn ${m.n===i+1?'active':''}" aria-pressed="${m.n===i+1}" onclick="state.market.n=${i+1};marketRefresh139()">${i+1}</button>`).join('')}</div><p>${h(r.universe)}</p></section><div class="grid-2"><section class="card"><h3>Top ${r.top_n} Volume made ${r.top_pct.toFixed(2)}% of Total Volume</h3>${donut139(r)}</section><section class="card"><h3>Top ${r.top_n} Volume made ${r.top_pct.toFixed(2)}% of Total Volume</h3>${columns139(r)}</section></div><section class="card">${smallTable(['Symbol','Volume (M)','Share'],r.parts.map(p=>[h(p.symbol),fmtNum(p.volume/1e6,3)+'M',fmtPct(p.pct,false)]))}<button class="btn btn-secondary" onclick="downloadMarket139()">Download view data</button></section></div></div>`;
 }else{
 const r=await apiGet('/api/v139/market/symbol/'+encodeURIComponent(m.symbol)+'?'+new URLSearchParams({n:m.days,end:m.date}),false);if(!currentViewRender(container,ticket))return;
 html+=`<section class="card filter-bar"><label>Records <input type="number" min="1" max="6000" value="${m.days}" onchange="state.market.days=Math.min(6000,Math.max(1,Math.floor(Number(this.value)||1)));marketRefresh139()"/></label><label>Symbol <select onchange="state.market.symbol=this.value;marketRefresh139()">${meta.symbols.map(s=>`<option ${s===m.symbol?'selected':''}>${h(s)}</option>`).join('')}</select></label><label>As-of session <select onchange="state.market.date=this.value;marketRefresh139()">${meta.dates.map(d=>`<option value="${d}" ${d===m.date?'selected':''}>${fmtDate(d)}</option>`).join('')}</select></label></section>`;
 if(r.status!=='OK'){container.innerHTML=html+'<section class="card">No symbol records on or before this date.</section>';return;}
 const card=(label,v)=>`<div class="kpi-box"><div class="kpi-label">${h(label)}</div><div class="kpi-value ${pnlClass(v?.change)}">${fmtNum(v?.change)}</div><p>${fmtPct(v?.pct,false)}</p></div>`;
 html+=`<section class="card"><h3>${h(m.symbol)} — last ${r.count} records ${r.count<r.requested?'(less than requested available)':''}</h3><div class="grid-4">${card('Symbol period change',r.symbol_change)}${card('Index period change',r.index_change)}${card('Current-week symbol change',r.week_symbol)}${card('Current-week index change',r.week_index)}</div><p><b>Minimum date:</b> ${fmtDate(r.first)} · <b>Maximum date:</b> ${fmtDate(r.last)}</p><p>Period baseline: ${fmtDate(r.baseline_date)} · Week baseline: ${fmtDate(r.week_baseline_date)}. One day means one stored symbol record. ${h(r.benchmark_note)}</p>${r.missing_index_dates.length?`<p class="neg">Missing benchmark dates: ${r.missing_index_dates.map(fmtDate).join(', ')}.</p>`:''}</section><section class="card extrema139">${r.extrema.map(x=>`<div><b>${h(x.label)}</b><h3>${fmtNum(x.value,x.label==='Max volume'?0:2)}</h3><p>${x.dates.map(fmtDate).join(', ')||'Unavailable'}</p></div>`).join('')}</section><div class="grid-2"><section class="card"><h3>${h(m.symbol)} records</h3>${smallTable(['Date','High','Low','Average','Close','Change','Change %','Volume'],r.rows.map(x=>[fmtDate(x.trade_date),fmtNum(x.high),fmtNum(x.low),fmtNum(x.avg_price),fmtNum(x.close),`<span class="${pnlClass(x.change)}">${fmtNum(x.change)}</span>`,fmtPct(x.pct,false),fmtInt(x.volume)]))}</section><section class="card"><h3>Imported Index — identity unverified</h3>${smallTable(['Date','Close','High','Low','Change','Change %','Volume'],r.index_rows.map(x=>[fmtDate(x.trade_date),fmtNum(x.close),fmtNum(x.high),fmtNum(x.low),fmtNum(x.change),fmtPct(x.pct,false),fmtInt(x.volume)]))}</section></div><button class="btn btn-secondary" onclick="downloadMarket139()">Download view data</button>`;
 }
 if(currentViewRender(container,ticket)){container.innerHTML=html;enhanceWorkspace();}
 }catch(e){if(currentViewRender(container,ticket))container.innerHTML=`<section class="card"><h3>Market view unavailable</h3><p>${h(e.message)}</p><button onclick="marketRefresh139()">Retry</button></section>`;}
 finally{if(currentViewRender(container,ticket)){container.removeAttribute('aria-busy');container.classList.remove('refreshing139');}}
}
const colors139=['#38bdf8','#a78bfa','#34d399','#fbbf24','#f472b6','#2dd4bf','#fb923c','#818cf8','#a3e635','#f87171','#94a3b8'];
function donut139(r){if(!r.total)return '<p>No positive reported volume.</p>';let offset=0;return `<svg class="market-svg" viewBox="0 0 420 350" role="img" aria-label="Top volume donut; data table follows"><circle cx="210" cy="165" r="112" fill="none" stroke="#334155" stroke-width="48"/>${r.parts.map((p,i)=>{const length=p.pct/100*703.717;const s=`<circle cx="210" cy="165" r="112" fill="none" stroke="${p.symbol==='Others'?'#94a3b8':colors139[i]}" stroke-width="48" stroke-dasharray="${length} ${703.717-length}" stroke-dashoffset="${-offset}" transform="rotate(-90 210 165)"><title>${h(p.symbol)} ${fmtNum(p.volume/1e6,2)}M (${p.pct.toFixed(2)}%)</title></circle>`;offset+=length;return s;}).join('')}<text x="210" y="164" text-anchor="middle" fill="currentColor" font-size="32" font-weight="700">${fmtNum(r.total/1e6,2)}M</text><text x="210" y="189" text-anchor="middle" fill="currentColor" font-size="14">TOTAL VOLUME</text></svg><ul class="chart-legend139">${r.parts.map((p,i)=>`<li><i style="background:${p.symbol==='Others'?'#94a3b8':colors139[i]}"></i>${h(p.symbol)} ${fmtNum(p.volume/1e6,2)}M (${p.pct.toFixed(2)}%)</li>`).join('')}</ul>`;}
function columns139(r){if(!r.total)return '<p>No volume data.</p>';const max=Math.max(...r.parts.map(x=>x.volume)),w=600/r.parts.length;return `<svg class="market-svg" viewBox="0 0 700 400" role="img" aria-label="Top volume columns with millions and share labels">${[0,.25,.5,.75,1].map(f=>`<text x="0" y="${320-f*250}" fill="currentColor" font-size="12">${fmtNum(max*f/1e6,1)}M</text><line x1="65" x2="690" y1="${320-f*250}" y2="${320-f*250}" stroke="#64748b" opacity=".3"/>`).join('')}${r.parts.map((p,i)=>{const x=65+i*w,y=320-p.volume/max*250;return `<rect x="${x}" y="${y}" width="${w*.65}" height="${320-y}" fill="${p.symbol==='Others'?'#94a3b8':colors139[i]}"/><text x="${x}" y="${y-22}" fill="currentColor" font-size="11">${fmtNum(p.volume/1e6,1)}M</text><text x="${x}" y="${y-8}" fill="currentColor" font-size="10">(${p.pct.toFixed(1)}%)</text><text x="${x}" y="338" transform="rotate(40 ${x} 338)" fill="currentColor" font-size="11">${h(p.symbol)}</text>`;}).join('')}</svg>`;}
function marketRefresh139(){renderMarketView(document.getElementById('viewContainer'));}
async function marketDate139(value,size){const meta=await apiGet('/api/v139/market/meta');const prefix=size===4?value:state.market.date.slice(0,4)+'-'+value;state.market.date=meta.dates.find(d=>d.startsWith(prefix));marketRefresh139();}
async function downloadMarket139(){const m=state.market;const path=m.tab==='volume'?'/api/v139/market/volume?'+new URLSearchParams({date:m.date,n:m.n}):'/api/v139/market/symbol/'+encodeURIComponent(m.symbol)+'?'+new URLSearchParams({n:m.days,end:m.date});downloadJson139(await apiGet(path,false),'market-explorer.json');}

async function renderImportCenter(container){await renderImportLegacy(container);if(container.isConnected)container.insertAdjacentHTML('afterbegin',referencePanel139());}

function weeklyChart139(ws){
 const weeks=ws?.recent_weeks||[];if(weeks.length<2)return '';
 const values=weeks.map(w=>w.close);let lo=Math.min(...values),hi=Math.max(...values);if(hi===lo){lo-=1;hi+=1;}
 const x=i=>65+i/(weeks.length-1)*600,y=v=>210-(v-lo)/(hi-lo)*170;
 return `<section class="card"><h3>Completed weekly closes</h3><p>${h(ws.method)} Current incomplete week is excluded.</p><svg class="market-svg" viewBox="0 0 740 265" role="img" aria-label="Completed weekly close chart"><rect width="740" height="265" fill="#080e1b"/><text x="5" y="40" fill="#cbd5e1" font-size="12">${fmtNum(hi)}</text><text x="5" y="210" fill="#cbd5e1" font-size="12">${fmtNum(lo)}</text><path d="${weeks.map((w,i)=>`${i?'L':'M'}${x(i)},${y(w.close)}`).join(' ')}" fill="none" stroke="#a78bfa" stroke-width="3"/>${weeks.map((w,i)=>`<text x="${x(i)}" y="240" text-anchor="middle" fill="#cbd5e1" font-size="10">${fmtDate(w.end_date)}</text>`).join('')}</svg></section>`;
}

// 1.3.10: distinguish data coverage, scope filters, signal readiness and valid trades.
let coverage140=null;
function scanDiagnostics140(r){
 const c=r.scan_counts||{};
 const counters=[['Matched & examined',c.analyzed],['Current data ready',c.data_ready],['Direction eligible',c.direction_eligible],['Valid structural plans',c.structurally_qualified],['Displayed',c.displayed]];
 return `<section class="card"><h3>Scan accounting — no silent exclusions</h3><div class="grid-4">${counters.map(([label,n])=>`<div class="kpi-box"><b>${h(label)}</b><p>${fmtInt(n||0)}</p></div>`).join('')}</div><p>${h(r.message||'')}</p><p>${h(r.scope_note||'')}</p><p>Query interpretation: ${h(r.query_interpretation||'none')}. Examined means the stored cash history and available indicators were checked; it does not mean a trade qualified. Rule scores are not win probabilities.</p>${(r.outside_scope||[]).length?`<h4>Matching cash symbols outside scope</h4>${smallTable(['Symbol','Cash sessions','Reason'],r.outside_scope.map(x=>[h(x.symbol),fmtInt(x.bars_count),h(x.reason)]))}`:''}<h4>Every matched symbol: history, signal and decision</h4>${(r.diagnostics||[]).length?smallTable(['Symbol','Cash sessions','First cash date','Latest cash date','Raw signal','Rule score','Decision / reasons'],r.diagnostics.map(x=>[h(x.symbol),fmtInt(x.bars_count),fmtDate(x.first_date),fmtDate(x.latest_date),h(x.raw_signal),h(x.score),h(x.status+': '+x.reason)])):'<p>No cash history matched this scope/query. This is not evidence that the symbol has no data elsewhere. Open Data coverage & exclusions to inspect references, futures, Top5 and accounts.</p>'}<button class="btn btn-secondary" onclick="state.technical.subtab='coverage';renderTechnicalView(document.getElementById('viewContainer'))">Inspect cross-module data coverage</button><button class="btn btn-secondary" onclick="downloadLastScan140()">Download scan diagnostics</button></section>`;
}
let lastScan140=null;
const originalScanDiagnostics140=scanDiagnostics140;
scanDiagnostics140=function(r){lastScan140=r;return originalScanDiagnostics140(r);};
function downloadLastScan140(){if(lastScan140)downloadJson139(lastScan140,'scan-diagnostics.json');}
function coveragePanel140(r){
 const s=r.summary;
 return `<section class="card"><h3>Cross-module symbol coverage</h3><p>${h(r.note)}</p><div class="grid-4">${[['Cash / engine symbols',s.cash_symbols+' / '+s.technical_symbols],['Current / historical-stale',s.current_cash_symbols+' / '+s.stale_cash_symbols],['Futures bases / Top5 symbols',s.futures_base_symbols+' / '+s.top5_symbols],['Cash missing in engine',s.cash_missing_in_engine.length]].map(([label,value])=>`<div class="kpi-box"><b>${h(label)}</b><p>${h(value)}</p></div>`).join('')}</div><p>Latest cash: ${fmtDate(s.latest_cash_date)} · Latest imported INDEX: ${fmtDate(s.index.latest)}. Different source dates are not silently filled.</p><p>Signals with insufficient history: ${fmtInt(s.insufficient_signal_symbols)} (including stale symbols). Missing cash: Core36 ${s.core_missing_cash.length}; futures bases ${s.futures_missing_cash.length}; Top5 ${s.top5_missing_cash.length}; account bases ${s.account_missing_cash.length}.</p><label>Filter symbol or sector <input id="coverageSearch140" placeholder="e.g. TRG, MLCF, CEMENT" oninput="filterCoverage140()" /></label><button class="btn btn-secondary" onclick="downloadJson139(coverage140,'cross-module-coverage.json')">Download complete coverage report</button><p id="coverageCount140"></p><div id="coverageRows140"></div></section>`;
}
function filterCoverage140(){
 if(!coverage140)return;
 const q=(document.getElementById('coverageSearch140')?.value||'').trim().toUpperCase();
 const rows=coverage140.items.filter(x=>x.symbol.includes(q)||x.sector.toUpperCase().includes(q));
 document.getElementById('coverageCount140').textContent=`${rows.length} matching instruments / reference members. Dates show source coverage; missing does not mean zero price.`;
 document.getElementById('coverageRows140').innerHTML=smallTable(['Symbol','Sector','Cash sessions','Engine sessions','First cash','Latest cash','Freshness / signal','Futures rows / latest','Top5 rows / latest','Accounts / instruments','Reference lists','Decision evidence'],rows.map(x=>[h(x.symbol),h(x.sector),fmtInt(x.cash_rows),fmtInt(x.engine_bars),fmtDate(x.first_cash_date),fmtDate(x.latest_cash_date),h(x.freshness+' / '+x.signal),h(x.futures_rows+' / '+(x.latest_futures_date||'—')),h(x.top5_rows+' / '+(x.latest_top5_date||'—')),h(x.accounts.join(', ')+' / '+x.account_symbols.join(', ')),h(x.reference_lists.join(', ')),h(x.notes.join(' ')||'Structural plan passes; direction/scope/entry conditions still apply.')]));
 enhanceWorkspace();
}
