const topVolume1339={date:'',symbol:'',sort:'rank',direction:'asc'};
function topVolumeSet1339(k,v){topVolume1339[k]=v;return renderTopVolume1339(document.getElementById('viewContainer'));}
function topVolumeSort1339(k){const s=topVolume1339;if(s.sort===k)s.direction=s.direction==='asc'?'desc':'asc';else{s.sort=k;s.direction='asc';}return renderTopVolume1339(document.getElementById('viewContainer'));}
async function renderTopVolume1339(container){
 const ticket=beginViewRender(container),s=topVolume1339;container.setAttribute('aria-busy','true');
 try{
  const meta=await panelGet1322('/api/v139/market/meta');if(!currentViewRender(container,ticket)||state.currentView!=='records'||records1339.tab!=='topvolumes')return;
  if(!s.date)s.date=meta.dates[0]||'';
  if(!s.date){container.innerHTML=recordsTabs1339()+'<section class="card">No imported cash-market records available.</section>';return;}
  const params=new URLSearchParams({date:s.date,symbol:s.symbol}),snapshot=params.toString(),r=await panelGet1322('/api/v139/top-symbol-volumes?'+snapshot);
  if(!currentViewRender(container,ticket)||state.currentView!=='records'||records1339.tab!=='topvolumes'||new URLSearchParams({date:s.date,symbol:s.symbol}).toString()!==snapshot)return;
  const headings=[['rank','Rank'],['symbol','Symbol'],['volume','Trading Volume'],['trade_date','Date'],['close','Trading Rate (Close)']];
  const th=headings.map(([k,v])=>`<th${['rank','volume','close'].includes(k)?' class="num"':''} aria-sort="${s.sort===k?(s.direction==='asc'?'ascending':'descending'):'none'}"><button class="text-button" onclick="topVolumeSort1339('${k}')">${h(v)}${s.sort===k?(s.direction==='asc'?' ▲':' ▼'):''}</button></th>`).join('');
  const rows=r.rows.map((x,i)=>({...x,rank:i+1})).sort((a,b)=>{let x=a[s.sort],y=b[s.sort];return (x==null?1:y==null?-1:typeof x==='number'?x-y:String(x).localeCompare(String(y)))*(s.direction==='asc'?1:-1)||a.rank-b.rank;}).map(x=>`<tr><td class="num">${x.rank}</td><td>${h(x.symbol)}</td><td class="num">${fmtInt(x.volume)}</td><td>${h(fmtDate(x.trade_date))}</td><td class="num">${fmtNum(x.close)}</td></tr>`).join('');
  container.innerHTML=recordsTabs1339()+`<section class="card filter-bar compare-fields1333"><label>Date <input type="date" value="${h(s.date)}" onchange="topVolumeSet1339('date',this.value)"></label><label>Symbol <select aria-label="Symbol" onchange="topVolumeSet1339('symbol',this.value)"><option value="">All symbols</option>${meta.symbols.map(x=>`<option value="${h(x)}" ${s.symbol===x?'selected':''}>${h(x)}</option>`).join('')}</select></label></section><section class="card"><div class="card-header"><h3>Top Symbol Volumes</h3><span>${h(fmtDate(s.date))}</span></div><div class="table-wrap" tabindex="0" role="region" aria-label="Top volume records"><table class="data-table"><thead><tr>${th}</tr></thead><tbody>${rows||'<tr><td colspan="5">No records match the selected filters.</td></tr>'}</tbody></table></div></section>`;enhanceWorkspace();
 }catch(error){if(currentViewRender(container,ticket))container.innerHTML=recordsTabs1339()+`<section class="card" role="alert"><h3>Volume records unavailable</h3><button class="btn btn-secondary" onclick="renderTopVolume1339(document.getElementById('viewContainer'))">Retry</button></section>`;}
 finally{if(currentViewRender(container,ticket))container.removeAttribute('aria-busy');}
}
