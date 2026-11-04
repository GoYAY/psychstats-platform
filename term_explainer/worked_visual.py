"""Reusable, deterministic pairwise worked examples, independent of any term."""
import math
import re
import textwrap


def _text(value,limit):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValueError('Worked-example label is missing or too long')
    return value


def prepare_pairwise(payload):
    allowed={'layout','items','example_label','order','reference_label','observed_label','rows','scope_note','output_label','next_label'}
    if set(payload)-allowed: raise ValueError('Worked examples derive results; unsupported payload fields')
    for key,limit in [('example_label',40),('reference_label',16),('observed_label',16),('scope_note',120),('output_label',24),('next_label',32)]:
        _text(payload.get(key),limit)
    items=payload.get('items')
    if not isinstance(items,list) or not 3<=len(items)<=6: raise ValueError('Use 3–6 named choices')
    ids=set()
    for item in items:
        if not isinstance(item,dict) or set(item)-{'id','label','detail'}: raise ValueError('Invalid choice')
        key=item.get('id')
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9]{1,4}',key) or key in ids: raise ValueError('Choice IDs must be short and distinct')
        ids.add(key);_text(item.get('label'),16);_text(item.get('detail'),16)
    order=payload.get('order')
    if not isinstance(order,list) or not all(isinstance(x,str) for x in order) or len(order)!=len(ids) or set(order)!=ids:
        raise ValueError('One complete, non-repeated ranking is required')
    rows=payload.get('rows')
    if not isinstance(rows,list) or not 2<=len(rows)<=6: raise ValueError('Use 2–6 pair comparisons')
    rank={key:i for i,key in enumerate(order)};seen=set();references=[];observed=[];matches=[]
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'pair','reference'}: raise ValueError('Pair rows only supply a pair and reference choice')
        pair=row['pair']
        if not isinstance(pair,list) or len(pair)!=2 or not all(isinstance(x,str) for x in pair) or len(set(pair))!=2 or not set(pair)<=ids:
            raise ValueError('A row must compare two different known choices')
        identity=frozenset(pair)
        if identity in seen or row['reference'] not in pair: raise ValueError('Duplicate pair or reference outside pair')
        seen.add(identity);actual=min(pair,key=rank.get)
        references.append(row['reference']);observed.append(actual);matches.append(int(actual==row['reference']))
    return dict(references=references,observed=observed,matches=matches)


