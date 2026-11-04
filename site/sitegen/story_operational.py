"""Quantified teaching examples, not empirical study results.

Each single plot answers one question. Source observations remain explicit;
normal-model examples fix sigma=1 and use independent density products.
The common exporter owns editable SVG/PDF and rendered collision/font audits.
"""
from itertools import combinations
from math import exp, pi, sqrt, isfinite
from matplotlib import pyplot as plt
from .illustrated_examples import _chart_style

SUPPORTED = {'p-value', 'likelihood', 'maximum-likelihood', 'reliability'}
SLEEP = [6, 6.5, 7]
INK, MUTED, ACCENT = '#202a38', '#465366', '#167d79'

def permutation_example(a, b):
    values = list(a) + list(b)
    observed = sum(a)/len(a)-sum(b)/len(b)
    differences = []
    for subset in combinations(range(len(values)), len(a)):
        group = set(subset)
        differences.append(sum(values[i] for i in group)/len(a)-
                           sum(values[i] for i in range(len(values)) if i not in group)/len(b))
    extreme = [abs(d) >= abs(observed)-1e-12 for d in differences]
    return dict(observed=observed, differences=differences, extreme=extreme,
                p=sum(extreme)/len(extreme))

def likelihood_example(observations, means, sigma):
    if not observations or sigma <= 0 or not all(isfinite(x) for x in [*observations,*means,sigma]):
        raise ValueError('Finite observations and positive sigma required')
    heights = [[exp(-.5*((x-mu)/sigma)**2)/(sigma*sqrt(2*pi)) for x in observations] for mu in means]
    likelihoods = []
    for row in heights:
        product = 1
        for height in row: product *= height
        likelihoods.append(product)
    return dict(observations=list(observations), heights=heights, likelihoods=likelihoods,
                mle=sum(observations)/len(observations))

def agreement_example(a, b):
    if len(a) != len(b) or not a: raise ValueError('Matched observations required')
    return dict(differences=[y-x for x,y in zip(a,b)],
                same_order=all((a[i]-a[j])*(b[i]-b[j])>0 for i in range(len(a)) for j in range(i)))

def _frame(title, subtitle, theme, mobile):
    width, height = (360, 490) if mobile else (760, 440)
    fig = plt.figure(figsize=(width/72,height/72),dpi=300)
    fig.text(24/width,1-30/height,title,fontsize=15 if mobile else 17,
             weight='bold',color=theme,va='top')
    fig.text(24/width,1-67/height,subtitle,fontsize=10 if mobile else 12,color=MUTED,va='top')
    ax = fig.add_axes([.17 if mobile else .12,.29,.75 if mobile else .82,.46])
    ax.set_gid('data-panel-0');_chart_style(ax)
    ax.tick_params(labelsize=10);ax.xaxis.label.set_size(11);ax.yaxis.label.set_size(11)
    return fig, ax

def _footer(fig, lines, theme):
    height=fig.get_figheight()*72
    for index,line in enumerate(lines):
        fig.text(.067 if fig.get_figwidth()<6 else .032, (88-index*23)/height,
                 line,fontsize=10.5,color=theme if index==0 else MUTED,va='top')

