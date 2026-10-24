/* Display helpers only. Dates/identifiers remain neutral; absent data is never zero-filled. */
function resolveCalendar1311(requested, dates) {
 if(!/^\d{4}-\d{2}-\d{2}$/.test(requested)||!Number.isFinite(Date.parse(requested+'T12:00:00Z'))||new Date(requested+'T12:00:00Z').toISOString().slice(0,10)!==requested)return null;
 return [...new Set(dates)].sort().reverse().find(d=>d<=requested)||null;
}
function clearCalendarNotice1311(){if(state.calendarNotices)delete state.calendarNotices[state.currentView];}
function calendarChoice1311(requested,dates){
 const selected=resolveCalendar1311(requested,dates);
 if(!selected){showToast('No stored trading day on or before this date. Choose a date within the available history.',true);return null;}
 state.calendarNotices=state.calendarNotices||{};
 state.calendarNotices[state.currentView]=selected!==requested?`Selected ${fmtDate(requested)}. No stored trading day matches; showing ${fmtDate(selected)}, the most recent available day BEFORE your selection. No later data is substituted.`:'';
 return selected;
}
async function marketCalendar1311(value){
 try{const meta=await apiGet('/api/v139/market/meta',false);const selected=calendarChoice1311(value,meta.dates);if(selected)state.market.date=selected;marketRefresh139();}catch(e){showToast(e.message,true);}
}
function accountCalendar1311(account,value,dates){const selected=calendarChoice1311(value,dates);if(selected)openAccountDateDetail(account,selected);else renderAccountView(document.getElementById('viewContainer'),account);}
function futuresCalendar1311(tab,value,dates){const selected=calendarChoice1311(value,dates);if(selected){state.futures[tab].date_manual=true;state.futures[tab].selected_date=selected;}renderFuturesView(document.getElementById('viewContainer'));}
function numericValue1311(text){
 const clean=String(text).trim().replace(/\u2212/g,'-');
 if(!/^[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:%|\s*(?:PKR|M|K))?$/.test(clean))return null;
 return Number(clean.replace(/[, %]|PKR|M|K/g,''));
}
function enhanceDisplay1311(root){
 let notice=root.querySelector('#calendarNotice1311');const msg=state.calendarNotices?.[state.currentView];
 if(msg){if(!notice){notice=document.createElement('p');notice.id='calendarNotice1311';notice.className='card calendar-notice';notice.setAttribute('role','status');root.prepend(notice);}if(notice.textContent!==msg)notice.textContent=msg;}else notice?.remove();
 root.querySelectorAll('table').forEach(table=>{
 const headers=[...(table.tHead?.rows[0]?.cells||[])].map(el=>el.textContent.trim());
 table.querySelectorAll('tbody tr,tfoot tr').forEach(row=>[...row.cells].forEach((cell,i)=>{
  const header=headers[i]||'';
  if(/date|time|year|month|symbol|stock|account|order.*id|execution.*id|batch|version|rank|^id$|indicator votes|rule score|check after/i.test(header))return;
  const value=numericValue1311(cell.textContent);
  if(value!==null){cell.classList.toggle('pos',value>0);cell.classList.toggle('neg',value<0);}
 }));
 });
 root.querySelectorAll('.kpi-value').forEach(el=>{const val=numericValue1311(el.textContent);if(val!==null){el.classList.toggle('pos',val>0);el.classList.toggle('neg',val<0);}});
}
