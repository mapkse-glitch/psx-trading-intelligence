/* v1.3.21: market panels and keyboard-first native dropdowns. No external assets. */
function marketTabs1321(active){
 return `<div class="subtabs" role="group" aria-label="Market Explorer pages">${[['volume','Market volume'],['symbol','Symbol vs Index'],['matching','Matching Rate'],['smallcards','Small Cards']].map(([id,label])=>`<button class="subtab-btn ${active===id?'active':''}" aria-pressed="${active===id}" onclick="marketTab1321('${id}')">${label}</button>`).join('')}</div>`;
}
function marketTab1321(tab){clearCalendarNotice1311();state.market.tab=tab;marketRefresh139();}
function rangeBar1321(range){return `<div class="range-window-bar1321 ${range.high==null||range.low==null?'range-window-empty1321':''}" role="img" aria-label="${h(range.high==null||range.low==null?'Range unavailable':`High ${fmtNum(range.high)} at left to Low ${fmtNum(range.low)} at right`)}"></div>`;}
function metric1321(label,value,tone=''){return `<div class="small-metric1321"><span>${h(label)}</span><strong class="${tone}">${value}</strong></div>`;}
function number1321(value,decimals=2){return value==null?'Not available':fmtNum(value,decimals);}
function signed1321(value){return value==null?'Not available':`<span class="${pnlClass(value)}">${fmtNum(value)}</span>`;}
function pct1321(value){return value==null?'Not available':fmtPct(value,false);}
function periodMetric1321(label,period){return `<div class="small-metric1321"><span>${h(label)}</span><strong class="${pnlClass(period?.change)}">${number1321(period?.change)}</strong><small class="${pnlClass(period?.pct)}">${pct1321(period?.pct)}</small></div>`;}
function smallSymbolCard1321(card,report){
 const tone=pnlClass(card.change),index=report.index,now=index?.latest,window=index?.window;
 let html=`<article class="card small-symbol-card1321" aria-label="${h(card.symbol)} sector card"><header><h3 class="${tone}">${h(card.symbol)}</h3><p>${h(card.company)}</p><small>${card.trade_date?fmtDate(card.trade_date):'No imported prices'}${card.stale?' · Older than latest market date':''}</small></header>`;
 // A reference member without price records still gets exactly one honest card.
 if(card.status!=='OK')return html+'<p class="small-empty1321">No imported price records for this symbol. Import its authentic data to populate the figures.</p></article>';
 html+=`<div class="small-metric-row1321 three1321">${metric1321('Latest close',number1321(card.close),tone)}${metric1321('DoD change',number1321(card.change),tone)}${metric1321('DoD change (%)',pct1321(card.pct),tone)}</div>`;
 html+=`<div class="small-metric-row1321">${metric1321('Latest high',number1321(card.high),'pos')}${metric1321('Latest low',number1321(card.low),'neg')}</div>`;
 html+=`<div class="small-metric-row1321">${metric1321('Source average',number1321(card.avg_price))}${metric1321('Volume',card.volume==null?'Not available':fmtInt(card.volume))}</div>`;
 html+=`<div class="small-metric-row1321">${periodMetric1321('Week to date',card.week)}${periodMetric1321('Month to date',card.month)}</div>`;
 html+=`<section class="small-window1321"><h4>Based on Selected Sessions (${fmtInt(report.requested)})</h4><div class="small-metric-row1321">${metric1321('Session high',number1321(card.session_high),'pos')}${metric1321('Session low',number1321(card.session_low),'neg')}</div><p class="small-coverage1321">${fmtInt(card.session_count)} of ${fmtInt(report.requested)} sessions available · ${fmtDate(card.session_first)} – ${fmtDate(card.trade_date)}</p></section>`;
 const itone=pnlClass(now?.change),wtone=pnlClass(window?.change);
 html+=`<section class="small-index1321"><h4>Current index${now?' · '+fmtDate(now.trade_date):''}</h4><div class="small-metric-row1321 three1321">${metric1321('Close',number1321(now?.close),itone)}${metric1321('High',number1321(now?.high),itone)}${metric1321('Low',number1321(now?.low),itone)}${metric1321('Change',number1321(now?.change),itone)}${metric1321('Change (%)',pct1321(now?.pct),itone)}</div></section>`;
 html+=`<section class="small-index1321"><h4>Index · selected ${fmtInt(report.requested)} sessions</h4><div class="small-metric-row1321">${metric1321('High',number1321(window?.high),wtone)}${metric1321('Low',number1321(window?.low),wtone)}${metric1321('Change',number1321(window?.change),wtone)}${metric1321('Change (%)',pct1321(window?.pct),wtone)}</div><p class="small-coverage1321">${window?`${fmtInt(window.count)} sessions · ${fmtDate(window.first)} – ${fmtDate(window.last)}<br>Baseline: ${window.baseline_date?fmtDate(window.baseline_date):'Not available'}`:'No imported index data'}</p></section>`;
 return html+'</article>';
}
async function renderMarketExtra1321(container,ticket){
 const m=state.market,tab=m.tab;
 const current=()=>currentViewRender(container,ticket)&&state.market.tab===tab;
 let html=marketTabs1321(tab);
 if(tab==='matching'){
  const meta=await apiGet('/api/v139/market/meta',false);if(!current())return;
  if(!meta.symbols.includes(m.match_symbol))m.match_symbol=meta.symbols.includes(m.symbol)?m.symbol:meta.symbols[0];
  html+=`<section class="card filter-bar panels-filter1321"><label>Symbol <select id="matchingSymbol1321" ${meta.symbols.length?'':'disabled'} onchange="state.market.match_symbol=this.value;marketRefresh139()">${meta.symbols.map(s=>`<option value="${h(s)}" ${s===m.match_symbol?'selected':''}>${h(s)}</option>`).join('')}</select></label><span class="panels-note1321">10 nearest historical closes · excludes the most recent calendar month</span></section>`;
  if(!m.match_symbol){container.innerHTML=html+'<section class="card">No imported symbol prices are available.</section>';enhanceWorkspace();return;}
  const r=await apiGet('/api/v139/market/matching/'+encodeURIComponent(m.match_symbol),false);if(!current())return;
  if(r.status!=='OK'){container.innerHTML=html+'<section class="card">No imported prices for this symbol.</section>';enhanceWorkspace();return;}
  html+=`<section class="card"><div class="matching-heading1321"><h3>${h(r.symbol)} · Matching Rate</h3><span>Latest symbol: ${fmtDate(r.latest.trade_date)}${r.latest_index?' · Latest index: '+fmtDate(r.latest_index.trade_date):' · Index unavailable'}</span></div><p class="panels-note1321">Matches strictly before ${fmtDate(r.cutoff)}. Differences = latest close − historical close. Gaps count stored trading sessions for this symbol. Index dates must match exactly.</p>`;
  const headers=['Latest close','Latest index close','Nearby close','Match date','Close difference','Sessions ago','Index date','Index close on match','Index difference'];
  const rows=r.rows.map(x=>[number1321(x.latest_close),number1321(x.latest_index_close),number1321(x.close),fmtDate(x.trade_date),signed1321(x.close_difference),fmtInt(x.sessions_ago),x.index_date?fmtDate(x.index_date):'No exact match',number1321(x.index_close),signed1321(x.index_difference)]);
  html+=`<div class="matching-table1321">${smallTable(headers,rows)}</div>${r.rows.length<10?`<p class="panels-note1321">${r.rows.length} of 10 eligible historical matches available; no rows are fabricated.</p>`:''}</section>`;
 }else{
  const meta=await apiGet('/api/v139/market/selected-sectors',false);if(!current())return;
  if(meta.status!=='OK'||!meta.sectors.length){container.innerHTML=html+'<section class="card"><h3>Imported SEL_COMP_LIST required</h3><p>Import your authentic Sector Wise workbook containing SEL_COMP_LIST through the existing reference import. This view does not substitute the broader company directory.</p></section>';enhanceWorkspace();return;}
  if(!meta.sectors.some(s=>s.sector===m.card_sector))m.card_sector=meta.sectors[0].sector;
  m.card_sessions=Math.min(6000,Math.max(1,Math.floor(Number(m.card_sessions)||14)));
  html+=`<section class="card filter-bar panels-filter1321"><label>Sector <select id="smallSector1321" onchange="state.market.card_sector=this.value;marketRefresh139()">${meta.sectors.map(s=>`<option value="${h(s.sector)}" ${s.sector===m.card_sector?'selected':''}>${h(s.sector)} (${fmtInt(s.symbols)})</option>`).join('')}</select></label><label>Number of sessions <input id="smallSessions1321" type="number" min="1" max="6000" step="1" value="${m.card_sessions}" onchange="state.market.card_sessions=Math.min(6000,Math.max(1,Math.floor(Number(this.value)||14)));marketRefresh139()"/></label><span class="panels-note1321">Imported ${h(meta.source)} only</span></section>`;
  const r=await apiGet('/api/v139/market/small-cards?'+new URLSearchParams({sector:m.card_sector,sessions:m.card_sessions}),false);if(!current())return;
  html+=`<section class="card sector-overview1321"><h3>${h(r.sector)} · ${fmtInt(r.cards.length)} symbols</h3><span>Latest cash-market date: ${r.as_of?fmtDate(r.as_of):'Not available'} · Imported index${r.index?' as of '+fmtDate(r.index.latest.trade_date):' unavailable'}</span><p class="panels-note1321">WTD/MTD compare with the last close before the week/month began. Each symbol and the index use their own last N stored sessions. Partial coverage and older dates remain explicit.</p></section><div class="sector-cards1321">${r.cards.map(c=>smallSymbolCard1321(c,r)).join('')}</div>`;
 }
 if(current()){container.innerHTML=html;enhanceWorkspace();}
}

