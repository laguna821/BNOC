"""Opt-in preservation of a reviewed native article, with reversible UI-only changes."""
import html
import base64
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from bible import digest, plain
import editorial
import revision

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'bnoc-source-reader-1.3'
PROFILE = 'sardis-native-v1'
PROFILES = (PROFILE, 'ezekiel-native-v1', 'luke-9-51-native-v1', 'luke-9-57-native-v1', 'luke-10-native-v1')
REVIEW_KEYS = ('historicalAccuracy','originalLanguages','orthodoxyOrthopraxy','layReadability','citationsChecked','visualAccuracy','mobileLightDark','mobileTables','readerControls','searchNotesDownload','printLayout')

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def enabled(path):
    return (Path(path)/'source-reader-plan.json').is_file()

def apply_content_edits(source, edits):
    """Apply individually authored prose changes; never regenerate an article from an outline."""
    if set(edits)!={'originalSha256','rationale','cards'} or not edits['rationale']:
        raise ValueError('Explain the native content edit scope')
    originals=cards(source);result=source;seen=set()
    for edit in edits['cards']:
        if set(edit)!={'cardId','beforeSha256','afterHtml','rationale'} or not edit['rationale']:
            raise ValueError('Incomplete native prose edit')
        key=edit['cardId']
        if key in seen or key not in originals:raise ValueError('Unknown or duplicate native prose edit')
        seen.add(key);before=originals[key];after=edit['afterHtml']
        if digest(before)!=edit['beforeSha256']:raise ValueError('Native prose baseline changed')
        parsed_after=cards(after)
        if key.startswith('@ordinal:'):
            valid_after=len(parsed_after)==1 and next(iter(parsed_after.values()))==after and next(iter(parsed_after)).startswith('@ordinal:')
        else:valid_after=parsed_after=={key:after}
        if not valid_after:raise ValueError('Native prose edit changed the card boundary')
        pattern=r'<div class="prose">(.*)</div>\s*</details>$'
        old=re.search(pattern,before,re.S);new=re.search(pattern,after,re.S)
        if not old or not new or before[:old.start(1)]!=after[:new.start(1)] or before[old.end(1):]!=after[new.end(1):]:
            raise ValueError('Native prose edits must preserve heading, summary and card identity')
        if re.search(r'<(?:script|style|iframe|object|embed)\b|\bon\w+\s*=|javascript:',new[1],re.I):
            raise ValueError('Native prose edit contains executable content')
        if result.count(before)!=1:raise ValueError('Ambiguous native prose baseline')
        result=result.replace(before,after,1)
    if not seen:raise ValueError('Empty native prose edits')
    return result

def meaningful_visuals(doc):
    from reader_layout import ReaderContract
    actual={digest(x):dict(kind='vector') for x in re.findall(r'<svg\b.*?</svg>',doc,re.S) if '<title' in x}
    parsed=ReaderContract(doc)
    for image in [n for n in parsed.nodes if n['tag']=='img']:
        src=image['attrs'].get('src','')
        match=re.fullmatch(r'data:image/(?:webp|png|jpeg);base64,([A-Za-z0-9+/=\r\n]+)',src)
        if not match:raise ValueError('Native illustration must remain embedded')
        data=base64.b64decode(match[1],validate=True)
        actual[digest(data)]=dict(kind='image',alt=image['attrs'].get('alt',''))
    # An inspected CSS composition is artwork too; bind its markup AND original styles.
    styles=[digest(x) for x in re.findall(r'<style\b[^>]*>(.*?)</style>',doc,re.S)]
    for figure in re.findall(r'<figure\b.*?</figure>',doc,re.S):
        if not re.search(r'<(?:img|svg)\b',figure) and 'role="img"' in figure:
            if not styles or not re.search(r'aria-label="[^"]+"',figure) or '<figcaption>' not in figure:
                raise ValueError('CSS composition needs styles, accessible description and caption')
            actual[digest(dict(figure=figure,styles=styles))]=dict(kind='css-composition')
    return actual


