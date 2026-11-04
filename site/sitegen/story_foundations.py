"""Concrete, editable Matplotlib stories for foundational statistical ideas.

Marks depict records, provenance and logical comparisons. They never stand in
for measured probabilities, effect estimates or a calculated recruitment plan.
The caller owns export and rendered geometry audits.
"""
from __future__ import annotations

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, FancyBboxPatch

from . import illustrated_examples as samples

SUPPORTED = {
    'continuous-variable', 'extreme-value', 'independence', 'missing-data-mechanism',
    'missing-data', 'null-hypothesis', 'outlier', 'p-value', 'parameter-and-statistic',
    'partial-correlation', 'sample-size-planning', 'sesoi', 'significance-level',
    'statistical-assumptions', 'statistical-power',
}


def _wrap(value, count):
    """Wrap CJK annotations without shrinking their type."""
    return '\n'.join(value[i:i+count] for i in range(0, len(value), count))


class Story:
    def __init__(self, entry, color, mobile):
        self.w = 360 if mobile else 760
        self.h = 760 if mobile else 650
        self.mobile, self.color = mobile, color
        self.accent = '#167d87' if color not in ('#006d70', '#17643b') else '#6657bd'
        self.fig = plt.figure(figsize=(self.w/72, self.h/72), dpi=300)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set(xlim=(0, self.w), ylim=(self.h, 0))
        self.ax.axis('off')
        self.text(20, 29, entry['title'], size=16, bold=True)
        self.text(20, 58, '概念示意 · 图形不对应实际人数或结果', size=12, muted=True)
        self.y = (88, 388 if mobile else 350)
        self.bh = 246 if mobile else 222

    def text(self, x, y, value, size=14, bold=False, muted=False, gid=None, center=False, color=None):
        return samples._text(self.ax, x, y, value,
                             color or ('#465366' if muted else (self.color if bold else '#202a38')),
                             size=size, weight='bold' if bold else 'normal',
                             gid=gid, ha='center' if center else 'left')

    def stage(self, index, title):
        y = self.y[index]
        samples._surface(self.ax, 16, y, self.w-32, self.bh, self.color)
        self.text(30, y+25, title, bold=True)
        return y

    def arrow(self, a, b):
        return samples._arrow(self.ax, a, b, self.color)

    def person(self, x, y, label, selected=True):
        samples._person(self.ax, x, y, self.color, selected)
        self.text(x, y+44, label, size=13, center=True)

    def card(self, x, y, width, height, value='', gid=None, missing=False, color=None):
        shade = color or self.color
        patch = FancyBboxPatch((x, y), width, height,
            boxstyle='round,pad=0,rounding_size=8', facecolor=shade,
            edgecolor=shade, linewidth=1, alpha=0.05 if missing else 0.10,
            linestyle='--' if missing else '-', gid=gid)
        self.ax.add_patch(patch)
        if value:
            self.text(x+width/2, y+height/2, value, size=13, center=True, color=shade)
        return patch

    def note(self, value):
        self.text(20, self.h-65, _wrap(value, 22 if self.mobile else 48), size=13)

    def transition(self, label):
        middle = (self.y[0]+self.bh+self.y[1])/2
        self.arrow((self.w/2, middle-12), (self.w/2, middle+12))
        self.text(self.w/2+20, middle, label, size=12)


def _continuous(s):
    s.ax.texts[1].set_text('生活例子 · 非真实调查记录')
    y = s.stage(0, '时长：同一段时间可以细分')
    left, right = 54, s.w-54
    s.ax.plot([left, right], [y+86]*2, color=s.color, linewidth=1.5)
    for minute in range(16):
        x = left+(right-left)*minute/15
        major = minute % 5 == 0
        s.ax.plot([x, x], [y+(77 if major else 82), y+(97 if major else 91)],
                  color=s.color, alpha=1 if major else .4, linewidth=1)
        if major:
            label = '7小时' if minute == 0 else f'7小时{minute}分钟'
            s.text(x, y+122, label, size=12, center=True)
    s.text(30, y+169, '7小时15分钟 = 7.25小时', size=14)
    s.text(30, y+204, '每小格1分钟，还能按秒继续细分', size=13)
    y = s.stage(1, '人数：同一家庭，按完整的人计数')
    centers = (s.w*.23, s.w*.76)
    spacing = 30 if s.mobile else 42
    groups = []
    for group, count, center in zip(('before', 'after'), (2, 3), centers):
        positions = [center+(i-(count-1)/2)*spacing for i in range(count)]
        groups.append(positions)
        for i, x in enumerate(positions):
            start = len(s.ax.patches)
            added = group=='after' and i==2
            samples._person(s.ax, x, y+100, '#187b55' if added else s.color, False)
            s.ax.patches[start].set_gid(f'count-{group}-{i}')
            s.ax.patches[start].set_alpha(.75)
            s.ax.patches[start+1].set_alpha(.5)
        s.text(center, y+156, f'{count}个孩子', bold=True, center=True)
        s.ax.plot([center+43,center+48,center+57],[y+157,y+162,y+150],
                  color='#187b55',linewidth=1.7)
    s.arrow((groups[0][-1]+20, y+96), (groups[1][0]-20, y+96))
    label=s.text(s.w*.49, y+65, '增加1个', size=13, center=True)
    label.set_color('#187b55')
    s.text(30, y+202, '增加的是完整的人，不是切出一小段', size=13)
    s.note('时长可继续分割；人数按个计数。记录精度仍受测量工具限制。')


