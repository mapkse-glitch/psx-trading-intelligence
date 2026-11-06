/* Progressive, keyboard-accessible suggestions for native dashboard filters. */
(function installLongSelectSearch1327(){
 const norm=s=>String(s??'').normalize('NFKD').toLocaleLowerCase().trim();
 let sequence=0;
 function install(select){
  if(select.dataset.search1327||select.disabled||select.multiple||select.querySelector('optgroup'))return;
  let label=select.labels?.[0];
  if(!label){const group=select.closest('.filter-group');const labels=group?.querySelectorAll('label');if(group&&labels.length===1&&group.querySelectorAll('input,select,textarea').length===1&&!labels[0].htmlFor&&!labels[0].querySelector('input,select,textarea'))label=labels[0];}
  let name=select.getAttribute('aria-label')||'';
  if(!name&&label)name=[...label.childNodes].filter(n=>n.nodeType===Node.TEXT_NODE).map(n=>n.textContent).join(' ').replace(/\s+/g,' ').replace(/[:：]\s*$/,'').trim();
  if(select.options.length<12&&!/symbol|ticker/i.test(name+' '+select.id))return;
  select.dataset.search1327='1';name=name||'options';
  const target=label&&label.contains(select)&&label.querySelectorAll('input,select,textarea').length===1?label:select;
  const wrap=document.createElement('div');wrap.className='select-search-wrap1327';
  target.parentNode.insertBefore(wrap,target);
  if(target===label){if(!select.id)select.id='searchable-select1329-'+(++sequence);label.htmlFor=select.id;wrap.append(label);select.remove();}
  else if(!select.id)select.id='searchable-select1329-'+(++sequence);
  if(label&&!label.contains(select)&&!label.htmlFor)label.htmlFor=select.id;
  const group=document.createElement('div');group.className='select-search-group1329';
  const area=document.createElement('div');area.className='select-search1327';
  const input=document.createElement('input');input.type='search';input.autocomplete='off';input.placeholder='Search '+name;input.setAttribute('aria-label','Search '+name+' options');input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-expanded','false');
  const result=document.createElement('small');result.id='search-status1327-'+(++sequence);result.className='select-search-status1327';result.setAttribute('aria-live','polite');input.setAttribute('aria-describedby',result.id);
  const list=document.createElement('div');list.id='search-suggestions1330-'+(++sequence);list.className='search-suggestions1330';list.setAttribute('role','listbox');list.setAttribute('aria-label',name+' suggestions');list.hidden=true;input.setAttribute('aria-controls',list.id);
  area.append(input);group.append(area,select);wrap.append(group,list,result);
  const original=[...select.options];let committed=select.value,matches=[],active=-1,pointerInside=false;
  const placeholder=document.createElement('option');placeholder.value='';placeholder.disabled=true;placeholder.textContent='Choose a match';
  function close(){list.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');active=-1;}
  function clear(){input.value='';select.replaceChildren(...original);select.value=committed;result.textContent='';matches=[];close();}
  function activate(index){if(!matches.length)return;active=Math.max(0,Math.min(index,Math.min(matches.length,300)-1));[...list.querySelectorAll('[role=option]')].forEach((item,i)=>{item.setAttribute('aria-selected',String(i===active));if(i===active){input.setAttribute('aria-activedescendant',item.id);item.scrollIntoView({block:'nearest'});}});}
  function choose(option){if(!option||option.disabled||option.hidden)return;const value=option.value;committed=value;input.value='';select.replaceChildren(...original);select.value=value;result.textContent='';matches=[];close();select.dispatchEvent(new Event('change',{bubbles:true}));}
  function filter(){
   const q=norm(input.value);if(!q){clear();return;}
   matches=original.filter(o=>!o.disabled&&!o.hidden&&(norm(o.textContent).includes(q)||norm(o.value).includes(q)));
   matches.sort((a,b)=>{const prefix=o=>norm(o.value).startsWith(q)||norm(o.textContent).startsWith(q);return Number(prefix(b))-Number(prefix(a));});
   select.replaceChildren(placeholder,...matches);placeholder.selected=true;
   list.replaceChildren();active=-1;input.removeAttribute('aria-activedescendant');
   const fragment=document.createDocumentFragment();const shown=matches.slice(0,300);const starts=o=>norm(o.value).startsWith(q)||norm(o.textContent).startsWith(q);const mixed=shown.some(starts)&&shown.some(o=>!starts(o));let lastGroup='';shown.forEach((option,i)=>{const section=starts(option)?'Starts with your search':'Also contains your search';if(mixed&&section!==lastGroup){const caption=document.createElement('div');caption.className='search-suggestion-heading1330';caption.setAttribute('role','presentation');caption.textContent=section;fragment.append(caption);lastGroup=section;}const row=document.createElement('div');row.id=list.id+'-'+i;row.setAttribute('role','option');row.setAttribute('aria-selected','false');row.className='search-suggestion1330';row.textContent=option.textContent.trim();row.addEventListener('pointerdown',e=>{if(e.pointerType==='mouse')e.preventDefault();});row.addEventListener('click',()=>choose(option));fragment.append(row);});list.append(fragment);
   list.hidden=!matches.length;input.setAttribute('aria-expanded',String(!!matches.length));
   result.textContent=matches.length?`${matches.length} matching option${matches.length===1?'':'s'}${matches.length>300?' · first 300 shown; type more to narrow':''}`:'No matching options';
  }
  input.addEventListener('input',filter);
  input.addEventListener('focus',()=>{if(input.value)filter();});
  input.addEventListener('keydown',e=>{if(e.isComposing)return;if(e.key==='Escape'){e.preventDefault();clear();}else if(e.key==='ArrowDown'&&matches.length){e.preventDefault();activate(active<0?0:active+1);}else if(e.key==='ArrowUp'&&matches.length){e.preventDefault();activate(active<0?matches.length-1:active-1);}else if(e.key==='Enter'&&input.value){e.preventDefault();if(matches.length)choose(matches[active<0?0:active]);}});
  wrap.addEventListener('pointerdown',e=>{if(list.contains(e.target))pointerInside=true;});
  wrap.addEventListener('pointerup',()=>setTimeout(()=>{pointerInside=false;},200));
  wrap.addEventListener('pointercancel',()=>{pointerInside=false;});
  wrap.addEventListener('focusout',()=>setTimeout(()=>{if(wrap.isConnected&&!pointerInside&&!wrap.contains(document.activeElement)&&(input.value||!list.hidden))clear();},100));
  wrap.addEventListener('search-dismiss1330',()=>{if(input.value||!list.hidden)clear();});
  select.addEventListener('change',()=>{committed=select.value;if(input.value)clear();},true);
 }
 function scan(root){if(root.nodeType!==Node.ELEMENT_NODE&&root.nodeType!==Node.DOCUMENT_NODE)return;if(root.matches?.('select'))install(root);root.querySelectorAll?.('select').forEach(install);}
 document.addEventListener('pointerdown',e=>document.querySelectorAll('.select-search-wrap1327').forEach(w=>{if(!w.contains(e.target))w.dispatchEvent(new Event('search-dismiss1330'));}),true);
 scan(document);
 new MutationObserver(records=>records.forEach(r=>r.addedNodes.forEach(scan))).observe(document.getElementById('appShell')||document.body,{childList:true,subtree:true});
})();
