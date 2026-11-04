"""Create separate immutable static/backend handoff ZIPs; no deployment or secrets."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TOOLS=('serve_term_generation.py','term_generation_worker.py','manage_term_invites.py','requirements-term-generation.lock','requirements-term-generation.in')
EXCLUDE={'fixtures','__pycache__','.superpowers','private','responses','tests'}

def digest(content):return hashlib.sha256(content).hexdigest()

def package_release(root,release,output,*,qa_dir):
    root=Path(root).resolve();release=Path(release).resolve();output=Path(output).resolve();qa_dir=Path(qa_dir).resolve()
    if output.exists():raise FileExistsError('Handoff is immutable; choose a fresh output')
    manifest=json.loads((release/'release-manifest.json').read_bytes());public={}
    for row in manifest['resources']:
        name=row['path'];path=(release/name).resolve()
        if not path.is_relative_to(release) or path.is_symlink() or name in public:raise ValueError('Unsafe release path')
        content=path.read_bytes()
        if len(content)!=row['bytes'] or digest(content)!=row['sha256']:raise ValueError('Release hash mismatch: '+name)
        public[name]=content
    public['release-manifest.json']=(release/'release-manifest.json').read_bytes()
    backend={}
    for path in sorted((root/'term_explainer').rglob('*')):
        relative=path.relative_to(root)
        if not path.is_file() or set(relative.parts)&EXCLUDE or any(p.startswith('.') for p in relative.parts):continue
        if path.suffix not in {'.py','.md','.json','.txt','.css','.js','.mjs','.svg','.html'}:continue
        if path.is_symlink():raise ValueError('Backend symlink rejected')
        backend[relative.as_posix()]=path.read_bytes()
    for name in TOOLS:backend['tools/'+name]=(root/'tools'/name).read_bytes()
    for path in sorted((root/'deploy').iterdir()):
        if path.is_file() and (path.name in {'term-generation.env.example','figure-qa-manifest.json'} or path.suffix=='.service'):
            backend['deploy/'+path.name]=path.read_bytes()
    qa=json.loads((root/'deploy/figure-qa-manifest.json').read_bytes())
    for name,expected in qa['sha256'].items():
        if Path(name).name!=name:raise ValueError('Unsafe QA path')
        content=(qa_dir/name).read_bytes()
        if digest(content)!=expected:raise ValueError('QA hash mismatch: '+name)
        backend['figure-qa/'+name]=content
    notices=root/'deploy'/'third-party'
    if qa.get('requireRuntimeNotices'):
        inventory=notices/'python-runtime/inventory.json'
        if not inventory.is_file():raise ValueError('Runtime license inventory missing')
        for row in json.loads(inventory.read_bytes())['files']:
            path=(inventory.parent/row['path']).resolve()
            if not path.is_relative_to(inventory.parent.resolve()) or not path.is_file() or digest(path.read_bytes())!=row['sha256']:
                raise ValueError('Runtime license file missing or altered')
        if 'assets/third-party/NOTICE.txt' not in public:raise ValueError('Frontend license notices missing from hashed release')
    for path in sorted(notices.rglob('*')):
        if path.is_symlink():raise ValueError('Notice symlink rejected')
        if path.is_file():backend['third-party/'+path.relative_to(notices).as_posix()]=path.read_bytes()
    output.mkdir(parents=True)
    backend_files=[dict(path=name,sha256=digest(content),bytes=len(content)) for name,content in sorted(backend.items())]
    backend_id=digest(json.dumps(backend_files,sort_keys=True,separators=(',',':')).encode())[:20]
    result=dict(version=1,releaseId=manifest['releaseId'],backendId=backend_id,backendFiles=backend_files,staticSource=str(release),archives={},deployment='test site only; no deployment performed')
    for name,files in [('static.zip',public),('backend.zip',backend)]:
        with zipfile.ZipFile(output/name,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for filename,content in sorted(files.items()):archive.writestr(filename,content)
        result['archives'][name]=dict(sha256=digest((output/name).read_bytes()),bytes=(output/name).stat().st_size,files=len(files))
    (output/'handoff-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--release',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--qa-dir',type=Path,required=True);a=p.parse_args()
    print(json.dumps(package_release(ROOT,a.release,a.output,qa_dir=a.qa_dir),ensure_ascii=False,indent=2))
