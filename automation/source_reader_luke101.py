"""Preserve the latest Luke 10 design, its embedded font bytes and anonymous cards."""
import base64
import re
from bible import digest,plain

def font_hashes(css):
    result=[]
    for face in re.findall(r'@font-face\s*\{(.*?)\}',css,re.S):
        uri=re.search(r'url\(["\']?(data:[^"\'\)]+)',face)
        if not uri:raise ValueError('Existing font must remain embedded')
        result.append(digest(base64.b64decode(uri[1].split(',',1)[1],validate=True)))
    return result

def verify_existing_fonts(source,baseline):
    block=re.search(r'<style id="embedded-fonts">(.*?)</style>',source,re.S)
    expected=font_hashes(baseline)
    if not block or not expected or sorted(font_hashes(block[1]))!=sorted(expected):
        raise ValueError('Latest Luke fonts need individual byte comparison')

def structural_changes(source,passage):
    changes=[]
    def change(old,new):
        if source.count(old)!=1:raise ValueError('Luke 10 native UI baseline changed: '+old[:80])
        changes.append((old,new))
    block=re.search(r'<details class="scripture-panel" id="scripture" open>(.*?)</details>',source,re.S)
    if not block or '<details' in block[1]:raise ValueError('Luke 10 Scripture structure changed')
    heading=re.match(r'\s*<summary>(.*?)</summary>',block[1],re.S)
    if not heading:raise ValueError('Luke 10 Scripture heading missing')
    body=block[1][heading.end():]
    actual=[(n,plain(t)) for n,t in re.findall(r'<p><span class="verse-no">(\d+)</span>(.*?)</p>',body,re.S)]
    if actual!=[(str(v['verse']),v['text']) for v in passage['verses']]:raise ValueError('Luke 10 Bible differs from verified passage')
    change(block[0],'<aside class="scripture-panel" id="scripture"><div class="scripture-heading">'+heading[1]+'</div>'+body+'</aside>')
    change('<a class="brand" href="#top" aria-label="누가복음 10장 1–9절 노트 처음으로">','<a class="brand" href="https://laguna821.github.io/BNOC/" aria-label="BNOC 전체 해설">')
    change("dialog.addEventListener('cancel',function(){if(lastFocus&&lastFocus.focus)lastFocus.focus({preventScroll:true})});","dialog.addEventListener('cancel',function(e){e.preventDefault();closeToc()});dialog.addEventListener('keydown',function(e){if(e.key==='Escape'){e.preventDefault();closeToc()}});")
    change('if(dialog.open)closeToc();reveal(target,fromSearch);',"if(dialog.open)closeToc();if(fromSearch)target.querySelectorAll('details').forEach(function(d){d.open=true});reveal(target,fromSearch);")
    return changes
