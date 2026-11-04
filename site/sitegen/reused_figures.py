"""Adapt original simple SVG geometry through the exclusive Python backend.

The measured coordinates, labels and teaching results remain unchanged. This is
not SVG rasterization: every original mark is reconstructed as editable artists.
"""
import re
import xml.etree.ElementTree as ET
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, PathPatch
from matplotlib.path import Path as MplPath
from matplotlib.colors import to_rgba
from .rollout_figures import canvas


def _path(value):
    tokens=re.findall(r'[MLHVQCZmlhvqcz]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',value)
    vertices,codes=[],[]; i=0; command=None; x=y=0; origin=(0,0)
    while i<len(tokens):
        if tokens[i].isalpha(): command=tokens[i]; i+=1
        relative=command.islower(); cmd=command.upper()
        if cmd=='Z':
            vertices.append(origin); codes.append(MplPath.CLOSEPOLY); x,y=origin; command=None; continue
        n={'M':2,'L':2,'H':1,'V':1,'Q':4,'C':6}[cmd]
        values=[float(t) for t in tokens[i:i+n]]; i+=n
        if cmd in ('H','V'):
            if cmd=='H': x=(x+values[0]) if relative else values[0]
            else: y=(y+values[0]) if relative else values[0]
            vertices.append((x,y)); codes.append(MplPath.LINETO)
        else:
            points=[(values[j]+(x if relative else 0),values[j+1]+(y if relative else 0)) for j in range(0,n,2)]
            for p in points:
                vertices.append(p); codes.append({'M':MplPath.MOVETO,'L':MplPath.LINETO,'Q':MplPath.CURVE3,'C':MplPath.CURVE4}[cmd])
            x,y=points[-1]
            if cmd=='M': origin=(x,y); command='l' if relative else 'L'
    return MplPath(vertices,codes)


def make_reused_figure(source,theme):
    root=ET.parse(source).getroot()
    _,_,width,height=[float(v) for v in root.get('viewBox').split()]
    fig,ax=canvas(width,height)
    def paint(original,role):
        if original in ('none',None): return 'none'
        if original in ('white','#fff','#ffffff'): return to_rgba('white',0.90)
        if original.lower() in ('#244da4','#2447a5','#2563a0'):
            return to_rgba(theme,0.46 if role=='fill' else 0.90)
        if role=='fill' and original.lower() in ('#eff4ff','#f5f7fb','#f6f8fb','#dbeafe','#dce7f4'):
            return to_rgba(theme,0.06)
        return to_rgba(original,0.40 if role=='fill' else 0.75)
    def visit(node,parent=None):
        attrs={**(parent or {}),**node.attrib}; tag=node.tag.rsplit('}',1)[-1]
        if tag in ('defs','title','desc'): return
        fill=attrs.get('fill','#111827'); stroke=attrs.get('stroke','none')
        width_line=min(float(attrs.get('stroke-width',1)),1.8)
        linestyle=(0,tuple(float(v) for v in attrs['stroke-dasharray'].split())) if attrs.get('stroke-dasharray') else '-'
        kw={'facecolor':paint(fill,'fill'),'edgecolor':paint(stroke,'stroke'),'linewidth':width_line,'linestyle':linestyle}
        if tag=='text':
            value=''.join(node.itertext()).replace('蓝线：','实线：')
            if value:
                color=theme if fill.lower() in ('#244da4','#2447a5','#2563a0') else fill
                tx,ty=float(attrs.get('x',0)),float(attrs.get('y',0))
                align={'middle':'center','end':'right'}.get(attrs.get('text-anchor'),'left')
                if source.name=='p-value.svg' and value.startswith('零假设 H'):
                    tx,align=100,'left'
                if source.name=='data-cleaning-mobile.svg' and value in ('可核实','无法核实'):
                    tx=30 if value=='可核实' else 250
                    align='left'
                ax.text(tx,ty,value,
                        fontsize=float(attrs.get('font-size',14)),color=color,va='baseline',
                        fontfamily=['Microsoft YaHei','DejaVu Sans'],
                        ha=align,
                        weight='bold' if attrs.get('font-weight') in ('700','600','bold') else 'normal')
        elif tag=='rect':
            rw,rh=float(attrs['width']),float(attrs['height'])
            if rw>=width and rh>=height:
                pass # Transparent canvas, rather than a solid white background.
            else:
                ax.add_patch(FancyBboxPatch((float(attrs.get('x',0)),float(attrs.get('y',0))),rw,rh,
                                           boxstyle=f"round,pad=0,rounding_size={float(attrs.get('rx',0))}",**kw))
        elif tag=='circle':
            ax.add_patch(Circle((float(attrs['cx']),float(attrs['cy'])),float(attrs['r']),**kw))
        elif tag=='line':
            a=(float(attrs['x1']),float(attrs['y1'])); b=(float(attrs['x2']),float(attrs['y2']))
            if attrs.get('marker-end'):
                ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=12,color=paint(stroke,'stroke'),linewidth=width_line))
            else:
                ax.plot([a[0],b[0]],[a[1],b[1]],color=paint(stroke,'stroke'),linewidth=width_line,linestyle=linestyle)
        elif tag=='polyline':
            numbers=[float(v) for v in re.findall(r'[-+]?[\d.]+(?:[eE][-+]?\d+)?',attrs['points'])]
            ax.plot(numbers[::2],numbers[1::2],color=paint(stroke,'stroke'),linewidth=width_line,linestyle=linestyle)
        elif tag=='path':
            geometry=_path(attrs['d'])
            if source.name=='data-cleaning-mobile.svg':
                return # Recreate its branching relationships as complete curves below.
            if attrs.get('marker-end'):
                if sum(geometry.codes==MplPath.LINETO)>1:
                    points=geometry.vertices
                    geometry=MplPath([points[0],points[1],points[-2],points[-1]],
                        [MplPath.MOVETO,MplPath.CURVE4,MplPath.CURVE4,MplPath.CURVE4])
                ax.add_patch(FancyArrowPatch(path=geometry,arrowstyle='-|>',mutation_scale=10,
                    color=paint(stroke,'stroke'),linewidth=width_line,linestyle=linestyle))
            else:
                ax.add_patch(PathPatch(geometry,**kw))
        for child in node:
            visit(child,attrs)
    visit(root)
    if source.name=='data-cleaning-mobile.svg':
        for start,end in [((160,91),(160,106)),((160,160),(160,175))]:
            ax.add_patch(FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=8,
                color=paint('#64748b','stroke'),linewidth=1.2,shrinkA=0,shrinkB=0))
        for start,end,level in [((160,229),(82,261),245),((160,229),(238,261),245),
            ((82,370),(160,403),389),((238,370),(160,403),389)]:
            geometry=MplPath([start,(start[0],level),(end[0],level),end],
                [MplPath.MOVETO,MplPath.CURVE4,MplPath.CURVE4,MplPath.CURVE4])
            ax.add_patch(FancyArrowPatch(path=geometry,arrowstyle='-|>',mutation_scale=8,
                color=paint('#64748b','stroke'),linewidth=1.2))
    return fig