def _extreme(s, outlier=False):
    y = s.stage(0, '把待核查记录放回常见范围')
    left, right = 54, s.w-54
    s.ax.plot([left, right], [y+103]*2, color=s.color, linewidth=1)
    if outlier:
        bandleft, bandright, dot = left, left+(right-left)/10, right
        common, unusual = '多数不到1秒', '10秒'
    else:
        bandleft, bandright, dot = left+(right-left)*.60, right, left
        common, unusual = '常见6—8小时', '甲：3小时'
    s.ax.add_patch(Rectangle((bandleft, y+86), bandright-bandleft, 34,
                            facecolor=s.color, alpha=.22))
    s.ax.add_patch(Circle((dot, y+103), 6, facecolor='#966111', gid='unusual-record'))
    s.text(dot, y+142, unusual, size=13, center=True)
    s.text(30, y+183, '浅色带：'+common, size=13)
    s.text(30, y+209, '标出的点需核查，不能直接删除', size=13)
    y = s.stage(1, '同一条记录，回查不同来源')
    s.card(s.w/2-57, y+50, 114, 40, '原始记录')
    labels = ['真实长停顿', '设备中断', '填写单位'] if outlier else ['真实熬夜', '填写单位']
    n = len(labels)
    gap = 12
    cw = (s.w-60-gap*(n-1))/n
    for i, label in enumerate(labels):
        x = 30+i*(cw+gap)
        s.arrow((s.w/2, y+96), (x+cw/2, y+132))
        s.card(x, y+137, cw, 49, label)
    s.note('远离常见范围提示回查。核对来源与预先规则之后，再决定如何处理。')


def _identity(s, assumptions=False):
    y = s.stage(0, '不同记录，共享同一个人')
    if assumptions:
        s.text(s.w/2, y+79, '甲 → 甲 → 甲', bold=True, center=True,
               gid='repeated-identities')
        labels = ['前测', '中测', '后测']
        cw = (s.w-84)/3
        for i, value in enumerate(labels):
            s.card(30+i*(cw+12), y+110, cw, 54, value)
        s.text(30, y+195, '身份不变，测量时间变化', size=14)
    else:
        s.person(65, y+97, '学生甲')
        x = 120 if s.mobile else 250
        s.arrow((98, y+106), (x-8, y+85)).set_gid('person-to-today')
        s.arrow((98, y+106), (x-8, y+146)).set_gid('person-to-tomorrow')
        s.card(x, y+63, s.w-x-30, 45)
        s.card(x, y+124, s.w-x-30, 45, color=s.accent)
        s.text(x+12, y+85, '甲 · 今天 · 压力6分', size=12, gid='record-today')
        s.text(x+12, y+146, '甲 · 明天 · 压力7分', size=12, gid='record-tomorrow', color=s.accent)
        s.text(30, y+205, '两行记录需要保留同一身份关系', size=13)
    y = s.stage(1, '不同的人，也要考虑设计与环境')
    if assumptions:
        s.text(s.w/2, y+61, '甲     乙     丙', bold=True, center=True,
               gid='different-identities')
        for x, label in zip((s.w*.25, s.w*.5, s.w*.75), ('甲', '乙', '丙')):
            s.person(x, y+116, label)
        s.text(30, y+203, '三名观测对象，不是三次测量', size=13)
    else:
        s.text(s.w/2, y+68, '共同期末考试', bold=True, center=True, gid='shared-exam')
        for x, label in ((s.w*.30, '甲'), (s.w*.70, '乙')):
            s.arrow((s.w/2, y+87), (x, y+119))
            s.person(x, y+140, label)
    s.note('记录是否独立需要结合身份、抽样与共同环境判断；图没有估计依赖程度。')


