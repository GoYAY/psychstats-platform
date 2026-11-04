"""Zero-model local migration verification; outputs metadata, never paper text."""
import argparse
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from rag.paths import input_path


def main(output):
    from term_explainer.online.sources import parse_source
    from term_explainer.online.config import load_config
    from term_explainer.figures import render_visual
    from term_explainer.figure_qa.audit_figure_collisions import audit_pdf
    from tests.term_explainer.online.helpers import environment
    from tests.term_explainer.online.test_pdf_migration import make_pdf
    from tests.term_explainer.helpers import result_payload
    output=Path(output).resolve()
    if output.exists():raise FileExistsError('QA output is immutable')
    output.mkdir(parents=True)
    if importlib.util.find_spec('pymupdf') or importlib.util.find_spec('fitz'):raise RuntimeError('Expected a PyMuPDF-free environment')
    limits=load_config(environment(output/'private')).limits
    supplied=input_path('PSY_STATS_DTP_PDF','data/papers/dtp.pdf')
    teaching=output/'private'/'controlled.pdf';teaching.parent.mkdir(parents=True,exist_ok=True);make_pdf(teaching)
    sources=[]
    for label,path in [('controlled',teaching),('user-dtp',supplied)]:
        started=time.perf_counter()
        result=parse_source(path,dict(id='s',name=path.name,title=path.name,mime='application/pdf'),limits)
        text=result['source']['text']
        if not all(text.startswith(h['title'],h['start']) for h in result['headings']):raise AssertionError('Heading offset mismatch')
        sources.append(dict(case=label,seconds=time.perf_counter()-started,characters=len(text),headingCount=len(result['headings']),textSha256=hashlib.sha256(text.encode()).hexdigest(),extraction=result['extraction'],warnings=len(result['warnings'])))
    live=ROOT/'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live'
    paths=[live/'dtp-user-pdf/dtp-complete-run/preview/figures',live/'dtp-user-pdf/dtp-multi-literature-run/preview/figures',live/'cognitive-drift-generation-v3/preview/figures']
    figures=[]
    for folder in paths:
        for path in [folder/'figure.pdf',folder/'figure-mobile.pdf']:
            if not path.is_file():raise FileNotFoundError(path)
            result=audit_pdf(path)
            figures.append(dict(case=folder.parent.parent.name,file=path.name,verdict=result['verdict'],summary=result['summary'],findings=[dict(kind=f['kind'],severity=f['severity']) for f in result['findings']]))
    # Real end-to-end render + external font, alignment, collision subprocesses.
    assets=render_visual(result_payload()['visual'],output/'rendered')
    report=dict(pymupdfInstalled=False,newModelCalls=0,newNetworkReads=0,sources=sources,existingFigures=figures,realRenderAudit=json.loads(Path(assets.audit).read_bytes()))
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(sources=sources,figures=len(figures),verdicts=[f['verdict'] for f in figures],externalQa='completed',newModelCalls=0),ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.output)
