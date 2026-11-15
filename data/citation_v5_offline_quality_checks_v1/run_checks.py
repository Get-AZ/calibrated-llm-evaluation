"""Offline integrity checks and a separate protocol-based promotion gate."""
import argparse,hashlib,importlib.util,json
from datetime import datetime,timezone
from pathlib import Path

def require(ok,message):
    if not ok:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(Path(path).read_bytes())

def assess(report,protocol):
    m=report['metrics'];a=report['operational_audit'];rows=report['records'];g=protocol['acceptance_gates']
    integrity=[];blocks=[]
    if len(rows)!=m['included_cases']:integrity.append('Included record count differs from reported count.')
    if len({r['case_id'] for r in rows})!=len(rows):integrity.append('Duplicate case records.')
    if any(r['status']!='valid' for r in rows):integrity.append('A retained included response is not valid and internally consistent.')
    for row in rows:
        if type(row['reference_score']) is not int or row['reference_score'] not in (0,1,2):integrity.append('Invalid reference score.')
        if row['status']=='valid' and (type(row['judge_score']) is not int or row['judge_score'] not in (0,1,2)):integrity.append('Invalid judge score.')
    matches=sum(r['status']=='valid' and r['judge_score']==r['reference_score'] for r in rows)
    if matches!=m['matches']:integrity.append('Agreement does not match unchanged reference records.')
    if m['valid_consistent_cases']!=sum(r['status']=='valid' for r in rows):integrity.append('Valid-response count mismatch.')
    if a.get('all_request_and_response_bindings_verified') is not True:integrity.append('Request/response bindings were not verified.')
    if a.get('retry_backoff_verified') is not True:integrity.append('Retry backoff was not verified.')
    gap=a.get('minimum_recorded_start_gap_seconds')
    if gap is not None and gap<protocol['execution']['minimum_seconds_between_requests']:integrity.append('Request pacing is below the registered minimum.')
    if report.get('original_acceptance_attempt')!='BLOCKED':
        # This checker is scoped to the currently frozen, blocked descriptive run.
        integrity.append('Unexpected original acceptance status for this fixed run.')
    if report.get('eligible_for_final_pass') is not False or report.get('candidate_promoted') is not False:integrity.append('Descriptive report improperly claims promotion eligibility.')
    if report.get('original_acceptance_attempt')=='BLOCKED':blocks.append('Original registered acceptance attempt is BLOCKED.')
    if report.get('analysis_role')!='primary_acceptance':blocks.append('Run is descriptive, not the registered primary acceptance run.')
    if m['included_cases']!=g['primary_denominator']:blocks.append('Not all 30 primary cases have eligible numeric references.')
    if report.get('exclusions'):blocks.append('Preserved primary-case exclusions remain.')
    if m['valid_consistent_cases']<g['required_structurally_valid_and_consistent_cases']:blocks.append('Required primary valid/consistent count is not met.')
    if matches<g['minimum_exact_matches_all_primary_cases']:blocks.append('Original-reference exact-match threshold is not met.')
    if len(m['reference_zero_judge_two_cases'])>g['maximum_reference_zero_judge_two_cases']:blocks.append('Frozen-reference-0 / judge-2 count exceeds the registered limit; this is not an independently verified error label.')
    if any(m['reference_support_included'].get(str(k),0)<g['minimum_reference_cases_each_score'] for k in (0,1,2)):blocks.append('Reference score-class coverage is insufficient.')
    if integrity:blocks.append('Offline integrity checks failed.')
    return {'integrity_status':'PASS' if not integrity else 'FAIL','integrity_errors':integrity,
            'promotion_status':'BLOCKED' if blocks else 'PASS','promotion_block_reasons':blocks,
            'candidate_promoted':False,'reference_semantics_independently_verified':False,
            'original_matches':matches,'included_cases':len(rows),
            'note':'An integrity PASS is not a model-quality pass. This tool never changes labels or promotes a candidate.'}

