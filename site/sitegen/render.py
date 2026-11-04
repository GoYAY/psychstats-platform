from __future__ import annotations

from html import escape
import re
import json
from typing import Any
from .reading_aids import leading_zero, reading_metadata, formula_aid
from .statistical_display import normalize_p_text, significant_phrases

TYPE_LABELS = {"concept": "概念", "method": "方法", "indicator": "指标", "workflow": "流程"}
LEVEL_LABELS = {"basic": "基础", "intermediate": "进阶", "advanced": "高级"}
TAB_TITLE = "心理统计学术语图鉴-轻松掌握心理统计和r语言数据分析"


def _text(value: Any) -> str:
    return escape(leading_zero(normalize_p_text(str("" if value is None else value))), quote=True)


def topic_overview(basis: str) -> str:
    overview = re.sub(r'(?:现代心理与教育统计学|高级心理统计)\s*[：:]\s*', '', basis or '')
    return overview.replace('结合基础教材的', '').strip()


def page_shell(title: str, body: str, *, root: str = "", active_nav: str = "terms") -> str:
    nav_items = [('terms','index.html','术语'),('paths','paths.html','学习路径'),('practice','practice.html','练习'),('datasets','datasets.html','示例数据'),('symbols','symbols.html','符号速查'),('analysis','analysis.html','怎么看数据'),('sources','sources.html','来源说明')]
    navigation = ''.join(f'<a href="{root}{file}"'+(' aria-current="page"' if slug == active_nav else '')+f'>{label}</a>' for slug,file,label in nav_items)
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml">
  <link rel="alternate icon" href="{root}assets/favicon.ico" type="image/x-icon">
  <link rel="stylesheet" href="{root}assets/site.css">
  {analysis_style}
  <link rel="stylesheet" href="{root}assets/vendor/katex/katex.min.css">
  <script src="{root}assets/theme.js"></script>
  <script src="{root}assets/card-transition.js"></script>
</head>
<body>
  <header class="site-head"><div class="wrap nav-row">
    <a class="brand" href="{root}index.html"><img src="{root}assets/favicon.svg" width="28" height="28" alt="" aria-hidden="true"><span>心理统计学术语图鉴</span></a>
    <nav aria-label="主导航">
      {navigation}
    </nav><div class="header-search" data-root="{root}">
      <label class="search-scope-label">范围 <select id="search-scope" aria-label="搜索范围"><option value="global">全站</option></select></label>
      <label class="search-input-label">搜索 <input id="q" type="search" placeholder="搜索全站术语" autocomplete="off" aria-describedby="search-help" aria-controls="search-panel"></label>
      <div id="search-panel" class="search-panel" hidden>
        <p id="search-help">全站搜索：名称优先，也查正文。选择范围可缩小搜索。</p>
        <p id="search-status" role="status" aria-live="polite" aria-atomic="true"></p>
        <div id="page-find-controls" hidden><button type="button" id="find-previous">上一处</button><button type="button" id="find-next">下一处</button></div>
        <ol id="search-results"></ol>
      </div>
    </div>
  </div></header>
  <main>{body}</main>
  <p id="favorite-status" class="favorite-status" role="status" aria-live="polite" hidden></p>
  <script src="{root}assets/data/site-data.js" defer></script>
  <script src="{root}assets/search.js" defer></script>
  <script src="{root}assets/navigation-policy.js" defer></script>
  <script src="{root}assets/page-runtime.js" defer></script>
  {practice_data}
  <script src="{root}assets/practice.js" defer></script>
  <script src="{root}assets/filter-menu.js" defer></script>
  <script src="{root}assets/cursor.js" defer></script>
  <script src="{root}assets/favorites.js" defer></script>
  <script src="{root}assets/site.js" defer></script>
  <script src="{root}assets/search-ui.js" defer></script>
  <script src="{root}assets/formula-reading.js" defer></script>
  {symbol_script}
  {analysis_script}
  <script src="{root}assets/navigation-motion.js" defer></script>
  <script src="{root}assets/soft-navigation.js" defer></script>
