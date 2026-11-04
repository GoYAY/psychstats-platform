"""Static, readable R-output walkthroughs with optional field interaction."""
from __future__ import annotations
from html import escape
from pathlib import Path
from .analysis_catalog import validate_result, artifact_fingerprints, analysis_dependencies, select_analysis_examples
from .reading_aids import leading_zero
from .output_guides import guides, source_map, annotated_stdout, field_button, runtime_notice
from .render import page_shell
from .statistical_display import format_p, format_number, is_p_column, is_p_field, normalize_p_text, significant_columns, significant_phrases, console_html, governing_p
import re

GROUPS = {'foundations':'描述与关联', 'data-preparation':'数据准备',
          'hypothesis-testing':'统计推断', 'group-comparisons':'差异比较',
          'regression':'回归', 'classification-clustering':'分类与聚类',
          'factor-analysis':'因素与测量', 'structural-equation-modeling':'结构方程',
          'mediation-moderation':'中介与调节', 'multilevel-longitudinal':'多层与纵向'}


def text(value) -> str:
    return escape(leading_zero(normalize_p_text(str(value))), quote=True)


def result_prose(value: str) -> str:
    source = leading_zero(normalize_p_text(value))
    phrases = significant_phrases(source)
    if not phrases:
        return escape(source)
    pattern = re.compile('|'.join(re.escape(p) for p in sorted(set(phrases),key=len,reverse=True)))
    pieces=[];cursor=0
    for m in pattern.finditer(source):
        pieces.extend([escape(source[cursor:m.start()]),'<strong class="stat-significant">'+escape(m.group())+'</strong>'])
        cursor=m.end()
    return ''.join(pieces)+escape(source[cursor:])


def report_text(case: dict, result: dict) -> str:
    errors = validate_result(case, result)
    if errors:
        raise ValueError('; '.join(errors))
    if result['status'] != 'valid':
        return '本例为故障诊断示范：' + case['invalid_reason'] + '，不得将当前估计写成成功分析结论。'
    template = guides().get(case['id'], {}).get('report_template', case['report_template'])
    return leading_zero(normalize_p_text(template.format_map(result['metrics'])))


def analysis_report_for_term(term_id: str, catalog: dict, cases: dict, results: dict) -> str | None:
    route = next((r for r in catalog.get('term_routes', []) if r['term_id'] == term_id), None)
    if not route or route.get('mode') != 'tutorial':
        return None
    for unit in route.get('unit_ids', []):
        candidates = select_analysis_examples(term_id,{'unit_ids':[unit]},cases)
        if candidates:
            case = candidates[0]
            result = results.get(case['id'], {})
            hashes = artifact_fingerprints(case, Path(__file__).resolve().parents[2])
            if any(result.get(key) != value for key, value in hashes.items()):
                raise ValueError('stale analysis artifact')
            return report_text(case, result)
    return None


def render_dendrogram(result: dict) -> str:
    tables = result.get('tables')
    if not isinstance(tables, dict) or 'dendrogram_merges' not in tables:
        return ''
    merges, order = tables['dendrogram_merges'], tables['leaf_order']
    n = len(order)
    if n < 2 or len(merges) != n-1 or {r['leaf'] for r in order} != set(range(1,n+1)):
        raise ValueError('invalid dendrogram structure')
    maximum = max(r['height'] for r in merges)
    if maximum <= 0:
        raise ValueError('dendrogram height must be positive')
    nodes = {-r['leaf']:(64+816*(r['position']-1)/(n-1),280) for r in order}
    paths = []
    for row in merges:
        x1,y1 = nodes[row['left']]; x2,y2 = nodes[row['right']]
        y = 280-240*row['height']/maximum
        paths.append(f'<path d="M{x1:.2f},{y1:.2f}V{y:.2f}H{x2:.2f}V{y2:.2f}"/>')
        nodes[row['step']] = ((x1+x2)/2,y)
    ticks = ''.join(f'<text x="54" y="{284-60*i}" text-anchor="end">{maximum*i/4:.1f}</text><path class="tree-grid" d="M64,{280-60*i}H880"/>' for i in range(5))
    k = int(result['metrics']['k'])
    cut = (merges[n-k-1]['height']+merges[n-k]['height'])/2 if 1<k<n else 0
    y = 280-240*cut/maximum
    return f'<figure class="analysis-dendrogram"><svg viewBox="0 0 900 330" role="img" aria-label="本次 Ward.D2 聚类的实际树状图"><title>Ward.D2 层次聚类：实际合并高度</title><g class="tree-axis">{ticks}<text x="64" y="22">合并高度</text><text x="450" y="315" text-anchor="middle">{n} 位教学个体（按树叶顺序排列）</text></g><g class="tree-branches">{"".join(paths)}</g><path class="tree-cut" d="M64,{y:.2f}H880"/><text x="880" y="{y-8:.2f}" text-anchor="end">教学切分：{k} 组</text></svg><figcaption>从底部个体向上读：分支连接表示合并，越高的连接对应更大的 Ward.D2 合并高度。虚线是本次三组切分；横向顺序不表示程度排名，高度不是 p 值，也不能证明真实心理类型。树和画像来自同次 R 运行。</figcaption></figure>'


