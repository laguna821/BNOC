"""Record editorial judgement before design; never score theological quality mechanically."""
import datetime as dt
import json
from pathlib import Path
from bible import digest, plain

AXES = ('textAndContext', 'orthodoxy', 'orthopraxy', 'application', 'originalLanguages', 'readerDepth')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def content(manuscript):
    """Bind all authored text and sources, independent of later illustration/layout choices."""
    return {k: v for k, v in manuscript.items() if k not in
            {'figures', 'heroFigure', 'scriptureCollapsible', 'revision', 'coverage', 'sections'}} | {
        'sections': [{k: v for k, v in section.items() if k not in {'cards', 'presentation'}} | {
            'cards': [{k: v for k, v in card.items() if k not in {'figure','figurePosition','tableLayout'}} for card in section['cards']]
        } for section in manuscript['sections']]}


def timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed
    except (AttributeError, TypeError, ValueError):
        raise ValueError('A timezone-aware review timestamp is required')


def review(manuscript, passage, run_dir):
    path = Path(run_dir) / 'editorial-review.json'
    if not path.is_file():
        raise ValueError('Read and review the manuscript before layout: editorial-review.json missing')
    report = read(path)
    if report.get('contentSha256') != digest(content(manuscript)) or report.get('passageSha256') != passage['sha256']:
        raise ValueError('Stale editorial review: reread changed text or passage')
    if report.get('decision') != 'ready-for-design' or report.get('blockingFindings'):
        raise ValueError('Editorial concerns remain unresolved')
    if not report.get('model') or not report.get('thesis') or not report.get('preservationDecision'):
        raise ValueError('Record reviewer, text-specific thesis and what was retained or changed')
    timestamp(report.get('reviewedAt'))
    cards = {c['id']: c for s in manuscript['sections'] for c in s['cards']}
    for axis in AXES:
        assessment = report.get('assessments', {}).get(axis, {})
        if not assessment.get('rationale') or not assessment.get('anchors'):
            raise ValueError('Editorial reading evidence missing: ' + axis)
        for anchor in assessment['anchors']:
            card = cards.get(anchor.get('cardId'))
            if not card or not anchor.get('quote') or anchor['quote'] not in plain(card['html']):
                raise ValueError('Editorial evidence does not match the manuscript: ' + axis)
    sources = {s['id'] for s in manuscript['sources']}
    if set(report.get('checkedSourceIds', [])) != sources:
        raise ValueError('Editorial source checking incomplete')
    # These are a review record and anchors, not a machine verdict about the interpretation.
    return report


def visuals(manuscript, passage, run_dir, reviewed=None):
    reviewed = reviewed or review(manuscript, passage, run_dir)
    path = Path(run_dir) / 'visual-plan.json'
    if not path.is_file():
        raise ValueError('Decide visual needs after editorial review: visual-plan.json missing')
    plan = read(path)
    if plan.get('contentSha256') != reviewed['contentSha256'] or plan.get('editorialReviewSha256') != digest(reviewed):
        raise ValueError('Visual plan predates the reviewed interpretation')
    if timestamp(plan.get('decidedAt')) < timestamp(reviewed['reviewedAt']):
        raise ValueError('Visual planning must follow editorial review')
    if not plan.get('rationale') or plan.get('mode') not in ('text-only', 'illustrated'):
        raise ValueError('Explain this manuscript’s visual needs, including a text-only decision')
    figures = {f['id']: f for f in manuscript.get('figures', [])}
    placements = {}
    if manuscript.get('heroFigure'):
        placements.setdefault(manuscript['heroFigure'], []).append('hero')
    for section in manuscript['sections']:
        for card in section['cards']:
            if card.get('figure'):
                placements.setdefault(card['figure'], []).append(card['id'])
    items = plan.get('items', [])
    if plan['mode'] == 'text-only':
        if figures or placements or items:
            raise ValueError('Text-only plan contains illustrations')
        return plan
    if not items:
        raise ValueError('Illustrated plan needs actual planned items')
    if len({x['id'] for x in items}) != len(items):
        raise ValueError('Duplicate visual-plan item')
    if {x['id'] for x in items} != set(figures) or set(placements) != set(figures):
        raise ValueError('Planned, supplied and embedded figures must match; no silent omissions or unused assets')
    for item in items:
        f = figures[item['id']]
        if not item.get('purpose') or placements[item['id']] != [item.get('at')]:
            raise ValueError('Figure placement must serve its recorded explanatory purpose')
        if item.get('kind') != f.get('kind'):
            raise ValueError('A diagram cannot silently replace a planned illustration')
        if item.get('at')!='hero':
            card=next(c for s in manuscript['sections'] for c in s['cards'] if c['id']==item['at'])
            if item.get('position','before')!=card.get('figurePosition','before'):
                raise ValueError('Figure before/after position differs from plan')
        asset = (Path(run_dir) / f['file']).resolve()
        if not asset.is_relative_to(Path(run_dir).resolve()) or not asset.is_file():
            raise ValueError('Visual asset missing or outside run')
        data = asset.read_bytes()
        asset_hash = digest(data)
        inspection = f.get('inspection', {})
        if f.get('sha256') != asset_hash or inspection.get('sha256') != asset_hash:
            raise ValueError('Visual asset changed after inspection')
        if not inspection.get('evidence'):
            raise ValueError('Record what was actually inspected in each visual')
        timestamp(inspection.get('reviewedAt'))
        provenance = f.get('provenance', {})
        if f['kind'] == 'generated-illustration':
            raster = data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff') or (data[:4] == b'RIFF' and data[8:12] == b'WEBP')
            if not raster:
                raise ValueError('Generated illustration requires an actual raster image, not a renamed diagram')
            if not all(provenance.get(k) for k in ('tool', 'prompt', 'originalSha256', 'generatedAt')):
                raise ValueError('Record the actual image generation tool, prompt, time and original asset hash')
            timestamp(provenance['generatedAt'])
        elif f['kind'] == 'sourced-image':
            if not provenance.get('url') or not provenance.get('rights'):
                raise ValueError('Sourced image needs origin and usage conditions')
        elif f['kind'] == 'diagram':
            if not provenance.get('basis'):
                raise ValueError('Explain the textual/data basis of the diagram')
    return plan


def validate(manuscript, passage, run_dir):
    reviewed = review(manuscript, passage, run_dir)
    plan = visuals(manuscript, passage, run_dir, reviewed)
    return {'contentSha256': reviewed['contentSha256'], 'editorialReviewSha256': digest(reviewed),
            'visualPlanSha256': digest(plan)}
