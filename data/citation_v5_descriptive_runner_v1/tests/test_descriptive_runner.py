import copy,importlib.util,json,os,sys,tempfile,types,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import run_descriptive as runner
for name in ('citation_evidence_contract_v5','citation_evidence_pages_v5','citation_evidence_scoring_v5'):
    runner.load(name,ROOT/(name+'.py'))
engine=runner.load('v5_unit_execution',ROOT/'execution.py')
SNAPSHOT=ROOT.parent/'citation_v5_descriptive_freeze_v1'

class ProviderError(Exception):
    def __init__(self,code):self.code=code;super().__init__('Synthetic provider error.')

class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.results=Path(self.temp.name)/'results'
        self.now=datetime(2026,11,14,tzinfo=timezone.utc)
        self.input={'question':'What number is supplied?','candidate_answer':'Seven (demo.pdf, PDF page 2).','context':[{'passage_id':'P1','source':'demo.pdf','page':2,'text':'Seven.'}]}
        messages=[{'role':'system','content':'Synthetic rubric.'},{'role':'user','content':json.dumps(self.input)}]
        record={'messages':messages,'messages_sha256':engine.digest(messages)}
        self.context={'snapshot_hash':'a'*64,'candidate_hash':'b'*64,'model':'synthetic','sdk_version':'synthetic-sdk','config':{'temperature':0,'response_mime_type':'application/json','response_json_schema':{'type':'object'}},'expected_versions':['synthetic'],'execution':{'request_timeout_ms':120000,'sdk_attempts_per_invocation':1,'maximum_attempts_per_case':3,'minimum_seconds_between_requests':60,'retry_wait_seconds':[120,300],'retryable_http_statuses':[429,503],'completed_response_retries':False},'prompts':{'FRESH-V5-002':record,'FRESH-V5-004':copy.deepcopy(record)}}
        self.judgment={'answer_type':'factual_answer','coverage_status':'complete','claims':[{'claim_quote':'Seven','centrality':'central','requires_attribution':True,'citation_quotes':['(demo.pdf, PDF page 2)'],'cited_source_filenames':['demo.pdf'],'cited_pdf_pages':[2],'supporting_passage_ids':['P1'],'locator_assessment':'fully_supported','evidence_rationale':'Synthetic support assessment.'}],'score':2,'rationale':'Synthetic complete attribution.'}
        self.response={'text':json.dumps(self.judgment),'finish_reason':'STOP','model_version':'synthetic','usage':None}
        self.provider=Mock(return_value=self.response)
    def invoke(self,seconds=0,case='FRESH-V5-002',**kwargs):
        return engine.run_case(self.context,case,self.results,provider=self.provider,now=self.now+timedelta(seconds=seconds),**kwargs)
    def update(self):self.response['text']=json.dumps(self.judgment)
    def test_dry_run_writes_nothing(self):
        self.assertEqual(self.invoke()['status'],'dry_run');self.assertFalse(self.results.exists());self.provider.assert_not_called()
    def test_valid_response_reused(self):
        self.assertEqual(self.invoke(execute=True)['status'],'valid');self.assertTrue(self.invoke(execute=True)['reused']);self.provider.assert_called_once()
    def test_raw_response_preserved(self):
        self.invoke(execute=True);saved=json.loads((self.results/'FRESH-V5-002/attempt-001.response.json').read_bytes());self.assertEqual(saved['response'],self.response);self.assertEqual(saved['response_sha256'],engine.digest(self.response))
    def test_changed_prompt_rejected_before_request(self):
        self.context['prompts']['FRESH-V5-002']['messages'][0]['content']='changed'
        with self.assertRaises(ValueError):self.invoke(execute=True)
        self.provider.assert_not_called();self.assertFalse(self.results.exists())
    def test_changed_settings_cannot_reuse_folder(self):
        self.invoke(execute=True);self.context['config']['temperature']=1
        with self.assertRaises(ValueError):self.invoke(execute=True)
        self.provider.assert_called_once()
    def test_preflight_failure_creates_no_results(self):
        def fail():raise ValueError('Synthetic missing key.')
        with self.assertRaises(ValueError):self.invoke(execute=True,preflight=fail)
        self.provider.assert_not_called();self.assertFalse(self.results.exists())
    def test_inconsistent_score_preserved_without_retry(self):
        self.judgment['score']=1;self.update();self.assertEqual(self.invoke(execute=True)['status'],'score_evidence_inconsistent');self.assertEqual(self.invoke(seconds=300,execute=True,retry=True)['status'],'score_evidence_inconsistent');self.provider.assert_called_once()
    def test_uncertain_coverage_needs_review(self):
        self.judgment['coverage_status']='uncertain';self.update();self.assertEqual(self.invoke(execute=True)['status'],'needs_human_review')
    def test_malformed_response_terminal(self):
        self.response['text']='not json';self.assertEqual(self.invoke(execute=True)['status'],'contract_failure');self.invoke(seconds=300,execute=True,retry=True);self.provider.assert_called_once()
    def test_invalid_evidence_terminal(self):
        self.judgment['claims'][0]['claim_quote']='Invented.';self.update();self.assertEqual(self.invoke(execute=True)['status'],'contract_failure')
    def test_unfinished_response_terminal(self):
        self.response['finish_reason']='MAX_TOKENS';self.assertEqual(self.invoke(execute=True)['status'],'unfinished_response');self.invoke(seconds=300,execute=True,retry=True);self.provider.assert_called_once()
    def test_model_drift_blocks_execution(self):
        self.response['model_version']='different';self.assertEqual(self.invoke(execute=True)['status'],'model_metadata_blocked')
        with self.assertRaises(ValueError):self.invoke(seconds=100,case='FRESH-V5-004',execute=True)
        self.provider.assert_called_once()
    def test_fresh_case_prefix_pacing_enforced(self):
        self.invoke(execute=True)
        with self.assertRaises(ValueError):self.invoke(seconds=59,case='FRESH-V5-004',execute=True)
        self.provider.assert_called_once()
    def test_pacing_elapsed_permits_next_case(self):
        self.invoke(execute=True);self.assertEqual(self.invoke(seconds=60,case='FRESH-V5-004',execute=True)['status'],'valid');self.assertEqual(self.provider.call_count,2)
    def test_503_retry_requires_flag_and_elapsed_backoff(self):
        self.provider.side_effect=[ProviderError(503),self.response]
        self.assertEqual(self.invoke(execute=True)['status'],'provider_error')
        with self.assertRaises(ValueError):self.invoke(seconds=121,execute=True)
        with self.assertRaises(ValueError):self.invoke(seconds=119,execute=True,retry=True)
        self.assertEqual(self.invoke(seconds=121,execute=True,retry=True)['status'],'valid');self.assertEqual(self.provider.call_count,2)
    def test_nonretryable_error_retained(self):
        self.provider.side_effect=ProviderError(400);self.invoke(execute=True)
        with self.assertRaises(ValueError):self.invoke(seconds=500,execute=True,retry=True)
        self.provider.assert_called_once()
    def test_three_attempt_limit(self):
        self.provider.side_effect=ProviderError(503)
        self.invoke(execute=True);self.invoke(seconds=121,execute=True,retry=True);self.invoke(seconds=422,execute=True,retry=True)
        with self.assertRaises(ValueError):self.invoke(seconds=1000,execute=True,retry=True)
        self.assertEqual(self.provider.call_count,3)
    def test_tampered_response_rejected(self):
        self.invoke(execute=True);p=self.results/'FRESH-V5-002/attempt-001.response.json';v=json.loads(p.read_bytes());v['response']['text']='tampered';p.write_text(json.dumps(v))
        with self.assertRaises(ValueError):self.invoke(execute=True)
    def test_interruption_preserved_and_not_resubmitted(self):
        self.provider.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.invoke(execute=True)
        self.assertTrue((self.results/'FRESH-V5-002/attempt-001.started.json').exists());self.assertEqual(self.invoke(seconds=300,execute=True)['status'],'interrupted_or_unresolved');self.provider.assert_called_once()
    def test_existing_lock_preserved(self):
        self.results.mkdir();lock=self.results/'.execution.lock';lock.write_text('keep')
        with self.assertRaises(FileExistsError):self.invoke(execute=True)
        self.assertEqual(lock.read_text(),'keep');self.provider.assert_not_called()
    def test_provider_inputs_contain_no_human_review_payload(self):
        self.context['human_references']='SECRET_REFERENCE_PAYLOAD';self.invoke(execute=True)
        supplied=self.provider.call_args.args;self.assertNotIn('SECRET_REFERENCE_PAYLOAD',repr(supplied));self.assertEqual(supplied[2],self.context['prompts']['FRESH-V5-002']['messages'])
    def test_request_role_and_false_promotion(self):
        r=engine.request_for(self.context,'FRESH-V5-002');self.assertEqual(r['runner_version'],'citation-v5-descriptive-runner-v1');self.assertFalse(r['eligible_for_final_pass']);self.assertEqual(r['analysis_role'],'descriptive evaluation of 28 reviewed cases')

