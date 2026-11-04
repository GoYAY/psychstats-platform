"""Validated, countable feedback traces; model output is data, never code."""
import copy
import re
import textwrap


def _object(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError('Feedback example fields are missing or unknown')


def _text(value, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('Feedback labels must be short, non-empty text')


def _names(rows, maximum):
    if not isinstance(rows, list) or not 1 <= len(rows) <= maximum:
        raise ValueError('Feedback objects are missing or exceed the readable limit')
    found = {}
    for row in rows:
        _object(row, ['id', 'label'])
        key = row['id']
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', key) or key in found:
            raise ValueError('Feedback identities must be short and distinct')
        _text(row['label'], 16); found[key] = row['label']
    return found


def _selection(value, known, *, empty=True):
    if not isinstance(value, list) or len(value) > len(known) or any(not isinstance(x, str) or x not in known for x in value):
        raise ValueError('Feedback selection contains an unknown object')
    if len(set(value)) != len(value) or not empty and not value:
        raise ValueError('Feedback selections must be distinct and observable')


def prepare_feedback(payload):
    _object(payload, ['layout', 'example_label', 'scope_note', 'choices', 'criteria', 'turns'])
    if payload['layout'] != 'feedback_trace': raise ValueError('Not a feedback trace')
    _text(payload['example_label'], 40); _text(payload['scope_note'], 160)
    choices = _names(payload['choices'], 4); criteria = _names(payload['criteria'], 4)
    turns = payload['turns']
    if not isinstance(turns, list) or not 2 <= len(turns) <= 4:
        raise ValueError('A feedback trace needs 2–4 complete rounds')
    seen = {}; transfers = []; preferences = []
    for turn in turns:
        _object(turn, ['id', 'userCompared', 'userPreferred', 'aiFocus', 'aiIntroduced', 'userAdopted'])
        key = turn['id']
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', key) or key in seen:
            raise ValueError('Feedback round identities must be distinct')
        _selection(turn['userCompared'], choices, empty=False)
        _selection(turn['aiFocus'], choices, empty=False)
        _selection(turn['aiIntroduced'], criteria)
        if turn['userPreferred'] not in turn['userCompared']:
            raise ValueError('Preference must belong to the actual compared choices')
        adopted = turn['userAdopted']
        if not isinstance(adopted, list) or len(adopted) > 4:
            raise ValueError('Too many adopted criteria')
        used = set()
        for item in adopted:
            _object(item, ['criterion', 'fromTurn'])
            criterion, previous = item['criterion'], item['fromTurn']
            if not isinstance(criterion, str) or criterion not in criteria or not isinstance(previous, str) or previous not in seen or criterion not in seen[previous]['aiIntroduced'] or criterion in used:
                raise ValueError('Adopted criteria must trace to a distinct, earlier AI introduction')
            used.add(criterion)
            transfers.append(dict(criterion=criterion, fromTurn=previous, toTurn=key))
        preferences.append(dict(turn=key, choice=turn['userPreferred']))
        seen[key] = turn
    if not transfers: raise ValueError('A feedback example must show a traceable return influence')
    return dict(compared_counts=[len(t['userCompared']) for t in turns],
                focus_counts=[len(t['aiFocus']) for t in turns], transfers=transfers,
                preferences=preferences, turns=copy.deepcopy(turns))


def render_feedback(payload, width, mobile, theme):
    """One continuous schematic: countable choices and traceable return influence."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch
    from matplotlib.path import Path
    derived = prepare_feedback(payload)
    turns = payload['turns']; choices = payload['choices']; criteria = {v['id']: v['label'] for v in payload['criteria']}
    columns = 1 if mobile or len(turns) > 3 else len(turns)
    gutter = 32; margin = 18; span = (width - 2 * margin - (columns - 1) * gutter) / columns
    lane_gap = 28 if columns > 1 else 50; lane_width = (span - lane_gap) / 2
    text_columns = max(3, int((lane_width - 25) / 12))
    card_height = max(28, 13 * max(len(textwrap.wrap(v['label'], text_columns)) for v in choices) + 8)
    adopt_rows = max(1, max(len(t['userAdopted']) for t in turns))
    intro_rows = max(1, max(len(t['aiIntroduced']) for t in turns))
    criterion_columns=max(3,int((lane_width-8)/12))
    chip_height=max(24,14*max(len(textwrap.wrap(v,criterion_columns)) for v in criteria.values())+10)
    chip_step=chip_height+6
    label_offset = 40 + adopt_rows * chip_step + 18
    card_offset = label_offset + 20
    count_offset = card_offset + len(choices) * (card_height + 8) + 10
    intro_offset = count_offset + 42
    section_height = intro_offset + intro_rows * chip_step + 20
    rows = 1 if columns > 1 else len(turns)
    bottom_lane = 58 if any(next(i for i,t in enumerate(turns) if t['id']==e['toTurn']) - next(i for i,t in enumerate(turns) if t['id']==e['fromTurn']) > 1 for e in derived['transfers']) else 14
    scope='\n'.join(textwrap.wrap(payload['scope_note'],max(12,int((width-2*margin)/12))))
    scope_height=14*len(scope.splitlines())+12
    height = 72 + rows * section_height + (rows - 1) * 35 + bottom_lane + 32 + scope_height
    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.set(xlim=(0, width), ylim=(height, 0)); ax.axis('off')
    ink = '#28334a'; muted = '#69758a'; warm = '#a66a35'
    def text(x, y, value, size=9, color=ink, **kwargs):
        kwargs.setdefault('va','center')
        return ax.text(x, y, value, fontsize=size, color=color, **kwargs)
    def chip(x, y, label, color, width_override=None):
        w = lane_width if width_override is None else width_override
        ax.add_patch(FancyBboxPatch((x, y), w, chip_height, boxstyle='round,pad=0,rounding_size=6', facecolor=color, alpha=.11, edgecolor='none'))
        text(x+w/2, y+chip_height/2, '\n'.join(textwrap.wrap(label, max(3,int((w-8)/12)))), size=8.5, color=color, ha='center')
        return (x, y, w, chip_height)
    text(margin, 20, payload['example_label'], size=10, color=theme, weight='bold')
    text(margin, 45, '实心：本轮纳入　空心：本轮未纳入', size=8.5, color=muted)
    introduced = {}; adopted = {}; stages = {}; positions = {}
    for index, turn in enumerate(turns):
        left = margin + (index if columns > 1 else 0) * (span + gutter)
        top = 72 + (index if columns == 1 else 0) * (section_height + 35)
        right = left + lane_width + lane_gap; stages[turn['id']] = (left, top, right)
        text(left, top, f'{index+1:02}', size=15, color=theme, weight='bold')
        text(left+32, top, '本轮互动', size=10, weight='bold')
        if turn['userAdopted']:
            for j, entry in enumerate(turn['userAdopted']):
                adopted[(turn['id'], entry['criterion'])] = chip(left, top+35+j*chip_step, criteria[entry['criterion']], warm)
        else: chip(left, top+35, '初始偏好', theme)
        text(left, top+label_offset, '人的比较', color=theme, weight='bold')
        text(right, top+label_offset, 'AI回应聚焦', color=theme, weight='bold')
        for side, x, selected in [('human', left, turn['userCompared']), ('ai', right, turn['aiFocus'])]:
            for j, item in enumerate(choices):
                y = top + card_offset + j * (card_height+8); active = item['id'] in selected
                preferred = side == 'human' and item['id'] == turn['userPreferred']
                box = FancyBboxPatch((x,y), lane_width, card_height, boxstyle='round,pad=0,rounding_size=6',
                                     facecolor=theme if active else '#d1d7e1', alpha=.15 if active else .08,
                                     edgecolor=theme if active else '#98a3b5', linewidth=1.2 if preferred else .6,
                                     linestyle='solid' if active else 'dashed')
                box.set_gid(f"choice-{turn['id']}-{side}-{item['id']}"); ax.add_patch(box)
                ax.add_patch(Circle((x+9,y+card_height/2), 2.5, facecolor=theme if active else 'white', edgecolor=theme if active else '#9ba6b7', linewidth=.7))
                text(x+18, y+card_height/2, '\n'.join(textwrap.wrap(item['label'],text_columns)), size=9, color=ink if active else '#8d98a9')
                positions[(turn['id'], side, item['id'])] = (x,y,lane_width,card_height)
        count = text(left, top+count_offset, f"{derived['compared_counts'][index]}项", size=15, color=theme, weight='bold')
        count.set_gid('compared-count-'+turn['id'])
        text(right, top+count_offset, f"{derived['focus_counts'][index]}项", size=15, color=theme, weight='bold')
        text(left, top+count_offset+21, '实际比较的候选', size=8, color=muted)
        text(right, top+count_offset+21, '回应涉及的候选', size=8, color=muted)
        if turn['aiIntroduced']:
            text(right, top+intro_offset-9, 'AI新提出的依据', size=8, color=warm)
            for j, criterion in enumerate(turn['aiIntroduced']):
                introduced[(turn['id'],criterion)] = chip(right, top+intro_offset+j*chip_step, criteria[criterion], warm)
        a = positions[(turn['id'], 'human', turn['userPreferred'])]
        if turn['userPreferred'] in turn['aiFocus']:
            b = positions[(turn['id'],'ai',turn['userPreferred'])]
            end=(b[0]-3,b[1]+b[3]/2)
        else:
            end=(right-3,top+label_offset)
        arrow=FancyArrowPatch((a[0]+a[2]+3,a[1]+a[3]/2),end,arrowstyle='-|>',mutation_scale=8,color=theme,linewidth=1.2,connectionstyle='arc3,rad=0')
        arrow.set_gid('preference-transfer-'+turn['id']);ax.add_patch(arrow)
    # Continuous cubic curves carry a named criterion to a later human state.
    for number, edge in enumerate(derived['transfers']):
        a = introduced[(edge['fromTurn'],edge['criterion'])]; b = adopted[(edge['toTurn'],edge['criterion'])]
        if columns == 1:
            start = (a[0]+a[2]/2,a[1]+a[3]+2); end = (b[0]+b[2]+3,b[1]+b[3]/2)
            mid = (start[1]+end[1])/2
            vertices = [start,(start[0],mid),(end[0]+25,mid),end]
        else:
            start=(a[0]+a[2]+2,a[1]+a[3]/2); end=(b[0]-3,b[1]+b[3]/2)
            if stages[edge['toTurn']][0]-stages[edge['fromTurn']][0] > span+gutter+1:
                x1=start[0]+gutter/2; x2=end[0]-gutter/2; floor=72+section_height+20+number*5
                vertices=[start,(x1,start[1]),(x1,floor),(x1+12,floor),
                          (x1+28,floor),(x2-28,floor),(x2-12,floor),
                          (x2,floor),(x2,end[1]),end]
            else:
                mid=(start[0]+end[0])/2; vertices=[start,(mid,start[1]),(mid,end[1]),end]
        path=Path(vertices,[Path.MOVETO]+[Path.CURVE4]*(len(vertices)-1))
        arrow=FancyArrowPatch(path=path,arrowstyle='-|>',mutation_scale=8,color=warm,linewidth=1.2)
        arrow.set_gid('criterion-transfer-'+str(number));ax.add_patch(arrow)
    text(margin,height-scope_height-18,'蓝线：偏好进入回应　暖线：AI依据进入后续判断',size=8,color=muted)
    text(margin,height-scope_height+4,scope,size=8,color=muted,va='top')
    return fig, height, derived
