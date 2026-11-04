"""Prepare selected, source-mapped method sections from two lawfully acquired PDFs."""
from pathlib import Path
import hashlib,json,re,sys
import pymupdf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.read_term_sections import atomic_write


def select_sections(text,bounds):
    chosen=[];mapping=[]
    for begin,finish in bounds:
        first=re.search(begin,text,re.I)
        if not first:raise ValueError('Section heading not found: '+begin)
        last=re.search(finish,text[first.end():],re.I)
        if not last:raise ValueError('Section end not found: '+finish)
        start,end=first.start(),first.end()+last.start()
        prefix='\n\n' if chosen else ''
        offset=sum(map(len,chosen))+len(prefix)
        chosen.append(prefix+text[start:end])
        mapping.append(dict(selected_start=offset,selected_end=offset+end-start,original_start=start,original_end=end))
    return ''.join(chosen),mapping


def main():
    base=Path(__file__).resolve().parents[1]/'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live/dtp-user-pdf/related-literature'
    papers=[dict(id='brown2011',title='Item Response Modeling of Forced-Choice Questionnaires',doi='10.1177/0013164410375112',year=2011,
        authors=['Anna Brown','Alberto Maydeu-Olivares'],url='https://kar.kent.ac.uk/29626/1/IRT_modeling_of_FC_tests_FINAL.pdf',
        bounds=[(r'The most popular way of presenting questionnaire items',r'Applying\s+A\s+Thurstonian\s+Factor\s+Model\s+To\s+Forced-Choice\s+Questionnaires'),
                (r'Applying\s+A\s+Thurstonian\s+Factor\s+Model\s+To\s+Forced-Choice\s+Questionnaires',r'Identification\s+Of\s+Thurstonian\s+IRT\s+Models')]),
        dict(id='nie2024',title='Multidimensional IRT for forced choice tests: A literature review',doi='10.1016/j.heliyon.2024.e26884',year=2024,
        authors=['Lei Nie','Peiyi Xu','Di Hu'],url='https://pmc.ncbi.nlm.nih.gov/articles/PMC10915382/',
        bounds=[(r'2\.\s*IRT model for multidimensional forced choice test',r'2\.1\.1\.\s*Response format'),
                (r'2\.1\.2\.\s*Measurement model',r'2\.1\.3\.\s*Decision theory'),
                (r'2\.2\.1\.\s*TIRT model',r'2\.2\.2\.')])]
    sources=[]
    for paper in papers:
        matches=list((base/paper['id']/'PDFs').glob('*.pdf'))
        if len(matches)!=1:raise ValueError('Expected one verified main PDF')
        file=matches[0];raw=file.read_bytes()
        if not raw.startswith(b'%PDF'):raise ValueError('Not a PDF')
        with pymupdf.open(file) as doc:
            pages=[p.get_text() for p in doc]
        full='\n\n'.join(pages)
        normalized=lambda t:re.sub(r'\W','',t).casefold()
        if normalized(paper['title']) not in normalized(full[:12000]):raise ValueError('Title mismatch')
        text,mapping=select_sections(full,paper.pop('bounds'))
        source=dict(paper,text=text,scope='excerpt',origin='reference',technical_evidence_eligible=True,references=[],
            retrieved_title=paper['title'],retrieved_url=paper['url'],scope_basis='selected_related_method_sections_not_full_paper_read',
            selection_mapping=mapping,pdf_sha256=hashlib.sha256(raw).hexdigest(),pdf_pages=len(pages),
            reading_scope='Only selected introduction/framework/model sections are supplied; not a claim of full-paper deep reading.')
        atomic_write(base/paper['id']/'extracted-source.json',dict(text=full,pages=len(pages),pdf_sha256=source['pdf_sha256']))
        sources.append(source)
    atomic_write(base/'selected-sources.json',dict(sources=sources,si_requested=True,
        si_status={'brown2011':'none_on_repository_landing_publisher_access_unavailable','nie2024':'no_attachment_in_accessible_PMC_associated_data'}))
    print(json.dumps(dict(sources=[dict(id=s['id'],chars=len(s['text']),pages=s['pdf_pages']) for s in sources],new_model_calls=0),indent=2))


if __name__=='__main__':main()
