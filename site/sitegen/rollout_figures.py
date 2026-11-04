"""Offline rollout of the approved translucent teaching-figure style.

Data contract: all plotted values and topology come from the existing manifest.
Lines join the supplied points, without fitting, smoothing or invented errors.
Theme hues identify series; marker/dash shapes and labels provide redundancy.
"""
from __future__ import annotations

import math
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch, Rectangle
from matplotlib.path import Path as MplPath
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, FuncFormatter
from .illustrated_examples import _text, _surface, _chart_style, SLUGS
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
                     'svg.fonttype':'none','pdf.fonttype':42})


def wrap(value, width=24):
    """Wrap by approximate glyph width, preserving every character."""
    lines, current, length = [], '', 0
    for char in str(value):
        if char == '\n':
            lines.append(current); current=''; length=0; continue
        cost = 1 if ord(char)>127 else 0.56
        if current and length+cost>width:
            lines.append(current); current=''; length=0
        current+=char; length+=cost
    if current: lines.append(current)
    return '\n'.join(lines)


def colors(theme):
    # One topic hue plus distinct readable accent hues, never a rainbow scale.
    return [theme, '#7656ab' if theme not in ('#6741ad','#953970') else '#246b91', '#137d7b']


def canvas(width, height):
    fig=plt.figure(figsize=(width/72,height/72),dpi=300)
    ax=fig.add_axes([0,0,1,1])
    ax.set(xlim=(0,width),ylim=(height,0)); ax.axis('off')
    return fig,ax


def cell_color(value):
    """Signal only explicit judgments, never the sign of a numerical result."""
    text=str(value)
    if text in {'正确拒绝','正确不拒绝'}: return '#187b55'
    if text in {'第一类：误报','第二类：漏报'}: return '#ae3f53'
    if text in {'待核查','待检查','需核查'}: return '#966111'
    return '#202a38'


def _charts(entry, theme, mobile):
    chart=entry['chart']; series=chart['series']; kind=entry['kind']
    separate=bool(chart.get('separate'))
    count=len(series) if separate else 1
    width=360 if mobile else 760
    xlab=wrap(chart['x_label'], 21 if mobile else 49)
    ylab=wrap(chart['y_label'], 21 if mobile else 43)
    legend_height=0 if separate else sum((wrap(s['label'],22 if mobile else 47).count('\n')+1)*18+7 for s in series)
    label_height=(xlab.count('\n')+1)*18
    height=100+count*260+label_height+legend_height
    fig,axes=plt.subplots(count,1,figsize=(width/72,height/72),dpi=300,squeeze=False)
    fig.subplots_adjust(left=0.17 if mobile else 0.10, right=0.96, top=1-65/height,
                        bottom=(label_height+legend_height+48)/height,hspace=0.70)
    points=[p for s in series for p in s['values']]
    xs=[p[0] for p in points]; ys=[p[1] for p in points]
    xmin,xmax=min(xs),max(xs); ymin,ymax=min(ys),max(ys)
    if xmin==xmax: xmin-=1; xmax+=1
    if ymin==ymax: ymin-=0.5; ymax+=0.5
    ux=sorted(set(xs)); gap=min((b-a for a,b in zip(ux,ux[1:])),default=1)
    if kind in {'bars','histogram'}:
        xmin-=gap*0.65; xmax+=gap*0.65
        ymin=min(0,min(ys)); ymax=max(ys)+max(0.3,(max(ys)-ymin)*0.12)
    else:
        dx=(xmax-xmin)*0.05; dy=(ymax-ymin)*0.12
        xmin-=dx; xmax+=dx; ymin-=dy; ymax+=dy
    palette=colors(theme)
    for i,ax in enumerate(axes.flat):
        _chart_style(ax); ax.set_gid(f'data-panel-{i}')
        group=[series[i]] if separate else series
        ax.set(xlim=(xmin,xmax),ylim=(ymin,ymax))
        ax.yaxis.set_major_locator(MaxNLocator(4,integer=kind in {'bars','histogram'} and all(float(y).is_integer() for y in ys)))
        ax.xaxis.set_major_locator(MaxNLocator(5,integer=all(float(x).is_integer() for x in xs)))
        for j,s in enumerate(group):
            color=palette[(i if separate else j)%len(palette)]
            vx,vy=zip(*s['values'])
            if kind in {'bars','histogram'}:
                bw=gap*(1 if kind=='histogram' else 0.72)/len(group)
                positions=[x+(j-(len(group)-1)/2)*bw for x in vx]
                ax.bar(positions,vy,width=bw,color=color,edgecolor=color,alpha=0.35,linewidth=0.85)
            elif kind=='scatter':
                ax.scatter(vx,vy,s=37,marker=['o','s','D'][j%3],facecolor=color,
                           edgecolor=color,alpha=0.62,linewidth=0.8)
            else:
                ax.plot(vx,vy,color=color,linewidth=1.8,linestyle=['-','--',':'][j%3],
                        marker=['o','s','D'][j%3],markersize=4.5,markerfacecolor='white',markeredgewidth=1.1)
                if chart.get('highlight_interval'):
                    low,high=chart['highlight_interval']
                    ax.fill_between(vx,vy,0,where=[low<=x<=high for x in vx],
                                    color=color,alpha=.16,gid='interval-area')
        ax.set_title(wrap(group[0]['label'],23 if mobile else 47) if separate else ylab,
                     fontsize=12,color=palette[i%3] if separate else '#465366',loc='left',pad=18)
        if separate:
            ax.set_ylabel(wrap(chart['y_label'],18),fontsize=12,labelpad=9)
        if i==count-1: ax.set_xlabel(xlab,fontsize=12,labelpad=13)
    if not separate:
        yy=legend_height+10
        for i,s in enumerate(series):
            label=wrap(s['label'],22 if mobile else 47)
            ly=(yy-7)/height
            if kind in {'bars','histogram'}:
                swatch=Rectangle((.10,ly-4/height),.027,8/height,
                                  transform=fig.transFigure,facecolor=palette[i%3],
                                  edgecolor=palette[i%3],alpha=.35,linewidth=.85)
            else:
                swatch=Line2D([.10,.13],[ly,ly],transform=fig.transFigure,
                              color=palette[i%3],marker=['o','s','D'][i%3],
                              linestyle='None' if kind=='scatter' else ['-','--',':'][i%3],
                              markersize=5,markerfacecolor=palette[i%3] if kind=='scatter' else 'white',
                              linewidth=1.8,alpha=.62 if kind=='scatter' else 1)
            swatch.set_gid(f'legend-swatch-{i}')
            fig.add_artist(swatch)
            fig.text(0.15,yy/height,label,fontsize=12,color='#465366',va='top')
            yy-=18*(label.count('\n')+1)+7
    return fig


