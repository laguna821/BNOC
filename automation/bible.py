"""Local GAE lookup and narrowly scoped verification. No full corpus is published."""
import datetime as dt
import hashlib
import json
import re
import unicodedata
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROWS = """창|창세기|gen
출|출애굽기|exo
레|레위기|lev
민|민수기|num
신|신명기|deu
수|여호수아|jos
삿|사사기|jdg
룻|룻기|rut
삼상|사무엘상|1sa
삼하|사무엘하|2sa
왕상|열왕기상|1ki
왕하|열왕기하|2ki
대상|역대상|1ch
대하|역대하|2ch
스|에스라|ezr
느|느헤미야|neh
에|에스더|est
욥|욥기|job
시|시편|psa
잠|잠언|pro
전|전도서|ecc
아|아가|sng
사|이사야|isa
렘|예레미야|jer
애|예레미야애가|lam
겔|에스겔|ezk
단|다니엘|dan
호|호세아|hos
욜|요엘|jol
암|아모스|amo
옵|오바댜|oba
욘|요나|jnh
미|미가|mic
나|나훔|nam
합|하박국|hab
습|스바냐|zep
학|학개|hag
슥|스가랴|zec
말|말라기|mal
마|마태복음|mat
막|마가복음|mrk
눅|누가복음|luk
요|요한복음|jhn
행|사도행전|act
롬|로마서|rom
고전|고린도전서|1co
고후|고린도후서|2co
갈|갈라디아서|gal
엡|에베소서|eph
빌|빌립보서|php
골|골로새서|col
살전|데살로니가전서|1th
살후|데살로니가후서|2th
딤전|디모데전서|1ti
딤후|디모데후서|2ti
딛|디도서|tit
몬|빌레몬서|phm
히|히브리서|heb
약|야고보서|jas
벧전|베드로전서|1pe
벧후|베드로후서|2pe
요일|요한일서|1jn
요이|요한이서|2jn
요삼|요한삼서|3jn
유|유다서|jud
계|요한계시록|rev"""
BOOKS = [dict(zip(('short','name','code'),line.split('|'))) for line in ROWS.splitlines()]
ALIASES = {v:b for b in BOOKS for v in b.values()}
OFFICIAL_NAMES={'요일':'요한1서','요이':'요한2서','요삼':'요한3서'}
ALIASES.update({name:ALIASES[short] for short,name in OFFICIAL_NAMES.items()})
ALIASES['jon']=ALIASES['욘']
KEY = re.compile(r'^([^0-9]+)(\d+):(\d+)(?:-(\d+))?$')

def digest(data):
    if not isinstance(data, bytes):data=json.dumps(data,ensure_ascii=False,sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()

def save(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    temp.replace(path)

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'BNOC/1.0 personal Bible-study archive'})
    with urllib.request.urlopen(req,timeout=30) as r:
        data=r.read(20_000_001)
        if len(data)>20_000_000:raise ValueError('Response too large')
        return data

