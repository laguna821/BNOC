"""Explicit, hash-bound archive revisions. Private context never enters public manifests."""
import datetime as dt
import json
import re
import subprocess
from pathlib import PurePosixPath, Path
from html.parser import HTMLParser
from bible import digest, save

KINDS = {'design', 'theology', 'expansion', 'scripture'}

def source(repo, relative, ref='origin/main'):
    p = PurePosixPath(relative)
    if p.is_absolute() or '..' in p.parts or '\\' in relative or not re.fullmatch(r'20\d{2}/\d{8}/[^/]+\.html\.?', relative):
        raise ValueError('Revision target must be an existing archive HTML')
    return subprocess.check_output(['git', 'show', ref + ':' + relative], cwd=repo)

def check_base(repo, revision, relative, ref):
    actual = digest(source(repo, relative, ref))
    if actual != revision['originalSha256']:
        raise ValueError('Revision conflict: original document changed; inspect and start a new revision')

def begin(c, relative, reference, date, kinds, intent, mode):
    import bnoc
    if not kinds or not set(kinds) <= KINDS:
        raise ValueError('Choose design, theology, expansion, or scripture')
    if 'scripture' in kinds and kinds != ['scripture']:
        raise ValueError('Scripture visibility revisions must be isolated')
    if not intent.strip():
        raise ValueError('Record preserved editorial intent before revising')
    bnoc.git(c['repo'], 'fetch', 'origin', 'main')
    base = bnoc.git(c['repo'], 'rev-parse', 'origin/main')
    raw = source(c['repo'], relative, base)
    # The archive directory remains authoritative, including its known legacy typo.
    folder = PurePosixPath(relative).parent.name; year = int(relative[:4])
    expected = dt.date(year, int(folder[4:6]) if folder.startswith(str(year)) else int(folder[:2]), int(folder[6:]) if folder.startswith(str(year)) else int(folder[2:4])).isoformat()
    if date != expected:
        raise ValueError('Revision must preserve the original archive date: ' + expected)
    service = 'revision-' + digest([relative, digest(raw), sorted(kinds)])[:20]
    result = bnoc.make_run(c, reference, date, service, mode)
    path = bnoc.runpath(c, result['runId'])
    run = bnoc.load(path / 'run.json')
    if not run.get('revision'):
        run['relativePath'] = relative
        run['revision'] = dict(originalCommit=base, originalSha256=digest(raw),
            revisedAt=dt.datetime.now(dt.timezone.utc).isoformat(), kinds=sorted(kinds),
            intent=intent, publicPath=relative.rstrip('.'))
        (path / 'original.html').write_bytes(raw)
        save(path / 'run.json', run)
        state = bnoc.state(c); state['issues'][run['id']]['relativePath'] = relative
        save(c['root'] / 'state.json', state)
    result['relativePath'] = relative
    return result

class Content(HTMLParser):
    """Compare original text, scripts, IDs and interactive attributes for design-only edits."""
    def __init__(self):
        super().__init__(convert_charrefs=True); self.skip=0; self.parts=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='style': self.skip+=1
        if not self.skip:
            stable={k:v for k,v in attrs if k not in {'style','class'} and tag!='meta'}
            if stable:self.parts.append([tag,stable])
    def handle_endtag(self, tag):
        if tag=='style':self.skip=max(0,self.skip-1)
    def handle_data(self, data):
        if not self.skip and data.strip():self.parts.append(data.strip())

def content_hash(doc):
    p=Content();p.feed(doc);return digest(p.parts)

def public_metadata(revision):
    return {k:revision[k] for k in ('originalCommit','originalSha256','revisedAt','kinds')}

def stamp(doc, revision):
    import html
    meta = '<meta name="bnoc-revised" content="' + html.escape(revision['revisedAt'],quote=True) + '"><meta name="bnoc-revision-kinds" content="' + ','.join(revision['kinds']) + '">'
    return doc.replace('</head>',meta+'</head>',1)

def render_design(path, run):
    root=Path(__file__).resolve().parents[1]
    raw=(path/'original.html').read_bytes()
    if digest(raw)!=run['revision']['originalSha256']:
        raise ValueError('Original snapshot changed; recover the recorded Git blob')
    original=raw.decode('utf-8-sig')
    if run['revision']['kinds']==['scripture']:
        # Narrow migration of our exact old renderer markup, never arbitrary legacy DOM.
        opening='<details class="scripture"><summary>성경 본문 전체 보기</summary>'
        if original.count(opening)!=1:
            raise ValueError('Expected exactly one known collapsed scripture block')
        start=original.index(opening); end=original.index('</details>',start)
        inner=original[start+len(opening):end]
        if '<details' in inner or '<h2>' not in inner or 'verse-no' not in inner:
            raise ValueError('Unexpected scripture structure; inspect individually')
        doc=original[:start]+'<aside class="scripture">'+inner+'</aside>'+original[end+10:]
        # Reversibility proves all scripture, commentary, assets, scripts and storage keys are untouched.
        restored=doc[:start]+opening+inner+'</details>'+doc[start+len('<aside class="scripture">')+len(inner)+len('</aside>'):]
        if restored!=original:raise ValueError('Visibility migration changed unrelated content')
        doc=stamp(doc,run['revision'])
        return doc,dict(originalSha256=run['revision']['originalSha256'],contentSha256=content_hash(original),htmlSha256=digest(doc.encode()))
    css=(root/'web/reader-fonts.css').read_text(encoding='utf-8')+'\n'+(root/'automation/typography.css').read_text(encoding='utf-8')+'\n'+(root/'automation/revision.css').read_text(encoding='utf-8')
    licenses=(root/'web/assets/FONT-LICENSES.txt').read_text(encoding='utf-8').replace('*/','* /')
    css+='\n/* Embedded font licenses\n'+licenses+'\n*/'
    # No script or authored DOM replacement. This also preserves localStorage keys and fragment links.
    doc=original.replace('</head>','<style id="bnoc-remake-design">'+css+'</style></head>',1)
    if content_hash(original)!=content_hash(doc):raise ValueError('Design changed authored content or interaction')
    doc=stamp(doc,run['revision'])
    banner='<aside class="bnoc-revision-notice">디자인 개정 '+run['revision']['revisedAt'][:10]+' · 최초 게재일과 원문은 유지됩니다.</aside>'
    doc=re.sub(r'(<body\b[^>]*>)',lambda m:m[0]+banner,doc,count=1,flags=re.I)
    return doc,dict(originalSha256=run['revision']['originalSha256'],contentSha256=content_hash(original),htmlSha256=digest(doc.encode()))

def audit_design(path, run):
    report=json.loads((path/'review.json').read_text(encoding='utf-8'))
    rebuilt,binding=render_design(path,run)
    output=(path/PurePosixPath(run['relativePath']).name.rstrip('.')).read_bytes()
    if digest(output)!=binding['htmlSha256']:raise ValueError('Design output changed; render and review again')
    for k,v in binding.items():
        if report.get(k)!=v:raise ValueError('Stale design review: '+k)
    if report.get('blockingFindings') or not report.get('model') or not report.get('reviewedAt'):raise ValueError('Incomplete design review')
    if report.get('preservedIntent')!=run['revision']['intent']:raise ValueError('Editorial intent not confirmed')
    for key in ('contentPreserved','mobileLightDark','mobileTables','readerControls','originalLanguages','searchNotesDownload','printLayout'):
        item=report.get('checks',{}).get(key,{})
        if item.get('passed') is not True or not item.get('evidence'):raise ValueError('Design review incomplete: '+key)
    return binding
