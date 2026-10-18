(()=>{'use strict';
const $=s=>document.querySelector(s),key='bnoc:'+document.body.dataset.issue,theme=$('#theme'),size=$('#size'),summary=$('#summary'),dialog=$('#searchDialog'),q=$('#query'),note=$('#note');
function get(k){try{return localStorage.getItem(k)}catch(e){return null}}
function put(k,v){try{localStorage.setItem(k,v);return true}catch(e){return false}}
function label(){theme.textContent=document.documentElement.dataset.theme==='dark'?'밝게':'어둡게'}
document.documentElement.dataset.theme=get('bnoc-theme')||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');label();
theme.onclick=()=>{const t=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=t;put('bnoc-theme',t);label()};
let font=Number(get('bnoc-reader-size'))||18;
function fontsize(){document.documentElement.style.setProperty('--body-size',font+'px');size.textContent='글자 '+font}
fontsize();size.onclick=()=>{font=font===18?20:font===20?22:18;put('bnoc-reader-size',font);fontsize()};
summary.onclick=()=>{const on=document.body.classList.toggle('summary-mode');summary.setAttribute('aria-pressed',String(on));summary.textContent=on?'전체 읽기':'요약 읽기';document.querySelectorAll('.study-card').forEach(x=>x.open=true)};
$('#search').onclick=()=>{dialog.showModal();q.focus()};$('#closeSearch').onclick=()=>dialog.close();
q.oninput=()=>{const text=q.value.trim().toLocaleLowerCase(),box=$('#matches');box.replaceChildren();const cards=[...document.querySelectorAll('.study-card')].filter(x=>text&&x.textContent.toLocaleLowerCase().includes(text));$('#matchCount').textContent=text?cards.length+'개 항목':'검색어를 입력하세요.';for(const card of cards){const a=document.createElement('a');a.href='#'+card.id;a.textContent=card.querySelector('h3').textContent;a.onclick=()=>{card.open=true;document.body.classList.remove('summary-mode');summary.setAttribute('aria-pressed','false');summary.textContent='요약 읽기';dialog.close()};box.append(a)}};
note.value=get(key+':note')||'';note.oninput=()=>{$('#noteStatus').textContent=put(key+':note',note.value)?'이 브라우저에 저장했습니다.':'브라우저 저장이 불가능합니다. 메모를 파일로 저장해 주세요.'};
document.querySelectorAll('.checklist input').forEach((x,i)=>{x.checked=get(key+':check:'+i)==='1';x.onchange=()=>put(key+':check:'+i,x.checked?'1':'0')});
$('#saveNote').onclick=()=>{const blob=new Blob([document.title+'\n\n'+note.value],{type:'text/plain;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=document.body.dataset.issue+'-메모.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
let openBefore=[];addEventListener('beforeprint',()=>{openBefore=[...document.querySelectorAll('details')].map(x=>x.open);document.querySelectorAll('details').forEach(x=>x.open=true)});addEventListener('afterprint',()=>document.querySelectorAll('details').forEach((x,i)=>x.open=openBefore[i]));$('#print').onclick=()=>window.print();
})();