def _table(entry, theme, mobile):
    cols=entry['columns']; rows=entry['rows']; width=360 if mobile else 760
    if mobile:
        blocks=[]
        for row in rows:
            cells=[(wrap(c,8),wrap(v,15)) for c,v in zip(cols,row)]
            rh=[max(c.count('\n')+1,v.count('\n')+1)*19+16 for c,v in cells]
            blocks.append((cells,rh))
        height=24+sum(sum(rh)+28 for _,rh in blocks)
        fig,ax=canvas(width,height); y=12
        for cells,rh in blocks:
            _surface(ax,12,y,width-24,sum(rh)+12,theme)
            cy=y+14
            for (label,value),hh in zip(cells,rh):
                ax.text(25,cy,label,fontsize=12,color=theme,va='top',weight='bold')
                ax.text(137,cy,value,fontsize=13,color=cell_color(value),va='top')
                cy+=hh
            y+=sum(rh)+28
    else:
        colwidth=(width-32)/len(cols)
        contents=[[wrap(v,(colwidth-24)/13) for v in row] for row in [cols,*rows]]
        heights=[max(v.count('\n')+1 for v in row)*19+24 for row in contents]
        height=24+sum(heights)
        fig,ax=canvas(width,height); y=12
        for i,(row,rh) in enumerate(zip(contents,heights)):
            _surface(ax,16,y,width-32,rh-2,theme,0.09 if i==0 else (0.035 if i%2 else 0.065))
            for j,value in enumerate(row):
                ax.text(28+j*colwidth,y+rh/2,value,fontsize=12,va='center',
                        color=theme if i==0 else cell_color(value),weight='bold' if i==0 else 'normal',linespacing=1.45)
            y+=rh
    return fig


