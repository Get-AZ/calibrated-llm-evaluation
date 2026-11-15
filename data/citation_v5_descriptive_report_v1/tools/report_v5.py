"""Offline audit and descriptive comparison. Never calls a provider."""
import argparse,collections,csv,hashlib,importlib.util,json,math
from datetime import datetime,timezone
from pathlib import Path

def require(ok,message):
    if not ok:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(Path(path).read_bytes())
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    require(spec is not None and spec.loader is not None,'Audit dependency unavailable.')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def wilson(matches,total):
    if total==0:return None
    z=1.959963984540054;p=matches/total;den=1+z*z/total
    mid=(p+z*z/(2*total))/den;half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [mid-half,mid+half]

def metrics(rows,planned=30,excluded=2):
    included=len(rows);valid=[r for r in rows if r['status']=='valid'];matches=sum(r['judge_score']==r['reference_score'] for r in valid)
    matrix=[[sum(r['reference_score']==h and r['judge_score']==j for r in valid) for j in (0,1,2)] for h in (0,1,2)]
    n=len(valid);expected=sum(sum(matrix[k])*sum(row[k] for row in matrix) for k in range(3))/(n*n) if n else None
    observed=matches/n if n else None;kappa=(observed-expected)/(1-expected) if n and expected<1 else None
    support={str(k):sum(r['reference_score']==k for r in rows) for k in (0,1,2)}
    families=[]
    for family in sorted({r['document_family_id'] for r in rows}):
        subset=[r for r in rows if r['document_family_id']==family];vv=[r for r in subset if r['status']=='valid'];mm=sum(r['judge_score']==r['reference_score'] for r in vv)
        families.append({'document_family_id':family,'included':len(subset),'valid':len(vv),'matches':mm,'agreement_over_included':mm/len(subset)})
    return {'planned_cases':planned,'excluded_cases':excluded,'included_cases':included,'valid_consistent_cases':n,'matches':matches,
            'numeric_disagreements':n-matches,'included_without_valid_consistent_score':included-n,
            'agreement_over_included':matches/included if included else None,'agreement_valid_only':observed,
            'confirmed_matches_over_planned_inventory':matches/planned if planned else None,
            'planned_inventory_ratio_note':'Not a primary acceptance score; excluded cases have no human numeric label.',
            'mean_absolute_score_error_valid_only':sum(abs(r['judge_score']-r['reference_score']) for r in valid)/n if n else None,
            'confusion_reference_rows_judge_columns':matrix,'reference_support_included':support,
            'unweighted_cohen_kappa_valid_only':kappa,'nominal_case_level_wilson_95':wilson(matches,included),
            'interval_note':'Descriptive only; ignores family clustering, curated selection and reference uncertainty.',
            'reference_zero_judge_two_cases':[r['case_id'] for r in valid if r['reference_score']==0 and r['judge_score']==2],
            'families':families}

