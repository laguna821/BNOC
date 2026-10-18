import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import bnoc
import revision
import render
from bible import digest, save

class RevisionTests(unittest.TestCase):
    def test_target_traversal_and_non_archive_rejected(self):
        for path in ('../index.html','/2025/08172025/x.html','2025/08172025/../x.html','index.html','2025\\08172025\\x.html'):
            with self.assertRaises(ValueError):revision.source('.',path)

    def test_concurrent_original_change_blocks(self):
        with patch('revision.source',return_value=b'new'):
            with self.assertRaisesRegex(ValueError,'conflict'):
                revision.check_base('.',{'originalSha256':digest(b'old')},'2025/08172025/a.html','HEAD')

    def test_date_cannot_be_reassigned(self):
        with patch('bnoc.git',return_value='commit'),patch('revision.source',return_value=b'original'):
            with self.assertRaisesRegex(ValueError,'original archive date: 2025-08-17'):
                revision.begin({'repo':'.'},'2025/08172025/x.html','민18:21','2026-10-18',['design'],'Preserve','publish')

    def test_design_fingerprint_preserves_prose_and_behavior(self):
        doc='<html><head><style>p{color:red}</style></head><body><p id="a">기존 해설</p><button onclick="quiz()">질문</button><script>let answer=2;</script></body></html>'
        base=revision.content_hash(doc)
        self.assertEqual(base,revision.content_hash(doc.replace('red','blue')))
        for old,new in [('기존 해설','다른 해설'),('id="a"','id="b"'),('quiz()','nothing()'),('answer=2','answer=3')]:
            self.assertNotEqual(base,revision.content_hash(doc.replace(old,new)))

    def test_original_snapshot_tamper_blocks_design_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'original.html').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'snapshot changed'):
                revision.render_design(path,{'revision':{'originalSha256':digest(b'original')}})

    def test_print_proof_opens_collapsed_scripture(self):
        doc='<html><head></head><body><details class="scripture"><summary>본문</summary><p>Verse</p></details><details open><p>Study</p></details></body></html>'
        proof=render.print_proof(doc)
        self.assertIn('<details class="scripture" open>',proof)
        self.assertNotIn('open open',proof)

    def test_scripture_visibility_preserves_every_other_byte(self):
        original='<html><head></head><body><details class="scripture"><summary>성경 본문 전체 보기</summary><h2>민수기</h2><p><span class="verse-no">1</span>본문</p></details><details id="study"><summary>해설</summary>보존</details><script>let note="keep";</script></body></html>'
        rev={'originalSha256':digest(original.encode()),'kinds':['scripture'],'revisedAt':'2026-10-18T08:45:00+00:00'}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'original.html').write_bytes(original.encode())
            doc,_=revision.render_design(path,{'revision':rev})
            expected=original.replace('<details class="scripture"><summary>성경 본문 전체 보기</summary>','<aside class="scripture">').replace('</details>','</aside>',1)
            self.assertEqual(doc,revision.stamp(expected,rev))
            self.assertIn('<details id="study">',doc)
            bad=original.replace('class="scripture"','class="unknown"')
            (path/'original.html').write_bytes(bad.encode());rev['originalSha256']=digest(bad.encode())
            with self.assertRaisesRegex(ValueError,'known collapsed'):
                revision.render_design(path,{'revision':rev})

    def test_revision_replaces_only_target_and_retries_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir();remote=root/'remote.git'
            import subprocess
            subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
            subprocess.run(['git','init',str(repo)],check=True,capture_output=True)
            def g(*args,input=None):return bnoc.git(repo,*args,input=input)
            g('remote','add','origin',str(remote))
            target='2025/08172025/numbers.html'
            for name,data in [(target,b'old'),('historical.html.',b'preserved')]:
                blob=g('hash-object','-w','--stdin',input=data);g('update-index','--add','--cacheinfo','100644',blob,name)
            tree=g('write-tree');base=g('-c','user.name=Test','-c','user.email=test@example.test','commit-tree',tree,input=b'baseline')
            g('push','origin',base+':refs/heads/main')
            save(root/'bible.json',{'민18:21':'fixture'})
            c={'root':root/'state','repo':repo,'bible':str(root/'bible.json'),'site':'https://example.test/','gitAuthor':{'name':'Test','email':'test@example.test'}}
            result=revision.begin(c,target,'민18:21','2025-08-17',['design'],'Keep original theme','publish')
            path=Path(result['path']);run=bnoc.load(path/'run.json');output=path/'numbers.html';output.write_bytes(b'revised')
            save(path/'review.json',{'model':'test-fixture'})
            with patch('bnoc.audit_review',return_value={'htmlSha256':digest(b'revised')}):
                first=bnoc.publish(c,path,run);self.assertEqual(first['status'],'pushed-awaiting-deployment')
                g('fetch','origin','main')
                self.assertEqual(g('show','origin/main:'+target),'revised')
                self.assertEqual(g('show','origin/main:historical.html.'),'preserved')
                manifest=json.loads(g('show','origin/main:issues/'+run['id']+'.json'))
                self.assertEqual(manifest['date'],'2025-08-17')
                self.assertNotIn('intent',manifest['revision'])
                self.assertEqual(bnoc.publish(c,path,run)['status'],'already-pushed')

if __name__=='__main__':unittest.main()
