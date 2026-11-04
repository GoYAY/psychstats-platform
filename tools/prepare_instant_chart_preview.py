"""Build only the approved isolated shared-chart candidate, never deploy it."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'site'))
from tools.prepare_local_library_preview import prepare_preview
from sitegen.instant_charts import annotate_official_chart

def prepare(baseline,output,chart_build):
    target=Path(output).resolve()
    if target!=ROOT/'site/instant-chart-preview':raise ValueError('Only the approved new chart candidate may be built')
    report=prepare_preview(baseline,target,chart_build=chart_build)
    slug='central-tendency-and-dispersion';page=target/'terms'/(slug+'.html')
    visual=json.loads((ROOT/'site/content/plain_visuals/foundations.json').read_text(encoding='utf-8'))[slug]
    page.write_text(annotate_official_chart(page.read_text(encoding='utf-8'),visual,slug),encoding='utf-8')
    report['officialFigurePolicy']='preserve-separate-distributions-v1'
    return integrate_bridge(target,report,(ROOT/'site/assets/chart-runtime.js').read_bytes())

def integrate_bridge(target,report,bridge):
    (target/'assets/chart-runtime.js').write_bytes(bridge);version=hashlib.sha256(bridge).hexdigest()[:16]
    identity=report['runtimeVersion']+':'+hashlib.sha256(bridge).hexdigest()+':'+report.get('officialFigurePolicy','')
    report['runtimeVersion']=hashlib.sha256(identity.encode()).hexdigest()[:16]
    for file in target.rglob('*.html'):
        if 'qa' in file.relative_to(target).parts:continue
        prefix='../'*(len(file.relative_to(target).parts)-1)
        script='<script src="'+prefix+'assets/chart-runtime.js?v='+version+'" data-chart-loader="'+report['chartCoreDirectory']+'/loader.mjs" data-chart-module="'+report['chartDirectory']+'/'+report['chartEntry']+'" defer></script>'
        html=re.sub(r'(<meta name="psych-runtime" content=")[^"]+',lambda m:m[1]+report['runtimeVersion'],file.read_text(encoding='utf-8'))
        file.write_text(html.replace('</body>',script+'</body>'),encoding='utf-8')
    (target/'library-build.json').write_text(json.dumps({k:v for k,v in report.items() if k not in {'output','baseline'}},ensure_ascii=False,indent=2),encoding='utf-8')
    # Bridge is a deferred lifecycle hook, not a navigation prerequisite.
    # Add the new library HTML and bridge to the existing hash-checked manifest.
    manifest_file=target/'library/offline-manifest.json';manifest=json.loads(manifest_file.read_text(encoding='utf-8'))
    for row in manifest['resources']:
        if row['url']=='index.html':row['hash']=hashlib.sha256((target/'library/index.html').read_bytes()).hexdigest()
    manifest['resources'].append(dict(url='../assets/chart-runtime.js?v='+version,hash=hashlib.sha256(bridge).hexdigest()))
    manifest['version']=hashlib.sha256(json.dumps(manifest['resources'],sort_keys=True).encode()).hexdigest()[:16]
    manifest_file.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (target/'library/sw.js').write_text((ROOT/'site/library/sw.js').read_text(encoding='utf-8').replace('__BUILD_VERSION__',manifest['version']),encoding='utf-8')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','output','chart-build'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.baseline,args.output,args.chart_build),ensure_ascii=False,indent=2))
