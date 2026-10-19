"""Opt-in preservation of a reviewed native article, with reversible UI-only changes."""
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from bible import digest, plain
import editorial
import revision

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'bnoc-source-reader-1.0'
PROFILE = 'sardis-native-v1'
REVIEW_KEYS = ('historicalAccuracy','originalLanguages','orthodoxyOrthopraxy','layReadability','citationsChecked','visualAccuracy','mobileLightDark','mobileTables','readerControls','searchNotesDownload','printLayout')

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def enabled(path):
    return (Path(path)/'source-reader-plan.json').is_file()

def cards(doc):
    class Capture(HTMLParser):
        def __init__(self):
            super().__init__();self.stack=[];self.found={}
            self.lines=[0]
            for line in doc.splitlines(keepends=True):self.lines.append(self.lines[-1]+len(line))
        def absolute_position(self):
            line,col=self.getpos();return self.lines[line-1]+col
        def handle_starttag(self,tag,attrs):
            if tag=='details':
                a=dict(attrs);key=a.get('id') if 'study-card' in a.get('class','').split() else None
                if key and any(k for _,k in self.stack):raise ValueError('Nested study card')
                self.stack.append((self.absolute_position(),key))
        def handle_endtag(self,tag):
            if tag=='details':
                if not self.stack:raise ValueError('Unbalanced native details')
                start,key=self.stack.pop()
                if key:
                    if key in self.found:raise ValueError('Duplicate native card')
                    self.found[key]=doc[start:doc.index('>',self.absolute_position())+1]
    parser=Capture();parser.feed(doc);parser.close()
    if parser.stack or not parser.found:raise ValueError('Incomplete native cards')
    return parser.found

def snapshot(doc):
    return dict(cards={k:digest(v) for k,v in cards(doc).items()},
                svgHashes=[digest(x) for x in re.findall(r'<svg\b.*?</svg>',doc,re.S)],
                scripts=[digest(x) for x in re.findall(r'<script\b[^>]*>(.*?)</script>',doc,re.S)],
                title=plain(re.search(r'<title>(.*?)</title>',doc,re.S)[1]))

def validate(path, run):
    path = Path(path)
    original = (path/'original.html').read_bytes()
    source = original.decode('utf-8-sig')
    plan = read(path/'source-reader-plan.json')
    passage = read(path/'passage.json')
    if plan.get('profile') != PROFILE or plan.get('originalSha256') != digest(original) or digest(original) != run['revision']['originalSha256']:
        raise ValueError('Source profile or original binding mismatch')
    if not passage.get('verified') or digest({k:v for k,v in passage.items() if k!='sha256'}) != passage['sha256'] or plan.get('passageSha256') != passage['sha256']:
        raise ValueError('Source passage integrity mismatch')
    state = snapshot(source)
    if plan.get('sourceSnapshot') != state:
        raise ValueError('Changed native cards, SVG or script')
    review = read(path/'source-exegesis-review.json')
    if review.get('originalSha256') != digest(original) or review.get('passageSha256') != passage['sha256']:
        raise ValueError('Stale native editorial review')
    if review.get('decision') != 'ready-for-design' or review.get('blockingFindings') or not all(review.get(k) for k in ('model','thesis','preservationDecision','researchRefs','checkedSources')):
        raise ValueError('Native editorial review incomplete')
    editorial.timestamp(review.get('reviewedAt'))
    native = cards(source)
    for axis in editorial.AXES:
        item = review.get('assessments',{}).get(axis,{})
        if not item.get('rationale') or not item.get('anchors'):
            raise ValueError('Native editorial evidence missing: '+axis)
        for anchor in item['anchors']:
            if anchor.get('cardId') not in native or not anchor.get('quote') or anchor['quote'] not in plain(native[anchor['cardId']]):
                raise ValueError('Native editorial anchor mismatch: '+axis)
    sources = review['checkedSources']
    if len({s['id'] for s in sources}) != len(sources) or any(not s.get('scope') or not s.get('url','').startswith(('https://','http://')) for s in sources):
        raise ValueError('Native source checking scope required')
    visual = read(path/'source-visual-plan.json')
    if visual.get('editorialReviewSha256') != digest(review) or visual.get('originalSha256') != digest(original) or not visual.get('rationale'):
        raise ValueError('Native visual plan not bound to editorial reading')
    if editorial.timestamp(visual.get('decidedAt')) < editorial.timestamp(review['reviewedAt']):
        raise ValueError('Native visual decision predates reading')
    actual = {digest(x):x for x in re.findall(r'<svg\b.*?</svg>',source,re.S) if '<title' in x}
    if not actual or {x.get('sha256') for x in visual.get('items',[])} != set(actual):
        raise ValueError('Native meaningful visual inventory mismatch')
    for item in visual['items']:
        if not all(item.get(k) for k in ('purpose','captionScope','inspectedAt','inspectionEvidence')) or item.get('decision') != 'retain':
            raise ValueError('Native SVG must be actually inspected and individually retained')
    return source, plan, passage, review, visual

