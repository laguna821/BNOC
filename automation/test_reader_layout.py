"""Regression cases for mobile table meaning and reader-only migrations."""
import json
import unittest
import reader_layout as layout


class ReaderLayoutTests(unittest.TestCase):
    def fixture(self, prose):
        meta = json.dumps({'templateVersion': 'bnoc-reader-1.1', 'manuscriptSha256': 'unchanged'})
        return '<html><head><style id="bnoc-reader-v1">old</style></head><body><header><div class="tools">old</div></header><main><aside class="scripture"><h2>본문</h2><p data-verse="행14:22">성경은 항상 보입니다.</p></aside><article class="essay" id="essay-one"><h3>원래 제목</h3><div class="brief">원래 요약</div><div class="prose">'+prose+'</div></article></main><dialog id="searchDialog"></dialog><script>old()</script><script type="application/json" id="bnoc-provenance">'+meta+'</script></body></html>'

    def test_greek_hebrew_labels_and_citations_survive_without_text_rewrite(self):
        source = self.fixture('<p>긴 해설을 생략하지 않습니다.</p><table><thead><tr><th>원어</th><th>본문의 역할 &amp; 용례</th></tr></thead><tbody><tr><th scope="row"><span lang="he" dir="rtl">חֶסֶד</span></th><td><span lang="grc">ἀγάπη</span>와 단순 등치하지 않음. <a href="#ref-one">자료</a></td></tr></tbody></table><figure><img src="data:image/webp;base64,AA==" alt="실제 삽화"><figcaption>창작 캡션</figcaption></figure>')
        doc, meta = layout.upgrade(source)
        self.assertEqual(layout.content_snapshot(source), layout.content_snapshot(doc))
        self.assertIn('data-label="본문의 역할 &amp; 용례"', doc)
        self.assertIn('class="cell-label" aria-hidden="true">본문의 역할 &amp; 용례</span>', doc)
        self.assertEqual(meta['manuscriptSha256'], 'unchanged')
        self.assertIn('<aside class="scripture" id="scripture">', doc)
        self.assertIn('<details class="study-card essay" id="essay-one" open>', doc)
        self.assertIn('id="collapse"', doc)

    def test_idempotent_upgrade_does_not_duplicate_labels_or_tools(self):
        source = self.fixture('<table><thead><tr><th>말씀</th><th>해설</th></tr></thead><tbody><tr><th scope="row">한 단어</th><td>충분한 내용</td></tr></tbody></table>')
        first, _ = layout.upgrade(source)
        second, _ = layout.upgrade(first)
        self.assertEqual(first, second)
        self.assertEqual(second.count('id="summary"'), 1)
        self.assertEqual(second.count('id="search"'), 1)

    def test_colspan_and_rowspan_keep_the_correct_column_meanings(self):
        table = '<table><thead><tr><th>개념</th><th>MT</th><th>LXX</th><th>NT</th></tr></thead><tbody><tr><th scope="row" rowspan="2">연결</th><td colspan="2">두 전승 비교</td><td>신약 문맥</td></tr><tr><td>히브리어</td><td>그리스어</td><td>해석</td></tr></tbody></table>'
        result = layout.responsive_table(table)
        self.assertIn('data-label="MT · LXX"', result)
        self.assertIn('data-label="MT"><span class="cell-label" aria-hidden="true">MT</span>히브리어', result)
        self.assertIn('data-label="LXX"><span class="cell-label" aria-hidden="true">LXX</span>그리스어', result)
        self.assertIn('data-label="NT"><span class="cell-label" aria-hidden="true">NT</span>해석', result)

    def test_missing_header_does_not_invent_an_interpretation(self):
        result = layout.responsive_table('<table><tr><td>단독 설명</td></tr></table>')
        self.assertIn('단독 설명', result)
        self.assertNotIn('data-label=', result)

    def test_unknown_html_is_refused_before_a_bulk_update(self):
        with self.assertRaisesRegex(ValueError, 'Not a BNOC'):
            layout.upgrade('<main>다른 문서</main>')


if __name__ == '__main__': unittest.main()
