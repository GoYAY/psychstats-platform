"""Trusted educational graphics; model specifications are data, never drawing code."""
from dataclasses import dataclass
from pathlib import Path
import json
import math
import re
import subprocess
import sys
import textwrap


def _label(value, maximum):
    if not isinstance(value,str) or len(value)>maximum or not value.strip():
        raise ValueError('图示文字缺失或超过可读长度，请使用短标签。')
    return value


def validate_visual(spec):
    if not isinstance(spec,dict) or spec.get('kind') not in ('story','statistical'):
        raise ValueError('Unsupported visual kind')
    from .visual_presentation import validate_presentation
    validate_presentation(spec)
    for key in ('title','takeaway','alt'): _label(spec.get(key),1000)
    for key in ('learning_goal','adds_beyond_prose'):
        if key in spec:_label(spec[key],500)
    if spec.get('origin') not in ('conceptual','teaching','source','theoretical'):
        raise ValueError('Figure provenance is required')
    if spec['origin'] in ('source','theoretical') and not spec.get('refs'):
        raise ValueError('Source/theoretical graphics require evidence')
    p=spec.get('payload')
    if not isinstance(p,dict): raise ValueError('Figure payload must be an object')
    if spec['kind']=='story':
        if p.get('layout')=='feedback_trace':
            from .feedback_visual import prepare_feedback
            prepare_feedback(p)
            return spec
        if p.get('layout')=='pairwise_match':
            from .worked_visual import prepare_pairwise
            prepare_pairwise(p)
            return spec
        if p.get('layout') not in (None,'scenes'):raise ValueError('Unsupported story layout')
        if type(p.get('ordered',False)) is not bool:raise ValueError('Story ordering must be boolean')
        scenes=p.get('scenes')
        if not isinstance(scenes,list) or not 1<=len(scenes)<=4: raise ValueError('Use 1–4 story scenes')
        for scene in scenes:
            _label(scene.get('title'),24)
            objects=scene.get('objects'); connections=scene.get('connections',[])
            if not isinstance(objects,list) or not 1<=len(objects)<=8: raise ValueError('Use 1–8 objects per scene')
            ids=set()
            for obj in objects:
                key=obj.get('id')
                if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,96}',key) or key in ids:
                    raise ValueError('Object IDs must be distinct')
                ids.add(key); _label(obj.get('label'),16)
                if obj.get('kind') not in ('person','group','record','container','item'): raise ValueError('Unknown object kind')
                if obj.get('state') not in ('neutral','selected','missing','match','mismatch'): raise ValueError('Unknown object state')
            if not isinstance(connections,list) or len(connections)>8: raise ValueError('Too many story connections')
            for edge in connections:
                if edge.get('from') not in ids or edge.get('to') not in ids or edge['from']==edge['to']:
                    raise ValueError('Story arrow has an invalid endpoint')
                if edge.get('label'): _label(edge['label'],16)
                connection_mark(edge)
    else:
        if p.get('chart_type') not in ('bar','line','scatter','histogram'): raise ValueError('Unsupported chart')
        for axis in ('x','y'):
            _label(p.get(axis+'_label'),40)
            unit=p.get(axis+'_unit','')
            if not isinstance(unit,str) or len(unit)+len(p[axis+'_label'])>40: raise ValueError('Axis unit too long')
        series=p.get('series')
        if not isinstance(series,list) or not 1<=len(series)<=4: raise ValueError('Use 1–4 series')
        for s in series:
            _label(s.get('label'),24)
            hist=p['chart_type']=='histogram'
            x,y=(s.get('bin_edges'),s.get('counts')) if hist else (s.get('x'),s.get('y'))
            if not isinstance(x,list) or not isinstance(y,list) or not 1<=len(y)<=200 or len(x)!=len(y)+int(hist):
                raise ValueError('Chart arrays do not match')
            numeric=lambda v:type(v) in (int,float) and math.isfinite(v)
            if not all(numeric(v) for v in y): raise ValueError('Chart values must be finite numbers')
            if p['chart_type']!='bar' and not all(numeric(v) for v in x): raise ValueError('Numeric axis required')
            if p['chart_type']=='bar' and any(not (numeric(v) or isinstance(v,str) and len(v)<=24) for v in x):
                raise ValueError('Invalid category')
            if hist and (any(b<=a for a,b in zip(x,x[1:])) or any(v<0 for v in y)):
                raise ValueError('Invalid histogram bins or counts')
        semantics=spec.get('data_semantics')
        if semantics is not None:
            if (not isinstance(semantics,dict) or set(semantics)!={'type','denominator','rounding_digits'}
                or semantics['type'] not in {'partition','independent'}
                or semantics['denominator'] is not None and (type(semantics['denominator']) is not int or semantics['denominator']<1)
                or type(semantics['rounding_digits']) is not int or not 0<=semantics['rounding_digits']<=6):
                raise ValueError('Invalid data semantics')
            if semantics['type']=='partition':
                if p.get('y_unit') not in {'%','％'}:raise ValueError('构成比例必须明确百分比单位')
                for s in series:
                    values=s.get('y',s.get('counts',[]))
                    tolerance=len(values)*0.5*10**(-semantics['rounding_digits'])+1e-8
                    if any(v<0 or v>100 for v in values) or abs(sum(values)-100)>tolerance:
                        raise ValueError('构成比例与互斥穷尽分组不自洽；不能编造四舍五入原因或修改原值')
    return spec


