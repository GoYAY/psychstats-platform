"""Create a full-site network-readiness experiment without rebuilding analyses."""
import hashlib
import json
from pathlib import Path
import shutil
import argparse
import re
import posixpath
from urllib.parse import urlsplit
from tools.export_next_preview import Tree, formula_fonts

ROOT=Path(__file__).resolve().parents[1]

def critical_record(html, css):
    tree=Tree(html)
    mains=tree.root.find(lambda n:n.tag=='main')
    if not mains:
        return {'firstScreenResources':[], 'formulaFonts':[]}
    main=mains[0]
    articles=main.find(lambda n:'term-content' in n.attrs.get('class','').split())
    images=[]
    if articles:
        pictures=articles[0].find(lambda n:n.tag=='picture')
        candidates=(pictures[0].find(lambda n:n.tag=='img') if pictures else []) or articles[0].find(lambda n:n.tag=='img')
        if candidates and candidates[0].attrs.get('src'):
            image={'kind':'image','url':candidates[0].attrs['src']}
            sources=[]
            for node in pictures[0].find(lambda n:n.tag=='source') if pictures else []:
                source=node.attrs.get('srcset','').split(',')[0].split()
                if source:
                    sources.append({'media':node.attrs.get('media',''),'url':source[0]})
            if sources:
                image['sources']=sources
            images.append(image)
    return {'firstScreenResources':images, 'formulaFonts':formula_fonts(main, css)}

def linked_resource_hints(html, page_relative, records):
    hints={}
    for node in Tree(html).root.find(lambda n:n.tag=='a'):
        if 'download' in node.attrs:
            continue
        link=urlsplit(node.attrs.get('href',''))
        if link.scheme or link.netloc or not link.path:
            continue
        route=posixpath.normpath(posixpath.join(posixpath.dirname(str(page_relative).replace('\\','/')),link.path))
        record=records.get(route)
        if record and (record['firstScreenResources'] or record['formulaFonts']):
            hints[route]=record
    return hints

def prepare(output=None, navigation=False, *, source=None):
    source=Path(source).resolve() if source else ROOT/'site/dist'
    output=Path(output).resolve() if output else ROOT/'site/network-readiness-preview'
    protected=ROOT/'site/dist'
    if not output.is_relative_to(ROOT/'site') or output==protected or output.is_relative_to(protected) or protected.is_relative_to(output) or output==source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Preview must remain isolated inside site and outside dist')
    shutil.copytree(source, output, dirs_exist_ok=True)
    replacements={}
    if navigation:
        for asset in ('soft-navigation.js','navigation-policy.js','site.css'):
            content=(ROOT/'site/assets'/asset).read_bytes()
            (output/'assets'/asset).write_bytes(content)
            replacements[asset]=hashlib.sha256(content).hexdigest()[:16]
    helper=(ROOT/'site/next-preview/lib/page-resources.mjs').read_bytes()
    helper_name='critical-page-resources.'+hashlib.sha256(helper).hexdigest()[:16]+'.mjs'
    (output/'assets'/helper_name).write_bytes(helper)
    bridge=(ROOT/'site/experiments/critical-resources-bridge.mjs').read_text(encoding='utf-8').replace('../next-preview/lib/page-resources.mjs', './'+helper_name)
    bridge_name='critical-resources-bridge.'+hashlib.sha256(bridge.encode()).hexdigest()[:16]+'.mjs'
    (output/'assets'/bridge_name).write_text(bridge, encoding='utf-8')
    css=(source/'assets/vendor/katex/katex.min.css').read_text(encoding='utf-8')
    originals={str(p.relative_to(source)).replace('\\','/'):p.read_text(encoding='utf-8') for p in source.rglob('*.html')}
    records={route:critical_record(html,css) for route,html in originals.items()}
    content_digest=hashlib.sha256(json.dumps(originals,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    release=hashlib.sha256((bridge_name+json.dumps(replacements,sort_keys=True)+content_digest).encode()).hexdigest()[:16]
    pages=0
    for original in source.rglob('*.html'):
        text=original.read_text(encoding='utf-8')
        if '</head>' not in text or 'assets/soft-navigation.js' not in text:
            continue
        relative=original.relative_to(source)
        prefix='../'*len(relative.parts[:-1])
        record=json.dumps(critical_record(text, css), ensure_ascii=False).replace('<','\\u003c')
        extra=f'<script type="application/json" data-psych-critical-resources>{record}</script><script type="module" src="{prefix}assets/{bridge_name}"></script>'
        if navigation:
            hints=json.dumps(linked_resource_hints(text,relative,records),ensure_ascii=False).replace('<','\\u003c')
            extra+=f'<script type="application/json" data-psych-resource-hints>{hints}</script>'
        for asset,digest in replacements.items():
            text=re.sub(r'(assets/'+re.escape(asset)+r'\?v=)[^"\s]+',lambda match:match.group(1)+digest,text)
        if navigation:
            text=re.sub(r'(<meta name="psych-runtime" content=")[^"]+',lambda match:match.group(1)+release,text)
        (output/relative).write_text(text.replace('</head>',extra+'</head>',1), encoding='utf-8')
        pages+=1
    return {'output':str(output),'source':str(source),'pages':pages,'bridge':bridge_name,'distPreserved':output!=ROOT/'site/dist','statisticsRerun':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output');parser.add_argument('--source');parser.add_argument('--navigation',action='store_true');args=parser.parse_args()
    print(json.dumps(prepare(args.output,args.navigation,source=args.source), ensure_ascii=False))
