import copy,tempfile,unittest
from pathlib import Path
from bible import digest
import reading_axes as axes
import source_reader
class ReadingAxesTests(unittest.TestCase):
 def setUp(self):
  self.doc='<html><head></head><body><aside id="scripture"><p>항상 보이는 성경</p></aside>'
  self.guide={'model':'test-fixture','reviewedAt':'2026-10-20T01:00:00+09:00','blockingFindings':[],'axes':{}}
  for n,key in enumerate(axes.AXES):
   card='<details class="study-card" id="'+key+'" open><summary>본문별 제목 '+key+'</summary><div class="brief">작성된 요약</div><div class="prose"><p>'+key+' 실제 해설 문단입니다.</p><details><summary>문법</summary><p>중첩 설명 보존</p></details></div></details>'
   self.doc+=card
   self.guide['axes'][key]={'cardId':key,'quote':key+' 실제 해설','introduction':'이 본문의 전환을 설명하는 문단입니다.','rationale':'Fixture is structural evidence, not theology approval.','beforeSha256':digest(card)}
  self.doc+="<textarea id='note'></textarea><script>const key='original_note';</script></body></html>"
  self.guide['applicationScopes']={key:{'cardId':'application','quote':'application 실제 해설'} for key in ('personal','community','public')}
 def test_nested_authored_html_scripts_and_notes_survive_exactly(self):
  result,binding=axes.apply(self.doc,self.guide)
  self.assertEqual(axes.audit(result),{'readingAxes':3})
  self.assertEqual(result.count('중첩 설명 보존'),3)
  self.assertIn("const key='original_note'",result)
  self.assertIn("<textarea id='note'>",result)
  self.assertEqual(binding['preservedCardsSha256'],digest(source_reader.cards(self.doc)))
  for card in source_reader.cards(self.doc).values():
   # Removing only the explicit addition reproduces each full original card.
   import re
   augmented=source_reader.cards(result)[next(k for k,v in source_reader.cards(self.doc).items() if v==card)]
   self.assertEqual(re.sub(r'<div class="analysis-landmark".*?</div>','',augmented,flags=re.S),card)
 def test_missing_or_combined_axis_is_rejected(self):
  bad=copy.deepcopy(self.guide);del bad['axes']['orthopraxy']
  with self.assertRaisesRegex(ValueError,'distinct reading axes'):axes.apply(self.doc,bad)
  bad=copy.deepcopy(self.guide);bad['axes']['orthopraxy']=copy.deepcopy(bad['axes']['orthodoxy'])
  with self.assertRaisesRegex(ValueError,'collapse'):axes.apply(self.doc,bad)
 def test_anchors_tampering_and_missing_public_scope_are_rejected(self):
  for kind in ('quote','sha','scope'):
   bad=copy.deepcopy(self.guide)
   if kind=='quote':bad['axes']['orthodoxy']['quote']='없는 해설'
   elif kind=='sha':bad['axes']['orthodoxy']['beforeSha256']='0'*64
   else:del bad['applicationScopes']['public']
   with self.assertRaises(ValueError):axes.apply(self.doc,bad)
 def test_anonymous_native_ids_and_original_count_remain_unchanged(self):
  doc=self.doc
  guide=copy.deepcopy(self.guide)
  for i,key in enumerate(axes.AXES,1):
   doc=doc.replace(' id="'+key+'"','')
   guide['axes'][key].update(cardId='@ordinal:'+str(i).zfill(2))
   guide['axes'][key].pop('beforeSha256')
  guide['applicationScopes']={k:{'cardId':'@ordinal:03','quote':'application 실제 해설'} for k in ('personal','community','public')}
  result,_=axes.apply(doc,guide)
  self.assertEqual(list(source_reader.cards(result)),['@ordinal:01','@ordinal:02','@ordinal:03'])
  self.assertNotIn('id="@ordinal:',result)
 def test_incomplete_manual_review_and_executable_introduction_are_rejected(self):
  for value in ('<script>alert(1)</script>',''):
   bad=copy.deepcopy(self.guide);bad['axes']['orthodoxy']['introduction']=value
   with self.assertRaises(ValueError):axes.apply(self.doc,bad)
  with self.assertRaises(ValueError):axes.verify_review({'readingAxes':{'guideSha256':'stale'}},{'readingAxes':{'guideSha256':'new'}})
 def test_duplicate_guide_is_not_silently_stacked(self):
  result,_=axes.apply(self.doc,self.guide)
  with self.assertRaisesRegex(ValueError,'already exists'):axes.apply(result,self.guide)
 def test_new_public_application_is_distinguished_from_existing_prose(self):
  guide=copy.deepcopy(self.guide)
  guide['axes']['application']['introduction']='기존 적용으로 들어갑니다.\n\n공적 삶에서 보강한 설명입니다.'
  guide['applicationScopes']['public']={'cardId':'@guide:application','quote':'공적 삶에서 보강한 설명'}
  result,_=axes.apply(self.doc,guide)
  self.assertIn('<p>공적 삶에서 보강한 설명입니다.</p>',result)
  guide['applicationScopes']['public']['cardId']='application'
  with self.assertRaisesRegex(ValueError,'Application scope'):axes.apply(self.doc,guide)
if __name__=='__main__':unittest.main()
