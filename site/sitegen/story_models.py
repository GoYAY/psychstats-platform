"""Conceptual measurement stories; no empirical scores or reliability estimates.

Contract: keep the measured object matched while varying environment, rater,
occasion or proposed interpretation. Payment lengths alone encode amounts.
The caller owns export and final PDF/phone QA; normal builds read cached SVGs.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, FancyBboxPatch, Rectangle, FancyArrowPatch

from .illustrated_examples import _arrow, _person, _surface, _text


SUPPORTED = {'measurement-error', 'model-identification', 'reliability', 'validity'}
HEIGHTS = {
    'measurement-error': (470, 760),
    'model-identification': (490, 560),
    'reliability': (660, 840),
    'validity': (640, 840),
}


def _canvas(slug, mobile):
    width = 360 if mobile else 760
    height = HEIGHTS[slug][bool(mobile)]
    fig = plt.figure(figsize=(width / 72, height / 72), dpi=300)
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, width), ylim=(height, 0))
    ax.set_facecolor('none')
    ax.axis('off')
    return fig, ax, width, height


def _label(ax, x, y, value, *, mobile=False, size=14, **kwargs):
    """Wrap explanatory prose; semantic/direct object labels stay unwrapped."""
    length = 23 if mobile else 48
    lines = '\n'.join(value[i:i + length] for i in range(0, len(value), length))
    return _text(ax, x, y, lines, size=size, **kwargs)


def _paper(ax, x, y, width, height, color, gid=None, ruled=True):
    patch = FancyBboxPatch((x, y), width, height,
                          boxstyle='round,pad=0,rounding_size=5',
                          facecolor=color, alpha=0.07, edgecolor='none', gid=gid)
    ax.add_patch(patch)
    for dy in (height * .32, height * .50, height * .68) if ruled else ():
        ax.plot([x + 10, x + width - 10], [y + dy, y + dy], color=color,
                alpha=.30, linewidth=1)


def _measurement(entry, color, mobile):
    fig, ax, w, h = _canvas('measurement-error', mobile)
    _text(ax, 20, 28, '人和任务相同，环境改变', color=color, size=16, weight='bold')
    _label(ax, 20, 59, '记录的是表现，环境也可能进入记录。', mobile=mobile, size=13)
    for index, key in enumerate(('quiet', 'noisy')):
        x = 16 if mobile else 16 + index * 390
        y = 99 + index * 292 if mobile else 103
        cw = 328 if mobile else 338
        _surface(ax, x, y, cw, 250, color)
        environment = '安静教室' if index == 0 else '走廊有声音干扰'
        _text(ax, x + 18, y + 26, environment, size=14, weight='bold', gid=f'environment-{key}')
        _person(ax, x + 58, y + 100, color, True)
        _text(ax, x + 26, y + 154, '学生A', color=color, gid=f'identity-{key}')
        # Same table, task sheet and target on both occasions: no result geometry.
        ax.add_patch(Rectangle((x + 108, y + 115), 132, 7, facecolor=color, alpha=.22))
        ax.plot([x + 121, x + 121], [y + 122, y + 159], color=color, alpha=.25)
        ax.plot([x + 228, x + 228], [y + 122, y + 159], color=color, alpha=.25)
        _paper(ax, x + 126, y + 66, 76, 48, color, gid=f'task-sheet-{key}')
        ax.add_patch(Circle((x + 164, y + 78), 5, fill=False, edgecolor=color, linewidth=1))
        _text(ax, x + 105, y + 181, '同一注意力任务', size=13, gid=f'task-{key}')
        _text(ax, x + 18, y + 220, f'保留记录{"甲" if index == 0 else "乙"}', color=color, size=14)
        if index:
            for r in (12, 23, 34):
                ax.add_patch(Arc((x + 266, y + 93), 2 * r, 2 * r,
                                 theta1=135, theta2=225, edgecolor=color, alpha=.5, linewidth=1.2))
    if mobile:
        _arrow(ax, (180, 355), (180, 386), color)
    else:
        _arrow(ax, (362, 218), (398, 218), color)
    _label(ax, 20, h - 63, '同一人、同一任务，前后记录配对比较。', mobile=mobile, size=13)
    _label(ax, 20, h - 27, '不预设分数升降；图中未量化环境影响。', mobile=mobile,
           size=12, gid='measurement-note')
    return fig


def _identification(entry, color, mobile):
    fig, ax, w, h = _canvas('model-identification', mobile)
    _text(ax, 20, 28, '总额不变，分法可以变', color=color, size=16, weight='bold')
    _text(ax, 20, 58, '只有账单：甲乙共付90元', size=14, weight='bold')
    _label(ax, 20, 87, '没有个人付款记录，两种组合都符合已知总额。', mobile=mobile, size=12)
    rowh = 176 if mobile else 148
    for i, (a, b) in enumerate(((40, 50), (30, 60))):
        top = 121 + i * rowh
        _surface(ax, 16, top, w - 32, rowh - 18, color)
        _text(ax, 30, top + 26, f'可能组合{"一" if i == 0 else "二"}', size=14, weight='bold')
        bx, by, bw = 50, top + 50, w - 100
        offset = 0
        for j, amount in enumerate((a, b)):
            segment = bw * amount / 90
            ax.add_patch(Rectangle((bx + offset, by), segment, 36, facecolor=color,
                                   alpha=.24 if j == 0 else .43, edgecolor='none',
                                   gid=f'payment-{i}-{j}'))
            _text(ax, bx + offset + segment / 2, by + 18,
                  f'{"甲乙"[j]} {amount}元', color=color, size=14, ha='center')
            offset += segment
        # Same overall endpoints, different interior division.
        ax.plot([bx + bw * a / 90] * 2, [by - 5, by + 41],
                color=color, linewidth=1, alpha=.6)
        _text(ax, 30, top + 114, f'甲{a}元 + 乙{b}元 = 90元',
              color=color, size=14, gid=f'allocation-{i}')
    _label(ax, 20, h - 51, '能重现90元，也不能选出唯一分法。', mobile=mobile, size=14, weight='bold')
    _label(ax, 20, h - 23, '这是信息不足的类比，不是统计识别算法。', mobile=mobile, size=12)
    return fig


def _reliability(entry, color, mobile):
    fig, ax, w, h = _canvas('reliability', mobile)
    _text(ax, 20, 28, '同一对象，不同的重复方式', color=color, size=16, weight='bold')
    _surface(ax, 16, 66, w - 32, 330 if mobile else 276, color)
    _text(ax, 30, 93, '评分者之间：同一篇作文交给两位老师', size=12 if mobile else 14, weight='bold')
    sx = w / 2 - 37
    _paper(ax, sx, 118, 74, 55, color, gid='same-essay')
    _text(ax, w / 2, 193, '同一篇作文', color=color, ha='center', gid='essay-source')
    raters = (96, 264) if mobile else (210, 550)
    for index, rx in enumerate(raters):
        _arrow(ax, (w / 2 + (-16 if index == 0 else 16), 211), (rx, 239), color)
        _person(ax, rx, 259, color, True)
        _text(ax, rx, 299, f'老师{"甲" if index == 0 else "乙"}', color=color, ha='center', gid=f'rater-{index}')
        if mobile:
            _text(ax, rx, 337, f'评分记录{"甲" if index == 0 else "乙"}', size=13, ha='center')
    if mobile:
        _text(ax, w / 2, 375, '比较同一作文的两份评分', size=13, ha='center')
    else:
        _text(ax, w / 2, 320, '比较同一作文的两份评分记录', size=13, ha='center')
    top = 422 if mobile else 369
    _surface(ax, 16, top, w - 32, 327 if mobile else 225, color)
    _text(ax, 30, top + 27, '时间之间：同一学生隔时填写同一问卷', size=12 if mobile else 14, weight='bold')
    xs = (95, 265) if mobile else (210, 550)
    for i, x in enumerate(xs):
        _text(ax, x, top + 69, '第一次' if i == 0 else '隔一段时间', size=13, ha='center', gid=f'occasion-{i}')
        _person(ax, x, top + 107, color, True)
        _text(ax, x, top + 152, '学生A', color=color, ha='center', gid=f'occasion-identity-{i}')
        if mobile:
            _paper(ax, x - 27, top + 174, 54, 48, color)
            _text(ax, x, top + 242, f'回答记录{"甲" if i == 0 else "乙"}', size=13, ha='center')
    _arrow(ax, (xs[0] + 35, top + 104), (xs[1] - 35, top + 104), color)
    _text(ax, w / 2, top + (287 if mobile else 194), '按同一学生配对，检查时间稳定性',
          size=13, ha='center')
    _label(ax, 20, h - 46, '两种资料回答不同的一致性问题。', mobile=mobile, size=14)
    _label(ax, 20, h - 20, '未给分数或信度；稳定不等于用途合适。',
           mobile=mobile, size=12, gid='reliability-note')
    return fig


def _validity(entry, color, mobile):
    fig, ax, w, h = _canvas('validity', mobile)
    _text(ax, 20, 28, '题目内容，要接得上解释用途', color=color, size=16, weight='bold')
    _surface(ax, 16, 67, w - 32, 258 if mobile else 187, color)
    _paper(ax, 35, 107, 110, 90, color, gid='reading-passage', ruled=False)
    _text(ax, 51, 125, '短文', size=14, color=color)
    ax.plot([51, 128], [148, 148], color=color, alpha=.30, linewidth=1)
    _text(ax, 51, 174, '理解题', size=14, color=color)
    _text(ax, 167 if mobile else 190, 119, '阅读任务', color=color, weight='bold', gid='task-content')
    _text(ax, 167 if mobile else 190, 153, '读文字', size=14)
    _text(ax, 167 if mobile else 190, 185, '回答含义', size=14)
    if mobile:
        _arrow(ax, (180, 221), (180, 250), color)
        _paper(ax, 155, 253, 50, 40, color, gid='response-record')
        _text(ax, 180, 311, '得到作答与评分记录', color=color, ha='center', size=13)
    else:
        _arrow(ax, (345, 159), (425, 159), color)
        _paper(ax, 449, 107, 75, 90, color)
        _text(ax, 550, 145, '作答与评分记录', color=color, size=14)
        _text(ax, 190, 224, '即使重复表现接近，也还要问：这个分数能解释什么？', size=13)
    start, rowh = (356, 184) if mobile else (292, 132)
    for index, key in enumerate(('reading', 'anxiety')):
        y = start + index * rowh
        _surface(ax, 16, y, w - 32, rowh - 18, color)
        _text(ax, 30, y + 25, '阅读理解用途' if index == 0 else '焦虑程度用途',
              weight='bold', color=color, gid=f'purpose-{key}')
        evidence = '内容与阅读理解相符：一条线索' if index == 0 else '阅读成绩与焦虑解释之间：仍缺证据'
        _label(ax, 30, y + 65, evidence, mobile=mobile, size=12, gid=f'evidence-{key}')
        _paper(ax,30,y+86,100,34,color,ruled=False)
        _text(ax,80,y+103,'阅读得分',size=13,ha='center',gid=f'score-{key}')
        target='阅读理解？' if index==0 else '焦虑程度？'
        shade=color if index==0 else '#167d87'
        _paper(ax,w-150,y+86,120,34,shade,ruled=False)
        _text(ax,w-90,y+103,target,color=shade,size=13,ha='center',gid=f'interpretation-{key}')
        ax.add_patch(FancyArrowPatch((138,y+103),(w-158,y+103),arrowstyle='-|>',
                                    color=shade,linewidth=1.2,alpha=.6,
                                    linestyle='solid' if index==0 else (0,(4,4))))
        if mobile:
            _text(ax, 30, y + 144, '还需用途对应的研究证据', size=13)
    _label(ax, 20, h - 48, '内容匹配是线索，不是效度已经成立。', mobile=mobile, size=14)
    _label(ax, 20, h - 20, '阅读理解用途也须验证；图中未估计效度。',
           mobile=mobile, size=12, gid='validity-note')
    return fig


def make_story(slug, entry, color, mobile=False):
    """Return an editable conceptual Figure; leave all source data untouched."""
    functions = {'measurement-error': _measurement, 'model-identification': _identification,
                 'reliability': _reliability, 'validity': _validity}
    if slug not in SUPPORTED:
        raise ValueError(f'Unsupported model story: {slug}')
    return functions[slug](entry, color, mobile)
