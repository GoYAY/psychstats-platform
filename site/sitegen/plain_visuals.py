"""Small deterministic, dependency-free illustrations for everyday examples."""
from __future__ import annotations

import json
import math
import re
from html import escape
from pathlib import Path

KINDS = {'story', 'table', 'histogram', 'bars', 'scatter', 'lines', 'intervals', 'network', 'segments', 'boxplot'}
COLORS = ['#2563a0', '#a84c24', '#6945a3', '#227058', '#9a3971', '#57616e']
ARTWORK_DIR = Path(__file__).resolve().parents[1] / 'assets/examples-v2'


def validate_entry(slug, entry):
    if not re.fullmatch(r'[a-z0-9-]+', slug) or not isinstance(entry, dict):
        raise ValueError(f'{slug}: invalid example entry')
    decision = entry.get('decision')
    if decision == 'skip':
        if not entry.get('reason'):
            raise ValueError(f'{slug}: skip needs reason')
        return
    if decision not in {'draw', 'reuse'}:
        raise ValueError(f'{slug}: invalid decision')
    if 'artwork' in entry:
        artwork = entry['artwork']
        if not isinstance(artwork, dict) or artwork.get('file') != slug+'.svg':
            raise ValueError(f'{slug}: invalid cached artwork filename')
        for key in ('width', 'height', 'mobile_height'):
            if type(artwork.get(key)) is not int or artwork[key] <= 0:
                raise ValueError(f'{slug}: invalid artwork dimensions')
        for filename in (slug+'.svg', slug+'-mobile.svg'):
            if not (ARTWORK_DIR / filename).is_file():
                raise ValueError(f'{slug}: missing cached artwork {filename}')
        if not isinstance(entry.get('narrative'), list) or not entry['narrative'] or not all(isinstance(p,str) and p.strip() for p in entry['narrative']) or not entry.get('caution'):
            raise ValueError(f'{slug}: missing narrative/caution')
    for field in ('title', 'read', 'takeaway', 'limit'):
        if not isinstance(entry.get(field), str) or not entry[field].strip():
            raise ValueError(f'{slug}: missing {field}')
    if decision == 'reuse':
        if not re.fullmatch(r'[a-z0-9-]+', entry.get('reuse', '')):
            raise ValueError(f'{slug}: invalid reuse reference')
        return
    kind = entry.get('kind')
    if kind not in KINDS or entry.get('basis') not in {'synthetic', 'conceptual'}:
        raise ValueError(f'{slug}: invalid kind or basis')
    def number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{slug}: nonfinite/non-numeric value')
    if kind in {'histogram', 'bars', 'scatter', 'lines'}:
        chart = entry['chart']
        if not chart.get('x_label') or not chart.get('y_label') or not chart.get('series'):
            raise ValueError(f'{slug}: missing axes/series')
        for series in chart['series']:
            if not series.get('label') or not series.get('values'):
                raise ValueError(f'{slug}: empty series')
            for point in series['values']:
                if len(point) != 2:
                    raise ValueError(f'{slug}: invalid point')
                for value in point:
                    number(value)
                if kind == 'histogram' and (point[1] < 0 or point[1] != int(point[1])):
                    raise ValueError(f'{slug}: invalid frequency')
            xs = [p[0] for p in series['values']]
            if kind == 'histogram' and len(xs) > 2:
                if xs != sorted(set(xs)) or any(not math.isclose(xs[i]-xs[i-1], xs[1]-xs[0]) for i in range(2, len(xs))):
                    raise ValueError(f'{slug}: histogram requires equal-width bins')
    elif kind == 'story':
        if not 2 <= len(entry['panels']) <= 3:
            raise ValueError(f'{slug}: story requires 2–3 scenes')
    elif kind == 'table':
        if not entry['columns'] or any(len(row) != len(entry['columns']) for row in entry['rows']):
            raise ValueError(f'{slug}: inconsistent table')
    elif kind in {'intervals', 'boxplot'}:
        if not entry.get('rows'):
            raise ValueError(f'{slug}: empty rows')
        for row in entry['rows']:
            keys = ('low', 'mid', 'high') if kind == 'intervals' else ('low','q1','median','q3','high')
            for key in keys:
                number(row[key])
            if [row[k] for k in keys] != sorted(row[k] for k in keys):
                raise ValueError(f'{slug}: invalid interval')
            for value in row.get('outliers', []):
                number(value)
    elif kind == 'network':
        for node in entry['nodes']:
            for key in ('x', 'y'):
                number(node[key])
                if not 0 <= node[key] <= 100:
                    raise ValueError(f'{slug}: node outside diagram')
        for edge in entry['edges']:
            if any(not isinstance(edge[k], int) or not 0 <= edge[k] < len(entry['nodes']) for k in ('from', 'to')):
                raise ValueError(f'{slug}: invalid edge')
            if 'moderates' in edge and (not isinstance(edge['moderates'],int) or
                not 0<=edge['moderates']<len(entry['edges']) or 'moderates' in entry['edges'][edge['moderates']]):
                raise ValueError(f'{slug}: invalid moderated path')
    elif kind == 'segments':
        for row in entry['rows']:
            if len(row['values']) != len(entry['legend']):
                raise ValueError(f'{slug}: segment legend mismatch')
            for value in row['values']:
                number(value)
                if value < 0:
                    raise ValueError(f'{slug}: negative segment')


