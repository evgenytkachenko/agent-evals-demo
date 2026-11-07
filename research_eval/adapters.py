"""Read-only importer for companion researcher exports. Never executes a trace."""
import hashlib
from pathlib import Path
from .common import load,write_new,digest
from .packs import validate_pack
from .scorer import validate_trace
from .common import parse_json


def import_runs(pack,root,out):
    validate_pack(pack); root=Path(root); out=Path(out)
    if out.exists(): raise ValueError('Import output already exists')
    if not root.is_dir(): raise ValueError('Runner export directory missing')
    known={c['case_id'] for c in pack['cases']}; rows=[]; traces={}
    # Only registered case directory names are considered. Never interpolate an
    # unvalidated case id or trust manifest paths as filesystem instructions.
    for cid in sorted(known):
        folder=root/cid
        if not folder.exists(): continue
        if folder.is_symlink() or not folder.is_dir(): raise ValueError('Unsafe export directory')
        files={name:folder/name for name in ['run.json','events.jsonl','report.md','SHA256SUMS.json']}
        for path in files.values():
            if path.is_symlink() or not path.is_file() or path.stat().st_size>16*1024*1024: raise ValueError('Missing, linked or oversized runner file')
        manifest=load(files['SHA256SUMS.json'])
        if not isinstance(manifest,dict) or set(manifest)!={'run.json','events.jsonl','report.md'}: raise ValueError('Unsupported runner manifest')
        for name,expected in manifest.items():
            if hashlib.sha256(files[name].read_bytes()).hexdigest()!=expected: raise ValueError('Runner file hash mismatch: '+name)
        trace=validate_trace(load(files['run.json']))
        journal=[parse_json(line) for line in files['events.jsonl'].read_text(encoding='utf-8').splitlines()]
        if journal!=trace['events'] or trace['scenario_id']!=cid: raise ValueError('Runner journal/scenario mismatch')
        traces[cid]=trace; rows.append({'case_id':cid,'trace_sha256':digest(trace),'runner_file_hashes':manifest})
    if not traces: raise ValueError('No registered runner exports found')
    out.mkdir(parents=True,exist_ok=False)
    for cid,trace in traces.items(): write_new(out/'traces'/(cid+'.json'),trace)
    receipt={'schema_version':'research-adapter-import/1','pack_sha256':digest(pack),'imports':rows,'missing_case_ids':sorted(known-set(traces)),'evidence':'Local file/journal consistency only; not authenticated execution.'}
    write_new(out/'receipt.json',receipt)
    return receipt
