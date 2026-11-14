const records1339={tab:'highs',date:'',sort:'symbol',direction:'asc',page:1};
function recordsSet1339(k,v){records1339[k]=v;if(k!=='page')records1339.page=1;return renderRecords1339(document.getElementById('viewContainer'));}
function recordsSort1339(k){const s=records1339;if(s.sort===k)s.direction=s.direction==='asc'?'desc':'asc';else{s.sort=k;s.direction='asc';}s.page=1;return renderRecords1339(document.getElementById('viewContainer'));}
async function renderRecords1339(container){
 const ticket=beginViewRender(container),s=records1339;container.setAttribute('aria-busy','true');
 try{
  const meta=await panelGet1322('/api/v139/market/meta');if(!currentViewRender(container,ticket)||state.currentView!=='records')return;
  if(!s.date)s.date=meta.dates[0]||'';
  let data=null;if(s.tab==='highs'&&s.date){const date=s.date;data=await panelGet1322('/api/v139/records/new-highs?'+new URLSearchParams({date}));if(!currentViewRender(container,ticket)||state.currentView!=='records'||s.tab!=='highs'||s.date!==date)return;}
  const tabs=[['highs','List of New High'],['caps','Upper Cap & Lower Cap'],['splits','List of Split Shares']].map(([id,name])=>`<button class="subtab-btn ${s.tab===id?'active':''}" aria-pressed="${s.tab===id}" onclick="recordsSet1339('tab','${id}')">${h(name)}</button>`).join('');
  const filter=s.tab==='splits'?'':`<section class="card filter-bar"><label>Date <input type="date" value="${h(s.date)}" onchange="recordsSet1339('date',this.value)"></label></section>`;
  let body='';
  if(s.tab==='highs'){
   const fields=[['symbol','Symbol'],['company','Company Name'],['price','Current / Record High Price'],['previous','Previous High Price'],['record_type','Record Type'],['date','Date']];
   const heads=fields.map(([k,n])=>`<th${k==='price'||k==='previous'?' class="num"':''} aria-sort="${s.sort===k?(s.direction==='asc'?'ascending':'descending'):'none'}"><button class="text-button" onclick="recordsSort1339('${k}')">${h(n)}${s.sort===k?(s.direction==='asc'?' ▲':' ▼'):''}</button></th>`).join('');
   const all=(data?.rows||[]).slice().sort((a,b)=>{let x=a[s.sort],y=b[s.sort];return (x==null?1:y==null?-1:typeof x==='number'?x-y:String(x).localeCompare(String(y)))*(s.direction==='asc'?1:-1)||a.symbol.localeCompare(b.symbol)||a.record_type.localeCompare(b.record_type)}),pages=Math.max(1,Math.ceil(all.length/50));s.page=Math.min(s.page,pages);
   const rows=all.slice((s.page-1)*50,s.page*50).map(x=>`<tr><td>${h(x.symbol)}</td><td>${h(x.company||'Unavailable')}</td><td class="num">${fmtNum(x.price)}${x.closing_ath?newClosing1338(true):''}</td><td class="num">${fmtNum(x.previous)}</td><td>${h(x.record_type)}</td><td>${h(fmtDate(x.date))}</td></tr>`).join('');
   body=`<section class="card"><div class="card-header"><h3>List of New High</h3><span>${fmtInt(all.length)} records</span></div><div class="table-wrap" tabindex="0" role="region" aria-label="New highs"><table class="data-table"><thead><tr>${heads}</tr></thead><tbody>${rows||'<tr><td colspan="6">No new records available for this date.</td></tr>'}</tbody></table></div><div class="daily-pages1331"><button class="btn btn-secondary" onclick="recordsSet1339('page',${s.page-1})" ${s.page<=1?'disabled':''}>Previous</button><span>Page ${s.page} of ${pages}</span><button class="btn btn-secondary" onclick="recordsSet1339('page',${s.page+1})" ${s.page>=pages?'disabled':''}>Next</button></div></section>`;
  }else if(s.tab==='caps')body='<section class="card"><h3>Upper Cap &amp; Lower Cap</h3><p>Historical per-symbol exchange limits are unavailable.</p></section>';
  else body='<section class="card"><h3>List of Split Shares</h3><p>Stock-split records are unavailable.</p></section>';
  container.innerHTML=`<div class="subtabs" role="group" aria-label="Records tabs">${tabs}</div>${filter}${body}`;enhanceWorkspace();
 }catch(e){if(currentViewRender(container,ticket))container.innerHTML='<section class="card" role="alert"><h3>Records unavailable</h3><button class="btn btn-secondary" onclick="renderRecords1339(document.getElementById(\'viewContainer\'))">Retry</button></section>';}
 finally{if(currentViewRender(container,ticket))container.removeAttribute('aria-busy');}
}