class Text(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[];self.skip=0;self.stack=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        hide=tag in ('script','style') or a.get('class') in ('D2','comment','smallTitle') or 'display:none' in a.get('style','').replace(' ','')
        if tag not in ('br','img','meta','link','input','hr'):
            self.stack.append((tag,hide));self.skip+=int(hide)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                self.skip-=sum(x[1] for x in self.stack[i:]);self.stack=self.stack[:i];break
    def handle_data(self,s):
        if not self.skip:self.parts.append(s)

def plain(html):
    p=Text();p.feed(html);return ' '.join(''.join(p.parts).split())

def normalize(s):
    return re.sub(r'\s+','',unicodedata.normalize('NFC',s)).strip()

def official_units(html):
    units={}
    for marker in re.finditer(r'<span\s+class=["\']number["\']>(\d+(?:-\d+)?).*?</span>',html,re.S|re.I):
        start=marker.end();depth=0;stop=None
        for tag in re.finditer(r'</?span\b[^>]*>',html[start:],re.I):
            if tag[0].lower().startswith('</'):
                if depth==0:
                    stop=start+tag.start();break
                depth-=1
            else:depth+=1
        if stop is None:raise ValueError('Unclosed official verse container')
        text=plain(html[start:stop])
        if not text:raise ValueError('Empty official verse')
        if marker[1] in units:raise ValueError('Duplicate official verse marker')
        units[marker[1]]=text
    if not units:raise ValueError('Official page contains no verse markers')
    return units

class Bible:
    def __init__(self,path,cache):
        self.path=Path(path);raw=self.path.read_bytes();self.sha=digest(raw)
        pairs=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=list)
        if len(dict(pairs))!=len(pairs):raise ValueError('Duplicate Bible keys')
        self.data=dict(pairs);self.cache=Path(cache);self.maxima={};self.ranges=[];self.invalid=[]
        for key,value in pairs:
            m=KEY.fullmatch(key)
            if not m or m[1] not in ALIASES:self.invalid.append(key);continue
            b,c,v,end=m[1],int(m[2]),int(m[3]),int(m[4] or m[3])
            self.maxima[b,c]=max(end,self.maxima.get((b,c),0))
            if end!=v:self.ranges.append(dict(key=key,book=b,chapter=c,start=v,end=end))
    def audit(self):
        represented=set()
        for key in self.data:
            m=KEY.fullmatch(key)
            if m:
                represented.update((m[1],int(m[2]),v) for v in range(int(m[3]),int(m[4] or m[3])+1))
        gaps=[f'{b}{c}:{v}' for (b,c),end in self.maxima.items() for v in range(1,end+1) if (b,c,v) not in represented]
        return dict(sha256=self.sha,keys=len(self.data),books=len({x[0] for x in self.maxima}),invalidKeys=self.invalid,combined=self.ranges,unrepresented=gaps,empty=[k for k,v in self.data.items() if not str(v).strip()],note='Gaps may be translation omissions; verify, never invent missing text.')
    def parse(self,reference):
        ref=reference.replace('장',':').replace('절','')
        ref=re.sub(r'[–—~〜]','-',ref);ref=re.sub(r'\s+','',ref)
        selected=[];lastbook=None;lastchapter=None
        for segment in re.split('[;,；+]',ref):
            if not segment:raise ValueError('Empty passage segment')
            book=next((a for a in sorted(ALIASES,key=len,reverse=True) if segment.startswith(a)),None)
            if book:
                lastbook=ALIASES[book];segment=segment[len(book):]
            if lastbook is None:raise ValueError('Book required')
            m=re.fullmatch(r'(?:(\d+):)?(\d+)(?:-(?:(\d+):)?(\d+))?',segment)
            if not m:raise ValueError('Use book chapter:verse[-chapter:verse]')
            c=int(m[1]) if m[1] else lastchapter
            if c is None:raise ValueError('Chapter required')
            v=int(m[2]);ec=int(m[3] or c);ev=int(m[4] or v);b=lastbook['short']
            if (ec,ev)<(c,v):raise ValueError('Reversed passage')
            for chapter in range(c,ec+1):
                end=self.maxima.get((b,chapter))
                if end is None:raise ValueError('Unknown chapter')
                start=v if chapter==c else 1;stop=ev if chapter==ec else end
                if start<1 or stop>end:raise ValueError('Verse outside chapter')
                selected.extend((b,chapter,n) for n in range(start,stop+1))
            lastchapter=ec
        if len(selected)>500:raise ValueError('Split very large requests into reading units')
        return list(dict.fromkeys(selected))
    def official(self,b,c,refresh=False):
        code=ALIASES[b]['code'];path=self.cache/'chapters'/f'{code}-{c}-{self.sha[:16]}.json'
        if path.exists() and not refresh:
            cached=json.loads(path.read_text(encoding='utf-8'))
            if cached.get('parserVersion')==2:return cached
        url=f'https://www.bskorea.or.kr/bible/korbibReadpage.php?version=GAE&book={code}&chap={c}'
        raw=fetch(url);html=raw.decode('utf-8-sig')
        if not re.search(r'<b>\s*개역개정\s*</b>',html):raise ValueError('Unexpected translation')
        chapter=re.search(r'class=["\']chapNum["\']>(.*?)</font>',html,re.S)
        expected_heading=f'제{c}'+('편' if b=='시' else '장')
        if not chapter or normalize(plain(chapter[1]))!=expected_heading:raise ValueError('Unexpected chapter')
        heading=re.search(r'class=["\']titleBg["\']>(.*?)</div>',html,re.S)
        if not heading or OFFICIAL_NAMES.get(b,ALIASES[b]['name']) not in plain(heading[1]):raise ValueError('Unexpected book')
        units=official_units(html)
        result=dict(parserVersion=2,url=url,retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat(),htmlSha256=digest(raw),units=units)
        save(path,result);return result
    def extract(self,reference,verify=True):
        selected=self.parse(reference);wanted=set(selected);out=[];used=set();sources=[];changes=[]
        chapters={(b,c):self.official(b,c) for b,c,_ in selected} if verify else {}
        for b,c,v in selected:
            key=f'{b}{c}:{v}'
            if (b,c,v) in used:continue
            group=next((r for r in self.ranges if r['book']==b and r['chapter']==c and r['start']<=v<=r['end']),None)
            local=self.data.get(key)
            unitkey=str(v);end=v
            if verify:
                chapter=chapters[b,c];official=chapter['units']
                if unitkey not in official:
                    merged=next((k for k in official if '-' in k and int(k.split('-')[0])<=v<=int(k.split('-')[1])),None)
                    if not merged:raise ValueError(f'Official verse unavailable: {key}; requires documented review')
                    start,end=map(int,merged.split('-'))
                    if not all((b,c,n) in wanted for n in range(start,end+1)):raise ValueError('Requested partial combined verse; resolve exact wording before publishing')
                    unitkey=merged;v=start;key=f'{b}{c}:{unitkey}'
                text=official[unitkey]
                local=self.data.get(key)
                if normalize(local or '')!=normalize(text):changes.append(dict(key=key,reason='combined/missing/different',source=chapter['url']))
                if chapter['url'] not in [x['url'] for x in sources]:sources.append({k:chapter[k] for k in ('url','retrievedAt','htmlSha256')})
            else:
                if local is None:raise ValueError(f'Unverified combined or missing key: {key}')
                text=local.strip()
            used.update((b,c,n) for n in range(v,end+1))
            out.append(dict(key=key,book=ALIASES[b]['name'],chapter=c,verse=unitkey,text=text,omitted=text.strip() in ('(없음)','없음','（없음）')))
        result=dict(reference=reference,translation='개역개정',datasetSha256=self.sha,verified=verify,verses=out,sources=sources,corrections=changes)
        result['sha256']=digest(result)
        if verify:save(self.cache/'passages'/(digest(selected)+'.json'),result)
        return result
