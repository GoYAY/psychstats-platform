"""Project adapter: PDFium tight glyphs/paths, pypdf diagnostic annotations.

Coordinates stay unrotated in PDF page space with y reversed at crop top.
All geometry (including nested Form XObjects) uses that same space. Rotation
is a display transform and therefore does not change collision relationships.
PDFium is only used inside the serial QA subprocess, never concurrent threads.
"""
import ctypes
import math
import os
from pathlib import Path
import tempfile


def extract(path,types):
    import pypdfium2 as p
    G,T,R,S,F,union,cubic=types
    raw=p.raw;pages=[]
    def color_alpha(obj,stroke):
        values=[ctypes.c_uint() for _ in range(4)]
        method=raw.FPDFPageObj_GetStrokeColor if stroke else raw.FPDFPageObj_GetFillColor
        if not method(obj,*values):raise RuntimeError('Cannot audit PDF object opacity')
        return values[-1].value
    with p.PdfDocument(path) as doc:
        for index in range(len(doc)):
            page=doc[index]
            left,bottom,right,top=page.get_bbox()
            def point(x,y):return (float(x),top-float(y))
            def box(rect):
                l,b,r,t=rect
                return (min(l,r),top-max(b,t),max(l,r),top-min(b,t))
            geo=G(page=index+1,bbox=(left,0,right,top-bottom))
            tp=page.get_textpage()
            try:
                # Group by actual PDF text object, not baseline: independent
                # overlapping labels must stay independent audit candidates.
                groups={}
                for i in range(tp.count_chars()):
                    code=raw.FPDFText_GetUnicode(tp,i)
                    char=chr(code) if code else '\ufffd'
                    if char.isspace():continue
                    obj=tp.get_textobj(i)
                    if obj and raw.FPDFTextObj_GetTextRenderMode(obj)==3:continue
                    key=ctypes.cast(obj.raw,ctypes.c_void_p).value if obj else ('glyph',i)
                    bounds=box(tp.get_charbox(i))
                    if not all(math.isfinite(v) for v in bounds):raise RuntimeError('Non-finite PDF glyph geometry')
                    if bounds[0]==bounds[2] or bounds[1]==bounds[3]:continue
                    # Line breaks within a PDF object also split audit boxes.
                    rows=groups.setdefault(key,[])
                    if not rows or abs(rows[-1][2]-bounds[3])>max(2,(bounds[3]-bounds[1])*.6):
                        rows.append([[],[],bounds[3]])
                    rows[-1][0].append(char);rows[-1][1].append(bounds)
                for rows in groups.values():
                    for chars,bounds,_ in rows:
                        i=len(geo.texts);rect=union(bounds);text=''.join(chars)
                        geo.texts.append(T(i,text,rect));geo.traces.append(R(i,text,rect))
                max_form_depth=15
                for n,obj in enumerate(page.get_objects(max_depth=max_form_depth)):
                    if obj.type==raw.FPDF_PAGEOBJ_FORM and obj.level+1>=max_form_depth and raw.FPDFFormObj_CountObjects(obj)>0:
                        raise RuntimeError('PDF Form nesting exceeds audit depth; incomplete geometry rejected')
                    # get_bounds includes the object's own matrix; outer Form
                    # matrices are composed separately (local -> parent -> page).
                    parent_matrix=p.PdfMatrix();parent=obj.container
                    while parent is not None:
                        parent_matrix=parent_matrix.multiply(parent.get_matrix());parent=parent.container
                    bounds=box(parent_matrix.on_rect(*obj.get_bounds()))
                    if obj.type==raw.FPDF_PAGEOBJ_IMAGE:
                        geo.images.append(F(n,bounds,'image'));continue
                    if obj.type!=raw.FPDF_PAGEOBJ_PATH:continue
                    matrix=obj.get_matrix().multiply(parent_matrix)
                    fill=ctypes.c_int();stroke=ctypes.c_int()
                    if not raw.FPDFPath_GetDrawMode(obj,fill,stroke):raise RuntimeError('Cannot audit path draw mode')
                    segments=[];current=None;start=None;controls=[];subpaths=[];subpath=[]
                    for k in range(raw.FPDFPath_CountSegments(obj)):
                        part=raw.FPDFPath_GetPathSegment(obj,k);x=ctypes.c_float();y=ctypes.c_float()
                        if not raw.FPDFPathSegment_GetPoint(part,x,y):raise RuntimeError('Cannot audit path point')
                        pos=point(*matrix.on_point(x.value,y.value));kind=raw.FPDFPathSegment_GetType(part)
                        if kind==raw.FPDF_SEGMENT_MOVETO:
                            if subpath:subpaths.append(subpath)
                            current=start=pos;controls=[];subpath=[pos]
                        elif kind==raw.FPDF_SEGMENT_LINETO:
                            if current is not None:segments.append((current,pos))
                            current=pos;subpath.append(pos)
                        elif kind==raw.FPDF_SEGMENT_BEZIERTO:
                            controls.append(pos)
                            if len(controls)==3:
                                if current is not None:
                                    curved=cubic([current,*controls]);segments.extend(curved);subpath.extend(s[1] for s in curved)
                                current=pos;controls=[]
                        else:raise RuntimeError('Unsupported PDF path segment')
                        if raw.FPDFPathSegment_GetClose(part) and current is not None and start is not None:
                            segments.append((current,start));current=start
                    if stroke.value and color_alpha(obj,True):
                        width=ctypes.c_float()
                        if not raw.FPDFPageObj_GetStrokeWidth(obj,width):raise RuntimeError('Cannot audit stroke width')
                        scale=max(math.hypot(matrix.a,matrix.b),math.hypot(matrix.c,matrix.d))
                        geo.strokes.append(S(n,bounds,width.value*scale,tuple(segments)))
                    if subpath:subpaths.append(subpath)
                    if fill.value and color_alpha(obj,False):
                        # A compound path's overall bounds can look like a page
                        # background even when one small subpath covers a label.
                        # Preserve disjoint subpath extents, matching the prior
                        # audit's per-rectangle fill semantics.
                        for offset,points in enumerate(subpaths):
                            xs,ys=zip(*points)
                            geo.fills.append(F(n*1000+offset,(min(xs),min(ys),max(xs),max(ys)),'fill'))
            finally:tp.close();page.close()
            pages.append(geo)
    return pages


