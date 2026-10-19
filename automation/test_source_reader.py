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
    def test_stale_editorial_anchor_is_rejected(self):
        data=sr.read(self.p/'source-exegesis-review.json');data['assessments']['orthodoxy']['anchors'][0]['quote']='없는 문장';self.save('source-exegesis-review.json',data)
        with self.assertRaisesRegex(ValueError,'anchor mismatch'):sr.validate(self.p,self.run)
    def test_visual_omission_is_rejected(self):
        data=sr.read(self.p/'source-visual-plan.json');data['items']=[];self.save('source-visual-plan.json',data)
        with self.assertRaisesRegex(ValueError,'visual inventory'):sr.validate(self.p,self.run)
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