def make_story(slug, entry, theme, mobile=False):
    if slug not in SUPPORTED: raise ValueError('Unknown quantified teaching example')
    if slug=='p-value':
        result=permutation_example([6,8,10],[1,3,5])
        fig,ax=_frame('把差 5 分放回随机分组中',
                      '教学数据：甲 6、8、10；乙 1、3、5 分',theme,mobile)
        stack={}; ys=[]
        for d in result['differences']:
            key=round(d,8);stack[key]=stack.get(key,0)+1;ys.append(stack[key])
        ax.scatter(result['differences'],ys,s=58,c=[theme if e else '#a9b4c3' for e in result['extreme']],
                   marker='o',alpha=.75,edgecolors='white',linewidths=.8,gid='permutation-allocations')
        ax.set(xlim=(-6,6),ylim=(0,4.5),xticks=[-5,0,5],yticks=[1,2,3,4],
               xlabel='甲组均值 − 乙组均值（分）',ylabel='同一差值下的分组数')
        ax.axvspan(-6,-5,color=theme,alpha=.07);ax.axvspan(5,6,color=theme,alpha=.07)
        _footer(fig,['两端着色：2 / 20，双侧 p = 0.10',
                     '每点一种分组；固定每组 3 人，穷举 20 种。',
                     '参照条件：处理无效、组标签可交换。'],theme)
    elif slug=='likelihood':
        result=likelihood_example(SLEEP,[6,8],1)
        fig,ax=_frame('同一批记录，比较两个候选均值',
                      '教学睡眠记录：6、6.5、7 小时；固定 σ = 1',theme,mobile)
        xs=[3+i*.025 for i in range(321)]
        for mu,color,style in [(6,theme,'-'),(8,ACCENT,'--')]:
            ax.plot(xs,[exp(-.5*(x-mu)**2)/sqrt(2*pi) for x in xs],color=color,lw=1.8,ls=style,label=f'μ = {mu}')
            for x in SLEEP:ax.vlines(x,0,exp(-.5*(x-mu)**2)/sqrt(2*pi),color=color,alpha=.45,lw=1)
        ax.scatter(SLEEP,[0,0,0],s=50,color=INK,gid='observed-sleep',zorder=4,clip_on=False)
        ax.set(xlim=(3,11),ylim=(-.025,.48),xlabel='睡眠时长（小时）',ylabel='概率密度')
        fig.text(.54,.80,'实线：均值 6；虚线：均值 8',fontsize=10,color=MUTED,ha='center')
        a,b=result['likelihoods']
        _footer(fig,[f'L(6) = {a:.4f}；L(8) = {b:.4f}',
                     '同一均值下，三条记录的密度高度相乘。',
                     '似然比较参数；密度高度不等于点的概率。'],theme)
    elif slug=='maximum-likelihood':
        fig,ax=_frame('最高处对应哪一个平均时长？',
                      '教学睡眠记录：6、6.5、7 小时；固定 σ = 1',theme,mobile)
        mle=likelihood_example(SLEEP,[6,8],1)['mle']
        xs=[4+i*.02 for i in range(251)]
        ys=[exp(-len(SLEEP)*(mu-mle)**2/2) for mu in xs]
        ax.fill_between(xs,ys,color=theme,alpha=.10);ax.plot(xs,ys,color=theme,lw=2)
        ax.scatter([mle],[1],s=65,color=ACCENT,zorder=3,gid='mle-location')
        ax.vlines(mle,0,1,color=ACCENT,ls='--',lw=1,alpha=.6)
        ax.set(xlim=(4,9),ylim=(0,1.2),xticks=[4,5,6.5,8,9],
               xlabel=r'候选平均时长 $\mu$（小时）',ylabel=r'相对似然 $L(\mu)$ / L(6.5)')
        _footer(fig,[r'峰值在 $\hat{\mu}$ = 6.5 小时，相对似然为 1',
                     '固定资料，仅改变候选 μ；曲线按峰值缩放。',
                     '这里的估计是在已指定的正态模型内得到的。'],theme)
    else:
        a,b=[70,80,85,90],[72,82,87,92];agreement_example(a,b)
        fig,ax=_frame('同一作文，评分差在哪里？',
                      '教学配对评分：每行同一篇作文，n = 4',theme,mobile)
        for i,(x,y) in enumerate(zip(a,b)):ax.plot([x,y],[i,i],color=theme,alpha=.4,lw=2)
        ax.scatter(a,range(4),s=48,color=theme,alpha=.8,gid='rater-pairs',label='老师甲')
        ax.scatter(b,range(4),s=48,marker='D',facecolors='none',edgecolors=ACCENT,label='老师乙')
        ax.set(xlim=(65,97),ylim=(-.7,3.7),yticks=range(4),yticklabels=['作文 A','作文 B','作文 C','作文 D'],xlabel='作文得分')
        ax.invert_yaxis()
        fig.text(.54,.80,'实心圆：老师甲；空心菱形：老师乙',fontsize=10,color=MUTED,ha='center')
        _footer(fig,['四篇均为乙比甲高 2 分，排序相同',
                     '连线保留同一作品的对应关系与评分差距。',
                     '要区分排序一致与绝对一致；此处未估计信度。'],theme)
    return fig