def connection_mark(edge):
    relation=edge.get('relation','association')
    if relation not in ('comparison','association','sequence'):raise ValueError('Unsupported story relation')
    if relation=='sequence' and not edge.get('label'):raise ValueError('A directional step needs an explicit label')
    return dict(arrowstyle='-|>' if relation=='sequence' else '-',linestyle='dashed' if relation=='association' else 'solid')


@dataclass
class FigureAssets:
    desktop: str
    mobile: str
    preview: str
    pdf: str
    audit: str
    data: str
    alt: str


COLLISION='Figure rendered QA requires correction; artifacts preserved for review'
# Deterministic mechanical layout strategies.  They only change spacing and
# canvas size; the teaching JSON, objects, values and refs stay identical.
LAYOUT_STRATEGIES=(0,1,2)
def _layout_metrics(strategy,width,mobile):
    row_gap={0:70,1:88,2:96}[strategy]
    caption_gap={0:44,1:56,2:64}[strategy]
    scene_gap={0:30,1:44,2:52}[strategy]
    stretch=({0:1.0,1:1.0,2:1.15} if not mobile else {0:1.0,1:1.0,2:1.08})[strategy]
    return row_gap,caption_gap,scene_gap,int(width*stretch)


def render_visual(spec,output_dir,theme='#4263bd',*,run_external_qa=True,qa_dir=None,font_path=None,qa_timeout=120,layout_strategy=0):
    validate_visual(spec)
    qa_dir=Path(qa_dir) if qa_dir is not None else Path(__file__).resolve().parent/'figure_qa'
    if run_external_qa and any(not (qa_dir/name).is_file() for name in ['audit_panel_alignment.py','audit_pdf_text.py','audit_figure_collisions.py']):raise ValueError('Figure QA tools unavailable; export is not approved')
    if font_path is not None and not Path(font_path).is_file():raise ValueError('Configured figure font is unavailable')
    if type(qa_timeout) not in (int,float) or not 1<=qa_timeout<=300:raise ValueError('Invalid QA timeout')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',theme): raise ValueError('Invalid figure theme')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyBboxPatch, FancyArrowPatch, Rectangle, Ellipse
    from matplotlib.path import Path as MPath
    from matplotlib import font_manager
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    candidates=[Path(font_path)] if font_path is not None else [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),Path('/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc')]
    font=next((p for p in candidates if p.is_file()),None)
    family=font_manager.FontProperties(fname=str(font)).get_name() if font else 'DejaVu Sans'
    if font: font_manager.fontManager.addfont(str(font))
    params={'font.family':'sans-serif','font.sans-serif':[family,'DejaVu Sans'],'font.size':11,'svg.fonttype':'none','pdf.fonttype':42,'text.usetex':False,
            'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False}
    audit=dict(origin=spec['origin'],kind=spec['kind'],takeaway=spec['takeaway'],
               data_changed=False,human_review='pending',archetype='schematic-led composite' if spec['kind']=='story' else 'quantitative grid',
               layouts=[],external_qa=[])
    colors=[theme,'#409585','#b78a50','#7c6cb3']
    with plt.rc_context(params):
        for mobile in (False,True):
            presentation_audit=None
            width=360 if mobile else 760
            stem=output_dir/('figure-mobile' if mobile else 'figure')
            if spec['kind']=='story' and spec['payload'].get('layout')=='feedback_trace':
                from .feedback_visual import render_feedback
                fig,height,derived=render_feedback(spec['payload'],width,mobile,theme)
                audit['feedback_trace']=derived
            elif spec['kind']=='story' and spec['payload'].get('layout')=='pairwise_match':
                from .worked_visual import render_pairwise
                fig,height,derived=render_pairwise(spec['payload'],width,mobile,theme)
                audit['worked_example']=derived
            elif spec['kind']=='story':
                scenes=spec['payload']['scenes']; n=len(scenes)
                row_gap,_,scene_gap,width=_layout_metrics(layout_strategy,width,mobile)
                scene_width=width-24 if mobile else width/n-24
                title_columns=max(4,int((scene_width-40)/13)-(2 if layout_strategy else 0))
                # Captions get a reserved band under the objects; its height comes
                # from the wrapped line count, never from a fixed per-edge gap.
                caption_columns=max(6,int((scene_width-26)/13))
                line_height=15.0
                slot_gap=10+4*layout_strategy
                def wrap_lines(value):
                    return [line for part in str(value).split('\n') for line in (textwrap.wrap(part,caption_columns) or [''])]
                headers=[35+15*len(textwrap.wrap(s['title'],title_columns)) for s in scenes]
                row_heights=[]; caption_blocks=[]
                for scene in scenes:
                    per_row=[row_gap]*max(1,math.ceil(len(scene['objects'])/2))
                    for oi,obj in enumerate(scene['objects']):
                        lines=len(textwrap.wrap(obj['label'],8)) or 1
                        per_row[oi//2]=max(per_row[oi//2],22+line_height*lines+10)
                    row_heights.append(per_row)
                    labels={o['id']:o['label'] for o in scene['objects']}
                    caption_blocks.append([wrap_lines(labels[e['from']]+' · '+labels[e['to']]+'\n'+e['label'])
                                           for e in scene.get('connections',[]) if e.get('label')])
                caption_heights=[sum(line_height*len(b)+slot_gap for b in blocks)+(4 if blocks else 0) for blocks in caption_blocks]
                heights=[max(180,header+25+sum(rows)+captions+12) for header,rows,captions in zip(headers,row_heights,caption_heights)]
                height=sum(heights)+scene_gap*(n-1)+20 if mobile else max(heights)+scene_gap
                fig,ax=plt.subplots(figsize=(width/100,height/100))
                fig.subplots_adjust(left=0,right=1,bottom=0,top=1)
                ax.set(xlim=(0,width),ylim=(0,height)); ax.axis('off')
                ytop=height-10
                for si,scene in enumerate(scenes):
                    left=12 if mobile else si*width/n+12
                    right=width-12 if mobile else (si+1)*width/n-12
                    top=ytop if mobile else height-10
                    ax.text(left+3,top-5,f'{si+1:02}',color=theme,fontsize=17,weight='bold',va='top',alpha=.65)
                    ax.text(left+38,top-9,'\n'.join(textwrap.wrap(scene['title'],title_columns)),color='#171d2b',fontsize=10.2 if not mobile else 11,va='top')
                    pos={}
                    for oi,obj in enumerate(scene['objects']):
                        cols=min(2,len(scene['objects']))
                        x=left+(right-left)*(oi%cols+.5)/cols
                        y=top-headers[si]-25-sum(row_heights[si][:oi//2])
                        pos[obj['id']]=(x,y)
                        color={'match':'#2c8c69','mismatch':'#c85858','missing':'#8b929e'}.get(obj['state'],theme)
                        if obj['kind'] in ('person','group'):
                            for dx in ([-9,9] if obj['kind']=='group' else [0]):
                                ax.add_patch(Circle((x+dx,y+9),5,facecolor=color,alpha=.20,edgecolor=color,lw=1))
                                ax.add_patch(FancyBboxPatch((x+dx-8,y-11),16,15,boxstyle='round,pad=0,rounding_size=5',facecolor=color,alpha=.13,edgecolor=color,lw=1))
                        elif obj['kind']=='container':
                            ax.add_patch(Ellipse((x,y),34,17,facecolor=color,alpha=.14,edgecolor=color,lw=1.2))
                            ax.plot([x-16,x-11,x+11,x+16],[y,y-13,y-13,y],color=color,lw=1)
                        else:
                            ax.add_patch(FancyBboxPatch((x-15,y-11),30,26,boxstyle='round,pad=0,rounding_size=4',facecolor=color,alpha=.12,edgecolor=color,lw=1))
                            for k in range(3): ax.plot([x-8,x+8],[y+7-k*6]*2,color=color,alpha=.6,lw=1.3)
                        if obj['state'] in ('match','mismatch'):
                            ax.text(x+20,y+9,'+' if obj['state']=='match' else '×',color=color,fontsize=12,weight='bold')
                        ax.text(x,y-22,'\n'.join(textwrap.wrap(obj['label'],8)),ha='center',va='top',fontsize=10 if mobile else 9.4,color='#283448')
                    # Cross-row links detour through the gutter between the two
                    # object columns: labels are wider than the icons and fill both
                    # sides of a column, so any lane inside a column would cross a
                    # label.  Same-row links stay straight; the relation caption no
                    # longer sits on the midpoint.
                    cols=min(2,len(scene['objects']))
                    gutter=left+(right-left)*(1/cols if cols>1 else .5)
                    lane_slot=0
                    for edge in scene.get('connections',[]):
                        a,b=pos[edge['from']],pos[edge['to']]
                        mark=connection_mark(edge)
                        if abs(a[1]-b[1])<1e-6:
                            ax.add_patch(FancyArrowPatch(a,b,**mark,mutation_scale=10,connectionstyle='arc3,rad=.13',shrinkA=20,shrinkB=20,color=theme,alpha=.55,lw=1.1))
                        else:
                            # ±6px keeps every lane inside the gutter (labels are
                            # at most 8 chars wide, i.e. ~104px centred on a column).
                            lane=gutter+((lane_slot*3)%13)-6; lane_slot+=1
                            sa=20 if lane>a[0] else -20; sb=20 if lane>b[0] else -20
                            verts=[(a[0]+sa,a[1]),(lane,a[1]),(lane,b[1]),(b[0]+sb,b[1])]
                            codes=[MPath.MOVETO]+[MPath.LINETO]*3
                            ax.add_patch(FancyArrowPatch(path=MPath(verts,codes),**mark,mutation_scale=10,shrinkA=0,shrinkB=0,color=theme,alpha=.55,lw=1.1))
                    cursor=top-(headers[si]+25+sum(row_heights[si])+10)
                    for block in caption_blocks[si]:
                        ax.text(left+8,cursor,'\n'.join(block),ha='left',va='top',fontsize=9,color='#596477',linespacing=1.4)
                        cursor-=line_height*len(block)+slot_gap
                    if si<n-1:
                        if mobile:
                            ytop-=heights[si]+scene_gap
                            if spec['payload'].get('ordered',False):
                                ax.annotate('',xy=(width/2,ytop+8),xytext=(width/2,ytop+29),arrowprops=dict(arrowstyle='->',color=theme,alpha=.5))
                        elif spec['payload'].get('ordered',False):
                            xx=(si+1)*width/n
                            ax.annotate('',xy=(xx+10,height*.49),xytext=(xx-10,height*.49),arrowprops=dict(arrowstyle='->',color=theme,alpha=.5))
            elif spec['kind']=='statistical' and 'presentation' in spec:
                from .statistical_visual import make_statistical_figure
                fig,height,presentation_audit=make_statistical_figure(spec,width,mobile,theme)
            else:
                height=320 if mobile else 370
                fig,ax=plt.subplots(figsize=(width/100,height/100))
                p=spec['payload']; count=len(p['series'])
                fig.subplots_adjust(left=.20 if mobile else .12,right=.94,bottom=.23,top=.73 if count>1 else .93)
                for i,s in enumerate(p['series']):
                    color=colors[i]
                    if p['chart_type']=='histogram':
                        edges=s['bin_edges']; ax.bar(edges[:-1],s['counts'],width=[b-a for a,b in zip(edges,edges[1:])],align='edge',color=color,alpha=.30,edgecolor=color,label=s['label'])
                    elif p['chart_type']=='bar':
                        positions=[j+(i-(count-1)/2)*.72/count for j in range(len(s['x']))]
                        ax.bar(positions,s['y'],width=.66/count,color=color,alpha=.32,edgecolor=color,label=s['label'])
                        ax.set_xticks(range(len(s['x'])),[str(x) for x in s['x']])
                    elif p['chart_type']=='line': ax.plot(s['x'],s['y'],color=color,linewidth=1.7,label=s['label'])
                    else: ax.scatter(s['x'],s['y'],color=color,alpha=.58,s=22,label=s['label'])
                ax.set_xlabel(p['x_label']+(f"（{p['x_unit']}）" if p.get('x_unit') else ''))
                ax.set_ylabel(p['y_label']+(f"（{p['y_unit']}）" if p.get('y_unit') else ''))
                ax.grid(axis='y',alpha=.12); ax.set_axisbelow(True)
                if count>1: ax.legend(fontsize=9,frameon=False,loc='lower left',bbox_to_anchor=(0,1.04),borderaxespad=0)
            fig.canvas.draw()
            # A story is one continuous schematic canvas, not comparable data panels.
            if qa_dir.is_dir():
                import importlib.util
                module_spec=importlib.util.spec_from_file_location('term_figure_alignment',qa_dir/'audit_panel_alignment.py')
                alignment=importlib.util.module_from_spec(module_spec); sys.modules[module_spec.name]=alignment; module_spec.loader.exec_module(alignment)
                alignment.require_matplotlib_panel_alignment(fig,json_out=str(stem)+'.alignment.json',strict=True)
            else:
                Path(str(stem)+'.alignment.json').write_text(json.dumps(dict(status='not_applicable',reason='single axes')),encoding='utf-8')
            for suffix in ('svg','png','pdf'): fig.savefig(str(stem)+'.'+suffix,dpi=300)
            plt.close(fig)
            audit['layouts'].append(dict(width_px=width,height_px=height,pdf=str(stem.name)+'.pdf'))
            if presentation_audit:audit['layouts'][-1]['presentation']=presentation_audit
            if run_external_qa:
                if not qa_dir.is_dir(): raise ValueError('Figure QA tools unavailable; export is not approved')
                for script,args in [('audit_pdf_text.py',['--min-pt','5']),('audit_figure_collisions.py',
                        ['--json-out',str(stem)+'.collisions.json','--overlay-pdf',str(stem)+'.collisions.pdf'])]:
                    result=subprocess.run([sys.executable,'-X','utf8',str(qa_dir/script),str(stem)+'.pdf',*args],capture_output=True,text=True,encoding='utf-8',timeout=qa_timeout)
                    audit['external_qa'].append(dict(script=script,layout=stem.name,exit_code=result.returncode,output=result.stdout[-10000:]))
                    if result.returncode: 
                        (output_dir/'figure-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
                        raise ValueError(COLLISION)
    data=output_dir/'figure-data.json'; data.write_text(json.dumps(spec,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
    audit_path=output_dir/'figure-audit.json'; audit_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    return FigureAssets(str(output_dir/'figure.svg'),str(output_dir/'figure-mobile.svg'),str(output_dir/'figure.png'),str(output_dir/'figure.pdf'),str(audit_path),str(data),spec['alt'])
