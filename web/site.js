'use strict';
const $=s=>document.querySelector(s),form=$('#filters'),q=$('#q'),year=$('#year'),book=$('#book'),sort=$('#sort'),entries=$('#entries'),result=$('#result');
let items=null,loading=null;
const theme=$('#theme');
function themeLabel(){const dark=document.documentElement.dataset.theme==='dark';theme.setAttribute('aria-label',dark?'밝은 테마로 변경':'어두운 테마로 변경');theme.setAttribute('aria-pressed',String(dark));}
themeLabel();
theme.addEventListener('click',()=>{const t=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=t;try{localStorage.setItem('bnoc-theme',t)}catch(e){}themeLabel()});
function load(){return loading||(loading=fetch('/BNOC/search.json').then(r=>{if(!r.ok)throw Error(r.status);return r.json()}).then(data=>items=data).catch(e=>{loading=null;result.textContent='검색 자료를 불러오지 못했습니다. 다시 검색해 주세요. 아래 전체 자료는 읽을 수 있습니다.';throw e}))}
function node(tag,text,cls){const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n}
function card(x){const a=node('article',null,'entry'),meta=node('div',null,'entry-meta'),time=node('time',x.date.replaceAll('-','.'));time.dateTime=x.date;meta.append(time,node('span',x.books.join(' · ')||'성경 연구'));const h=node('h3'),link=node('a',x.title);link.href=x.link;h.append(link);const read=node('a','자료 읽기 ↗','read');read.href=x.link;a.append(meta,h,node('p',x.description),read);return a}
function selected(){const terms=q.value.trim().normalize('NFKC').toLocaleLowerCase().split(/\s+/).filter(Boolean);return items.filter(x=>(!year.value||x.year===year.value)&&(!book.value||x.books.includes(book.value))&&terms.every(t=>x.search.normalize('NFKC').toLocaleLowerCase().includes(t))).sort((a,b)=>sort.value==='title'?a.title.localeCompare(b.title,'ko'):sort.value==='old'?a.date.localeCompare(b.date):b.date.localeCompare(a.date))}
async function render(){try{await load()}catch(e){return}const filtered=selected();entries.replaceChildren(...filtered.map(card));result.textContent=(q.value.trim()?'“'+q.value.trim()+'” · ':'')+filtered.length+'개 자료';$('#empty').hidden=filtered.length>0;const params=new URLSearchParams();for(const key of ['q','year','book','sort']){const val=$('#'+key).value;if(val&&val!=='new')params.set(key,val)}history.replaceState(null,'',location.pathname+(params.size?'?'+params:'')+location.hash)}
form.addEventListener('submit',e=>{e.preventDefault();render()});
let timer;q.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(render,160)});
for(const el of [year,book,sort])el.addEventListener('change',render);
form.addEventListener('reset',()=>setTimeout(render,0));
$('#random').addEventListener('click',async()=>{try{await load();const list=selected();if(list.length)location.href=list[Math.floor(Math.random()*list.length)].link;else result.textContent='현재 조건에 맞는 자료가 없습니다.'}catch(e){}});
const params=new URLSearchParams(location.search);for(const key of ['q','year','book','sort'])if(params.has(key))$('#'+key).value=params.get(key);
if(params.size)render();
