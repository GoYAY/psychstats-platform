"""Located literature extraction. One layout parse supplies text and typography.

Extraction versions belong to NEW document records. Persisted records retain
their original text/offsets; this module never reinterprets old checkpoints.
"""
from importlib.metadata import version
from io import BytesIO, StringIO
import hashlib
from .pdf_order import order_page


def extract_document(raw, *, max_pages, max_chars):
    import pdfplumber
    from pdfminer.converter import TextConverter
    from pdfminer.layout import LTTextBox, LTTextLine, LTChar
    from pypdf import PdfReader
    from .online.config import OnlineError
    reader=PdfReader(BytesIO(raw),strict=True)
    if reader.is_encrypted:
        raise OnlineError('source_unreadable','请提供可以读取文字的未加密材料。')
    if len(reader.pages)>max_pages:
        raise OnlineError('source_too_large','PDF页数超过本轮限制。',413)
    toc=[]
    def outlines(rows,level=1):
        for row in rows:
            if isinstance(row,list):outlines(row,level+1)
            else:
                page=reader.get_destination_page_number(row)
                if page is not None:toc.append((level,row.title,page+1))
    outlines(reader.outline)
    title=(reader.metadata.title or '') if reader.metadata else ''
    parts=[];layouts=[];count=0;offset_map=[];legacy_parts=[]
    with pdfplumber.open(BytesIO(raw),laparams={}) as pdf:
        for page in pdf.pages:
            layout=page.layout
            stream=StringIO();device=TextConverter(pdf.rsrcmgr,stream)
            try:device.receive_layout(layout);text=stream.getvalue().rstrip('\x0c')
            finally:device.close()
            count+=len(text)
            if count>max_chars:
                raise OnlineError('source_too_large','文字超过当前单篇阅读限制，未截断材料。',413)
            blocks=[];boxes=[]
            def collect(node):
                if isinstance(node,LTTextBox):
                    lines=[]
                    for line in node:
                        if not isinstance(line,LTTextLine):continue
                        chars=[c for c in line if isinstance(c,LTChar)]
                        if not chars:continue
                        # Keep synthetic spaces exactly as in the extracted line.
                        lines.append({'spans':[dict(text=line.get_text().rstrip('\n'),size=max(c.size for c in chars),flags=16 if all('bold' in c.fontname.casefold() for c in chars) else 0)]})
                    blocks.append(dict(lines=lines,bbox=list(node.bbox)))
                    boxes.append(dict(text=node.get_text(),bbox=list(node.bbox)))
                elif hasattr(node,'__iter__'):
                    for child in node:collect(child)
            collect(layout)
            legacy_parts.append(text)
            text,mapping=order_page(text,boxes,page.width)
            offset_map.append(mapping);parts.append(text)
            layouts.append(dict(blocks=blocks));page.close()
    return dict(parts=parts,layouts=layouts,toc=toc,title=title,
                extraction=dict(engine='pdfminer.six',version=version('pdfminer.six'),layout_version=2,
                    text_sha256=hashlib.sha256('\n'.join(parts).encode()).hexdigest(),
                    legacy_text_sha256=hashlib.sha256('\n'.join(legacy_parts).encode()).hexdigest(),
                    page_offset_map=offset_map))
