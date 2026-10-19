import copy
import json
import tempfile
import unittest
import subprocess
import bnoc
from pathlib import Path
from bible import digest
import source_reader as sr
import reader_layout

CARD='<details class="study-card" id="guide" open><summary>깊은 해설</summary><div class="brief">요약</div><div class="prose"><p>본문의 경고와 약속을 함께 읽는다.</p><details class="subdetails"><summary>문법</summary><p>분사 설명</p></details><p>끝까지 보존할 문단</p></div></details>'
SVG='<svg viewBox="0 0 20 20"><title>원고의 그림</title><path d="M0 0L20 20"/></svg>'
SOURCE='''<!doctype html><html><head><title>개별 원고</title></head><body>
<a class="brand" href="#top"><span class="brand-symbol"><svg viewBox="0 0 20 20"><path d="M0 0"/></svg></span></a>
<details id="scripture" class="scripture-panel" open><summary><span>본문</span></summary><div class="scripture-text"><p><span class="verse-no">1</span>정확한 성경 본문</p></div></details>'''+CARD+SVG+'''
<nav class="bottom-tools"><button data-open-toc>찾기</button><button id="summaryBtn">요약</button><button id="collapseBtn">접기</button><button id="topBtn">위</button></nav>
<dialog id="tocDialog"><input id="tocSearch"><button id="closeToc">닫기</button></dialog><button id="fontBtn">글자</button><button id="themeBtn">테마</button>
<textarea data-note="reality"></textarea><textarea data-note="strengthen"></textarea><textarea data-note="action"></textarea>
<p>화면 글꼴은 기기의 기본 글꼴을 사용하므로 기기에 따라 조금 다르게 보일 수 있습니다.</p>
<script>const fontSizes=[17,19,21];const PREFIX='unchanged_native_';function test(a,target){if(a.classList.contains('dialog-link'))setSummary(false);reveal(target);}dialog.addEventListener('cancel',()=>{if(lastFocus&&lastFocus.focus)lastFocus.focus()});</script></body></html>'''

class NativePreservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)
        self.passage=dict(reference='계3:1',verified=True,verses=[dict(verse='1',text='정확한 성경 본문')])
        self.passage['sha256']=digest(self.passage)
        sha=digest(SOURCE.encode())
        self.run=dict(id='native-test',date='2026-09-13',relativePath='native.html',revision=dict(originalSha256=sha,originalCommit='a'*40,revisedAt='2026-10-19T09:00:00+00:00',kinds=['design','theology'],intent='본문과 기록 보존'))
        review=dict(originalSha256=sha,passageSha256=self.passage['sha256'],decision='ready-for-design',blockingFindings=[],model='test',thesis='문맥 안에서 읽기',preservationDecision='전체 원고 보존',researchRefs=['research:test:revision'],reviewedAt='2026-10-19T09:00:00+00:00',
                    assessments={axis:dict(rationale='실제 원고의 문맥을 확인',anchors=[dict(cardId='guide',quote='본문의 경고와 약속을 함께 읽는다.')]) for axis in sr.editorial.AXES},
                    checkedSources=[dict(id='a',url='https://example.org/one',scope='원전'),dict(id='b',url='https://example.org/two',scope='독립 대조')])
        plan=dict(profile=sr.PROFILE,originalSha256=sha,passageSha256=self.passage['sha256'],sourceSnapshot=sr.snapshot(SOURCE))
        visual=dict(originalSha256=sha,editorialReviewSha256=digest(review),decidedAt='2026-10-19T09:01:00+00:00',rationale='기존 의미 그림 유지',items=[dict(sha256=digest(SVG),decision='retain',purpose='내용 설명',captionScope='창작',inspectedAt='2026-10-19',inspectionEvidence='실제 그림 확인')])
        (self.p/'original.html').write_bytes(SOURCE.encode())
        for name,data in [('passage.json',self.passage),('source-reader-plan.json',plan),('source-exegesis-review.json',review),('source-visual-plan.json',visual)]:self.save(name,data)
    def tearDown(self):self.tmp.cleanup()
    def save(self,name,data):(self.p/name).write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    def test_nested_grammar_and_following_paragraph_are_exact(self):
        self.assertEqual(sr.cards(SOURCE),{'guide':CARD})
    def test_anonymous_cards_keep_html_and_order_without_invented_dom_ids(self):
        a=CARD.replace(' id="guide"','');b=a.replace('깊은 해설','둘째 해설')
        self.assertEqual(sr.cards(a+b),{'@ordinal:01':a,'@ordinal:02':b})
        edit=dict(originalSha256='test',rationale='둘째 표의 실제 모바일 라벨만 보완',cards=[dict(cardId='@ordinal:02',beforeSha256=digest(b),afterHtml=b.replace('끝까지 보존할 문단','끝까지 보존할 문단과 추가 설명'),rationale='개별 검토')])
        doc=sr.apply_content_edits(a+b,edit)
        self.assertEqual(sr.cards(doc)['@ordinal:01'],a)
        self.assertNotIn('id="@ordinal:',doc)
    def test_existing_fonts_are_reused_only_after_exact_asset_byte_comparison(self):
        from source_reader_luke101 import verify_existing_fonts
        baseline="@font-face{font-family:Test;src:url(data:font/woff2;base64,YWJj)}"
        source='<style id="embedded-fonts">'+baseline+'</style>'
        verify_existing_fonts(source,baseline)
        with self.assertRaisesRegex(ValueError,'byte comparison'):verify_existing_fonts(source.replace('YWJj','ZGVm'),baseline)
    def test_render_preserves_authored_cards_keys_and_native_note_fields(self):
        doc,meta=sr.render(self.p,self.run)
        self.assertEqual(sr.cards(doc),sr.cards(SOURCE))
        self.assertIn("PREFIX='unchanged_native_'",doc)
        self.assertIn('const fontSizes=[18,20,22]',doc)
        self.assertIn("target.querySelectorAll('details').forEach(d=>d.open=true)",doc)
        self.assertIn("e.key==='Escape'",doc)
        self.assertIn(SVG,doc);self.assertEqual(meta['metrics']['verses'],1)
        self.assertIn('download="native.html"',doc)
        self.assertIn('원어용 글꼴을 이 파일에 내장했습니다.',doc)
        self.assertEqual(reader_layout.audit(doc)['cards'],1)
    def test_original_tamper_requires_new_reading(self):
        (self.p/'original.html').write_text(SOURCE.replace('깊은 해설','바뀐 글'),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'binding'):sr.validate(self.p,self.run)
    def test_content_revision_requires_exact_baseline_and_preserves_identity(self):
        after=CARD.replace('끝까지 보존할 문단','끝까지 보존할 문단과 개별 보강')
        edit=dict(originalSha256=digest(SOURCE.encode()),rationale='수동 보강',cards=[dict(cardId='guide',beforeSha256=digest(CARD),afterHtml=after,rationale='보강')])
        result=sr.apply_content_edits(SOURCE,edit)
        self.assertEqual(sr.cards(result)['guide'],after)
        edit['cards'][0]['beforeSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'baseline changed'):sr.apply_content_edits(SOURCE,edit)
    def test_native_content_cannot_change_heading_or_add_executable_code(self):
        for after,message in [(CARD.replace('깊은 해설','다른 제목'),'preserve heading'),(CARD.replace('끝까지 보존할 문단','<script>alert(1)</script>'),'executable')]:
            edit=dict(originalSha256=digest(SOURCE.encode()),rationale='보강',cards=[dict(cardId='guide',beforeSha256=digest(CARD),afterHtml=after,rationale='보강')])
            with self.assertRaisesRegex(ValueError,message):sr.apply_content_edits(SOURCE,edit)
    def test_unbound_native_content_file_is_rejected(self):
        self.save('source-content-edits.json',{})
        with self.assertRaisesRegex(ValueError,'explicit source-plan'):sr.validate(self.p,self.run)
    def test_bound_revision_needs_post_edit_editorial_reading(self):
        edit=dict(originalSha256=digest(SOURCE.encode()),rationale='보강',cards=[dict(cardId='guide',beforeSha256=digest(CARD),afterHtml=CARD.replace('끝까지 보존할 문단','새로 보강한 문단'),rationale='보강')])
        self.save('source-content-edits.json',edit)
        plan=sr.read(self.p/'source-reader-plan.json');plan.update(contentEditsSha256=digest(edit),reviewedSnapshot=sr.snapshot(sr.apply_content_edits(SOURCE,edit)),revisionDescription='직접 검토한 해설과 표의 열 제목을 보완했습니다.');self.save('source-reader-plan.json',plan)
        with self.assertRaisesRegex(ValueError,'edited-content review'):sr.validate(self.p,self.run)
        review=sr.read(self.p/'source-exegesis-review.json');review['reviewedContentSha256']=digest(plan['reviewedSnapshot']['cards']);self.save('source-exegesis-review.json',review)
        visual=sr.read(self.p/'source-visual-plan.json');visual['editorialReviewSha256']=digest(review);self.save('source-visual-plan.json',visual)
        doc,meta=sr.render(self.p,self.run)
        self.assertIn('새로 보강한 문단',doc);self.assertEqual(meta['contentSha256'],review['reviewedContentSha256'])
        self.assertIn(plan['revisionDescription'],doc)
    def test_ezekiel_wrapped_verse_and_existing_large_font_controls(self):
        src=SOURCE.replace('<p><span class="verse-no">1</span>정확한 성경 본문</p>','<p id="verse-1"><span class="verse-no">1</span><span class="verse-content">정확한 성경 본문</span></p>').replace('const fontSizes=[17,19,21]','const fontSizes=[18,20,22]').replace('화면 글꼴은 기기의 기본 글꼴을 사용하므로 기기에 따라 조금 다르게 보일 수 있습니다.','이미지와 글은 오프라인으로 읽을 수 있습니다. 외부 자료 링크는 인터넷 연결이 필요합니다.')
        src=src.replace('</body>','8개 장 · 43개 해설 카드 · 20개 자료 · 묵상 기록</body>')
        changes=sr.structural_changes(src,self.passage,'ezekiel-native-v1')
        for before,after in changes:src=src.replace(before,after,1)
        self.assertIn('<aside id="scripture"',src);self.assertIn('원전 대조 자료',src);self.assertIn('원어용 글꼴도',src)
    def test_stale_editorial_anchor_is_rejected(self):
        data=sr.read(self.p/'source-exegesis-review.json');data['assessments']['orthodoxy']['anchors'][0]['quote']='없는 문장';self.save('source-exegesis-review.json',data)
        with self.assertRaisesRegex(ValueError,'anchor mismatch'):sr.validate(self.p,self.run)
    def luke_annotated_source(self):
        note=' <sup><a href="#manuscripts" title="제공된 각주 번호와 사본 차이의 설명">2)</a></sup>'
        src=SOURCE.replace('<p><span class="verse-no">1</span>정확한 성경 본문</p>','<p id="verse-55"><span class="verse-no">55</span><span class="verse-content">정확한 성경 본문</span>'+note+'</p>')
        src=src.replace('const fontSizes=[17,19,21]','const fontSizes=[18,20,22]').replace('화면 글꼴은 기기의 기본 글꼴을 사용하므로 기기에 따라 조금 다르게 보일 수 있습니다.','글과 그림은 오프라인으로 읽을 수 있습니다. 출처 링크를 여는 데에는 인터넷 연결이 필요합니다.')
        passage=copy.deepcopy(self.passage);passage['verses'][0]['verse']='55'
        return src,passage,note
    def test_luke_keeps_known_annotation_separate_from_verified_bible(self):
        src,passage,note=self.luke_annotated_source()
        for before,after in sr.structural_changes(src,passage,'luke-9-51-native-v1'):src=src.replace(before,after,1)
        self.assertIn(note,src);self.assertIn('<aside id="scripture"',src)
        self.assertEqual(sr.cards(src),{'guide':CARD})
    def test_unknown_scripture_note_cannot_hide_bible_tampering(self):
        src,passage,note=self.luke_annotated_source()
        for bad in [src.replace('>2)</a>','>3)</a>'),src.replace('</span>'+note,'</span>추가 성경 문장'+note)]:
            with self.assertRaisesRegex(ValueError,'annotation'):sr.structural_changes(bad,passage,'luke-9-51-native-v1')
    def test_visual_omission_is_rejected(self):
        data=sr.read(self.p/'source-visual-plan.json');data['items']=[];self.save('source-visual-plan.json',data)
        with self.assertRaisesRegex(ValueError,'visual inventory'):sr.validate(self.p,self.run)
    def test_css_composition_binds_its_markup_and_actual_styles(self):
        figure='<figure><div role="img" aria-label="고랑을 나타낸 도안">방향</div><figcaption>추상 표현</figcaption></figure>'
        doc='<style>.poster{color:blue}</style>'+figure
        inventory=sr.meaningful_visuals(doc)
        self.assertEqual([v['kind'] for v in inventory.values()],['css-composition'])
        self.assertNotEqual(inventory,sr.meaningful_visuals(doc.replace('blue','red')))
        self.assertNotEqual(inventory,sr.meaningful_visuals(doc.replace('방향','다른 방향')))
    def test_text_only_needs_an_individual_editorial_visual_rationale(self):
        src=SOURCE.replace(SVG,'');sha=digest(src.encode())
        (self.p/'original.html').write_bytes(src.encode());self.run['revision']['originalSha256']=sha
        plan=sr.read(self.p/'source-reader-plan.json');plan.update(originalSha256=sha,sourceSnapshot=sr.snapshot(src));self.save('source-reader-plan.json',plan)
        review=sr.read(self.p/'source-exegesis-review.json');review['originalSha256']=sha;self.save('source-exegesis-review.json',review)
        visual=sr.read(self.p/'source-visual-plan.json');visual.update(originalSha256=sha,editorialReviewSha256=digest(review),items=[]);self.save('source-visual-plan.json',visual)
        with self.assertRaisesRegex(ValueError,'visual inventory'):sr.validate(self.p,self.run)
        visual['textOnlyRationale']='이 본문은 서술과 대화의 대조로 충분하며 별도 장면을 그리면 알려지지 않은 결말을 사실화할 수 있다.';self.save('source-visual-plan.json',visual)
        sr.validate(self.p,self.run)
    def test_scripture_cannot_be_collapsible_even_with_provenance(self):
        doc,_=sr.render(self.p,self.run)
        doc=doc.replace('<aside id="scripture" class="scripture-panel">','<details id="scripture" class="scripture-panel">')
        with self.assertRaisesRegex(ValueError,'independent aside'):reader_layout.audit(doc)
    def test_mobile_table_heading_must_match_real_column(self):
        doc,_=sr.render(self.p,self.run)
        table='<table class="lex-table"><thead><tr><th>원어</th><th>의미</th></tr></thead><tbody><tr><td data-label="틀린 열">λόγος</td><td data-label="의미">말씀</td></tr></tbody></table>'
        with self.assertRaisesRegex(ValueError,'heading mismatch'):sr.audit_html(doc.replace('</body>',table+'</body>'))
    def test_bible_replacement_is_not_a_design_change(self):
        source=SOURCE.replace('정확한 성경 본문','다른 성경 본문')
        with self.assertRaisesRegex(ValueError,'differs'):sr.structural_changes(source,self.passage)
    def test_native_audit_is_consumed_by_real_publisher_and_manifest(self):
        repo=self.p/'repo';repo.mkdir();remote=self.p/'remote.git'
        subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
        subprocess.run(['git','init',str(repo)],check=True,capture_output=True)
        def git(*args,input=None):return bnoc.git(repo,*args,input=input)
        git('remote','add','origin',str(remote))
        target='2026/09132026/native.html'
        for name,data in [(target,SOURCE.encode()),('untouched.html',b'keep')]:
            blob=git('hash-object','-w','--stdin',input=data)
            git('update-index','--add','--cacheinfo','100644',blob,name)
        tree=git('write-tree')
        base=git('-c','user.name=Test','-c','user.email=test@example.test','commit-tree',tree,input=b'baseline')
        git('push','origin',base+':refs/heads/main')
        run=copy.deepcopy(self.run)
        run.update(relativePath=target,reference='계3:1',service='fixture',mode='publish',stage='validated',versions={'template':sr.VERSION})
        run['revision']['originalCommit']=base
        doc,meta=sr.render(self.p,run);(self.p/'native.html').write_bytes(doc.encode())
        report=dict(**meta,model='test-fixture',reviewedAt='2026-10-19T10:00:00+00:00',preservedIntent=run['revision']['intent'],blockingFindings=[],
                    checkedSourceIds=['a','b'],checks={key:dict(passed=True,evidence='Fixture only') for key in sr.REVIEW_KEYS})
        self.save('review.json',report)
        cfg=dict(root=self.p/'state',repo=repo,site='https://example.test/',gitAuthor=dict(name='Test',email='test@example.test'))
        cfg['root'].mkdir()
        bnoc.save(cfg['root']/'state.json',dict(schemaVersion=1,issues={run['id']:dict(stage='validated')},observations={},failures={}))
        result=bnoc.publish(cfg,self.p,run)
        self.assertEqual(result['status'],'pushed-awaiting-deployment')
        git('fetch','origin','main')
        manifest=json.loads(git('show','origin/main:issues/'+run['id']+'.json'))
        self.assertEqual(manifest['date'],run['date'])
        self.assertEqual(manifest['htmlSha256'],digest(doc.encode()))
        self.assertEqual(git('show','origin/main:untouched.html'),'keep')

if __name__=='__main__':unittest.main()