def _segments(entry,theme,mobile):
    width=360 if mobile else 760
    rows=entry['rows']; legend=[wrap(v,22 if mobile else 53) for v in entry['legend']]
    legend_height=sum(20*(s.count('\n')+1)+9 for s in legend)
    height=110+len(rows)*105+legend_height
    fig,ax=plt.subplots(figsize=(width/72,height/72),dpi=300)
    fig.subplots_adjust(left=0.10,right=0.96,top=0.96,bottom=(legend_height+45)/height)
    ax.set_gid('data-panel-0'); ax.spines[['top','right','left']].set_visible(False)
    palette=colors(theme)
    # Each row occupies separate y coordinates with sufficient label clearance.
    for i,row in enumerate(rows):
        y=len(rows)-i; start=0
        for j,value in enumerate(row['values']):
            ax.barh(y,value,left=start,height=0.34,color=palette[j%3],alpha=0.36,
                    edgecolor=palette[j%3],linewidth=0.8)
            if value>0:
                ax.text(start+value/2,y,str(value),ha='center',va='center',fontsize=12,color='#202a38')
            start+=value
        ax.text(0,y+0.27,wrap(row['label'],25 if mobile else 52),fontsize=12,va='bottom')
    ax.set(ylim=(0.48,len(rows)+0.85),yticks=[],xlim=(0,max(sum(r['values']) for r in rows)*1.03 or 1))
    ax.tick_params(axis='x',labelsize=12,length=0)
    yy=legend_height+5
    for j,label in enumerate(legend):
        fig.text(0.10,yy/height,f'{j+1}. {label}',fontsize=12,color=palette[j%3],va='top')
        yy-=20*(label.count('\n')+1)+9
    return fig


def _intervals(entry,theme,mobile):
    width=360 if mobile else 760; rows=entry['rows']
    label=wrap(entry.get('x_label','数值'),23 if mobile else 50)
    height=110+len(rows)*105+label.count('\n')*19
    fig,ax=plt.subplots(figsize=(width/72,height/72),dpi=300)
    fig.subplots_adjust(left=0.13,right=0.95,top=0.92,bottom=(70+label.count('\n')*19)/height)
    _chart_style(ax); ax.set_gid('data-panel-0'); ax.spines['left'].set_visible(False)
    ax.grid(False); ax.set_yticks([])
    lo=min(r['low'] for r in rows); hi=max(r['high'] for r in rows); pad=(hi-lo)*0.10 or 1
    ax.set(xlim=(lo-pad,hi+pad),ylim=(0.48,len(rows)+0.7)); ax.set_xlabel(label,fontsize=12,labelpad=12)
    ax.xaxis.set_major_locator(MaxNLocator(5))
    for i,row in enumerate(rows):
        y=len(rows)-i
        if entry.get('reference_bounds'):
            bounds=entry['reference_bounds']
            ymin,ymax=ax.get_ylim()
            ax.axvspan(bounds[0],bounds[1],ymin=(y-.085-ymin)/(ymax-ymin),
                       ymax=(y+.085-ymin)/(ymax-ymin),alpha=.075,color=theme)
            marks=ax.vlines(bounds,y-.11,y+.11,color=theme,linewidth=1.2)
            marks.set_gid(f'reference-bounds-{i}')
        ax.plot([row['low'],row['high']],[y,y],color=theme,linewidth=2.4,alpha=0.65)
        ax.plot([row['low'],row['high']],[y,y],linestyle='none',marker='|',markersize=12,color=theme)
        ax.scatter([row['mid']],[y],color=theme,s=35,zorder=4)
        ax.text(lo-pad,y+0.20,wrap(row['label'],24 if mobile else 51),fontsize=12,va='bottom')
        ax.text((lo+hi)/2,y-0.27,f"{row['low']} — {row['mid']} — {row['high']}",fontsize=12,color='#465366',ha='center',va='top')
    return fig


