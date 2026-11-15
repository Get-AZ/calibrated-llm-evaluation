"""Run one frozen V5 descriptive case; default dry run. No score-guided retries."""
import argparse,copy,hashlib,importlib.util,json,os,sys
from importlib.metadata import version
from pathlib import Path

def require(ok,message):
    if not ok:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(Path(path).read_bytes())
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    require(spec is not None and spec.loader is not None,'Module unavailable.')
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

def load_context(snapshot,project,installed_sdk):
    here=Path(__file__).resolve().parent;snapshot=Path(snapshot).resolve()
    tools=read(here/'tool_manifest.json')
    for name,binding in tools['files'].items():
        p=Path(name);require(not p.is_absolute() and '..' not in p.parts,'Unsafe tool path.')
        raw=(here/p).read_bytes();require(sha(raw)==binding['sha256'] and len(raw)==binding['bytes'],'Runner file changed: '+name)
    adaptation=read(here/'adaptation.json')
    require(sha((snapshot/'freeze_manifest.json').read_bytes())==adaptation['snapshot_freeze_manifest_sha256'],'Unexpected frozen run inputs.')
    require(sha((snapshot/'bundle_manifest.json').read_bytes())==adaptation['snapshot_bundle_manifest_sha256'],'Unexpected snapshot bundle.')
    verifier=load('v5_descriptive_snapshot_verifier',snapshot/'verify_freeze.py')
    verifier.verify(snapshot,project)
    f=snapshot/'freeze';candidate_raw=(f/'review_packet/candidate.json').read_bytes();candidate=json.loads(candidate_raw)
    config=candidate['request_configuration'];require(installed_sdk==config['sdk_version'],'Installed google-genai differs from locked SDK.')
    protocol=read(f/'review_packet/protocol.json');execution=protocol['execution']
    require(execution=={
        'maximum_attempts_per_case':3,'retryable_http_statuses':[429,503],
        'retry_wait_seconds':[120,300],'minimum_seconds_between_requests':60,
        'request_timeout_ms':120000,'sdk_attempts_per_invocation':1,
        'completed_response_retries':False},'Unexpected execution controls.')
    frozen_files=f/'candidate_freeze/files'
    base=(frozen_files/'data/citation_v5_development_runner_v1/evidence_execution.py').read_bytes()
    require(sha(base)==adaptation['base_execution_sha256'],'Base execution changed.')
    expected=base.decode('utf-8')
    for change in adaptation['execution_changes']:
        require(change['from'] in expected,'Adaptation no longer matches source.')
        expected=expected.replace(change['from'],change['to'])
    require((here/'execution.py').read_bytes()==expected.encode('utf-8'),'Execution differs beyond declared adaptation.')
    for name,expected_hash in candidate['validator_file_sha256'].items():
        require(sha((here/name).read_bytes())==expected_hash,'Validator differs from candidate.')
        require((here/name).read_bytes()==(frozen_files/name).read_bytes(),'Frozen validator bytes differ.')
    # Install verified validator modules explicitly, avoiding project import shadowing.
    for name in ('citation_evidence_contract_v5','citation_evidence_pages_v5','citation_evidence_scoring_v5'):
        load(name,here/(name+'.py'))
    engine=load('v5_descriptive_execution',here/'execution.py')
    records=read(f/'judge_prompts.json')['records']
    require(len(records)==28 and len({r['case_id'] for r in records})==28,'Unexpected prompt inventory.')
    prompts={r['case_id']:copy.deepcopy(r) for r in records}
    require('FRESH-V5-001' not in prompts and 'FRESH-V5-003' not in prompts,'Excluded case entered prompts.')
    context={
        'snapshot_hash':sha((snapshot/'freeze_manifest.json').read_bytes()),
        'candidate_hash':sha(candidate_raw),'model':config['model'],
        'config':copy.deepcopy(config['config']),'sdk_version':installed_sdk,
        'expected_versions':copy.deepcopy(candidate['returned_model_versions']),
        'execution':copy.deepcopy(execution),'prompts':prompts,
    }
    return context,engine

def google_preflight():
    key=os.environ.get('GOOGLE_API_KEY','')
    require(len(key)>1 and not any(c.isspace() for c in key) and set(key)!={'*'},'GOOGLE_API_KEY is missing or malformed; value not displayed.')
    from google import genai
    from google.genai import types

def google_provider(model,config,messages,execution):
    from google import genai
    from google.genai import types
    require([m['role'] for m in messages]==['system','user'],'Unexpected message roles.')
    with genai.Client(api_key=os.environ['GOOGLE_API_KEY'],http_options=types.HttpOptions(
        timeout=execution['request_timeout_ms'],retry_options=types.HttpRetryOptions(attempts=execution['sdk_attempts_per_invocation']))) as client:
        result=client.models.generate_content(model=model,contents=messages[1]['content'],
            config=types.GenerateContentConfig(system_instruction=messages[0]['content'],**config))
    candidates=result.candidates or [];finish=candidates[0].finish_reason if candidates else None
    return {'text':result.text or '','finish_reason':getattr(finish,'value',str(finish)),
            'model_version':getattr(result,'model_version',None),
            'usage':result.usage_metadata.model_dump(mode='json') if result.usage_metadata else None}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--project-root',type=Path,default=Path.cwd())
    parser.add_argument('--execute',action='store_true');parser.add_argument('--retry',action='store_true')
    args=parser.parse_args();project=args.project_root.resolve()
    snapshot=project/'data/citation_v5_descriptive_freeze_v1'
    context,engine=load_context(snapshot,project,version('google-genai'))
    outcome=engine.run_case(context,args.case,project/'data/citation_v5_descriptive_results_v1',
        execute=args.execute,retry=args.retry,provider=google_provider,preflight=google_preflight)
    print('VERIFIED: frozen V5 descriptive inputs, local bindings and locked SDK/settings.')
    print('Case:',args.case,'| model:',context['model']);print('Request hash:',outcome['request_sha256']);print('Status:',outcome['status'])
    if outcome['status']=='dry_run':print('DRY RUN: no API requests or result files.')
    elif outcome['status']=='provider_error':
        print('Provider HTTP status:',outcome['http_status'],'| attempt:',outcome['attempt'])
        print('Error preserved. Only 429/503 permit explicit retry after backoff.')
    else:
        print('REUSED saved terminal response; no API request.' if outcome.get('reused') else 'SAVED raw response and attempt audit; no response repair or score correction.')
        if outcome['status']=='valid':print('Evidence contract valid and internally consistent; semantic correctness is not independently verified.')
    print('28-case descriptive evaluation only. Original acceptance: BLOCKED. Eligible for final pass: False.')
    if outcome['status'] not in ('dry_run','valid'):raise SystemExit(2)

if __name__=='__main__':main()
