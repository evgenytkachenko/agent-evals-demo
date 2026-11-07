"""Immutable-by-convention report exports, replay verification and review gate."""
from datetime import datetime, timezone
from pathlib import Path
from .common import digest, load, write_new, exact, bounded_text, text_hash
from .packs import validate_pack, validate_review
from .scorer import grade


def cohort_identity(pack):
    return digest([{'task':c['task'],'pages':c['pages']} for c in pack['cases'] if c['split']=='holdout'])


def source_identity():
    return {p.name:text_hash(p.read_text(encoding='utf-8')) for p in sorted(Path(__file__).parent.glob('*.py'))}


def evaluate(pack,traces,split,out,ledger=None,review=None):
    validate_pack(pack)
    if split not in ['development','holdout']: raise ValueError('Unknown split')
    if not isinstance(traces,dict): raise ValueError('Traces must map case id to trace')
    selected={c['case_id'] for c in pack['cases'] if c['split']==split}
    if not selected or not set(traces)<=selected: raise ValueError('Unknown or cross-split trace')
    if review is not None: validate_review(pack,review)
    grades=[grade(pack,cid,traces[cid]) for cid in sorted(traces)]
    out=Path(out)
    if out.exists(): raise ValueError('Output already exists; reports cannot be overwritten')
    # Every attempted evaluation consumes the exposed reserved cohort, including
    # partial and failing evaluations. This local file is not a secure registry.
    consumption=None
    if split=='holdout':
        if ledger is None: raise ValueError('Holdout evaluation requires a consumption ledger directory')
        ledger=Path(ledger); ledger.mkdir(parents=True,exist_ok=True)
        consumption={'schema_version':'holdout-consumption/1','pack_sha256':digest(pack),'split':split,'cohort_sha256':cohort_identity(pack),'consumed_at':datetime.now(timezone.utc).isoformat(),'trace_hashes':{k:digest(v) for k,v in traces.items()},'freshness_claim':False}
        write_new(ledger/(cohort_identity(pack)+'.json'),consumption)
    out.mkdir(parents=True,exist_ok=False)
    report={'schema_version':'research-evaluation-report/1','pack_sha256':digest(pack),'split':split,
        'mode':'HUMAN_REVIEWED' if review else 'UNREVIEWED_PREVIEW','review_sha256':digest(review) if review else None,
        'source_identity':source_identity(),'case_count':len(selected),'attempt_count':len(grades),
        'missing_cases':sorted(selected-set(traces)), 'passes':sum(g['passed'] for g in grades),'failures':sum(not g['passed'] for g in grades),
        'grades':grades,'trace_hashes':{k:digest(traces[k]) for k in sorted(traces)},
        'execution_summary':{cid:traces[cid].get('execution') for cid in sorted(traces)},
        'agent_summary':{cid:traces[cid].get('agent') for cid in sorted(traces)},
        'holdout_consumption':consumption, 'semantic_review_required':True,
        'scope':'Exposed deterministic controlled fixtures; not general browser-agent reliability.',
        'release_decision':'NOT_A_RELEASE_DECISION'}
    report['report_sha256']=digest(report)
    write_new(out/'pack.json',pack)
    if review: write_new(out/'review.json',review)
    for cid,trace in traces.items(): write_new(out/'traces'/(cid+'.json'),trace)
    write_new(out/'report.json',report)
    write_new(out/'human-semantic-review.json',semantic_review_template(report))
    return report


def verify(folder):
    folder=Path(folder); report=load(folder/'report.json'); pack=validate_pack(load(folder/'pack.json'))
    exact(report,['schema_version','pack_sha256','split','mode','review_sha256','source_identity','case_count','attempt_count','missing_cases','passes','failures','grades','trace_hashes','execution_summary','agent_summary','holdout_consumption','semantic_review_required','scope','release_decision','report_sha256'],'report')
    if report['schema_version']!='research-evaluation-report/1': raise ValueError('Unsupported report schema')
    raw=dict(report); recorded_hash=raw.pop('report_sha256')
    if digest(raw)!=recorded_hash or report['pack_sha256']!=digest(pack) or report['source_identity']!=source_identity(): raise ValueError('Report/pack/evaluator identity mismatch')
    traces={p.stem:load(p) for p in sorted((folder/'traces').glob('*.json'))} if (folder/'traces').exists() else {}
    expected={c['case_id'] for c in pack['cases'] if c['split']==report['split']}
    if report['split'] not in ['development','holdout'] or not set(traces)<=expected: raise ValueError('Invalid report split')
    if report['mode']=='HUMAN_REVIEWED':
        review=validate_review(pack,load(folder/'review.json'))
        if report['review_sha256']!=digest(review): raise ValueError('Review mismatch')
    elif report['mode']!='UNREVIEWED_PREVIEW' or report['review_sha256'] is not None: raise ValueError('Invalid review mode')
    grades=[grade(pack,cid,traces[cid]) for cid in sorted(traces)]
    required={'grades':grades,'trace_hashes':{k:digest(v) for k,v in sorted(traces.items())},'case_count':len(expected),'attempt_count':len(grades),'missing_cases':sorted(expected-set(traces)),'passes':sum(g['passed'] for g in grades),'failures':sum(not g['passed'] for g in grades),'execution_summary':{cid:traces[cid].get('execution') for cid in sorted(traces)},
        'agent_summary':{cid:traces[cid].get('agent') for cid in sorted(traces)},'semantic_review_required':True,'scope':'Exposed deterministic controlled fixtures; not general browser-agent reliability.','release_decision':'NOT_A_RELEASE_DECISION'}
    for key,value in required.items():
        if report[key]!=value: raise ValueError('Recomputed '+key+' differs')
    consumption=report['holdout_consumption']
    if report['split']=='holdout':
        exact(consumption,['schema_version','pack_sha256','split','cohort_sha256','consumed_at','trace_hashes','freshness_claim'],'consumption receipt')
        if consumption['schema_version']!='holdout-consumption/1' or consumption['split']!='holdout' or consumption['cohort_sha256']!=cohort_identity(pack) or datetime.fromisoformat(consumption['consumed_at']).tzinfo is None: raise ValueError('Invalid consumption receipt')
        if not isinstance(consumption,dict) or consumption.get('pack_sha256')!=digest(pack) or consumption.get('trace_hashes')!=report['trace_hashes'] or consumption.get('freshness_claim') is not False: raise ValueError('Holdout consumption mismatch')
    elif consumption is not None: raise ValueError('Unexpected holdout consumption')
    return report


