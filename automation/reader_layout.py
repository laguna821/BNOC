"""Reader interaction upgrades without changing authored words or embedded media."""
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from bible import digest, plain

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'bnoc-reader-1.2'
TOOLS = '''<nav class="reading-tools" aria-label="읽기 도구"><div class="reading-tools-inner">
<button id="search" type="button">목차 · 찾기</button><button id="summary" type="button" aria-pressed="false">요약 보기</button><button id="collapse" type="button" aria-expanded="true">전체 접기</button><button id="top" type="button">맨 위로</button>
</div></nav>'''
DIALOG = '''<dialog id="searchDialog" aria-labelledby="searchTitle"><div class="dialog-head"><h2 id="searchTitle">목차와 본문 찾기</h2><button id="closeSearch" type="button">닫기</button></div><label for="query">검색어</label><input id="query" type="search" autocomplete="off" placeholder="단어나 내용을 입력하세요"><p id="matchCount" role="status" aria-live="polite"></p><div id="matches"></div></dialog>'''


def _span(attrs, name):
    m = re.search(r'\b' + name + r'\s*=\s*["\']?(\d+)', attrs, re.I)
    return max(1, int(m[1])) if m else 1


def responsive_table(table):
    """Derive mobile labels from actual column headers, preserving each cell's HTML."""
    if re.search(r'class=["\'][^"\']*\breading-table\b', table):
        return table
    if len(re.findall(r'<table\b', table, re.I)) != 1:
        raise ValueError('Nested tables need an individual mobile layout')
    rows = list(re.finditer(r'<tr\b[^>]*>(.*?)</tr>', table, re.S | re.I))
    cells = lambda row: list(re.finditer(r'<(th|td)\b([^>]*)>(.*?)</\1>', row, re.S | re.I))
    headers = []
    header_rows = set()
    header_spans = {}
    for index, row in enumerate(rows):
        parts = cells(row[1])
        if parts and all(c[1].lower() == 'th' and not re.search(r'\bscope=["\']?row', c[2]) for c in parts):
            column = 0
            occupied = dict(header_spans)
            header_spans = {k: v - 1 for k, v in header_spans.items() if v > 1}
            header_rows.add(index)
            for cell in parts:
                while occupied.get(column, 0):
                    column += 1
                label = plain(cell[3]).strip()
                for offset in range(_span(cell[2], 'colspan')):
                    while len(headers) <= column + offset:
                        headers.append([])
                    if label and label not in headers[column + offset]:
                        headers[column + offset].append(label)
                    if _span(cell[2], 'rowspan') > 1:
                        header_spans[column + offset] = _span(cell[2], 'rowspan') - 1
                column += _span(cell[2], 'colspan')
        elif header_rows:
            break
    positions = {}
    spans = {}
    for index, row in enumerate(rows):
        if index in header_rows:
            continue
        column = 0
        occupied = dict(spans)
        spans = {k: v - 1 for k, v in spans.items() if v > 1}
        for cell in cells(row[1]):
            while occupied.get(column, 0):
                column += 1
            width = _span(cell[2], 'colspan')
            labels = []
            for col in range(column, column + width):
                if col < len(headers):
                    labels.extend(x for x in headers[col] if x not in labels)
                if _span(cell[2], 'rowspan') > 1:
                    spans[col] = _span(cell[2], 'rowspan') - 1
            label = ' · '.join(labels)
            opening = '<' + cell[1] + cell[2] + '>'
            role = 'rowheader' if cell[1].lower() == 'th' else 'cell'
            attrs = '' if re.search(r'\brole\s*=', cell[2]) else f' role="{role}"'
            if cell[1].lower() == 'td' and label:
                attrs += ' data-label="' + html.escape(label, quote=True) + '"'
                content = '<span class="cell-label" aria-hidden="true">' + html.escape(label) + '</span>' + cell[3]
            else:
                content = cell[3]
            positions[row.start(1) + cell.start()] = (row.start(1) + cell.end(), opening[:-1] + attrs + '>' + content + '</' + cell[1] + '>')
            column += width
    for start, (end, replacement) in sorted(positions.items(), reverse=True):
        table = table[:start] + replacement + table[end:]
    opening = re.match(r'<table\b[^>]*>', table, re.I)[0]
    if re.search(r'\bclass=', opening):
        updated = re.sub(r'(\bclass=["\'])', r'\1reading-table ', opening, count=1)
    else:
        updated = opening[:-1] + ' class="reading-table">'
    if not re.search(r'\brole=', updated):
        updated = updated[:-1] + ' role="table">'
    return updated + table[len(opening):]