def load_visuals(directory: Path):
    result = {}
    updates_path = directory.parent / 'operational_visuals.json'
    updates = json.loads(updates_path.read_text(encoding='utf-8')) if updates_path.is_file() else {}
    for path in sorted(directory.glob('*.json')):
        entries = json.loads(path.read_text(encoding='utf-8'))
        for slug, entry in entries.items():
            if slug in updates:
                entry = {**entry, **updates[slug]}
                entry['caution'] = entry['limit']
            if slug in result:
                raise ValueError(f'{slug}: duplicate plain visual')
            validate_entry(slug, entry)
            result[slug] = entry
    return result


def dimensions(entry, mobile=False):
    if entry.get('artwork'):
        a = entry['artwork']
        return (360, a['mobile_height']) if mobile else (a['width'], a['height'])
    w = 360 if mobile else 760
    kind = entry.get('kind')
    if kind == 'story':
        return w, 56 + len(entry['panels']) * 178 if mobile else 270
    if kind == 'table':
        return w, 100 + 48 * len(entry['rows'])
    if kind in {'histogram', 'bars', 'scatter', 'lines'}:
        n = len(entry['chart']['series']) if entry['chart'].get('separate') else 1
        return w, 60 + n * 320 + (len(entry['chart']['series']) * 23 if n == 1 else 0)
    if kind == 'boxplot':
        return w, 165 + len(entry['rows']) * 85
    if kind in {'segments', 'intervals'}:
        return w, 110 + len(entry['rows']) * 66 + (25 * len(entry.get('legend', [])))
    return w, (500 if mobile else 420) + len(entry.get('edges', [])) * (48 if mobile else 28)


