"""Auditable single-case pilot execution. Standard library only until live execution."""
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_bytes())


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def parse_response(text):
    def reject(value):
        raise ValueError('Non-finite JSON value.')
    def unique(pairs):
        result={}
        for k,v in pairs:
            require(k not in result, 'Duplicate JSON key.')
            result[k]=v
        return result
    value=json.loads(text, parse_constant=reject, object_pairs_hook=unique)
    require(isinstance(value,dict) and set(value)=={'score','rationale'}, 'Expected exactly score and rationale.')
    require(type(value['score']) is int and value['score'] in (0,1,2), 'Invalid citation score.')
    require(isinstance(value['rationale'],str) and bool(value['rationale'].strip()), 'Missing rationale.')
    return value


def request_for(context, case_id):
    require(case_id in context['prompts'], 'Unknown case ID.')
    record=context['prompts'][case_id]
    require(digest(record['messages'])==record['messages_sha256'],'Prompt hash mismatch.')
    return {
        'runner_version':'citation-v5-descriptive-runner-v1',
        'analysis_role':'descriptive evaluation of 28 reviewed cases','eligible_for_final_pass':False,
        'snapshot_manifest_sha256':context['snapshot_hash'],
        'candidate_manifest_sha256':context['candidate_hash'],
        'case_id':case_id,'model':context['model'],'sdk_version':context['sdk_version'],
        'config':context['config'],'messages_sha256':record['messages_sha256'],
        'timeout_ms':context['execution']['request_timeout_ms'],
        'sdk_attempts':context['execution']['sdk_attempts_per_invocation'],
    }


def parse_time(value):
    t=datetime.fromisoformat(value)
    require(t.tzinfo is not None,'Audit timestamp lacks timezone.')
    return t


def classify_response(response, expected_versions, evidence_input=None):
    if response['model_version'] not in expected_versions:
        return {'status':'model_metadata_blocked','detail':'Unexpected or missing returned model version.'}
    if response['finish_reason']!='STOP':
        return {'status':'unfinished_response','detail':'Response did not finish with STOP.'}
    if evidence_input is None:
        return {'status':'contract_failure','detail':'Evidence input unavailable.'}
    from citation_evidence_pages_v5 import validate_evidence_response
    from citation_evidence_scoring_v5 import check_consistency
    try:
        parsed=validate_evidence_response(
            response['text'], evidence_input['candidate_answer'], evidence_input['context'])
        consistency=check_consistency(
            response['text'], evidence_input['candidate_answer'], evidence_input['context'])
    except (ValueError, TypeError, KeyError) as error:
        return {'status':'contract_failure','detail':str(error)}
    status={
        'consistent':'valid',
        'inconsistent':'score_evidence_inconsistent',
        'needs_review':'needs_human_review',
    }[consistency['status']]
    return {'status':status,'judgment':parsed,'consistency':consistency}


def history(folder, request, expected_versions, evidence_input=None):
    if not folder.exists():
        return []
    require(read(folder/'request.json')==request,'Saved request differs from fixed inputs.')
    starts=sorted(folder.glob('attempt-*.started.json'))
    require(len(starts)<=3,'Too many attempts.')
    events=[]
    for index,start in enumerate(starts,1):
        prefix=f'attempt-{index:03d}'
        require(start.name==prefix+'.started.json','Noncontiguous attempt sequence.')
        event=read(start)
        require(event['request_sha256']==digest(request) and event['attempt']==index,'Attempt binding mismatch.')
        parse_time(event['started_at_utc'])
        response_path=folder/(prefix+'.response.json')
        error_path=folder/(prefix+'.error.json')
        require(not (response_path.exists() and error_path.exists()),'Ambiguous attempt artifacts.')
        if response_path.exists():
            stored=read(response_path)
            require(stored['request_sha256']==digest(request),'Response request binding mismatch.')
            require(stored['response_sha256']==digest(stored['response']),'Response hash mismatch.')
            outcome=classify_response(stored['response'],expected_versions,evidence_input)
            event.update(outcome)
        elif error_path.exists():
            stored=read(error_path)
            require(stored['request_sha256']==digest(request),'Error request binding mismatch.')
            parse_time(stored['finished_at_utc'])
            event.update(status='provider_error',error=stored)
        else:
            event['status']='interrupted_or_unresolved'
        # A later attempt is allowed only after a retryable provider error.
        if events:
            previous=events[-1]
            require(previous['status']=='provider_error' and previous['error']['http_status'] in (429,503), 'Invalid retry after a terminal or ambiguous outcome.')
            delay=(120,300)[index-2]
            elapsed=(parse_time(event['started_at_utc'])-parse_time(previous['error']['finished_at_utc'])).total_seconds()
            require(elapsed>=delay,'Retry occurred before required backoff.')
        events.append(event)
    recognized={'request.json'}|{p.name for p in starts}
    for index in range(1,len(starts)+1):
        recognized|={f'attempt-{index:03d}.response.json',f'attempt-{index:03d}.error.json'}
    require(all(p.name in recognized for p in folder.iterdir()),'Unexpected case-result files.')
    return events


