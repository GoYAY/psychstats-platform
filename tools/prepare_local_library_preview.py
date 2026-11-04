"""Read-only baseline copy for the isolated personal-library preview."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from term_explainer.library_export import public_catalogue
from tools.official_knowledge_graph import official_graph
from html import escape


def library_navigation(page,prefix,*,active):
    def replace(match):
        links=re.sub(r'<a\b[^>]*href="[^"#]*library/index\.html"[^>]*>.*?</a>','',match[2],flags=re.S)
        if active:links=links.replace(' aria-current="page"','')
        return match[1]+links+'<a href="'+prefix+'library/index.html"'+(' aria-current="page"' if active else '')+'>我的知识库</a>'+match[3]
    return re.sub(r'(<nav aria-label="主导航">)(.*?)(</nav>)',replace,page,count=1,flags=re.S)


def strip_library_overlays(page):
    page=re.sub(r'<script\b[^>]*data-library-module="[^"]*"[^>]*>.*?</script>','',page,flags=re.S)
    page=re.sub(r'<style\b[^>]*data-library-entry[^>]*>.*?</style>','',page,flags=re.S)
    return re.sub(r'<link\b[^>]*href="[^"#]*assets/library(?:-[A-Za-z0-9-]+)?/library\.css"[^>]*>','',page)

def overlay_operational_examples(output):
    """Narrow verified-figure overlay; preserve the validated navigation build."""
    sys.path.insert(0,str(ROOT/'site'))
    from sitegen.plain_visuals import load_visuals
    updates=json.loads((ROOT/'site/content/operational_visuals.json').read_text(encoding='utf-8'))
    entries=load_visuals(ROOT/'site/content/plain_visuals')
    for slug in updates:
        page_path=output/'terms'/(slug+'.html')
        if not page_path.is_file():continue
        e=entries[slug];versions={}
        for suffix in ('','-mobile'):
            source=ROOT/'site/assets/examples-v2'/(slug+suffix+'.svg')
            target=output/'assets/examples'/source.name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target);versions[source.name]=hashlib.sha256(source.read_bytes()).hexdigest()[:10]
        url=lambda suffix:'../assets/examples/'+slug+suffix+'.svg?v='+versions[slug+suffix+'.svg']
        caption=''.join('<p class="figure-narrative">'+escape(p)+'</p>' for p in e['narrative'])
        figure=('<figure class="plain-example-visual illustrated-example"><h3>'+escape(e['title'])+'</h3>'
                '<picture><source media="(max-width: 600px)" srcset="'+url('-mobile')+'">'
                '<img src="'+url('')+'" width="760" height="440" loading="lazy" alt="'+escape(e['title']+'。'+e['takeaway'])+'"></picture>'
                '<figcaption><span class="example-basis">教学合成数据 · 非真实研究结果</span>'+caption+
                '<p class="figure-caution"><strong>注意</strong> '+escape(e['caution'])+'</p></figcaption></figure>')
        page=page_path.read_text(encoding='utf-8')
        page,count=re.subn(r'<figure class="plain-example-visual illustrated-example">.*?</figure>',lambda m:figure,page,count=1,flags=re.S)
        if count!=1:raise ValueError('Expected exactly one teaching figure: '+slug)
        for name,version in versions.items():page=re.sub(re.escape(name)+r'\?v=[a-z0-9]+',name+'?v='+version,page)
        page_path.write_text(page,encoding='utf-8')

def verified_chart_build(chart_build):
    build=Path(chart_build).resolve();manifest=json.loads((build/'manifest.json').read_text(encoding='utf-8'))
    resources=manifest.get('resources');entry=manifest.get('entry');verified=[];seen=set();total=0
    if manifest.get('version')!=1 or not isinstance(resources,list) or not 1<=len(resources)<=256:raise ValueError('Invalid chart manifest')
    for row in resources:
        name=row.get('file','');expected=row.get('sha256','')
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]*',name) or '..' in name.split('/') or name in seen or Path(name).suffix not in {'.mjs','.js','.css','.json','.txt'}:raise ValueError('Unsafe public chart path')
        file=(build/name).resolve()
        if not file.is_relative_to(build) or not file.is_file() or not re.fullmatch(r'[a-f0-9]{64}',expected):raise ValueError('Invalid chart resource')
        content=file.read_bytes();total+=len(content)
        if total>5000000 or hashlib.sha256(content).hexdigest()!=expected:raise ValueError('Chart hash or size mismatch')
        seen.add(name);verified.append((name,content))
    if entry not in seen or not entry.endswith(('.js','.mjs')):raise ValueError('Missing chart module entry')
    version=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:16]
    return manifest,verified,'charts-'+version

def prepare_preview(baseline,output,*,online_generation=False,chart_build=None,visual_policy_version=0,bundle_library=False):
    baseline=Path(baseline).resolve();output=Path(output).resolve();site=(ROOT/'site').resolve()
    protected=[p.resolve() for p in site.iterdir() if p.is_dir() and p.name in {'dist','online-generation-preview','local-library-preview','paper-table-audit-preview','paper-table-audit-source','navigation-readiness-preview','prefetch-coverage-preview','next-preview','assets','content','sitegen','templates','library'}]
    if not output.is_relative_to(site) or output==site or output==baseline or output.is_relative_to(baseline) or baseline.is_relative_to(output) or any(output==p or output.is_relative_to(p) or p.is_relative_to(output) for p in protected):
        raise ValueError('Output must be isolated from protected previews, sources and baseline')
    if not (baseline/'index.html').is_file():raise ValueError('Baseline index missing')
    if type(visual_policy_version) is not int or visual_policy_version not in (0,1):raise ValueError('Unsupported trusted visual policy')
    chart=verified_chart_build(chart_build) if chart_build is not None else None
    if visual_policy_version and not chart:raise ValueError('New visual candidate requires verified chart resources')
    shutil.copytree(baseline,output,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.env','private-fixtures','responses','__pycache__'))
    overlay_operational_examples(output)
    modules=site/'assets/library'
    if modules.exists():shutil.copytree(modules,output/'assets/library',dirs_exist_ok=True)
    core_files={name:(site/'assets/charts'/name).read_bytes() for name in ('data.mjs','loader.mjs','presentation.mjs')}
    core_directory='charts-core-'+hashlib.sha256(b''.join(name.encode()+value for name,value in sorted(core_files.items()))).hexdigest()[:16]
    for name,content in core_files.items():
        dest=output/'assets'/core_directory/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
    for name in ('reader.mjs','contract.mjs'):
        reader_file=output/'assets/library'/name
        if reader_file.exists():reader_file.write_text(reader_file.read_text(encoding='utf-8').replace('../charts/','../'+core_directory+'/'),encoding='utf-8')
    if chart:
        manifest,files,chart_directory=chart
        for name,content in files:
            dest=output/'assets'/chart_directory/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
        (output/'assets'/chart_directory/'manifest.json').write_text(json.dumps(manifest,sort_keys=True),encoding='utf-8')
    if modules.exists():
        for name in ('reader.js','glossary.js'):
            shutil.copyfile(ROOT/'term_explainer/assets'/name,output/'assets/library'/('legacy-'+name))
        (output/'assets/library/catalogue.json').write_text(json.dumps(public_catalogue(baseline),ensure_ascii=False,indent=2),encoding='utf-8')
        (output/'assets/library/official-graph.json').write_text(json.dumps(official_graph(baseline,ROOT/'site/content/registry.json'),ensure_ascii=False,indent=2),encoding='utf-8')
    vendor=site/'assets/vendor/fflate'
    if vendor.exists():shutil.copytree(vendor,output/'assets/vendor/fflate',dirs_exist_ok=True)
    shutil.copytree(site/'assets/vendor/katex',output/'assets/vendor/katex',dirs_exist_ok=True)
    host=ROOT/'tests/library/browser-host.html'
    (output/'qa').mkdir(parents=True,exist_ok=True);shutil.copyfile(host,output/'qa/library-host.html')
    library_entry='app.mjs'
    if bundle_library:
        bundled=subprocess.run(['node',str(ROOT/'tools/bundle-library.mjs'),str(output/'assets/library')],capture_output=True,text=True,encoding='utf-8',timeout=60,check=True)
        bundle_report=json.loads(bundled.stdout)
        if bundle_report.get('entry')!='app-boot.mjs' or bundle_report.get('staticImports')!=[]:raise ValueError('Library startup bundle retains static request waterfall')
        library_entry=bundle_report['entry']
    digest=hashlib.sha256()
    for path in sorted((output/'assets/library').rglob('*')):
        if path.is_file():digest.update(path.name.encode());digest.update(path.read_bytes())
    module_directory='library-'+digest.hexdigest()[:16]
    shutil.copytree(output/'assets/library',output/'assets'/module_directory,dirs_exist_ok=True)
    # Patch the validated runtime in place; do not replace performance assets
    # with a possibly older source-tree build.
    changed={}
    # Ship the bounded cursor fix without replacing the validated CSS/runtime.
    cursor=site/'assets/cursor.js'
    if cursor.is_file():
        shutil.copyfile(cursor,output/'assets/cursor.js')
        changed[cursor.name]=hashlib.sha256(cursor.read_bytes()).hexdigest()[:16]
    policy=output/'assets/navigation-policy.js'
    if policy.is_file():
        code=policy.read_text(encoding='utf-8').replace('|index|paths|practice|datasets|symbols|analysis|sources)',r'|library\/index|index|paths|practice|datasets|symbols|analysis|sources)')
        # The source and baseline policy were identical before the narrow
        # library additions, so retain its new same-document predicate too.
        code=(site/'assets/navigation-policy.js').read_text(encoding='utf-8')
        policy.write_text(code,encoding='utf-8');changed[policy.name]=hashlib.sha256(policy.read_bytes()).hexdigest()[:16]
    runtime=output/'assets/page-runtime.js'
    if runtime.is_file():
        code=runtime.read_text(encoding='utf-8')
        allowed=next(line for line in (site/'assets/page-runtime.js').read_text(encoding='utf-8').splitlines() if 'var allowed=' in line)
        code=re.sub(r'^.*var allowed=.*$',lambda m:allowed,code,flags=re.M)
        code=re.sub(r'assets/page-runtime\.js\?v=[^"\]]+',r'assets/page-runtime.js',code)
        runtime.write_text(code,encoding='utf-8');changed[runtime.name]=hashlib.sha256(runtime.read_bytes()).hexdigest()[:16]
    adapter=site/'assets/library-runtime.js'
    navigation=output/'assets/soft-navigation.js'
    if navigation.is_file():
        code=navigation.read_text(encoding='utf-8').replace("window.addEventListener('popstate',function(event){navigate(","window.addEventListener('popstate',function(event){if(policy.sameLibraryDocument?.(activeURL,location.href,siteRoot))return;navigate(")
        navigation.write_text(code,encoding='utf-8');changed[navigation.name]=hashlib.sha256(navigation.read_bytes()).hexdigest()[:16]
    if adapter.is_file():shutil.copyfile(adapter,output/'assets/library-runtime.js');changed[adapter.name]=hashlib.sha256(adapter.read_bytes()).hexdigest()[:16]
    version=hashlib.sha256((module_directory+json.dumps(changed,sort_keys=True)+(chart_directory if chart else '')+':visual-policy-'+str(visual_policy_version)+':generation-'+str(bool(online_generation))).encode()).hexdigest()[:16]
    fragment=(site/'library/index.html').read_text(encoding='utf-8')
    if online_generation:
        fragment=fragment.replace('class="library-page"','class="library-page" data-generation-api="api/term-explainer/"')
        fragment=fragment.replace('本机资料 · 不上传','本机保存 · 生成时按需发送')
    template=baseline/'datasets.html'
    if template.is_file():
        page=template.read_text(encoding='utf-8')
        page=re.sub(r'<main\b[^>]*>.*?</main>',lambda m:fragment,page,flags=re.S)
        page=re.sub(r'\b(href|src)="([^"#:]+)"',lambda m:m[1]+'="'+(m[2] if re.match(r'^[a-z]+:',m[2]) else '../'+m[2])+'"',page)
        page=page.replace('data-root=""','data-root="../"')
        page=re.sub(r'(<nav aria-label="主导航">)(.*?)(</nav>)',lambda m:m[1]+m[2].replace(' aria-current="page"','')+m[3],page,flags=re.S)
        (output/'library').mkdir(exist_ok=True);(output/'library/index.html').write_text(page,encoding='utf-8')
    for path in output.rglob('*.html'):
        if 'qa' in path.relative_to(output).parts:continue
        page=strip_library_overlays(path.read_text(encoding='utf-8'));prefix='../'*(len(path.relative_to(output).parts)-1)
        page=library_navigation(page,prefix,active=path.relative_to(output).as_posix()=='library/index.html')
        for name,hash_value in changed.items():page=re.sub(re.escape(name)+r'\?v=[^"\s]+',lambda m:name+'?v='+hash_value,page)
        page=re.sub(r'(<meta name="psych-runtime" content=")[^"]+',lambda m:m[1]+version,page)
        chart_attribute=(' data-chart-module="'+chart_directory+'/'+manifest['entry']+'"') if chart else ''
        adapter_markup='<script src="'+prefix+'assets/library-runtime.js?v='+changed.get('library-runtime.js','')+'" data-library-module="'+module_directory+'/'+library_entry+'"'+chart_attribute+' defer></script>'
        page=page.replace('</body>',adapter_markup+'</body>')
        page=page.replace('</head>','<style data-library-entry>@media(min-width:1121px){.site-head .nav-row{gap:16px}.site-head .nav-row>nav{flex-wrap:nowrap;white-space:nowrap;gap:2px}.site-head .nav-row>nav a{padding-inline:7px}.site-head .header-search input{width:150px}}</style></head>')
        if path.relative_to(output).as_posix()=='library/index.html':page=page.replace('</head>','<link rel="stylesheet" href="'+prefix+'assets/'+module_directory+'/library.css"></head>')
        path.write_text(page,encoding='utf-8')
    report=dict(output=str(output),baseline=str(baseline),baselineIndexHash=hashlib.sha256((baseline/'index.html').read_bytes()).hexdigest(),privateFilesCopied=0,moduleDirectory=module_directory,runtimeVersion=version,changedRuntimeAssets=changed)
    report['chartCoreDirectory']=core_directory
    report['libraryEntry']=library_entry
    if visual_policy_version:report['visualPresentationVersion']=visual_policy_version
    if chart:report.update(chartDirectory=chart_directory,chartEntry=manifest['entry'])
    (output/'library-build.json').write_text(json.dumps({k:v for k,v in report.items() if k not in {'output','baseline'}},ensure_ascii=False,indent=2),encoding='utf-8')
    if (output/'library/index.html').exists():
        page=(output/'library/index.html').read_text(encoding='utf-8')
        resources={'library/index.html':None}
        for value in re.findall(r'(?:src|href)="([^"#]+)"',page):
            if re.match(r'^[a-z]+:',value):continue
            name=value.split('?')[0]
            if name.startswith('../assets/'):
                resources['assets/'+name[len('../assets/'):]]=value.split('?',1)[1] if '?' in value else None
        for folder in [output/'assets'/module_directory,output/'assets'/core_directory,output/'assets/vendor/fflate',output/'assets/vendor/katex']+([output/'assets'/chart_directory] if chart else []):
            for file in folder.rglob('*'):
                if file.is_file() and file.suffix not in {'.pdf','.md'}:resources.setdefault(file.relative_to(output).as_posix(),None)
        items=[dict(url=('../'+name if name.startswith('assets/') else 'index.html')+('?' + query if query else ''),hash=hashlib.sha256((output/name).read_bytes()).hexdigest()) for name,query in sorted(resources.items()) if (output/name).is_file()]
        offline_version=hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()[:16]
        (output/'library/offline-manifest.json').write_text(json.dumps(dict(version=offline_version,resources=items),ensure_ascii=False,indent=2),encoding='utf-8')
        (output/'library/sw.js').write_text((site/'library/sw.js').read_text(encoding='utf-8').replace('__BUILD_VERSION__',offline_version),encoding='utf-8')
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--online-generation',action='store_true');args=parser.parse_args()
    print(json.dumps(prepare_preview(args.baseline,args.output,online_generation=args.online_generation),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
