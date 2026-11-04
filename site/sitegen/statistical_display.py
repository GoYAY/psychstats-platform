"""Presentation-only p formatting and significance; saved evidence stays intact."""
from __future__ import annotations

import math
import re
from html import escape

NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
P_EXPRESSION = re.compile(r'(?<![A-Za-z_])(?P<label>p(?:[-_ ]?value)?|p[_ .]?(?:holm|adj|adjusted|reference)|p\s*值|prob)\s*(?P<op>[=:：]\s*[<>≤≥]?|[<>≤≥]|为)\s*(?P<value>'+NUMBER+r')', re.I)
ESTIMATES = {'estimate','est','value','std.all','std.lv','std.nox','diff','difference','slope','coefficient','f','f.value','approx f','t value','t.value','z','chisq.diff','pillai'}


def is_p_column(key: str) -> bool:
    key = str(key).strip().lower()
    return key in {'p','pvalue','p.value','p_value','p-value','p adj','g-g pr','h-f pr'} or bool(re.fullmatch(r'pr\(.+\)|pr\..+\.|p[_ .](?:holm|adj|adjusted|reference)',key))


def is_p_field(key: str) -> bool:
    return is_p_column(key) or key.endswith('_p') or key.endswith('_gg_p')


def valid_p(value) -> bool:
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and 0 <= value <= 1


def format_p(value: float) -> str:
    if not valid_p(value):
        raise ValueError('p must be finite and between 0 and 1')
    return '<0.001' if value < 0.001 else format(value,'.4g')


def information_criterion(key: str, row: dict | None = None) -> bool:
    names = [str(key), *(str((row or {}).get(k, '')) for k in ('index', 'field_id'))]
    return any(re.search(r'(?:^|_)(?:aic|aicc|bic|bic2|sabic|caic|icl)(?:$|_)', name.lower()) for name in names)


def format_number(value: float, key: str = '', row: dict | None = None, precision: str = '.4g') -> str:
    row = row or {}
    if is_p_column(key) or key == governing_p(row) or key == 'value' and is_p_field(row.get('field_id', '')):
        return format_p(value)
    if information_criterion(key, row):
        return format(value, '.2f')
    return str(value) if isinstance(value, int) else format(value, precision)


def normalize_p_text(value: str) -> str:
    def replace(match):
        number = float(match['value'])
        if valid_p(number) and number < 0.001 and not any(c in match['op'] for c in '>≥'):
            return match['label']+' < 0.001'
        return match.group()
    return P_EXPRESSION.sub(replace,value)


def governing_p(row: dict) -> str | None:
    if 'pvalue' in str(row.get('index','')).split('.') and valid_p(row.get('value')):
        return 'value'
    keys = [key for key,value in row.items() if is_p_column(key) and valid_p(value)]
    priority = {'p_holm':0,'p adj':0,'p_adj':0,'p.adjusted':0,'p_reference':1,'g-g pr':1,'h-f pr':2}
    return min(keys,key=lambda key:priority.get(key.lower(),3)) if keys else None


def significant_row(row: dict, alpha: float = 0.05) -> bool:
    key = governing_p(row)
    return key is not None and row[key] < alpha


def significant_columns(row: dict, alpha: float = 0.05) -> set[str]:
    if not significant_row(row,alpha):
        return set()
    return {governing_p(row)} | {key for key,value in row.items() if key.lower() in ESTIMATES and isinstance(value,(int,float))}


def significant_phrases(source: str, alpha: float = 0.05) -> list[str]:
    result=[]
    for match in P_EXPRESSION.finditer(source):
        p=float(match['value'])
        if not valid_p(p) or p >= alpha or '>' in match['op'] or '≥' in match['op']:
            continue
        start=max(source.rfind(c,0,match.start()) for c in '。；;\n')+1
        end=min((i for c in '。；;\n' if (i:=source.find(c,match.end()))>=0),default=len(source))
        corrected=[m for m in P_EXPRESSION.finditer(source,start,end) if re.search('holm|adj',m['label'],re.I)]
        if corrected and (not re.search('holm|adj',match['label'],re.I) or any(float(m['value'])>=alpha for m in corrected)):
            continue
        result.append(match.group())
        # Associate estimates only within this result clause, not an earlier finding.
        context=source[start:match.start()]
        pattern=r'(?<![A-Za-z_])(?:B|b|β|r|ρ|OR|a|c[′\']?|t|F|χ²)(?:\([^)]*\))?\s*[=＝]\s*'+NUMBER
        result.extend(m.group() for m in re.finditer(pattern,context))
    return result


