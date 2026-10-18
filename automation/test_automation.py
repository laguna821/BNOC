import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
from bible import Bible, plain, digest, save, official_units
import bulletin
import bnoc
import render

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        data={'마1:1':'A','마1:2':'B','마2:1':'C','마2:2':'D','신6:18-19':'E','눅10:1':'F','요18:이':'invalid','행24:6':'G','행24:8':'H'}
        save(self.root/'bible.json',data);self.b=Bible(self.root/'bible.json',self.root/'cache')
        self.c={'root':self.root/'state','bible':str(self.root/'bible.json')}
    def tearDown(self):self.temp.cleanup()
    def test_ranges_aliases_and_bounds(self):
        self.assertEqual(self.b.parse('마태복음 1장 1–2절; 마 2:1'),[('마',1,1),('마',1,2),('마',2,1)])
        self.assertEqual(self.b.parse('마1:2-2:1'),[('마',1,2),('마',2,1)])
        for s in ('마1:2-1','마1:0','마1:999','마999:1','1:1'):
            with self.assertRaises(ValueError):self.b.parse(s)
    def test_combined_verses_never_duplicated_or_split(self):
        official={'url':'https://example.test','retrievedAt':'today','htmlSha256':'x','units':{'18-19':'E'}}
        with patch.object(self.b,'official',return_value=official):
            p=self.b.extract('신6:18-19');self.assertEqual(len(p['verses']),1);self.assertEqual(p['verses'][0]['verse'],'18-19')
            with self.assertRaises(ValueError):self.b.extract('신6:18')
    def test_omission_and_invalid_key(self):
        self.assertEqual(self.b.audit()['invalidKeys'],['요18:이'])
        official={'url':'https://example.test','retrievedAt':'today','htmlSha256':'x','units':{'7':'(없음)'}}
        with patch.object(self.b,'official',return_value=official):
            p=self.b.extract('행24:7');self.assertTrue(p['verses'][0]['omitted'])
    def test_footnotes_do_not_enter_scripture(self):
        self.assertEqual(plain('만일 <a class="comment">1)</a>평안<div class="D2">설명</div> 이 있다'), '만일 평안 이 있다')
    def test_internal_line_break_does_not_truncate_verse(self):
        html='<span><span class="number">6&nbsp;</span>이새는 다윗 왕을 낳으니라 <br />다윗은 솔로몬을 낳고 </span><br><font class="smallTitle">다음 제목</font><span><span class="number">7&nbsp;</span>솔로몬은</span><footer>메뉴</footer>'
        self.assertEqual(official_units(html),{'6':'이새는 다윗 왕을 낳으니라 다윗은 솔로몬을 낳고','7':'솔로몬은'})
    def test_official_page_identity(self):
        html='<div class="titleBg">[마태복음 1:1]</div><b>개역개정</b><font class="chapNum">제 1 장</font><span><span class="number">1&nbsp;</span>A</span>'
        with patch('bible.fetch',return_value=html.encode()):
            self.assertEqual(self.b.official('마',1)['units'],{'1':'A'})
            with self.assertRaisesRegex(ValueError,'chapter'):self.b.official('마',2)
            with self.assertRaisesRegex(ValueError,'book'):self.b.official('신',1)
    def test_discovery_and_schedule(self):
        html='<a href="/main/sub.html?boardID=www199&num=1&Mode=view">2026년 10월 18일 주보</a>'
        self.assertEqual(bulletin.parse_list(html)[0]['date'],'2026-10-18')
        self.assertTrue(bulletin.due(dt.datetime(2026,10,16,6,tzinfo=bulletin.KST)))
        self.assertFalse(bulletin.due(dt.datetime(2026,10,18,10,tzinfo=bulletin.KST)))
    def test_observation_fails_on_conflicting_service(self):
        candidate={'date':'2026-10-18','images':['https://img']}
        obs=dict(date='2026-10-18',service='sunday-morning-adult',passage='눅10:1',unambiguous=True,visuallyConfirmed=True,evidence='first page',imageUrl='https://img',morningPassages=['눅10:1','마1:1'])
        with self.assertRaises(ValueError):bulletin.validate_observation(candidate,obs)
    def test_duplicate_draft_resumes(self):
        a=bnoc.make_run(self.c,'마1:1','2026-10-18','manual','draft')
        b=bnoc.make_run(self.c,'마태복음 1:1','2026-10-18','manual','draft')
        self.assertEqual(a['runId'],b['runId']);self.assertEqual(b['status'],'resume')
    def test_published_issue_not_overwritten(self):
        selected=self.b.parse('눅10:1');key=bnoc.identity('2026-10-18','sunday-morning-adult',selected)
        save(self.c['root']/'state.json',{'issues':{key:{'stage':'published','url':'https://example.test'}}})
        r=bnoc.make_run(self.c,'누가복음 10:1','2026-10-18','sunday-morning-adult','publish')
        self.assertEqual(r['status'],'already-published')
    def test_untrusted_prose_rejected(self):
        for s in ('<script>alert(1)</script>','<p onclick="x">x</p>','<a href="javascript:x">x</a>','<p>x'):
            with self.assertRaises(ValueError):render.fragment(s)
        self.assertIn('שָׁלוֹם',render.fragment('<p><span lang="he" dir="rtl">שָׁלוֹם</span></p>'))
    def test_wrong_lease_rejected(self):
        a=bnoc.make_run(self.c,'마1:1','2026-10-18','manual','draft')
        with self.assertRaises(ValueError):bnoc.owned(self.c,a['runId'],'unknown')
    def test_review_must_match_artifact(self):
        a=bnoc.make_run(self.c,'마1:1','2026-10-18','manual','draft')
        path=Path(a['path']);run=json.loads((path/'run.json').read_text(encoding='utf-8'))
        save(path/'manuscript.json',{});save(path/'passage.json',{'sha256':'fresh'})
        save(path/'review.json',{'manuscriptSha256':'stale'});(path/Path(run['relativePath']).name).write_text('html')
        with self.assertRaisesRegex(ValueError,'Stale review'):bnoc.audit_review(path,run)
    def test_tampered_passage_rejected(self):
        p={'verified':True,'verses':[]};p['sha256']=digest(p);p['verses'].append({'text':'changed'})
        with self.assertRaisesRegex(ValueError,'integrity'):render.validate({'passageSha256':p['sha256']},p,self.root)
    def test_publication_preserves_remote_tree_and_is_idempotent(self):
        # A real local bare Git remote verifies tree assembly without publishing a test page.
        remote=self.root/'remote.git';repo=self.root/'checkout';repo.mkdir()
        subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
        subprocess.run(['git','init',str(repo)],check=True,capture_output=True)
        def g(*args,input=None):return bnoc.git(repo,*args,input=input)
        g('remote','add','origin',str(remote))
        blob=g('hash-object','-w','--stdin',input=b'historical content')
        g('update-index','--add','--cacheinfo','100644',blob,'historical.html.')
        tree=g('write-tree')
        base=g('-c','user.name=Test','-c','user.email=test@example.test','commit-tree',tree,input=b'Baseline')
        g('push','origin',base+':refs/heads/main')
        self.c.update(repo=repo,site='https://example.test/',gitAuthor={'name':'Test','email':'test@example.test'})
        a=bnoc.make_run(self.c,'마1:1','2026-10-18','manual','publish')
        path=Path(a['path']);run=bnoc.load(path/'run.json')
        output=path/Path(run['relativePath']).name;output.write_bytes(b'<html>Test fixture</html>')
        save(path/'review.json',{'model':'unit-test-fixture'})
        binding={'htmlSha256':digest(output.read_bytes()),'manuscriptSha256':'fixture','passageSha256':'fixture'}
        with patch('bnoc.audit_review',return_value=binding):
            first=bnoc.publish(self.c,path,run)
            self.assertEqual(first['status'],'pushed-awaiting-deployment')
            g('fetch','origin','main')
            self.assertEqual(g('show','origin/main:historical.html.'),'historical content')
            self.assertEqual(g('show','origin/main:'+run['relativePath']),'<html>Test fixture</html>')
            before=g('rev-parse','origin/main');again=bnoc.publish(self.c,path,run)
            self.assertEqual(again['status'],'already-pushed');self.assertEqual(g('rev-parse','origin/main'),before)
        with patch('bnoc.audit_review',return_value=dict(binding,htmlSha256='changed')):
            with self.assertRaisesRegex(ValueError,'explicit revision'):bnoc.publish(self.c,path,run)
        run['mode']='draft'
        with self.assertRaisesRegex(ValueError,'Draft'):bnoc.publish(self.c,path,run)

    def test_deployment_rejects_stale_archive_at_the_same_url(self):
        a=bnoc.make_run(self.c,'마1:1','2026-10-18','manual','publish')
        save(self.root/'config.json',dict(stateRoot=str(self.c['root']),repository=str(self.root/'repository'),bible=self.c['bible']))
        claimed=subprocess.run([sys.executable,'-X','utf8',bnoc.__file__,'--config',str(self.root/'config.json'),'claim',a['runId'],'--owner','unit-test'],capture_output=True)
        self.assertEqual(claimed.returncode,0,claimed.stderr.decode('utf-8'))
        path=Path(a['path']);run=bnoc.load(path/'run.json');run['commit']='new-commit'
        self.c['site']='https://example.test/'
        doc='<title>New &amp; thoughtful</title><meta name="description" content="New description"><meta name="bnoc-revised" content="2026-10-18T12:00:00Z"><meta name="bnoc-revision-kinds" content="theology,expansion"><style>private-font-code</style><script>private-script</script><p>New prose with substance.</p>'
        (path/Path(run['relativePath']).name).write_text(doc,encoding='utf-8')
        item=dict(link='/BNOC/'+run['relativePath'],title='New & thoughtful',description='New description',revisedAt='2026-10-18T12:00:00Z',revisionKinds=['theology','expansion'])
        search=dict(item,search='prefix New & thoughtful New prose with substance. suffix')
        workflow={'workflow_runs':[dict(name='BNOC Pages (hub+feed)',status='completed',conclusion='success',html_url='https://example.test/workflow')]}
        def check(index,search_item):
            def response(url):
                if 'actions/runs?' in url:return json.dumps(workflow).encode()
                if url.endswith('index.json'):return json.dumps({'items':[index]}).encode()
                if url.endswith('search.json'):return json.dumps([search_item]).encode()
                return doc.encode()
            with patch('bnoc.fetch',side_effect=response):return bnoc.verify_deployment(self.c,path,run)
        for field,value in [('title','Old title'),('description','Old description'),('revisedAt','old-time'),('revisionKinds',['design'])]:
            stale=dict(item,**{field:value})
            result=check(stale,search)
            self.assertEqual(result['status'],'waiting-for-live-archive');self.assertEqual(result['artifact'],'index.json')
            self.assertIsNotNone(run['lease'])
        for stale in [dict(search,title='Old title'),dict(search,search='Old prose at exactly the same URL')]:
            result=check(item,stale)
            self.assertEqual(result['status'],'waiting-for-live-archive');self.assertEqual(result['artifact'],'search.json')
            self.assertIsNotNone(run['lease'])
        self.assertEqual(check(item,search)['status'],'published')
        self.assertIsNone(bnoc.load(path/'run.json')['lease'])

if __name__=='__main__':unittest.main()