def audit(snapshot,runner,results,project=None):
    snapshot=Path(snapshot).resolve();runner=Path(runner).resolve();results=Path(results).resolve()
    candidate=read(snapshot/'freeze/review_packet/candidate.json');sdk=candidate['request_configuration']['sdk_version']
    adapter=load('offline_v5_report_runner',runner/'run_descriptive.py')
    context,engine=adapter.load_context(snapshot,project,sdk)
    # Use recorded locked SDK metadata for offline audit, not a new SDK installation.
    cases=read(snapshot/'freeze/review_packet/cases.json')['records'];by_case={c['case_id']:c for c in cases}
    references=read(snapshot/'freeze/human_reviews.json')['records'];by_reference={r['case_id']:r for r in references}
    excluded=[r for r in references if r['status']=='excluded']
    require(results.is_dir(),'Results folder missing.')
    require(not (results/'.execution.lock').exists(),'Unresolved execution lock remains.')
    require(not (results/'MODEL_METADATA_BLOCK.json').exists(),'Model metadata block remains.')
    allowed={'run_binding.json'}|set(context['prompts'])
    require(all(p.name in allowed for p in results.iterdir()),'Unexpected results-root entries.')
    first=engine.request_for(context,sorted(context['prompts'])[0])
    expected={'snapshot_manifest_sha256':context['snapshot_hash'],'candidate_manifest_sha256':context['candidate_hash'],
              'model':context['model'],'sdk_version':context['sdk_version'],'config':context['config'],
              'runner_version':first['runner_version'],'analysis_role':first['analysis_role'],'eligible_for_final_pass':False}
    require(read(results/'run_binding.json')==expected,'Results run binding differs from frozen inputs.')
    rows=[];attempts=[];versions=set();response_count=0
    for cid in sorted(context['prompts']):
        prompt=context['prompts'][cid];inp=json.loads(prompt['messages'][1]['content']);request=engine.request_for(context,cid)
        events=engine.history(results/cid,request,context['expected_versions'],inp)
        last=events[-1] if events else {'status':'missing'};judgment=last.get('judgment');score=judgment['score'] if judgment else None
        numeric=last['status']=='valid';c=by_case[cid];ref=by_reference[cid]
        row={'case_id':cid,'document_family_id':c['document_family_id'],'status':last['status'],'reference_score':ref['score'],
             'reference_rationale':ref['rationale'],'judge_score':score,'judge_rationale':judgment['rationale'] if judgment else None,
             'evidence_response':judgment,'consistency':last.get('consistency'),'attempts':len(events),
             'matches_reference':numeric and score==ref['score'],'question':c['question'],'candidate_answer':c['candidate_answer'],'context':c['context']}
        rows.append(row)
        for index,event in enumerate(events,1):
            start=engine.parse_time(event['started_at_utc']);prefix=f'attempt-{index:03d}';folder=results/cid
            record={'case_id':cid,'attempt':index,'started_at_utc':event['started_at_utc'],'status':event['status'],
                    'http_status':None,'finished_at_utc':None,'returned_model_version':None,'finish_reason':None,'retry_wait_seconds':None}
            if (folder/(prefix+'.response.json')).exists():
                saved=read(folder/(prefix+'.response.json'));finished=engine.parse_time(saved['finished_at_utc']);response=saved['response'];response_count+=1
                record.update(finished_at_utc=saved['finished_at_utc'],returned_model_version=response.get('model_version'),finish_reason=response.get('finish_reason'))
                versions.add(response.get('model_version'))
            elif (folder/(prefix+'.error.json')).exists():
                saved=read(folder/(prefix+'.error.json'));finished=engine.parse_time(saved['finished_at_utc'])
                record.update(finished_at_utc=saved['finished_at_utc'],http_status=saved['http_status'])
            else:finished=None
            require(finished is None or finished>=start,'Attempt finished before it started.')
            if index>1:
                previous=attempts[-1];require(previous['case_id']==cid,'Attempt ordering mismatch.')
                record['retry_wait_seconds']=(start-engine.parse_time(previous['finished_at_utc'])).total_seconds()
            attempts.append(record)
    chronological=sorted(attempts,key=lambda x:x['started_at_utc'])
    gaps=[(engine.parse_time(b['started_at_utc'])-engine.parse_time(a['started_at_utc'])).total_seconds() for a,b in zip(chronological,chronological[1:])]
    require(not gaps or min(gaps)>=context['execution']['minimum_seconds_between_requests'],'Request-start pacing violated.')
    hashes={str(p.relative_to(results)):sha(p.read_bytes()) for p in sorted(results.rglob('*')) if p.is_file()}
    return {'report_version':'citation-v5-descriptive-report-v1','created_at_utc':datetime.now(timezone.utc).isoformat(),
            'analysis_role':'descriptive_evaluation_of_28_reviewed_cases','eligible_for_final_pass':False,'candidate_promoted':False,
            'original_acceptance_attempt':'BLOCKED','exclusions':excluded,'metrics':metrics(rows,len(cases),len(excluded)),
            'operational_audit':{'recorded_sdk_invocations':len(attempts),'saved_responses':response_count,
                'provider_error_attempts':sum(r['status']=='provider_error' for r in attempts),'retry_attempts':sum(r['attempt']>1 for r in attempts),
                'minimum_recorded_start_gap_seconds':min(gaps) if gaps else None,'returned_model_versions':sorted(versions,key=str),
                'all_request_and_response_bindings_verified':True,'retry_backoff_verified':True,'attempts':attempts},
            'request_configuration':candidate['request_configuration'],'actual_runner_version':first['runner_version'],
            'bindings':{'snapshot_freeze_manifest_sha256':sha((snapshot/'freeze_manifest.json').read_bytes()),
                'runner_tool_manifest_sha256':sha((runner/'tool_manifest.json').read_bytes()),'results_file_sha256':hashes},
            'limitations':['Frozen human labels are not independently adjudicated.','One rubric-trained reviewer; not independent human agreement.',
                'Two guidance-related exclusions block the original acceptance attempt.','Case 001 exclusion rationale contains an unreadable control character; preserved unchanged.',
                'Assistant-authored controlled cases, one supplied passage per case; not natural RAG traffic.',
                'USGS source is a generated publication-record conversion, not the full booklet.',
                'Structural validity and internal consistency do not prove semantic correctness.','No labels were changed after judge execution.'],
            'records':rows}

def write_csv(path,fields,rows):
    with Path(path).open('x',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)

