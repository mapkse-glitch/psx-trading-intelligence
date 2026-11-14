/* Daily volume is derived from imported cash rows; index changes use index sessions. */
const volumeIndex1339=state.market.volumeIndex1339={start:'',end:''};
function volumeIndexSet1339(key,value){volumeIndex1339[key]=value;marketRefresh139();}
function cardinalPath1339(points){
 if(!points.length)return '';
 let path=`M ${points[0][0]} ${points[0][1]}`;
 for(let i=0;i<points.length-1;i++){
  const p0=points[Math.max(0,i-1)],p1=points[i],p2=points[i+1],p3=points[Math.min(points.length-1,i+2)];
  // Cardinal spline with tension 0.5; separate segments preserve missing sessions.
  const k=1/12;
  path+=` C ${(p1[0]+(p2[0]-p0[0])*k).toFixed(2)} ${(p1[1]+(p2[1]-p0[1])*k).toFixed(2)} ${(p2[0]-(p3[0]-p1[0])*k).toFixed(2)} ${(p2[1]-(p3[1]-p1[1])*k).toFixed(2)} ${p2[0].toFixed(2)} ${p2[1].toFixed(2)}`;
 }
 return path;
}
function volumeIndexGraph1339(rows, options={}){
 if(!rows.length)return '<p>No cash-market records in the selected period.</p>';
 const W=Math.max(900,rows.length*32+150),H=380,L=90,R=W-95,T=45,B=310;
 const width=R-L,spacing=width/rows.length,x=i=>L+spacing*(i+.5),maxVol=Math.max(1,...rows.map(r=>r.volume||0));
 const vals=rows.map(r=>r.index_change).filter(v=>v!==null&&Number.isFinite(v));
 let lo=Math.min(0,...vals),hi=Math.max(0,...vals);if(lo===hi){lo-=1;hi+=1;}else {let pad=(hi-lo)*.08;lo-=pad;hi+=pad;}
 const y=v=>B-(v-lo)/(hi-lo)*(B-T),yv=v=>B-(v/maxVol)*(B-T);
 let svg=`<svg viewBox="0 0 ${W} ${H}" style="min-width:${W}px" role="img" aria-label="${h(options.label||'Daily market volume and index change')}"><text x="${L}" y="20" class="analytic-axis1335">Volume (shares)</text><text x="${R}" y="20" text-anchor="end" class="analytic-axis1335">Index change (points)</text>`;
 for(let j=0;j<=4;j++){const yy=T+(B-T)*j/4,vol=maxVol*(1-j/4),change=hi-(hi-lo)*j/4;svg+=`<line class="analytic-grid1335" x1="${L}" x2="${R}" y1="${yy}" y2="${yy}"/><text class="analytic-axis1335" text-anchor="end" x="${L-8}" y="${yy+4}">${h(fmtInt(Math.round(vol)))}</text><text class="analytic-axis1335" x="${R+8}" y="${yy+4}">${h(fmtNum(change))}</text>`;}
 let segments=[],seg=[];
 rows.forEach((r,i)=>{const v=r.volume,delta=r.index_change,xx=x(i),tone=delta==null?'neutral':delta>0?'up':delta<0?'down':'neutral';const volumeText=v==null?'Unavailable':fmtInt(v)+' shares';const tip=`${fmtDate(r.date)} · Volume ${volumeText} · Index change ${delta==null?'Unavailable':fmtNum(delta)+' points'}`;
 const bw=Math.min(22,spacing*.7),top=yv(v),barHeight=Math.max(0,B-top);
 if(v!=null)svg+=`<rect class="analytic-bar-${tone}1335" x="${(xx-bw/2).toFixed(2)}" y="${top.toFixed(2)}" width="${bw.toFixed(2)}" height="${barHeight.toFixed(2)}" tabindex="0" data-chart-tip1329="${h(tip)}" aria-label="${h(tip)}"><title>${h(tip)}</title></rect>`;else svg+=`<text class="analytic-axis1335" x="${xx}" y="${B-8}" text-anchor="middle"><title>Volume unavailable</title>—</text>`;
 if(delta==null){if(seg.length)segments.push(seg);seg=[];}else{seg.push([xx,y(delta)]);}
 });if(seg.length)segments.push(seg);
 svg+=segments.map(points=>`<path class="index-line-halo1340" d="${cardinalPath1339(points)}"/><path d="${cardinalPath1339(points)}" fill="none" stroke="var(--index-line1340)" stroke-width="2"/>`).join('');
 rows.forEach((r,i)=>{if(r.index_change==null)return;const tip=`${fmtDate(r.date)} · Volume ${r.volume==null?'Unavailable':fmtInt(r.volume)+' shares'} · Index change ${fmtNum(r.index_change)} points`;svg+=`<circle cx="${x(i).toFixed(2)}" cy="${y(r.index_change).toFixed(2)}" r="3" class="volume-index-dot1340" tabindex="0" data-chart-tip1329="${h(tip)}" aria-label="${h(tip)}"><title>${h(tip)}</title></circle>`;});
 const step=Math.max(1,Math.ceil(115/spacing));rows.forEach((r,i)=>{if(i%step===0)svg+=`<text class="analytic-axis1335" x="${x(i)}" y="${B+23}" text-anchor="middle">${h(fmtDate(r.date))}</text>`;});
 svg+=`<text class="analytic-axis1335" x="${(L+R)/2}" y="${H-10}" text-anchor="middle">${h(options.xLabel||'Trading date')}</text></svg>`;return svg;
}
async function renderDailyVolumeIndex1339(container,ticket){
 const s=volumeIndex1339,meta=await panelGet1322('/api/v139/market/meta');
 if(!currentViewRender(container,ticket)||state.market.tab!=='dailyVolumeIndex')return;
 const dates=[...meta.dates].sort();if(!dates.length){container.innerHTML=marketTabs1321('dailyVolumeIndex')+'<section class="card">No imported cash-market history available.</section>';enhanceWorkspace();return;}
 if(!s.end)s.end=dates.at(-1);if(!s.start)s.start=dates[Math.max(0,dates.length-60)];
 const controls=`<section class="card compare-filters1333"><div class="card-header"><h3>Daily Volume and Index Changes</h3><span>${h(fmtDate(s.start))} – ${h(fmtDate(s.end))}</span></div><div class="compare-fields1333"><label>Start Date <input type="date" value="${h(s.start)}" onchange="volumeIndexSet1339('start',this.value)"></label><label>End Date <input type="date" value="${h(s.end)}" onchange="volumeIndexSet1339('end',this.value)"></label></div></section>`;
 if(!s.start||!s.end||s.start>s.end){container.innerHTML=marketTabs1321('dailyVolumeIndex')+controls+'<section class="card" role="alert">Choose a valid start and end date.</section>';enhanceWorkspace();return;}
 const q=new URLSearchParams({start:s.start,end:s.end}),snapshot=q.toString(),r=await panelGet1322('/api/v139/market/daily-volume-index?'+snapshot);
 if(!currentViewRender(container,ticket)||state.market.tab!=='dailyVolumeIndex'||new URLSearchParams({start:s.start,end:s.end}).toString()!==snapshot)return;
 container.innerHTML=marketTabs1321('dailyVolumeIndex')+controls+`<section class="card analytic-card1335"><div class="card-header"><h3>Daily market volume and index changes</h3></div><div class="analytic-legend1335"><span class="pos">■ Index up</span> · <span class="neg">■ Index down</span> · ■ Unchanged or unavailable · <span><span class="index-key1340" aria-hidden="true">━</span> Index change</span></div><div class="analytic-plot1335" tabindex="0" role="region" aria-label="Scrollable daily volume and index chart">${volumeIndexGraph1339(r.rows)}</div></section>`;enhanceWorkspace();
}