def run_case(context, case_id, results, execute=False, retry=False, provider=None, preflight=None, now=None):
    results=Path(results)
    require(not (results/'MODEL_METADATA_BLOCK.json').exists(),'Model metadata block exists; investigate before further execution.')
    request=request_for(context,case_id)

    evidence_input=json.loads(context['prompts'][case_id]['messages'][1]['content'])
    require(isinstance(evidence_input,dict) and
            'candidate_answer' in evidence_input and 'context' in evidence_input,
            'Invalid evidence input.')
    case_folder=results/case_id
    run_binding={
        'snapshot_manifest_sha256':context['snapshot_hash'],
        'candidate_manifest_sha256':context['candidate_hash'],
        'model':context['model'],'sdk_version':context['sdk_version'],
        'config':context['config'],'runner_version':request['runner_version'],
        'analysis_role':'descriptive evaluation of 28 reviewed cases','eligible_for_final_pass':False,
    }
    if (results/'run_binding.json').exists():
        require(read(results/'run_binding.json')==run_binding,'Results folder belongs to different inputs or settings.')
    events=history(case_folder,request,context['expected_versions'],evidence_input)
    if events and events[-1]['status']!='provider_error':
        last=events[-1]
        return {'status':last['status'],'reused':True,'case_id':case_id,'request_sha256':digest(request)}
    if not execute:
        return {'status':'dry_run','case_id':case_id,'request_sha256':digest(request),'attempts_already_recorded':len(events)}
    require(callable(provider),'No live provider configured.')
    current=now or datetime.now(timezone.utc)
    require(current.tzinfo is not None,'Execution time must have timezone.')
    maximum=context['execution']['maximum_attempts_per_case']
    if events:
        require(retry,'Previous provider error preserved. Use --retry only after the documented backoff.')
        last=events[-1]
        require(last['error']['http_status'] in context['execution']['retryable_http_statuses'],'This error is not automatically retryable.')
        require(len(events)<maximum,'Maximum attempts reached; no further request permitted.')
        wait=context['execution']['retry_wait_seconds'][len(events)-1]
        remaining=wait-(current-parse_time(last['error']['finished_at_utc'])).total_seconds()
        require(remaining<=0,f'Retry backoff not complete; wait at least {math.ceil(remaining)} seconds.')
    else:
        require(not retry,'No earlier provider error exists for --retry.')
    if preflight is not None:
        preflight()
    results.mkdir(parents=True,exist_ok=True)
    lock=results/'.execution.lock'
    with lock.open('x',encoding='utf-8') as stream:
        stream.write('One pilot invocation is in progress. Inspect before clearing an orphaned lock.\n')
    try:
        if (results/'run_binding.json').exists():
            require(read(results/'run_binding.json')==run_binding,'Run binding changed.')
        else:
            write_new(results/'run_binding.json',run_binding)
        # Recheck case state inside the lock to avoid concurrent duplicate calls.
        latest=history(case_folder,request,context['expected_versions'],evidence_input)
        require(len(latest)==len(events),'Case state changed during invocation.')
        starts=list(results.glob('FRESH-V5-*/attempt-*.started.json'))
        if starts:
            latest_time=max(parse_time(read(p)['started_at_utc']) for p in starts)
            remaining=context['execution']['minimum_seconds_between_requests']-(current-latest_time).total_seconds()
            require(remaining<=0,f'Pacing limit: wait at least {math.ceil(remaining)} seconds.')
        case_folder.mkdir(exist_ok=True)
        if not (case_folder/'request.json').exists():
            write_new(case_folder/'request.json',request)
        attempt=len(events)+1;prefix=f'attempt-{attempt:03d}'
        write_new(case_folder/(prefix+'.started.json'),{
            'request_sha256':digest(request),'attempt':attempt,'started_at_utc':current.isoformat()
        })
        try:
            # Provider sees only fixed model/config plus the frozen messages.
            response=provider(context['model'],context['config'],context['prompts'][case_id]['messages'],context['execution'])
        except Exception as error:
            code=getattr(error,'code',None)
            code=code if type(code) is int else None
            write_new(case_folder/(prefix+'.error.json'),{
                'request_sha256':digest(request),'finished_at_utc':(now or datetime.now(timezone.utc)).isoformat(),
                'http_status':code,'error_type':type(error).__name__,
                'note':'Provider error text omitted to avoid recording credentials or request URLs.'
            })
            return {'status':'provider_error','case_id':case_id,'http_status':code,'attempt':attempt,'request_sha256':digest(request)}
        write_new(case_folder/(prefix+'.response.json'),{
            'request_sha256':digest(request),'finished_at_utc':(now or datetime.now(timezone.utc)).isoformat(),
            'response':response,'response_sha256':digest(response),
        })
        outcome=classify_response(response,context['expected_versions'],evidence_input)
        if outcome['status']=='model_metadata_blocked':
            write_new(results/'MODEL_METADATA_BLOCK.json',{
                'case_id':case_id,'returned_model_version':response['model_version'],
                'expected_versions':context['expected_versions'],'note':'Investigate before further requests.'
            })
        return {'status':outcome['status'],'case_id':case_id,'attempt':attempt,'request_sha256':digest(request)}
    finally:
        lock.unlink(missing_ok=True)