def console_marks(raw: str, alpha: float = 0.05) -> dict[tuple[int,int],tuple[str,bool]]:
    """Locate p tokens using explicit labels or complete named table headers."""
    marks={}
    for m in re.finditer(r'(?im)\b(?:AIC|BIC|AICc|SABIC)\b\)?\s*[:=]?\s*('+NUMBER+r')', raw):
        value = float(m[1])
        if math.isfinite(value):
            marks[m.span(1)] = (format(value, '.2f'), False)
    for m in P_EXPRESSION.finditer(raw):
        p=float(m['value'])
        if not valid_p(p):continue
        start=m.start('value')
        # Existing '<' stays in the console prefix, so replace its entire span.
        operator=m['op'].strip()
        if '<' in operator and p < 0.001:
            start=raw.rfind('<',m.start('op'),m.start('value'))
        display='<0.001' if p < 0.001 and not any(c in operator for c in '>≥') else raw[start:m.end()]
        significant=p < alpha and not any(c in operator for c in '>≥')
        marks[(start,m.end())]=(display,significant)
        if significant:
            line_start=raw.rfind('\n',0,m.start())+1
            for est in re.finditer(r'\b(?:t|F|W|X-squared|chi-squared)\s*=\s*('+NUMBER+r')',raw[line_start:m.start()]):
                span=(line_start+est.start(1),line_start+est.end(1))
                marks[span]=(raw[slice(*span)],True)
    offset=0;columns=[]
    numeric=re.compile(r'(?<![\w.])(?:<\s*)?'+NUMBER+r'(?![\w.])')
    nonnumeric={'term','effect','outcome','comparison','lhs','op','rhs','group','model','call'}
    for line in raw.splitlines(keepends=True):
        normalized=line.strip()
        for label in ['Std. Error','t value','F value','Sum Sq','Mean Sq','approx F','num Df','den Df','G-G Pr','H-F Pr','p adj']:
            normalized=normalized.replace(label,label.replace(' ','_'))
        possible=[token.replace('_',' ') if token in {'Std._Error','t_value','F_value','Sum_Sq','Mean_Sq','approx_F','num_Df','den_Df','G-G_Pr','H-F_Pr','p_adj'} else token for token in normalized.split()]
        # Named vectors and R lists also carry explicit p field labels.
        if possible and any(is_p_column(c) or information_criterion(c) for c in possible) and not numeric.search(line) and not line.lstrip().startswith(('Signif.','Call:')):
            columns=[c for c in possible if c.lower() not in nonnumeric and c != '[1]']
        elif line.strip().startswith('$') and is_p_column(line.strip()[1:]):
            columns=[line.strip()[1:]]
        elif columns:
            tokens=list(numeric.finditer(line))
            if len(tokens)>=len(columns):
                tokens=tokens[-len(columns):]
                row={c:float(t.group().replace('<','').strip()) for c,t in zip(columns,tokens)}
                strong=significant_columns(row,alpha)
                for c,t in zip(columns,tokens):
                    if is_p_column(c) and valid_p(row[c]):
                        marks[(offset+t.start(),offset+t.end())]=(format_p(row[c]) if row[c]<0.001 else t.group(),c in strong)
                    elif information_criterion(c):
                        marks[(offset+t.start(),offset+t.end())]=(format_number(row[c], c), False)
                    elif c in strong:
                        marks[(offset+t.start(),offset+t.end())]=(t.group(),True)
            elif line.strip() and not line.lstrip().startswith('[1]'):
                columns=[]
        offset+=len(line)
    return marks


def console_html(raw: str, annotations: dict | None = None, alpha: float = 0.05) -> str:
    marks=console_marks(raw,alpha)
    spans={span:(display,strong,None) for span,(display,strong) in marks.items()}
    for span,annotation in (annotations or {}).items():
        matching=[(s,v) for s,v in marks.items() if s[0]>=span[0] and s[1]<=span[1]]
        display=raw[slice(*span)];strong=False
        for s,(replacement,significant) in sorted(matching,reverse=True):
            display=display[:s[0]-span[0]]+replacement+display[s[1]-span[0]:]
            strong=strong or significant
        for s in list(spans):
            if s[0]<span[1] and s[1]>span[0]:del spans[s]
        if is_p_field(annotation['field']):
            token=re.search(NUMBER,display)
            if token and valid_p(float(token.group())):
                p=float(token.group());display=format_p(p) if p<0.001 else display;strong=p<alpha
        spans[span]=(display,strong,annotation)
    parts=[];cursor=0
    for (start,end),(display,strong,annotation) in sorted(spans.items()):
        if start<cursor:continue
        parts.append(escape(raw[cursor:start]))
        # Preserve fixed-width column boundaries when compacting long p numbers.
        padding=' '*max(0,end-start-len(display))
        if annotation:
            from .output_guides import field_button
            parts.append(field_button(annotation['field'],display,annotation['label'],annotation.get('topic',''),strong)+padding)
        else:
            rendered=escape(display)
            parts.append(('<strong class="stat-significant">'+rendered+'</strong>' if strong else rendered)+padding)
        cursor=end
    parts.append(escape(raw[cursor:]))
    return ''.join(parts)