def overlay(source,destination,findings):
    from pypdf import PdfReader,PdfWriter
    from pypdf.annotations import Rectangle
    from pypdf.generic import ArrayObject,FloatObject,NameObject,NumberObject
    source=Path(source);destination=Path(destination)
    if source.resolve()==destination.resolve():raise ValueError('overlay PDF must not overwrite source PDF')
    writer=PdfWriter(clone_from=PdfReader(source))
    for finding in findings:
        i=int(finding['page'])-1
        if not 0<=i<len(writer.pages):continue
        page=writer.pages[i];top=min(float(page.mediabox.top),float(page.cropbox.top))
        for key,width in [('text_bbox',1.2),('other_bbox',.6)]:
            rect=finding.get(key)
            if not rect:continue
            l,t,r,b=rect;annotation=Rectangle(rect=(l,top-b,r,top-t))
            color=[.9,.05,.05] if finding['severity']=='FAIL' else [1,.55,0]
            annotation[NameObject('/C')]=ArrayObject([FloatObject(v) for v in color])
            annotation[NameObject('/F')]=NumberObject(4)
            from pypdf.generic import DictionaryObject
            border=DictionaryObject({NameObject('/W'):FloatObject(width)})
            if key=='other_bbox':border[NameObject('/S')]=NameObject('/D');border[NameObject('/D')]=ArrayObject([NumberObject(2),NumberObject(2)])
            annotation[NameObject('/BS')]=border
            writer.add_annotation(i,annotation)
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+destination.stem+'.',suffix='.tmp.pdf',dir=destination.parent)
    os.close(fd)
    try:writer.write(name);Path(name).replace(destination)
    finally:
        if Path(name).exists():Path(name).unlink()