def _boxes(entry,theme,mobile):
    width=360 if mobile else 760; rows=entry['rows']; height=160+120*len(rows)
    fig,ax=plt.subplots(figsize=(width/72,height/72),dpi=300)
    fig.subplots_adjust(left=0.12,right=0.95,top=0.95,bottom=0.25)
    _chart_style(ax); ax.set_gid('data-panel-0'); ax.grid(False); ax.spines['left'].set_visible(False)
    stats=[dict(label=r['label'],whislo=r['low'],q1=r['q1'],med=r['median'],q3=r['q3'],
                whishi=r['high'],fliers=r.get('outliers',[])) for r in rows]
    artists=ax.bxp(stats,orientation='horizontal',patch_artist=True,showfliers=True,positions=list(range(len(rows),0,-1)),widths=0.3,
                   boxprops={'facecolor':theme,'alpha':0.24,'edgecolor':theme},
                   medianprops={'color':theme,'linewidth':2},whiskerprops={'color':theme},capprops={'color':theme},
                   flierprops={'marker':'o','markerfacecolor':'white','markeredgecolor':'#9b5160','markersize':5})
    ax.set_yticks([])
    for i,row in enumerate(rows):
        y=len(rows)-i
        ax.text(ax.get_xlim()[0],y+0.32,row['label'],fontsize=12,va='bottom')
    label=wrap(entry['x_label'],23 if mobile else 52)
    ax.set_xlabel(label,fontsize=12,labelpad=13)
    return fig


def _network(entry,theme,mobile):
    width=360 if mobile else 760; nodes=entry['nodes']; edges=entry['edges']
    base=510 if mobile else 440; legend=[]
    for i,e in enumerate(edges):
        if 'moderates' in e:
            base_edge=edges[e['moderates']]
            label=f"{i+1}. {nodes[e['from']]['label']} ↓ {nodes[base_edge['from']]['label']} → {nodes[base_edge['to']]['label']}：{e.get('label','调节')}"
        else:
            label=f"{i+1}. {nodes[e['from']]['label']} → {nodes[e['to']]['label']}：{e.get('label','联系')}"
        legend.append(wrap(label,24 if mobile else 56))
    height=base+sum((s.count('\n')+1)*18+10 for s in legend)+15
    fig,ax=canvas(width,height)
    nw=60 if mobile else 145
    labels=[wrap(n['label'],3.5 if mobile else 10.2) for n in nodes]
    nh=[max(48,(v.count('\n')+1)*20+18) for v in labels]
    coords=[(20+nw/2+n['x']/100*(width-40-nw),65+n['y']/100*(base-145)) for n in nodes]
    latent=[i for i,n in enumerate(nodes) if n.get('shape')=='latent']
    if latent:
        shift=max(0,140-min(coords[i][1] for i in latent))
        coords=[(x,y+shift if i in latent else y) for i,(x,y) in enumerate(coords)]
        reference=min(coords[i][1]-nh[i]/2-6 for i in latent)
    for i,e in enumerate(edges):
        x1,y1=coords[e['from']]; x2,y2=coords[e['to']]
        if 'moderates' in e:
            base_edge=edges[e['moderates']]
            a,b=coords[base_edge['from']],coords[base_edge['to']]
            x2,y2=(a[0]+b[0])/2,(a[1]+b[1])/2
            if abs(x1-x2)>1e-6 or y1>=y2:
                raise ValueError('Place the moderator above the midpoint of the affected path')
            ax.add_patch(FancyArrowPatch((x1,y1+nh[e['from']]/2+6),(x2,y2),
                arrowstyle='-|>',mutation_scale=12,linewidth=1.1,color=theme,alpha=.65,
                linestyle='--' if e.get('dashed') else '-',gid=f'moderates-edge-{e["moderates"]}'))
            continue
        if e['from'] in latent and e['to'] in latent:
            start=(x1,y1-nh[e['from']]/2-6);end=(x2,y2-nh[e['to']]/2-6)
            peak=reference-(20+.10*abs(x2-x1))
            crown=(peak-(start[1]+end[1])/8)/.75
            geometry=MplPath([start,(x1,crown),(x2,crown),end],
                [MplPath.MOVETO,MplPath.CURVE4,MplPath.CURVE4,MplPath.CURVE4])
            ax.add_patch(FancyArrowPatch(path=geometry,arrowstyle='-|>',mutation_scale=12,
                linewidth=1.1,color=theme,alpha=.65,linestyle='--' if e.get('dashed') else '-',
                gid=f'factor-relation-{e["from"]}-{e["to"]}'))
            continue
        dx,dy=x2-x1,y2-y1
        reciprocal=any(a['from']==e['to'] and a['to']==e['from'] for a in edges)
        crossed=any(j not in (e['from'],e['to']) and abs((cx-x1)*dy-(cy-y1)*dx)/(math.hypot(dx,dy) or 1)<nw/2 and 0<((cx-x1)*dx+(cy-y1)*dy)/(dx*dx+dy*dy or 1)<1 for j,(cx,cy) in enumerate(coords))
        candidates=[0.28,-0.28,0.48,-0.48,0.70,-0.70] if reciprocal else [0,0.28,-0.28,0.48,-0.48,0.70,-0.70]
        def boundary(x,y,vx,vy,idx):
            factor=min((nw/2+6)/abs(vx) if vx else float('inf'),(nh[idx]/2+6)/abs(vy) if vy else float('inf'))
            return x+vx*factor,y+vy*factor
        chosen=None
        for rad in candidates:
            # Arc3 bends in DISPLAY coordinates. Derive candidates, then inspect
            # the actual clipped Matplotlib curve after conversion back to data.
            cx,cy=(x1+x2)/2-rad*dy,(y1+y2)/2+rad*dx
            start=(x1+nw/2+6,y1) if dx>nw+12 else boundary(x1,y1,cx-x1,cy-y1,e['from'])
            end=(x2-nw/2-6,y2) if dx>nw+12 else boundary(x2,y2,cx-x2,cy-y2,e['to'])
            patch=FancyArrowPatch(start,end,connectionstyle=f'arc3,rad={rad}',arrowstyle='-|>',
                mutation_scale=12,linewidth=1.1,color=theme,alpha=0.65,
                linestyle='--' if e.get('dashed') else '-')
            ax.add_patch(patch)
            safe=True
            for curve,code in patch.get_path().iter_bezier():
                for t in [n/20 for n in range(21)]:
                    px,py=curve(t)
                    if not 6<=px<=width-6 or not 20<=py<=base-12:
                        safe=False; break
                    if any(j not in (e['from'],e['to']) and abs(px-nx)<nw/2+5 and abs(py-ny)<nh[j]/2+5 for j,(nx,ny) in enumerate(coords)):
                        safe=False; break
                if not safe: break
            if safe:
                chosen=patch; break
            patch.remove()
        if chosen is None:
            raise ValueError(f'No collision-free network route for edge {i}')
    for i,(node,(x,y),label) in enumerate(zip(nodes,coords,labels)):
        face=(*plt.matplotlib.colors.to_rgb(theme),0.09)
        edge=(*plt.matplotlib.colors.to_rgb(theme),0.45)
        if node.get('shape')=='latent':
            p=Ellipse((x,y),nw,nh[i],facecolor=face,edgecolor=edge,linewidth=0.9,gid=f'node-{i}')
        else:
            p=FancyBboxPatch((x-nw/2,y-nh[i]/2),nw,nh[i],boxstyle='round,pad=0,rounding_size=9',facecolor=face,edgecolor=edge,linewidth=0.9,gid=f'node-{i}')
        ax.add_patch(p)
        _text(ax,x,y,label,size=12,ha='center')
    y=base
    for label in legend:
        ax.text(20,y,label,fontsize=12,color='#465366',va='top',linespacing=1.5)
        y+=(label.count('\n')+1)*18+10
    return fig


