import copy, importlib.util, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('checks',ROOT/'run_checks.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class Checks(unittest.TestCase):
 def fixture(self):
  rows=[{'case_id':str(i),'reference_score':i%3,'judge_score':i%3,'status':'valid'} for i in range(28)]
  r={'records':rows,'metrics':{'included_cases':28,'matches':28,'valid_consistent_cases':28,'reference_zero_judge_two_cases':[],'reference_support_included':{'0':10,'1':9,'2':9}},'operational_audit':{'all_request_and_response_bindings_verified':True,'retry_backoff_verified':True,'minimum_recorded_start_gap_seconds':62},'original_acceptance_attempt':'BLOCKED','eligible_for_final_pass':False,'candidate_promoted':False,'analysis_role':'descriptive','exclusions':['a','b']}
  protocol={'acceptance_gates':{'primary_denominator':30,'required_structurally_valid_and_consistent_cases':30,'minimum_exact_matches_all_primary_cases':27,'maximum_reference_zero_judge_two_cases':0,'minimum_reference_cases_each_score':5},'execution':{'minimum_seconds_between_requests':60}}
  return r,protocol
 def test_integrity_pass_does_not_promote(self):
  r,p=self.fixture();out=c.assess(r,p);self.assertEqual(out['integrity_status'],'PASS');self.assertEqual(out['promotion_status'],'BLOCKED');self.assertFalse(out['candidate_promoted'])
 def test_changed_agreement_fails(self):
  r,p=self.fixture();r['metrics']['matches']=27;self.assertEqual(c.assess(r,p)['integrity_status'],'FAIL')
 def test_duplicate_case_fails(self):
  r,p=self.fixture();r['records'][1]['case_id']='0';self.assertEqual(c.assess(r,p)['integrity_status'],'FAIL')
 def test_bool_score_fails(self):
  r,p=self.fixture();r['records'][0]['reference_score']=False;self.assertEqual(c.assess(r,p)['integrity_status'],'FAIL')
 def test_unverified_binding_fails(self):
  r,p=self.fixture();r['operational_audit']['all_request_and_response_bindings_verified']=False;self.assertEqual(c.assess(r,p)['integrity_status'],'FAIL')
 def test_pacing_fails(self):
  r,p=self.fixture();r['operational_audit']['minimum_recorded_start_gap_seconds']=59;self.assertEqual(c.assess(r,p)['integrity_status'],'FAIL')
 def test_promotion_claim_fails(self):
  r,p=self.fixture();r['candidate_promoted']=True;self.assertEqual(c.assess(r,p)['integrity_status'],'FAIL')
 def test_inputs_unchanged(self):
  r,p=self.fixture();before=copy.deepcopy((r,p));c.assess(r,p);self.assertEqual((r,p),before)
if __name__=='__main__':unittest.main()
