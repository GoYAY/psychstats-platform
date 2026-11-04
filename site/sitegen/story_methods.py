"""Concrete, editable method stories using the approved Matplotlib style.

All positions in these stories are schematic composition coordinates, never
measured observations or results from a fitted model. Original teaching
parameters (three centers, six/eight hours, twenty candidate variables) are
retained. This module returns figures only; the common exporter owns QA.
"""
from __future__ import annotations

import math
import unicodedata

from matplotlib import pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, FancyBboxPatch, Rectangle

from .illustrated_examples import _surface, _text, _person


SUPPORTED = {
    'causal-relationship', 'cluster-analysis', 'confounding', 'convergence',
    'k-means-clustering', 'likelihood', 'maximum-likelihood', 'model-fit',
    'overfitting', 'product-indicator', 'stepwise-regression',
}
INK, MUTED, PURPLE, TEAL, ROSE = '#202a38', '#465366', '#6657bd', '#006d70', '#a33052'


def _wrap(value, width, size=14):
    """Wrap Chinese and Latin labels by their approximate glyph advance."""
    limit = max(5, (width - 8) / size)
    lines = []
    for source in value.split('\n'):
        line, advance = '', 0
        for char in source:
            step = 1 if unicodedata.east_asian_width(char) in ('W', 'F') else 0.56
            if line and advance + step > limit:
                lines.append(line)
                line, advance = '', 0
            line += char
            advance += step
        lines.append(line)
    return '\n'.join(lines)


def _label(ax, x, y, value, width, size=14, color=INK, weight='normal', gid=None, ha='left'):
    return _text(ax, x, y, _wrap(value, width, size), color=color,
                 size=size, weight=weight, gid=gid, ha=ha)


def _link(ax, a, b, color, gid=None, dashed=False):
    patch = FancyArrowPatch(a, b, arrowstyle='-|>', mutation_scale=14,
                           linewidth=1.3, color=color, alpha=0.75,
                           linestyle=(0, (4, 4)) if dashed else '-')
    patch.set_gid(gid)
    ax.add_patch(patch)
    return patch


def _node(ax, x, y, width, height, label, color, gid=None, size=14):
    patch = FancyBboxPatch((x, y), width, height,
                          boxstyle='round,pad=0,rounding_size=8',
                          facecolor=color, alpha=0.11, edgecolor=color,
                          linewidth=0.8)
    patch.set_gid(gid)
    ax.add_patch(patch)
    _label(ax, x + width/2, y + height/2, label, width-12, size,
           color, ha='center')
    return patch


def _dot(ax, x, y, color, radius=5, gid=None, hollow=False):
    patch = Circle((x, y), radius, facecolor='white' if hollow else color,
                   alpha=0.8, edgecolor=color, linewidth=1.1)
    patch.set_gid(gid)
    ax.add_patch(patch)


def _cross(ax, x, y, color, gid=None, faded=False):
    line, = ax.plot([x-7, x+7], [y-7, y+7], color=color,
                    lw=2, alpha=0.3 if faded else 1, gid=gid)
    ax.plot([x-7, x+7], [y+7, y-7], color=color, lw=2,
            alpha=0.3 if faded else 1)
    return line


def _layout(entry, color, mobile, titles, stage_height=330, disclaimer=None):
    n = len(titles)
    width = 360 if mobile else 760
    gap = 38 if mobile else (32 if n == 3 else 44)
    top = 88 if mobile else 76
    panel_width = width-32 if mobile else (width-32-(n-1)*gap)/n
    height = top+n*stage_height+(n-1)*gap+64 if mobile else top+stage_height+64
    fig = plt.figure(figsize=(width/72, height/72), dpi=300)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, width), ylim=(height, 0))
    ax.axis('off')
    _label(ax, 20, 30 if not mobile else 35, entry['title'], width-40,
           16, color, 'bold')
    _text(ax, 20, 59 if not mobile else 70, '概念故事 · 操作与关系示意', size=12, color=MUTED)
    stages = []
    for i, title in enumerate(titles):
        x = 16 if mobile else 16+i*(panel_width+gap)
        y = top+i*(stage_height+gap) if mobile else top
        _surface(ax, x, y, panel_width, stage_height, color)
        _label(ax, x+16, y+28, title, panel_width-32, 14, color, 'bold', f'stage-{i}')
        stages.append((x, y, panel_width, stage_height))
        if i:
            px, py, pw, ph = stages[i-1]
            if mobile:
                _link(ax, (width/2, py+ph+6), (width/2, y-7), color)
            else:
                _link(ax, (px+pw+6, py+ph/2), (x-7, y+stage_height/2), color)
    disclaimer = disclaimer or '位置与连线为概念示意，不代表实际测量或分析结果。'
    _label(ax, 20, height-30, disclaimer, width-40, 12, MUTED, gid='conceptual-only')
    return fig, ax, stages