def semantic_review_template(report):
    return {'schema_version':'research-semantic-review/1','report_sha256':report['report_sha256'],'reviewer':'','reviewed_at':'','human_attestation':False,'decision':'unreviewed','rationale':'','case_decisions':[{'case_id':g['case_id'],'decision':'unreviewed','notes':''} for g in report['grades']]}


def validate_semantic_review(report,review):
    exact(review,['schema_version','report_sha256','reviewer','reviewed_at','human_attestation','decision','rationale','case_decisions'],'semantic review')
    if review['schema_version']!='research-semantic-review/1' or review['report_sha256']!=report['report_sha256'] or review['human_attestation'] is not True or review['decision']!='approved': raise ValueError('Exact report requires human semantic review')
    for key in ['reviewer','reviewed_at','rationale']: bounded_text(review[key],key)
    if len(review['rationale'])<20 or datetime.fromisoformat(review['reviewed_at']).tzinfo is None: raise ValueError('Substantive dated review required')
    rows=review['case_decisions']; seen=set()
    if not isinstance(rows,list) or len(rows)!=report['case_count']: raise ValueError('All cases need semantic review')
    for row in rows:
        exact(row,['case_id','decision','notes'],'case semantic review')
        if row['decision']!='approved' or row['case_id'] in seen: raise ValueError('Unapproved or duplicate semantic review')
        bounded_text(row['notes'],'semantic notes'); seen.add(row['case_id'])
    if seen!={g['case_id'] for g in report['grades']}: raise ValueError('Missing semantic review')


def assess_promotion(development_folder,holdout_folder,development_review,holdout_review):
    """Never promotes itself or changes the historic NO_GO."""
    development=verify(development_folder); holdout=verify(holdout_folder)
    reasons=[]
    promotion_pack=load(Path(development_folder)/'pack.json')
    families={'direct','follow_link','missing','conflict','injection','timeout'}
    for split in ['development','holdout']:
        if {c['family'] for c in promotion_pack['cases'] if c['split']==split}!=families: reasons.append('Required scenario families absent: '+split)
    if development['split']!='development' or holdout['split']!='holdout' or development['pack_sha256']!=holdout['pack_sha256']: reasons.append('Both matching development and holdout reports required')
    identities=[]
    for report,review in [(development,development_review),(holdout,holdout_review)]:
        if report['mode']!='HUMAN_REVIEWED': reasons.append('Pack review missing: '+report['split'])
        if report['missing_cases'] or report['failures'] or report['passes']!=report['case_count']: reasons.append('Full passing cohort required: '+report['split'])
        try: validate_semantic_review(report,review)
        except (ValueError,TypeError,KeyError) as exc: reasons.append(str(exc))
        for cid,execution in report['execution_summary'].items():
            if not execution or execution['mode']!='model' or not execution['model']['real_model'] or not execution['browser']['real_browser']: reasons.append('Real model and real browser evidence required')
            if execution: identities.append(digest({'agent':report['agent_summary'][cid],'model':execution['model'],'browser':execution['browser']}))
    if len(set(identities))!=1: reasons.append('One consistent evaluated model/browser configuration required')
    return {'schema_version':'research-promotion-assessment/1','status':'BLOCKED' if reasons else 'ELIGIBLE_FOR_HUMAN_DECISION','blockers':sorted(set(reasons)),'release_authorized':False,'historical_release_decision':'NO_GO_UNCHANGED','fresh_holdout_claim':False,'execution_attested':False,'note':'Review assertions and trace provenance are not authenticated. A human must decide any further controlled evaluation; this is never production approval.'}
