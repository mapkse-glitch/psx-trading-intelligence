/* Imported-only performance. One bounded report, revision-scoped cache, no CDN. */
const perfTabs1325=[['daily','Daily'],['weekly','Weekly'],['monthly','Monthly'],['quarterly','Quarterly'],['halfyear','Half Year'],['ninemonth','Nine Month Ended'],['yearly','Yearly']];
state.performance={kind:'daily',keys:{},report:null};
function perfTabsHtml1325(){return `<div class="subtabs" role="group" aria-label="Market Performance periods">${perfTabs1325.map(([id,name])=>`<button class="subtab-btn ${state.performance.kind===id?'active':''}" aria-pressed="${state.performance.kind===id}" onclick="changePerformance1325('${id}')">${name}</button>`).join('')}</div>`;}
function changePerformance1325(kind,key){clearCalendarNotice1311();state.performance.kind=kind;if(key!==undefined)state.performance.keys[kind]=key||null;return renderPerformance1325(document.getElementById('viewContainer'));}
function perfCompact1325(value){if(value==null)return 'Not available';const abs=Math.abs(value);if(abs<1e-9)return '0';return abs>=1e9?fmtNum(value/1e9,1)+'B':abs>=1e6?fmtNum(value/1e6,1)+'M':abs>=1e3?fmtNum(value/1e3,1)+'K':fmtNum(value,abs<10?2:0);}
function perfValue1325(value,unit){return value==null?'Not available':unit==='shares'?fmtInt(value):fmtNum(value)+(unit==='%'?'%':'');}
function perfChart1325(chart){
 const rows=chart.rows, note=chart.unavailable?'Import the KSE100 membership sheet to enable this chart.':!rows.length?'No eligible '+(chart.tone==='neg'?'losers':chart.tone==='pos'?'gainers':'volume leaders')+' in this period.':null;
 const heading=`<header class="performance-chart-head1325"><h3>${h(chart.title)}</h3><span>${h(chart.unit)}</span></header>`;
 if(note)return `<article class="card performance-chart1325">${heading}<p class="performance-empty1325">${h(note)}</p></article>`;
 const W=Math.max(600,rows.length*68+94),H=335,L=76,R=W-18,T=36,B=224,step=(R-L)/rows.length;
 const negative=chart.tone==='neg',max=Math.max(...rows.map(r=>Math.abs(r.value)),1)*1.16;
 const y=v=>negative?T+Math.abs(v)/max*(B-T):B-v/max*(B-T),zero=negative?T:B;
 let svg=`<svg viewBox="0 0 ${W} ${H}" style="min-width:${W}px" role="img" aria-label="${h(chart.title)}. ${rows.length} leaders. Exact figures in chart data.">`;
 for(let n=0;n<=4;n++){const v=max*n/4,yy=negative?T+(B-T)*n/4:B-(B-T)*n/4;svg+=`<line class="performance-grid1325" x1="${L}" x2="${R}" y1="${yy}" y2="${yy}"/><text class="performance-axis1325" x="${L-9}" y="${yy+4}" text-anchor="end">${h(perfCompact1325(negative?-v:v))}</text>`;}
 rows.forEach((r,i)=>{const x=L+step*(i+.5),yy=y(r.value),height=Math.abs(yy-zero),full=`${r.name}: ${perfValue1325(r.value,chart.unit)}${r.eligible!=null?`; ${r.eligible} of ${r.members} members`:''}`;
 svg+=`<g class="performance-bar1325" tabindex="0" role="img" aria-label="${h(full)}"><title>${h(full)}</title><rect class="performance-fill-${chart.tone}1325" x="${x-step*.31}" y="${Math.min(yy,zero)}" width="${step*.62}" height="${Math.max(1,height)}" rx="3"/><text class="performance-value1325" x="${x}" y="${negative?yy+15:yy-8}" text-anchor="middle">${h(perfCompact1325(r.value))}${chart.unit==='%'?'%':''}</text></g>`;
 const short=r.name.length>24?r.name.slice(0,22)+'…':r.name;svg+=`<text class="performance-category1325" transform="translate(${x},${B+31}) rotate(30)" text-anchor="start"><title>${h(r.name)}</title>${h(short)}</text>`;
 });svg+='</svg>';
 return `<article class="card performance-chart1325">${heading}<div class="performance-plot1325" tabindex="0" role="region" aria-label="Scrollable ${h(chart.title)}">${svg}</div><p class="performance-scroll1325">Scroll chart horizontally for all labels · focus a column for its exact value</p><details class="performance-data1325" data-chart="${h(chart.id)}" ontoggle="perfData1325(this)"><summary>Chart data · ${rows.length} ${rows.length===1?'leader':'leaders'}</summary><div class="performance-table1325"></div></details></article>`;
}
const perfStackColors1325=['#3979D6','#86B8F7','#9764C9','#D4A72C','#5DB3B6','#8795AA','#C777A1'];
function perfCombo1325(combo,kind){
 if(!combo)return '';
 const rows=combo.buckets,W=Math.max(780,rows.length*48+150),H=335,L=82,R=W-88,T=35,B=251;
 const maxV=Math.max(...rows.map(r=>r.volume||0),1)*1.12;
 const changes=rows.map(r=>r.index_change).filter(v=>v!=null),minP=Math.min(0,...changes),maxP=Math.max(0,...changes),pad=Math.max((maxP-minP)*.12,1),low=minP-pad,high=maxP+pad;
 const yP=v=>B-(v-low)/(high-low)*(B-T),yV=v=>B-v/maxV*(B-T),step=(R-L)/Math.max(1,rows.length);
 let svg=`<svg viewBox="0 0 ${W} ${H}" style="min-width:${W}px" role="img" aria-label="Index change in points as a line, and imported cash-market volume as stacked sector columns"><text class="performance-axis1325" x="${L}" y="17">Index change · points</text><text class="performance-axis1325" x="${R}" y="17" text-anchor="end">Volume · shares</text>`;
 for(let i=0;i<=4;i++){const yy=T+(B-T)*i/4;svg+=`<line class="performance-grid1325" x1="${L}" x2="${R}" y1="${yy}" y2="${yy}"/><text class="performance-axis1325" x="${L-8}" y="${yy+4}" text-anchor="end">${h(perfCompact1325(high-(high-low)*i/4))}</text><text class="performance-axis1325" x="${R+8}" y="${yy+4}">${h(perfCompact1325(maxV*(1-i/4)))}</text>`;}
 let path='',pen=false;
 rows.forEach((r,i)=>{const x=L+step*(i+.5);let cumulative=0;
  if(r.sectors){combo.sectors.forEach((s,j)=>{const v=r.sectors[s]||0,yy=yV(cumulative+v),hh=(B-T)*v/maxV;
   if(v)svg+=`<rect class="performance-stack1325" tabindex="0" x="${x-step*.29}" y="${yy}" width="${step*.58}" height="${hh}" fill="${perfStackColors1325[j%perfStackColors1325.length]}"><title>${h(fmtDate(r.date)+' · '+s+': '+fmtInt(v)+' shares')}</title></rect>`;cumulative+=v;});}
  else svg+=`<text class="performance-axis1325" x="${x}" y="${B-8}" text-anchor="middle">—</text>`;
  if(r.index_change!=null){path+=`${pen?'L':'M'}${x},${yP(r.index_change)} `;pen=true;}else pen=false;
  const label=kind==='weekly'||kind==='monthly'?fmtDate(r.date).replace(/ \d{4}$/,''):fmtDate(r.date).replace(/^\d+ /,'');
  svg+=`<text class="performance-category1325" transform="translate(${x},${B+22}) rotate(35)" text-anchor="start">${h(label)}</text>`;
 });
 svg+=`<path class="performance-line1325" d="${path}"/>`;
 rows.forEach((r,i)=>{if(r.index_change!=null)svg+=`<circle class="performance-dot1325" tabindex="0" cx="${L+step*(i+.5)}" cy="${yP(r.index_change)}" r="4"><title>${h(fmtDate(r.date)+': '+fmtNum(r.index_change)+' points; '+(r.volume==null?'volume unavailable':fmtInt(r.volume)+' shares')+'; index date '+fmtDate(r.index_date)+'; baseline '+fmtDate(r.baseline_date))}</title></circle>`;});svg+='</svg>';
 return `<article class="card performance-combo1325"><header class="performance-chart-head1325"><h3>Index change &amp; sector volume</h3><span>${kind==='weekly'||kind==='monthly'?'Daily':'Monthly'} observations</span></header><div class="performance-legend1325"><span><i class="performance-line-key1325"></i>Index change · points (left axis)</span>${combo.sectors.map((s,j)=>`<span><i style="background:${perfStackColors1325[j%perfStackColors1325.length]}"></i>${h(s)}</span>`).join('')}</div><div class="performance-plot1325" tabindex="0" role="region" aria-label="Scrollable index change and volume chart">${svg}</div><p class="performance-note1325">${h(combo.volume_source)} (right axis). Missing observations are gaps, not zero. Index changes use each bucket’s last close versus the last stored close before it began.</p><details class="performance-data1325" data-chart="combo" ontoggle="perfData1325(this)"><summary>Chart data &amp; source dates</summary><div class="performance-table1325"></div></details></article>`;
}
function perfData1325(details){if(!details.open||details.dataset.ready)return;const r=state.performance.report;if(!r)return;const box=details.querySelector('.performance-table1325');let headers,rows;
 if(details.dataset.chart==='combo'){headers=['Period start','Index date','Baseline date','Index change (pts)','Imported volume',...r.combo.sectors];rows=r.combo.buckets.map(x=>[fmtDate(x.date),fmtDate(x.index_date),fmtDate(x.baseline_date),number1321(x.index_change),x.volume==null?'Not available':fmtInt(x.volume),...r.combo.sectors.map(s=>x.sectors?fmtInt(x.sectors[s]):'Not available')]);}
 else {const ch=r.charts.find(x=>x.id===details.dataset.chart);if(!ch)return;headers=['Scrip / sector',`Value (${ch.unit})`,'Coverage / baseline'];rows=ch.rows.map(x=>[h(x.name),perfValue1325(x.value,ch.unit),x.eligible!=null?`${x.eligible} / ${x.members} members`:x.baseline_date?fmtDate(x.baseline_date)+' → '+fmtDate(x.date):'Imported cash volume']);}
 box.innerHTML=smallTable(headers,rows);details.dataset.ready='1';enhanceWorkspace();
}
async function renderPerformance1325(container){
 const ticket=beginViewRender(container),s=state.performance,kind=s.kind,key=s.keys[kind]||null;
 const current=()=>currentViewRender(container,ticket)&&s.kind===kind&&(s.keys[kind]||null)===key;
 s.report=null;container.innerHTML=perfTabsHtml1325()+'<section class="card performance-loading1325" role="status">Loading imported market performance…</section>';
 try{
  const params=new URLSearchParams({period:kind});if(key)params.set('key',key);
  const r=await panelGet1322('/api/v139/market-performance?'+params);if(!current())return;
  s.report=r;
  if(r.status!=='OK'){container.innerHTML=perfTabsHtml1325()+'<section class="card"><h3>No eligible period available</h3><p>No imported dates are eligible for this period type. Weekly periods use Monday–Friday; fiscal nine-month periods use July–March. Import authentic cash and KSE100 index data through the existing Import and Update Center. No sample records are substituted.</p></section>';enhanceWorkspace();return;}
  const titles={daily:'Date',weekly:'Year / week · Monday–Friday',monthly:'Month',quarterly:'Fiscal quarter',halfyear:'Fiscal half-year',ninemonth:'Nine months ended',yearly:'Fiscal year'};
  const filter=kind==='daily'?`<input type="date" aria-label="Performance date" value="${h(r.selected)}" min="${h(r.options[r.options.length-1].key)}" max="${h(r.options[0].key)}" onchange="changePerformance1325('daily',this.value)">`:`<select aria-label="${h(titles[kind])}" onchange="changePerformance1325('${kind}',this.value)">${r.options.map(o=>`<option value="${h(o.key)}" ${r.selected===o.key?'selected':''}>${h(o.label)}${kind==='weekly'?' · '+fmtDate(o.start)+' – '+fmtDate(o.end):''}</option>`).join('')}</select>`;
  const idx=r.index,tone=pnlClass(idx.change),word=idx.change==null?'Comparison unavailable':idx.change>0?'UP':idx.change<0?'DOWN':'UNCHANGED';
  const periodHeading=kind==='daily'?fmtDate(r.selected):kind==='weekly'?'Week ended '+fmtDate(r.end):kind==='monthly'?'Month ended '+r.label:({quarterly:'Quarter ended ',halfyear:'Half-year ended ',ninemonth:'Nine months ended ',yearly:'Year ended '})[kind]+fmtDate(r.end)+' · '+r.label;
  const periodTag={daily:'DoD',weekly:'WoW',monthly:'MoM',quarterly:'QoQ',halfyear:'Period',ninemonth:'Period',yearly:'FY'}[kind];
  let html=perfTabsHtml1325()+`<section class="card filter-bar performance-filter1325"><label>${h(titles[kind])} ${filter}</label><span>Fiscal year: Jul–Jun · Weeks: Mon–Fri</span>${key?`<button class="btn btn-secondary" onclick="changePerformance1325('${kind}',null)">Latest period</button>`:''}</section>`;
  html+=`<section class="card performance-hero1325"><div><div class="eyebrow">MARKET PERFORMANCE ${r.partial?'· PARTIAL PERIOD':''}</div><h2>Market Performance of ${h(periodHeading)}</h2><p>${fmtDate(r.start)} – ${fmtDate(r.end)}${r.requested&&r.requested!==r.selected?' · Requested '+h(fmtDate(r.requested))+'; last available session shown':''}</p><span class="badge ${r.partial?'badge-amber':'badge-green'}">${r.partial?'Incomplete imported period':'Final weekday reached · import coverage applies'}</span></div><div class="performance-index1325"><span>KSE100 index · ${idx.date?fmtDate(idx.date):'No period quote'}</span><strong class="${tone}">${number1321(idx.close)} <small>points</small></strong><b class="${tone}">${word}${idx.change!=null?' by '+fmtNum(Math.abs(idx.change))+' pts | '+fmtPct(idx.pct,false):''}</b><small>${periodTag} · Baseline ${idx.baseline_date?fmtDate(idx.baseline_date):'unavailable'}</small></div></section>`;
  html+=`<div class="performance-stats1325"><span>Cash through <b>${r.cash_as_of?fmtDate(r.cash_as_of):'unavailable'}</b></span><span>Imported volume <b>${fmtInt(r.coverage.volume)} shares</b></span><span>KSE100 returns <b>${r.coverage.eligible} / ${r.coverage.members} members</b></span></div>`;
  html+=`<details class="card performance-method1325"><summary>Calculation &amp; coverage${r.warnings.length?' · '+r.warnings.length+' notes':''}</summary><p>${h(r.method)}</p><p>Cash coverage: ${r.cash_first?fmtDate(r.cash_first):'unavailable'} – ${r.cash_as_of?fmtDate(r.cash_as_of):'unavailable'}. Membership: ${h(r.coverage.membership_source||'not imported')}.</p><ul>${r.warnings.map(x=>`<li>${h(x)}</li>`).join('')}</ul></details>`;
  if(!r.coverage.members)html+='<p class="performance-warning1325" role="status">Imported KSE100 membership is missing. Volume charts remain available; KSE100 return charts are not fabricated.</p>';
  html+='<div class="performance-grid-layout1325">'+r.charts.map(perfChart1325).join('')+'</div>'+perfCombo1325(r.combo,kind);
  container.innerHTML=html;enhanceWorkspace();
 }catch(error){if(current()){s.report=null;container.innerHTML=perfTabsHtml1325()+`<section class="card"><h3>Performance could not be loaded</h3><p>${h(error.message)}</p><button class="btn btn-secondary" onclick="renderPerformance1325(document.getElementById('viewContainer'))">Retry</button><button class="btn btn-secondary" onclick="changePerformance1325('${kind}',null)">Latest period</button></section>`;}}
}
function exportPerformance1325(){
 const r=state.performance.report;if(!r||r.status!=='OK'){showToast('Load a market performance period before exporting.');return;}
 const rows=[['Market Performance',r.label],['Period start',r.start,'Period end',r.end],['Cash date',r.cash_as_of,'Index date',r.index.date],['Index close',r.index.close,'Change (pts)',r.index.change,'Change (%)',r.index.pct],['Method',r.method],...r.warnings.map(x=>['Coverage',x])];
 r.charts.forEach(ch=>{rows.push([], [ch.title],['Scrip / sector',`Value (${ch.unit})`,'Baseline date','End date','Eligible members','Sector members']);ch.rows.forEach(x=>rows.push([x.name,x.value,x.baseline_date,x.date,x.eligible,x.members]));});
 if(r.combo){rows.push([],['Index change and imported sector volume'],['Bucket start','Index date','Baseline date','Index change (pts)','Volume',...r.combo.sectors]);r.combo.buckets.forEach(x=>rows.push([x.date,x.index_date,x.baseline_date,x.index_change,x.volume,...r.combo.sectors.map(s=>x.sectors?.[s]??null)]));}
 const safe=value=>{let s=value==null?'':String(value);if(typeof value==='string'&&/^[\s]*[=+\-@\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};
 const blob=new Blob(['\uFEFF'+rows.map(row=>row.map(safe).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='Market_Performance_'+r.selected+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
