"""Synthetic traces for checker tests only. No model or browser execution."""
from copy import deepcopy
import json
from research_eval.common import digest
from research_eval.packs import fixture_spec,public_task


def synthetic_trace(case):
    base='http://127.0.0.1:18080'; task=public_task(case,base)
    trace={'schema_version':'browser-research-run/1','run_id':'synthetic-'+case['case_id'],'scenario_id':case['case_id'],'agent':{'id':'synthetic-checker-control','version':'1'},'execution':{'mode':'scripted_test','model':{'provider':'test-double','model_id':'scripted-synthetic','real_model':False},'browser':{'engine':'test-double','real_browser':False},'policy':{'allowed_urls':task['allowed_urls'],'max_steps':task['max_steps'],'navigation_timeout_ms':case['budgets']['navigation_timeout_ms'],'run_timeout_ms':case['budgets']['duration_ms']}},'status':case['oracle']['expected_status'],'stop_reason':'Synthetic checker fixture only','task':task,'fixture':{'id':case['case_id'],'content_sha256':digest(fixture_spec(case)['pages']),'allowed_origins':[base],'allowed_methods':['GET']},'observations':[],'actions':[],'answer':None,'timing':{'duration_ms':500,'budget_ms':case['budgets']['duration_ms']},'events':[]}
    decisions=[]
    def emit(kind,payload):
        trace['events'].append({'seq':len(trace['events'])+1,'type':kind,'payload':deepcopy(payload)})
    def act(requested):
        emit('model_request',{'trusted_task':task,'untrusted_observations':trace['observations'],'prior_gateway_decisions':decisions,'steps_remaining':task['max_steps']-len(trace['actions'])})
        emit('model_response',{'raw':json.dumps(requested)})
        aid='action-'+str(len(trace['actions'])+1)
        row={'action_id':aid,'type':requested['action'],'url':requested.get('url'),'method':'GET' if requested['action']=='navigate' else None,'allowed':True,'performed':False,'reason':'Accepted by closed action contract','requested':requested}
        trace['actions'].append(row); emit('action_proposed',{'action_id':aid,'requested':requested})
        decision={'action_id':aid,'allowed':True,'reason':row['reason']}; emit('gateway_decision',decision); decisions.append(decision)
        return row
    for page in case['pages']:
        url=base+page['path']; row=act({'action':'navigate','url':url}); aid=row['action_id']
        emit('browser_request',{'action_id':aid,'url':url,'method':'GET','resource_type':'document','allowed':True,'reason':'Allowed fixture navigation'})
        if case['family']=='timeout':
            emit('error',{'kind':'navigation_timeout','message':'Synthetic timeout','action_id':aid}); return trace
        emit('browser_response',{'action_id':aid,'url':url,'status_code':200})
        obs={'observation_id':'obs-'+str(len(trace['observations'])+1),'url':url,'final_url':url,'status_code':200,'title':'Archive guide','body_text':page['text'],'body_sha256':page['text_sha256'],'observed_at':'2026-11-07T12:00:00+00:00','links':[],'truncated':False}
        trace['observations'].append(obs); row['performed']=True
        emit('observation',{'action_id':aid,'observation_id':obs['observation_id'],'body_sha256':obs['body_sha256']})
    requests=[]; normalized=[]
    for index,quote in enumerate(case['oracle']['required_quotes'],1):
        obs=next(o for o in trace['observations'] if o['url']==base+quote['path'])
        requests.append({'observation_id':obs['observation_id'],'quote':quote['quote']})
        normalized.append({'claim_id':'claim-'+str(index),'text':quote['quote'],'citations':[{'observation_id':obs['observation_id'],'url':obs['url'],'quote':quote['quote']}]})
    uncertainty=[{'kind':kind,'detail':'Synthetic expected declaration, semantic prose ungraded.'} for kind in case['oracle']['uncertainty_kinds']]
    row=act({'action':'finish','claims':requests,'uncertainty':uncertainty}); row['performed']=True
    trace['answer']={'claims':normalized,'uncertainty':uncertainty}
    emit('final_validation',{'action_id':row['action_id'],'accepted':True,'claim_count':len(normalized)})
    return trace
