"""Assemble authored prose; never ask a model to rewrite it during layout."""
import base64
import html
import json
import mimetypes
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from html.parser import HTMLParser
from bible import digest, plain
import editorial

ROOT=Path(__file__).resolve().parents[1]
TAGS={'p','h4','strong','b','em','i','blockquote','cite','ul','ol','li','table','thead','tbody','tr','td','th','caption','small','span','a','br','sup','sub'}
VOID={'br'}

class Fragment(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[]
    def handle_starttag(self,tag,attrs):
        if tag not in TAGS:raise ValueError('Unsupported prose tag: '+tag)
        for k,v in attrs:
            if k not in {'lang','dir','href','scope','colspan','rowspan','class'}:raise ValueError('Unsupported prose attribute: '+k)
            if k=='href' and not (v.startswith('#ref-') or v.startswith('https://') or v.startswith('http://')):raise ValueError('Unsafe link')
            if k=='class' and v!='table-scroll':raise ValueError('Unknown prose class')
        if tag not in VOID:self.stack.append(tag)
    def handle_endtag(self,tag):
        if tag in VOID:return
        if not self.stack or self.stack.pop()!=tag:raise ValueError('Unbalanced prose HTML')
    def close(self):
        super().close()
        if self.stack:raise ValueError('Unclosed prose HTML')

def fragment(s):
    p=Fragment();p.feed(s);p.close();return s

def diagram_svg(source,figure_id):
    # Inline diagrams share the actual embedded SameTone font; an <img> SVG cannot inherit it.
    if re.search(r'<!DOCTYPE|<!ENTITY',source,re.I):raise ValueError('SVG declarations are not allowed')
    node=ET.fromstring(source)
    tags={'svg','g','path','rect','circle','ellipse','line','polyline','polygon','text','tspan','title','desc','defs','marker'}
    attrs={'id','width','height','viewBox','role','aria-labelledby','x','y','x1','x2','y1','y2','cx','cy','r','rx','ry','d','points','fill','stroke','stroke-width','stroke-linecap','stroke-linejoin','font-family','font-size','font-weight','text-anchor','dominant-baseline','transform','opacity','marker-end','marker-start','markerWidth','markerHeight','refX','refY','orient'}
    ids={e.get('id'):figure_id+'-'+e.get('id') for e in node.iter() if e.get('id')}
    for e in node.iter():
        if e.tag.split('}')[-1] not in tags:raise ValueError('Unsupported SVG element')
        for key,value in list(e.attrib.items()):
            if key not in attrs or re.search(r'https?:|javascript:|data:|//',value,re.I):raise ValueError('Unsafe SVG attribute')
            if key=='id':e.set(key,ids[value])
            elif key=='aria-labelledby':e.set(key,' '.join(ids.get(x,x) for x in value.split()))
            elif key in ('marker-end','marker-start'):
                if not re.fullmatch(r'url\(#[a-zA-Z0-9_-]+\)',value):raise ValueError('Unsafe SVG marker')
                e.set(key,'url(#'+ids.get(value[5:-1],value[5:-1])+')')
            elif 'url(' in value:raise ValueError('SVG resource URL not allowed')
            elif key=='font-family':e.set(key,'var(--sans)')
    ET.register_namespace('','http://www.w3.org/2000/svg')
    return ET.tostring(node,encoding='unicode')

def print_proof(doc):
    # Local visual proof of the exact print rules; pagination still belongs to the user's print dialog.
    css='\n'.join((ROOT/'automation'/name).read_text(encoding='utf-8')
                  for name in ('reader.css','typography.css'))
    blocks=[];cursor=0
    while (marker:=css.find('@media print{',cursor))!=-1:
        start=marker+len('@media print{');depth=1;end=start
        while depth:
            if css[end]=='{':depth+=1
            elif css[end]=='}':depth-=1
            end+=1
        blocks.append(css[start:end-1]);cursor=end
    rules='\n'.join(blocks)
    doc=re.sub(r'<script>.*?</script>','',doc,flags=re.S)
    doc=re.sub(r'<details\b([^>]*)>',lambda m:'<details'+re.sub(r'\sopen(?:=["\'][^"\']*["\'])?','',m[1])+' open>',doc)
    return doc.replace('</head>',f'<style>{rules}main{{max-width:180mm;margin:auto}}html{{background:#fff}}</style></head>')

def validate(manuscript,passage,run_dir):
    if digest({k:v for k,v in passage.items() if k!='sha256'})!=passage['sha256']:raise ValueError('Passage integrity mismatch')
    if manuscript.get('passageSha256')!=passage['sha256']:raise ValueError('Manuscript uses a different passage')
    if not passage.get('verified'):raise ValueError('Passage must be verified')
    ids=[];prose=[];refs={s['id'] for s in manuscript['sources']}
    if len(refs)!=len(manuscript['sources']) or len(refs)<2:raise ValueError('At least two distinct research sources required')
    for source in manuscript['sources']:
        if not re.fullmatch('[a-z0-9-]+',source['id']) or not source['url'].startswith(('https://','http://')) or not source.get('usedFor'):raise ValueError('Incomplete source')
    for section in manuscript['sections']:
        if not section['title'] or not section.get('cards'):raise ValueError('Empty section')
        ids.append(section['id'])
        for card in section['cards']:
            ids.append(card['id']);fragment(card['html']);prose.append(card['html'])
            if not card.get('summary') or not card.get('title'):raise ValueError('Card needs title and meaningful summary')
            for ref in re.findall(r'href=["\']#ref-([^"\']+)',card['html']):
                if ref not in refs:raise ValueError('Unresolved citation: '+ref)
    if len(ids)!=len(set(ids)) or any(not re.fullmatch('[a-z][a-z0-9-]+',x) for x in ids):raise ValueError('Duplicate or invalid IDs')
    text=' '.join(plain(x) for x in prose)
    if not text.strip():raise ValueError('Empty manuscript')
    if not re.search('#ref-', ''.join(prose)):raise ValueError('No citations attached to prose')
    figures={f['id']:f for f in manuscript.get('figures',[])}
    if len(figures)!=len(manuscript.get('figures',[])):raise ValueError('Duplicate figure IDs')
    if manuscript.get('heroFigure') and manuscript['heroFigure'] not in figures:raise ValueError('Unknown hero figure')
    if not manuscript.get('practices'):raise ValueError('Concrete practices required')
    for f in figures.values():
        p=(Path(run_dir)/f['file']).resolve()
        if not p.is_relative_to(Path(run_dir).resolve()) or not p.is_file():raise ValueError('Missing or external figure file')
        if p.suffix.lower() not in ('.png','.jpg','.jpeg','.webp','.svg'):raise ValueError('Unsupported figure')
        if not f.get('alt') or not f.get('caption') or f.get('kind') not in ('generated-illustration','sourced-image','diagram'):raise ValueError('Figure provenance required')
        if p.suffix=='.svg' and re.search(r'<script|<foreignObject|(?:href|src)=["\'](?:https?:|//)|\bon\w+\s*=',p.read_text(encoding='utf-8'),re.I):raise ValueError('SVG must be self-contained and inert')
        if p.suffix.lower()=='.svg':diagram_svg(p.read_text(encoding='utf-8'),f['id'])
    for section in manuscript['sections']:
        if section.get('presentation','disclosure') not in ('disclosure','essay'):raise ValueError('Unknown section presentation')
        for card in section['cards']:
            if card.get('figure') and card['figure'] not in figures:raise ValueError('Unknown figure reference')
            if card.get('figurePosition','before') not in ('before','after'):raise ValueError('Unknown figure position')
            if card.get('tableLayout','auto') not in ('auto','wide'):raise ValueError('Unknown table layout')
    binding=editorial.validate(manuscript,passage,run_dir)
    return dict(proseCharacters=len(text),cards=len(ids)-len(manuscript['sections']),figures=len(figures),proseSha256=digest(prose),**binding)

def render(manuscript,passage,run_dir,issue_id,filename):
    metrics=validate(manuscript,passage,run_dir)
    esc=lambda s:html.escape(str(s),quote=True)
    figures={f['id']:f for f in manuscript.get('figures',[])}
    def figure(fid):
        f=figures[fid];p=Path(run_dir)/f['file'];mime=mimetypes.guess_type(p.name)[0] or 'image/png'
        if p.suffix.lower()=='.svg':
            graphic=diagram_svg(p.read_text(encoding='utf-8'),fid)
            return f'<figure aria-label="{esc(f["alt"])}">{graphic}<figcaption>{esc(f["caption"])}</figcaption></figure>'
        data=base64.b64encode(p.read_bytes()).decode()
        return f'<figure><img src="data:{mime};base64,{data}" alt="{esc(f["alt"])}"><figcaption>{esc(f["caption"])}</figcaption></figure>'
    body=[]
    for i,section in enumerate(manuscript['sections'],1):
        cards=[]
        for c in section['cards']:
            picture=figure(c['figure']) if c.get('figure') else ''
            table_class='table-scroll wide-table' if c.get('tableLayout')=='wide' else 'table-scroll'
            prose=re.sub(r'(<table\b.*?</table>)',lambda match:f'<div class="{table_class}" tabindex="0" role="region" aria-label="가로로 읽는 표">{match[1]}</div>',c['html'],flags=re.S)
            if c.get('figurePosition')=='after':prose,picture=prose+picture,''
            if section.get('presentation')=='essay':
                cards.append(f'<article class="essay" id="{esc(c["id"])}"><h3>{esc(c["title"])}</h3><div class="brief">{esc(c["summary"])}</div><div class="prose">{picture}{prose}</div></article>')
            else:
                cards.append(f'<details class="study-card" id="{esc(c["id"])}" open><summary><h3>{esc(c["title"])}</h3></summary><div class="brief">{esc(c["summary"])}</div><div class="prose">{picture}{prose}</div></details>')
        body.append(f'<section class="chapter" id="{esc(section["id"])}"><div class="chapter-head"><span aria-hidden="true">{i:02d}</span><h2>{esc(section["title"])}</h2></div>'+''.join(cards)+'</section>')
    toc=''.join(f'<a href="#{esc(s["id"])}">{esc(s["title"])}</a>' for s in manuscript['sections'])
    verses=''.join(f'<p data-verse="{esc(v["key"])}"><span class="verse-no">{esc(v["chapter"])}:{esc(v["verse"])}</span>{esc(v["text"])}</p>' for v in passage['verses'])
    refs=''.join(f'<li id="ref-{esc(s["id"])}"><a href="{esc(s["url"])}">{esc(s["title"])}</a><p>{esc(s["usedFor"])}</p></li>' for s in manuscript['sources'])
    checks=''.join(f'<label><input type="checkbox"><span>{esc(x)}</span></label>' for x in manuscript['practices'])
    font=(ROOT/'web/reader-fonts.css').read_text(encoding='utf-8')
    css=(ROOT/'automation/reader.css').read_text(encoding='utf-8')+'\n'+(ROOT/'automation/typography.css').read_text(encoding='utf-8')
    js=(ROOT/'automation/reader.js').read_text(encoding='utf-8')
    logo=(ROOT/'web/logo.svg').read_text(encoding='utf-8')
    license=(ROOT/'web/assets/FONT-LICENSES.txt').read_text(encoding='utf-8')
    meta=dict(issueId=issue_id,templateVersion='bnoc-reader-1.1',manuscriptSha256=digest(manuscript),passageSha256=passage['sha256'],figureHashes={f['id']:digest((Path(run_dir)/f['file']).read_bytes()) for f in figures.values()},metrics=metrics)
    metadata_json=json.dumps(meta,ensure_ascii=False).replace('<','\\u003c')
    license_json=json.dumps(license,ensure_ascii=False).replace('<','\\u003c')
    doc=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(manuscript['title'])}</title><meta name="description" content="{esc(manuscript['description'])}"><meta name="bnoc-style" content="original">
