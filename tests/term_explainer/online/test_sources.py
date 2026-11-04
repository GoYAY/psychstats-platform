from dataclasses import replace
from term_explainer.online.sources import parse_source
from term_explainer.online.config import load_config,OnlineError
from .helpers import OnlineCase

class SourceTests(OnlineCase):
    def test_exact_document_title_creates_located_identity_not_method_approval(self):
        from term_explainer.online.sources import exact_identity_review,normalize_pdf_text
        from term_explainer.section_quality import validate_identity_review
        source=dict(id='s',title='A Research Title',authors=[],year=None,doi='',text='Front\nA Research\nTitle\nIntroduction\nContent')
        review=exact_identity_review(source)
        self.assertEqual(validate_identity_review(review,source)['status'],'matches')
        self.assertIsNone(exact_identity_review(dict(source,title='A Different Paper')))
        self.assertIsNone(exact_identity_review(dict(source,doi='10.1234/not-in-this-file')))
        clean,warnings=normalize_pdf_text('Known\x00unknown')
        self.assertEqual(clean,'Known\ufffdunknown');self.assertTrue(warnings)

    def test_pdf_uses_real_bookmarks_and_typographic_headings_not_equations(self):
        from .pdf_fixtures import document
        path=self.root/'structured.pdf'
        document(path,[[('A Clear Research Title',18,.92),('1 + exp z\n2020) as well as a sentence\nPlain text content.',10,.8)],
                       [('A Branch Concept',13,.92),('Reading a branch of the main research topic.',10,.8)]],bookmark=('A Branch Concept',1))
        doc=parse_source(path,{'id':'s','name':'structured.pdf','title':'structured.pdf','mime':'application/pdf'},load_config(self.env).limits)
        self.assertIn('A Branch Concept',[h['title'] for h in doc['headings']])
        self.assertNotIn('1 + exp z',[h['title'] for h in doc['headings']])
        self.assertNotIn('2020) as well as a sentence',[h['title'] for h in doc['headings']])

    def test_verified_pdf_metadata_title_precedes_upload_filename(self):
        from .pdf_fixtures import document
        path=self.root/'opaque.pdf'
        document(path,[[('Introduction\nA research concept.',11,.9)]],title='A Verified Research Title')
        doc=parse_source(path,{'id':'s','title':'opaque.pdf','name':'opaque.pdf','mime':'application/pdf'},load_config(self.env).limits)
        self.assertEqual(doc['source']['title'],'A Verified Research Title')

    def test_text_sections_are_exact_offsets_and_not_percentage_slices(self):
        path=self.root/'paper.txt';text='# Introduction\nA concept.\n\n# Methods\nHow it works.\n\n# References\nAuthor 2025.';path.write_text(text,encoding='utf-8')
        doc=parse_source(path,{'id':'source-1','title':'Paper','mime':'text/plain'},load_config(self.env).limits)
        self.assertEqual(doc['source']['text'],text)
        self.assertEqual([h['title'] for h in doc['headings']],['# Introduction','# Methods','# References'])
        for h in doc['headings']:self.assertTrue(text.startswith(h['title'],h['start']))

    def test_fake_pdf_and_oversized_text_are_rejected_without_truncation(self):
        path=self.root/'fake.pdf';path.write_bytes(b'not a pdf')
        with self.assertRaises(OnlineError):parse_source(path,{'id':'s','title':'p','mime':'application/pdf'},load_config(self.env).limits)
        path.write_bytes(b'abcde')
        with self.assertRaises(OnlineError):parse_source(path,{'id':'s','title':'p','mime':'text/plain'},replace(load_config(self.env).limits,max_text_chars=4))

    def test_scanned_or_encrypted_pdf_requests_readable_material(self):
        from .pdf_fixtures import document
        path=self.root/'scan.pdf';document(path,[[]])
        with self.assertRaises(OnlineError) as c:parse_source(path,{'id':'s','title':'scan','mime':'application/pdf'},load_config(self.env).limits)
        self.assertEqual(c.exception.code,'source_unreadable')