/* Native selects keep their normal pointer/arrow behavior. Type-ahead is staged
   until Enter or blur so cycling letters never triggers a request per keystroke. */
(function installFilterTypeahead1321(){
 const states=new WeakMap();
 const valid=el=>el?.matches?.('select')&&!el.disabled&&!el.multiple;
 const norm=s=>String(s).normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase().trim();
 const commit=el=>{const s=states.get(el);if(s?.pending){s.pending=false;el.dispatchEvent(new Event('change',{bubbles:true}));}};
 document.addEventListener('keydown',e=>{
  const el=e.target;if(!valid(el)||e.ctrlKey||e.metaKey||e.altKey||e.isComposing)return;
  const old=states.get(el);
  if(e.key==='Enter'&&old?.pending){e.preventDefault();commit(el);return;}
  if(e.key==='Escape'&&old?.pending){e.preventDefault();el.selectedIndex=old.original;states.delete(el);return;}
  if(e.key.length!==1||(!/[\p{L}\p{N}]/u.test(e.key)&&!(e.key===' '&&old?.prefix)))return;
  e.preventDefault();
  const now=Date.now(),key=e.key===' '?' ':norm(e.key),s=old||{prefix:'',at:0,original:el.selectedIndex,pending:false};
  const active=now-s.at<1000;
  const repeat=active&&s.prefix===key;
  let prefix=active&&!repeat?s.prefix+key:key;
  let options=[...el.options].map((o,i)=>({o,i})).filter(({o})=>!o.disabled&&!o.hidden&&!(o.parentElement?.tagName==='OPTGROUP'&&o.parentElement.disabled));
  let matches=options.filter(({o})=>norm(o.textContent).startsWith(prefix));
  if(!matches.length&&prefix!==key){prefix=key;matches=options.filter(({o})=>norm(o.textContent).startsWith(prefix));}
  if(matches.length){const hit=repeat?(matches.find(x=>x.i>el.selectedIndex)||matches[0]):matches[0];el.selectedIndex=hit.i;s.pending=el.selectedIndex!==s.original;}
  s.prefix=prefix;s.at=now;states.set(el,s);
 },true);
 document.addEventListener('focusout',e=>{if(valid(e.target))commit(e.target);},true);
 document.addEventListener('change',e=>{if(valid(e.target))states.delete(e.target);},true);
 document.addEventListener('pointerdown',e=>{if(valid(e.target)){const s=states.get(e.target);if(s)s.prefix='';}},true);
 // Hint metadata only: no added controls or changed tab order anywhere.
 const mark=()=>document.querySelectorAll('select:not([multiple])').forEach(el=>{if(!el.dataset.typeahead1321){el.dataset.typeahead1321='true';if(!el.title)el.title='Type letters to jump; repeat a letter to cycle. Enter or leave the filter to apply; Escape cancels.';}});
 mark();new MutationObserver(mark).observe(document.getElementById('appShell')||document.body,{childList:true,subtree:true});
})();
