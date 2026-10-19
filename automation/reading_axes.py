"""Bind an authored three-part reading guide to real exposition, preserving native records."""
import html,json,re
from pathlib import Path
from bible import digest,plain
ROOT=Path(__file__).resolve().parents[1]
VERSION='bnoc-analysis-guide-1.0'
AXES={'orthodoxy':'① 정론 · 무엇을 믿는가','orthopraxy':'② 정행 · 어떻게 살아가는가','application':'③ 현대 적용 · 개인·공동체·공적 삶'}

def validate(guide, cards):
    if set(guide.get('axes',{}))!=set(AXES):raise ValueError('Three distinct reading axes are required')
    if guide.get('blockingFindings'):raise ValueError('Reading-axis concerns remain unresolved')
    if not guide.get('model') or not guide.get('reviewedAt'):raise ValueError('Record the actual reading-axis review')
    targets=[]
    for axis,item in guide['axes'].items():
        key=item.get('cardId');raw=cards.get(key)
        if not raw or not item.get('quote') or item['quote'] not in plain(raw):
            raise ValueError('Reading axis is not anchored to real exposition: '+axis)
        if item.get('beforeSha256') and item['beforeSha256']!=digest(raw):
            raise ValueError('Reading-axis exposition changed: '+axis)
        if not item.get('introduction') or not item.get('rationale'):
            raise ValueError('Read and explain each axis before adding navigation: '+axis)
        if '<' in item['introduction'] or '>' in item['introduction']:
            raise ValueError('Reading-axis introduction must be authored plain text')
        targets.append(key)
    if len(set(targets))!=3:raise ValueError('Do not collapse the three reading axes into one exposition target')
    scopes=guide.get('applicationScopes',{})
    if set(scopes)!={'personal','community','public'}:raise ValueError('Read personal, community and public application separately')
    for name,item in scopes.items():
        scope_text=guide['axes']['application']['introduction'] if item.get('cardId')=='@guide:application' else plain(cards.get(item.get('cardId'),''))
        if not item.get('quote') or item['quote'] not in scope_text:
            raise ValueError('Application scope is not anchored to actual prose: '+name)
    return guide

def apply(doc,guide):
    """Add only exact, reversible introductions and navigation; never rewrite existing exposition."""
    from source_reader import cards
    if 'id="bnoc-analysis-guide"' in doc:raise ValueError('Reading-axis guide already exists')
    original=doc;before=cards(doc);validate(guide,before);changes=[]
    for axis,label in AXES.items():
        item=guide['axes'][axis];old=before[item['cardId']]
        paragraphs=''.join('<p>'+html.escape(p)+'</p>' for p in item['introduction'].split('\n\n') if p.strip())
        marker='<div class="analysis-landmark" id="analysis-'+axis+'"><h3>'+label+'</h3>'+paragraphs+'</div>'
        opening=re.search(r'<div\b[^>]*class=["\'][^"\']*\bprose\b[^"\']*["\'][^>]*>',old)
        if not opening:raise ValueError('Reading-axis target needs an authored prose body')
        new=old[:opening.end()]+marker+old[opening.end():]
        if doc.count(old)!=1:raise ValueError('Ambiguous reading-axis target')
        doc=doc.replace(old,new,1);changes.append((old,new))
    nav='<nav id="bnoc-analysis-guide" class="analysis-guide" aria-label="정론·정행·현대 적용"><p class="analysis-guide-title">세 관점으로 깊이 읽기</p>'+''.join('<a href="#analysis-'+axis+'">'+label+'</a>' for axis,label in AXES.items())+'</nav>'
    # Insert in the same article column as the always-open Scripture, without changing the sidebar/layout.
    scripture=re.search(r'<aside\b[^>]*\bid=["\']scripture["\'][^>]*>',doc)
    if not scripture:raise ValueError('Reading guide requires the always-open Scripture aside')
    doc=doc[:scripture.start()]+nav+doc[scripture.start():];changes.append(('',nav))
    css=(ROOT/'automation/reading_axes.css').read_text(encoding='utf-8')
    js=(ROOT/'automation/reading_axes.js').read_text(encoding='utf-8')
    style='<style id="bnoc-analysis-style">'+css+'</style>'
    script='<script id="bnoc-analysis-navigation">'+js+'</script>'
    doc=doc.replace('</head>',style+'</head>',1).replace('</body>',script+'</body>',1)
    restored=doc.replace(style,'',1).replace(script,'',1).replace(nav,'',1)
    for old,new in reversed(changes[:-1]):
        if restored.count(new)!=1:raise ValueError('Ambiguous reading-axis inverse')
        restored=restored.replace(new,old,1)
    # Exact bytes outside the explicitly added guide remain unchanged, including notes and scripts.
    if restored!=original or cards(restored)!=before:raise ValueError('Reading guide altered authored exposition or records')
    audit(doc)
    return doc,{'version':VERSION,'guideSha256':digest(guide),'preservedCardsSha256':digest(before)}

def audit(doc):
    from reader_layout import ReaderContract
    p=ReaderContract(doc)
    byid=lambda key:[n for n in p.nodes if n['attrs'].get('id')==key]
    nav=byid('bnoc-analysis-guide')
    if len(nav)!=1 or nav[0]['tag']!='nav':raise ValueError('Three-axis navigation missing')
    for axis in AXES:
        nodes=byid('analysis-'+axis)
        if len(nodes)!=1 or not any('prose' in n['attrs'].get('class','').split() for n in nodes[0]['parents']):
            raise ValueError('Three-axis destination must be inside its full exposition: '+axis)
        if not any(n['tag']=='a' and n['attrs'].get('href')=='#analysis-'+axis for n in p.within(nav[0])):
            raise ValueError('Three-axis navigation target missing: '+axis)
    return {'readingAxes':3}

def finalize(doc,meta,path):
    source=Path(path)/'reading-axes.json'
    if not source.is_file():raise ValueError('Read the original three-part analysis contract and author reading-axes.json first')
    guide=json.loads(source.read_text(encoding='utf-8-sig'))
    doc,binding=apply(doc,guide)
    return doc,{**meta,'readingAxes':binding,'htmlSha256':digest(doc.encode('utf-8'))}

def verify_review(report,meta):
    if report.get('readingAxes')!=meta.get('readingAxes'):raise ValueError('Stale three-axis reading review')
    item=report.get('checks',{}).get('readingAxes',{})
    if item.get('passed') is not True or not item.get('evidence'):
        raise ValueError('Actually review three-part exposition and navigation before publishing')
