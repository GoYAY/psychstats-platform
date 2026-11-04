"""Incremental offline export + Nature-figure audits for all drawn examples.

No content manifest is modified here. Dimension results are applied separately
after narrative review. Cached figures with identical source/data are reused.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'site'))
sys.path.insert(0,str(Path.home()/'.codex/skills/nature-figure/scripts'))
from sitegen.rollout_figures import make_figure, export_figure
from sitegen.plain_visuals import load_visuals
from audit_panel_alignment import require_matplotlib_panel_alignment
from audit_figure_collisions import audit_pdf as collision_audit, exit_code as collision_exit, write_overlay_pdf
from audit_pdf_text import audit_pdf as text_audit
import matplotlib.pyplot as plt

PALETTE={'foundations':'#244da4','data-preparation':'#006d70','hypothesis-testing':'#6741ad',
         'group-comparisons':'#a33052','regression':'#8a5200','classification-clustering':'#006d70',
         'factor-analysis':'#6741ad','structural-equation-modeling':'#244da4',
         'mediation-moderation':'#953970','multilevel-longitudinal':'#17643b'}


def raw_entries():
    return load_visuals(ROOT/'site/content/plain_visuals')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind',choices=['statistics','story','all'],default='all')
    parser.add_argument('--slug',action='append')
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    entries=raw_entries()
    assets=ROOT/'site/assets/examples-v2'; out=ROOT/'logs/figure-rollout'
    assets.mkdir(parents=True,exist_ok=True); out.mkdir(parents=True,exist_ok=True)
    cache_path=out/'export-records.json'
    records=json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.is_file() else {}
    topics={p.stem:json.loads(p.read_text(encoding='utf-8')).get('topic') for p in (ROOT/'site/content/drafts').glob('*.json')}
    ns='http://www.w3.org/2000/svg'; ET.register_namespace('',ns); ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
    failures=[]; rendered=0; reused=0
    sources=[ROOT/'site/sitegen'/f for f in ('rollout_figures.py','illustrated_examples.py')]
    for slug,entry in entries.items():
        if entry['decision']!='draw' or (args.slug and slug not in args.slug): continue
        if args.kind=='story' and entry['kind']!='story': continue
        if args.kind=='statistics' and entry['kind']=='story': continue
        relevant=list(sources)
        if entry['kind']=='story':
            relevant.extend(p for p in (ROOT/'site/sitegen').glob('story_*.py'))
        source_hash=hashlib.sha256(b''.join(p.read_bytes() for p in relevant)).hexdigest()
        meaning={k:v for k,v in entry.items() if k!='artwork'}
        fingerprint=hashlib.sha256((source_hash+json.dumps(meaning,ensure_ascii=False,sort_keys=True)).encode('utf-8')).hexdigest()
        color=PALETTE.get(topics.get(slug),'#244da4')
        for mobile in (False,True):
            stem=slug+('-mobile' if mobile else '')
            svg=assets/(stem+'.svg'); pdf=out/(stem+'.pdf')
            saved=records.get(stem,{})
            if not args.force and saved.get('fingerprint')==fingerprint and svg.is_file() and pdf.is_file():
                reused+=1
                if saved.get('failed'): failures.append(stem)
                continue
            fig=None
            try:
                fig=make_figure(slug,entry,color,mobile)
                fig.canvas.draw()
                comparable=[a for a in fig.axes if a.get_gid() and a.get_gid().startswith('data-panel')]
                if len(comparable)>1:
                    for index,ax in enumerate(comparable): ax.set_gid(f'data-panel-{index}')
                    require_matplotlib_panel_alignment(fig,json_out=str(out/(stem+'.alignment.json')),
                        overlay_svg=str(out/(stem+'.alignment.svg')),strict=True)
                width,height=[round(v*72) for v in fig.get_size_inches()]
                export_figure(fig,svg,pdf)
                tree=ET.parse(svg); root=tree.getroot(); root.set('role','img'); root.set('aria-labelledby','title desc')
                for tag,body in [('title',entry['title']),('desc',entry['takeaway']+'。'+entry.get('caution',entry['limit']))]:
                    node=ET.Element('{'+ns+'}'+tag,id=tag); node.text=body; root.insert(0,node)
                tree.write(svg,encoding='utf-8',xml_declaration=True)
                fonts=text_audit(pdf.read_bytes(),minimum_pt=5)
                collisions=collision_audit(pdf)
                failed=not fonts['auditable'] or fonts['below_minimum_count']>0 or collision_exit(collisions)!=0
                result={'fingerprint':fingerprint,'width':width,'height':height,'kind':entry['kind'],
                        'font_audit':fonts,'collision_audit':collisions,'failed':failed}
                records[stem]=result
                (out/(stem+'.audit.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                if failed:
                    failures.append(stem)
                    write_overlay_pdf(pdf,out/(stem+'.collision.pdf'),collisions['findings'])
                    print('FAIL',stem,[(f['kind'],f.get('text')) for f in collisions['findings'] if f['severity']=='FAIL'],flush=True)
                rendered+=1
            except Exception as error:
                failures.append(stem); records[stem]={'fingerprint':fingerprint,'failed':True,'error':str(error)}
                print('ERROR',stem,type(error).__name__,str(error),flush=True)
            finally:
                if fig is not None: plt.close(fig)
        cache_path.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
        print(slug,flush=True)
    cache_path.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'rendered':rendered,'reused':reused,'failures':failures}),flush=True)
    return bool(failures)


if __name__=='__main__': sys.exit(main())
