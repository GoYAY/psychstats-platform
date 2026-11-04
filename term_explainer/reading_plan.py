"""Deterministic reading-plan: merge adjacent small sections into reading
units.  Original headings/sections stay recorded; every unit maps back to
absolute source offsets.  Bibliography/front-matter never merge with body.
Plan is computed once per new task and checkpointed; resumed tasks reuse it.
"""
import re

PLAN_VERSION=1
SMALL=600;LOW=2500;HIGH=8000;CAP=8000;MAX_MERGE=6
_PARENT=re.compile(r'^\s*(\d+(?:\.\d+)*)')

def _role(section):
    role=section.get('role')
    if role:return role
    title=(section.get('title') or '')
    if re.fullmatch(r'(?:参\s*考\s*文\s*献|致\s*谢|References|Acknowledg\w*)',title.strip(),re.I):return 'bibliography'
    return 'body'

def _parent(title):
    match=_PARENT.match(title or '')
    return match.group(1).split('.')[0] if match else ''

def build_units(sections,*,plan_version=PLAN_VERSION,small=SMALL,low=LOW,high=HIGH,cap=CAP,max_merge=MAX_MERGE):
    units=[];cur=[]
    def flush():
        if not cur:return
        first,last=cur[0],cur[-1]
        unit_id=f'unit-{len(units)+1:03d}'
        units.append(dict(id=unit_id,unit_id=unit_id,
            title=first['title'],start=first['start'],end=last['end'],
            chars=last['end']-first['start'],role=_role(first),
            parent=_parent(first['title']),plan_version=plan_version,
            merged=len(cur)>1,section_ids=[s['id'] for s in cur],
            section_titles=[s['title'] for s in cur]))
        cur.clear()
    for s in sections:
        role=_role(s);chars=s['end']-s['start']
        if role!='body':
            flush();cur=[s];flush();continue
        if not cur:cur=[s]
        else:
            span=cur[-1]['end']-cur[0]['start']
            if (len(cur)<max_merge and span+chars<=cap
                and (span<low or chars<small)):
                cur.append(s)
            else:
                flush();cur=[s]
        if s['end']-s['start']>=low:flush()
    flush()
    return units


def validate_units(units,sections,text):
    """Prove full coverage: no gaps, no overlap, body text identical."""
    if not units:raise ValueError('reading plan: no units')
    previous=0
    body_source=[(s['start'],s['end']) for s in sections if _role(s)=='body']
    covered=[]
    for unit in units:
        if unit['start']!=previous:raise ValueError('reading plan: gap or overlap at '+unit['unit_id'])
        if not 0<=unit['start']<unit['end']<=len(text):raise ValueError('reading plan: unit out of bounds')
        covered.append((unit['start'],unit['end']));previous=unit['end']
        joined=text[unit['start']:unit['end']]
        for sid in unit['section_ids']:
            match=next((s for s in sections if s['id']==sid),None)
            if match is None or joined[match['start']-unit['start']:match['end']-unit['start']]!=text[match['start']:match['end']]:
                raise ValueError('reading plan: section mapping does not round-trip for '+sid)
    if covered and covered[-1][1]!=len(text):raise ValueError('reading plan: tail not covered')
    def union(ranges):
        out=[]
        for start,end in sorted(ranges):
            if out and start<=out[-1][1]:out[-1]=(out[-1][0],max(out[-1][1],end))
            else:out.append((start,end))
        return out
    body_units=union([(u['start'],u['end']) for u in units if u.get('role')=='body'])
    if union(body_source)!=body_units:
        raise ValueError('reading plan: body coverage differs from original sections')
    return True