def cards(doc):
    class Capture(HTMLParser):
        def __init__(self):
            super().__init__();self.stack=[];self.found={};self.ordinal=0
            self.lines=[0]
            for line in doc.splitlines(keepends=True):self.lines.append(self.lines[-1]+len(line))
        def absolute_position(self):
            line,col=self.getpos();return self.lines[line-1]+col
        def handle_starttag(self,tag,attrs):
            if tag=='details':
                a=dict(attrs);study='study-card' in a.get('class','').split()
                if study:self.ordinal+=1
                key=(a.get('id') or '@ordinal:'+str(self.ordinal).zfill(2)) if study else None
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
    result=dict(cards={k:digest(v) for k,v in cards(doc).items()},
                svgHashes=[digest(x) for x in re.findall(r'<svg\b.*?</svg>',doc,re.S)],
                scripts=[digest(x) for x in re.findall(r'<script\b[^>]*>(.*?)</script>',doc,re.S)],
                title=plain(re.search(r'<title>(.*?)</title>',doc,re.S)[1]))
    images=[sha for sha,item in meaningful_visuals(doc).items() if item['kind']=='image']
    if images:result['imageHashes']=images
    compositions=[sha for sha,item in meaningful_visuals(doc).items() if item['kind']=='css-composition']
    if compositions:result['cssCompositionHashes']=compositions
    return result

def validate(path, run):
    path = Path(path)
    original = (path/'original.html').read_bytes()
    source = original.decode('utf-8-sig')
    plan = read(path/'source-reader-plan.json')
    passage = read(path/'passage.json')
    if plan.get('profile') not in PROFILES or plan.get('originalSha256') != digest(original) or digest(original) != run['revision']['originalSha256']:
        raise ValueError('Source profile or original binding mismatch')
    if not passage.get('verified') or digest({k:v for k,v in passage.items() if k!='sha256'}) != passage['sha256'] or plan.get('passageSha256') != passage['sha256']:
        raise ValueError('Source passage integrity mismatch')
    state = snapshot(source)
    if plan.get('sourceSnapshot') != state:
        raise ValueError('Changed native cards, SVG or script')
    edits_path=path/'source-content-edits.json'
    if plan.get('contentEditsSha256'):
        edits=read(edits_path)
        if digest(edits)!=plan['contentEditsSha256'] or edits.get('originalSha256')!=digest(original):
            raise ValueError('Native content edits are not bound to the source plan')
        source=apply_content_edits(source,edits)
        if plan.get('reviewedSnapshot')!=snapshot(source):
            raise ValueError('Native edited content changed after review')
    elif edits_path.exists():
        raise ValueError('Native content edits need an explicit source-plan binding')
    review = read(path/'source-exegesis-review.json')
    if review.get('originalSha256') != digest(original) or review.get('passageSha256') != passage['sha256']:
        raise ValueError('Stale native editorial review')
    if plan.get('contentEditsSha256') and review.get('reviewedContentSha256')!=digest(snapshot(source)['cards']):
        raise ValueError('Stale native edited-content review')
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
    actual = meaningful_visuals(source)
    if {x.get('sha256') for x in visual.get('items',[])} != set(actual) or (not actual and not visual.get('textOnlyRationale')):
        raise ValueError('Native meaningful visual inventory mismatch')
    for item in visual['items']:
        if not all(item.get(k) for k in ('purpose','captionScope','inspectedAt','inspectionEvidence')) or item.get('decision') != 'retain':
            raise ValueError('Native visual must be actually inspected and individually retained')
    return source, plan, passage, review, visual

