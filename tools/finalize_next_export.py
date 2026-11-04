"""Create real static compatibility entries; never rely on server rewrites."""
import argparse
import json
from pathlib import Path
import shutil


def resolve_output(root, value):
    if not value.startswith('/psy-stats/'):
        raise ValueError('Unexpected public path')
    relative=value[len('/psy-stats/'):]
    if '..' in relative.split('/') or '\\' in relative or '?' in relative or '#' in relative:
        raise ValueError('Unsafe output path')
    path=(root/relative).resolve()
    if not path.is_relative_to(root): raise ValueError('Output escapes root')
    return path


def finalize_export(out, manifest):
    root=Path(out).resolve();pairs=[]
    for record in manifest['pages'].values():
        source=resolve_output(root,record['canonicalPath'])/'index.html'
        if not source.is_file(): raise FileNotFoundError(source)
        for alias in record['aliases']:
            target=resolve_output(root,alias['path'])
            if not target.name.endswith('.html'): raise ValueError('Alias must be html')
            if source!=target: pairs.append((source,target))
    for source,target in pairs:
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    return {'aliases':len(pairs)}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--manifest',required=True);args=parser.parse_args()
    print(json.dumps(finalize_export(args.root,json.loads(Path(args.manifest).read_text(encoding='utf-8')))))
