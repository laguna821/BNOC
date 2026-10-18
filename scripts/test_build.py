import unittest, json, re
from pathlib import Path
from xml.etree import ElementTree as ET
from urllib.parse import unquote
from build_site import ROOT, reader, date_for, Text

class PublishTests(unittest.TestCase):
    def test_routes(self):
        items=json.loads((ROOT/'_site/index.json').read_text(encoding='utf-8'))['items']
        self.assertGreaterEqual(len(items),58)
        self.assertEqual(items[0]['date'],max(x['date'] for x in items))
        self.assertEqual(len({x['link'] for x in items}),len(items))
        for x in items:self.assertTrue((ROOT/'_site'/unquote(x['link'].removeprefix('/BNOC/'))).is_file(),x['link'])
        self.assertFalse((ROOT/'_site/.git').exists())
        ET.parse(ROOT/'_site/feed.xml');ET.parse(ROOT/'_site/sitemap.xml')
    def test_legacy_date(self):
        self.assertEqual(date_for(Path('2025/10122005/a.html')),'2025-10-12')
    def test_document_title_excludes_svg_titles(self):
        p=Text();p.feed('<head><title>자료 제목</title></head><body><svg><title>그림 설명</title></svg></body>')
        self.assertEqual(''.join(p.t),'자료 제목')
    def test_reader_preservation(self):
        source='<html><head><title>새 자료</title></head><body><h1>말씀</h1><p lang="he">שָׁלוֹם</p><script>const a=1;</script></body></html>'
        self.assertEqual(reader(source,'2026-10-11'),source)
        styled=reader(source,'2026-10-25')
        self.assertIn('<script>const a=1;</script>',styled)
        self.assertIn('שָׁלוֹם',styled)
        self.assertIn('data:font/woff2;base64,',styled)
        self.assertEqual(reader(styled,'2026-10-25'),styled)
        optout=source.replace('<head>','<head><meta content="original" name="bnoc-style">')
        self.assertEqual(reader(optout,'2026-10-25'),optout)
    def test_today(self):
        p=ROOT/'_site/2026/10182026/luke_10_1_9_premium_guide.html'
        s=p.read_text(encoding='utf-8')
        self.assertIn('id="sametone-editorial"',s)
        self.assertIn('href="luke_10_1_9_premium_guide.html" download=',s)
        self.assertEqual(len(re.findall(r'<img\b',s)),4)

if __name__=='__main__':unittest.main()
