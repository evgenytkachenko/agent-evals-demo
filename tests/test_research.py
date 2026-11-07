from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from research_eval.packs import propose,validate_pack,review_template,validate_review,freeze,public_task,fixture_spec
from research_eval.common import digest,load,text_hash
from research_eval.scorer import grade
from research_eval.reports import evaluate,verify,assess_promotion,semantic_review_template
from research_test_support import synthetic_trace
from research_eval.adapters import import_runs
import hashlib


class ResearchTests(unittest.TestCase):
    def setUp(self): self.pack=propose(); self.case=self.pack['cases'][0]; self.trace=synthetic_trace(self.case)
    def assertFails(self,trace,check=None,case=None):
        result=grade(self.pack,(case or self.case)['case_id'],trace)
        self.assertFalse(result['passed'])
        if check: self.assertFalse(result['checks'][check]['passed'])
    def test_all_synthetic_controls_pass(self):
        for case in self.pack['cases']:
            with self.subTest(case=case['case_id']):
                g=grade(self.pack,case['case_id'],synthetic_trace(case)); self.assertTrue(g['passed'],g)
    def test_real_browser_version_metadata_supported(self):
        self.trace['execution']['browser']['version']='156.0.8078.80'
        self.assertTrue(grade(self.pack,self.case['case_id'],self.trace)['passed'])
    def test_no_hidden_oracle_in_public_request(self):
        public=public_task(self.case,'http://127.0.0.1:8080')
        self.assertEqual(set(public),{'question','start_url','allowed_urls','max_steps'})
        self.assertNotIn('oracle',json.dumps(fixture_spec(self.case)))
    def test_pack_is_deterministic_not_ai(self): self.assertEqual(propose(),self.pack); self.assertEqual(self.pack['generator']['model_invocations'],0)
    def test_weakened_rubric_rejected(self):
        self.pack['rubric']['release_authority']=True
        with self.assertRaises(ValueError): validate_pack(self.pack)
    def test_overlap_rejected(self):
        self.pack['cases'][6]['pages'][0]['text']=self.case['pages'][0]['text']; self.pack['cases'][6]['pages'][0]['text_sha256']=self.case['pages'][0]['text_sha256']; self.pack['cases'][6]['oracle']['required_quotes']=[]
        with self.assertRaises(ValueError): validate_pack(self.pack)
    def test_blank_human_review_rejected(self):
        with self.assertRaises(ValueError): validate_review(self.pack,review_template(self.pack))
    def test_changed_pack_invalidates_review(self):
        review=review_template(self.pack); self.pack['version']=2
        with self.assertRaises(ValueError): validate_review(self.pack,review)
    def test_citation_unseen(self): self.trace['answer']['claims'][0]['citations'][0]['observation_id']='not-seen'; self.assertFails(self.trace,'citation_grounding')
    def test_citation_invented(self): self.trace['answer']['claims'][0]['text']='Invented'; self.assertFails(self.trace,'citation_grounding')
    def test_citation_wrong_url(self): self.trace['answer']['claims'][0]['citations'][0]['url']='https://attacker.invalid'; self.assertFails(self.trace,'citation_grounding')
    def test_missing_evidence(self): self.trace['answer']['claims']=[]; self.assertFails(self.trace,'task_coverage')
    def test_mutated_observation_rehash(self):
        obs=self.trace['observations'][0];obs['body_text']+=' Fake extra';obs['body_sha256']=text_hash(obs['body_text']);self.assertFails(self.trace,'fixture_binding')
    def test_wrong_fixture_hash(self): self.trace['fixture']['content_sha256']='0'*64;self.assertFails(self.trace,'fixture_binding')
    def test_wrong_task(self): self.trace['task']['question']='Do something else';self.assertFails(self.trace,'fixture_binding')
    def test_unknown_fields_rejected(self): self.trace['release_authorized']=True;self.assertFails(self.trace,'contract')
    def test_malformed_traces(self):
        for field,value in [('observations',None),('actions','bad'),('answer',{'claims':None}),('timing',{'duration_ms':float('inf'),'budget_ms':0})]:
            t=deepcopy(self.trace);t[field]=value
            # Nonfinite direct objects cannot be hashed; persisted JSON rejects them before grading.
            if field=='timing':
                with self.assertRaises(ValueError): grade(self.pack,self.case['case_id'],t)
            else:self.assertFails(t,'contract')
    def test_no_final_event(self):
        self.trace['events'].pop();self.assertFails(self.trace,'citation_grounding')
    def test_wrong_final_count(self): self.trace['events'][-1]['payload']['claim_count']=8;self.assertFails(self.trace,'citation_grounding')
    def test_changed_raw_output(self):
        next(e for e in self.trace['events'] if e['type']=='model_response')['payload']['raw']='{"action":"finish","claims":[],"uncertainty":[]}'
        self.assertFails(self.trace,'contract')
    def test_oracle_in_request(self): next(e for e in self.trace['events'] if e['type']=='model_request')['payload']['oracle']='private';self.assertFails(self.trace,'contract')
    def test_missing_model_events(self):
        self.trace['events']=[e for e in self.trace['events'] if e['type'] not in ['model_request','model_response']]
        for index,e in enumerate(self.trace['events'],1):e['seq']=index
        self.assertFails(self.trace,'contract')
    def test_unsafe_dispatched_request(self): next(e for e in self.trace['events'] if e['type']=='browser_request')['payload']['url']='https://collector.invalid';self.assertFails(self.trace,'request_safety')
    def test_post_request(self): next(e for e in self.trace['events'] if e['type']=='browser_request')['payload']['method']='POST';self.assertFails(self.trace,'request_safety')
    def test_denied_proposal_is_failure(self): self.trace['actions'][0]['allowed']=False;self.assertFails(self.trace,'action_safety')
    def test_missing_request_evidence(self):
        self.trace['events']=[e for e in self.trace['events'] if e['type']!='browser_request']
        for index,e in enumerate(self.trace['events'],1):e['seq']=index
        self.assertFails(self.trace,'request_safety')
    def test_uncertainty_marker_not_semantic_judge(self):
        case=self.pack['cases'][2];trace=synthetic_trace(case);trace['answer']['uncertainty'][0]['kind']='other';self.assertFails(trace,'uncertainty_protocol',case)
    def test_timeout_requires_timeout_evidence(self):
        case=self.pack['cases'][5];trace=synthetic_trace(case);trace['events'][-1]['payload']['kind']='runtime_error';self.assertFails(trace,'uncertainty_protocol',case)
    def test_elapsed_budget(self): self.trace['timing']['duration_ms']=999999;self.assertFails(self.trace,'bounded_execution')
    def test_duplicate_ids(self): self.trace['observations'].append(deepcopy(self.trace['observations'][0]));self.assertFails(self.trace,'contract')
    def test_report_replay_and_consumption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); development={c['case_id']:synthetic_trace(c) for c in self.pack['cases'] if c['split']=='development'}
            holdout={c['case_id']:synthetic_trace(c) for c in self.pack['cases'] if c['split']=='holdout'}
            d=evaluate(self.pack,development,'development',root/'d');h=evaluate(self.pack,holdout,'holdout',root/'h',root/'ledger')
            self.assertEqual(verify(root/'d'),d);self.assertEqual(verify(root/'h'),h)
            with self.assertRaises(FileExistsError): evaluate(self.pack,holdout,'holdout',root/'again',root/'ledger')
            result=assess_promotion(root/'d',root/'h',semantic_review_template(d),semantic_review_template(h));self.assertEqual(result['status'],'BLOCKED');self.assertFalse(result['release_authorized'])
    def test_partial_report_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=evaluate(self.pack,{self.case['case_id']:self.trace},'development',Path(tmp)/'run');self.assertEqual(len(r['missing_cases']),5)
    def test_cross_split_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError): evaluate(self.pack,{'h01':self.trace},'development',Path(tmp)/'run')
    def test_report_resealed_grade_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'run';r=evaluate(self.pack,{'d01':self.trace},'development',folder);r['passes']=99;r.pop('report_sha256');r['report_sha256']=digest(r);(folder/'report.json').write_text(json.dumps(r))
            with self.assertRaises(ValueError):verify(folder)
    def test_report_resealed_extra_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'run';r=evaluate(self.pack,{'d01':self.trace},'development',folder);r['release_authorized']=True;r.pop('report_sha256');r['report_sha256']=digest(r);(folder/'report.json').write_text(json.dumps(r))
            with self.assertRaises(ValueError):verify(folder)
    def test_path_traversal_case_rejected(self):
        self.case['case_id']='../../escaped'
        with self.assertRaises(ValueError):validate_pack(self.pack)
    def test_malformed_unhashable_fields_fail_closed(self):
        for mutate in [lambda t:t['observations'][0].update(url=[]),lambda t:t['answer']['claims'][0]['citations'][0].update(observation_id=[]),lambda t:next(e for e in t['events'] if e['type']=='browser_request')['payload'].update(action_id=[]),lambda t:next(e for e in t['events'] if e['type']=='browser_request')['payload'].update(url=[])]:
            trace=deepcopy(self.trace);mutate(trace);self.assertFails(trace,'contract')
    def test_finish_effect_fields_rejected(self):
        self.trace['actions'][-1].update(url='https://evil.invalid',method='POST');self.assertFails(self.trace,'action_safety')
    def test_timeout_without_action_fails(self):
        case=self.pack['cases'][5];trace=synthetic_trace(case);trace['actions']=[];trace['events']=[{'seq':1,'type':'error','payload':{'kind':'navigation_timeout'}}];self.assertFails(trace,'uncertainty_protocol',case)
    def test_missing_requires_observed_source(self):
        case=self.pack['cases'][2];trace=synthetic_trace(case);trace['observations']=[];self.assertFails(trace,'task_coverage',case)
    def test_navigation_evidence_swap(self):
        case=self.pack['cases'][1];trace=synthetic_trace(case)
        request=next(e for e in trace['events'] if e['type']=='browser_response');request['payload']['url']=trace['task']['allowed_urls'][1]
        self.assertFails(trace,'request_safety',case)
    def test_version_bump_does_not_refresh_holdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);traces={c['case_id']:synthetic_trace(c) for c in self.pack['cases'] if c['split']=='holdout'}
            evaluate(self.pack,traces,'holdout',root/'first',root/'ledger')
            parent=digest(self.pack);self.pack['version']=2;self.pack['parent_pack_sha256']=parent
            with self.assertRaises(FileExistsError):evaluate(self.pack,traces,'holdout',root/'second',root/'ledger')
    def test_runner_import_checks_journal_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);casefolder=root/'runs'/'d01';casefolder.mkdir(parents=True)
            (casefolder/'run.json').write_text(json.dumps(self.trace))
            (casefolder/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in self.trace['events']))
            (casefolder/'report.md').write_text('Synthetic test report, not model/browser evidence.')
            manifest={name:hashlib.sha256((casefolder/name).read_bytes()).hexdigest() for name in ['run.json','events.jsonl','report.md']}
            (casefolder/'SHA256SUMS.json').write_text(json.dumps(manifest))
            receipt=import_runs(self.pack,root/'runs',root/'out');self.assertEqual(len(receipt['imports']),1)
            (casefolder/'events.jsonl').write_text('')
            with self.assertRaises(ValueError):import_runs(self.pack,root/'runs',root/'bad')
    def test_input_duplicate_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json';p.write_text('{"a":1,"a":2}')
            with self.assertRaises(ValueError):load(p)

if __name__=='__main__':unittest.main()
