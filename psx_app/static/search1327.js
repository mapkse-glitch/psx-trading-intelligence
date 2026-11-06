/* Progressive search for long native filters; selection stays a native select. */
(function installLongSelectSearch1327(){
 const norm=s=>String(s??'').normalize('NFKD').toLocaleLowerCase().trim();
 let sequence=0;
 function install(select){
  if(select.dataset.search1327||select.disabled||select.multiple||select.options.length<12||select.querySelector('optgroup'))return;
  select.dataset.search1327='1';
  const label=select.labels?.[0];
  let name=select.getAttribute('aria-label')||'';
  if(!name&&label)name=[...label.childNodes].filter(n=>n.nodeType===Node.TEXT_NODE).map(n=>n.textContent).join(' ').replace(/\s+/g,' ').replace(/[:：]\s*$/,'').trim();
  name=name||'options';
  const target=label&&label.contains(select)&&label.querySelectorAll('input,select,textarea').length===1?label:select;
  const wrap=document.createElement('div');wrap.className='select-search-wrap1327';
  target.parentNode.insertBefore(wrap,target);
  // Retain a real associated label, while visually joining search and select.
  if(target===label){
   if(!select.id)select.id='searchable-select1329-'+(++sequence);
   label.htmlFor=select.id;wrap.append(label);select.remove();
  }else if(!select.id)select.id='searchable-select1329-'+(++sequence);
  const group=document.createElement('div');group.className='select-search-group1329';
  const area=document.createElement('div');area.className='select-search1327';
  const input=document.createElement('input');input.type='search';input.autocomplete='off';input.placeholder='Search '+name;input.setAttribute('aria-label','Search '+name+' options');input.setAttribute('aria-controls',select.id);
  const result=document.createElement('small');result.id='search-status1327-'+(++sequence);result.className='select-search-status1327';result.setAttribute('aria-live','polite');input.setAttribute('aria-describedby',result.id);
  area.append(input);group.append(area,select);wrap.append(group,result);
  const original=[...select.options],selected=select.value;
  let committed=selected;
  const placeholder=document.createElement('option');placeholder.value='';placeholder.disabled=true;placeholder.textContent='Select a matching result';
  function filter(){
   const q=norm(input.value),matches=original.filter(o=>!q||!o.hidden&&(norm(o.textContent).includes(q)||norm(o.value).includes(q)));
   if(!q){select.replaceChildren(...original);select.value=committed;result.textContent='';return;}
   select.replaceChildren(placeholder,...matches);placeholder.selected=true;
   const available=matches.filter(o=>!o.disabled&&!o.hidden).length;
   result.textContent=available?`${available} matching option${available===1?'':'s'} · choose below`:'No matching options';
  }
  input.addEventListener('input',filter);
  input.addEventListener('keydown',e=>{if(e.key==='Escape'){input.value='';filter();select.focus();}else if(e.key==='Enter'){e.preventDefault();const matches=[...select.options].filter(o=>o!==placeholder&&!o.disabled&&!o.hidden);if(input.value&&matches.length===1){matches[0].selected=true;select.dispatchEvent(new Event('change',{bubbles:true}));}else select.focus();}});
  select.addEventListener('change',()=>{const chosen=select.value;committed=chosen;if(!input.value)return;input.value='';select.replaceChildren(...original);select.value=chosen;result.textContent='';},true);
 }
 function scan(root){if(root.nodeType!==Node.ELEMENT_NODE&&root.nodeType!==Node.DOCUMENT_NODE)return;if(root.matches?.('select'))install(root);root.querySelectorAll?.('select').forEach(install);}
 scan(document);
 new MutationObserver(records=>records.forEach(r=>r.addedNodes.forEach(scan))).observe(document.getElementById('appShell')||document.body,{childList:true,subtree:true});
})();
