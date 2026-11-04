"""Prepare three private local QA packages from explicitly accepted artefacts."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from term_explainer.library_export import export_package
from tools.read_term_sections import atomic_write

def load(path):return json.loads(path.read_text(encoding='utf-8'))

def prepare(output,*,dtp_pdf=None,cognitive_pdf=None):
    output=Path(output).resolve()
    if output.is_relative_to(ROOT/'site'):raise ValueError('Private fixtures must not be served with the site')
    old=ROOT/'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live'
    new=ROOT/'.superpowers/sdd/2026-10-19-local-term-library-implementation/entanglement'
    dtp=old/'dtp-user-pdf/dtp-multi-literature-run';cog=old/'cognitive-drift-generation-v3'
    dtp_sources=load(dtp/'job.json')['reader_sources']
    brown=old/'dtp-user-pdf/related-literature/brown2011/PDFs/Item_Response_Modeling_of_Forced-Choice_Questionnaires.pdf'
    nie=old/'dtp-user-pdf/related-literature/nie2024/PDFs/Multidimensional_IRT_for_forced_choice_tests_A_literature_review.pdf'
    original_dtp={s['id']:Path(dtp_pdf) for s in dtp_sources if dtp_pdf and s['id'].startswith('dtp-user-paper')}
    original_dtp.update({sid:p for sid,p in [('brown2011',brown),('nie2024',nie)] if p.is_file()})
    entries=[('dtp',dtp,load(dtp/'input.json')['request'],dtp_sources,original_dtp),
        ('cognitive-drift',cog,load(cog/'request.json'),load(cog/'evidence.json')['sources'],None),
        ('human-ai-entanglement',new,load(new/'render-request.json'),load(new/'evidence.json')['sources'],None)]
    reports=[]
    for label,folder,request,sources,originals in entries:
        originals=originals if originals is not None else {s['id']:Path(cognitive_pdf) for s in sources if cognitive_pdf and s['id'].startswith('user-paper')}
        figures={role:folder/'preview/figures'/name for role,name in [('desktop','figure.svg'),('mobile','figure-mobile.svg')]}
        lesson=load(folder/'lesson.json')
        report=export_package(request,lesson,sources=sources,originals=originals,figures=figures,term_id=lesson['term']['id'],output=output/(label+'.zip'))
        report.update(case=label,lessonHash=hashlib.sha256((folder/'lesson.json').read_bytes()).hexdigest())
        reports.append(report)
    atomic_write(output/'cases.json',reports)
    return reports

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'logs/local-library/private-fixtures');parser.add_argument('--dtp-pdf',type=Path);parser.add_argument('--cognitive-pdf',type=Path);args=parser.parse_args()
    print(json.dumps(prepare(args.output,dtp_pdf=args.dtp_pdf,cognitive_pdf=args.cognitive_pdf),ensure_ascii=False,indent=2))