def render_pairwise(payload,width,mobile,theme):
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    from matplotlib.patches import FancyBboxPatch
    derived=prepare_pairwise(payload)
    fig,ax=plt.subplots(figsize=(width/100,1),dpi=100)
    renderer=fig.canvas.get_renderer()
    def measure(text,size,weight='normal'):
        return renderer.get_text_width_height_descent(text,FontProperties(size=size,weight=weight),ismath=False)[0]
    pad=16 if mobile else 24;span=width-2*pad;cols=1 if mobile else 3
    item_rows=math.ceil(len(payload['items'])/cols)
    id_width=max(measure(item['id'],15,'bold') for item in payload['items'])+14
    item_columns=max(4,int((span/cols-id_width-8)/14))
    item_labels=['\n'.join(textwrap.wrap(i['label'],item_columns)) for i in payload['items']]
    item_details=['\n'.join(textwrap.wrap(i['detail'],item_columns)) for i in payload['items']]
    label_lines=max(t.count('\n')+1 for t in item_labels)
    item_height=38+17*(label_lines-1)+14*max(t.count('\n')+1 for t in item_details)
    rank_lines=[];line=''
    for key in payload['order']:
        candidate=(line+'  ＞  '+key) if line else key
        if line and measure(candidate,17,'bold')>span:
            rank_lines.append(line);line='＞  '+key
        else:line=candidate
    if line:rank_lines.append(line)
    example_y=56+item_rows*item_height+4
    section_y=example_y+46+30*len(rank_lines);table_y=section_y+44
    headers=['陈述对',payload['reference_label'],payload['observed_label'],'本对匹配']
    wrapped=['\n'.join(textwrap.wrap(s,5 if mobile else 10)) for s in headers]
    head_height=16*max(s.count('\n')+1 for s in wrapped)+14
    row_height=64 if mobile else 60;rows_y=table_y+head_height
    end_y=rows_y+row_height*len(payload['rows'])
    scope='\n'.join(textwrap.wrap(payload['scope_note'],24 if mobile else 58))
    scope_y=end_y+22;scope_end=scope_y+16*(scope.count('\n')+1)
    vector='['+', '.join(str(n) for n in derived['matches'])+']'
    output='\n'.join(textwrap.wrap(payload['output_label']+'  '+vector,17 if mobile else 14))
    output_height=20*(output.count('\n')+1)
    footer_y=scope_end+34;height=footer_y+(output_height+100 if mobile else max(output_height+30,84))
    fig.set_size_inches(width/100,height/100);fig.subplots_adjust(left=0,right=1,bottom=0,top=1)
    ax.set(xlim=(0,width),ylim=(height,0));ax.axis('off')
    ink='#233044';muted='#586478';green='#258365';red='#b75157'
    ax.text(pad,18,'01  同一份作答',va='top',fontsize=12,weight='bold',color=ink)
    for i,item in enumerate(payload['items']):
        x=pad+(i%cols)*span/cols;y=56+(i//cols)*item_height
        ax.text(x+2,y+1,item['id'],va='top',fontsize=15,weight='bold',color=theme)
        ax.text(x+id_width,y,item_labels[i],va='top',fontsize=10.2,color=ink,linespacing=1.25)
        ax.text(x+id_width,y+17*label_lines+5,item_details[i],va='top',fontsize=9,color=muted,linespacing=1.25)
    ax.text(pad,example_y,payload['example_label'],va='top',fontsize=10,color=muted)
    for i,line in enumerate(rank_lines):
        ax.text(width/2,example_y+28+30*i,line,va='top',ha='center',fontsize=17,weight='bold',color=theme)
    ax.text(pad,section_y,'02  逐对核对',va='top',fontsize=12,weight='bold',color=ink)
    centers=[pad+span*f for f in ([.08,.34,.60,.86] if mobile else [.10,.39,.64,.88])]
    ax.plot([pad,width-pad],[table_y-9]*2,color='#9ba6b7',lw=.7)
    for x,label in zip(centers,wrapped):ax.text(x,table_y,label,va='top',ha='center',fontsize=9 if mobile else 10,color=muted)
    ax.plot([pad,width-pad],[rows_y-5]*2,color='#c5cdd8',lw=.55)
    for i,row in enumerate(payload['rows']):
        top=rows_y+i*row_height;y=top+24;match=derived['matches'][i];signal=green if match else red
        ax.add_patch(FancyBboxPatch((pad,top+3),span,row_height-8,boxstyle='round,pad=0,rounding_size=7',facecolor=theme,alpha=.035,edgecolor='none'))
        pair_label=' 与 '.join(row['pair'])
        if mobile and len(pair_label)>7:pair_label='\n与\n'.join(row['pair'])
        ax.text(centers[0],y,pair_label,ha='center',va='center',fontsize=10.5,color=ink)
        ax.text(centers[1],y,derived['references'][i],ha='center',va='center',fontsize=14,weight='bold',color=theme)
        ax.text(centers[2],y,derived['observed'][i],ha='center',va='center',fontsize=14,weight='bold',color=ink)
        ax.text(centers[3],y-5,str(match),ha='center',va='center',fontsize=14,weight='bold',color=signal)
        ax.text(centers[3],y+15,'相同' if match else '不同',ha='center',va='center',fontsize=8.6,color=signal)
    ax.plot([pad,width-pad],[end_y+2]*2,color='#9ba6b7',lw=.7)
    ax.text(pad,scope_y,scope,va='top',fontsize=9,color=muted,linespacing=1.5)
    if mobile:
        ax.text(width/2,footer_y,output,ha='center',va='top',fontsize=12,weight='bold',color=theme)
        ax.annotate('',xy=(width/2,footer_y+output_height+36),xytext=(width/2,footer_y+output_height+11),arrowprops=dict(arrowstyle='->',color=theme,lw=1.2))
        ax.text(width/2,footer_y+output_height+52,'\n'.join(textwrap.wrap(payload['next_label'],19)),ha='center',va='top',fontsize=11,color=ink)
    else:
        ax.text(pad+span*.23,footer_y,output,ha='center',va='top',fontsize=12,weight='bold',color=theme)
        ax.annotate('',xy=(pad+span*.59,footer_y+9),xytext=(pad+span*.44,footer_y+9),arrowprops=dict(arrowstyle='->',color=theme,lw=1.2))
        ax.text(pad+span*.78,footer_y,'\n'.join(textwrap.wrap(payload['next_label'],15)),ha='center',va='top',fontsize=11,color=ink)
    return fig,height,derived