def make_figure(slug,entry,theme,mobile=False):
    if slug in SLUGS:
        from .illustrated_examples import make_figure as sample
        return sample(slug,mobile)
    kind=entry['kind']
    if kind=='story':
        from . import story_operational
        if slug in story_operational.SUPPORTED:
            return story_operational.make_story(slug,entry,theme,mobile)
        from . import story_foundations, story_methods, story_models
        for module in (story_foundations,story_methods,story_models):
            if slug in module.SUPPORTED:
                return module.make_story(slug,entry,theme,mobile)
        raise ValueError(f'Missing semantic story: {slug}')
    if kind in {'bars','histogram','scatter','lines'}: return _charts(entry,theme,mobile)
    functions={'table':_table,'segments':_segments,'intervals':_intervals,'boxplot':_boxes,'network':_network}
    if kind not in functions: raise ValueError(f'Unsupported figure kind: {kind}')
    return functions[kind](entry,theme,mobile)


def export_figure(fig, svg_path, pdf_path, preview_path=None):
    """Final vector exports; optional high-resolution review artifact only."""
    fig.savefig(svg_path.parent/(svg_path.stem+'.svg'))
    fig.savefig(pdf_path.parent/(pdf_path.stem+'.pdf'))
    if preview_path is not None:
        fig.savefig(preview_path.parent/(preview_path.stem+'.png'),dpi=300,transparent=False,facecolor='white')
