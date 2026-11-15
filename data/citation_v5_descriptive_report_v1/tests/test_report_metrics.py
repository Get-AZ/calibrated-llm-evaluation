import importlib.util,json,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'tools/report_v5.py';s=importlib.util.spec_from_file_location('v5_report_metrics',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def row(h,j,status='valid',cid='FRESH-V5-002'):
    return {'case_id':cid,'document_family_id':'synthetic','status':status,'reference_score':h,'judge_score':j,'matches_reference':status=='valid' and h==j,'reference_rationale':'Synthetic human rationale.','judge_rationale':'Synthetic judge rationale.','question':'Synthetic question?','candidate_answer':'Synthetic answer.','context':[{'passage_id':'P1','source':'demo.pdf','page':1,'text':'Synthetic evidence.'}],'attempts':1}

class ReportTests(unittest.TestCase):
    def test_failure_stays_in_included_denominator(self):
        v=m.metrics([row(2,2),row(1,None,'provider_error','FRESH-V5-004')],planned=4,excluded=2)
        self.assertEqual(v['agreement_over_included'],.5);self.assertEqual(v['agreement_valid_only'],1);self.assertEqual(v['included_without_valid_consistent_score'],1)
    def test_mae_does_not_impute_failure(self):
        v=m.metrics([row(2,2),row(1,None,'provider_error','FRESH-V5-004')],planned=4,excluded=2)
        self.assertEqual(v['mean_absolute_score_error_valid_only'],0)
    def test_exclusions_are_inventory_not_numeric_labels(self):
        v=m.metrics([row(1,1)],planned=3,excluded=2)
        self.assertEqual(v['agreement_over_included'],1);self.assertEqual(v['confirmed_matches_over_planned_inventory'],1/3);self.assertEqual(v['confusion_reference_rows_judge_columns'],[[0,0,0],[0,1,0],[0,0,0]])
    def test_confusion_and_support_include_unscored_reference(self):
        v=m.metrics([row(0,2),row(1,None,'contract_failure','FRESH-V5-004')],planned=4,excluded=2)
        self.assertEqual(v['reference_support_included'],{'0':1,'1':1,'2':0});self.assertEqual(v['confusion_reference_rows_judge_columns'][0][2],1)
    def test_large_gap_does_not_replace_reference(self):
        r=row(0,2);v=m.metrics([r],planned=3,excluded=2)
        self.assertEqual(r['reference_score'],0);self.assertEqual(v['mean_absolute_score_error_valid_only'],2);self.assertEqual(v['reference_zero_judge_two_cases'],['FRESH-V5-002'])
    def test_kappa_perfect_and_degenerate(self):
        self.assertAlmostEqual(m.metrics([row(0,0),row(1,1),row(2,2)],planned=5,excluded=2)['unweighted_cohen_kappa_valid_only'],1)
        self.assertIsNone(m.metrics([row(2,2)],planned=3,excluded=2)['unweighted_cohen_kappa_valid_only'])
    def test_wilson_bounds_and_empty(self):
        lo,hi=m.wilson(19,28);self.assertLess(lo,19/28);self.assertGreater(hi,19/28);self.assertIsNone(m.wilson(0,0))
    def test_report_roundtrip_hashes_and_no_overwrite(self):
        rows=[row(1,1)];report={'metrics':m.metrics(rows,planned=3,excluded=2),'operational_audit':{'recorded_sdk_invocations':1,'saved_responses':1,'provider_error_attempts':0,'retry_attempts':0,'minimum_recorded_start_gap_seconds':None,'attempts':[]},'records':rows,'limitations':['Synthetic report.']}
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'report';m.write_report(report,out);self.assertEqual(m.read(out/'report.json'),report)
            for name,expected in m.read(out/'report_manifest.json')['files'].items():self.assertEqual(m.sha((out/name).read_bytes()),expected)
            with self.assertRaises(ValueError):m.write_report(report,out)

if __name__=='__main__':unittest.main()
