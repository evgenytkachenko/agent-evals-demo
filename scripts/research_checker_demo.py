"""Generate explicit synthetic checker controls, not agent performance evidence."""
import argparse
from copy import deepcopy
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from research_eval.packs import propose,review_template
from research_eval.common import write_new
from research_eval.reports import evaluate,verify,semantic_review_template,assess_promotion
from research_test_support import synthetic_trace


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args();out=Path(args.out)
    if out.exists():raise SystemExit('Output already exists')
    pack=propose();out.mkdir(parents=True)
    write_new(out/'pack.json',pack);write_new(out/'blank-pack-review.json',review_template(pack))
    summary={'mode':'SYNTHETIC_CHECKER_CONTROLS','model_calls':0,'browser_calls':0,'real_agent_performance':False,'reports':{}}
    for split in ['development','holdout']:
        traces={c['case_id']:synthetic_trace(c) for c in pack['cases'] if c['split']==split}
        report=evaluate(pack,traces,split,out/split,out/'holdout-consumption' if split=='holdout' else None)
        verify(out/split);summary['reports'][split]={'passes':report['passes'],'failures':report['failures']}
    bad={c['case_id']:synthetic_trace(c) for c in pack['cases'] if c['split']=='development'}
    for trace in bad.values():trace['fixture']['content_sha256']='0'*64
    report=evaluate(pack,bad,'development',out/'tampered-controls');verify(out/'tampered-controls')
    summary['reports']['tampered-controls']={'passes':report['passes'],'failures':report['failures']}
    summary['promotion']=assess_promotion(out/'development',out/'holdout',__import__('json').loads((out/'development'/'human-semantic-review.json').read_text()),__import__('json').loads((out/'holdout'/'human-semantic-review.json').read_text()))
    write_new(out/'summary.json',summary)
    print(__import__('json').dumps(summary,indent=2))
if __name__=='__main__':main()
