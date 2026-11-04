"""Actual PDF fixtures catch omissions in path, glyph and clipping extraction."""
from pathlib import Path
import tempfile
import unittest


def raw_pdf(path,content,depth=0):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,ArrayObject,NumberObject,DecodedStreamObject
    writer=PdfWriter();page=writer.add_blank_page(300,200)
    font=writer._add_object(DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')}))
    fonts=DictionaryObject({NameObject('/F1'):font})
    resources=DictionaryObject({NameObject('/Font'):fonts})
    for _ in range(depth):
        form=DecodedStreamObject();form.set_data(content)
        form.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Form'),NameObject('/BBox'):ArrayObject([NumberObject(x) for x in [0,0,300,200]]),NameObject('/Resources'):resources})
        ref=writer._add_object(form)
        resources=DictionaryObject({NameObject('/Font'):fonts,NameObject('/XObject'):DictionaryObject({NameObject('/F'):ref})})
        content=b'/F Do'
    stream=DecodedStreamObject();stream.set_data(content)
    page[NameObject('/Contents')]=writer._add_object(stream);page[NameObject('/Resources')]=resources
    writer.write(path)


def fixture(path,mode):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.path import Path as MPath
    from matplotlib.patches import PathPatch
    plt.rcParams['pdf.fonttype']=42
    fig=plt.figure(figsize=(4,3));fig.text(.35,.5,'READABLE',fontsize=16)
    if mode=='text':fig.text(.36,.5,'OVERLAP',fontsize=16)
    if mode in ('line','transparent'):
        fig.add_artist(plt.Line2D([.2,.9],[.52,.52],transform=fig.transFigure,alpha=0 if mode=='transparent' else 1))
    if mode=='curve':
        pathdata=MPath([(.2,.52),(.4,.52),(.6,.52),(.9,.52)],[1,4,4,4])
        fig.add_artist(PathPatch(pathdata,transform=fig.transFigure,fill=False))
    if mode=='fill':fig.add_artist(plt.Rectangle((.3,.45),.1,.15,transform=fig.transFigure,facecolor='red'))
    if mode=='image':fig.figimage(__import__('numpy').ones((80,40,3)),xo=130,yo=145)
    if mode=='clip':fig.text(.99,.2,'OUTSIDE',fontsize=16)
    fig.savefig(path);plt.close(fig)


class PermissiveQaTests(unittest.TestCase):
    def test_deep_form_is_never_reported_as_partially_audited_pass(self):
        from term_explainer.figure_qa.audit_figure_collisions import audit_pdf
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'forms.pdf'
            content=b'BT /F1 16 Tf 50 100 Td (HELLO) Tj ET 40 105 m 150 105 l S'
            raw_pdf(path,content,depth=1)
            self.assertIn('text-stroke',[f['kind'] for f in audit_pdf(path)['findings']])
            raw_pdf(path,content,depth=16)
            with self.assertRaisesRegex(RuntimeError,'Form.*depth'):audit_pdf(path)

    def test_compound_rectangles_do_not_hide_a_partial_text_cover(self):
        from term_explainer.figure_qa.audit_figure_collisions import audit_pdf
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'fills.pdf'
            raw_pdf(path,b'BT /F1 16 Tf 50 100 Td (HELLO) Tj ET 45 95 20 25 re 250 180 20 15 re f')
            self.assertIn('text-fill-edge',[f['kind'] for f in audit_pdf(path)['findings']])

    def test_runtime_collision_checks_preserve_positive_and_negative_controls(self):
        from term_explainer.figure_qa.audit_figure_collisions import audit_pdf
        with tempfile.TemporaryDirectory() as tmp:
            for mode,kind in [('clean',None),('transparent',None),('line','text-stroke'),('curve','text-stroke'),('text','text-text'),('fill','text-fill-edge'),('image','text-image-edge'),('clip','text-page-clipping')]:
                with self.subTest(mode=mode):
                    path=Path(tmp)/f'{mode}.pdf';fixture(path,mode);result=audit_pdf(path)
                    if kind:self.assertIn(kind,[f['kind'] for f in result['findings']])
                    else:self.assertEqual(result['verdict'],'PASS')

    def test_overlay_preserves_source_and_renders_with_pdfium(self):
        from term_explainer.figure_qa.audit_figure_collisions import audit_pdf,write_overlay_pdf
        import pypdfium2 as pdfium
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.pdf';fixture(path,'line');original=path.read_bytes()
            result=audit_pdf(path);output=Path(tmp)/'overlay.pdf'
            write_overlay_pdf(path,output,result['findings'])
            self.assertEqual(path.read_bytes(),original)
            with self.assertRaises(ValueError):write_overlay_pdf(path,path,result['findings'])
            with pdfium.PdfDocument(output) as pdf:
                bitmap=pdf[0].render(scale=1,draw_annots=True)
                self.assertGreater(bitmap.width,100);bitmap.close()

    def test_rotated_and_cropped_page_keep_collisions_located(self):
        from term_explainer.figure_qa.audit_figure_collisions import audit_pdf
        from pypdf import PdfReader,PdfWriter
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.pdf';fixture(path,'line')
            for angle in (0,90,180,270):
                writer=PdfWriter();page=PdfReader(path).pages[0]
                page.cropbox.lower_left=(20,10);page.rotate(angle);writer.add_page(page)
                out=Path(tmp)/f'rot{angle}.pdf';writer.write(out)
                self.assertIn('text-stroke',[f['kind'] for f in audit_pdf(out)['findings']])
