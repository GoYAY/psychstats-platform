"""Executable, data-only visual intent. Absence is legacy, invalidity is not."""
from copy import deepcopy
import math,re
from decimal import Decimal

FIELDS={'version','focus','numeric_role','layout','interaction'}

def _inspection_data(visual):
    """Mirror personalBarData/validateBarData, not merely the layout matrix."""
    text=lambda v,n:isinstance(v,str) and bool(v.strip()) and len(v.encode('utf-16-le',errors='surrogatepass'))//2<=n
    number=lambda v:type(v) in (int,float) and math.isfinite(v)
    if not text(visual.get('title'),120) or not text(visual.get('takeaway'),400) or not text(visual.get('alt'),1000):return False
    if visual.get('origin') not in ('conceptual','teaching','source','theoretical') or (visual.get('origin') in ('source','theoretical') and not visual.get('refs')):return False
    payload=visual['payload']
    for axis in ('x','y'):
        label=payload.get(axis+'_label');unit=payload.get(axis+'_unit','')
        if not text(label,40) or not isinstance(unit,str) or len((label+unit).encode('utf-16-le',errors='surrogatepass'))//2>40:return False
    def category(x):
        if isinstance(x,str):return x
        x=float(x)
        if x==0:return '0'
        if x.is_integer() and abs(x)<1e21:return str(int(x))
        raw=repr(x)
        if 1e-6<=abs(x)<1e21:return format(Decimal(raw),'f')
        raw=re.sub(r'e([+-]?)0+(\d+)',r'e\1\2',raw)
        return raw if 'e-' in raw or 'e+' in raw else raw.replace('e','e+')
    for item in payload['series']:
        x=item.get('x');y=item.get('y')
        if not text(item.get('label'),24) or not isinstance(x,list) or not isinstance(y,list) or not 1<=len(x)<=200 or len(x)!=len(y):return False
        if any(not (number(v) or text(v,24)) for v in x) or any(not number(v) or v<0 for v in y):return False
        if len(set(map(category,x)))!=len(x):return False
    return True

def validate_presentation(visual: dict, *, required: bool=False) -> dict|None:
    def invalid(message):raise ValueError('visual.presentation: '+message)
    if 'presentation' not in visual:
        if required:invalid('required for this generation policy')
        return None
    p=visual['presentation']
    if not isinstance(p,dict) or set(p)!=FIELDS:invalid('unknown or missing fields')
    if type(p['version']) is not int or p['version']!=1:invalid('unsupported version')
    allowed={'focus':('whole','local','process','structure'),'numeric_role':('exact','relative','none'),
             'layout':('single','facets','overlay','grouped','story'),'interaction':('none','inspect')}
    for key,values in allowed.items():
        if not isinstance(p[key],str) or p[key] not in values:invalid('invalid '+key)
    if visual.get('kind')=='story':
        if p['layout']!='story' or p['interaction']!='none':invalid('unsupported story layout or interaction')
        return deepcopy(p)
    if visual.get('kind')!='statistical' or p['numeric_role']=='none':invalid('invalid statistical role')
    payload=visual.get('payload')
    if not isinstance(payload,dict):invalid('missing payload')
    chart=payload.get('chart_type');series=payload.get('series')
    if not isinstance(series,list) or not 1<=len(series)<=4 or any(not isinstance(s,dict) for s in series):invalid('invalid series')
    layouts={'bar':('grouped','facets'),'histogram':('overlay','facets'),'line':('overlay',),'scatter':('overlay',)}
    if not isinstance(chart,str) or chart not in layouts or p['layout'] not in (('single',) if len(series)==1 else layouts[chart]):invalid('unsupported chart/layout combination')
    if p['interaction']=='inspect' and not (chart=='bar' and p['layout'] in ('single','grouped') and p['numeric_role']=='exact'):invalid('unsupported inspection capability')
    if p['interaction']=='inspect' and not _inspection_data(visual):invalid('data exceeds inspection host bounds; use none or a supported exact chart without changing observations')
    if p['layout'] in ('facets','grouped'):
        key='bin_edges' if chart=='histogram' else 'x'
        values=[s.get(key) for s in series]
        if any(not isinstance(v,list) or not v or any(type(x) is bool for x in v) for v in values) or any(v!=values[0] for v in values[1:]):invalid('facets/grouped require identical ordered categories/boundaries')
    return deepcopy(p)