def structural_changes(source, passage):
    """Only this inspected native structure is supported, never arbitrary HTML repair."""
    changes = []
    def change(old,new):
        if source.count(old) != 1:
            raise ValueError('Native UI source no longer matches: '+old[:70])
        changes.append((old,new))
    block = re.search(r'<details id="scripture" class="scripture-panel" open>(.*?)</details>',source,re.S)
    if not block or '<details' in block[1]:
        raise ValueError('Native Scripture structure changed')
    heading = re.match(r'<summary>(.*?)</summary>',block[1],re.S)
    if not heading: raise ValueError('Native Scripture heading missing')
    body = block[1][heading.end():]
    verses = re.findall(r'<p><span class="verse-no">(\d+)</span>(.*?)</p>',body,re.S)
    if [(str(v['verse']),v['text']) for v in passage['verses']] != [(n,html.unescape(t)) for n,t in verses]:
        raise ValueError('Native Bible differs from verified passage')
    # Preserve every original verse byte, replacing only the disclosure container and heading.
    new = '<aside id="scripture" class="scripture-panel"><div class="scripture-heading">'+heading[1]+'</div>'+body+'</aside>'
    change(block[0],new)
    change('const fontSizes=[17,19,21]','const fontSizes=[18,20,22]')
    change("if(a.classList.contains('dialog-link'))setSummary(false);reveal(target);","if(a.classList.contains('dialog-link')){setSummary(false);target.querySelectorAll('details').forEach(d=>d.open=true);}reveal(target);")
    change("dialog.addEventListener('cancel',()=>{if(lastFocus&&lastFocus.focus)lastFocus.focus()});","dialog.addEventListener('cancel',e=>{e.preventDefault();closeToc()});dialog.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();closeToc()}});")
    change('<a class="brand" href="#top">','<a class="brand" href="https://laguna821.github.io/BNOC/">')
    change('화면 글꼴은 기기의 기본 글꼴을 사용하므로 기기에 따라 조금 다르게 보일 수 있습니다.','SameTone Lite 가변 글꼴과 원어용 글꼴을 이 파일에 내장했습니다.')
    return changes

def render(path,run):
    source,plan,passage,review,visual = validate(path,run)
    doc = source
    changes = structural_changes(source,passage)
    for old,new in changes: doc=doc.replace(old,new,1)
    # Exact inverse is stronger than a text-only comparison: scripts, keys, anchors and all prose survive.
    restored=doc
    for old,new in reversed(changes):
        if restored.count(new)!=1: raise ValueError('Ambiguous source-preservation inverse')
        restored=restored.replace(new,old,1)
    if restored!=source: raise ValueError('Unapproved native change')
    if {k:digest(v) for k,v in cards(doc).items()}!=plan['sourceSnapshot']['cards']:
        raise ValueError('Native authored card changed')
    css='\n'.join((ROOT/name).read_text(encoding='utf-8') for name in
                  ('web/reader-fonts.css','automation/typography.css','automation/revision.css','automation/source_reader.css'))
    licenses=(ROOT/'web/assets/FONT-LICENSES.txt').read_text(encoding='utf-8').replace('*/','* /')
    logo=(ROOT/'web/logo.svg').read_text(encoding='utf-8')
    brand=re.search(r'(<span class="brand-symbol">)(<svg\b.*?</svg>)(</span>)',doc,re.S)
    if not brand:raise ValueError('Native brand icon missing')
    doc=doc[:brand.start(2)]+logo+doc[brand.end(2):]
    meta=dict(issueId=run['id'],templateVersion=VERSION,profile=PROFILE,originalSha256=plan['originalSha256'],
              passageSha256=passage['sha256'],sourcePlanSha256=digest(plan),
              editorialReviewSha256=digest(review),visualPlanSha256=digest(visual))
    addition='<style id="bnoc-source-reader">'+css+'\n/* Embedded font licenses\n'+licenses+'\n*/</style>'
    addition+='<script type="application/json" id="bnoc-provenance">'+json.dumps(meta,ensure_ascii=False).replace('<','\\u003c')+'</script>'
    doc=doc.replace('</head>',addition+'</head>',1)
    doc=revision.stamp(doc,run['revision'])
    filename=html.escape(Path(run['relativePath']).name.rstrip('.'),quote=True)
    notice='<aside class="bnoc-revision-notice">개정 '+run['revision']['revisedAt'][:10]+' · 기존 해설·삽화·메모 구조를 보존하고 원전 대조와 읽기 환경을 보완했습니다. <a href="'+filename+'" download="'+filename+'">HTML 저장</a></aside>'
    doc=re.sub(r'(<body\b[^>]*>)',lambda m:m[0]+notice,doc,count=1)
    metrics=audit_html(doc)
    return doc,dict(**meta,htmlSha256=digest(doc.encode()),contentSha256=digest(plan['sourceSnapshot']['cards']),title=plan['sourceSnapshot']['title'],date=run['date'],metrics=metrics)