def write_report(report,output):
    output=Path(output);require(not output.exists(),'Output exists; nothing overwritten.');output.mkdir(parents=True)
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_csv(output/'case_comparison.csv',['case_id','document_family_id','reference_score','judge_score','status','matches_reference','attempts','question','candidate_answer','reference_rationale','judge_rationale'],report['records'])
    write_csv(output/'attempt_audit.csv',['case_id','attempt','started_at_utc','finished_at_utc','status','http_status','returned_model_version','finish_reason','retry_wait_seconds'],report['operational_audit']['attempts'])
    m=report['metrics'];a=report['operational_audit'];percent=lambda v:'n/a' if v is None else f'{100*v:.1f}%'
    lines=['# V5 citation-support descriptive evaluation','',
        '**Original acceptance: BLOCKED. Candidate not promoted.**','',
        'The original 30-case acceptance attempt was blocked before judge execution because two cases were excluded after requests for guidance. This report describes the remaining 28 reviewed cases. Human references remain unchanged and have not been independently adjudicated.','',
        '| Measure | Result |','|---|---:|',f"| Planned / excluded / included cases | {m['planned_cases']} / {m['excluded_cases']} / {m['included_cases']} |",
        f"| Structurally valid and internally consistent responses | {m['valid_consistent_cases']}/{m['included_cases']} |",f"| Exact agreement with frozen human labels | {m['matches']}/{m['included_cases']} ({percent(m['agreement_over_included'])}) |",
        f"| Numeric disagreements | {m['numeric_disagreements']} |",f"| MAE among valid responses | {m['mean_absolute_score_error_valid_only']} |",f"| Unweighted Cohen kappa, valid responses | {m['unweighted_cohen_kappa_valid_only']} |",'',
        'Agreement is not verified accuracy. A matching human/judge decision can still be wrong; a disagreement is not automatically a judge error. The ratio of confirmed matches to all 30 planned cases is an inventory summary, not a restored acceptance score.','',
        '## Confusion matrix','', 'Rows are frozen human reference scores; columns are judge scores. Excluded cases have no numeric label and are not placed in this matrix.','',
        '| Human reference | Judge 0 | Judge 1 | Judge 2 |','|---|---:|---:|---:|']
    for score,row in enumerate(m['confusion_reference_rows_judge_columns']):lines.append('| '+str(score)+' | '+' | '.join(map(str,row))+' |')
    lines += ['', '## Document families','', '| Family | Included | Valid | Matches |','|---|---:|---:|---:|']
    for f in m['families']:lines.append(f"| {f['document_family_id']} | {f['included']} | {f['valid']} | {f['matches']} |")
    lines += ['', '## Operational audit','',f"Recorded SDK invocations: {a['recorded_sdk_invocations']}. Saved responses: {a['saved_responses']}. Provider-error attempts: {a['provider_error_attempts']}. Retries: {a['retry_attempts']}. Minimum recorded request-start gap: {a['minimum_recorded_start_gap_seconds']} seconds.",'',
        'Requests and response hashes, fixed model/settings, retry eligibility/backoff and pacing were checked offline. SDK invocations are recorded calls, not independently measured network packets. Cached reuses are not new requests.','',
        '## Disagreements with frozen human references','', 'The evidence below is for post-run diagnostic review. It does not replace any human labels.']
    for r in report['records']:
        if r['status']!='valid' or r['matches_reference']:continue
        lines += ['', '### '+r['case_id'],'',f"Human reference: **{r['reference_score']}**; judge: **{r['judge_score']}**.",'','Question: '+r['question'],'','Candidate answer: '+r['candidate_answer'],'','Human rationale: '+r['reference_rationale'],'','Judge rationale: '+r['judge_rationale']]
        for p in r['context']:
            lines += ['',f"Supplied context: {p['passage_id']} | {p['source']} | PDF page {p['page']}",'','```text',p['text'],'```']
    lines += ['', '## Exclusions','', 'FRESH-V5-001 and FRESH-V5-003 remain excluded. Their original records are preserved in the report JSON and frozen snapshot. Case 001 contains a control-character rationale, not a readable explanation.','', '## Limitations','']
    lines.extend('- '+x for x in report['limitations'])
    lines += ['', 'The nominal case-level Wilson interval in report.json is descriptive and ignores document-family clustering, curated sampling and reference uncertainty. No new judge calls were made to produce this report.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    require(read(output/'report.json')==report,'Report round-trip verification failed.')
    hashes={p.name:sha(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}
    (output/'report_manifest.json').write_text(json.dumps({'version':'v5-report-output-manifest-v1','eligible_for_final_pass':False,'files':hashes},indent=2)+'\n',encoding='utf-8')
    for name,expected in hashes.items():require(sha((output/name).read_bytes())==expected,'Written report hash failed.')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project-root',type=Path,default=Path.cwd());parser.add_argument('--snapshot',type=Path);parser.add_argument('--runner',type=Path);parser.add_argument('--results',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    project=args.project_root.resolve();report=audit(args.snapshot or project/'data/citation_v5_descriptive_freeze_v1',args.runner or project/'data/citation_v5_descriptive_runner_v1',args.results or project/'data/citation_v5_descriptive_results_v1',project)
    write_report(report,args.output);m=report['metrics'];print('SAVED AND VERIFIED:',args.output);print('Valid/consistent:',str(m['valid_consistent_cases'])+'/'+str(m['included_cases']));print('Exact agreement:',str(m['matches'])+'/'+str(m['included_cases']),f"{100*m['agreement_over_included']:.1f}%");print('Original acceptance: BLOCKED. No labels changed. No API requests.')

if __name__=='__main__':main()