</body>
</html>
""".format(title=_text(TAB_TITLE), body=body, root=root, navigation=navigation,
           practice_data=f'<script src="{root}assets/data/practice-data.js" defer></script>' if active_nav == 'practice' else '',
           symbol_script=f'<script src="{root}assets/symbols.js" defer></script>' if active_nav == 'symbols' else '',
           analysis_script=f'<script src="{root}assets/analysis-reader.js" defer></script>' if active_nav == 'analysis' else '',
           analysis_style=f'<link rel="stylesheet" href="{root}assets/analysis-reader.css">' if active_nav == 'analysis' else '')


def _favorite_button(term: dict[str, Any]) -> str:
    return (f'<button type="button" class="favorite-button" data-favorite="{_text(term.get("id"))}" '
            f'data-name="{_text(term.get("zh"))}" aria-pressed="false" aria-label="收藏{_text(term.get("zh"))}">'
            '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M6 4h12v17l-6-4-6 4z"/></svg>'
            '<span data-favorite-label>收藏</span></button>')


def _term_cards(terms: list[dict[str, Any]], *, preview: bool, topic_names: dict[str,str], root: str = "", active_topic: str | None = None) -> str:
    from .symbol_reference import symbol_html
    cards = []
    for term in terms:
        symbols = term.get('card_symbols', [])
        symbol_links = ('<div class="term-symbols">' + ''.join(
            f'<a class="term-symbol-badge" href="{root}symbols.html#{_text(entry["id"])}" '
            f'aria-label="查看{_text(entry["label"])}符号释义" title="{_text(entry["label"])} · 点击查看符号释义">'
            + symbol_html(entry) + '</a>' for entry in symbols) + '</div>') if symbols else ''
        symbol_width = sum(max(44, len(entry['symbol']) * 15 + 16) for entry in symbols) + 8
        symbol_style = f' style="--symbol-space:{symbol_width}px"' if symbols else ''
        has_r = isinstance(term.get("r_practice"), dict)
        r_badge = '<span class="tag">含 R 实操</span>' if has_r else ""
        hidden = ' hidden' if active_topic is not None and term.get('topic') != active_topic else ''
        cards.append(
            f'<article class="term-card" data-term data-id="{_text(term.get("id"))}" '
            f'data-topic="{_text(term.get("topic"))}" data-type="{_text(term.get("type"))}" '
            f'data-level="{_text(term.get("level"))}" data-has-r="{str(has_r).lower()}"{symbol_style}{hidden}>'
            f'<a href="{root}terms/{_text(term.get("id"))}.html" data-expand-card="term">'
            f'<h2>{_text(term.get("zh"))}</h2>'
            f'<p lang="en">{_text(term.get("en"))}</p>'
            f'<p>{_text(term.get("summary"))}</p><div class="tags">'
            f'<span class="tag">{_text(topic_names.get(term.get("topic"), term.get("topic")))}</span>'
            f'<span class="tag">{_text(TYPE_LABELS.get(term.get("type"), term.get("type")))}</span>'
            f'<span class="tag">{_text(LEVEL_LABELS.get(term.get("level"), term.get("level")))}</span>{r_badge}</div></a>{symbol_links}{_favorite_button(term)}</article>'
        )
    return '<section class="term-grid">'+"".join(cards)+'</section>'


def _filters(topics: list[dict[str, Any]] | None = None) -> str:
    origin_options = ''.join(f'<option value="{_text(t["id"])}">{_text(t["zh"])}</option>' for t in (topics or []))
    return (
        '<section class="filter-bar" aria-label="筛选本主题术语">'
        '<label>难度 <select id="level-filter"><option value="">全部难度</option>'
        '<option value="basic">基础</option><option value="intermediate">进阶</option><option value="advanced">高级</option></select></label>'
        '<label>类型 <select id="type-filter"><option value="">全部类型</option>'
        '<option value="concept">概念</option><option value="method">方法</option><option value="indicator">指标</option><option value="workflow">流程</option></select></label>'
        '<label>R 实操 <select id="r-filter"><option value="">全部</option><option value="true">含 R 实操</option><option value="false">不含 R 实操</option></select></label>'
        f'<label id="favorite-topic-label" hidden>所属主题 <select id="favorite-topic-filter"><option value="">全部主题</option>{origin_options}</select></label>'
        '<span id="result-count" class="filter-count" role="status" aria-live="polite"></span></section>'
        '<p id="filter-empty" class="empty-state" hidden>本主题没有符合条件的术语，请调整筛选或搜索词。</p>'
    )


def _topic_nav(topics: list[dict[str, Any]], active: str, root: str = "", counts: dict[str, int] | None = None) -> str:
    links=[]
    for i,topic in enumerate(topics,1):
        current=' aria-current="page"' if topic['id']==active else ''
        links.append(f'<a href="{root}index.html?topic={_text(topic["id"])}" data-topic-link="{_text(topic["id"])}"{current}>'
                     f'<span class="topic-number" aria-hidden="true">{i:02}</span>{_text(topic["zh"])}'
                     f'<span class="topic-count" data-topic-count="{_text(topic["id"])}" aria-label="{(counts or {}).get(topic["id"],0)}个术语">{(counts or {}).get(topic["id"],0)}</span></a>')
    links.append(f'<a href="{root}index.html?topic=favorites" data-topic-link="favorites"><span class="topic-number" aria-hidden="true">11</span>收藏'
                 '<span class="topic-count" data-topic-count="favorites" aria-label="0个收藏">0</span></a>')
    return '<nav class="topic-nav" aria-label="按学习顺序选择主题">'+''.join(links)+'</nav>'


def render_index(terms: list[dict[str, Any]], *, preview: bool, topic_names: dict[str, str] | None = None, topics: list[dict[str,Any]] | None = None) -> str:
    topic_names=topic_names or {}
    if topics is None:
        topics=[{'id':slug,'zh':topic_names.get(slug,slug)} for slug in dict.fromkeys(t['topic'] for t in terms)]
    first=next((topic for topic in topics if any(t['topic']==topic['id'] for t in terms)),topics[0] if topics else {'id':'','zh':'术语'})
    body = (
        '<section class="hero"><div class="hero-main"><div><h1>心理统计学术语图鉴</h1>'
        '<p>先选主题，再沿着同一条学习链理解概念与方法。</p>'
        '</div></div></section>'
        '<p class="curriculum-hint">主题按基础教材到高级教材的学习顺序排列；点击切换，下方筛选只作用于当前主题。</p>'
        +_topic_nav(topics,first['id'],counts={t['id']:sum(term['topic']==t['id'] for term in terms) for t in topics})
        +f'<section id="topic-intro" class="topic-intro" data-topic="{_text(first["id"])}"><h2 id="topic-title">{_text(first["zh"])}</h2>'
        +f'<p id="topic-description">{_text(first.get("description", ""))}</p><p id="topic-basis" class="curriculum-basis">{_text(first.get("overview", topic_overview(first.get("basis", ""))))}</p></section>'
        +_filters(topics)+_term_cards(terms,preview=preview,topic_names=topic_names,active_topic=first['id'])
    )
    return page_shell("心理统计学术语图鉴", body)


def _term_candidates(names: dict[str, str | list[str]]) -> dict[str, str]:
    candidates = {name: slug for slug, labels in names.items()
                  for name in (labels if isinstance(labels, list) else [labels]) if name}
    # Prefer canonical names over aliases or embedded concepts with the same name.
    for slug, labels in names.items():
        if '#' not in slug:
            canonical = (labels[0] if labels else '') if isinstance(labels, list) else labels
            if canonical:
                candidates[canonical] = slug
    return candidates


def _term_pattern(candidates: dict[str, str]) -> re.Pattern:
    parts = []
    for name in sorted(candidates, key=len, reverse=True):
        part = re.escape(name)
        if re.match(r'[A-Za-z0-9_]', name[0]):
            part = r'(?<![A-Za-z0-9_])' + part
        if re.match(r'[A-Za-z0-9_]', name[-1]):
            part += r'(?![A-Za-z0-9_])'
        parts.append(part)
    return re.compile('|'.join(parts))


def _linked_text(value: Any, current_id: str, names: dict[str, str | list[str]]) -> str:
    candidates = _term_candidates(names)
    if not candidates:
        return _text(value)
    pattern = _term_pattern(candidates)
    source = normalize_p_text(str(value or ""))
    result: list[str] = []
    end = 0
    for match in pattern.finditer(source):
        result.append(_text(source[end:match.start()]))
        if candidates[match.group()] == current_id or (match.group() in {'拟合','模型拟合'} and source[match.end():].startswith(('值','指数','优度'))):
            result.append(_text(match.group()))
        else:
            slug, separator, anchor = candidates[match.group()].partition('#')
            href = slug + '.html' + ('#' + anchor if separator else '')
            result.append(f'<a href="{_text(href)}" class="term-inline-link">{_text(match.group())}</a>')
        end = match.end()
    result.append(_text(source[end:]))
    return "".join(result)


def _reading_text(value: Any, current_id: str, names: dict[str,str], emphasis: list[str] | None = None) -> str:
    source=normalize_p_text(str(value or ''))
    selected=[phrase for phrase in [*(emphasis or []),*significant_phrases(source)] if phrase and phrase in source]
    if not selected: return _linked_text(source,current_id,names)
    pattern=re.compile('|'.join(re.escape(phrase) for phrase in sorted(set(selected),key=len,reverse=True)))
    ranges = [match.span() for match in pattern.finditer(source)]
    candidates = _term_candidates(names)
    terms = list(_term_pattern(candidates).finditer(source)) if candidates else []
    # Expand emphasis boundaries inside complete terms instead of linking fragments.
    expanded = []
    for start, end in ranges:
        for term in terms:
            if term.start() < end and term.end() > start:
                start, end = min(start, term.start()), max(end, term.end())
        if expanded and start <= expanded[-1][1]:
            expanded[-1] = (expanded[-1][0], max(end, expanded[-1][1]))
        else:
            expanded.append((start, end))
    output=[]; cursor=0
    for start, end in expanded:
        output.append(_linked_text(source[cursor:start],current_id,names))
        output.append('<strong class="key-point">'+_linked_text(source[start:end],current_id,names)+'</strong>')
        cursor=end
    output.append(_linked_text(source[cursor:],current_id,names))
    return ''.join(output)


def _relation_list(term: dict[str, Any], available_ids: set[str] | None = None, available_names: dict[str, str] | None = None) -> str:
    relations = term.get("relations") or {}
    blocks = []
    labels = {"prerequisites": "先知道", "components": "组成部分", "contrasts": "容易混淆", "used_in": "用于何处", "next": "接下来"}
    for relation in labels:
        targets = [target for target in relations.get(relation, []) if available_ids is None or target in available_ids]
        if not targets:
            continue
        links = "".join(
            f'<li><a href="{_text(target)}.html">{_text((available_names or {}).get(target, target))}</a></li>'
            for target in targets
        )
        blocks.append(
            f'<section data-relation="{_text(relation)}"><h3>{labels[relation]}</h3>'
            f'<ul>{links}</ul></section>'
        )
    return "".join(blocks)


def render_practice_reading(term: dict[str, Any], names: dict) -> str:
    slug = str(term.get('id'))
    aid = reading_metadata().get(slug, {})
    emphasis = aid.get('body_emphasis', {})
    plain = str(term.get('plain_explanation') or '')
    plain_emphasis = [p for p in emphasis.get('plain_explanation', []) if p in plain]
    if not plain_emphasis and plain:
        plain_emphasis = [plain.split('。')[0]]
    blocks = [f'<a class="practice-open-link" href="terms/{_text(slug)}.html" data-expand-card="practice" aria-label="展开{_text(term.get("zh"))}的完整讲解"><h2>{_text(term.get("zh"))}</h2><span class="practice-expand-hint">展开完整讲解 ↗</span></a><p class="practice-term-en" lang="en">{_text(term.get("en"))}</p>',
              '<h3>通俗解释</h3><p>' + _reading_text(plain, slug, names, plain_emphasis) + ' ' + _linked_text(term.get('plain_example'), slug, names) + '</p>',
              '<h3>操作性定义</h3><p>' + _reading_text(term.get('operational_definition'), slug, names, emphasis.get('operational_definition')) + '</p>']
    for index, section in enumerate(term.get('sections', [])):
        blocks.append(f'<h3>{_text(section.get("heading") or section.get("h"))}</h3><p>' +
                      _reading_text(section.get('body') or section.get('md'), slug, names,
                                    section.get('emphasis') or aid.get('sections', {}).get(str(index), [])) + '</p>')
    for concept in term.get('concepts', []):
        blocks.append(f'<h3>{_text(concept["zh"])}</h3><p>' + _linked_text(concept['definition'], slug, names) + ' ' + _linked_text(concept.get('example'), slug, names) + '</p>')
    # Only concept links need the practice-page prefix; the header entry already has it.
    return ''.join(blocks).replace('href="', 'href="terms/').replace('href="terms/terms/', 'href="terms/')


def render_term(term: dict[str, Any], *, preview: bool, available_ids: set[str] | None = None, available_names: dict[str, str] | None = None, available_aliases: dict[str, list[str]] | None = None, available_concepts: dict[str, list[str]] | None = None, visual: dict[str, Any] | None = None, plain_visual: dict[str, Any] | None = None, formula_markup: str | None = None, topic_label: str = '', previous_term: dict | None = None, next_term: dict | None = None, analysis_examples: list[dict] | None = None) -> str:
    aid=reading_metadata().get(str(term.get('id')), {})
    names = {slug:[name, *(available_aliases or {}).get(slug, [])] for slug,name in (available_names or {}).items()}
    names.update(available_concepts or {})
    visual_html = ""
    if visual:
        mobile_source = (
            f'<source media="(max-width: 600px)" srcset="../assets/diagrams/{_text(visual["mobile_file"])}">'
            if visual.get("mobile_file") else ""
        )
        visual_html = (
            '<section class="term-visual"><h2>图解</h2><figure>'
            f'<div class="diagram-scroll"><picture>{mobile_source}'
            f'<img src="../assets/diagrams/{_text(visual.get("file"))}" '
            f'alt="{_text(visual.get("alt"))}" '
            f'width="{_text(visual.get("width"))}" height="{_text(visual.get("height"))}" loading="lazy">'
            '</picture></div>'
            f'<figcaption>{_text(visual.get("caption"))}</figcaption></figure></section>'
        )
    elif term.get("visual_steps"):
        steps = "".join(
            f'<li><strong>{_text(step.get("label"))}</strong>'
            f'<p>{_linked_text(step.get("detail"), str(term.get("id")), names)}</p></li>'
            for step in term["visual_steps"]
        )
        visual_html = f'<section class="term-flow"><h2>使用路径</h2><ol class="flow-steps">{steps}</ol></section>'
    plain_visual_html = ''
    if plain_visual and plain_visual.get('decision') != 'skip':
        if plain_visual['decision'] == 'reuse' and visual:
            # Move the existing image into the example; never show it twice.
            picture = visual_html.split('<figure>', 1)[1].rsplit('</figure>', 1)[0]
            picture = picture.replace('<figcaption>', '<p class="reused-diagram-note">').replace('</figcaption>', '</p>')
            picture = f'<div class="term-visual">{picture}</div>'
            visual_html = ''
        elif plain_visual['decision'] == 'draw':
            from .plain_visuals import dimensions
            width, height = dimensions(plain_visual)
            slug = str(term['id'])
            picture = (f'<picture><source media="(max-width: 600px)" srcset="../assets/examples/{_text(slug)}-mobile.svg">'
                       f'<img src="../assets/examples/{_text(slug)}.svg" width="{width}" height="{height}" '
                       f'alt="{_text(plain_visual["title"]+"。"+plain_visual["takeaway"])}" loading="lazy"></picture>')
        else:
            picture = ''
        if picture:
            basis = '教学合成数据 · 非真实研究结果' if plain_visual.get('basis') == 'synthetic' else '概念示意 · 不代表实际测量结果'
            if plain_visual['decision'] == 'reuse':
                basis = '结合本页教学例子阅读'
            notes = ''.join(f'<div><dt>{label}</dt><dd>{_linked_text(plain_visual[field], str(term.get("id")), names)}</dd></div>'
                            for field, label in [('read','先看哪里'),('takeaway','说明什么'),('limit','不能说明什么')])
            caption = f'<dl>{notes}</dl>'
            figure_class = 'plain-example-visual'
            if plain_visual.get('narrative'):
                figure_class += ' illustrated-example'
                caption = ''.join(f'<p class="figure-narrative">{_linked_text(p, str(term.get("id")), names)}</p>' for p in plain_visual['narrative'])
                caption += f'<p class="figure-caution"><strong>注意</strong> {_linked_text(plain_visual["caution"], str(term.get("id")), names)}</p>'
            plain_visual_html = (f'<figure class="{figure_class}"><h3>{_text(plain_visual["title"])}</h3>'
                                 f'{picture}<figcaption><span class="example-basis">{basis}</span>{caption}</figcaption></figure>')
    section_parts = "".join(
        f'<section class="explanation-part"><h3>{_text(section.get("heading") or section.get("h"))}</h3>'
        f'<p>{_reading_text(section.get("body") or section.get("md"), str(term.get("id")), names, section.get("emphasis") or aid.get("sections",{}).get(str(index),[]))}</p></section>'
        for index,section in enumerate(term.get("sections", []))
        if isinstance(section, dict)
    )
    sections = f'<section class="detailed-explanation"><h2>详细讲解</h2>{section_parts}</section>' if section_parts else ""
    plain_text = " ".join(str(term.get(key) or "").strip() for key in ("plain_explanation", "plain_example")).strip()
    plain_emphasis = [p for p in aid.get('body_emphasis',{}).get('plain_explanation',[]) if p in plain_text]
    if not plain_emphasis and term.get('plain_explanation'):
        plain_emphasis = [str(term['plain_explanation']).split('。')[0]]
    formula = term.get("formula") or {}
    formula_html = ""
    if str(formula.get("latex", "")).strip():
        _,symbols=formula_aid(formula['latex'],str(term.get('id')),str(formula.get('note') or ''))
        keys=''.join(f'<li id="meaning-{entry["key"]}" class="formula-row" data-symbol="{entry["key"]}"><button type="button" class="formula-key" data-symbol="{entry["key"]}" data-token="{_text(entry["token"])}" aria-pressed="false" aria-describedby="description-{entry["key"]}"><span class="symbol-label">{_text(entry["label"])}<span class="symbol-state" aria-hidden="true">常亮</span></span></button><span class="formula-description" id="description-{entry["key"]}">{_linked_text(entry["meaning"], str(term.get("id")), names)}</span></li>' for entry in symbols)
        logic=aid.get('formula_logic') or '按式中顺序辨认目标量与输入，再理解括号、求和和运算如何组合；下方条件决定该公式能否用于你的数据。'
        formula_html = (
            '<section class="formula"><h2>公式</h2>'
            + (f'<div class="formula-display">{formula_markup}</div>' if formula_markup else f'<pre><code>{_text(formula.get("latex"))}</code></pre>')
            + '<p class="formula-hint">悬停即可操作，无需先点击：<kbd>Enter</kbd> / <kbd>空格</kbd> 切换常亮，可同时保留多个；<kbd>Tab</kbd> / <kbd>Shift+Tab</kbd> 顺序阅读；<kbd>Esc</kbd> 清除常亮。也可直接点选符号或解释。</p>'
            + f'<ol class="formula-keys">{keys}</ol><p class="formula-logic">{_text(logic)}</p>'
            + f'<p>{_linked_text(formula.get("note"), str(term.get("id")), names)}</p></section>'
        )
    r_practice = term.get("r_practice")
    r_html = ""
    if isinstance(r_practice, dict):
        example = r_practice.get("example_code", "")
        own = r_practice.get("your_data_code", "")
        csv_names = sorted(set(re.findall(r'read\.csv\("([A-Za-z0-9_]+\.csv)"', example)))
        downloads = "".join(f'<li><a href="../data/{_text(name)}" download>{_text(name)}</a></li>' for name in csv_names)
        dataset_html = f'<p>先下载教学用合成数据，并把 CSV 放在 R 当前工作目录：</p><ul>{downloads}</ul>' if downloads else "<p>此示例直接模拟数据，无需下载 CSV。</p>"
        package_html = '<p>软件包：' + _text('、'.join(r_practice.get('packages', [])) or 'R 基础功能') + '。缺少包时先使用 install.packages("包名") 安装；自己的数据模板需替换列名，尚未在你的数据上验证。</p>'
        checks = "".join(f"<li>{_text(check)}</li>" for check in r_practice.get("assumption_checks", []))
        checks_html = f'<h3>运行前检查</h3><ul>{checks}</ul>' if checks else ""
        interpretation = r_practice.get("interpretation", "")
        body_aid=aid.get('body_emphasis',{})
        interpretation_html = f'<h3>如何理解输出</h3><p class="output-interpretation">{_reading_text(interpretation, str(term.get("id")), names, body_aid.get("interpretation",[]))}</p>' if interpretation else ""
        report_template = str(r_practice.get('report_template') or '').strip()
        report_example = str(aid.get('report_example') or r_practice.get('report_example') or '').strip()
        report_html = ''
        if report_template or report_example:
            report_html = '<h3>研究结果怎么写</h3>'
            if report_template:
                report_html += f'<p>{_reading_text(report_template, str(term.get("id")), names, body_aid.get("report_template",[]))}</p>'
            if report_example:
                report_html += f'<aside class="report-example" aria-label="教学数据报告示例"><h4>教学数据报告示例</h4><p>{_reading_text(report_example, str(term.get("id")), names, body_aid.get("report_example",[]))}</p><p class="report-example-note">本段使用教学数据示范报告格式。撰写论文时，请使用自己的研究设计与分析结果。</p></aside>'
        report_limits = r_practice.get('report_limits') or []
        if report_limits:
            checks_html += '<div class="practice-interpretation-checks"><h3>使用与解释时的检查</h3><ul>' + ''.join(f'<li>{_reading_text(limit, str(term.get("id")), names, body_aid.get("report_limits",[]))}</li>' for limit in report_limits) + '</ul></div>'
        r_html = (
            '<section class="r-practice"><h2>怎么实操</h2>'
            f'{dataset_html}{package_html}{checks_html}'
            '<div class="tabs" role="tablist"><button data-tab="example">可直接运行的示例</button>'
            '<button data-tab="your-data">换成你的数据</button></div>'
            f'<div class="tab-panel" data-panel="example"><button data-copy="#r-example">复制代码</button><pre id="r-example"><code class="language-r">{escape(str(example), quote=True)}</code></pre></div>'
            f'<div class="tab-panel" data-panel="your-data" hidden><button data-copy="#r-your-data">复制代码</button><pre id="r-your-data"><code class="language-r">{escape(str(own), quote=True)}</code></pre></div>{interpretation_html}{term.get("paper_result_html", "")}{report_html}</section>'
        )
        prompt=aid.get('agent_prompt','')
        if prompt:
            agent_html=('<div class="agent-brief"><div class="agent-brief-head"><h3>你可以这样告诉 AI Agent</h3>'
                        '<button type="button" data-copy="#agent-prompt">复制提示</button></div>'
                        f'<p id="agent-prompt">{_text(prompt)}</p><p class="agent-caution">请先脱敏；这是给外部 Agent 的提示，本网站不上传数据、不执行分析。</p></div>')
            r_html=r_html.replace('<div class="tabs"',agent_html+'<div class="tabs"',1)
    quiz = term.get("quiz") or {}
    option_explanations = quiz.get("option_explanations") or []
    options = "".join(
        f'<div class="quiz-option"><button class="opt" type="button" data-idx="{index}" aria-pressed="false">{_text(option)}</button>'
        f'<p class="option-feedback" hidden>{_text(option_explanations[index] if index < len(option_explanations) else quiz.get("explanation", ""))}</p></div>'
        for index, option in enumerate(quiz.get("options", []))
    )
    quiz_html = ""
    if options:
        quiz_html = f'<section class="quiz-card"><h2>选择题</h2><div class="quiz" data-answer="{_text(quiz.get("answer"))}"><p>{_text(quiz.get("question"))}</p>{options}<p class="quiz-result" role="status" aria-live="polite"></p></div></section>'
    sources = ""
    for source in term.get("sources", []):
        if not isinstance(source, dict):
            continue
        title = _text(source.get("title"))
        url = str(source.get("url") or "")
        if re.match(r"https?://", url):
            title = f'<a href="{_text(url)}" target="_blank" rel="noopener noreferrer">{title}</a>'
        role = f'<span class="source-role"> · {_text(source["role"])}</span>' if source.get("role") else ""
        sources += f'<li>{title}{role}</li>'
    relation_html = _relation_list(term, available_ids, available_names)
    sidebar = f'<aside class="knowledge-sidebar"><h2>知识关系</h2>{relation_html}</aside>' if relation_html else ""
    layout_class = "term-layout" if relation_html else "term-layout term-layout--single"
    breadcrumb = (f'<nav class="breadcrumb" aria-label="当前位置"><a href="../index.html">术语</a>'
                  f'<a href="../index.html?topic={_text(term.get("topic"))}" data-collapse-term="{_text(term.get("id"))}">{_text(topic_label or term.get("topic"))}</a>'
                  f'<span class="breadcrumb-current" aria-current="page">{_text(term.get("zh"))}</span></nav>')
    neighbors = ''.join(f'<a class="sequence-link sequence-{direction}" data-direction="{direction}" href="{_text(item["id"])}.html" aria-label="{_text(label)}：{_text(item["zh"])}">'
                        f'<span aria-hidden="true" class="sequence-arrow"><svg viewBox="0 0 28 16" width="28" height="16" fill="none" focusable="false"><path d="M27 8H1M8 1L1 8L8 15" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg></span><span>{_text(item["zh"])}</span></a>'
                        for direction,label,item in [('previous','← 上一术语',previous_term),('next','下一术语 →',next_term)] if item)
    concept_html = ''.join(f'<section class="explanation-part" id="{_text(item["id"])}"><h3>{_text(item["zh"])}</h3><p>{_linked_text(item["definition"],str(term["id"]),names)}</p><p>{_linked_text(item.get("example"),str(term["id"]),names)}</p></section>' for item in term.get('concepts',[]))
    if concept_html: sections += f'<section class="concept-definitions"><h2>{_text(term.get("concept_heading") or "相关概念怎么理解")}</h2>{concept_html}</section>'
    analysis_html = ''
    if analysis_examples:
        tutorial_links = ''.join(f'<li><a class="inline-term" href="../analyses/{_text(c["id"])}.html">{_text(c["title"])} ⟶</a></li>' for c in analysis_examples)
        analysis_html = '<section class="analysis-crosslinks"><h2>看完整分析示例</h2><p>不同教学问题可能采用不同数据或模型；请以对应示例实际运行的输出为准，不混用两份案例的数字。</p><ul>'+tutorial_links+'</ul></section>'
    body = (
        f'<div class="{layout_class}"><article class="term-content" data-topic="{_text(term.get("topic"))}" data-term-id="{_text(term.get("id"))}"><header><h1>{_text(term.get("zh"))}</h1>'
        f'<p lang="en">{_text(term.get("en"))}</p>{breadcrumb}{_favorite_button(term)}</header>'
        '<section class="real-question"><h2><span class="question-quote" aria-hidden="true">“</span>你可能会问</h2>'
        f'<p>{_text(term.get("real_question"))}</p></section>'
        '<section><h2>操作性定义</h2>'
        f'<p>{_reading_text(term.get("operational_definition"), str(term.get("id")), names, aid.get("body_emphasis",{}).get("operational_definition",[]))}</p></section>'
        '<section><h2>通俗解释</h2>'
        f'<p>{_reading_text(plain_text, str(term.get("id")), names, plain_emphasis)}</p>{plain_visual_html}</section>{visual_html}'
        f'{sections}{formula_html}{r_html}{analysis_html}{quiz_html}<section><h2>出处</h2><ul>{sources}</ul></section></article>'
        f'{sidebar}<nav class="term-sequence" aria-label="按术语列表顺序阅读">{neighbors}</nav></div>'
    )
    return page_shell(
        f"{term.get('zh', '')} | 心理统计学术语图鉴",
        body,
        root="../",
    )


def render_topic(topic: dict[str, Any], terms: list[dict[str, Any]], *, topics: list[dict[str,Any]] | None = None, preview: bool = False) -> str:
    target='../index.html?topic='+str(topic['id'])
    body=f'<section class="page-head"><h1>主题已合并到术语主界面</h1><p><a href="{_text(target)}">查看{_text(topic["zh"])}</a></p></section>'
    page=page_shell(str(topic['zh']),body,root='../')
    redirect=f'<meta http-equiv="refresh" content="0;url={_text(target)}"><script>location.replace({json.dumps(target)});</script>'
    return page.replace('</head>',redirect+'</head>')


def _render_learning_network(network: dict[str,Any], terms_by_id: dict[str,dict[str,Any]]) -> str:
    def links(ids):
        return '<ul class="map-term-links">'+''.join(
            f'<li><a href="terms/{_text(slug)}.html">{_text(terms_by_id[slug]["zh"])}</a></li>'
            for slug in ids if slug in terms_by_id)+'</ul>'
    foundation=''.join(f'<li><h3>{_text(node["title"])}</h3>{links(node["terms"])}</li>' for node in network['foundation'])
    directions=network['directions']
    labels={d['id']:d['title'] for d in directions}
    overview=''.join(f'<a class="map-direction-link" href="#direction-{_text(d["id"])}" data-topic="{_text(d["topic"])}">'
                     f'<strong>{_text(d["title"])}</strong><span>{_text(d["question"])}</span></a>' for d in directions)
    branches=[]
    for direction in directions:
        steps=''.join(f'<li><span class="map-step-label">第 {i} 步</span><h3>{_text(step["title"])}</h3>'
                      f'<p>{_text(step["detail"])}</p>{links(step["terms"])}</li>' for i,step in enumerate(direction['stages'],1))
        connections=''.join(f'<li><a class="map-cross-link" href="#direction-{_text(edge["target"])}">'
                            f'{_text(labels[edge["target"]])}</a><p>{_text(edge["label"])}</p>{links(edge["terms"])}</li>' for edge in direction.get('connections',[]))
        branches.append(f'<details class="direction-map" id="direction-{_text(direction["id"])}" data-topic="{_text(direction["topic"])}">'
                        f'<summary><span><strong>{_text(direction["title"])}</strong><span class="direction-question">{_text(direction["question"])}</span></span>'
                        '<span class="map-expand-hint">展开学习链</span></summary>'
                        f'<div class="direction-map-body"><p><a href="index.html?topic={_text(direction["topic"])}">进入对应术语主题</a> · '
                        '<a href="#shared-foundation">返回共同基础</a></p>'
                        f'<ol class="direction-stages">{steps}</ol>'
                        f'<section class="map-connections"><h3>与其他方向共享的知识</h3><ul>{connections}</ul></section></div></details>')
    body=('<section class="page-head"><h1>心理统计学习导图</h1>'
          '<p>从共同基础出发，按研究目标选择分支；方法之间通过共享知识连接。</p></section>'
          '<section class="learning-network" aria-label="研究方向与学习顺序">'
          '<section id="shared-foundation" class="map-foundation"><h2>共同基础</h2>'
          f'<ol class="foundation-stages">{foundation}</ol></section>'
          '<div class="map-branch-stem" aria-hidden="true"><span>按研究目标分支</span></div>'
          f'<nav class="map-directions" aria-label="选择研究方向">{overview}</nav>'
          '<p class="map-legend">箭头表示建议学习顺序，不表示因果关系；跨方向链接表示共享知识。'
          '展开某个方向查看方法与诊断，点击术语阅读解释和 R 示例。</p>'
          f'<div class="direction-branches">{"".join(branches)}</div></section>')
    return page_shell('学习路径 | 心理统计学术语图鉴',body,active_nav='paths')


def render_paths(paths: list[dict[str, Any]], terms_by_id: dict[str, dict[str, Any]], *, network: dict[str,Any] | None = None) -> str:
    if network:
        return _render_learning_network(network,terms_by_id)
    cards = []
    for path in paths:
        steps = []
        for index, step in enumerate(path.get("steps", []), 1):
            links = "".join(
                (f'<li><a href="terms/{_text(term_id)}.html">{_text(terms_by_id[term_id].get("zh", term_id))}</a></li>'
                 if term_id in terms_by_id else f'<li><span>{_text(term_id)}（尚未发布）</span></li>')
                for term_id in step.get("terms", [])
            )
            steps.append(
                f'<article class="path-step"><span>第 {index} 步</span><h3>{_text(step.get("title"))}</h3>'
                f'<p><strong>前置：</strong>{_text(step.get("prerequisite"))}</p>'
                f'<p><strong>目标：</strong>{_text(step.get("goal"))}</p><ul>{links}</ul></article>'
            )
        cards.append(
            f'<section class="path-card"><h2>{_text(path.get("title"))}</h2>'
            f'<p>{_text(path.get("description"))}</p><div class="path-steps">{"".join(steps)}</div></section>'
        )
    body = '<section class="page-head"><h1>学习路径</h1><p>按目标选择路径；每一步只保留关键节点。</p></section>' + "".join(cards)
    return page_shell("学习路径 | 心理统计学术语图鉴", body, active_nav="paths")


def render_datasets(datasets: list[dict[str, Any]]) -> str:
    cards = []
    for dataset in datasets:
        uses = "".join(f'<span class="tag">{_text(item)}</span>' for item in dataset.get("suitable_for", []))
        if dataset.get("download"):
            action = f'<a class="button" href="{_text(dataset["download"])}">下载 CSV</a>'
        else:
            action = '<span class="planned">计划中</span>'
        cards.append(
            f'<article class="dataset-card"><h2>{_text(dataset.get("title"))}</h2>'
            f'<p>{_text(dataset.get("scenario"))}</p><div class="tags">{uses}</div>{action}</article>'
        )
    body = '<section class="page-head"><h1>示例数据</h1><p>所有数据均为教学合成数据，不作为真实心理学证据。</p></section><section class="dataset-list">' + "".join(cards) + "</section>"
    return page_shell("示例数据 | 心理统计学术语图鉴", body, active_nav="datasets")


def render_sources(policy: dict[str, Any]) -> str:
    sources = "".join(
        f'<article><h3>{_text(source.get("title"))}</h3><p>{_text(source.get("role"))}</p></article>'
        for source in policy.get("sources", [])
    )
    rules = "".join(f'<li>{_text(item)}</li>' for item in policy.get("review_rules", []))
    boundaries = "".join(f'<li>{_text(item)}</li>' for item in policy.get("boundaries", []))
    body = (
        f'<section class="page-head"><h1>{_text(policy.get("title"))}</h1><p>版本：{_text(policy.get("version"))}</p></section>'
        f'<section><h2>来源分工</h2>{sources}</section><section><h2>审核规则</h2><ul>{rules}</ul></section>'
        f'<section><h2>使用边界</h2><ul>{boundaries}</ul></section>'
    )
    return page_shell("来源说明 | 心理统计学术语图鉴", body, active_nav="sources")


def render_practice() -> str:
    body = ('<section class="page-head"><h1>全站练习</h1></section>'
            '<section id="practice-app" data-quiz-src="assets/data/quiz-bank.json">'
            '<p class="empty-state">正在载入题库……</p></section>')
    return page_shell("全站练习 | 心理统计学术语图鉴", body, active_nav="practice")
