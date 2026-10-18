(()=>{'use strict';
const $=s=>document.querySelector(s),key='bnoc:'+document.body.dataset.issue,theme=$('#theme'),size=$('#size'),summary=$('#summary'),collapse=$('#collapse'),dialog=$('#searchDialog'),q=$('#query'),note=$('#note');
const cards=[...document.querySelectorAll('details.study-card')];
function get(k){try{return localStorage.getItem(k)}catch(e){return null}}
function put(k,v){try{localStorage.setItem(k,v);return true}catch(e){return false}}
function label(){theme.textContent=document.documentElement.dataset.theme==='dark'?'밝게':'어둡게'}
document.documentElement.dataset.theme=get('bnoc-theme')||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');label();
theme.onclick=()=>{const t=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=t;put('bnoc-theme',t);label()};
let font=Number(get('bnoc-reader-size'));if(![18,20,22].includes(font))font=18;
function fontsize(){document.documentElement.style.setProperty('--body-size',font+'px');size.textContent='글자 '+font}
fontsize();size.onclick=()=>{font=font===18?20:font===20?22:18;put('bnoc-reader-size',font);fontsize()};
let printState=null,lastFocus=null;
function updateCollapse(){const open=cards.length>0&&cards.every(x=>x.open);collapse.textContent=open?'전체 접기':'전체 펼치기';collapse.setAttribute('aria-expanded',String(open))}
function setSummary(on,persist=true){document.body.classList.toggle('summary-mode',on);summary.setAttribute('aria-pressed',String(on));summary.textContent=on?'자세히 보기':'요약 보기';if(on)cards.forEach(x=>x.open=true);if(persist)put(key+':summary',on?'1':'0');updateCollapse()}
setSummary(get(key+':summary')==='1',false);
summary.onclick=()=>setSummary(!document.body.classList.contains('summary-mode'));
collapse.onclick=()=>{const open=!cards.every(x=>x.open);cards.forEach(x=>x.open=open);updateCollapse()};
cards.forEach(x=>x.addEventListener('toggle',()=>{if(!printState)updateCollapse()}));
const motion=()=>matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth';
$('#top').onclick=()=>window.scrollTo({top:0,behavior:motion()});
function reveal(target){if(!target)return;setSummary(false);let d=target.matches('details')?target:target.closest('details');while(d){d.open=true;d=d.parentElement?.closest('details')}updateCollapse();if(!target.matches('a,button,input,textarea,summary'))target.setAttribute('tabindex','-1');requestAnimationFrame(()=>{target.focus({preventScroll:true});target.scrollIntoView({behavior:motion(),block:'start'})})}
const entries=[];
const scripture=$('#scripture');if(scripture)entries.push({target:scripture,title:scripture.querySelector('h2').textContent,group:'성경 본문'});
document.querySelectorAll('.chapter').forEach(section=>{const heading=section.querySelector('h2');if(!heading)return;const group=heading.textContent;const items=[...section.querySelectorAll('.study-card,.essay')];if(items.length){for(const card of items)entries.push({target:card,title:card.querySelector('h3').textContent,group})}else if(section.id)entries.push({target:section,title:group,group:'함께 읽기'})});
function search(){const words=q.value.trim().toLocaleLowerCase('ko-KR').split(/\s+/).filter(Boolean),box=$('#matches');box.replaceChildren();const results=entries.filter(x=>words.every(w=>(x.title+' '+x.target.textContent).toLocaleLowerCase('ko-KR').includes(w)));$('#matchCount').textContent=words.length?results.length+'개 항목':'성경 본문과 '+cards.length+'개 해설에서 찾아보세요.';for(const entry of results){const a=document.createElement('a'),small=document.createElement('span'),title=document.createElement('span');a.href='#'+entry.target.id;small.className='search-group';small.textContent=entry.group;title.textContent=entry.title;a.append(small,title);a.onclick=e=>{e.preventDefault();dialog.close();reveal(entry.target);history.pushState(null,'',a.getAttribute('href'))};box.append(a)}if(words.length&&!results.length){const p=document.createElement('p');p.textContent='찾은 내용이 없습니다. 더 짧은 말로 다시 찾아보세요.';box.append(p)}}
$('#search').onclick=()=>{lastFocus=document.activeElement;q.value='';search();dialog.showModal();q.focus()};
function closeSearch(){dialog.close();lastFocus?.focus({preventScroll:true})}
$('#closeSearch').onclick=closeSearch;
dialog.addEventListener('cancel',e=>{e.preventDefault();closeSearch()});
dialog.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();closeSearch()}});q.oninput=search;
document.addEventListener('click',e=>{const a=e.target instanceof Element?e.target.closest('a[href^="#"]'):null;if(!a||a.closest('dialog'))return;let target;try{target=document.getElementById(decodeURIComponent(a.hash.slice(1)))}catch(error){return}if(target){e.preventDefault();reveal(target);history.pushState(null,'',a.getAttribute('href'))}});
note.value=get(key+':note')||'';note.oninput=()=>{$('#noteStatus').textContent=put(key+':note',note.value)?'이 브라우저에 저장했습니다.':'브라우저 저장이 불가능합니다. 메모를 파일로 저장해 주세요.'};
document.querySelectorAll('.checklist input').forEach((x,i)=>{x.checked=get(key+':check:'+i)==='1';x.onchange=()=>put(key+':check:'+i,x.checked?'1':'0')});
$('#saveNote').onclick=()=>{const blob=new Blob([document.title+'\n\n'+note.value],{type:'text/plain;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=document.body.dataset.issue+'-메모.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
addEventListener('beforeprint',()=>{printState={open:cards.map(x=>x.open),summary:document.body.classList.contains('summary-mode')};document.body.classList.remove('summary-mode');cards.forEach(x=>x.open=true)});
addEventListener('afterprint',()=>{if(!printState)return;cards.forEach((x,i)=>x.open=printState.open[i]);document.body.classList.toggle('summary-mode',printState.summary);printState=null;updateCollapse()});$('#print').onclick=()=>window.print();
})();
