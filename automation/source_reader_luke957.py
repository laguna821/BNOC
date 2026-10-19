"""Exact, reversible affordance changes for the individually reviewed Luke 9:57 article."""
import re
from bible import plain

def structural_changes(source,passage):
    changes=[]
    def change(old,new):
        if source.count(old)!=1:raise ValueError('Luke 9:57 native UI baseline changed: '+old[:80])
        changes.append((old,new))
    block=re.search(r'<details class="scripture" id="scripture" open>(.*?)</details>',source,re.S)
    if not block or '<details' in block[1]:raise ValueError('Luke 9:57 Scripture structure changed')
    heading=re.match(r'<summary>(.*?)</summary>',block[1],re.S)
    if not heading:raise ValueError('Luke 9:57 Scripture heading missing')
    body=block[1][heading.end():]
    actual=[(n,plain(t)) for n,t in re.findall(r'<p><span class="verse-no">(\d+)</span>(.*?)</p>',body,re.S)]
    if actual!=[(str(v['verse']),v['text']) for v in passage['verses']]:
        raise ValueError('Luke 9:57 Bible differs from verified passage')
    change(block[0],'<aside class="scripture" id="scripture"><div class="scripture-heading">'+heading[1]+'</div>'+body+'</aside>')
    change('<a class="brand" href="#top">','<a class="brand" href="https://laguna821.github.io/BNOC/">')
    change('<nav class="toolbar" aria-label="읽기 도구">','<nav class="toolbar bottom-tools" aria-label="읽기 도구">')
    change("const dialog=$('#tocDialog'),index=", "let tocFocus=null;const dialog=$('#tocDialog');function closeToc(){dialog.close();if(tocFocus&&tocFocus.focus)tocFocus.focus()}dialog.addEventListener('cancel',e=>{e.preventDefault();closeToc()});dialog.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();closeToc()}});const index=")
    change("e.preventDefault();dialog.close();summary(false);history.replaceState(null,'','#'+i.id);reveal(i.id)","e.preventDefault();dialog.close();summary(false);document.getElementById(i.id).querySelectorAll('details').forEach(d=>d.open=true);history.replaceState(null,'','#'+i.id);reveal(i.id)")
    change("b.onclick=()=>{toc();dialog.showModal();$('#searchInput').focus()}","b.onclick=()=>{tocFocus=b;toc();dialog.showModal();$('#searchInput').focus()}")
    change("$('#closeToc').onclick=()=>dialog.close()","$('#closeToc').onclick=closeToc")
    change("e.clientY>r.bottom)dialog.close()","e.clientY>r.bottom)closeToc()")
    change("document.documentElement.style.setProperty('--size',size+'px');$('#fontBtn').onclick=", "document.documentElement.style.setProperty('--size',size+'px');$('#fontBtn').setAttribute('aria-label','글자 크기 변경, 현재 '+size+'px');$('#fontBtn').onclick=")
    change("set('size',size);notify('본문 글자 크기 '+size+'px')", "set('size',size);$('#fontBtn').setAttribute('aria-label','글자 크기 변경, 현재 '+size+'px');notify('본문 글자 크기 '+size+'px')")
    change("$('#themeMeta').content=dark?'#14221c':'#f6f4ed'", "$('#themeMeta').content=dark?'#08090a':'#ffffff'")
    return changes