def _missing(s, mechanism=False):
    if not mechanism:
        for i, (person, raw, stored) in enumerate((('甲', '', '缺失'), ('乙', '0', '0 小时'))):
            y = s.stage(i, '空白：未获得记录' if i == 0 else '明确填写：获得数值回答')
            s.text(30, y+67, f'{person}的睡眠问卷', size=14)
            x = 45
            shade = '#966111' if i == 0 else s.accent
            s.card(x, y+93, 95, 57, raw, gid='missing-cell' if i == 0 else 'zero-cell',
                   missing=i == 0, color=shade)
            s.arrow((150, y+122), (s.w-137, y+122))
            s.text(s.w-127, y+122, stored, bold=True,
                   gid='missing-value' if i == 0 else 'observed-zero', color=shade)
            s.text(30, y+190, '保存缺失标记' if i == 0 else '保存数值，仍要核实真实性', size=13)
        s.note('空白不能自动填成零。缺失原因与分析方案决定下一步处理。')
        return
    for i in range(2):
        y = s.stage(i, '随机漏发：与压力高低无关' if i == 0 else '拒答可能与未观测压力有关')
        labels = ('压力较低', '压力较高', '压力较低')
        gap, cw = 12, (s.w-84)/3
        for j, label in enumerate(labels):
            x = 30+j*(cw+gap)
            s.text(x+cw/2, y+70, label, size=12, center=True)
            missing = (j == 0) if i == 0 else (j == 1)
            cell = s.card(x, y+103, cw, 55, '未收到' if i == 0 and missing else
                          ('未填答' if missing else '有回答'), missing=missing)
            if missing:
                cell.set_alpha(None)
                cell.set_facecolor((*plt.matplotlib.colors.to_rgb(s.color), .045))
                cell.set_edgecolor((*plt.matplotlib.colors.to_rgb('#966111'), .65))
                cell.set_linewidth(1.2)
                cell.set_gid(f'missing-cell-{i}-{j}')
        s.text(30, y+205, '漏发位置不按压力挑选' if i == 0 else '留下的回答可能更偏向轻松者', size=13)
    s.note('虚线框表示未取得回答。压力是情境设定，真实缺失者的压力可能未知；不能据图确认机制。')


def _null(s):
    y = s.stage(0, '先规定要评估的基准')
    for i, label in enumerate(('训练组总体', '等待组总体')):
        x = 35+i*(s.w-70)/2
        bw = (s.w-90)/2
        shade = s.color if i == 0 else s.accent
        s.card(x, y+66, bw, 84, label, color=shade)
        s.ax.plot([x+20, x+bw-20], [y+128]*2, color=shade)
    s.text(s.w/2, y+185, '基准：总体平均进步相同', bold=True,
           center=True, gid='null-reference')
    y = s.stage(1, '两组样本记录汇入同一基准比较')
    for cx, group, label, endpoint in (
        (s.w*.29, 'training', '训练组样本', s.w/2-42),
        (s.w*.71, 'waiting', '等待组样本', s.w/2+42),
    ):
        s.text(cx, y+60, label, size=13, center=True)
        start = len(s.ax.patches)
        shade = s.color if group == 'training' else s.accent
        samples._person(s.ax, cx-40, y+101, shade, True)
        s.ax.patches[start].set_gid(f'null-{group}-person')
        s.card(cx-6, y+78, 65, 55, '进步\n记录', gid=f'null-{group}-records', color=shade)
        s.arrow((cx+26, y+140), (endpoint, y+176))
        s.ax.patches[-1].set_gid(f'null-{group}-to-comparison')
    s.card(30, y+180, s.w-60, 34)
    s.text(s.w/2, y+197, '按总体平均进步相同的基准比较',
           size=13, center=True, gid='comparison-under-null')
    s.note('若反对基准的证据不足，仍保留不确定性；未拒绝不等于证明相同或等效。')