def _footer(ax, stage, first, second=None, color=MUTED):
    x, y, w, h = stage
    _label(ax, x+16, y+h-62 if second else y+h-40, first, w-32, 12, color)
    if second:
        _label(ax, x+16, y+h-32, second, w-32, 12, color)


def _records(ax, stage, color, title='同一批睡眠记录', notes=None):
    x, y, w, h = stage
    _label(ax, x+16, y+66, title, w-32, 14, color, 'bold', 'fixed-records')
    for i, (student, hours) in enumerate(zip(('甲', '乙', '丙'), (6, 6.5, 7))):
        _node(ax, x+20, y+93+i*45, w-40, 34, f'学生{student} · {hours}小时', color,
              gid=f'fixed-record-{i}')
    _footer(ax, stage, *(notes or ('数字是教学设定', '不随候选参数更换资料')))


def _causal(entry, color, mobile):
    fig, ax, stages = _layout(entry, color, mobile, ['观察一起变化', '安排可比较的条件'], 350)
    x, y, w, _ = stages[0]
    _node(ax, x+w/2-58, y+64, 116, 40, '原有健康状况', TEAL)
    _link(ax, (x+w/2-33, y+111), (x+w*.24, y+150), TEAL)
    _link(ax, (x+w/2+33, y+111), (x+w*.76, y+150), TEAL)
    _node(ax, x+16, y+154, w*.40, 48, '运动习惯', color)
    _node(ax, x+w*.60-16, y+154, w*.40, 48, '开心程度', PURPLE)
    _link(ax, (x+w*.43, y+177), (x+w*.57, y+177), color, dashed=True)
    _text(ax, x+w/2, y+222, '观察到关联 ≠ 已知因果', size=12, ha='center')
    _footer(ax, stages[0], '原来更健康，也可能更常运动', '情绪差异仍有其他解释')
    x, y, w, _ = stages[1]
    _node(ax, x+w/2-68, y+61, 136, 38, '条件相近的学生', color)
    _link(ax, (x+w/2-30, y+105), (x+w*.25, y+141), color)
    _link(ax, (x+w/2+30, y+105), (x+w*.75, y+141), color)
    for px, label, shade in [(x+w*.25, '安排运动', color), (x+w*.75, '安排不运动', PURPLE)]:
        _node(ax, px-57, y+145, 114, 38, label, shade)
        _link(ax, (px, y+190), (px, y+218), shade)
        _node(ax, px-49, y+224, 98, 40, '情绪待测 ?', shade)
    _footer(ax, stages[1], '依研究问题安排合理比较', '之后再收集结果，排查其他解释')
    return fig


def _confounding(entry, color, mobile):
    fig, ax, stages = _layout(entry, color, mobile, ['看到辅导与成绩相联', '加入可能的共同原因'], 350)
    x, y, w, _ = stages[0]
    _node(ax, x+25, y+85, w-50, 44, '参加辅导', color)
    _link(ax, (x+w/2, y+136), (x+w/2, y+183), color, dashed=True)
    _text(ax, x+w/2+18, y+160, '关联', size=12, color=color)
    _node(ax, x+25, y+191, w-50, 44, '观察到成绩较高', PURPLE)
    _footer(ax, stages[0], '两组的成绩差中', '可能还混入其他条件')
    x, y, w, _ = stages[1]
    _node(ax, x+w/2-58, y+70, 116, 40, '家庭资源', TEAL)
    _link(ax, (x+w/2-24, y+118), (x+w*.24, y+180), TEAL, 'resources-to-tutoring')
    _link(ax, (x+w/2+24, y+118), (x+w*.76, y+180), TEAL, 'resources-to-grades')
    _node(ax, x+12, y+187, w*.40, 48, '参加辅导', color)
    _node(ax, x+w*.60-12, y+187, w*.40, 48, '成绩', PURPLE)
    _link(ax, (x+w*.44, y+210), (x+w*.56, y+210), MUTED, dashed=True)
    _footer(ax, stages[1], '机会与成绩都可能受资源影响', '先核查这两条路径')
    return fig


