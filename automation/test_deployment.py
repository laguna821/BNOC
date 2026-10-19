import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import bnoc

class SupersedingDeploymentTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir();remote=self.root/'remote.git'
  subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
  subprocess.run(['git','init',str(self.repo)],check=True,capture_output=True)
  bnoc.git(self.repo,'remote','add','origin',str(remote))
  blob=bnoc.git(self.repo,'hash-object','-w','--stdin',input=b'fixture')
  bnoc.git(self.repo,'update-index','--add','--cacheinfo','100644',blob,'fixture.txt')
  tree=bnoc.git(self.repo,'write-tree')
  def commit(message,parent=None):
   args=['-c','user.name=Test','-c','user.email=test@example.test','commit-tree',tree]
   if parent:args+=['-p',parent]
   return bnoc.git(self.repo,*args,input=message.encode())
  self.base=commit('Original');self.child=commit('Descendant',self.base);self.other=commit('Unrelated root')
  bnoc.git(self.repo,'push','origin',self.child+':refs/heads/main')
  self.c={'repo':self.repo}
 def tearDown(self):self.temp.cleanup()
 def job(self,sha,**changes):
  return dict(name='BNOC Pages (hub+feed)',status='completed',conclusion='success',head_branch='main',event='push',head_sha=sha,html_url='https://example.test/'+sha,**changes)
 def test_only_a_proven_descendant_success_supersedes_cancellation(self):
  recent={'workflow_runs':[self.job(self.other),self.job(self.child)]}
  with patch('bnoc.fetch',return_value=json.dumps(recent).encode()):
   self.assertEqual(bnoc.successor_deployment(self.c,self.base)['head_sha'],self.child)
 def test_success_on_an_unrelated_history_is_not_evidence(self):
  with patch('bnoc.fetch',return_value=json.dumps({'workflow_runs':[self.job(self.other)]}).encode()):
   self.assertIsNone(bnoc.successor_deployment(self.c,self.base))
 def test_fork_branch_and_invalid_commit_are_not_trusted(self):
  a=self.job(self.child);a['head_branch']='feature'
  b=self.job(self.child);b['event']='pull_request'
  c=self.job(self.child);c['head_sha']='--all'
  with patch('bnoc.fetch',return_value=json.dumps({'workflow_runs':[a,b,c]}).encode()),patch('bnoc.git',side_effect=AssertionError('No candidate should fetch')):
   self.assertIsNone(bnoc.successor_deployment(self.c,self.base))
 def test_cancelled_job_without_descendant_waits_without_completing_run(self):
  job=self.job(self.base);job['conclusion']='cancelled'
  with patch('bnoc.fetch',return_value=json.dumps({'workflow_runs':[job]}).encode()),patch('bnoc.successor_deployment',return_value=None):
   result=bnoc.verify_deployment(self.c,self.root,{'commit':self.base})
  self.assertEqual(result['status'],'waiting-for-successor-deployment')
 def test_real_workflow_failure_is_not_masked(self):
  job=self.job(self.base);job['conclusion']='failure'
  with patch('bnoc.fetch',return_value=json.dumps({'workflow_runs':[job]}).encode()),patch('bnoc.successor_deployment',side_effect=AssertionError('Do not mask failure')):
   with self.assertRaisesRegex(ValueError,'Deployment failed'):bnoc.verify_deployment(self.c,self.root,{'commit':self.base})

if __name__=='__main__':unittest.main()