class ContentSnapshot(HTMLParser):
    """Compare authored main content, language direction, links, verses and media."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.words = []; self.languages = []; self.links = []; self.verses = []; self.media = []
        self.skip_label = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.skip_label:
            if tag == 'span': self.skip_label += 1
            return
        if 'cell-label' in a.get('class', '').split():
            self.skip_label = 1; return
        if a.get('lang'): self.languages.append((a['lang'], a.get('dir')))
        if tag == 'a': self.links.append(a.get('href'))
        if 'data-verse' in a: self.verses.append(a['data-verse'])
        if tag == 'img': self.media.append((digest(a.get('src', '')), a.get('alt')))
        if tag == 'svg': self.media.append(('svg', a))
        if tag in ('path', 'text', 'rect', 'line', 'polyline', 'polygon', 'circle', 'ellipse', 'tspan'):
            self.media.append((tag, a))

    def handle_endtag(self, tag):
        if tag == 'span' and self.skip_label: self.skip_label -= 1

    def handle_data(self, data):
        if not self.skip_label and data.strip(): self.words.append(' '.join(data.split()))


def content_snapshot(doc):
    main = re.search(r'<main\b[^>]*>(.*?)</main>', doc, re.S)
    if not main: raise ValueError('Reader main content missing')
    result = ContentSnapshot(); result.feed(main[1])
    return {key: getattr(result, key) for key in ('words', 'languages', 'links', 'verses', 'media')}


class ReaderContract(HTMLParser):
    """Inspect final structure, without judging prose or simulating browser QA."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, doc):
        super().__init__(convert_charrefs=True)
        self.nodes = []; self.stack = []
        self.feed(doc); self.close()

    def handle_starttag(self, tag, attrs):
        node = dict(tag=tag, attrs=dict(attrs), parents=tuple(self.stack), text=[])
        self.nodes.append(node)
        if tag not in self.VOID: self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]['tag'] == tag:
                del self.stack[index:]; break

    def handle_data(self, data):
        for node in self.stack:
            if node['tag'] == 'th' or 'cell-label' in node['attrs'].get('class', '').split(): node['text'].append(data)

    def within(self, parent, tag=None):
        return [n for n in self.nodes if any(p is parent for p in n['parents']) and (tag is None or n['tag'] == tag)]


def _body_column_headings(parsed, table):
    """Resolve actual header columns, including grouped headers and spanned cells."""
    rows = parsed.within(table, 'tr')
    cells = lambda row: [n for n in parsed.within(row) if n['tag'] in ('td', 'th')]
    span = lambda cell, name: max(1, int(cell['attrs'].get(name, '1')))
    headers = []; header_rows = set(); active = {}
    for index, row in enumerate(rows):
        parts = cells(row)
        if not parts or not all(n['tag'] == 'th' and n['attrs'].get('scope', '').lower() != 'row' for n in parts):
            break
        header_rows.add(index)
        occupied = dict(active); active = {k: v - 1 for k, v in active.items() if v > 1}
        column = 0
        for cell in parts:
            while occupied.get(column, 0): column += 1
            label = ' '.join(''.join(cell['text']).split())
            for col in range(column, column + span(cell, 'colspan')):
                while len(headers) <= col: headers.append([])
                if label and label not in headers[col]: headers[col].append(label)
                if span(cell, 'rowspan') > 1: active[col] = span(cell, 'rowspan') - 1
            column += span(cell, 'colspan')
    expected = {}; active = {}
    for index, row in enumerate(rows):
        if index in header_rows: continue
        occupied = dict(active); active = {k: v - 1 for k, v in active.items() if v > 1}
        column = 0
        for cell in cells(row):
            while occupied.get(column, 0): column += 1
            labels = []
            for col in range(column, column + span(cell, 'colspan')):
                if col < len(headers): labels.extend(x for x in headers[col] if x not in labels)
                if span(cell, 'rowspan') > 1: active[col] = span(cell, 'rowspan') - 1
            expected[id(cell)] = ' · '.join(labels)
            column += span(cell, 'colspan')
    return expected


