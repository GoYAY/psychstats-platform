"""Trusted statistical layouts selected by validated teaching intent."""
import math
import textwrap
from .visual_presentation import validate_presentation

def make_statistical_figure(spec: dict,width: int,mobile: bool,theme: str):
    import matplotlib.pyplot as plt
    from .figures import validate_visual
    validate_visual(spec)
    policy=validate_presentation(spec,required=True)
    if spec['kind']!='statistical':raise ValueError('Statistical visual required')
    payload=spec['payload'];series=payload['series'];count=len(series);facets=policy['layout']=='facets'
    chart=payload['chart_type']
    def interpolatable(values):
        return len(values)>1 and all(type(v) in (int,float) for v in values) and values[1]>values[0] and all(math.isclose(b-a,values[1]-values[0]) for a,b in zip(values,values[1:]))
    categorical=chart=='bar' and not all(interpolatable(s['x']) for s in series)
    horizontal=categorical and (max(len(s['x']) for s in series)>8 or (mobile and max(len(str(x)) for s in series for x in s['x'])>8))
    height=(300*count+45 if mobile else 370) if facets else (340 if mobile else 370)
    if horizontal:height=max(height,(max(len(s['x']) for s in series)*25+120)*(count if facets and mobile else 1))
    rows,cols=(count,1) if facets and mobile else (1,count if facets else 1)
    fig,grid=plt.subplots(rows,cols,figsize=(width/100,height/100),squeeze=False,sharex=facets,sharey=facets)
    axes=list(grid.flat)
    fig.subplots_adjust(left=.20 if mobile else .11,right=.96,bottom=.15 if mobile and not facets else .16 if not mobile else .09,top=.88,hspace=.65,wspace=.30)
    if horizontal:fig.subplots_adjust(left=.38 if mobile else .23,bottom=65/height,top=1-50/height,hspace=.55,wspace=.45)
    colors=[theme,'#7c6cb3','#409585','#b78a50']
    for i,item in enumerate(series):
        ax=axes[i] if facets else axes[0];color=colors[i];chart=payload['chart_type']
        if chart=='bar':
            n=len(item['x']);offset=0 if facets or count==1 else (i-(count-1)/2)*.72/count
            positions=[j+offset for j in range(n)];bar_width=.66 if facets or count==1 else .66/count
            bars=ax.barh(positions,item['y'],height=bar_width,color=color,alpha=.34,edgecolor=color,linewidth=.65,label=item['label']) if horizontal else ax.bar(positions,item['y'],width=bar_width,color=color,alpha=.34,edgecolor=color,linewidth=.65,label=item['label'])
            step=1 if categorical else max(1,math.ceil(n/(5 if mobile or facets else 10)));ticks=list(range(0,n,step))
            if n-1 not in ticks:ticks.append(n-1)
            labels=[str(item['x'][j]) for j in ticks]
            if horizontal:
                ax.set_yticks(ticks,['\n'.join(textwrap.wrap(v,8 if mobile else 12)) for v in labels]);ax.set_ylim(n-.4,-.6)
            else:
                wrap=max(2,int(width*(.76 if mobile else .8)/max(1,len(ticks))/9/(count if facets and not mobile else 1)))
                ax.set_xticks(ticks,['\n'.join(textwrap.wrap(v,wrap)) for v in labels]);ax.set_xlim(-.6,n-.4)
                if categorical:fig.subplots_adjust(bottom=max(.18,min(.38,.14+.04*max(math.ceil(len(v)/wrap) for v in labels))))
            if policy['numeric_role']=='exact':
                maximum=max(item['y'])
                for bar,value in zip(bars,item['y']):
                    if value and (n*count<=12 or value==maximum):
                        point=(value,bar.get_y()+bar.get_height()/2) if horizontal else (bar.get_x()+bar.get_width()/2,value)
                        ax.annotate(f'{value:g}',point,xytext=(4,0) if horizontal else (0,4),textcoords='offset points',ha='left' if horizontal else 'center',va='center' if horizontal else 'bottom',fontsize=9,color=color)
        elif chart=='histogram':
            edges=item['bin_edges'];ax.bar(edges[:-1],item['counts'],width=[b-a for a,b in zip(edges,edges[1:])],align='edge',color=color,alpha=.30,edgecolor=color,linewidth=.65,label=item['label'])
        elif chart=='line':ax.plot(item['x'],item['y'],color=color,linewidth=1.7,label=item['label'])
        else:ax.scatter(item['x'],item['y'],color=color,alpha=.58,s=22,label=item['label'])
        if facets:ax.set_title('\n'.join(textwrap.wrap(item['label'],16 if mobile else max(10,int(42/count)))),fontsize=10,color=color,pad=12)
    chart=payload['chart_type']
    all_y=[v for item in series for v in item['counts' if chart=='histogram' else 'y']]
    if chart in ('bar','histogram'):
        for ax in axes:
            if horizontal:ax.set_xlim(min(0,min(all_y)*1.15),max(1,max(all_y)*1.22))
            else:ax.set_ylim(min(0,min(all_y)*1.15),max(1,max(all_y)*1.22))
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
        # Exact bar labels carry the readings; grid strokes through those labels
        # add noise and fail the real PDF collision check.
        if not (chart=='bar' and policy['numeric_role']=='exact'):ax.grid(axis='x' if horizontal else 'y',alpha=.12)
        ax.set_axisbelow(True)
        ax.tick_params(labelsize=9,labelbottom=True,labelleft=True)
        xlabel='y' if horizontal else 'x';ylabel='x' if horizontal else 'y'
        ax.set_xlabel(payload[xlabel+'_label']+(f"（{payload[xlabel+'_unit']}）" if payload.get(xlabel+'_unit') else ''),fontsize=10)
        ax.set_ylabel(payload[ylabel+'_label']+(f"（{payload[ylabel+'_unit']}）" if payload.get(ylabel+'_unit') else ''),fontsize=10)
    if not facets and count>1:axes[0].legend(fontsize=9,frameon=False,loc='lower left',bbox_to_anchor=(0,1.04),borderaxespad=0)
    audit=dict(layout=policy['layout'],numeric_role=policy['numeric_role'],axes=[dict(xlim=list(a.get_xlim()),ylim=list(a.get_ylim())) for a in axes])
    return fig,height,audit
