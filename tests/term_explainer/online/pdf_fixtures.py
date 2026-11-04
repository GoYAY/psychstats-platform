"""Test-only PDF authoring, using the same permissive dependency closure."""
from io import BytesIO


def document(path,pages,*,title='',bookmark=None,encrypt=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from pypdf import PdfReader,PdfWriter
    stream=BytesIO()
    with PdfPages(stream,metadata={'Title':title}) as pdf:
        for rows in pages:
            fig=plt.figure(figsize=(8,10))
            for text,size,y in rows:fig.text(.06,y,text,fontsize=size)
            pdf.savefig(fig);plt.close(fig)
    stream.seek(0);writer=PdfWriter(clone_from=PdfReader(stream))
    if bookmark:writer.add_outline_item(bookmark[0],bookmark[1])
    if encrypt is not None:writer.encrypt(encrypt)
    writer.write(path)