def _pvalue(s):
    y = s.stage(0, '观察：两种训练的样本进步')
    cw = (s.w-90)/2
    s.card(30, y+67, cw, 63, '训练甲样本\n平均进步8分')
    s.card(s.w-30-cw, y+67, cw, 63, '训练乙样本\n平均进步3分', color=s.accent)
    s.text(s.w/2, y+145, '8 − 3 = 5分（教学设定）', size=13, center=True)
    s.text(s.w/2, y+176, '样本相差5分', bold=True, center=True, gid='observed-difference')
    y = s.stage(1, '在规定零假设和设计下比较')
    s.text(30, y+62, '基准：两组总体平均进步相同', size=13, gid='null-reference')
    left, right, split = 35, s.w-35, s.w*.57
    s.ax.plot([left, right], [y+119]*2, color=s.color, linewidth=1.2)
    s.ax.add_patch(Rectangle((split, y+104), right-split, 30,
                            facecolor=s.color, alpha=.20, gid='same-or-more-extreme'))
    s.ax.plot([split, split], [y+94, y+144], color=s.color, linewidth=1.5)
    s.text(split, y+164, '观察结果', size=12, center=True)
    s.text(30, y+203, '向右：同样或更极端（按检验定义）', size=13)
    s.note('着色是待计算概率的结果集合，长度不代表p值；仍需样本量、变异和检验设计。')


def _parameter(s):
    y = s.stage(0, '全校：想回答的范围')
    for i in range(9):
        samples._person(s.ax, 50+i*(s.w-100)/8, y+89, s.color, i in (1, 4, 6))
    s.text(30, y+171, '全校真实平均 = ?', bold=True, gid='population-parameter')
    s.transition('抽样')
    y = s.stage(1, '120名学生：实际获得的记录')
    s.card(30, y+62, s.w-60, 60, '睡眠记录 → 求样本平均', color=s.accent)
    s.arrow((s.w/2, y+134), (s.w/2, y+169)).set_gid('computation-to-statistic')
    s.text(s.w/2, y+185, '样本平均 = 7小时', bold=True, center=True, gid='sample-statistic', color=s.accent)
    s.note('可计算的样本统计量用来估计未知总体参数；抽样代表性决定推广的依据。')


def _partial(s):
    y = s.stage(0, '年龄可能夹在两个变量的联系中')
    s.text(s.w/2, y+70, '年龄', bold=True, center=True)
    for x, label in ((s.w*.25, '睡眠'), (s.w*.75, '压力')):
        s.ax.plot([s.w/2, x], [y+88, y+135], color=s.color, alpha=.6)
        s.text(x, y+154, label, bold=True, center=True)
    s.ax.plot([s.w*.32, s.w*.68], [y+153]*2, color=s.color, linestyle='--')
    s.text(30, y+204, '线表示统计联系，不是因果箭头', size=13)
    y = s.stage(1, '分别考虑年龄，再比较剩余部分')
    for i, variable in enumerate(('睡眠', '压力')):
        yy = y+62+i*76
        s.text(30, yy+17, variable, size=14)
        s.arrow((82, yy+17), (107, yy+17))
        s.card(111, yy, s.w-141, 43, '去除所设年龄项后的剩余')
    s.text(30, y+207, '比较两个剩余部分的统计联系', size=13, gid='residual-association')
    s.note('偏相关依赖所设控制方法。控制年龄后仍可能有其他共同原因。')


def _sesoi(s):
    y = s.stage(0, '学校先衡量投入与收益')
    for i in range(4):
        s.card(30+i*(s.w-60)/4, y+72, (s.w-76)/4, 57, '课时')
    s.text(30, y+179, '占用课时 → 需要有意义的成绩改善', size=13)
    s.transition('事先约定')
    y = s.stage(1, '在研究前设定最小重要效应')
    left, right, split = 40, s.w-40, s.w*.57
    s.ax.plot([left, right], [y+101]*2, color=s.color)
    s.ax.add_patch(Rectangle((split, y+83), right-split, 36,
                            facecolor=s.color, alpha=.18))
    s.ax.plot([split, split], [y+74, y+129], color=s.color)
    s.text(split, y+151, '平均提高3分', bold=True, center=True, gid='target-effect')
    s.text(30, y+201, '把教育意义用于规划与解释', size=13)
    s.note('3分是此情境事先约定的界限；着色没有显示本次研究的真实效果。')


def _planning(s):
    y = s.stage(0, '保持同一个关心的改善目标')
    s.text(30, y+65, '关心平均提高3分',
           bold=True, gid='target-effect')
    s.text(30, y+102, '从既有资料估计个体差异', size=13)
    # A symbolic spread of record cards; no numeric sample or variance is encoded.
    for i, offset in enumerate((0, 19, -13, 28, -5)):
        x = 38+i*(s.w-98)/5
        s.card(x, y+143+offset, (s.w-118)/5, 30, '记录')
    y = s.stage(1, '把研究设计和不确定性带入规划')
    labels = ('效应目标', '变异与设计', '目标功效')
    cw, gap = (s.w-84)/3, 12
    for i, label in enumerate(labels):
        x = 30+i*(cw+gap)
        s.card(x, y+62, cw, 47, label)
        s.arrow((x+cw/2, y+120), (s.w/2, y+150))
    s.text(s.w/2, y+172, '规划人数与退出缺失', bold=True, center=True)
    s.text(30, y+211, '更大波动、退出或缺失会改变人数需求', size=12)
    s.note('箭头连接规划所需信息，图没有给出正式人数计算或招募保证。')


