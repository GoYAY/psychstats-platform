"""Offline Matplotlib artwork for the five approved teaching examples.

Contract: compare unchanged teaching counts, or show concrete changes in a
conceptual story. Transparent surfaces never encode another measured variable.
Website builds consume cached SVGs; they do not import this plotting module.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Microsoft YaHei', 'DejaVu Sans'],
    'font.size': 13, 'svg.fonttype': 'none', 'pdf.fonttype': 42,
    'axes.labelcolor': '#303b4b', 'text.color': '#202a38',
    'axes.edgecolor': '#a7b1bf', 'xtick.color': '#465366',
    'ytick.color': '#465366', 'axes.spines.top': False,
    'axes.spines.right': False, 'savefig.transparent': True,
})

ROOT = Path(__file__).resolve().parents[1]
SLUGS = ('central-tendency-and-dispersion', 'skewness', 'degrees-of-freedom',
         'population-and-sample', 'data-cleaning')
HEIGHTS = {
    'central-tendency-and-dispersion': (380, 610), 'skewness': (370, 420),
    'degrees-of-freedom': (710, 920), 'population-and-sample': (430, 680),
    'data-cleaning': (570, 900),
}
BLUE, ROSE, TEAL = '#244da4', '#a33052', '#006d70'


def _data(slug):
    return json.loads((ROOT / 'content/plain_visuals/foundations.json').read_text(encoding='utf-8'))[slug]


def _surface(ax, x, y, w, h, color, alpha=0.055):
    # Flat translucent surface: no simulated 3D geometry on measured marks.
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0,rounding_size=14',
                               facecolor=color, alpha=alpha, edgecolor='none'))
    ax.plot([x+16, x+w-16], [y+1, y+1], color='white', linewidth=2, alpha=0.9)


def _text(ax, x, y, value, color='#202a38', size=14, weight='normal', gid=None, ha='left'):
    return ax.text(x, y, value, fontsize=size, color=color, weight=weight,
                   ha=ha, va='center', gid=gid)


def _arrow(ax, a, b, color):
    arrow = FancyArrowPatch(a, b, arrowstyle='-|>', mutation_scale=15,
                           linewidth=1.3, color=color, alpha=0.7)
    ax.add_patch(arrow)
    return arrow


def _person(ax, x, y, color, selected=False):
    ax.add_patch(Circle((x, y-10), 7, facecolor=color, alpha=0.70 if selected else 0.16, edgecolor='none'))
    ax.add_patch(FancyBboxPatch((x-11, y), 22, 20, boxstyle='round,pad=0,rounding_size=7',
                               facecolor=color, alpha=0.55 if selected else 0.12, edgecolor='none'))
    if selected:
        ax.add_patch(Circle((x, y+3), 25, fill=False, edgecolor=color, linewidth=1.2, alpha=0.6))


def _canvas(slug, mobile):
    width, height = (360 if mobile else 760), HEIGHTS[slug][bool(mobile)]
    fig = plt.figure(figsize=(width/72, height/72), dpi=300)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, width), ylim=(height, 0))
    ax.axis('off')
    return fig, ax, width, height


def _chart_style(ax):
    ax.set_gid('data-panel')
    ax.set_axisbelow(True)
    ax.grid(axis='y', color='#8193af', alpha=0.14, linewidth=0.7)
    ax.tick_params(length=0, pad=7, labelsize=12)
    for spine in ax.spines.values():
        spine.set_linewidth(0.7)
    ax.set_facecolor('none')


def _classes(mobile):
    width, height = (360 if mobile else 760), HEIGHTS[SLUGS[0]][bool(mobile)]
    fig, axes = plt.subplots(2 if mobile else 1, 1 if mobile else 2,
                             figsize=(width/72, height/72), dpi=300, squeeze=False)
    fig.subplots_adjust(left=0.17 if mobile else 0.09, right=0.97,
                        bottom=0.17 if mobile else 0.22, top=0.86,
                        hspace=0.60, wspace=0.27)
    colors = [BLUE, '#6657bd']
    for ax, series, color in zip(axes.flat, _data(SLUGS[0])['chart']['series'], colors):
        xs, ys = zip(*series['values'])
        _chart_style(ax)
        ax.bar(xs, ys, width=3.7, color=color, alpha=0.38, edgecolor=color, linewidth=1.0)
        ax.set(xlim=(56, 104), ylim=(0, 7), xticks=[60, 70, 80, 90, 100], yticks=[0, 2, 4, 6])
        ax.set_xlabel('成绩（分）', labelpad=10)
        ax.set_ylabel('学生人数（人）', labelpad=9)
        ax.vlines(80, 0, 1.7, color=color, linewidth=1.0, linestyle=(0, (3, 4)), alpha=0.7)
        ax.set_title(series['label'], fontsize=14, color=color, pad=20, loc='left')
        for x, y in zip(xs, ys):
            if y:
                ax.text(x, y+0.18, str(y), ha='center', va='bottom', color=color, fontsize=12)
    fig.text(0.09 if not mobile else 0.17, 0.035 if mobile else 0.05,
             '同样平均80分，成绩的聚拢程度却不同。', fontsize=12, color='#465366')
    return fig


def _skew(mobile):
    width, height = (360 if mobile else 760), HEIGHTS['skewness'][bool(mobile)]
    fig, ax = plt.subplots(figsize=(width/72, height/72), dpi=300)
    fig.subplots_adjust(left=0.18 if mobile else 0.09, right=0.97,
                        bottom=0.20, top=0.75)
    _chart_style(ax)
    values = _data('skewness')['chart']['series'][0]['values']
    xs, ys = zip(*values)
    ax.bar(xs, ys, width=10, color=BLUE, alpha=0.35, edgecolor=BLUE, linewidth=0.7)
    ax.set(xlim=(0, 100), ylim=(0, 17), xticks=[0, 20, 40, 60, 80, 100], yticks=[0, 5, 10, 15])
    ax.set_xlabel('完成任务时间（秒）', labelpad=12)
    ax.set_ylabel('完成人数（人）', labelpad=10)
    fig.text(0.18 if mobile else 0.09, 0.92, '大多数人较快完成', color=BLUE, fontsize=14, weight='bold')
    fig.text(0.18 if mobile else 0.09, 0.85, '少数人的较长用时，把尾巴拖向右边。', fontsize=12)
    ax.annotate('右侧长尾', xy=(88, 1.3), xytext=(65 if mobile else 73, 8.5),
                color=BLUE, fontsize=12, ha='center',
                arrowprops={'arrowstyle': '->', 'color': BLUE, 'linewidth': 1.2,
                            'connectionstyle': 'arc3,rad=-0.16'})
    return fig


def _payments(mobile):
    fig, ax, w, h = _canvas('degrees-of-freedom', mobile)
    _text(ax, 20, 27, '三个人，一张90元账单', color=ROSE, size=16, weight='bold')
    _text(ax, 20, 55, '可以不平摊，但最后必须付够90元。', size=13)
    states = [([], '先定总额', '三人还没有决定各付多少', '还差 90 元'),
              ([20], '甲自行选20元', '他可以改，但其他人要一起补足', '还差 70 元'),
              ([20, 30], '乙自行选30元', '前两笔定下，剩余金额随之确定', '还差 40 元'),
              ([20, 30, 40], '丙只能补40元', '不是第三次独立选择，而是补足余额', '正好 90 元')]
    rowh = 202 if mobile else 151
    people_colors = (ROSE, '#246b91', '#187b55')
    for i, (paid, title, subtitle, remaining) in enumerate(states):
        top = 84+i*rowh
        _surface(ax, 16, top, w-32, rowh-16, ROSE)
        _text(ax, 30, top+24, f'{i+1:02d}', color=ROSE, size=13, weight='bold')
        _text(ax, 65, top+24, title, size=15, weight='bold')
        _text(ax, 30, top+52, subtitle, size=12)
        bx, by, bw = 30, top+77, w-60
        ax.add_patch(FancyBboxPatch((bx, by), bw, 30, boxstyle='round,pad=0,rounding_size=6',
                                   facecolor=ROSE, alpha=0.06, edgecolor=ROSE, linewidth=0.8))
        offset = 0
        for j, amount in enumerate(paid):
            sw = bw*amount/90
            ax.add_patch(Rectangle((bx+offset, by), sw, 30, facecolor=people_colors[j], alpha=0.26, edgecolor='white'))
            _text(ax, bx+offset+sw/2, by+15, f'{"甲乙丙"[j]} {amount}', size=12, color=people_colors[j], ha='center')
            offset += sw
        _text(ax, 30, top+130 if mobile else top+126, remaining, color='#187b55' if i==3 else '#465366', size=14,
              weight='bold', gid=f'remaining-{i}')
        if mobile:
            for j in range(3):
                _person(ax, 210+40*j, top+149, people_colors[j], j < len(paid))
    _text(ax, 20, h-22, '能各自定的金额只有两笔。', size=14, color=ROSE, weight='bold')
    return fig


def _population(mobile):
    fig, ax, w, h = _canvas('population-and-sample', mobile)
    _text(ax, 20, 29, '想了解全校学生的睡眠', color=BLUE, size=16, weight='bold')
    x, y, bw, bh = 16, 66, (w-32 if mobile else 330), 240
    _surface(ax, x, y, bw, bh, BLUE)
    _text(ax, x+18, y+25, '全校学生 · 想了解的范围', size=14, weight='bold')
    selected = {1, 7, 10, 14, 18}
    centers = []
    for i in range(20):
        px, py = x+38+(i%5)*57, y+78+(i//5)*43
        _person(ax, px, py, BLUE, i in selected)
        if i in selected:
            centers.append((px, py))
    sx, sy = (16, 365) if mobile else (410, 66)
    _surface(ax, sx, sy, w-32 if mobile else 334, 240, TEAL)
    _text(ax, sx+18, sy+25, '抽取200人 · 实际调查的范围', size=14, weight='bold')
    for i in range(5):
        _person(ax, sx+38+i*57, sy+90, TEAL, True)
    _text(ax, sx+18, sy+148, '这200人的睡眠记录', size=14, color=TEAL, weight='bold')
    _text(ax, sx+18, sy+180, '用来估计全校情况，而不是代替全校。', size=12)
    if mobile:
        _arrow(ax, (w/2, 317), (w/2, 355), BLUE)
        _text(ax, w/2+18, 334, '抽样', color=BLUE, size=12)
    else:
        _arrow(ax, (355, 170), (398, 170), BLUE)
        _text(ax, 376, 146, '抽样', color=BLUE, size=12, ha='center')
    _text(ax, 20, h-54, '圈起的人来自全校，不等于全校只有这些人。', size=12)
    _text(ax, 20, h-27, '人数与人物图标均为示意；图标不对应200人的实际比例。', size=10.5, color='#465366')
    return fig


def _cleaning(mobile):
    fig, ax, w, h = _canvas('data-cleaning', mobile)
    _text(ax, 20, 27, '先核对证据，再改记录', color=TEAL, size=16, weight='bold')
    cases = [
        ('年龄', '200 岁', '原始问卷确认：20岁', '20 岁', '修正多输入的一个零'),
        ('同一编号', 'ID07 / ID07', '核对提交时间与有效版本', 'ID07 一份', '按预先规则保留有效版本'),
        ('睡眠时长', '7 小时 / 420 分钟', '原问卷确认各自填写单位', '7 小时 / 7 小时', '换成同一单位，含义不变'),
    ]
    rowh = 279 if mobile else 166
    for i, (name, raw, check, clean, reason) in enumerate(cases):
        top = 62+i*rowh
        _surface(ax, 16, top, w-32, rowh-15, TEAL)
        _text(ax, 30, top+23, name, size=14, weight='bold')
        if mobile:
            _text(ax, 30, top+57, '原记录', size=11, color='#465366')
            _text(ax, 30, top+86, raw, size=15, color='#ae3f53' if i==0 else '#966111')
            _arrow(ax, (w/2, top+108), (w/2, top+139), TEAL)
            _text(ax, w/2, top+160, check, size=12, ha='center', gid=f'cleaning-check-{i}')
            _text(ax, 30, top+198, clean, size=15, color='#187b55', weight='bold')
            _text(ax, 30, top+230, reason, size=12)
        else:
            _text(ax, 30, top+56, '原记录', size=11, color='#465366')
            _text(ax, 30, top+86, raw, size=15, color='#ae3f53' if i==0 else '#966111')
            _arrow(ax, (225, top+84), (272, top+84), TEAL)
            _text(ax, 290, top+66, check, size=12)
            _text(ax, 290, top+97, '证据 → 处理依据', size=11, color='#465366')
            _arrow(ax, (476, top+84), (515, top+84), TEAL)
            _text(ax, 536, top+82, clean, size=15, color='#187b55', weight='bold')
            _text(ax, 30, top+131, reason+'；保留修改记录。', size=12)
    return fig


def make_figure(slug, mobile=False):
    """Return an unsaved, editable figure. Data geometry is never inferred by AI."""
    functions = dict(zip(SLUGS, (_classes, _skew, _payments, _population, _cleaning)))
    if slug not in functions:
        raise ValueError(f'Unsupported teaching example: {slug}')
    return functions[slug](mobile)


def export_samples():
    """Editable SVG/PDF + 300-dpi review PNG; preserve final geometry audits."""
    import sys
    import xml.etree.ElementTree as ET
    skill_scripts = Path.home() / '.codex/skills/nature-figure/scripts'
    sys.path.insert(0, str(skill_scripts))
    from audit_panel_alignment import require_matplotlib_panel_alignment
    assets = ROOT / 'assets/examples-v2'
    audit = ROOT.parent / 'logs/figure-v2'
    assets.mkdir(parents=True, exist_ok=True)
    audit.mkdir(parents=True, exist_ok=True)
    ns = 'http://www.w3.org/2000/svg'
    ET.register_namespace('', ns)
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    for slug in SLUGS:
        for mobile in (False, True):
            stem = slug + ('-mobile' if mobile else '')
            fig = make_figure(slug, mobile)
            fig.canvas.draw()
            if slug == 'central-tendency-and-dispersion':
                for index, ax in enumerate(fig.axes):
                    ax.set_gid(f'comparison-panel-{index}')
                require_matplotlib_panel_alignment(fig, json_out=str(audit / (stem+'.alignment.json')),
                    overlay_svg=str(audit / (stem+'.alignment.svg')), strict=True)
            fig.savefig(assets / (stem+'.svg'))
            fig.savefig(audit / (stem+'.pdf'))
            fig.savefig(audit / (stem+'.png'), dpi=300, transparent=False, facecolor='white')
            plt.close(fig)
            path = assets / (stem+'.svg')
            tree = ET.parse(path)
            svg = tree.getroot()
            svg.set('role', 'img')
            svg.set('aria-labelledby', 'title desc')
            entry = _data(slug)
            for tag, body in [('title', entry['title']), ('desc', entry['takeaway']+'。'+entry['limit'])]:
                node = ET.Element('{'+ns+'}'+tag, id=tag)
                node.text = body
                svg.insert(0, node)
            tree.write(path, encoding='utf-8', xml_declaration=True)
            print(stem, flush=True)
