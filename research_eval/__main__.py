import argparse
import json
from pathlib import Path
from .common import load,write_new,digest
from .packs import propose,review_template,validate_pack,freeze,fixture_spec
from .scorer import grade
from .reports import evaluate,verify,assess_promotion
from .adapters import import_runs


def main():
    parser=argparse.ArgumentParser(description='Controlled research evaluation, no semantic AI judge or release GO.')
    commands=parser.add_subparsers(dest='cmd',required=True)
    p=commands.add_parser('propose'); p.add_argument('--out',required=True); p.add_argument('--parent-pack')
    p=commands.add_parser('import-runs'); p.add_argument('--pack',required=True); p.add_argument('--runs',required=True); p.add_argument('--out',required=True)
    p=commands.add_parser('validate'); p.add_argument('--pack',required=True)
    p=commands.add_parser('freeze'); p.add_argument('--pack',required=True); p.add_argument('--review',required=True); p.add_argument('--out',required=True)
    p=commands.add_parser('grade'); p.add_argument('--pack',required=True); p.add_argument('--case',required=True); p.add_argument('--trace',required=True); p.add_argument('--out',required=True)
    p=commands.add_parser('evaluate'); p.add_argument('--pack',required=True); p.add_argument('--traces',required=True); p.add_argument('--split',choices=['development','holdout'],required=True); p.add_argument('--out',required=True); p.add_argument('--ledger'); p.add_argument('--review')
    p=commands.add_parser('verify'); p.add_argument('--run',required=True)
    p=commands.add_parser('assess-promotion'); p.add_argument('--development',required=True); p.add_argument('--holdout',required=True); p.add_argument('--development-review',required=True); p.add_argument('--holdout-review',required=True)
    args=parser.parse_args()
    try:
        if args.cmd=='propose':
            target=Path(args.out); target.mkdir(parents=True,exist_ok=False); pack=propose()
            if args.parent_pack:
                parent=validate_pack(load(args.parent_pack)); pack['version']=parent['version']+1; pack['parent_pack_sha256']=digest(parent); validate_pack(pack)
            write_new(target/'pack.json',pack); write_new(target/'review.json',review_template(pack))
            for case in pack['cases']: write_new(target/'fixtures'/(case['case_id']+'.json'),fixture_spec(case))
            result={'status':'DRAFT','cases':len(pack['cases']),'generator':pack['generator'],'pack_sha256':digest(pack)}
        elif args.cmd=='import-runs': result=import_runs(load(args.pack),args.runs,args.out)
        elif args.cmd=='validate': result={'status':'VALIDATED_DRAFT','pack_sha256':digest(validate_pack(load(args.pack)))}
        elif args.cmd=='freeze': result=freeze(load(args.pack),load(args.review),args.out)
        elif args.cmd=='grade':
            result=grade(load(args.pack),args.case,load(args.trace)); write_new(args.out,result)
        elif args.cmd=='evaluate':
            if not Path(args.traces).is_dir(): raise ValueError('Trace directory does not exist')
            traces={p.stem:load(p) for p in sorted(Path(args.traces).glob('*.json'))}
            result=evaluate(load(args.pack),traces,args.split,args.out,args.ledger,load(args.review) if args.review else None)
            result={k:v for k,v in result.items() if k not in ['grades','execution_summary']}
        elif args.cmd=='verify':
            result=verify(args.run); result={k:result[k] for k in ['report_sha256','passes','failures','missing_cases','release_decision']}
        else: result=assess_promotion(args.development,args.holdout,load(args.development_review),load(args.holdout_review))
        print(json.dumps(result,indent=2)); return 0
    except (ValueError,TypeError,KeyError,OSError) as exc: parser.exit(2,f'Blocked: {exc}\n')

if __name__=='__main__': raise SystemExit(main())
