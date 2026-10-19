(()=>{'use strict';
const nav=document.getElementById('bnoc-analysis-guide');if(!nav)return;
// Keep the same named routes in the native search/contents dialog.
function dialogRoutes(dialog){
 if(!dialog.open||dialog.querySelector('.analysis-guide'))return;
 const copy=nav.cloneNode(true);copy.removeAttribute('id');
 copy.classList.add('analysis-guide-dialog');
 copy.querySelector('.analysis-guide-title').textContent='정론·정행·현대 적용 바로가기';
 const input=dialog.querySelector('input[type="search"],input');
 let container=input;
 while(container&&container.parentElement!==dialog)container=container.parentElement;
 // Native readers keep their search header sticky. Routes must scroll with the contents.
 if(container)container.after(copy);else dialog.prepend(copy);
}
for(const dialog of document.querySelectorAll('dialog')){
 new MutationObserver(()=>dialogRoutes(dialog)).observe(dialog,{attributes:true,attributeFilter:['open']});
 dialogRoutes(dialog);
}
document.addEventListener('click',event=>{
 const link=event.target.closest('.analysis-guide a[href^="#analysis-"],dialog[open] a[href^="#"]');if(!link)return;
 const target=document.getElementById(link.hash.slice(1));if(!target)return;
 event.preventDefault();event.stopPropagation();
 const dialog=link.closest('dialog');
 if(dialog){const close=dialog.querySelector('#closeToc,#closeSearch');if(close)close.click();else dialog.close();}
 const control=document.getElementById('summaryBtn')||document.getElementById('summary');
 if(control&&control.getAttribute('aria-pressed')==='true')control.click();
 for(let parent=target.closest('details');parent;parent=parent.parentElement?.closest('details'))parent.open=true;
 target.setAttribute('tabindex','-1');
 requestAnimationFrame(()=>{target.focus({preventScroll:true});target.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'})});
 history.pushState(null,'',link.getAttribute('href'));
},true);
})();
