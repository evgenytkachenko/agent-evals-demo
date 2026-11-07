import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
import math


def text_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load(path):
    path = Path(path)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Input exceeds 16 MiB')
    return parse_json(path.read_text(encoding='utf-8'))


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write('\n')


def origin(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            not parsed.port or not parsed.path.startswith('/')):
        raise ValueError('Exact HTTP 127.0.0.1 fixture URL without query or fragment required')
    return f'http://127.0.0.1:{parsed.port}'


def bounded_list(value, name, limit=256):
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f'{name}: bounded list required')
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()

def exact(obj, keys, name):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise ValueError(f'{name}: exact fields required: {sorted(keys)}')

def bounded_text(value, name, maximum=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{name}: nonempty string of at most {maximum} characters required')

def parse_json(raw):
    """Closed, bounded JSON: no duplicate keys, nonfinite numbers or surrogates."""
    def pairs(items):
        out={}
        for key,value in items:
            if key in out: raise ValueError('duplicate_json_key')
            out[key]=value
        return out
    def invalid(value): raise ValueError('invalid_json_constant')
    def number(value):
        result=float(value)
        if not math.isfinite(result): raise ValueError('nonfinite_json_number')
        return result
    try:
        if isinstance(raw,bytes): raw=raw.decode('utf-8')
        result=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid,parse_float=number)
    except UnicodeDecodeError as exc: raise ValueError('invalid_utf8') from exc
    except json.JSONDecodeError as exc: raise ValueError('invalid_json') from exc
    except RecursionError as exc: raise ValueError('json_depth_exceeded') from exc
    stack=[(result,0)]
    while stack:
        value,depth=stack.pop()
        if depth>32: raise ValueError('json_depth_exceeded')
        if isinstance(value,str):
            if any(0xD800<=ord(c)<=0xDFFF for c in value): raise ValueError('invalid_json_string')
        elif isinstance(value,dict):
            stack.extend((x,depth+1) for pair in value.items() for x in pair)
        elif isinstance(value,list): stack.extend((x,depth+1) for x in value)
    return result