def structural_changes(source, passage, profile=PROFILE):
    """Only this inspected native structure is supported, never arbitrary HTML repair."""
    if profile=='luke-9-57-native-v1':
        from source_reader_luke957 import structural_changes as luke_changes
        return luke_changes(source,passage)
    if profile=='luke-10-native-v1':
        from source_reader_luke101 import structural_changes as luke_changes
        return luke_changes(source,passage)
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
    verses = re.findall(r'<p\b[^>]*><span class="verse-no">(\d+)</span>(.*?)</p>',body,re.S)
    def verse_text(number, text):
        if profile=='luke-9-51-native-v1':
            # The supplied 2) is an annotation, never part of the Bible sentence.
            note=r' <sup><a href="#manuscripts" title="제공된 각주 번호와 사본 차이의 설명">2\)</a></sup>'
            match=re.fullmatch(r'<span class="verse-content">(.*?)</span>('+note+r')?',text,re.S)
            if not match or (match[2] and number!='55'):
                raise ValueError('Native Scripture annotation needs individual review')
            return plain(match[1])
        return plain(text)
    if [(str(v['verse']),v['text']) for v in passage['verses']] != [(n,verse_text(n,t)) for n,t in verses]:
        raise ValueError('Native Bible differs from verified passage')
    # Preserve every original verse byte, replacing only the disclosure container and heading.
    new = '<aside id="scripture" class="scripture-panel"><div class="scripture-heading">'+heading[1]+'</div>'+body+'</aside>'
    change(block[0],new)
    if profile==PROFILE:
        change('const fontSizes=[17,19,21]','const fontSizes=[18,20,22]')
    elif profile in ('ezekiel-native-v1','luke-9-51-native-v1'):
        if source.count('const fontSizes=[18,20,22]')!=1:raise ValueError('Unexpected native font controls')
    else:raise ValueError('Unknown native UI profile')
    change("if(a.classList.contains('dialog-link'))setSummary(false);reveal(target);","if(a.classList.contains('dialog-link')){setSummary(false);target.querySelectorAll('details').forEach(d=>d.open=true);}reveal(target);")
    change("dialog.addEventListener('cancel',()=>{if(lastFocus&&lastFocus.focus)lastFocus.focus()});","dialog.addEventListener('cancel',e=>{e.preventDefault();closeToc()});dialog.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();closeToc()}});")
    change('<a class="brand" href="#top">','<a class="brand" href="https://laguna821.github.io/BNOC/">')
    if profile==PROFILE:
        change('화면 글꼴은 기기의 기본 글꼴을 사용하므로 기기에 따라 조금 다르게 보일 수 있습니다.','SameTone Lite 가변 글꼴과 원어용 글꼴을 이 파일에 내장했습니다.')
    elif profile=='ezekiel-native-v1':
        change('8개 장 · 43개 해설 카드 · 20개 자료 · 묵상 기록','8개 장 · 43개 해설 카드 · 원전 대조 자료 · 묵상 기록')
        change('이미지와 글은 오프라인으로 읽을 수 있습니다. 외부 자료 링크는 인터넷 연결이 필요합니다.','이미지와 글은 오프라인으로 읽을 수 있습니다. 외부 자료 링크는 인터넷 연결이 필요합니다. SameTone Lite 가변 글꼴과 원어용 글꼴도 이 파일에 내장했습니다.')
    elif profile=='luke-9-51-native-v1':
        change('글과 그림은 오프라인으로 읽을 수 있습니다. 출처 링크를 여는 데에는 인터넷 연결이 필요합니다.','글과 그림은 오프라인으로 읽을 수 있습니다. 출처 링크를 여는 데에는 인터넷 연결이 필요합니다. SameTone Lite 가변 글꼴과 원어용 글꼴도 이 파일에 내장했습니다.')
    return changes