def _cluster(entry, color, mobile):
    fig, ax, stages = _layout(entry, color, mobile, ['每人一组生活记录', '按相近的组合描述模式'], 360)
    x, y, w, _ = stages[0]
    _text(ax, x+18, y+66, '学生', size=12)
    colx = [x+w*.39, x+w*.63, x+w*.86]
    for cx, label in zip(colx, ('睡眠', '活动', '压力')):
        _text(ax, cx, y+66, label, size=12, ha='center')
    profiles = [('甲', '较足', '较多', '较低'), ('乙', '较足', '较多', '较低'),
                ('丙', '较短', '较少', '较高'), ('丁', '较短', '较少', '较高')]
    for i, row in enumerate(profiles):
        yy = y+107+i*43
        _text(ax, x+23, yy, row[0], size=14, gid=f'input-student-{row[0]}')
        for cx, value in zip(colx, row[1:]):
            _node(ax, cx-25, yy-14, 50, 28, value, color, size=12)
    _footer(ax, stages[0], '相近程度同时考虑多个记录', '单位和尺度需要先考虑')
    x, y, w, _ = stages[1]
    for j, (shade, label) in enumerate(((color, '睡眠较足 · 活动较多'), (PURPLE, '睡眠较短 · 压力较高'))):
        cy = y+119+j*105
        patch = Ellipse((x+w/2, cy), w-48, 78, facecolor=shade, alpha=.08,
                        edgecolor=shade, linestyle=(0, (4, 4)), linewidth=1)
        ax.add_patch(patch)
        for member_index, student in enumerate((('甲', '乙'), ('丙', '丁'))[j]):
            px = x+w/2+(-42 if member_index == 0 else 42)
            _dot(ax, px, cy-9, shade, 6, gid=f'cluster-member-{student}')
            _text(ax, px, cy+16, student, size=12, color=shade, ha='center',
                  gid=f'group-student-{student}')
        _label(ax, x+w/2, cy+49, label, w-40, 12, shade, ha='center')
    _footer(ax, stages[1], '分组边界可随方法与样本改变', '模式示意，不是诊断或测量坐标')
    return fig


_POINTS = [(0.22, .29, 0), (.30, .44, 0), (.39, .32, 0),
           (.68, .23, 1), (.79, .39, 1), (.69, .49, 1),
           (.37, .77, 2), (.48, .65, 2), (.57, .80, 2)]
_OLD_CENTERS = [(0.23, .48), (.84, .23), (.30, .69)]
_NEW_CENTERS = [(0.30, .35), (.72, .37), (.47, .74)]


def _kmeans(entry, color, mobile):
    fig, ax, stages = _layout(entry, color, mobile,
                              ['预设三个中心', '记录分配到较近中心', '按成员更新中心'], 350,
                              '三组是预设条件；示意未运行算法，位置不是测量值。')
    shades = [color, PURPLE, TEAL]
    for stage_index, stage in enumerate(stages):
        x, y, w, _ = stage
        left, top, pw, ph = x+18, y+64, w-36, 185
        for point_index, (rx, ry, group) in enumerate(_POINTS):
            px, py = left+rx*pw, top+ry*ph
            if stage_index == 1:
                cx, cy = _OLD_CENTERS[group]
                _link(ax, (px, py), (left+cx*pw, top+cy*ph), shades[group], f'assignment-{point_index}')
            _dot(ax, px, py, shades[group] if stage_index else MUTED, 5.5)
        for group, (cx, cy) in enumerate(_OLD_CENTERS):
            ox, oy = left+cx*pw, top+cy*ph
            _cross(ax, ox, oy, shades[group], f'old-center-{stage_index}-{group}', faded=stage_index == 2)
            if stage_index == 2:
                nx, ny = _NEW_CENTERS[group]
                nx, ny = left+nx*pw, top+ny*ph
                _link(ax, (ox, oy), (nx, ny), shades[group], f'center-update-{group}')
                _cross(ax, nx, ny, shades[group], f'updated-center-{group}')
        footers = [('圆点：生活记录', '叉号：候选中心'),
                   ('连线：此轮分配示意', '比较各记录到中心的距离'),
                   ('中心移向本组的代表位置', '再分配，直到满足停止条件')]
        _footer(ax, stage, *footers[stage_index])
    return fig