def verify_postrun(project,report):
    project=Path(project);comparison=project/'data/citation_v5_postrun_comparison_v2.json';folder=project/'data/citation_v5_postrun_amendments_v1'
    if not comparison.exists() and not folder.exists():return {'status':'not_present','used_for_promotion':False}
    require(comparison.exists() and folder.is_dir(),'Incomplete post-run amendment/comparison files.')
    original_path=project/'data/citation_v5_descriptive_report_local_v1/report.json';raw=original_path.read_bytes();saved=json.loads(raw)
    require(saved['records']==report['records'] and saved['metrics']==report['metrics'],'Local original report differs from audited raw results.')
    v=read(comparison);require(v['original_report_sha256']==sha(raw),'Post-run comparison source hash differs.')
    require(v['eligible_for_final_pass'] is False and v['independent_review'] is False,'Post-run comparison improperly claims final eligibility or independence.')
    original={r['case_id']:r for r in report['records']};updates={}
    require(len(v['amendment_file_sha256'])==10,'Expected the ten recorded post-run amendments.')
    for name,expected in v['amendment_file_sha256'].items():
        p=Path(name);require(p.name==name and not p.is_absolute(),'Unsafe amendment filename.')
        data=(folder/p).read_bytes();require(sha(data)==expected,'Amendment changed: '+name);a=json.loads(data);cid=a['case_id']
        require(cid in original and cid not in updates,'Unknown or duplicate amendment case.')
        require(a['report_sha256']==sha(raw),'Amendment report binding differs.')
        require(a['original_score']==original[cid]['reference_score'] and a['original_rationale']==original[cid]['reference_rationale'],'Amendment original reference differs.')
        require(type(a['self_review_score']) is int and a['self_review_score'] in (0,1,2),'Invalid post-run score.')
        require(a['eligible_for_final_pass'] is False and a['independent_review'] is False and a['review_type']=='guided_post_run_self_review','Unexpected post-run review status.')
        updates[cid]=a
    require('FRESH-V5-028' in updates and 'rubric_interpretation_disputed' in updates['FRESH-V5-028'].get('flags',[]),'Case 028 dispute flag missing.')
    expected_rows={}
    for cid,row in original.items():
        revised=updates[cid]['self_review_score'] if cid in updates else row['reference_score']
        expected_rows[cid]=(revised,row['status']=='valid' and row['judge_score']==revised)
    require(len(v['records'])==28 and len({r['case_id'] for r in v['records']})==28,'Post-run case inventory differs.')
    for row in v['records']:
        cid=row['case_id'];require(cid in original,'Unknown post-run case.')
        require((row['exploratory_reference'],row['exploratory_match'])==expected_rows[cid],'Post-run comparison differs from amendment records.')
        require(row['original_reference']==original[cid]['reference_score'] and row['judge_score']==original[cid]['judge_score'],'Original score was changed in exploratory comparison.')
    revised_matches=sum(match for score,match in expected_rows.values())
    require(v['original_matches']==report['metrics']['matches'] and v['exploratory_matches']==revised_matches,'Post-run match counts differ.')
    require('FRESH-V5-028' in v['unresolved_rubric_review_cases'],'Unresolved case 028 omitted.')
    return {'status':'VERIFIED_EXPLORATORY_ONLY','amendments':len(updates),'exploratory_matches':revised_matches,
            'unresolved_case_ids':['FRESH-V5-028'],'used_for_promotion':False}

def run(project):
    project=Path(project).resolve();here=Path(__file__).resolve().parent;policy=read(here/'policy.json')
    manifest=read(here/'tool_manifest.json')
    for name,b in manifest['files'].items():
        p=Path(name);require(not p.is_absolute() and '..' not in p.parts,'Unsafe tool filename.')
        raw=(here/p).read_bytes();require(sha(raw)==b['sha256'] and len(raw)==b['bytes'],'Quality-check tool changed: '+name)
    for relative,expected in policy['auditor_bindings'].items():require(sha((project/relative).read_bytes())==expected,'Auditor file changed: '+relative)
    p=project/'data/citation_v5_descriptive_report_v1/tools/report_v5.py'
    spec=importlib.util.spec_from_file_location('offline_quality_auditor',p);require(spec is not None and spec.loader is not None,'Auditor unavailable.')
    auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)
    report=auditor.audit(project/'data/citation_v5_descriptive_freeze_v1',project/'data/citation_v5_descriptive_runner_v1',project/'data/citation_v5_descriptive_results_v1',project)
    protocol=read(project/'data/citation_v5_descriptive_freeze_v1/freeze/review_packet/protocol.json')
    require(sha((project/'data/citation_v5_descriptive_freeze_v1/freeze/review_packet/protocol.json').read_bytes())==policy['protocol_sha256'],'Registered protocol differs.')
    result=assess(report,protocol);result['postrun_comparison']=verify_postrun(project,report)
    result['created_at_utc']=datetime.now(timezone.utc).isoformat();result['analysis_role']=report['analysis_role'];result['api_requests_made']=False
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project-root',type=Path,default=Path.cwd());parser.add_argument('--mode',choices=['integrity','promotion'],default='integrity');parser.add_argument('--output',type=Path);args=parser.parse_args()
    result=run(args.project_root)
    if args.output:
        with args.output.open('x',encoding='utf-8') as handle:json.dump(result,handle,ensure_ascii=False,indent=2);handle.write('\n')
    print('Offline integrity:',result['integrity_status']);print('Promotion gate:',result['promotion_status']);print('Original agreement:',str(result['original_matches'])+'/'+str(result['included_cases']))
    print('Post-run amendments:',result['postrun_comparison']['status'])
    for reason in result['promotion_block_reasons']:print('BLOCK:',reason)
    print('No labels changed. No API requests. No candidate promoted.')
    if result['integrity_status']!='PASS':raise SystemExit(1)
    if args.mode=='promotion' and result['promotion_status']!='PASS':raise SystemExit(2)

if __name__=='__main__':main()
