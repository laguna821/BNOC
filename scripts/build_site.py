"""Dependency-free BNOC publisher. Sources remain intact; output goes to _site."""
from pathlib import Path
from html.parser import HTMLParser
from html import escape
import re, json, shutil, datetime, subprocess
from urllib.parse import quote
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
BASE='/BNOC'
ORIGIN='https://laguna821.github.io'
CUTOFF='2026-10-18'
BOOKS={'Genesis':'창세기','Exodus':'출애굽기','Numbers':'민수기','Deut':'신명기','Judges':'사사기','Isaiah':'이사야','Ezekiel':'에스겔','Matthew':'마태복음','Mark':'마가복음','Luke':'누가복음','John':'요한복음','Acts':'사도행전','Romans':'로마서','Ephesians':'에베소서','Colossians':'골로새서','Hebrews':'히브리서','Revelation':'요한계시록','Phil':'빌립보서'}

class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.skip=0;self.title=False;self.t=[];self.words=[];self.meta={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','style'):self.skip+=1
        if tag=='title' and not self.t:self.title=True
        if tag=='meta' and a.get('name'):self.meta[a['name']]=a.get('content','')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        if tag=='title':self.title=False
    def handle_data(self,data):
        if self.title:self.t.append(data)
        if not self.skip:self.words.append(data)

def date_for(path):
    folder=path.parent.name
    # Parent year is authoritative for legacy typo 2025/10122005.
    if re.fullmatch(r'\d{8}',folder):
        year=int(path.parts[0])
        if folder.startswith(str(year)):m,d=int(folder[4:6]),int(folder[6:])
        else:m,d=int(folder[:2]),int(folder[2:4])
        return datetime.date(year,m,d).isoformat()
    raise ValueError('Expected YYYY/MMDDYYYY or YYYY/YYYYMMDD: '+str(path))

def reader(html,date):
    parsed=Text();parsed.feed(html)
    if date<CUTOFF or parsed.meta.get('bnoc-style')=='original':
        return html
    if 'id="bnoc-reader-v1"' in html or 'id="sametone-editorial"' in html:return html
    font=(ROOT/'web/reader-fonts.css').read_text(encoding='utf-8')
    # Override inherited legacy font stacks without changing icons or authored layout.
    font+='\n@media screen{body{font-family:var(--sans)!important}body :where(h1,h2,h3,h4,p,li,td,th,summary,button,input,textarea,select,blockquote){font-family:inherit!important}strong,b{font-weight:600}}'
    if 'class="study-card"' in html and 'class="prose"' in html:
        font+='\n:root{--body-size:18px}\n'+(ROOT/'web/editorial.css').read_text(encoding='utf-8')
    licenses=(ROOT/'web/assets/FONT-LICENSES.txt').read_text(encoding='utf-8')
    style='<style id="bnoc-reader-v1">'+font+'</style>'
    attribution='<script type="application/json" id="bnoc-font-licenses">'+json.dumps(licenses,ensure_ascii=False).replace('</','<\\/')+'</script>'
    styled=re.sub('</head>',lambda m:style+m[0],html,count=1,flags=re.I)
    return re.sub('</body>',lambda m:attribution+m[0],styled,count=1,flags=re.I)

def build():
    out=ROOT/'_site';out.mkdir(exist_ok=True)
    # Dedicated output directory only. No repository internals are published.
    for child in out.iterdir():
        if child.is_dir():shutil.rmtree(child)
        else:child.unlink()
    items=[]
    for year in sorted(ROOT.iterdir()):
        if not year.is_dir() or not re.fullmatch(r'20\d{2}',year.name):continue
        shutil.copytree(year,out/year.name,dirs_exist_ok=True)
        for path in sorted(year.rglob('*')):
            if not path.is_file() or not path.name.lower().rstrip('.').endswith('.html'):continue
            rel=path.relative_to(ROOT);html=path.read_text(encoding='utf-8-sig')
            parsed=Text();parsed.feed(html);date=date_for(rel)
            title=' '.join(parsed.t).strip() or path.stem
            words=' '.join(' '.join(parsed.words).split())
            books=[v for k,v in BOOKS.items() if re.search(k,re.escape(path.name),re.I) or v in title]
            desc=parsed.meta.get('description','')
            if not desc:desc=' · '.join(books)+' 본문을 중심으로 배경과 의미, 삶의 적용을 살펴보는 말씀 자료.'
            target=rel
            if path.name.endswith('.'):target=rel.with_name(path.name.rstrip('.'))
            rendered=reader(html,date)
            (out/target).write_text(rendered,encoding='utf-8')
            link=BASE+'/'+quote(target.as_posix())
            items.append(dict(title=title,date=date,year=date[:4],books=books,description=desc,link=link,dir=rel.parent.as_posix(),search=' '.join([title,desc,*books,path.name,words]),style='sametone-lite-v1' if date>=CUTOFF and 'bnoc-style" content="original' not in html else 'original'))
    # Windows checkout omits exactly one non-portable historical name; recover its bytes from Git.
    legacy='2026/01252026/Luke_24_13-25_v1.html.'
    if not (ROOT/legacy).exists():
        data=subprocess.check_output(['git','show','HEAD:'+legacy],cwd=ROOT).decode('utf-8-sig')
        target=legacy.rstrip('.');(out/target).parent.mkdir(parents=True,exist_ok=True);(out/target).write_text(data,encoding='utf-8')
        p=Text();p.feed(data)
        items.append(dict(title=' '.join(p.t),date='2026-01-25',year='2026',books=['누가복음'],description='누가복음 본문을 중심으로 배경과 의미, 삶의 적용을 살펴보는 말씀 자료.',link=BASE+'/'+target,dir='2026/01252026',search=' '.join(p.words),style='original'))
    items.sort(key=lambda x:(x['date'],x['link']),reverse=True)
    shutil.copytree(ROOT/'web/assets',out/'assets')
    for name in ('site.css','site.js'):shutil.copy(ROOT/'web'/name,out/'assets'/name)
    (out/'.nojekyll').touch()
    public=[{k:v for k,v in x.items() if k!='search'} for x in items]
    (out/'index.json').write_text(json.dumps({'items':public},ensure_ascii=False),encoding='utf-8')
    (out/'search.json').write_text(json.dumps(items,ensure_ascii=False),encoding='utf-8')
    def card(x):
        return f'<article class="entry"><div class="entry-meta"><time datetime="{x["date"]}">{x["date"].replace("-",".")}</time><span>{escape(" · ".join(x["books"]) or "성경 연구")}</span></div><h3><a href="{x["link"]}">{escape(x["title"])}</a></h3><p>{escape(x["description"])}</p><a class="read" href="{x["link"]}">자료 읽기 <span aria-hidden="true">↗</span></a></article>'
    latest=items[0];template=(ROOT/'web/index.html').read_text(encoding='utf-8')
    values={'LOGO':(ROOT/'web/logo.svg').read_text(encoding='utf-8'),'CARDS':''.join(card(x) for x in items),'COUNT':str(len(items)),'DATE':latest['date'].replace('-','.'),'LATEST_TITLE':escape(latest['title']),'LATEST_LINK':latest['link'],'YEARS':''.join(f'<option value="{y}">{y}년</option>' for y in sorted({x['year'] for x in items},reverse=True)),'BOOKS':''.join(f'<option>{escape(b)}</option>' for b in sorted({b for x in items for b in x['books']}))}
    for k,v in values.items():template=template.replace('{{'+k+'}}',v)
    (out/'index.html').write_text(template,encoding='utf-8')
    rss=ET.Element('rss',version='2.0');channel=ET.SubElement(rss,'channel')
    for k,v in [('title','BNOC · 말씀 아카이브'),('link',ORIGIN+BASE+'/'),('description','Bible Notes on Context')]:ET.SubElement(channel,k).text=v
    for x in items[:50]:
        item=ET.SubElement(channel,'item')
        for k,v in [('title',x['title']),('link',ORIGIN+x['link']),('guid',ORIGIN+x['link']),('description',x['description']),('pubDate',datetime.datetime.fromisoformat(x['date']).strftime('%a, %d %b %Y 00:00:00 GMT'))]:ET.SubElement(item,k).text=v
    ET.ElementTree(rss).write(out/'feed.xml',encoding='utf-8',xml_declaration=True)
    sm=ET.Element('urlset',xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    for url in [ORIGIN+BASE+'/']+[ORIGIN+x['link'] for x in items]:ET.SubElement(ET.SubElement(sm,'url'),'loc').text=url
    ET.ElementTree(sm).write(out/'sitemap.xml',encoding='utf-8',xml_declaration=True)
    (out/'latest').mkdir()
    (out/'latest/index.html').write_text(f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={latest["link"]}"><link rel="canonical" href="{ORIGIN+latest["link"]}"><title>최신 말씀 자료</title><a href="{latest["link"]}">최신 자료 읽기</a></html>',encoding='utf-8')
    print(f'Built {len(items)} documents. Latest: {latest["date"]}. Search: {(out/"search.json").stat().st_size:,} bytes.')
    return items

if __name__=='__main__':build()
