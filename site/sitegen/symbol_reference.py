"""Curated notation shared by the reference page and term-card badges."""
from html import escape
import json
from pathlib import Path
import re


def load_reference(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    entries = json.loads(path.read_text(encoding='utf-8'))['entries']
    seen = set()
    for entry in entries:
        key = entry['id']
        if not re.fullmatch(r'[a-z0-9-]+', key) or key in seen:
            raise ValueError(f'Invalid/duplicate symbol entry: {key}')
        seen.add(key)
        if entry['kind'] not in ('statistic', 'output'):
            raise ValueError(f'{key}: unknown reference category')
        for field in ('symbol', 'label', 'context', 'note'):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValueError(f'{key}: missing {field}')
        if not entry.get('terms') or not set(entry.get('card_terms', [])) <= set(entry['terms']):
            raise ValueError(f'{key}: invalid term mapping')
    return entries


def symbol_html(entry: dict) -> str:
    text = escape(entry['symbol'])
    if entry.get('kind') == 'output':
        return '<code>' + text + '</code>'
    if entry.get('italic'):
        text = '<i class="stat-letter">' + text + '</i>'
    else:
        text = '<span class="stat-roman">' + text + '</span>'
    for script in ('sub', 'sup'):
        if entry.get(script):
            text += f'<{script}>' + escape(entry[script]) + f'</{script}>'
    return '<span class="stat-symbol">' + text + '</span>'


def attach_card_symbols(terms: list[dict], entries: list[dict]) -> None:
    for term in terms:
        term['card_symbols'] = [entry for entry in entries if term['id'] in entry.get('card_terms', [])][:2]


def render_reference(entries: list[dict], terms_by_id: dict) -> str:
    from .render import page_shell
    rows = []
    for entry in entries:
        links = ''.join(f'<a href="terms/{escape(key)}.html">{escape(terms_by_id[key]["zh"])}</a>'
                        for key in entry['terms'] if key in terms_by_id)
        if not links:
            continue
        tokens = [entry['symbol'] + entry.get('sub', '') + entry.get('sup', ''), *entry.get('aliases', [])]
        searchable = ' '.join([*tokens, entry['label'], entry['context'], entry['note'],
                              *(terms_by_id[key]['zh'] for key in entry['terms'] if key in terms_by_id)])
        rows.append(f'<tr id="{escape(entry["id"])}" data-symbol-row data-kind="{entry["kind"]}" '
                    f'data-tokens="{escape(json.dumps(tokens, ensure_ascii=False), quote=True)}" '
                    f'data-search="{escape(searchable, quote=True)}" tabindex="-1">'
                    f'<th scope="row" data-label="符号 / 字段">{symbol_html(entry)}</th>'
                    f'<td data-label="中文含义"><strong>{escape(entry["label"])}</strong></td>'
                    f'<td data-label="出现在哪里"><span class="symbol-context">{escape(entry["context"])}</span>'
                    f'<p>{escape(entry["note"])}</p></td>'
                    f'<td data-label="继续理解"><div class="symbol-term-links">{links}</div></td></tr>')
    body = ('<section class="page-head"><h1>符号速查</h1><p>认出符号，读懂输出，再回到对应术语理解它。</p></section>'
            '<section class="symbol-reference" aria-label="统计符号与输出字段对照">'
            '<div class="symbol-controls"><label for="symbol-query">查符号、英文或中文'
            '<input id="symbol-query" type="search" placeholder="例如 df、alpha、自由度、Estimate" '
            'autocomplete="off" aria-describedby="symbol-search-help"></label>'
            '<label for="symbol-kind">类别<select id="symbol-kind"><option value="">全部</option>'
            '<option value="statistic">统计符号</option><option value="output">R 输出字段</option></select></label>'
            '<button type="button" id="symbol-clear">重置</button></div>'
            '<p id="symbol-search-help" class="symbol-help">无需输入公式：可用中文含义或英文名称搜索。'
            '单个拉丁字母区分大小写；α / alpha 会同时列出不同含义，请结合使用情境判断。</p>'
            '<p class="symbol-type-note">排版约定：拉丁统计字母用斜体，希腊字母与指标缩写用正体；'
            'R 输出字段保留代码原样。样本量、系数等记号并非所有教材或软件完全一致。</p>'
            '<p id="symbol-count" role="status" aria-live="polite"></p>'
            '<table class="symbol-table"><caption class="sr-only">统计符号和 R 输出字段的情境释义</caption>'
            '<thead><tr><th>符号 / 字段</th><th>中文含义</th><th>出现在哪里 · 怎样理解</th><th>继续理解</th></tr></thead>'
            '<tbody>' + ''.join(rows) + '</tbody></table>'
            '<p id="symbol-empty" class="empty-state" hidden>没有找到对应符号。试试中文名称、英文全称，或重置类别。</p>'
            '<footer class="symbol-sources"><p>这是一份情境速查表，不是跨软件统一的符号标准；以实际函数和模型说明为准。</p>'
            '<p>依据：<a href="https://apastyle.apa.org/instructional-aids/numbers-statistics-guide.pdf">APA 数字与统计排版指南</a> · '
            '<a href="https://stat.ethz.ch/R-manual/R-devel/library/stats/html/summary.lm.html">R：summary.lm</a> · '
            '<a href="https://stat.ethz.ch/R-manual/R-devel/library/stats/html/t.test.html">R：t.test</a> · '
            '<a href="https://lavaan.ugent.be/tutorial/inspect.html">lavaan：结果提取</a></p></footer></section>')
    return page_shell('符号速查', body, active_nav='symbols')
