"""Adversarial integrity tests. Fixture reviews are not reviews of real manuscripts."""
import base64
import copy
import re
import tempfile
import unittest
from pathlib import Path
from bible import digest, save
import editorial
import render


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.passage = {'verified': True, 'reference': '테스트 본문', 'verses': []}
        self.passage['sha256'] = digest(self.passage)
        self.m = dict(title='테스트', date='2026-10-18', description='fixture', intro='fixture intro',
                      passageSha256=self.passage['sha256'], figures=[], practices=['fixture practice'],
                      sources=[{'id': key, 'title': key, 'url': 'https://example.test/' + key, 'usedFor': 'fixture'}
                               for key in ('source-one', 'source-two')],
                      sections=[{'id': 'first', 'title': '자유로운 구성', 'presentation': 'essay', 'cards': [
                          {'id': 'reading', 'title': '서술형 해설', 'summary': 'fixture summary',
                           'html': '<p>테스트의 짧은 본문입니다. <a href="#ref-source-one">출처</a></p>'}]}])
        self.review = dict(contentSha256=digest(editorial.content(self.m)), passageSha256=self.passage['sha256'],
                           model='test-fixture', reviewedAt='2026-10-18T07:00:00+00:00',
                           decision='ready-for-design', thesis='Fixture only; not theological approval.',
                           preservationDecision='New test fixture', blockingFindings=[], checkedSourceIds=['source-one', 'source-two'],
                           assessments={key: {'rationale': 'Fixture evidence', 'anchors': [
                               {'cardId': 'reading', 'quote': '테스트의 짧은 본문입니다.'}]} for key in editorial.AXES})
        self.plan = dict(contentSha256=self.review['contentSha256'], editorialReviewSha256=digest(self.review),
                         decidedAt='2026-10-18T07:01:00+00:00', mode='text-only', rationale='Fixture contains no visual claim', items=[])
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        save(self.root/'editorial-review.json', self.review)
        save(self.root/'visual-plan.json', self.plan)

    def diagram(self):
        data = b'<svg xmlns="http://www.w3.org/2000/svg"><text>Fixture</text></svg>'
        (self.root/'flow.svg').write_bytes(data)
        self.m['figures'] = [dict(id='flow', file='flow.svg', kind='diagram', alt='fixture', caption='fixture',
                                 sha256=digest(data), inspection={'sha256': digest(data), 'reviewedAt': '2026-10-18T07:02:00+00:00',
                                 'evidence': 'Fixture inspection'}, provenance={'basis': 'Fixture data'})]
        self.m['sections'][0]['cards'][0]['figure'] = 'flow'
        self.plan.update(mode='illustrated', items=[dict(id='flow', kind='diagram', at='reading', purpose='Fixture relationship')])
        self.save()

    def test_text_only_short_essay_is_not_rejected_by_length_or_layout(self):
        doc, meta = render.render(self.m, self.passage, self.root, 'fixture', 'fixture.html')
        self.assertLess(meta['metrics']['proseCharacters'], 3000)
        self.assertEqual(meta['metrics']['figures'], 0)
        self.assertIn('<article class="essay"', doc)
        self.assertNotIn('<details class="study-card"', doc)
        self.assertIn(self.m['sections'][0]['cards'][0]['html'], doc)

    def test_coverage_labels_cannot_replace_reading(self):
        (self.root/'editorial-review.json').unlink()
        self.m['coverage'] = list(editorial.AXES)
        with self.assertRaisesRegex(ValueError, 'review.*missing'):
            render.validate(self.m, self.passage, self.root)

    def test_text_or_source_change_invalidates_editorial_review(self):
        for update in ('prose', 'source', 'summary', 'practice', 'title'):
            with self.subTest(update=update):
                m = copy.deepcopy(self.m)
                if update == 'prose': m['sections'][0]['cards'][0]['html'] += '<p>변경</p>'
                elif update == 'source': m['sources'][0]['usedFor'] = 'changed'
                elif update == 'summary': m['sections'][0]['cards'][0]['summary'] = 'changed'
                elif update == 'practice': m['practices'][0] = 'changed'
                else: m['title'] = 'changed'
                with self.assertRaisesRegex(ValueError, 'Stale editorial'):
                    render.validate(m, self.passage, self.root)

    def test_unresolved_findings_block_layout(self):
        self.review['blockingFindings'] = ['Textual claim unresolved']
        self.save()
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            render.validate(self.m, self.passage, self.root)

    def test_fabricated_anchor_rejected(self):
        self.review['assessments']['orthodoxy']['anchors'][0]['quote'] = 'Absent from manuscript'
        self.save()
        with self.assertRaisesRegex(ValueError, 'does not match'):
            render.validate(self.m, self.passage, self.root)

    def test_layout_changes_do_not_invalidate_editorial_reading(self):
        self.m['sections'][0]['presentation'] = 'disclosure'
        self.m['scriptureCollapsible'] = True
        self.m['sections'][0]['cards'][0]['tableLayout'] = 'wide'
        render.validate(self.m, self.passage, self.root)

    def test_wide_table_preserves_words_and_print_width(self):
        card=self.m['sections'][0]['cards'][0]
        table='<table><tr><td>긴 설명을 줄이지 않습니다.</td></tr></table>'
        card['html']+=table
        self.review['contentSha256']=digest(editorial.content(self.m))
        self.plan['contentSha256']=self.review['contentSha256']
        self.plan['editorialReviewSha256']=digest(self.review)
        self.save()
        card['tableLayout']='wide'
        doc,_=render.render(self.m,self.passage,self.root,'fixture','fixture.html')
        self.assertIn('class="table-scroll wide-table"',doc)
        self.assertIn(table,doc)
        proof_rules=render.print_proof(doc).rsplit('<style>',1)[1].split('</style>',1)[0]
        self.assertIn('.wide-table table{min-width:0}',proof_rules)
        self.assertIn('table{font-size:10pt}',proof_rules)
        card['tableLayout']='arbitrary-css'
        with self.assertRaisesRegex(ValueError,'Unknown table layout'):
            render.validate(self.m,self.passage,self.root)

    def test_visual_decision_cannot_precede_review(self):
        self.plan['decidedAt'] = '2026-10-18T06:00:00+00:00'
        self.save()
        with self.assertRaisesRegex(ValueError, 'follow editorial'):
            render.validate(self.m, self.passage, self.root)

    def test_visual_plan_invalid_after_editorial_decision_changes(self):
        self.review['thesis'] = 'Different interpretation after rereading'
        self.save()
        with self.assertRaisesRegex(ValueError, 'predates'):
            render.validate(self.m, self.passage, self.root)

    def test_actual_diagram_is_embedded_and_hash_bound(self):
        self.diagram()
        doc, meta = render.render(self.m, self.passage, self.root, 'fixture', 'fixture.html')
        self.assertIn('<svg xmlns=', doc)
        self.assertEqual(meta['figureHashes']['flow'], self.m['figures'][0]['sha256'])
        (self.root/'flow.svg').write_bytes(b'<svg/>')
        with self.assertRaisesRegex(ValueError, 'changed after inspection'):
            render.validate(self.m, self.passage, self.root)

    def test_unused_or_silently_omitted_figure_rejected(self):
        self.diagram()
        del self.m['sections'][0]['cards'][0]['figure']
        with self.assertRaisesRegex(ValueError, 'Planned, supplied'):
            render.validate(self.m, self.passage, self.root)
        self.m['figures'] = []
        with self.assertRaisesRegex(ValueError, 'Planned, supplied'):
            render.validate(self.m, self.passage, self.root)

    def test_diagram_cannot_masquerade_as_generated_image(self):
        self.diagram()
        self.m['figures'][0]['kind'] = self.plan['items'][0]['kind'] = 'generated-illustration'
        self.save()
        with self.assertRaisesRegex(ValueError, 'actual raster'):
            render.validate(self.m, self.passage, self.root)

    def test_wrong_placement_is_not_silently_accepted(self):
        self.diagram()
        self.plan['items'][0]['at'] = 'hero'
        self.save()
        with self.assertRaisesRegex(ValueError, 'placement'):
            render.validate(self.m, self.passage, self.root)

    def test_figure_can_follow_explanation_without_rewriting_it(self):
        self.diagram()
        self.m['sections'][0]['cards'][0]['figurePosition']='after'
        with self.assertRaisesRegex(ValueError,'before/after'):
            render.validate(self.m,self.passage,self.root)
        self.plan['items'][0]['position']='after'
        self.save()
        doc,_=render.render(self.m,self.passage,self.root,'fixture','fixture.html')
        self.assertLess(doc.index('테스트의 짧은 본문입니다.'),doc.index('<figure'))

    def test_inline_diagram_is_inert_and_uses_embedded_font(self):
        for source in ('<svg><script>bad</script></svg>','<svg><text onclick="bad">text</text></svg>',
                       '<svg><text style="fill:url(https://bad)">text</text></svg>'):
            with self.assertRaises(ValueError):render.diagram_svg(source,'flow')
        safe=render.diagram_svg('<svg><title id="title">Diagram</title><text font-family="Fallback">text</text></svg>','flow')
        self.assertIn('id="flow-title"',safe)
        self.assertIn('font-family="var(--sans)"',safe)


class FontRegressionTests(unittest.TestCase):
    def test_same_font_binaries_and_variable_declarations_as_approved_week(self):
        root = Path(__file__).resolve().parents[1]
        def fonts(path):
            rows = []
            for block in re.findall(r'@font-face\s*\{([^}]+)\}', path.read_text(encoding='utf-8')):
                match = re.search(r'base64,([A-Za-z0-9+/=]+)', block)
                if match:
                    rows.append((re.search(r'font-family\s*:\s*([^;]+)', block)[1],
                                 re.search(r'font-weight\s*:\s*([^;]+)', block)[1],
                                 digest(base64.b64decode(match[1]))))
            return rows
        actual = fonts(root/'web/reader-fonts.css')
        self.assertEqual(len(actual), 5)
        self.assertEqual(actual, fonts(root/'2026/10182026/luke_10_1_9_premium_guide.html'))
        self.assertTrue(all(weight == '100 900' for _, weight, _ in actual))
        self.assertEqual(actual[0][2], '5e0c4af59d8a71a38dc4438d5fbeb15c30cca3b8db1e101a1469850f8a5b4f33')


if __name__ == '__main__':
    unittest.main()