def audit(doc):
    """Block missing reader controls/labels even if a manual review says passed."""
    provenance=re.search(r'<script type="application/json" id="bnoc-provenance">(.*?)</script>',doc,re.S)
    if provenance:
        meta=json.loads(provenance[1])
        if meta.get('templateVersion') in ('bnoc-source-reader-1.0','bnoc-source-reader-1.1'):
            import source_reader
            if meta.get('profile') not in source_reader.PROFILES:raise ValueError('Unknown native reader profile')
            return source_reader.audit_html(doc)
    def require(condition, message):
        if not condition: raise ValueError('Reader contract: ' + message)

    parsed = ReaderContract(doc)
    by_id = lambda key: [n for n in parsed.nodes if n['attrs'].get('id') == key]
    has_class = lambda n, name: name in n['attrs'].get('class', '').split()
    tools = [n for n in parsed.nodes if n['tag'] == 'nav' and has_class(n, 'reading-tools')]
    require(len(tools) == 1, 'one persistent reading toolbar required')
    for key in ('search', 'summary', 'collapse', 'top'):
        nodes = by_id(key)
        require(len(nodes) == 1 and nodes[0]['tag'] == 'button' and any(p is tools[0] for p in nodes[0]['parents']), 'missing or duplicate toolbar button: ' + key)
    for key, tag in (('searchDialog', 'dialog'), ('query', 'input'), ('matches', 'div'), ('closeSearch', 'button')):
        nodes = by_id(key)
        require(len(nodes) == 1 and nodes[0]['tag'] == tag, 'missing or duplicate search element: ' + key)
        if key != 'searchDialog':
            require(any(p is by_id('searchDialog')[0] for p in nodes[0]['parents']), 'search element outside dialog: ' + key)
    scripture = by_id('scripture')
    require(len(scripture) == 1 and scripture[0]['tag'] == 'aside' and has_class(scripture[0], 'scripture'), 'Scripture must be an independent aside')
    require(not any(p['tag'] == 'details' for p in scripture[0]['parents']), 'Scripture cannot collapse')
    verses = [n for n in parsed.nodes if 'data-verse' in n['attrs']]
    require(bool(verses) and all(any(p is scripture[0] for p in n['parents']) for n in verses), 'all verses must remain inside the Scripture aside')
    cards = [n for n in parsed.nodes if has_class(n, 'study-card') or has_class(n, 'essay')]
    require(bool(cards), 'authored exposition missing')
    for card in cards:
        require(card['tag'] == 'details' and 'open' in card['attrs'], 'exposition must be individually collapsible and initially open')
        children = [n for n in parsed.within(card) if n['parents'][-1] is card]
        require(sum(n['tag'] == 'summary' for n in children) == 1, 'exposition needs one disclosure heading')
        for name in ('brief', 'prose'):
            require(sum(has_class(n, name) for n in children) == 1, 'missing authored ' + name)
    tables = [n for n in parsed.nodes if n['tag'] == 'table']
    for table in tables:
        require(has_class(table, 'reading-table') and table['attrs'].get('role') == 'table', 'table lacks mobile reading layout')
        require(not any(p['tag'] == 'table' for p in table['parents']), 'nested table needs individual layout')
        rows = parsed.within(table, 'tr')
        multiple = any(len([n for n in parsed.within(row) if n['tag'] in ('td', 'th')]) > 1 for row in rows)
        require(not multiple or bool(parsed.within(table, 'thead')), 'multicolumn table needs an explicit thead for print headers')
        labelled = bool(parsed.within(table, 'thead')) or multiple
        expected = _body_column_headings(parsed, table)
        for cell in parsed.within(table, 'td'):
            labels = [n for n in parsed.within(cell) if has_class(n, 'cell-label')]
            if labelled:
                require(bool(cell['attrs'].get('data-label')) and len(labels) == 1, 'table cell lacks its column heading')
                require(''.join(labels[0]['text']).strip() == cell['attrs']['data-label'] and labels[0]['attrs'].get('aria-hidden') == 'true', 'mobile column heading is inconsistent')
                require(bool(expected.get(id(cell))) and cell['attrs']['data-label'] == expected[id(cell)], 'mobile column heading differs from actual table header')
    return dict(cards=len(cards), tables=len(tables), verses=len(verses), readingTools=4)


