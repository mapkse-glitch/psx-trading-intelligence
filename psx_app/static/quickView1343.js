/* Quick View: imported symbol history and last traded market session. */
const quickView1343={symbol:'',sessions:'1',report:null};
function quickViewSelect1343(value){quickView1343.symbol=value;quickView1343.report=null;const c=document.getElementById('viewContainer');c.innerHTML=marketTabs1321('quickView')+skeleton139();marketRefresh139();}
function quickVal1343(value,volume=false){return value==null?'—':h(volume?fmtInt(value):fmtNum(value));}
function quickDate1343(value){return value?h(fmtDate(value)):'—';}
function quickLock1345(coverage){
 if(!coverage||coverage.count==null)return '<span title="No sessions have sufficient data to assess this estimate">Unavailable</span>';
 const incomplete=coverage.checked<coverage.total;
 const text=(incomplete?'≥':'')+fmtInt(coverage.count);
 const detail=`Estimated intraday touches · ${coverage.checked} of ${coverage.total} imported records assessed${incomplete?' · incomplete':''}`;
 return `<span tabindex="0" title="${h(detail)}" aria-label="${h(text+' · '+detail)}">${h(text)}</span>`;
}
// N sessions means N close-to-close movements, requiring the previous close
// plus N stored sessions. An invalid endpoint is never skipped or replaced.
function quickSession1346(closes,raw){
 if(!/^[0-9]+$/.test(raw)||!Number.isSafeInteger(Number(raw))||Number(raw)<1)return {error:'Enter a positive whole number of sessions.'};
 const n=Number(raw),len=closes.length;
 if(len<=n)return {error:`Not enough historical records for ${fmtInt(n)} ${n===1?'session':'sessions'}.`};
 const before=closes[len-n-1],first=closes[len-n],last=closes[len-1];
 if(!Number.isFinite(before[1])||before[1]<=0||!Number.isFinite(last[1])||last[1]<=0)return {error:'Closing price unavailable for this period.'};
 return {n,start:first[0],end:last[0],baseline:before[0],change:last[1]-before[1],pct:(last[1]-before[1])*100/before[1]};
}
function quickMovement1346(closes){
 if(closes.length<2)return {status:'unavailable'};
 let i=closes.length-1;
 if(!Number.isFinite(closes[i][1])||!Number.isFinite(closes[i-1][1]))return {status:'unavailable'};
 let dir=Math.sign(closes[i][1]-closes[i-1][1]);
 if(!dir)return {status:'unchanged'};
 let count=0;
 while(i>0){
  if(!Number.isFinite(closes[i][1])||!Number.isFinite(closes[i-1][1]))break;
  if(Math.sign(closes[i][1]-closes[i-1][1])!==dir)break;
  count++;i--;
 }
 const partial=i===0||!Number.isFinite(closes[i-1][1]);
 return {status:dir>0?'positive':'negative',count,partial};
}
function quickSessionUpdate1346(input){
 quickView1343.sessions=input.value;
 const out=document.getElementById('quickSessionResult1346');if(!out)return;
 if(!quickView1343.report){out.textContent='Loading symbol data…';return;}
 const result=quickSession1346(quickView1343.report.closes||[],input.value);
 if(result.error){out.textContent=result.error;return;}
 const sign=result.change>0?'+':'',tone=pnlClass(result.change);
 out.innerHTML=`<strong>${h(fmtInt(result.n))} ${result.n===1?'session':'sessions'}</strong> · ${quickDate1343(result.start)} – ${quickDate1343(result.end)} · Previous close: ${quickDate1343(result.baseline)}<br><span class="${tone}">Net change: <b>${sign}${h(fmtNum(result.change))}</b> · <b>${sign}${h(fmtNum(result.pct))}%</b></span>`;
}
function quickMovementCard1346(r){
 const m=quickMovement1346(r.closes||[]),name=h(r.symbol);
 let text='Movement unavailable',tone='';
 if(m.status==='unchanged')text='Unchanged in the latest trading session';
 if(m.status==='positive'||m.status==='negative'){
  tone=m.status==='positive'?'pos':'neg';
  text=`${m.status==='positive'?'Positive':'Negative'} for ${m.partial?'at least ':''}${fmtInt(m.count)} consecutive trading ${m.count===1?'session':'sessions'}`;
 }
 return `<section class="card quick-move1346"><div class="card-header"><h3>Continuous Movement</h3></div><p class="${tone}"><b>${name}</b> — ${h(text)}</p></section>`;
}
async function renderQuickView1343(container,ticket){
 const current=()=>currentViewRender(container,ticket)&&state.currentView==='market'&&state.market.tab==='quickView';
 const meta=await panelGet1322('/api/v139/market/quick-view/meta');if(!current())return;
 if(!meta.symbols.some(x=>x.symbol===quickView1343.symbol))quickView1343.symbol=meta.symbols.find(x=>x.has_history)?.symbol||meta.symbols[0]?.symbol||'';
 const requested=quickView1343.symbol;
 let html=marketTabs1321('quickView')+`<section class="card filter-bar panels-filter1321 quick-filter1346"><label>Symbol <select id="quickSymbol1343" aria-label="Symbol" data-searchable onchange="quickViewSelect1343(this.value)" ${requested?'':'disabled'}>${meta.symbols.map(x=>`<option value="${h(x.symbol)}" ${x.symbol===requested?'selected':''}>${h(x.symbol)}${x.company?' · '+h(x.company):''}</option>`).join('')}</select></label><label class="quick-sessions1346">Number of Sessions <input id="quickSessions1346" type="number" min="1" step="1" inputmode="numeric" value="${h(quickView1343.sessions)}" oninput="quickSessionUpdate1346(this)" aria-describedby="quickSessionResult1346"></label><div id="quickSessionResult1346" class="quick-session-result1346" aria-live="polite"></div></section>`;
 if(!requested){container.innerHTML=html+'<section class="card">No imported symbols available.</section>';enhanceWorkspace();quickSessionUpdate1346(document.getElementById('quickSessions1346'));return;}
 container.innerHTML=html+'<section class="card" role="status">Loading symbol data…</section>';enhanceWorkspace();quickView1343.report=null;quickSessionUpdate1346(document.getElementById('quickSessions1346'));
 const r=await panelGet1322('/api/v139/market/quick-view/'+encodeURIComponent(requested));if(!current()||requested!==quickView1343.symbol)return;
 // Preserve edits made to the input during the request.
 quickView1343.report=r;
 html+=`<section class="card quick-title1343"><div class="card-header"><h3>${h(r.symbol)} · ${h(r.company||'Company unavailable')}</h3></div><div class="quick-dates1343"><span>First Available Record Date: <b>${quickDate1343(r.first)}</b></span><span>Last Available Record Date: <b>${quickDate1343(r.last)}</b></span></div></section>`;
 html+=`<div class="quick-cards1343">${smallSymbolCard1321(r.card,{}, {hideSelectedSessions:true})}<section class="card"><div class="card-header"><h3>Technical Analysis</h3></div><div class="quick-tech1343">${metric1321('RSI',quickVal1343(r.technical?.rsi))}${['R1','R2','R3','S1','S2','S3'].map(k=>metric1321(k,quickVal1343(r.technical?.pivots?.[k]))).join('')}</div></section></div>`;
 if(r.top10){html+=`<p class="quick-rank1343"><b>${h(r.symbol)}</b> · Top 10 by imported volume · Rank ${h(String(r.top10.rank))} · ${h(fmtInt(r.top10.volume))} shares · ${quickDate1343(r.market_date)}</p>`;}
 if(r.top5_block){html+=`<div class="quick-top5-wrap1344">${renderTop5Block1344(r.top5_block)}</div>`;}
 html+=quickMovementCard1346(r);
 const metrics=[['max_high','Maximum High','pos'],['max_close','Maximum Closing','pos'],['min_low','Minimum Low','neg'],['min_close','Minimum Closing','neg'],['max_average','Maximum Average',''],['min_average','Minimum Average',''],['max_volume','Maximum Volume',''],['min_volume','Minimum Volume','']];
 const headings=metrics.map(([,label])=>`<th scope="col" class="num">${h(label)}</th>`).join('');
 const labels=['7 Days','14 Days','30 Days','90 Days','180 Days','1 Year','All-Time High Since 1 October 2023','All-Time High Since 27 February 2026'];
 const rows=labels.map((label,i)=>{const row=r.ranges[i];const cells=metrics.map(([key,,tone])=>{const val=row?.metrics?.[key];return `<td class="num"><span class="quick-value1344 ${val?.value==null?'':tone}">${quickVal1343(val?.value,key.includes('volume'))}</span><small class="quick-date1344">${quickDate1343(val?.date)}</small></td>`}).join('');return `<tr><th scope="row">${h(label)}</th>${cells}<td class="num ${row?.upper_lock_coverage?.count==null?'':'pos'}">${quickLock1345(row?.upper_lock_coverage)}</td><td class="num ${row?.lower_lock_coverage?.count==null?'':'neg'}">${quickLock1345(row?.lower_lock_coverage)}</td></tr>`;}).join('');
 html+=`<section class="card"><div class="card-header"><h3>Historical Price and Volume Analysis</h3><span>Through ${quickDate1343(r.last)} · Scroll to see all columns →</span></div><div class="table-wrap quick-table1343" tabindex="0" role="region" aria-label="Scrollable historical price and volume statistics"><table class="data-table"><thead><tr><th scope="col">Historical Range</th>${headings}<th scope="col" class="num">Upper Lock Count<br><small>Est. touch</small></th><th scope="col" class="num">Lower Lock Count<br><small>Est. touch</small></th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
 container.innerHTML=html;enhanceWorkspace();const input=document.getElementById('quickSessions1346');input.value=quickView1343.sessions;quickSessionUpdate1346(input);
}