def _power(s):
    y = s.stage(0, '真实改善存在，样本记录仍有波动')
    s.text(30, y+66, '设真实平均提高3分', bold=True, gid='target-effect')
    # Spread record cards in space, without inventing individual score values.
    for i, offset in enumerate((0, 27, -7, 15)):
        x = 35+i*(s.w-76)/4
        s.card(x, y+109+offset, (s.w-106)/4, 36, '记录')
    s.text(30, y+203, '人数少、差异大，证据可能不稳定', size=13)
    y = s.stage(1, '保持真实改善，重复研究可能分流')
    s.card(s.w/2-70, y+59, 140, 42, '反复收集样本')
    cw = (s.w-90)/2
    for x, label, gid in ((30, '足以拒绝基准', 'detect-effect'),
                          (s.w-30-cw, '证据不足', 'miss-effect')):
        s.arrow((s.w/2, y+112), (x+cw/2, y+140))
        s.card(x, y+149, cw, 48, gid=gid)
        s.text(x+cw/2, y+173, label, size=13, center=True)
    s.note('功效是规定效应和设计下长期发现的概率；更充分的规划可能提高机会，仍非保证。')


def _alpha(s):
    y = s.stage(0, '研究前：把判断规则写入方案')
    s.card(30, y+61, s.w-60, 118)
    s.text(48, y+89, '检验问题与方法', size=14)
    s.text(48, y+135, '显著性水平 α = 0.05', bold=True, gid='alpha-rule')
    s.transition('固定规则')
    y = s.stage(1, '同一预设规则作用于每一次研究')
    s.text(s.w/2, y+59, '条件：零假设成立', size=13, center=True, gid='null-is-true')
    s.arrow((s.w/2, y+74), (s.w/2, y+91))
    s.ax.patches[-1].set_gid('truth-to-rule')
    s.card(s.w/2-95, y+96, 190, 38)
    s.text(s.w/2, y+115, '同一规则：α = 0.05', size=13, center=True, gid='fixed-alpha-rule')
    for cx, label, gid, annotation in (
        (s.w*.28, '拒绝', 'reject', '第一类错误'),
        (s.w*.72, '不拒绝', 'retain', '正确不拒绝'),
    ):
        s.arrow((s.w/2, y+141), (cx, y+156))
        s.ax.patches[-1].set_gid(f'rule-to-{gid}')
        s.card(cx-48, y+160, 96, 34)
        s.text(cx, y+177, label, size=13, center=True, gid=f'alpha-{gid}')
        s.text(cx, y+211, annotation, size=12, bold=gid == 'reject', center=True,
               color='#ae3f53' if gid == 'reject' else '#187b55',
               gid='alpha-false-rejection' if gid == 'reject' else 'alpha-correct-retention')
    s.note('显著性水平控制条件满足时长期错误拒绝的比率；分支不表示实际频率比例。')


def make_story(slug, entry, color, mobile=False):
    """Return an unsaved Matplotlib Figure for a supported concrete story."""
    if slug not in SUPPORTED:
        raise ValueError(f'Unsupported foundation story: {slug}')
    s = Story(entry, color, mobile)
    functions = {
        'continuous-variable': lambda: _continuous(s),
        'extreme-value': lambda: _extreme(s),
        'outlier': lambda: _extreme(s, True),
        'independence': lambda: _identity(s),
        'statistical-assumptions': lambda: _identity(s, True),
        'missing-data': lambda: _missing(s),
        'missing-data-mechanism': lambda: _missing(s, True),
        'null-hypothesis': lambda: _null(s),
        'p-value': lambda: _pvalue(s),
        'parameter-and-statistic': lambda: _parameter(s),
        'partial-correlation': lambda: _partial(s),
        'sesoi': lambda: _sesoi(s),
        'sample-size-planning': lambda: _planning(s),
        'statistical-power': lambda: _power(s),
        'significance-level': lambda: _alpha(s),
    }
    try:
        functions[slug]()
    except Exception:
        plt.close(s.fig)
        raise
    return s.fig