def render_analysis_index(catalog: dict, cases: dict[str, dict]) -> str:
    groups = {}
    for unit in sorted(catalog['units'], key=lambda u: u.get('order', 0)):
        members = [{**c, 'method_label': unit['title']} for c in cases.values() if c['unit_id'] == unit['id']]
        if not members:
            continue
        groups.setdefault(unit['group'], []).extend(members)
    sections = []
    for group, members in groups.items():
        cards = ''.join(f'<a class="analysis-card" href="analyses/{text(c["id"])}.html" data-expand-card data-analysis-id="{text(c["id"])}" data-analysis-search="{text(c["method_label"]+" "+c["unit_id"]+" "+c["title"]+" "+c["question"])}"><span class="analysis-card-label">{text(c["method_label"])} · R</span><h3>{text(c["title"])}</h3><p>{text(c["question"])}</p><span class="analysis-card-action">读懂这次分析 ⟶</span></a>' for c in members)
        sections.append(f'<section class="analysis-group"><h2>{text(GROUPS.get(group,group))}</h2><div class="analysis-grid">{cards}</div></section>')
    body = '<section class="page-head"><h1>读懂分析结果</h1><p>从现实问题出发，把输出、诊断和结论连起来看。所有示例均使用可复现的教学数据。</p></section><div class="wrap analysis-index"><label class="analysis-filter">查找分析示例 <input type="search" id="analysis-filter" placeholder="如：结构方程、量表、两组成绩"></label><p id="analysis-filter-status" role="status" aria-live="polite"></p>'+''.join(sections)+'</div>'
    return page_shell('读懂分析结果', body, active_nav='analysis')


