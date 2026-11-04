"""Authored links into saved R output. Presentation never changes R evidence."""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from html import escape
from pathlib import Path
from .statistical_display import console_html


@lru_cache(maxsize=1)
def guides() -> dict:
    path = Path(__file__).resolve().parents[1]/'content/analysis_guides.json'
    authored = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    support_path = path.with_name('analysis_support.json')
    if support_path.exists():
        support = json.loads(support_path.read_text(encoding='utf-8'))
        for slug, item in support['cases'].items():
            guide = authored.setdefault(slug, {})
            guide['variable_map'] = [row for name in item.get('variable_sets', [])
                                     for row in support['variable_sets'][name]] + item.get('variable_map', [])
            guide['diagnostics'] = item['diagnostics']
            guide['meanings'] = {**guide.get('meanings', {}), **item.get('meanings', {})}
            for field, location in item.get('locations', {}).items():
                # Only display labels change; numeric source selectors remain intact.
                guide.setdefault('sources', {}).setdefault(field, {})['location'] = location
            if 'design' in item:
                guide['design'] = item['design']
    return authored


def field_button(field: str, value: str, label: str, topic: str = '', significant: bool = False) -> str:
    content = escape(value)
    if significant:
        content = '<strong class="stat-significant">'+content+'</strong>'
    return (f'<button type="button" class="analysis-field analysis-source-field" '
            f'data-topic="{escape(topic)}" data-analysis-source="{escape(field)}" data-analysis-field="{escape(field)}" '
            f'aria-pressed="false" aria-label="{escape(label)}：{escape(value)}" '
            f'aria-describedby="analysis-meaning-{escape(field)}">{content}</button>')


def source_map(case: dict, result: dict) -> dict:
    """Resolve explicit selectors; never guess a location by numeric coincidence."""
    authored = guides().get(case['id'], {}).get('sources', {})
    sources = {}
    for annotation in case['annotations']:
        field = annotation['field_id']
        spec = authored.get(field, {})
        if 'table' in spec:
            rows = result.get('tables', {}).get(spec['table'], [])
            matches = [(i, row) for i, row in enumerate(rows)
                       if all(str(row.get(k, '')).strip() == str(v) for k, v in spec.get('where', {}).items())]
            if len(matches) != 1 or spec['column'] not in matches[0][1]:
                raise ValueError(f'{case["id"]}/{field}: ambiguous or missing table source')
            index, row = matches[0]
            value = row[spec['column']]
            if not isinstance(value, (float, int)) or not math.isclose(value, result['metrics'][field], rel_tol=1e-8, abs_tol=1e-10):
                raise ValueError(f'{case["id"]}/{field}: source value disagrees with metric')
            sources[field] = {**spec, 'row': index, 'location': spec.get('location', spec['table']+' → '+', '.join(f'{k}={v}' for k,v in spec.get('where',{}).items())+' → '+spec['column'])}
        elif 'pattern' in spec or 'vector' in spec:
            raw = result['stdout']
            if 'vector' in spec:
                columns = spec['vector'].split()
                pattern = r'(?m)^\s*' + r'\s+'.join(re.escape(x) for x in columns) + r'\s*\n([^\n]+)'
                match = re.search(pattern, raw)
                tokens = list(re.finditer(r'\S+', match[1])) if match else []
                if len(tokens) != len(columns):
                    raise ValueError(f'{case["id"]}/{field}: missing vector source')
                token = tokens[columns.index(spec['column'])]
                start, end = match.start(1)+token.start(), match.start(1)+token.end()
                location = spec.get('location', 'R 命名向量 → '+spec['column'])
            else:
                matches = list(re.finditer(spec['pattern'], raw, re.M))
                occurrence = spec.get('occurrence', 0)
                if len(matches) <= occurrence:
                    raise ValueError(f'{case["id"]}/{field}: missing console source')
                start, end = matches[occurrence].span(spec.get('group', 1))
                location = spec['location']
            sources[field] = {'start': start, 'end': end, 'location': location}
        else:
            sources[field] = {'derived': True, 'location': spec.get('location', '本例 R 脚本 → 补充计算记录 → '+field)}
    return sources


def annotated_stdout(case: dict, result: dict, sources: dict, topics: dict | None = None) -> str:
    raw = result['stdout']
    annotations = {(s['start'],s['end']): {'field':a['field_id'],'label':a['label'],'topic':(topics or {}).get(a['field_id'],'')}
                   for a in case['annotations'] if 'start' in (s := sources[a['field_id']])}
    # Move the startup locale echo into the verbatim full console, leaving analysis first.
    html = console_html(raw,annotations)
    if raw.startswith('[1] "LC_COLLATE='):
        html = html.split('\n', 1)[1] if '\n' in html else html
    return html.lstrip('\n')


def runtime_notice(result: dict) -> str:
    stderr = result.get('stderr', '').strip()
    if not stderr:
        return ''
    locale_only = all(not line.strip() or line.startswith('During startup') or
                      re.fullmatch(r'\d+: Setting LC_[A-Z_]+=C\.UTF-8 failed\s*', line)
                      for line in stderr.splitlines())
    if locale_only and result.get('exit_code') == 0:
        message = ('R 启动时尝试使用 C.UTF-8 的地区设置，当前 Windows 环境采用了其他可用设置。'
                   '这些设置负责字符识别、文字排序、日期和货币格式。本次分析已完成，并保存了统计输出。'
                   '复现时若出现乱码或日期读取异常，可在 RStudio 中使用 UTF-8 编码，并查看下方 R 环境记录中的 locale 设置。')
        title = '启动环境提示：地区与字符设置'
    else:
        message = '本次运行保存了以下提示。请结合具体模型查看提示涉及的步骤，再按“遇到这种结果怎么办”检查估计、收敛和数据设置。'
        title = '本次运行的提示'
    return f'<aside class="analysis-warning"><h3>{title}</h3><p>{message}</p><details><summary>查看原始运行提示</summary><pre>{escape(stderr)}</pre></details></aside>'