def upgrade(doc):
    """Update only our known reader format; refuse any loss of authored content."""
    provenance = re.search(r'<script type="application/json" id="bnoc-provenance">(.*?)</script>', doc, re.S)
    if not provenance: raise ValueError('Not a BNOC generated reader')
    meta = json.loads(provenance[1])
    if meta.get('templateVersion') not in ('bnoc-reader-1.1', VERSION):
        raise ValueError('Unsupported reader version')
    before = content_snapshot(doc)
    css = '\n'.join((ROOT / 'automation' / name).read_text(encoding='utf-8') for name in ('reader.css', 'typography.css'))
    doc, n = re.subn(r'<style id="bnoc-reader-v1">.*?</style>', lambda _: '<style id="bnoc-reader-v1">' + css + '</style>', doc, flags=re.S)
    if n != 1: raise ValueError('Reader style binding missing')
    doc = re.sub(r'<article class="essay"([^>]*)><h3>(.*?)</h3>', r'<details class="study-card essay"\1 open><summary><h3>\2</h3></summary>', doc, flags=re.S)
    doc = doc.replace('</article>', '</details>')
    doc = re.sub(r'(<table\b.*?</table>)', lambda m: responsive_table(m[1]), doc, flags=re.S)
    doc = doc.replace('<aside class="scripture">', '<aside class="scripture" id="scripture">')
    header = '<div class="tools"><button id="theme" type="button">테마</button><button id="size" type="button">글자 18</button><button id="print" type="button">인쇄</button></div></header>'
    doc, n = re.subn(r'<div class="tools">.*?</div></header>', lambda _: header, doc, count=1, flags=re.S)
    if n != 1: raise ValueError('Reader header missing')
    doc = re.sub(r'<nav class="reading-tools".*?</nav>\s*', '', doc, flags=re.S)
    doc = doc.replace('aria-label="가로로 읽는 표"', 'aria-label="본문 설명 표"')
    doc, n = re.subn(r'<dialog id="searchDialog".*?</dialog>', lambda _: TOOLS + '\n' + DIALOG, doc, count=1, flags=re.S)
    if n != 1: raise ValueError('Reader search dialog missing')
    js = (ROOT / 'automation/reader.js').read_text(encoding='utf-8')
    doc, n = re.subn(r'<script>.*?</script>', lambda _: '<script>' + js + '</script>', doc, flags=re.S)
    if n != 1: raise ValueError('Unexpected reader executable scripts')
    meta['templateVersion'] = VERSION
    data = json.dumps(meta, ensure_ascii=False).replace('<', '\\u003c')
    doc = re.sub(r'(<script type="application/json" id="bnoc-provenance">).*?(</script>)', lambda m: m[1] + data + m[2], doc, flags=re.S)
    if content_snapshot(doc) != before: raise ValueError('Reader upgrade changed authored content')
    audit(doc)
    return doc, meta
