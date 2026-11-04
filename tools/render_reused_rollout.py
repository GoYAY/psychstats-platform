"""Restyle existing diagrams without changing their source SVG geometry."""
from pathlib import Path
import json
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'site'))
sys.path.insert(0,str(Path.home()/'.codex/skills/nature-figure/scripts'))
from sitegen.reused_figures import make_reused_figure
from sitegen.rollout_figures import export_figure
from render_figure_rollout import PALETTE
from audit_figure_collisions import audit_pdf, exit_code, write_overlay_pdf
from audit_pdf_text import audit_pdf as audit_text
from matplotlib import pyplot as plt


def main():
    manifest=json.loads((ROOT/'site/content/diagram_samples.json').read_text(encoding='utf-8'))
    records={}; failures=[]; out=ROOT/'logs/figure-rollout'; out.mkdir(parents=True,exist_ok=True)
    ns='http://www.w3.org/2000/svg'; ET.register_namespace('',ns); ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
    for slug,entry in manifest.items():
        term=json.loads((ROOT/'site/content/drafts'/(slug+'.json')).read_text(encoding='utf-8'))
        color=PALETTE[term['topic']]
        for mobile in (False,True):
            key='mobile_file' if mobile else 'file'
            source=ROOT/'site/assets/diagrams'/entry.get('source_'+key,entry[key])
            original=source.stem
            stem=original+'-glass'
            svg=source.with_name(stem+'.svg'); pdf=out/(stem+'.pdf')
            fig=make_reused_figure(source,color)
            width,height=[round(v*72) for v in fig.get_size_inches()]
            export_figure(fig,svg,pdf); plt.close(fig)
            old=ET.parse(source).getroot(); tree=ET.parse(svg); root=tree.getroot()
            root.set('role','img'); root.set('aria-labelledby','title desc')
            for tag in ('title','desc'):
                node=ET.Element('{'+ns+'}'+tag,id=tag)
                node.text=old.find('{'+ns+'}'+tag).text
                root.insert(0,node)
            tree.write(svg,encoding='utf-8',xml_declaration=True)
            fonts=audit_text(pdf.read_bytes(),minimum_pt=5); collisions=audit_pdf(pdf)
            failed=not fonts['auditable'] or fonts['below_minimum_count']>0 or exit_code(collisions)!=0
            records[slug+('-mobile' if mobile else '')]={'source':source.name,'file':svg.name,'width':width,'height':height,
                'failed':failed,'font_audit':fonts,'collision_audit':collisions}
            if failed:
                failures.append(stem); write_overlay_pdf(pdf,out/(stem+'.collision.pdf'),collisions['findings'])
        print(slug,flush=True)
    (out/'reused-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'figures':len(records),'failures':failures}),flush=True)
    return bool(failures)


if __name__=='__main__': sys.exit(main())
