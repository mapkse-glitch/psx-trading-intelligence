/* One small, text-only tooltip for existing chart marks; no per-point requests. */
(function installChartTips1329(){
 const selector='[data-chart-tip1329],.perf-hrow1328,.performance-stack1325,.performance-dot1325,.perf-combo-dot1328,.volume-donut139 circle,.volume-columns139 g,.top5-mark1329,.range-window-bar1321,.price-range-track1319';
 let box=null,active=null;
 function mark(node){return node instanceof Element?node.closest(selector):null;}
 function info(el){
  if(!el)return '';let text=el.getAttribute('data-chart-tip1329')||el.getAttribute('aria-label')||el.getAttribute('title')||el.querySelector(':scope > title')?.textContent||'';
  if(!text.trim())return '';
  // Transfer browser-native title to accessible text to avoid duplicate tooltips.
  if(el.hasAttribute('title'))el.removeAttribute('title');const native=el.querySelector(':scope > title');if(native)native.remove();
  el.setAttribute('data-chart-tip1329',text);if(!el.getAttribute('aria-label'))el.setAttribute('aria-label',text);
  return text;
 }
 function show(el){const text=info(el);if(!text)return;if(active&&active!==el)hide();if(!box){box=document.createElement('div');box.className='chart-tooltip1329';box.setAttribute('role','tooltip');box.id='chart-tooltip1329';document.body.append(box);}active=el;box.textContent=text;box.hidden=false;const ids=(el.getAttribute('aria-describedby')||'').split(/\s+/).filter(Boolean);if(!ids.includes(box.id))ids.push(box.id);el.setAttribute('aria-describedby',ids.join(' '));
  const r=el.getBoundingClientRect(),w=box.offsetWidth,h=box.offsetHeight;const left=Math.max(8,Math.min(innerWidth-w-8,r.left+r.width/2-w/2));let top=r.top-h-10;if(top<8)top=Math.min(innerHeight-h-8,r.bottom+10);box.style.left=left+'px';box.style.top=Math.max(8,top)+'px';}
 function hide(){if(active){const ids=(active.getAttribute('aria-describedby')||'').split(/\s+/).filter(id=>id&&id!=='chart-tooltip1329');if(ids.length)active.setAttribute('aria-describedby',ids.join(' '));else active.removeAttribute('aria-describedby');}active=null;if(box)box.hidden=true;}
 document.addEventListener('pointerover',e=>{const el=mark(e.target);if(el&&el!==active)show(el);});
 document.addEventListener('pointerout',e=>{if(active&&document.activeElement!==active&&!active.contains(e.relatedTarget)&&mark(e.target)===active)hide();});
 document.addEventListener('focusin',e=>{const el=mark(e.target);if(el)show(el);});
 document.addEventListener('focusout',e=>{if(active&&!active.contains(e.relatedTarget)&&mark(e.target)===active)hide();});
 document.addEventListener('keydown',e=>{if(e.key==='Escape')hide();});window.addEventListener('scroll',()=>{if(active&&document.activeElement===active)show(active);else hide();},true);window.addEventListener('resize',hide);
})();