def _convergence(entry, color, mobile):
    fig, ax, stages = _layout(entry, color, mobile,
                              ['参数逐轮调整', '变化达到停止条件', '停止之后继续核查'], 340)
    for idx in (0, 1):
        x, y, w, _ = stages[idx]
        _text(ax, x+16, y+66, '同一问卷模型的参数', size=12)
        for row, label in enumerate(('较早', '下一轮', '再下一轮')):
            yy = y+104+row*51
            _text(ax, x+16, yy, label, size=12)
            left, right = x+76, x+w-24
            ax.plot([left, right], [yy, yy], color=color, alpha=.24, lw=3)
            position = ([.22, .68, .43] if idx == 0 else [.49, .505, .51])[row]
            _dot(ax, left+position*(right-left), yy, color, 8)
            if row:
                previous = ([.22, .68, .43] if idx == 0 else [.49, .505, .51])[row-1]
                _link(ax, (left+previous*(right-left), yy-39), (left+position*(right-left), yy-12), color)
        if idx == 0:
            _footer(ax, stages[idx], '滑块代表参数变化', '位置只是过程示意')
        else:
            _node(ax, x+16, y+247, w-32, 33, '停止条件达到', color, size=12)
            _footer(ax, stages[idx], '停止由程序规则决定')
    x, y, w, _ = stages[2]
    for i, label in enumerate(('程序警告 ?', '异常数值 ?', '模型设定 ?', '其他起点的解 ?')):
        yy = y+78+i*48
        ax.add_patch(Rectangle((x+19, yy-9), 17, 17, fill=False, edgecolor=TEAL, lw=1))
        _label(ax, x+48, yy, label, w-62, 14, TEAL)
    _footer(ax, stages[2], '勾选须依据实际诊断', '停止后仍可能存在问题')
    return fig


def _density_sketch(ax, x, baseline, width, color, mean, group):
    xs = [x+i*width/40 for i in range(41)]
    ys = [baseline-43*math.exp(-.5*(4+6*i/40-mean)**2) for i in range(41)]
    ax.plot(xs, ys, color=color, lw=1.8, gid=f'candidate-distribution-{group}')
    ax.plot([x, x+width], [baseline, baseline], color=MUTED, alpha=.28, lw=.8)
    for i,hours in enumerate((6,6.5,7)):
        px=x+(hours-4)/6*width
        _dot(ax,px,baseline,color,3.2,gid=f'candidate-observation-{group}-{i}')
    for hours in (4,6,8,10):
        _text(ax,x+(hours-4)/6*width,baseline+16,str(hours),size=12,ha='center')


def _likelihood(entry, color, mobile):
    fig, ax, stages = _layout(entry, color, mobile, ['固定资料不变', '只改变候选参数'], 360,
                              '曲线仅示意候选模型；无似然值，也无参数为真的概率。')
    _records(ax, stages[0], color)
    x, y, w, _ = stages[1]
    for i, (label, shade, mean) in enumerate([('平均6小时', color, 6), ('平均8小时', PURPLE, 8)]):
        yy = y+58+i*114
        _node(ax, x+20, yy, w-40, 108, '', shade)
        _text(ax, x+34, yy+22, label, color=shade, size=14, weight='bold')
        _density_sketch(ax, x+37, yy+84, w-74, shade, mean, i)
    _footer(ax, stages[1], '横轴：小时；圆点：同一批记录', '正态候选，标准差均设为1小时')
    return fig


def _maximum_likelihood(entry, color, mobile):
    fig, ax, stages = _layout(entry, color, mobile,
                              ['固定记录与模型', '尝试参数组合', '寻找更相容的参数'], 350,
                              '搜索为概念示意；未拟合模型，也未确认全局最优值。')
    _records(ax, stages[0], color, notes=('先指定分布模型', '同一批记录参与全部比较'))
    x, y, w, _ = stages[1]
    for i, shade in enumerate((color, PURPLE)):
        yy = y+61+i*104
        _node(ax, x+17, yy, w-34, 86, '', shade)
        _text(ax, x+29, yy+20, '参数组合 '+('甲' if i == 0 else '乙'), size=14, color=shade)
        _text(ax, x+29, yy+48, '平均时长 · 分散程度', size=12)
        for j in range(3):
            _dot(ax, x+31+j*22, yy+69, shade, 3.5)
    _footer(ax, stages[1], '候选在同一模型内比较', '数值由实际估计决定')
    x, y, w, _ = stages[2]
    _label(ax, x+16, y+68, '按相容程度继续搜索', w-32, 14, color)
    coordinates = [(x+w*.22, y+190), (x+w*.49, y+153), (x+w*.75, y+111)]
    for i, point in enumerate(coordinates):
        _dot(ax, *point, color, 11, f'parameter-candidate-{i}', hollow=i<2)
        if i:
            _link(ax, (coordinates[i-1][0]+14, coordinates[i-1][1]-10),
                  (point[0]-14, point[1]+10), color)
    _node(ax, x+18, y+232, w-36, 40, '估计候选 → 再核查', color, size=12)
    _footer(ax, stages[2], '圆点：候选参数，不是学生', '实心点是待核查的估计')
    return fig