def render_svg(entry, mobile=False):
    if entry.get('artwork'):
        filename = entry['artwork']['file']
        if not re.fullmatch(r'[a-z0-9-]+\.svg', filename):
            raise ValueError('Invalid cached artwork filename')
        if mobile:
            filename = filename.removesuffix('.svg')+'-mobile.svg'
        return (ARTWORK_DIR / filename).read_text(encoding='utf-8')
    w, h = dimensions(entry, mobile)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title desc">',
           f'<title id="title">{escape(entry["title"])}</title><desc id="desc">{escape(entry.get("read", ""))}。{escape(entry.get("takeaway", ""))}</desc>',
           '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10" fill="#637083"/></marker></defs>',
           '<rect width="100%" height="100%" rx="14" fill="#f6f8fb"/>']
    def text(x, y, value, size=15, color='#252c38', anchor='start', weight=400):
        out.append(f'<text x="{x:.2f}" y="{y:.2f}" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(str(value))}</text>')
    def line(x1,y1,x2,y2,color='#d3dae4',width=1,extra=''):
        out.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="{width}" {extra}/>')
    def rect(x,y,rw,rh,color,rx=0):
        out.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(0,rw):.2f}" height="{max(0,rh):.2f}" rx="{rx}" fill="{color}"/>')
    def circle(x,y,r,color):
        out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r}" fill="{color}"/>')
    def wrap(x,y,value,maxchars,size=15,anchor='start',color='#252c38'):
        chunks = [str(value)[i:i+maxchars] for i in range(0,len(str(value)),maxchars)]
        for i,chunk in enumerate(chunks):
            text(x,y+i*(size+6),chunk,size,color,anchor)
    def fmt(v):
        return f'{v:.3g}'
    text(22,32,entry['title'],16,weight=600)
    kind = entry['kind']
    if kind == 'story':
        panels = entry['panels']
        for i,panel in enumerate(panels):
            pw = w-32 if mobile else (w-40)/len(panels)
            x,y = (16,52+i*178) if mobile else (16+i*pw,58)
            cx,cy = x+pw/2,y+37
            icon = panel.get('icon')
            if icon == 'clock':
                circle(cx,cy,24,'#e0e9f4'); circle(cx,cy,19,'white'); line(cx,cy,cx,cy-13,COLORS[0],2); line(cx,cy,cx+12,cy+5,COLORS[0],2)
            elif icon in {'student','school'}:
                circle(cx,cy-10,11,'#d7e4f3'); rect(cx-18,cy+5,36,23,COLORS[0],10)
                if icon == 'school':
                    circle(cx-32,cy-3,7,'#cad4e2'); circle(cx+32,cy-3,7,'#cad4e2')
            elif icon == 'coins':
                for dx,dy in [(-17,9),(0,-5),(17,9)]:
                    circle(cx+dx,cy+dy,13,'#dce7f4'); text(cx+dx,cy+dy+5,'¥',14,COLORS[0],'middle',600)
            elif icon == 'ruler':
                rect(cx-44,cy-8,88,20,'#dce7f4',3)
                for dx in range(-36,40,12):
                    line(cx+dx,cy-8,cx+dx,cy+1,COLORS[0])
            elif icon == 'chart':
                for j,bh in enumerate([15,30,45]): rect(cx-27+j*20,cy+22-bh,12,bh,COLORS[0],2)
            else:
                rect(cx-24,cy-25,48,56,'white',4)
                for dy in [-12,0,12]: line(cx-15,cy+dy,cx+15,cy+dy,COLORS[0],2)
            wrap(cx,y+87,panel['title'],int(pw//16)-2,15,'middle')
            for j,value in enumerate(panel.get('lines', [])):
                wrap(cx,y+113+j*22,value,int(pw//14)-2,13,'middle','#546173')
            if not mobile and i < len(panels)-1: line(x+pw-4,y+10,x+pw-4,y+165)
    elif kind == 'table':
        columns = entry['columns']; cw=(w-32)/len(columns)
        for ri,row in enumerate([columns,*entry['rows']]):
            y=55+ri*48
            rect(16,y,w-32,46,'#e5ecf5' if ri==0 else ('white' if ri%2 else '#edf1f6'),4)
            for ci,value in enumerate(row): wrap(16+(ci+0.5)*cw,y+20,value,max(3,int(cw//13)-1),13,'middle')
    elif kind in {'histogram','bars','scatter','lines'}:
        chart=entry['chart']; series=chart['series']; separate=chart.get('separate',False)
        groups=[[s] for s in series] if separate else [series]
        points=[p for s in series for p in s['values']]
        xmin,xmax=min(p[0] for p in points),max(p[0] for p in points)
        ymin,ymax=min(p[1] for p in points),max(p[1] for p in points)
        if kind in {'bars','histogram'}: ymin=min(0,ymin)
        if xmin==xmax: xmin-=1; xmax+=1
        if ymin==ymax: ymin-=1; ymax+=1
        if kind in {'bars','histogram'}:
            ymax+=max(1,(ymax-ymin)*0.16)
            if ymin == 0 and all(p[1] == int(p[1]) for p in points):
                ymax = math.ceil(ymax/3)*3
        barxs=sorted(set(p[0] for p in points)); gap=min((b-a for a,b in zip(barxs,barxs[1:])),default=1)
        if kind in {'bars','histogram'}: xmin-=gap*0.6; xmax+=gap*0.6
        for gi,group in enumerate(groups):
            top=95+gi*320; left=54; right=w-24; bottom=top+171
            px=lambda x:left+(x-xmin)/(xmax-xmin)*(right-left)
            py=lambda y:bottom-(y-ymin)/(ymax-ymin)*171
            if separate: text(left,top-35,group[0]['label'],14,weight=600)
            for ti in range(4):
                value=ymin+(ymax-ymin)*ti/3; yy=py(value)
                line(left,yy,right,yy); text(left-8,yy+4,fmt(value),11,'#546173','end')
            line(left,top,left,bottom,'#8692a4'); line(left,bottom,right,bottom,'#8692a4')
            if kind in {'bars','histogram'}:
                xs=barxs[::max(1,math.ceil(len(barxs)/7))]
                if xs[-1] != barxs[-1]: xs.append(barxs[-1])
            else:
                xs=barxs if len(barxs)<=9 else [xmin+(xmax-xmin)*i/4 for i in range(5)]
            for value in xs: text(px(value),bottom+19,fmt(value),11,'#546173','middle')
            wrap((left+right)/2,bottom+45,chart['x_label'],int((right-left)//14),13,'middle')
            text(18,top-13,chart['y_label'],12,'#546173')
            for si,s in enumerate(group):
                color=COLORS[(gi if separate else si)%len(COLORS)]
                vals=s['values']
                if kind in {'bars','histogram'}:
                    bw=(right-left)*gap/(xmax-xmin)*(1 if kind=='histogram' else 0.76)/len(group)
                    for x,y in vals:
                        xx=px(x)-bw*len(group)/2+si*bw
                        rect(xx,min(py(y),py(0)),bw,max(abs(py(y)-py(0)),0.1),color,2)
                elif kind=='lines':
                    path=' '.join(f'{px(x):.2f},{py(y):.2f}' for x,y in vals)
                    out.append(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="2.5"'+(' stroke-dasharray="6 4"' if si%2 else '')+'/>')
                    for x,y in vals: circle(px(x),py(y),3,color)
                else:
                    for x,y in vals:
                        if si%2: rect(px(x)-4,py(y)-4,8,8,color)
                        else: circle(px(x),py(y),4,color)
        if not separate:
            for i,s in enumerate(series):
                yy= h-len(series)*23+i*23-5
                line(22,yy-5,42,yy-5,COLORS[i%len(COLORS)],3,'stroke-dasharray="5 3"' if i%2 else '')
                text(50,yy,s['label'],12)
    elif kind == 'boxplot':
        rows=entry['rows']; vals=[v for r in rows for v in [r['low'],r['high'],*r.get('outliers',[])]]
        lo,hi=min(vals),max(vals)
        if lo==hi: lo-=1; hi+=1
        left,right=55,w-30
        pos=lambda v:left+(v-lo)/(hi-lo)*(right-left)
        for i,row in enumerate(rows):
            yy=100+i*85; text(22,yy-27,row['label'],13)
            line(pos(row['low']),yy,pos(row['high']),yy,COLORS[0],2)
            rect(pos(row['q1']),yy-12,pos(row['q3'])-pos(row['q1']),24,'#cfdef0',3)
            for key in ('low','high','median'):
                line(pos(row[key]),yy-12,pos(row[key]),yy+12,COLORS[0],3 if key=='median' else 2)
            for v in row.get('outliers',[]): circle(pos(v),yy,4,COLORS[1])
            for key,label in [('q1','Q1'),('median','中位数'),('q3','Q3')]:
                text(pos(row[key]),yy+(33 if key!='median' else 51),label,11,'#546173','middle')
        for i in range(5):
            v=lo+(hi-lo)*i/4; text(pos(v),h-50,fmt(v),11,'#546173','middle')
        wrap(w/2,h-27,entry['x_label'],int((w-32)//13),12,'middle','#546173')
    elif kind == 'intervals':
        rows=entry['rows']; lo=min(r['low'] for r in rows); hi=max(r['high'] for r in rows)
        if lo==hi: lo-=1; hi+=1
        left=110 if mobile else 185; right=w-25
        pos=lambda v:left+(v-lo)/(hi-lo)*(right-left)
        for i,row in enumerate(rows):
            yy=80+i*66; wrap(16,yy,row['label'],6 if mobile else 11,13)
            line(pos(row['low']),yy,pos(row['high']),yy,COLORS[0],3)
            for key in ('low','high'): line(pos(row[key]),yy-7,pos(row[key]),yy+7,COLORS[0],2)
            circle(pos(row['mid']),yy,5,COLORS[0]); text((left+right)/2,yy+26,f'{fmt(row["low"])} — {fmt(row["mid"])} — {fmt(row["high"])}',12,'#546173','middle')
        wrap(w/2,h-28,entry.get('x_label','数值'),int((w-32)//13),12,'middle','#546173')
    elif kind == 'segments':
        rows=entry['rows']; total=max(sum(r['values']) for r in rows) or 1
        left=95 if mobile else 160; width=w-left-24
        for i,row in enumerate(rows):
            yy=67+i*66; wrap(16,yy+21,row['label'],5 if mobile else 9,13)
            x=left
            for j,v in enumerate(row['values']):
                ww=width*v/total; rect(x,yy,ww,32,COLORS[j%len(COLORS)],2)
                if ww>=30: text(x+ww/2,yy+22,fmt(v),12,'white','middle')
                x+=ww
        for i,value in enumerate(entry['legend']):
            yy=75+len(rows)*66+i*25; rect(22,yy-10,13,13,COLORS[i%len(COLORS)],2); text(44,yy,value,12)
    elif kind=='network':
        nodes=entry['nodes']; nw=60 if mobile else 132; maxchars=4 if mobile else 9
        base = 500 if mobile else 420
        heights = [max(48, math.ceil(len(n['label'])/maxchars)*20+20) for n in nodes]
        coords=[(18+nw/2+n['x']/100*(w-36-nw),90+n['y']/100*(base-155)) for n in nodes]
        for ei,edge in enumerate(entry['edges']):
            ax,ay=coords[edge['from']]; bx,by=coords[edge['to']]
            if 'moderates' in edge:
                affected=entry['edges'][edge['moderates']]
                a,b=coords[affected['from']],coords[affected['to']]
                bx,by=(a[0]+b[0])/2,(a[1]+b[1])/2
            dx,dy=bx-ax,by-ay; length=math.hypot(dx,dy) or 1
            reciprocal = any(e['from']==edge['to'] and e['to']==edge['from'] for e in entry['edges'])
            crosses = any(j not in (edge['from'],edge['to']) and abs((cx-ax)*dy-(cy-ay)*dx)/length < nw/2 and 0 < ((cx-ax)*dx+(cy-ay)*dy)/length**2 < 1 for j,(cx,cy) in enumerate(coords))
            bend=110 if crosses else (35 if reciprocal else 0)
            cx,cy=(ax+bx)/2+dy/length*bend,(ay+by)/2-dx/length*bend
            def boundary(x,y,towardx,towardy,index):
                vx,vy=towardx-x,towardy-y
                halfx,halfy=nw/2+5,heights[index]/2+5
                scale=min(halfx/abs(vx) if vx else float('inf'),halfy/abs(vy) if vy else float('inf'))
                return x+vx*scale,y+vy*scale
            sx,sy=boundary(ax,ay,cx,cy,edge['from'])
            ex,ey=(bx,by) if 'moderates' in edge else boundary(bx,by,cx,cy,edge['to'])
            out.append(f'<path d="M {sx:.2f} {sy:.2f} Q {cx:.2f} {cy:.2f} {ex:.2f} {ey:.2f}" fill="none" stroke="#637083" stroke-width="1.7" marker-end="url(#arrow)"'+(' stroke-dasharray="5 4"' if edge.get('dashed') else '')+'/>')
            for t in (0.5, 0.3, 0.7, 0.2, 0.8):
                mx=(1-t)**2*sx+2*(1-t)*t*cx+t*t*ex
                my=(1-t)**2*sy+2*(1-t)*t*cy+t*t*ey
                if all(abs(mx-x)>nw/2+12 or abs(my-y)>heights[j]/2+12 for j,(x,y) in enumerate(coords)):
                    break
            circle(mx,my,9,'#f6f8fb'); text(mx,my+4,str(ei+1),11,'#546173','middle')
            label = f'{ei+1}. {nodes[edge["from"]]["label"]} → {nodes[edge["to"]]["label"]}：{edge.get("label", "联系")}'
            if 'moderates' in edge:
                label=f'{ei+1}. {nodes[edge["from"]]["label"]} ↓ {nodes[affected["from"]]["label"]} → {nodes[affected["to"]]["label"]}：{edge.get("label", "调节")}'
            wrap(20,base+ei*(48 if mobile else 28),label,26 if mobile else 58,12,color='#546173')
        for i,(node,(x,y)) in enumerate(zip(nodes,coords)):
            nh=heights[i]
            if node.get('shape')=='latent': out.append(f'<ellipse data-network-node="{i}" cx="{x}" cy="{y}" rx="{nw/2}" ry="{nh/2}" fill="#dce7f4" stroke="#869bb7"/>')
            else: out.append(f'<rect data-network-node="{i}" x="{x-nw/2}" y="{y-nh/2}" width="{nw}" height="{nh}" rx="5" fill="white"/>')
            rows=math.ceil(len(node['label'])/maxchars)
            wrap(x,y-(rows-1)*10+4,node['label'],maxchars,12,'middle')
    out.append('</svg>')
    return ''.join(out)
