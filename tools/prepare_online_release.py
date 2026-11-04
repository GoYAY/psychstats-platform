"""Build a fresh combined public candidate; never deploy or overwrite a release."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.prepare_local_library_preview import prepare_preview, verified_chart_build

PUBLIC_DIRS={'assets','analyses','analysis-code','analysis-logs','data','library','terms','topics'}
PUBLIC_SUFFIXES={'.html','.js','.mjs','.css','.json','.svg','.png','.jpg','.jpeg','.webp','.ico','.woff','.woff2','.ttf','.otf','.txt','.pdf','.csv','.r','.md'}
PRIVATE_PARTS={'.env','private','private-fixtures','fixtures','responses','__pycache__','qa','.superpowers'}

def public_file(path):
    """Only web roots and formats consumed by this app, never workspace trees."""
    parts=path.parts
    if set(parts)&PRIVATE_PARTS or any(p.startswith('.') for p in parts):return False
    if len(parts)==1:return path.suffix=='.html' or path.name=='library-build.json'
    return parts[0] in PUBLIC_DIRS and (path.suffix.lower() in PUBLIC_SUFFIXES or path.name.upper().startswith(('LICENSE','NOTICE')))

def prepare_release(baseline,output,chart_build,*,bundle_library=False,notices_dir=None):
    site=(ROOT/'site').resolve();target=Path(output).resolve()
    if target.parent!=site or not re.fullmatch(r'online-release-[a-z0-9-]{1,48}',target.name):raise ValueError('Only a fresh isolated online-release directory is allowed')
    if target.exists():raise FileExistsError('Release is immutable; choose a new online-release suffix')
    _, chart_resources, _ = verified_chart_build(chart_build)
    if sum(len(content) for name,content in chart_resources if name.endswith(('.mjs','.js'))) > 450000:
        raise ValueError('Optional chart startup budget exceeds 450000 bytes')
    site.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=site,prefix='release-stage-') as d:
        stage=Path(d)/'build'
        report=prepare_preview(baseline,stage,online_generation=True,chart_build=chart_build,visual_policy_version=1,bundle_library=bundle_library)
        if notices_dir is not None:
            notices=Path(notices_dir)
            if not notices.is_dir() or not any(p.is_file() for p in notices.rglob('*')):raise ValueError('Frontend license notices missing')
            for path in sorted(notices.rglob('*')):
                if path.is_symlink():raise ValueError('Notice symlink rejected')
                if path.is_file():
                    dest=stage/'assets/third-party'/path.relative_to(notices)
                    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
        selected=[]
        for path in sorted(stage.rglob('*')):
            if path.is_symlink():raise ValueError('Release must not contain symlinks')
            if path.is_file() and public_file(path.relative_to(stage)):selected.append(path)
        resources=[dict(path=p.relative_to(stage).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in selected]
        release_id=hashlib.sha256(json.dumps(resources,sort_keys=True).encode()).hexdigest()[:20]
        # Create only after validation. Never replace an existing accepted tree.
        target.mkdir()
        for path in selected:
            dest=target/path.relative_to(stage);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
        manifest=dict(version=1,releaseId=release_id,onlineGeneration=True,visualPresentationVersion=1,runtimeVersion=report['runtimeVersion'],resources=resources)
        (target/'release-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        return dict(report,output=str(target),releaseId=release_id,publicFiles=len(resources),qaFilesCopied=0)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,default=ROOT/'site/paper-table-audit-preview');p.add_argument('--output',type=Path,default=ROOT/'site/online-release-preview');p.add_argument('--chart-build',type=Path,default=ROOT/'chart_widget/dist');p.add_argument('--bundle-library',action='store_true');p.add_argument('--notices-dir',type=Path);a=p.parse_args()
    print(json.dumps(prepare_release(a.baseline,a.output,a.chart_build,bundle_library=a.bundle_library,notices_dir=a.notices_dir),ensure_ascii=False,indent=2))
