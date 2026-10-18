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
    for index, row in enumerate(rows):
        parts = cells(row[1])
        if parts and all(c[1].lower() == 'th' and not re.search(r'\bscope=["\']?row', c[2]) for c in parts):
            column = 0
            header_rows.add(index)
            for cell in parts:
                label = plain(cell[3]).strip()
                for offset in range(_span(cell[2], 'colspan')):
                    while len(headers) <= column + offset:
                        headers.append([])
                    if label and label not in headers[column + offset]:
                        headers[column + offset].append(label)
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
    return doc, meta