<style id="embedded-fonts">{font}</style><style id="bnoc-reader-v1">{css}</style></head><body data-issue="{esc(issue_id)}">
<a href="#main" class="skip">본문으로 건너뛰기</a><header class="top"><a class="brand" href="https://laguna821.github.io/BNOC/">{logo}<span>BNOC 말씀 아카이브</span></a><div class="tools"><button id="theme">테마</button><button id="size">글자 18</button><button id="summary" aria-pressed="false">요약 읽기</button><button id="search">본문 검색</button><button id="print">인쇄</button></div></header>
<main id="main"><div class="intro"><p class="eyebrow">BIBLE NOTES ON CONTEXT · {esc(manuscript['date'])}</p><h1>{esc(manuscript['title'])}</h1><p class="lead">{esc(manuscript['intro'])}</p><p class="meta">{esc(passage['reference'])} · 개인 성경 연구 노트</p><p><a href="{esc(filename)}" download="{esc(filename)}">HTML 저장</a></p></div>
{figure(manuscript['heroFigure']) if manuscript.get('heroFigure') else ''}
<nav class="toc" aria-label="본문 목차">{toc}</nav><aside class="scripture"><h2>{esc(passage['reference'])}</h2>{verses}<p class="meta">개역개정 · 대한성서공회 본문 대조</p></aside>{''.join(body)}
<section class="chapter checklist"><h2>이번 주의 작은 실천</h2>{checks}</section><section class="chapter journal"><h2>읽고 난 뒤, 한 문장을 남깁니다</h2><label for="note">나의 묵상 메모</label><textarea id="note"></textarea><p class="note-status" id="noteStatus">메모는 이 기기의 브라우저에만 저장됩니다.</p><button id="saveNote">메모 파일 저장</button></section>
<section class="chapter"><h2>출처와 읽기의 범위</h2><ol class="source-list">{refs}</ol><p class="meta">주보는 본문 선정의 근거이며, 이 글은 교회의 공식 해석이나 설교 요약이 아닙니다. 창작 그림은 본문 이해를 돕는 해석적 삽화입니다.</p></section>
<footer>BNOC · Achmage · SameTone Lite<br>말씀의 맥락을 살피고, 오늘의 삶으로 이어갑니다.</footer></main>
<dialog id="searchDialog" aria-labelledby="searchTitle"><div class="dialog-head"><h2 id="searchTitle">본문 검색</h2><button id="closeSearch">닫기</button></div><label for="query">검색어</label><input id="query" type="search"><p id="matchCount" role="status">검색어를 입력하세요.</p><div id="matches"></div></dialog>
<script>{js}</script><script type="application/json" id="bnoc-provenance">{metadata_json}</script><script type="application/json" id="bnoc-font-licenses">{license_json}</script></body></html>'''
    if manuscript.get('revision'):
        import revision
        doc=revision.stamp(doc,manuscript['revision'])
        revised=esc(manuscript['revision']['revisedAt'][:10])
        doc=doc.replace('<p class="meta">',f'<p class="meta">개정 {revised} · 최초 게재일은 유지됩니다.</p><p class="meta">',1)
    if manuscript.get('scriptureCollapsible'):
        doc=doc.replace('<aside class="scripture">','<details class="scripture"><summary>성경 본문 전체 보기</summary>').replace('</aside>','</details>',1)
    if manuscript.get('revision'):
        doc=doc.replace('주보는 본문 선정의 근거이며, 이 글은 교회의 공식 해석이나 설교 요약이 아닙니다. 창작 그림은 본문 이해를 돕는 해석적 삽화입니다.', '기존에 게재된 본문과 제작 의도를 바탕으로 개정한 개인 성경 연구 노트입니다. 교회의 공식 해석이나 설교 원고를 대신하지 않습니다. 그림과 도표의 성격은 각 설명에 표시했습니다.')
    if any(v['text'] not in html.unescape(doc) for v in passage['verses']):raise ValueError('Verse lost during assembly')
    return doc,meta