def audit_html(doc):
    from reader_layout import ReaderContract,_body_column_headings
    def require(ok,message):
        if not ok:raise ValueError('Native reader contract: '+message)
    p=ReaderContract(doc)
    byid=lambda key:[n for n in p.nodes if n['attrs'].get('id')==key]
    cls=lambda n,key:key in n['attrs'].get('class','').split()
    scripture=byid('scripture')
    require(len(scripture)==1 and scripture[0]['tag']=='aside' and not any(n['tag']=='details' for n in scripture[0]['parents']),'Scripture must be an independent aside')
    verses=[n for n in p.within(scripture[0]) if cls(n,'verse-no')]
    require(bool(verses),'Scripture verses missing')
    native=[n for n in p.nodes if cls(n,'study-card')]
    require(bool(native),'Native exposition missing')
    for card in native:
        require(card['tag']=='details' and 'open' in card['attrs'],'Cards must initially open')
        children=[n for n in p.within(card) if n['parents'][-1] is card]
        require(sum(n['tag']=='summary' for n in children)==1,'One disclosure heading required')
        for name in ('brief','prose'):require(sum(cls(n,name) for n in children)==1,'Authored '+name+' missing')
    tools=[n for n in p.nodes if n['tag']=='nav' and cls(n,'bottom-tools')]
    require(len(tools)==1,'Persistent toolbar missing')
    buttons=p.within(tools[0],'button')
    require(len(buttons)==4 and any('data-open-toc' in n['attrs'] for n in buttons),'Four reading controls required')
    for key in ('summaryBtn','collapseBtn','topBtn'):
        require(len(byid(key))==1 and any(n is byid(key)[0] for n in buttons),'Toolbar control missing '+key)
    for key,tag in (('tocDialog','dialog'),('tocSearch','input'),('closeToc','button'),('fontBtn','button'),('themeBtn','button')):
        require(len(byid(key))==1 and byid(key)[0]['tag']==tag,'Native control missing '+key)
    require(len([n for n in p.nodes if n['tag']=='textarea' and 'data-note' in n['attrs']])==3,'Three native note fields required')
    tables=[n for n in p.nodes if n['tag']=='table']
    for table in tables:
        require(bool(p.within(table,'thead')),'Explicit print headings required')
        require(cls(table,'lex-table') or cls(table,'bridge-table'),'Unknown native table requires review')
        expected=_body_column_headings(p,table)
        for cell in p.within(table,'td'):
            require(bool(expected.get(id(cell))) and cell['attrs'].get('data-label')==expected[id(cell)],'Native mobile column heading mismatch')
    return dict(cards=len(native),tables=len(tables),verses=len(verses),readingTools=4)

def audit_review(path,run):
    doc,binding=render(path,run)
    report=read(Path(path)/'review.json')
    output=(Path(path)/Path(run['relativePath']).name.rstrip('.')).read_bytes()
    if digest(output)!=binding['htmlSha256']:raise ValueError('Native HTML changed; render again')
    for k in ('originalSha256','passageSha256','htmlSha256','contentSha256','sourcePlanSha256','editorialReviewSha256','visualPlanSha256'):
        if report.get(k)!=binding[k]:raise ValueError('Stale native final review: '+k)
    if report.get('blockingFindings') or not report.get('model') or report.get('preservedIntent')!=run['revision']['intent']:
        raise ValueError('Native final review incomplete')
    editorial.timestamp(report.get('reviewedAt'))
    for key in REVIEW_KEYS:
        item=report.get('checks',{}).get(key,{})
        if item.get('passed') is not True or not item.get('evidence'):raise ValueError('Native QA missing '+key)
    checked=read(Path(path)/'source-exegesis-review.json')['checkedSources']
    if set(report.get('checkedSourceIds',[]))!={s['id'] for s in checked}:raise ValueError('Native checked-source scope mismatch')
    return binding
