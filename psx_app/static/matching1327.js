/* Additional matching view: original closest matches plus an inclusive price range. */
function match1Number1327(v){return v==null?'Not available':Number(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:12});}
function match1State1327(){return state.market.range1327||(state.market.range1327={symbol:null,low:'',high:'',includeRecent:true,applied:null,page:1});}
function match1Symbol1327(value){const s=match1State1327();s.symbol=value;s.page=1;return marketRefresh139();}
function match1Apply1327(){
 const s=match1State1327(),lo=s.low.trim(),hi=s.high.trim(),target=document.getElementById('match1Error1327');
 if(!lo||!hi||!Number.isFinite(Number(lo))||!Number.isFinite(Number(hi))||Number(lo)<0||Number(hi)<Number(lo)){
  if(target)target.textContent='Enter both nonnegative prices; the starting price must not exceed the ending price.';return;
 }
 s.applied={low:Number(lo),high:Number(hi),includeRecent:s.includeRecent};s.page=1;marketRefresh139();
}
function match1Page1327(page){const s=match1State1327();s.page=page;marketRefresh139();}
function match1Clear1327(){const s=match1State1327();s.low='';s.high='';s.applied=null;s.page=1;marketRefresh139();}
async function renderMatchingOne1327(container,ticket){
 const m=state.market,s=match1State1327(),snapshot={symbol:s.symbol||m.match_symbol||m.symbol,applied:s.applied,page:s.page};
 const current=()=>currentViewRender(container,ticket)&&state.market.tab==='matching1';
 function path(symbol){if(!snapshot.applied)return '/api/v139/market/matching/'+encodeURIComponent(symbol);const p=new URLSearchParams({low:snapshot.applied.low,high:snapshot.applied.high,page:snapshot.page,include_recent:snapshot.applied.includeRecent});return '/api/v139/market/matching-range/'+encodeURIComponent(symbol)+'?'+p;}
 const [meta,prepared]=await Promise.all([panelGet1322('/api/v139/market/meta'),snapshot.symbol?panelGet1322(path(snapshot.symbol)):Promise.resolve(null)]);if(!current())return;
 if(!meta.symbols.includes(snapshot.symbol))s.symbol=meta.symbols.includes(m.symbol)?m.symbol:meta.symbols[0];else s.symbol=snapshot.symbol;
 let html=marketTabs1321('matching1')+`<form class="card filter-bar panels-filter1321 match1-filters1327" onsubmit="event.preventDefault();match1Apply1327()"><label>Symbol <select id="matchingOneSymbol1327" ${meta.symbols.length?'':'disabled'} onchange="match1Symbol1327(this.value)">${meta.symbols.map(symbol=>`<option value="${h(symbol)}" ${symbol===s.symbol?'selected':''}>${h(symbol)}</option>`).join('')}</select></label><label>Starting price (PKR) <input id="match1Low1327" type="number" inputmode="decimal" min="0" step="any" value="${h(s.low)}" oninput="match1State1327().low=this.value" placeholder="e.g. 95" /></label><label>Ending price (PKR) <input id="match1High1327" type="number" inputmode="decimal" min="0" step="any" value="${h(s.high)}" oninput="match1State1327().high=this.value" placeholder="e.g. 97" /></label><label class="match1-scope1327"><input type="checkbox" ${s.includeRecent?'checked':''} onchange="match1State1327().includeRecent=this.checked" /> Include latest month</label><button class="btn btn-primary" type="submit">Find prices</button>${snapshot.applied?'<button class="btn btn-secondary" type="button" onclick="match1Clear1327()">Clear range</button>':''}<p id="match1Error1327" class="match1-error1327" role="alert"></p><span class="panels-note1321">Inclusive range · all stored dates when latest month is included.</span></form>`;
 if(!s.symbol){container.innerHTML=html+'<section class="card">No imported symbol prices are available.</section>';enhanceWorkspace();return;}
 const r=snapshot.symbol===s.symbol&&prepared?prepared:await panelGet1322(path(s.symbol));if(!current())return;
 if(r.status!=='OK'){container.innerHTML=html+'<section class="card">No imported prices for this symbol.</section>';enhanceWorkspace();return;}
 const heading=`<section class="card"><div class="matching-heading1321"><h3>${h(r.symbol)} · Matching Rate 1</h3><span>Latest symbol: ${fmtDate(r.latest.trade_date)}${r.latest_index?' · Latest index: '+fmtDate(r.latest_index.trade_date):' · Index unavailable'}</span></div>`;
 let note;
 if(snapshot.applied){const a=snapshot.applied;note=`Prices from ${match1Number1327(a.low)} to ${match1Number1327(a.high)} inclusive · ${a.includeRecent?'all stored dates, including the latest date':`strictly before ${fmtDate(r.cutoff)}`} · ${fmtInt(r.total)} matching records. Closest to the latest close first; newest date first on ties.`;}
 else note=`10 nearest historical closes strictly before ${fmtDate(r.cutoff)}. Enter a price range above to find every matching record.`;
 html+=heading+`<p class="panels-note1321">${h(note)} Differences = latest close − historical close. Gaps count stored trading sessions for this symbol. Index dates must match exactly.</p>`;
 const headers=['Latest close','Latest index close','Nearby close','Match date','Close difference','Sessions ago','Index date','Index close on match','Index difference'];
 const rows=r.rows.map(x=>[number1321(x.latest_close),number1321(x.latest_index_close),match1Number1327(x.close),fmtDate(x.trade_date),signed1321(x.close_difference),fmtInt(x.sessions_ago),x.index_date?fmtDate(x.index_date):'No exact match',number1321(x.index_close),signed1321(x.index_difference)]);
 html+=`<div class="matching-table1321">${smallTable(headers,rows)}</div>`;
 if(snapshot.applied){const first=r.total?(r.page-1)*r.page_size+1:0,last=Math.min(r.total,r.page*r.page_size);html+=`<div class="match1-pages1327"><span>Showing ${fmtInt(first)}–${fmtInt(last)} of ${fmtInt(r.total)}</span><button type="button" class="btn btn-secondary" ${r.page<=1?'disabled':''} onclick="match1Page1327(${r.page-1})">Previous</button><button type="button" class="btn btn-secondary" ${last>=r.total?'disabled':''} onclick="match1Page1327(${r.page+1})">Next</button></div>`;}
 else if(r.rows.length<10)html+=`<p class="panels-note1321">${r.rows.length} of 10 eligible historical matches available; no rows are fabricated.</p>`;
 container.innerHTML=html+'</section>';enhanceWorkspace();
}
