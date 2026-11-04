"""Runtime contract: PDF text is located, versioned, and bounded without fitz."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from term_explainer.online.sources import parse_source
from term_explainer.online.config import load_config, OnlineError
from .helpers import OnlineCase


def make_pdf(path, *, blank=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(path, metadata={'Title': 'A Clear Research Title'}) as pdf:
        fig=plt.figure(figsize=(8,10))
        if not blank:
            fig.text(.08,.92,'A Clear Research Title',fontsize=20)
            fig.text(.08,.80,'Introduction',fontsize=14)
            fig.text(.08,.74,'One branch concerns cognitive drift.',fontsize=10)
            fig.text(.08,.58,'Methods',fontsize=14)
            fig.text(.08,.52,'Records are compared within a person.',fontsize=10)
        pdf.savefig(fig);plt.close(fig)


class PdfMigrationTests(OnlineCase):
    def test_doi_is_taken_from_header_not_reference_list(self):
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        path=self.root/'header.pdf'
        with PdfPages(path,metadata={'Title':'Microsoft Word - private-name'}) as pdf:
            fig=plt.figure(figsize=(8,10))
            for y,value,size in [(.95,'DOI: 10.1234/article',9),(.89,'A Located Research Article',20),
                (.75,'Introduction',14),(.68,'The body explains the concept.',10),
                (.5,'References',14),(.42,'Other article DOI: 10.5678/reference',10)]:
                fig.text(.08,y,value,fontsize=size)
            pdf.savefig(fig);plt.close(fig)
        doc=self.parse(path)
        self.assertEqual(doc['source']['doi'],'10.1234/article')
        self.assertEqual(doc['identity_review']['status'],'matches')

    def test_custom_body_heading_cannot_lend_cited_doi_to_article_identity(self):
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        path=self.root/'custom.pdf'
        with PdfPages(path,metadata={'Title':'A Located Research Article'}) as pdf:
            fig=plt.figure(figsize=(8,10))
            for y,value,size in [(.92,'A Located Research Article',20),
                (.79,'Theoretical background',14),(.70,'See earlier work: 10.5678/cited-paper',10),
                (.5,'References',14),(.4,'Other work.',10)]:
                fig.text(.08,y,value,fontsize=size)
            pdf.savefig(fig);plt.close(fig)
        doc=self.parse(path)
        self.assertEqual(doc['source']['doi'],'')
        descriptor=dict(id='s',title=path.name,name=path.name,mime='application/pdf',doi='10.5678/cited-paper')
        doc=parse_source(path,descriptor,load_config(self.env).limits)
        self.assertIsNone(doc['identity_review'])


    def test_word_metadata_is_replaced_by_located_article_title(self):
        from pypdf import PdfReader,PdfWriter
        path=self.root/'paper.pdf';make_pdf(path)
        writer=PdfWriter(clone_from=PdfReader(path))
        writer.add_metadata({'/Title':'Microsoft Word - internal-draft.docx'})
        with path.open('wb') as stream:writer.write(stream)
        doc=self.parse(path)
        self.assertEqual(doc['source']['title'],'A Clear Research Title')
        self.assertEqual(doc['identity_review']['status'],'matches')

    def test_real_two_column_pdf_is_ordered_and_every_character_has_a_legacy_location(self):
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        from term_explainer.pdf_runtime import extract_document
        path=self.root/'columns.pdf'
        with PdfPages(path,metadata={'Title':'Microsoft Word - manuscript.docx'}) as pdf:
            fig=plt.figure(figsize=(8,10))
            for x,y,value,size in [(.08,.94,'A Located Research Article',20),
                (.08,.84,'Introduction',14),(.56,.84,'Methods',14),
                (.08,.76,'Left column first paragraph.',10),(.56,.76,'Right column first paragraph.',10),
                (.08,.67,'Left column second paragraph.',10),(.56,.67,'Right column second paragraph.',10)]:
                fig.text(x,y,value,fontsize=size)
            pdf.savefig(fig);plt.close(fig)
        doc=self.parse(path);text=doc['source']['text']
        self.assertLess(text.index('Left column second'),text.index('Methods'))
        self.assertEqual(doc['identity_review']['status'],'matches')
        extracted=extract_document(path.read_bytes(),max_pages=3,max_chars=120000)
        for part,mapping in zip(extracted['parts'],extracted['extraction']['page_offset_map']):
            self.assertEqual([m['start'] for m in mapping],[0]+[m['end'] for m in mapping[:-1]])
            self.assertEqual(mapping[-1]['end'],len(part))
            spans=sorted(mapping,key=lambda m:m['legacy_start'])
            self.assertEqual([m['legacy_start'] for m in spans],[0]+[m['legacy_end'] for m in spans[:-1]])
            self.assertEqual(spans[-1]['legacy_end'],len(part))


    def parse(self,path,limits=None):
        return parse_source(path,dict(id='s',title=path.name,name=path.name,mime='application/pdf'),limits or load_config(self.env).limits)

    def test_extraction_is_versioned_and_headings_use_exact_new_text(self):
        path=self.root/'paper.pdf';make_pdf(path)
        doc=self.parse(path)
        self.assertEqual(doc['extraction']['engine'],'pdfminer.six')
        self.assertTrue(doc['extraction']['version'])
        self.assertEqual(doc['source']['title'],'A Clear Research Title')
        self.assertIn('Methods',[h['title'] for h in doc['headings']])
        for h in doc['headings']:self.assertTrue(doc['source']['text'].startswith(h['title'],h['start']))

    def test_character_limit_rejects_whole_document(self):
        path=self.root/'paper.pdf';make_pdf(path)
        with self.assertRaises(OnlineError) as caught:self.parse(path,replace(load_config(self.env).limits,max_text_chars=20))
        self.assertEqual(caught.exception.status,413)

    def test_encryption_scan_page_and_file_limits_are_preserved(self):
        from .pdf_fixtures import document
        path=self.root/'encrypted.pdf';document(path,[[('Introduction',14,.8)]],encrypt='private')
        with self.assertRaises(OnlineError) as c:self.parse(path)
        self.assertEqual(c.exception.code,'source_unreadable')
        document(path,[[]])
        with self.assertRaises(OnlineError) as c:self.parse(path)
        self.assertEqual(c.exception.code,'source_unreadable')
        document(path,[[('Introduction',14,.8)],[('Methods',14,.8)]])
        with self.assertRaises(OnlineError) as c:self.parse(path,replace(load_config(self.env).limits,max_pages=1))
        self.assertEqual(c.exception.status,413)
        with self.assertRaises(OnlineError) as c:self.parse(path,replace(load_config(self.env).limits,max_file_bytes=10))
        self.assertEqual(c.exception.code,'file_too_large')