def render_analysis_case(case: dict, result: dict, term_names: dict[str, str], term_topics: dict | None = None, topic: str = '') -> str:
    from .paper_reporting import render_paper_result, CORE_FIT
    report = report_text(case, result)
    sources = source_map(case, result)
    guide = guides().get(case['id'], {})
    meaning_overrides = guide.get('meanings', {})
    field_topics = {a['field_id']: (term_topics or {}).get(a.get('term'), topic) for a in case['annotations']}
    metrics, meanings = [], []
    for a in case['annotations']:
        field = a['field_id']
        value = result['metrics'][field]
        displayed = format_p(value) if is_p_field(field) else format_number(value, field, precision=a.get('format', '.3g'))
        if sources[field].get('derived'):
            metrics.append(f'<tr><th scope="row">{text(a["label"])}</th><td>{field_button(field,leading_zero(displayed),a["label"],field_topics[field],is_p_field(field) and value < 0.05)}</td></tr>')
        target = a.get('term')
        link = f'<a class="inline-term" href="../terms/{text(target)}.html">{text(term_names[target])} ⟶</a>' if target in term_names else ''
        meanings.append(f'<div id="analysis-meaning-{text(field)}" class="analysis-meaning" data-topic="{text(field_topics[field])}" data-analysis-meaning="{text(field)}"><h3>{text(a["label"])}</h3><p class="analysis-location">{text(sources[field]["location"])}</p><p>{text(meaning_overrides.get(field, a["meaning"]))}</p><button type="button" class="analysis-locate" data-analysis-locate="{text(field)}">定位到输出 ⟵</button>{link}</div>')
    diagnoses = ''.join(f'<section class="analysis-diagnosis"><h3>{text(d["title"])}</h3><p>{text(d.get("body", d.get("condition", "") + d.get("action", "")))}</p></section>'
                        for d in guide.get('diagnostics', case['diagnostics']))
    links = ' '.join(f'<a class="inline-term" href="../terms/{text(slug)}.html">{text(term_names[slug])}</a>' for slug in case.get('related_terms', []) if slug in term_names)
    source_links = ' '.join(f'<a href="{escape(s["url"],quote=True)}" target="_blank" rel="noopener">{text(s["title"])}</a>' for s in case.get('sources', []) if s.get('url','').startswith('https://'))
    warnings = runtime_notice(result)
    script_name = Path(case['script']).name
    packages = analysis_dependencies(case, Path(__file__).resolve().parents[2])
    install = 'required <- c(' + ', '.join('"'+p+'"' for p in packages) + ')\nmissing <- setdiff(required, rownames(installed.packages()))\nif (length(missing)) install.packages(missing)'
    data_links = ' '.join(f'<a href="../data/{text(Path(p).name)}" download>{text(Path(p).name)}</a>' for p in case.get('data_files', []))
    parameter_tables, extra_tables = [], []
    required_tables = {s['table'] for s in sources.values() if 'table' in s}
    for name, rows in (result.get('tables') or {}).items() if isinstance(result.get('tables'), dict) else []:
        if name in {'dendrogram_merges','leaf_order'}:
            continue
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            continue
        columns = list(dict.fromkeys(key for row in rows for key in row if key != '_row'))
        numeric_columns = {key for key in columns
                           if any(isinstance(row.get(key), (float, int)) for row in rows)
                           and all(row.get(key) is None or isinstance(row.get(key), (float, int)) for row in rows)}
        column_class = {key: 'analysis-numeric' if key in numeric_columns else 'analysis-text' for key in columns}
        heading = ''.join(f'<th scope="col" class="{column_class[key]}">{text(key)}</th>' for key in columns)
        body_rows, remaining_rows = [], []
        excerpt = name in required_tables and len(rows) > 20
        selected_rows = {s['row'] for s in sources.values() if s.get('table') == name}
        if excerpt:
            selected_rows.update(i for i,row in enumerate(rows)
                                 if name == 'fit' and row.get('index') in CORE_FIT
                                 or name == 'parameters' and row.get('op') in {'~',':='})
        for index, row in enumerate(rows):
            cells = []
            emphasized = significant_columns(row)
            for key in columns:
                value = leading_zero(format_number(row[key], key, row)) if isinstance(row.get(key), (float,int)) else str(row.get(key) if row.get(key) is not None else '—')
                annotation = next((a for a in case['annotations'] if sources[a['field_id']].get('table') == name and sources[a['field_id']]['row'] == index and sources[a['field_id']]['column'] == key), None)
                content = field_button(annotation['field_id'], value, annotation['label'], field_topics[annotation['field_id']],key in emphasized) if annotation else text(value)
                if not annotation and key in emphasized:
                    content = '<strong class="stat-significant">'+content+'</strong>'
                cells.append(f'<td class="{column_class[key]}">{content}</td>')
            (remaining_rows if excerpt and index not in selected_rows else body_rows).append('<tr>'+''.join(cells)+'</tr>')
        cells = ''.join(body_rows)
        note = ''
        if {'lhs', 'op', 'rhs'} <= set(columns):
            note = '<p class="analysis-help">读表顺序：lhs 是左侧变量，op 是关系，rhs 是右侧变量。=~ 表示测量载荷，~ 表示回归，~~ 表示方差或协方差，~1 表示截距/均值，| 表示有序题目阈值，:= 表示定义的效应。est 是原量纲估计，se 是标准误，ci.lower/ci.upper 是区间；std.all 为全部标准化，std.lv 只标准化潜变量。固定参数没有可检验的 p，空值以 — 显示，不解释为 p=0。</p>'
        target_tables = parameter_tables if name in required_tables else extra_tables
        label = text(case.get('table_labels', {}).get(name, name))
        excerpt_label = ' · 关键字段摘录（保留软件字段名）' if remaining_rows else ''
        target_tables.append(note+f'<div class="analysis-output"><table><caption>{label}{excerpt_label}</caption><thead><tr>{heading}</tr></thead><tbody>{cells}</tbody></table></div>')
        if remaining_rows:
            target_tables.append(f'<details class="analysis-table-rest"><summary>其余 {len(remaining_rows)} 行软件字段</summary><div class="analysis-output"><table><caption>{label} · 其余字段</caption><thead><tr>{heading}</tr></thead><tbody>{"".join(remaining_rows)}</tbody></table></div></details>')
    parameter_tables = ''.join(parameter_tables)
    supplement = ('<div class="analysis-output analysis-supplement"><table><caption>本次 R 脚本的补充计算记录</caption><tbody>'+''.join(metrics)+'</tbody></table><p class="analysis-help">这些值由本例脚本计算并保存；右侧注明计算所用的输出或步骤。</p></div>') if metrics else ''
    console = ('<div class="analysis-output analysis-software"><p class="analysis-card-label">R 控制台 · 本次实际输出</p><pre class="analysis-annotated-console">'+annotated_stdout(case,result,sources,field_topics)+'</pre></div>') if any('start' in s for s in sources.values()) or not required_tables else ''
    software_output = console+parameter_tables+supplement
    if extra_tables:
        software_output += '<details class="analysis-extra-output"><summary>其他软件输出表</summary>'+''.join(extra_tables)+'</details>'
    design = re.sub(r'固定种子(?:模拟|生成)?', '', guide.get('design', case['design']))
    variables = case['variables']
    is_reminder = any(word in variables for word in ['代码','脚本','固定种子','共享函数','CSV','原始文件','教学生成'])
    variable_html = '' if is_reminder else '<p>'+text(variables)+'</p>'
    if guide.get('variable_map'):
        rows = ''.join(f'<tr><th scope="row">{text(row["zh"])}</th><td><code>{text(row["code"])}</code></td><td>{text(row["role"])}</td></tr>'
                       for row in guide['variable_map'])
        variable_html = '<div class="analysis-variable-map"><table><caption>中文名称与 R 字段对照</caption><thead><tr><th scope="col">中文名称</th><th scope="col">R 字段 / 代码</th><th scope="col">在本例中的含义</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
    reproduction_note = '<aside class="analysis-reproduction-note" aria-label="复现提示"><h3>复现提示</h3><p>'+text(variables)+'</p></aside>' if is_reminder else ''
    toc = '<nav class="analysis-toc" aria-label="本页目录"><p>本页导航</p>'+''.join(
        f'<a data-analysis-section href="#{anchor}">{label}</a>' for anchor,label in (
            ('analysis-design','分析设计'),('analysis-output','输出与解读'),('analysis-diagnostics','遇到这种结果'),
            ('paper-results','整理成图表'),('analysis-report','结果怎么写'),('analysis-reproduce','复现与学习')) )+'</nav>'
    body = f'''<div class="analysis-reading-layout" data-topic="{text(topic)}"><article class="analysis-detail term-content" data-analysis-case="{text(case['id'])}" data-topic="{text(topic)}">
<div class="analysis-breadcrumb"><a href="../analysis.html" data-collapse-analysis>怎么看数据 ⟶</a><span>{text(case['title'])}</span></div>
<h1>{text(case['title'])}</h1>
<section class="analysis-question"><h2><span aria-hidden="true">“</span>你可能会问</h2><p>{text(case['question'])}</p></section>
<section id="analysis-design"><h2>这次分析了什么</h2><p>{text(design)}</p>{variable_html}</section>
<section id="analysis-output"><h2>真实运行输出</h2><p class="analysis-help">选择主题色数值，查看对应解释；点击可固定多个标记。“定位到输出”返回数值所在位置。加粗表示按 0.05 阈值达到显著的检验及对应估计。</p><button type="button" data-analysis-clear>清除标记</button>
<div class="analysis-output-layout"><div class="analysis-software-results">{software_output}</div><div class="analysis-meanings">{''.join(meanings)}</div></div>{warnings}
{render_dendrogram(result)}<details class="analysis-console"><summary>完整控制台输出</summary><pre>{console_html(result['stdout'])}</pre><p class="analysis-help">页面统一整理 p 值格式与显著性字重。<a href="../analysis-logs/{text(case['id'])}.txt" download>下载未改写的原始控制台日志</a></p></details></section>
<section id="analysis-diagnostics"><h2>遇到这种结果怎么办</h2>{diagnoses}</section>
{render_paper_result(case,result,source_page=True)}
<section id="analysis-report" class="analysis-report"><p class="analysis-card-label">教学结果写作示范</p><h2>研究结果怎么写</h2><p>{result_prose(report)}</p></section>
<section id="analysis-reproduce"><h2>复现与继续学习</h2><p><a href="../analysis-code/{text(script_name)}" download>下载本例 R 代码</a> · <a href="../analysis-code/_common.R" download>共享结果记录函数</a> · {data_links}</p><p>将代码、共享函数和数据放入同一目录，在 R/RStudio 将工作目录设为该文件夹，再运行脚本。</p>{reproduction_note}<details class="analysis-reproduction"><summary>首次安装依赖与运行环境</summary><p>依赖包：{text('、'.join(packages))}；仅首次缺包时运行：</p><pre><code class="language-r">{escape(install)}</code></pre><pre>{escape(result['session_info'])}</pre></details><p>{links}</p><details><summary>方法参考</summary><p>{source_links}</p></details></section>
</article>{toc}</div>'''
    return page_shell(case['title'], body, root='../', active_nav='analysis')


def analysis_search_entries(cases: dict[str, dict], catalog: dict | None = None) -> list[dict]:
    labels = {u['id']:u['title'] for u in (catalog or {}).get('units', [])}
    return [{'id': 'analysis-'+c['id'], 'zh': c['title'], 'en':'R analysis',
             'kind':'analysis', 'url':'analyses/'+c['id']+'.html',
             'topic': 'analysis', 'topic_label':'分析示例', 'aliases':[c['unit_id'],labels.get(c['unit_id'],c['unit_id'])],
             'summary':c['question'], 'body_text':c['question']+' '+c['design']+' '+
             ' '.join(a['label']+' '+a['meaning'] for a in c['annotations'])}
            for c in cases.values()]