class FrozenLoaderTests(unittest.TestCase):
    def setUp(self):
        self.sdk=json.loads((SNAPSHOT/'freeze/review_packet/candidate.json').read_bytes())['request_configuration']['sdk_version']
    def test_exact_frozen_config_and_twenty_eight_prompts(self):
        c,e=runner.load_context(SNAPSHOT,None,self.sdk);candidate=json.loads((SNAPSHOT/'freeze/review_packet/candidate.json').read_bytes());self.assertEqual(len(c['prompts']),28);self.assertEqual(c['config'],candidate['request_configuration']['config']);self.assertEqual(c['model'],candidate['request_configuration']['model'])
    def test_excluded_cases_rejected(self):
        c,e=runner.load_context(SNAPSHOT,None,self.sdk)
        for cid in ['FRESH-V5-001','FRESH-V5-003']:
            with self.assertRaises(ValueError):e.request_for(c,cid)
    def test_wrong_sdk_rejected(self):
        with self.assertRaises(ValueError):runner.load_context(SNAPSHOT,None,'wrong-sdk')
    def test_loader_context_excludes_review_fields(self):
        c,e=runner.load_context(SNAPSHOT,None,self.sdk);self.assertEqual(set(c),{'snapshot_hash','candidate_hash','model','config','sdk_version','expected_versions','execution','prompts'})
        for record in c['prompts'].values():self.assertEqual(set(json.loads(record['messages'][1]['content'])),{'question','context','candidate_answer'})
    def test_tampered_snapshot_rejected(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'snapshot';shutil.copytree(SNAPSHOT,p,ignore=shutil.ignore_patterns('__pycache__'));f=p/'freeze/human_reviews.json';f.write_bytes(f.read_bytes()+b' ')
            with self.assertRaises(ValueError):runner.load_context(p,None,self.sdk)
    def test_missing_or_malformed_key_rejected_without_display(self):
        for key in ['', '*','x','bad key']:
            with patch.dict(os.environ,{'GOOGLE_API_KEY':key}):
                with self.assertRaises(ValueError):runner.google_preflight()
    def test_google_adapter_sends_exact_schema_and_single_attempt(self):
        genai=types.ModuleType('google.genai');opts=types.ModuleType('google.genai.types');calls={}
        def option(kind):
            def make(**kwargs):calls[kind]=kwargs;return kwargs
            return make
        opts.HttpOptions=option('http');opts.HttpRetryOptions=option('retry');opts.GenerateContentConfig=option('generation')
        response=types.SimpleNamespace(text='synthetic',candidates=[types.SimpleNamespace(finish_reason=types.SimpleNamespace(value='STOP'))],model_version='synthetic',usage_metadata=None)
        client=Mock();client.__enter__=Mock(return_value=client);client.__exit__=Mock(return_value=False);client.models.generate_content.return_value=response;genai.Client=Mock(return_value=client);genai.types=opts
        google=types.ModuleType('google');google.__path__=[];google.genai=genai
        config={'temperature':0,'max_output_tokens':4096,'response_mime_type':'application/json','response_json_schema':{'type':'object'}}
        messages=[{'role':'system','content':'Synthetic system.'},{'role':'user','content':'Synthetic user.'}]
        with patch.dict(sys.modules,{'google':google,'google.genai':genai,'google.genai.types':opts}),patch.dict(os.environ,{'GOOGLE_API_KEY':'synthetic-key'}):
            out=runner.google_provider('synthetic',config,messages,{'request_timeout_ms':120000,'sdk_attempts_per_invocation':1})
        self.assertEqual(calls['retry'],{'attempts':1});self.assertEqual(calls['http']['timeout'],120000);self.assertEqual(calls['generation'],dict(config,system_instruction='Synthetic system.'));self.assertEqual(out['finish_reason'],'STOP');self.assertEqual(client.models.generate_content.call_args.kwargs['contents'],'Synthetic user.')

if __name__=='__main__':unittest.main()