def _question_model(ax, stage, color, observed=False):
    x, y, w, _ = stage
    upper = [(x+w*.27, y+101), (x+w*.73, y+101)]
    lower = [(x+w*fraction, y+207) for fraction in (.15, .39, .61, .85)]
    for center, label, shade in zip(upper, ('担忧', '身体\n不适'), (color, PURPLE)):
        ax.add_patch(Ellipse(center, w*.32, 47, facecolor=shade, alpha=.11, edgecolor=shade))
        _text(ax, *center, label, size=14, ha='center', color=shade)
    for i, (px, py) in enumerate(lower):
        _node(ax, px-29, py-21, 58, 42,
              ('担忧\n题1', '担忧\n题2', '身体\n题1', '身体\n题2')[i],
              color if i<2 else PURPLE, size=12)
        _link(ax, (upper[i//2][0], upper[i//2][1]+30), (px, py-23), color if i<2 else PURPLE)
    if observed:
        a, b = lower[1], lower[2]
        edge = FancyArrowPatch((a[0], a[1]+23), (b[0], b[1]+23),
                               arrowstyle='<->', connectionstyle='arc3,rad=.5',
                               mutation_scale=12, color='#966111', linewidth=1.4,
                               linestyle=(0, (4, 4)))
        edge.set_gid('observed-extra-link')
        ax.add_patch(edge)
        _label(ax, x+w/2, y+266, '待检查的额外联系 ?', w-30, 12, '#966111', ha='center')


def _fit(entry, color, mobile):
    fig, ax, stages = _layout(entry, color, mobile,
                              ['模型规定题目联系', '对照实际关系与偏差'], 360)
    _question_model(ax, stages[0], color)
    _question_model(ax, stages[1], color, observed=True)
    _footer(ax, stages[0], '题目归于两个测量方面', '模型安排需要与资料对照')
    _footer(ax, stages[1], '虚线提示核查模型未描述的联系', '不是已发现的真实关系')
    return fig


_PREDICTION = [(.08, .76), (.22, .39), (.37, .61), (.51, .26), (.66, .43), (.81, .12), (.94, .34)]


def _prediction_panel(ax, stage, color, new=False):
    x, y, w, _ = stage
    left, top, pw, ph = x+26, y+85, w-52, 170
    ax.plot([left, left, left+pw], [top-5, top+ph, top+ph], color=MUTED, alpha=.4, lw=.8)
    xs = [left+rx*pw for rx, _ in _PREDICTION]
    ys = [top+ry*ph for _, ry in _PREDICTION]
    ax.plot(xs, ys, color=color, lw=2, gid='new-prediction' if new else 'training-prediction')
    offsets = [-.28, .23, -.27, .36, -.22, .38, -.17] if new else [.02, -.03, .04, -.02, .04, -.03, .02]
    for i, (px, py, offset) in enumerate(zip(xs, ys, offsets)):
        actual = py+offset*ph
        _dot(ax, px, actual, PURPLE if new else color, 6, f'{"new" if new else "original"}-record-{i}')
        if new:
            ax.plot([px, px], [py, actual], color=ROSE, lw=1, alpha=.75, linestyle=(0, (3, 3)))
    _text(ax, x+26, y+69, '成绩（概念位置）', size=12)
    _label(ax, x+w/2, y+278, '学生记录的预测条件（示意）', w-32, 12, ha='center')


def _overfitting(entry, color, mobile):
    fig, ax, stages = _layout(entry, color, mobile,
                              ['在本班挑选模型', '同一规则带到新班'], 380,
                              '原班与新班均为概念示意；点和预测线没有真实数值。')
    _prediction_panel(ax, stages[0], color)
    _prediction_panel(ax, stages[1], color, new=True)
    _footer(ax, stages[0], '尝试很多组合后贴近本班记录', '可能也学入偶然的特点')
    _footer(ax, stages[1], '紫点：新班记录；虚线：偏离', '还要检查新班分布是否变化')
    return fig


def _product(entry, color, mobile):
    fig, ax, stages = _layout(entry, color, mobile,
                              ['选定压力与支持题', '按方法处理后相乘', '与其他题对共同建模'], 350)
    x, y, w, _ = stages[0]
    _node(ax, x+18, y+63, w-36, 72, '压力题 p1\n经常担忧', color)
    _node(ax, x+18, y+162, w-36, 72, '支持题 s1\n困难时有人帮助', PURPLE)
    _footer(ax, stages[0], '每一道题提供一个指标', '同一学生保留题目配对')
    x, y, w, _ = stages[1]
    _node(ax, x+18, y+63, w-36, 40, '选定方法处理两题', TEAL, size=12)
    _link(ax, (x+w/2, y+111), (x+w/2, y+143), TEAL)
    _node(ax, x+18, y+151, w-36, 52, 'p1 × s1', color, gid='question-pair-product', size=18)
    _link(ax, (x+w/2, y+211), (x+w/2, y+235), color)
    _text(ax, x+w/2, y+257, '一个乘积指标', size=14, ha='center', color=color)
    _footer(ax, stages[1], '符号代表处理后的指标', '处理方式依具体模型决定')
    x, y, w, _ = stages[2]
    pair_width = (w-52)/2
    for i, label in enumerate(('p1 × s1', '其他题对')):
        _node(ax, x+18+i*(pair_width+16), y+96, pair_width, 46,
              label, color if i == 0 else PURPLE, size=12)
    _link(ax, (x+18+pair_width/2, y+150), (x+w*.35, y+204), color)
    _link(ax, (x+w-18-pair_width/2, y+150), (x+w*.67, y+204), PURPLE)
    _node(ax, x+18, y+212, w-36, 49, '交互模型', TEAL)
    _footer(ax, stages[2], '结合测量部分一起建模', '一个乘积不能替代完整测量')
    return fig


def _candidates(ax, stage, selected, color, batch):
    x, y, w, _ = stage
    _text(ax, x+16, y+65, f'{batch} · 二十项生活记录', size=12)
    # The grid encodes twenty candidate-variable slots, not measured values.
    cell_w = (w-40)/5
    for i in range(20):
        cx, cy = x+20+(i%5)*cell_w+cell_w/2, y+103+(i//5)*36
        patch = Rectangle((cx-cell_w*.38, cy-12), cell_w*.76, 25,
                          facecolor=color, alpha=.50 if i in selected else .06,
                          edgecolor=color, linewidth=.7)
        patch.set_gid(f'{batch}-candidate-{i}')
        ax.add_patch(patch)
    _text(ax, x+16, y+250, '深色格：概念入选位置', size=12, color=color)
    _footer(ax, stage, '相同规则，换一批学生', '入选组合可能改变')


def _stepwise(entry, color, mobile):
    fig, ax, stages = _layout(entry, color, mobile,
                              ['第一批学生', '另一批学生', '留出资料检查'], 350,
                              '二十项候选与筛选结果为概念场景；没有运行筛选算法。')
    _candidates(ax, stages[0], {1, 7, 11}, color, '甲批')
    _candidates(ax, stages[1], {1, 9, 16}, PURPLE, '乙批')
    x, y, w, _ = stages[2]
    _node(ax, x+18, y+64, w-36, 51, '未参与筛选的学生', TEAL, size=14)
    for i in range(3):
        _person(ax, x+w*.25+i*w*.25, y+151, TEAL, True)
    _link(ax, (x+w/2, y+185), (x+w/2, y+220), TEAL)
    _node(ax, x+18, y+229, w-36, 40, '预测表现待检查 ?', TEAL, size=12)
    _footer(ax, stages[2], '共同与不同入选项用于查稳定性', '入选不证明因果或理论重要性')
    return fig


_MAKERS = {
    'causal-relationship': _causal, 'cluster-analysis': _cluster,
    'confounding': _confounding, 'convergence': _convergence,
    'k-means-clustering': _kmeans, 'likelihood': _likelihood,
    'maximum-likelihood': _maximum_likelihood, 'model-fit': _fit,
    'overfitting': _overfitting, 'product-indicator': _product,
    'stepwise-regression': _stepwise,
}


def make_story(slug, entry, color, mobile=False):
    """Return an unsaved figure, with a 760/360-point responsive canvas."""
    if slug not in SUPPORTED:
        raise ValueError(f'Unsupported method story: {slug}')
    return _MAKERS[slug](entry, color, mobile)
