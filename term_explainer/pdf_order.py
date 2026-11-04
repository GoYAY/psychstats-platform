"""Conservative two-column ordering with a lossless legacy-offset map.

Only moves complete located text boxes. Unknown geometry/text falls back to
the original extraction, rather than guessing or recreating glyphs.
"""


def order_page(text, boxes, width):
    original=[dict(start=0,end=len(text),legacy_start=0,legacy_end=len(text))]
    if not boxes or not width:return text,original
    located=[];cursor=0
    for box in boxes:
        value=box.get('text','');bbox=box.get('bbox')
        if not value or not bbox:return text,original
        at=text.find(value,cursor)
        if at<0:return text,original
        # Non-whitespace outside boxes may be figure text. Do not relocate it.
        if text[cursor:at].strip():return text,original
        located.append(dict(box,start=at));cursor=at+len(value)
    if text[cursor:].strip():return text,original
    middle=width/2;gutter=width*.002
    def side(box):
        x0,_,x1,_=box['bbox']
        if x1<=middle-gutter:return 'left'
        if x0>=middle+gutter:return 'right'
        return 'wide'
    if sum(side(b)=='left' for b in located)<2 or sum(side(b)=='right' for b in located)<2:
        return text,original
    for i,box in enumerate(located):
        box['legacy_start']=box['start'] if i else 0
        box['legacy_end']=located[i+1]['start'] if i+1<len(located) else len(text)
    wide=sorted((b for b in located if side(b)=='wide'),key=lambda b:-b['bbox'][3])
    rows=[[w] for w in wide]
    bands=[[] for _ in range(len(wide)+1)]
    for box in located:
        if side(box)=='wide':continue
        center=(box['bbox'][1]+box['bbox'][3])/2
        # Ambiguous overlap with full-width material cannot safely be reordered.
        overlapping=[i for i,w in enumerate(wide) if w['bbox'][1]<center<w['bbox'][3]]
        if overlapping:
            if len(overlapping)!=1:return text,original
            i=overlapping[0];w=wide[i]
            if not(box['bbox'][2]<=w['bbox'][0] or box['bbox'][0]>=w['bbox'][2]):return text,original
            rows[i].append(box);continue
        index=sum(center<(w['bbox'][1]+w['bbox'][3])/2 for w in wide)
        bands[index].append(box)
    ordered=[]
    for i,band in enumerate(bands):
        ordered.extend(sorted(band,key=lambda b:(side(b)=='right',-b['bbox'][3],b['bbox'][0])))
        if i<len(wide):ordered.extend(sorted(rows[i],key=lambda b:b['bbox'][0]))
    chunks=[];mapping=[];offset=0
    for box in ordered:
        chunk=text[box['legacy_start']:box['legacy_end']]
        chunks.append(chunk)
        mapping.append(dict(start=offset,end=offset+len(chunk),legacy_start=box['legacy_start'],legacy_end=box['legacy_end'],bbox=list(box['bbox'])))
        offset+=len(chunk)
    return ''.join(chunks),mapping
