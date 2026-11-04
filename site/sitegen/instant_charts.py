"""Narrow trusted official-figure mount annotations; keep the static picture."""
import json
import re
from html import escape

def annotate_official_chart(html: str,visual: dict,slug: str)->str:
    pattern=r'(<figure class="plain-example-visual illustrated-example">)(.*?)(</figure>)'
    matches=list(re.finditer(pattern,html,re.S))
    if len(matches)!=1:raise ValueError('Expected exactly one official teaching figure')
    if visual.get('decision')!='draw' or visual.get('kind')!='bars':raise ValueError('Only bar examples are enabled')
    chart=visual['chart']
    data=dict(version=1,title=visual['title'],xLabel=chart['x_label'],yLabel=chart['y_label'],note=visual.get('takeaway',''),series=[dict(id='s'+str(i),label=s['label'],points=[dict(category=str(x),value=y) for x,y in s['values']]) for i,s in enumerate(chart['series'])])
    if slug=='central-tendency-and-dispersion':
        if len(data['series'])!=2 or any(len(s['points'])!=9 or sum(p['value'] for p in s['points'])!=10 or sum(float(p['category'])*p['value'] for p in s['points'])!=800 for s in data['series']):raise ValueError('Original classroom data changed')
        data['reference']=dict(value=80,label='两班均分80分')
    serialized=json.dumps(data,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    match=matches[0];body=match[2]
    pictures=list(re.finditer(r'<picture>.*?</picture>',body,re.S))
    if len(pictures)!=1:raise ValueError('Expected one static picture')
    # Separate panels encode a whole-distribution comparison. The current
    # category widget cannot preserve that task; retain the accepted figure.
    if chart.get('separate') is True:return html
    picture=pictures[0]
    markup='<div data-instant-chart="'+escape(slug,quote=True)+'" data-chart-data="'+escape(serialized,quote=True)+'" style="position:relative;min-height:460px">'+picture[0].replace('<picture>','<picture data-chart-static style="display:block">',1)+'</div>'
    body=body[:picture.start()]+markup+body[picture.end():]
    return html[:match.start()]+match[1]+body+match[3]+html[match.end():]
