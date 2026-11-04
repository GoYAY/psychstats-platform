"""Offline, source-traceable paper figures. Normal builds do not import Matplotlib.

Contract: saved R coefficients -> directed model arrows; saved 95% CI -> interval
plots; saved loadings/profiles -> labelled matrices/lines. No inferred p or CI.
New plotting logic, with style-only inheritance of the existing topic palette.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'site'))
sys.path.insert(0,str(Path.home()/'.codex/skills/nature-figure/scripts'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Ellipse
from matplotlib.path import Path as MplPath
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
from sitegen.paper_reporting import paper_data, VARIABLES, formatted
from audit_panel_alignment import require_matplotlib_panel_alignment
from audit_pdf_text import audit_pdf as text_audit
from audit_figure_collisions import audit_pdf as collision_audit, exit_code as collision_exit

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
    'svg.fonttype':'none','pdf.fonttype':42,'font.size':8,'axes.spines.top':False,
    'axes.spines.right':False,'axes.labelcolor':'#343e4c','text.color':'#243041',
    'xtick.color':'#4c5869','ytick.color':'#4c5869'})
PALETTE={'foundations':'#244da4','data-preparation':'#006d70','hypothesis-testing':'#6741ad',
    'group-comparisons':'#a33052','regression':'#8a5200','classification-clustering':'#006d70',
    'factor-analysis':'#6741ad','structural-equation-modeling':'#244da4',
    'mediation-moderation':'#953970','multilevel-longitudinal':'#17643b'}


def arc_path(start, end, lift):
    """One cubic relationship with fixed endpoint ports and a smooth crown."""
    crown=max(start[1],end[1])+lift
    return MplPath([start,(start[0],crown),(end[0],crown),end],
                   [MplPath.MOVETO,MplPath.CURVE4,MplPath.CURVE4,MplPath.CURVE4])


def model_figure(data,color):
    if data.get('measurement'):
        return measurement_model_figure(data, color)
    if data['case_id'] in {'mediation','latent-mediation'}:
        return mediation_figure(data,color)
    if data['case_id'] in {'moderation','conditional-mediation','mediated-interaction'}:
        return moderation_model_figure(data,color)
    paths=data['paths']; nodes=list(dict.fromkeys(p[k] for p in paths for k in ('source','target')))
    incoming={node:{p['source'] for p in paths if p['target']==node} for node in nodes}
    depth={node:0 for node in nodes if not incoming[node]}
    for _ in nodes:
        for node in nodes:
            if incoming[node] and incoming[node]<=depth.keys():
                depth[node]=1+max(depth[parent] for parent in incoming[node])
    if len(depth)!=len(nodes):
        depth.update({node:1 for node in nodes if node not in depth})
    layers={d:[node for node in nodes if depth[node]==d] for d in sorted(set(depth.values()))}
    positions={node:(d*3.6, (len(values)-1)*1.25-i*2.5)
               for d,values in layers.items() for i,node in enumerate(values)}
    if data['case_id']=='feedback':
        positions={'x':(0,1.5),'z':(0,-1.5),'y1':(3.6,1.5),'y2':(3.6,-1.5)}
    tallest=max(len(values) for values in layers.values()); width=9.0;height=max(3.4,tallest*1.6+.6)
    fig,ax=plt.subplots(figsize=(width,height));fig.subplots_adjust(left=.035,right=.965,top=.94,bottom=.08)
    ax.axis('off'); xmax=max(depth.values())*3.6
    ax.set_xlim(-1.3,xmax+(4.8 if data['case_id']=='feedback' else 1.3))
    extents=[p[1] for p in positions.values()]
    for edge in paths:
        if abs(depth[edge['target']]-depth[edge['source']])>1:
            sy=positions[edge['source']][1]
            extents.append((1 if sy>=0 else -1)*(tallest*1.15+.6+(.6 if sy==0 else 0)))
    ax.set_ylim(min(extents)-1.2,max(extents)+1.2)
    drawn=set()
    direct_number=0
    for p in paths:
        key=(p['source'],p['target'])
        if key in drawn: continue
        drawn.add(key); start=positions[p['source']];end=positions[p['target']]
        peers=[q for q in paths if (q['source'],q['target'])==key]
        reciprocal=any(q['source']==p['target'] and q['target']==p['source'] for q in paths)
        direct=abs(depth[p['target']]-depth[p['source']])>1
        geometry=None
        if reciprocal:
            direction=1 if start[1]>end[1] else -1
            lane=start[0]+direction*1.8
            tail=(start[0],start[1]-direction*.375);head=(end[0],end[1]+direction*.375)
            geometry=MplPath([tail,(lane,tail[1]),(lane,head[1]),head],
                [MplPath.MOVETO,MplPath.CURVE4,MplPath.CURVE4,MplPath.CURVE4])
            mx=.25*tail[0]+.75*lane+direction*.35;my=(start[1]+end[1])/2
            align='left' if direction>0 else 'right'
        elif direct:
            direct_number+=1
            side=1 if start[1]>=0 else -1
            lane=side*(tallest*1.15+.6+(0.6 if start[1]==0 else 0))
            tail=(start[0],start[1]+side*.375);head=(end[0],end[1]+side*.375)
            geometry=MplPath([tail,(tail[0],lane),(head[0],lane),head],
                [MplPath.MOVETO,MplPath.CURVE4,MplPath.CURVE4,MplPath.CURVE4])
            mx=(start[0]+end[0])/2;my=(tail[1]+head[1])/8+.75*lane+side*.4;align='center'
        else:
            bend=(start[0]+end[0])/2
            tail=(start[0]+.85,start[1]);head=(end[0]-.85,end[1])
            mx=bend-.05
            offset=.9 if p.get('beta') is not None else .6
            my=start[1]+(offset if start[1]>end[1] else -offset);align='center'
            if start[1]==end[1] and tallest>1:mx=start[0]+.10;align='center'
        arrow=(FancyArrowPatch(path=geometry,arrowstyle='-|>',mutation_scale=10,lw=1.0,color=color,alpha=.8)
               if geometry is not None else FancyArrowPatch(tail,head,arrowstyle='-|>',mutation_scale=10,
                   shrinkA=0,shrinkB=0,lw=1.0,color=color,alpha=.8))
        ax.add_patch(arrow)
        label=[]
        for q in peers:
            prefix=(f'组 {q["group"]} · ' if q.get('group') else '')
            text=prefix+(q['label'] or 'b')+f' = {q["estimate"]:.3f}'
            if q.get('beta') is not None: text+=f'\nβ = {q["beta"]:.3f}'
            label.append(text)
        ax.text(mx,my,'\n'.join(label),ha=align,va='center',fontsize=7.4)
    for node,(x,y) in positions.items():
        latent=node.startswith('f') and node[1:].isdigit() or node=='interaction'
        patch=(Ellipse((x,y),1.7,.75) if latent else
               FancyBboxPatch((x-.85,y-.375),1.7,.75,boxstyle='round,pad=0.02,rounding_size=.08'))
        patch.set_facecolor(matplotlib.colors.to_rgba(color,.055));patch.set_edgecolor(color);patch.set_linewidth(.8)
        ax.add_patch(patch);ax.text(x,y,VARIABLES.get(node,node),ha='center',va='center',fontsize=8.4)
    return fig


def moderation_model_figure(data,color):
    """Semantic moderation view: the modifier terminates on the affected path.

    Interaction and additive main effects remain tied to the saved estimates.
    Combined models use a triangle and one internal W for all moderated paths.
    """
    paths=data['paths'];simple=data['case_id']=='moderation'
    if not simple:return triangular_moderation_figure(data,color)
    upper=False
    positions={'x':(0,0),'well_being':(7.2,0),'w':(3.6,2)} if simple else {
        'x':(0,0),'m':(4,0),'y':(8,0),'w':(2,1.15 if upper else 2.1)}
    fig,ax=plt.subplots(figsize=(8.2,5.0 if upper else 4.0))
    fig.subplots_adjust(left=.035,right=.965,top=.94,bottom=.07)
    ax.axis('off');ax.set_xlim(-1.2,9.2 if not simple else 8.4)
    ax.set_ylim(-2.8,4.8 if upper else 3.0)
    def coefficient(p):
        pv=formatted(p['p'],'p',{})
        return p['label']+f' = {p["estimate"]:.4f}\n'+('p '+pv if pv.startswith('<') else 'p = '+pv)
    boxes={}
    for node,(x,y) in positions.items():
        box=FancyBboxPatch((x-.85,y-.375),1.7,.75,boxstyle='round,pad=0.02,rounding_size=.08',
            facecolor=matplotlib.colors.to_rgba(color,.055),edgecolor=color,lw=.8)
        ax.add_patch(box);boxes[node]=box
        label=VARIABLES.get(node,node)
        ax.text(x,y,label,ha='center',va='center',fontsize=8)
    main=[p for p in paths if p['source'] in {'x','m'}]
    for p in main:
        start=positions[p['source']];end=positions[p['target']]
        direct=not simple and p['source']=='x' and p['target']=='y'
        if direct:
            sign=1 if upper else -1
            tail=(start[0],sign*.375);head=(end[0],sign*.375)
            lane=sign*(3.2 if upper else 1.9)
            geometry=MplPath([tail,(tail[0],lane),(head[0],lane),head],
                [MplPath.MOVETO,MplPath.CURVE4,MplPath.CURVE4,MplPath.CURVE4])
            arrow=FancyArrowPatch(path=geometry,arrowstyle='-|>',mutation_scale=10,color=color,lw=1.05)
            tx,ty=(6,2.70) if upper else (4,-1.90)
        else:
            arrow=FancyArrowPatch((start[0]+.87,0),(end[0]-.87,0),arrowstyle='-|>',
                mutation_scale=10,color=color,lw=1.05,shrinkA=0,shrinkB=0)
            tx,ty=(start[0]+end[0])/2-.6,-.55
        arrow.set_gid('effect-'+p['source']+'-'+p['target']);ax.add_patch(arrow)
        ax.text(tx,ty,coefficient(p),ha='center',va='center',fontsize=7.2)
    for p in (p for p in paths if p['source']=='x:w'):
        repeat=not simple and p['target']=='y'
        node='w_repeat' if repeat else 'w';wx,wy=positions[node]
        destination=(wx,.25*.375+.75*3.2) if repeat else (wx,0)
        arrow=FancyArrowPatch((wx,wy-.395),destination,arrowstyle='-|>',mutation_scale=10,
            color=color,lw=1.05,shrinkA=0,shrinkB=0,gid='moderates-x-'+p['target'])
        ax.add_patch(arrow)
        ax.text(wx+.38,(wy-.395+destination[1])/2,coefficient(p),ha='left',va='center',fontsize=7.2)
    additive=[p for p in paths if p['source']=='w']
    note='；'.join('W 对 '+VARIABLES.get(p['target'],p['target'])+' 的主效应 '+p['label']+
                  f' = {p["estimate"]:.4f}' for p in additive)
    ax.text(3.6 if simple else 4,-2.50 if not simple and not upper else -1.65,note,
            ha='center',va='center',fontsize=7,color='#526575')
    return fig


def triangular_moderation_figure(data,color):
    """One X–M–Y triangle; one W targets each fitted moderated edge."""
    positions={'x':(0,0),'m':(4,4.2),'y':(8,0),'w':(4,1.4)}
    fig,ax=plt.subplots(figsize=(8.2,4.8))
    fig.subplots_adjust(left=.035,right=.965,top=.95,bottom=.07)
    ax.axis('off');ax.set_xlim(-1.9,9.9);ax.set_ylim(-1.9,5.0)
    for node,(x,y) in positions.items():
        ax.add_patch(FancyBboxPatch((x-.85,y-.375),1.7,.75,
            boxstyle='round,pad=0.02,rounding_size=.08',
            facecolor=matplotlib.colors.to_rgba(color,.055),edgecolor=color,lw=.8))
        ax.text(x,y,VARIABLES.get(node,node),ha='center',va='center',fontsize=8)
    def port(start,end):
        vector=np.array(end)-np.array(start)
        scale=min(.87/abs(vector[0]) if vector[0] else float('inf'),
                  .395/abs(vector[1]) if vector[1] else float('inf'))
        return np.array(start)+scale*vector
    def coefficient(p):
        pv=formatted(p['p'],'p',{})
        return p['label']+f' = {p["estimate"]:.4f}\n'+('p '+pv if pv.startswith('<') else 'p = '+pv)
    label_positions={('x','m'):(.55,2.4),('m','y'):(7.45,2.4),('x','y'):(4,-.65)}
    for p in (p for p in data['paths'] if p['source'] in {'x','m'}):
        start=positions[p['source']];end=positions[p['target']]
        ax.add_patch(FancyArrowPatch(port(start,end),port(end,start),arrowstyle='-|>',
            mutation_scale=10,color=color,lw=1.05,shrinkA=0,shrinkB=0,
            gid='effect-'+p['source']+'-'+p['target']))
        tx,ty=label_positions[(p['source'],p['target'])]
        ax.text(tx,ty,coefficient(p),ha='center',va='center',fontsize=7.2)
    for p in (p for p in data['paths'] if p['source']=='x:w'):
        target=positions[p['target']]
        destination=((positions['x'][0]+target[0])/2,(positions['x'][1]+target[1])/2)
        start=positions['w']
        ax.add_patch(FancyArrowPatch(port(start,destination),destination,arrowstyle='-|>',
            mutation_scale=10,color=color,lw=1.05,shrinkA=0,shrinkB=0,
            gid='moderates-x-'+p['target']))
        tx,ty=(3.5,2.75) if p['target']=='m' else (5.05,.55)
        ax.text(tx,ty,coefficient(p),ha='center',va='center',fontsize=7.2)
    additive=[p for p in data['paths'] if p['source']=='w']
    note='；'.join('W 对 '+VARIABLES.get(p['target'],p['target'])+' 的主效应 '+p['label']+
                  f' = {p["estimate"]:.4f}' for p in additive)
    ax.text(4,-1.5,note,ha='center',va='center',fontsize=7,color='#526575')
    return fig


def measurement_model_figure(data, color):
    """Render the fitted measurement and structural model, including errors.

    One standardised model view: lambda, beta, residual variances and latent
    covariance are read from actual parameter rows, not inferred from a cartoon.
    Multiple-group estimates share a diagram and carry explicit group labels.
    """
    rows = data['measurement']
    factors = list(dict.fromkeys(r['lhs'] for r in rows))
    items = {f:list(dict.fromkeys(r['rhs'] for r in rows if r['lhs']==f)) for f in factors}
    count = max(len(v) for v in items.values())
    gap = max(6.8, count*2.2+1.8)
    positions = {f:(i*gap, 0) for i,f in enumerate(factors)}
    observed = {}
    for f in factors:
        for j,item in enumerate(items[f]):
            observed.setdefault(item, (positions[f][0]+(j-(len(items[f])-1)/2)*2.2, -2.65))
    fig,ax = plt.subplots(figsize=(max(7.2, 3.0*len(factors)), 5.2))
    fig.subplots_adjust(left=.025,right=.975,top=.94,bottom=.07)
    ax.axis('off')
    left = min(x for x,y in observed.values())-2.3
    right = max(x for x,y in observed.values())+2.3
    structural = [p for p in data['paths'] if p['source'] in positions and p['target'] in positions]
    edges = list(dict.fromkeys((p['source'],p['target']) for p in structural))
    covs = [r for r in data['covariances'] if r['lhs'] in positions and r['rhs'] in positions]
    cov_edges = list(dict.fromkeys((r['lhs'],r['rhs']) for r in covs))
    spans=[abs(positions[a][0]-positions[b][0]) for a,b in edges+cov_edges]
    top = max([2.0]+[.39+.75*(.7+.28*s)+.8 for s in spans])
    ax.set_xlim(left,right);ax.set_ylim(-4.6,top)
    boxes = {}
    for f,(x,y) in positions.items():
        node = Ellipse((x,y),2.2,.78,facecolor=matplotlib.colors.to_rgba(color,.055),edgecolor=color,lw=.85)
        ax.add_patch(node);boxes[f]=node
        ax.text(x,y,VARIABLES.get(f,f),ha='center',va='center',fontsize=9)
    for item,(x,y) in observed.items():
        node = FancyBboxPatch((x-.95,y-.31),1.90,.62,boxstyle='square,pad=0',
            facecolor=matplotlib.colors.to_rgba('#3c7da3',.045),edgecolor='#476579',lw=.75)
        ax.add_patch(node);boxes[item]=node
        ax.text(x,y,item,ha='center',va='center',fontsize=7.8)

    def labels(peers, symbol):
        groups = len({r.get('group',1) for r in peers})>1
        def value(row):
            keys=('std.all','beta','est','estimate') if data['model_scale']=='standardized' else ('est','estimate')
            return next(row[key] for key in keys if isinstance(row.get(key),(int,float)))
        return '\n'.join((f'组{r.get("group",1)} ' if groups else '')+symbol+' = '+
            f'{value(r):.2f}' for r in peers)

    for f in factors:
        for item in items[f]:
            sx,sy=positions[f];ex,ey=observed[item]
            geometry=MplPath([(sx,sy-.39),(sx,-1.2),(ex,-1.35),(ex,ey+.31)],
                [MplPath.MOVETO,MplPath.CURVE4,MplPath.CURVE4,MplPath.CURVE4])
            ax.add_patch(FancyArrowPatch(path=geometry,arrowstyle='-|>',mutation_scale=9,
                color=color,lw=.8,alpha=.85))
            peers=[r for r in rows if r['lhs']==f and r['rhs']==item]
            # Place text beside the final half of its loading arrow.
            outside_left=sx-ex>1.5
            ax.text(ex+(-.18 if outside_left else .18),-1.97,labels(peers,'λ'),
                ha='right' if outside_left else 'left',va='center',fontsize=7)

    endogenous={p['target'] for p in structural}
    for index,(item,(x,y)) in enumerate(observed.items(),1):
        ey=y-.93
        node=Ellipse((x,ey),.95,.46,facecolor='white',edgecolor='#697987',lw=.7)
        ax.add_patch(node);ax.text(x,ey,'e'+str(index),ha='center',va='center',fontsize=7)
        ax.add_patch(FancyArrowPatch((x,ey+.23),(x,y-.31),arrowstyle='-|>',mutation_scale=8,color='#697987',lw=.7))
        variance=[r for r in data['variances'] if r['lhs']==item]
        if variance:ax.text(x,ey-.46,labels(variance,'θ'),ha='center',va='center',fontsize=6.8)
    for i,f in enumerate(factors):
        if f not in endogenous:continue
        x,y=positions[f];ex=x+2.0
        node=Ellipse((ex,y),1.0,.48,facecolor='white',edgecolor='#697987',lw=.7)
        ax.add_patch(node);ax.text(ex,y,'ζ'+str(i+1),ha='center',va='center',fontsize=7)
        ax.add_patch(FancyArrowPatch((ex-.50,y),(x+1.10,y),arrowstyle='-|>',mutation_scale=8,color='#697987',lw=.7))
        variance=[r for r in data['variances'] if r['lhs']==f]
        if variance:ax.text(ex,y+.70,labels(variance,'ψ'),ha='center',va='center',fontsize=6.8)
    # Equal spans have equal curvature; longer connections form outer arcs.
    # Every factor relationship shares the node's single top-centre port.
    for i,(source,target) in enumerate(edges):
        sx,sy=positions[source];tx,ty=positions[target];lift=.7+.28*abs(tx-sx)
        arrow=FancyArrowPatch(path=arc_path((sx,sy+.39),(tx,ty+.39),lift),
            arrowstyle='-|>',mutation_scale=9,color=color,lw=.9,alpha=.85,
            gid=f'factor-relation-{source}-{target}')
        ax.add_patch(arrow)
        peers=[p for p in structural if p['source']==source and p['target']==target]
        ax.text((sx+tx)/2,.39+.75*lift+.28,labels(peers,'β' if data['model_scale']=='standardized' else 'b'),ha='center',va='center',fontsize=7.2)
    for i,(first,second) in enumerate(cov_edges):
        sx,sy=positions[first];tx,ty=positions[second]
        lift=.7+.28*abs(tx-sx)
        ax.add_patch(FancyArrowPatch(path=arc_path((sx,sy+.39),(tx,ty+.39),lift),
            arrowstyle='<|-|>',mutation_scale=8,color='#526b7d',lw=.8,
            gid=f'factor-relation-{first}-{second}'))
        peers=[r for r in covs if r['lhs']==first and r['rhs']==second]
        ax.text((sx+tx)/2,.39+.75*lift+.28,labels(peers,'φ'),ha='center',va='center',fontsize=7)
    return fig


def mediation_figure(data,color):
    """One triangle combines the paths and indirect-effect uncertainty."""
    paths={p['label']:p for p in data['paths']}
    a,b,c=paths['a'],paths['b'],paths['c′']
    positions={a['source']:(0,0),a['target']:(3.6,2),b['target']:(7.2,0)}
    fig,ax=plt.subplots(figsize=(7.2,3.4))
    fig.subplots_adjust(left=.035,right=.965,top=.93,bottom=.07)
    ax.axis('off');ax.set_xlim(-1.25,8.45);ax.set_ylim(-1.7,2.85)
    boxes={}
    for node,(x,y) in positions.items():
        latent=node.startswith('f') and node[1:].isdigit()
        patch=(Ellipse((x,y),1.7,.75) if latent else
               FancyBboxPatch((x-.85,y-.375),1.7,.75,boxstyle='round,pad=0.02,rounding_size=.08'))
        patch.set_facecolor(matplotlib.colors.to_rgba(color,.055))
        patch.set_edgecolor(color);patch.set_linewidth(.8)
        ax.add_patch(patch);boxes[node]=patch
        ax.text(x,y,VARIABLES.get(node,node),ha='center',va='center',fontsize=8.4)
    rows=next(t['rows'] for t in data['tables'] if t['name']=='parameters')
    label_positions={'a':(1.45,1.65),'b':(5.75,1.65),'c′':(3.6,-.40)}
    for p in (a,b,c):
        ax.add_patch(FancyArrowPatch(positions[p['source']],positions[p['target']],
            patchA=boxes[p['source']],patchB=boxes[p['target']],shrinkA=2,shrinkB=2,
            arrowstyle='-|>',mutation_scale=10,lw=1.05,color=color,alpha=.85))
        row=next(r for r in rows if r.get('op')=='~' and r['lhs']==p['target'] and r['rhs']==p['source'])
        ptext=formatted(p['p'],'p',{})
        ptext='p '+ptext if ptext.startswith('<') else 'p = '+ptext
        label=f'{p["label"]} = {p["estimate"]:.3f} · {ptext}'
        if isinstance(row.get('ci.lower'),(int,float)) and isinstance(row.get('ci.upper'),(int,float)):
            label+=f'\n95% CI [{row["ci.lower"]:.3f}, {row["ci.upper"]:.3f}]'
        ax.text(*label_positions[p['label']],label,ha='center',va='center',fontsize=7.5,
                fontweight='bold' if p['p'] is not None and p['p']<.05 else 'normal')
    indirect=next(t['rows'][0] for t in data['tables'] if t['name']=='effect_summary')
    ax.text(3.6,-1.18,f'间接效应 a × b = {indirect["estimate"]:.3f}\n'
            f'Bootstrap 95% CI [{indirect["ci_lower"]:.3f}, {indirect["ci_upper"]:.3f}]',
            ha='center',va='center',fontsize=8,color=color)
    return fig


def slopes_figure(data,color):
    if data.get('prediction_spec'):
        return prediction_figure(data, color)
    rows=data['predictions'];fig,ax=plt.subplots(figsize=(7.2,3.4));fig.subplots_adjust(left=.11,right=.96,bottom=.21,top=.77)
    groups=list(dict.fromkeys(r['group'] for r in rows)); colors=[color,'#39759a','#238078']
    for i,group in enumerate(groups):
        series=[r for r in rows if r['group']==group]
        x=[r['x'] for r in series];y=[r['estimate'] for r in series]
        ax.plot(x,y,color=colors[i],lw=1.5,linestyle=['-','--',':'][i],label=group)
        ax.fill_between(x,[r['ci_lower'] for r in series],[r['ci_upper'] for r in series],color=colors[i],alpha=.055)
    ax.set_xlabel('压力（中心化分数）');ax.set_ylabel('预测幸福感（量表分数）')
    ax.legend(frameon=False,fontsize=7,loc='lower left',bbox_to_anchor=(0,1.10),ncol=3);ax.grid(axis='y',alpha=.13)
    return fig


def prediction_figure(data, color):
    if data['case_id']=='logistic':return logistic_function_figure(data,color)
    spec=data['prediction_spec']; rows=data['predictions']
    fig,ax=plt.subplots(figsize=(7.2,3.5));fig.subplots_adjust(left=.12,right=.97,bottom=.19,top=.82)
    observations=data.get('observations',[])
    if observations:
        ax.scatter([r['x'] for r in observations],[r['y'] for r in observations],s=11,
            color='#617286',alpha=.22,edgecolors='none',label='实际教学观测')
    groups=list(dict.fromkeys(r['group'] for r in rows));colors=[color,'#3c7da3','#268475']
    names={'control':'对照条件','practice':'练习条件','combined':'组合条件','条件预测':'拟合函数'}
    for i,group in enumerate(groups):
        points=sorted((r for r in rows if r['group']==group),key=lambda r:r['x'])
        x=np.array([r['x'] for r in points]); y=np.array([r['estimate'] for r in points])
        lower=np.array([r['ci_lower'] for r in points]);upper=np.array([r['ci_upper'] for r in points])
        assert np.all(np.diff(x)>0) and np.all(lower<=y) and np.all(y<=upper)
        ax.fill_between(x,lower,upper,color=colors[i%3],alpha=.10,lw=0)
        ax.plot(x,y,color=colors[i%3],lw=1.6,alpha=.9,label=names.get(group,group))
    ax.set_xlabel(spec['x_label']);ax.set_ylabel(spec['y_label']);ax.grid(axis='y',alpha=.12)
    ax.margins(x=.055)
    if spec['scale']=='probability':ax.set_ylim(0,1)
    ax.legend(frameon=False,fontsize=7.5,loc='lower left',bbox_to_anchor=(0,1.04),ncol=3)
    return fig


def logistic_function_figure(data,color):
    """Full inverse-logit domain plus the unchanged, saved conditional predictions."""
    rows=sorted(data['predictions'],key=lambda r:r['estimate'])
    probability=np.array([r['estimate'] for r in rows])
    z=np.log(probability/(1-probability))
    complete=np.linspace(min(-6,z.min()-.5),max(6,z.max()+.5),401)
    fig,ax=plt.subplots(figsize=(7.2,3.8))
    fig.subplots_adjust(left=.12,right=.96,bottom=.23,top=.82)
    ax.plot(complete,1/(1+np.exp(-complete)),color='#7b8795',lw=1.25,alpha=.65,
        label='完整 S 型函数',gid='logistic-function')
    ax.fill_between(z,[r['ci_lower'] for r in rows],[r['ci_upper'] for r in rows],
        color=color,alpha=.10,lw=0)
    ax.plot(z,probability,color=color,lw=2,label='本例实际区间及 95% CI',gid='logistic-sample')
    ax.scatter(z[[0,-1]],probability[[0,-1]],s=16,color=color,zorder=4)
    for row,zvalue,label_position in [(rows[0],z[0],(-3.7,.36)),(rows[-1],z[-1],(2.6,.56))]:
        ax.annotate(f'睡眠 {row["x"]:.1f} 小时\np = {row["estimate"]:.3f}',
            xy=(zvalue,row['estimate']),xytext=label_position,ha='center',va='center',fontsize=7,
            color=color,arrowprops={'arrowstyle':'-','color':color,'lw':.7,'alpha':.65,
                'connectionstyle':'arc3,rad=0.12','shrinkB':5})
    ax.set_xlabel('线性预测子 z（各变量的加权和）')
    ax.set_ylabel('筛查阳性概率 p');ax.set_ylim(0,1)
    ax.set_xlim(complete[0],complete[-1]);ax.set_xticks([-6,-3,0,3,6]);ax.set_yticks([0,.25,.5,.75,1])
    ax.grid(axis='y',alpha=.12)
    ax.legend(frameon=False,fontsize=7.3,loc='lower left',bbox_to_anchor=(0,1.07),ncol=2)
    fig.text(.12,.035,'p = 1 / (1 + exp(−z))     睡眠增加 → z 减小 → 阳性概率降低',fontsize=7.2,color='#526575')
    return fig


def interval_figure(table,color):
    rows=table['rows']; lower=next((k for k in ('ci_lower','ci.lower','lwr') if any(r.get(k) is not None for r in rows)),None)
    upper=next((k for k in ('ci_upper','ci.upper','upr') if any(r.get(k) is not None for r in rows)),None)
    est=next((k for k in ('estimate','difference','diff','slope','est') if any(isinstance(r.get(k),(int,float)) for r in rows)),None)
    if not all((lower,upper,est)): return None
    rows=[r for r in rows if all(isinstance(r.get(k),(int,float)) for k in (lower,upper,est))]
    if not rows or len(rows)>15:return None
    labels=[]
    for r in rows:
        label=next((str(r[k]) for k in ('effect','comparison','term') if r.get(k) is not None),None)
        if label is None: label='W = '+format(r.get('support_centered',r.get('f2_marker_units',0)),'.3g')
        label=VARIABLES.get(label,label)
        if r.get('outcome'):label=str(r['outcome'])+' · '+label
        labels.append(label)
    fig,ax=plt.subplots(figsize=(7.2,max(2.2,.4*len(rows)+1)));fig.subplots_adjust(left=.30,right=.68,bottom=.26,top=.92)
    for i,r in enumerate(rows):
        # Percentile CI need not be centred on its point estimate.
        ax.plot([r[lower],r[upper]],[i,i],color=color,lw=1.3)
        ax.scatter([r[est]],[i],s=22,color=color,zorder=3)
        ax.text(1.06,i, f'{r[est]:.3f} [{r[lower]:.3f}, {r[upper]:.3f}]',fontsize=7,va='center',transform=ax.get_yaxis_transform(),clip_on=False)
    ax.set_yticks(range(len(rows)),labels);ax.invert_yaxis();ax.axvline(0,color='#8b95a3',lw=.7,ls='--')
    values=[r[k] for r in rows for k in (lower,upper)];span=max(values)-min(values) or 1
    ax.set_xlim(min(values)-.1*span,max(values)+.1*span);ax.set_xlabel('效应估计与 95% CI（本表量纲）')
    return fig


def loadings_figure(table,color):
    rows=table['rows']; data={}; factors=[];items=[]
    if table['name']=='parameters':
        for r in rows:
            if r.get('op')!='=~':continue
            factor=r['lhs'];item=r['rhs'];value=r['est'] if r['lhs'] in {'i','s'} else r.get('std.all',r['est'])
            if r.get('group') is not None:
                factor=VARIABLES.get(factor,factor)+' · 组'+str(r['group'])
            if factor not in factors:factors.append(factor)
            if item not in items:items.append(item)
            data[(item,factor)]=value
    else:
        items=[r.get('item',r.get('_row',str(i))) for i,r in enumerate(rows)]
        factors=[k for k in table['columns'] if k.startswith(('MR','PC'))]
        for item,r in zip(items,rows):
            for factor in factors:data[(item,factor)]=r.get(factor)
    if not data or not factors:return None
    matrix=np.array([[data.get((item,factor),np.nan) for factor in factors] for item in items])
    fig,ax=plt.subplots(figsize=(7.2,max(2.8,.24*len(items)+1)));fig.subplots_adjust(left=.14,right=.94,top=.86,bottom=.13)
    palette=LinearSegmentedColormap.from_list('loading',['#3779a3','#ffffff',color])
    scale=max(1,float(np.nanmax(np.abs(matrix))))
    ax.imshow(matrix,cmap=palette,vmin=-scale,vmax=scale,aspect='auto',alpha=.36)
    for i in range(len(items)):
        for j in range(len(factors)):
            if np.isfinite(matrix[i,j]):ax.text(j,i,f'{matrix[i,j]:.2f}',ha='center',va='center',fontsize=7.3)
    ax.set_xticks(range(len(factors)),[VARIABLES.get(f,f) for f in factors]);ax.set_yticks(range(len(items)),items)
    ax.xaxis.tick_top();ax.tick_params(length=0);ax.set_xlabel('颜色方向与数值共同标示载荷；空格表示未设定该测量路径',fontsize=7.3)
    for spine in ax.spines.values():spine.set_visible(False)
    return fig


def profiles_figure(table,color):
    rows=table['rows'];keys=[k for k in table['columns'] if k not in {'cluster','class','group','_row'}
        and all(isinstance(r.get(k),(int,float)) for r in rows)]
    if not keys:return None
    fig,ax=plt.subplots(figsize=(7.2,3.2));fig.subplots_adjust(left=.11,right=.96,bottom=.20,top=.76)
    colors=[color,'#3c7da3','#268475','#90664b']
    for i,r in enumerate(rows):
        ax.plot(range(len(keys)),[r[k] for k in keys],marker=['o','s','^','D'][i%4],
            ms=4,lw=1.15,alpha=.85,color=colors[i%4],label='组 '+str(r.get('cluster',r.get('class',i+1))))
    ax.set_xticks(range(len(keys)),[VARIABLES.get(k,k) for k in keys]);ax.set_ylabel('标准化指标均值（全体样本 SD 单位）')
    ax.legend(frameon=False,fontsize=7,loc='lower left',bbox_to_anchor=(0,1.10),ncol=4);ax.grid(axis='y',alpha=.13)
    return fig


def main():
    target=ROOT/'site/assets/paper-results';qa=ROOT/'logs/paper-results';target.mkdir(parents=True,exist_ok=True);qa.mkdir(parents=True,exist_ok=True)
    catalog=json.loads((ROOT/'site/content/analysis_catalog.json').read_text(encoding='utf-8'))
    topics={unit['id']:unit['group'] for unit in catalog['units']}
    cache_path=qa/'export-records.json';records=json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    source=hashlib.sha256(Path(__file__).read_bytes()+(ROOT/'site/sitegen/paper_reporting.py').read_bytes()).hexdigest()
    failures=[];rendered=0;reused=0
    for file in sorted((ROOT/'site/content/analysis_cases').glob('*.json')):
        case=json.loads(file.read_text(encoding='utf-8'));slug=case['id']
        result=json.loads((ROOT/f'site/content/analysis_results/{slug}.json').read_text(encoding='utf-8'))
        data=paper_data(case,result);payload=json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)
        (target/(slug+'.json')).write_text(payload,encoding='utf-8')
        fingerprint=hashlib.sha256((source+payload).encode('utf-8')).hexdigest()
        color=PALETTE.get(topics.get(case['unit_id']),'#244da4');jobs={}
        if data['valid'] and (data['paths'] or data['measurement'] and slug != 'growth'):jobs['model']=lambda:model_figure(data,color)
        if data['predictions']:jobs['slopes']=lambda:slopes_figure(data,color)
        ci_table=next((t for t in data['tables'] if t['name'] in {'conditional_effects','simple_slopes','paired_comparisons','change_comparison','pairwise','adjusted_pairwise_comparisons'}),None)
        if ci_table and ci_table['name']=='conditional_effects':
            ci_table={**ci_table,'rows':[r for r in ci_table['rows'] if r.get('effect')!='index']}
        if ci_table:jobs['estimates']=lambda:interval_figure(ci_table,color)
        loading=next((t for t in data['tables'] if t['name']=='loadings'),None)
        if loading is None:loading=next((t for t in data['tables'] if t['name']=='parameters' and any(r.get('op')=='=~' for r in t['rows'])),None)
        if loading:jobs['loadings']=lambda:loadings_figure(loading,color)
        profiles=next((t for t in data['tables'] if t['name']=='standardized_profiles'),None)
        if profiles:jobs['profiles']=lambda:profiles_figure(profiles,color)
        for kind,make in jobs.items():
            stem=slug+'-'+kind;svg=target/(stem+'.svg');pdf=target/(stem+'.pdf')
            saved=records.get(stem,{})
            if saved.get('fingerprint')==fingerprint and svg.exists() and pdf.exists():
                reused+=1
                if saved.get('failed'):failures.append(stem)
                continue
            fig=make()
            if fig is None:continue
            fig.canvas.draw()
            require_matplotlib_panel_alignment(fig,json_out=str(qa/(stem+'.alignment.json')),strict=True)
            fig.savefig(svg,transparent=False);fig.savefig(pdf,transparent=False)
            fig.savefig(qa/(stem+'.png'),dpi=300);plt.close(fig)
            tree=ET.parse(svg);root=tree.getroot();root.set('role','img')
            title=ET.Element('{http://www.w3.org/2000/svg}title');title.text=case['title']+' · '+kind;root.insert(0,title)
            tree.write(svg,encoding='utf-8',xml_declaration=True)
            fonts=text_audit(pdf.read_bytes(),minimum_pt=5);collisions=collision_audit(pdf)
            failed=not fonts['auditable'] or fonts['below_minimum_count']>0 or collision_exit(collisions)!=0
            records[stem]={'fingerprint':fingerprint,'failed':failed,'font_audit':fonts,'collision_audit':collisions,
                'svg_sha256':hashlib.sha256(svg.read_bytes()).hexdigest(),
                'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()}
            if failed:failures.append(stem)
            rendered+=1
            print(stem,'FAIL' if failed else 'OK',flush=True)
        cache_path.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'rendered':rendered,'reused':reused,'failures':failures}),flush=True)
    return bool(failures)


if __name__=='__main__':sys.exit(main())