def render(path,run):
    source,plan,passage,review,visual = validate(path,run)
    doc = source
    changes = structural_changes(source,passage,plan['profile'])
    for old,new in changes: doc=doc.replace(old,new,1)
    # Exact inverse is stronger than a text-only comparison: scripts, keys, anchors and all prose survive.
    restored=doc
    for old,new in reversed(changes):
        if restored.count(new)!=1: raise ValueError('Ambiguous source-preservation inverse')
        restored=restored.replace(new,old,1)
    if restored!=source: raise ValueError('Unapproved native change')
    expected=plan.get('reviewedSnapshot',plan['sourceSnapshot'])
    if {k:digest(v) for k,v in cards(doc).items()}!=expected['cards']:
        raise ValueError('Native authored card changed')
    if plan['profile']=='luke-10-native-v1':
        from source_reader_luke101 import verify_existing_fonts
        verify_existing_fonts(source,(ROOT/'web/reader-fonts.css').read_text(encoding='utf-8'))
        names=('automation/revision.css','automation/source_reader_luke101.css')
        licenses=''  # The reviewed source already embeds the full font licenses.
    else:
        names=('web/reader-fonts.css','automation/typography.css','automation/revision.css','automation/source_reader.css')
        licenses=(ROOT/'web/assets/FONT-LICENSES.txt').read_text(encoding='utf-8').replace('*/','* /')
    css='\n'.join((ROOT/name).read_text(encoding='utf-8') for name in names)
    logo=(ROOT/'web/logo.svg').read_text(encoding='utf-8')
    brand=re.search(r'(<span class="(?:brand-symbol|brand-mark)"(?: aria-hidden="true")?>)(.*?)(</span>)',doc,re.S)
    if not brand:raise ValueError('Native brand icon missing')
    doc=doc[:brand.start(2)]+logo+doc[brand.end(2):]
    meta=dict(issueId=run['id'],templateVersion=VERSION,profile=plan['profile'],originalSha256=plan['originalSha256'],
              passageSha256=passage['sha256'],sourcePlanSha256=digest(plan),
              editorialReviewSha256=digest(review),visualPlanSha256=digest(visual))
    addition='<style id="bnoc-source-reader">'+css+'\n/* Embedded font licenses\n'+licenses+'\n*/</style>'
    addition+='<script type="application/json" id="bnoc-provenance">'+json.dumps(meta,ensure_ascii=False).replace('<','\\u003c')+'</script>'
    doc=doc.replace('</head>',addition+'</head>',1)
    doc=revision.stamp(doc,run['revision'])
    filename=html.escape(Path(run['relativePath']).name.rstrip('.'),quote=True)
    message='기존 해설·삽화·메모 구조를 보존하고 원전 대조와 읽기 환경을 보완했습니다.' if not plan.get('contentEditsSha256') else '기존 해설과 메모 구조를 살리고, 원어·성경의 연결을 보강하며 읽기 환경을 보완했습니다.'
    message=plan.get('revisionDescription') or message
    notice='<aside class="bnoc-revision-notice">개정 '+run['revision']['revisedAt'][:10]+' · '+html.escape(message)+' <a href="'+filename+'" download="'+filename+'">HTML 저장</a></aside>'
    doc=re.sub(r'(<body\b[^>]*>)',lambda m:m[0]+notice,doc,count=1)
    doc=re.sub(r'(<body\b)',lambda m:m[0]+' data-bnoc-source-profile="'+plan['profile']+'"',doc,count=1)
    metrics=audit_html(doc)
    return doc,dict(**meta,htmlSha256=digest(doc.encode()),contentSha256=digest(expected['cards']),title=plan['sourceSnapshot']['title'],date=run['date'],metrics=metrics)

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
    luke=bool(re.search(r'<body\b[^>]*data-bnoc-source-profile="luke-9-57-native-v1"',doc))
    luke10=bool(re.search(r'<body\b[^>]*data-bnoc-source-profile="luke-10-native-v1"',doc))
    require(len(buttons)==4 and any(('data-toc' if luke else 'data-open-toc') in n['attrs'] for n in buttons),'Four reading controls required')
    for key in ('summaryBtn','foldBtn' if luke else 'collapseBtn','topBtn'):
        require(len(byid(key))==1 and any(n is byid(key)[0] for n in buttons),'Toolbar control missing '+key)
    for key,tag in (('tocDialog','dialog'),('searchInput' if luke else 'tocSearch','input'),('closeToc','button'),('fontBtn','button'),('themeBtn','button')):
        require(len(byid(key))==1 and byid(key)[0]['tag']==tag,'Native control missing '+key)
    require(len([n for n in p.nodes if n['tag']=='textarea' and 'data-note' in n['attrs']])==3,'Three native note fields required')
    tables=[n for n in p.nodes if n['tag']=='table']
    for table in tables:
        require(bool(p.within(table,'thead')),'Explicit print headings required')
        require(cls(table,'lex-table') or cls(table,'bridge-table') or (luke and cls(table,'lex')) or (luke10 and cls(table,'study-table')),'Unknown native table requires review')
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
    # The publisher owns issue/date fields; an audit returns only immutable evidence bindings.
    return {k:binding[k] for k in ('originalSha256','passageSha256','htmlSha256','contentSha256','sourcePlanSha256','editorialReviewSha256','visualPlanSha256')}
