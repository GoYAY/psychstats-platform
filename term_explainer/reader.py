"""Safe, static personal teaching pages. No model HTML is executed."""
from dataclasses import asdict
from html import escape
from pathlib import Path
import json
import shutil
from .inline_glossary import InlineGlossary,classic_catalogue
from .contract import used_source_ids


def _prose(paragraph,glossary=None):
    if glossary:
        return '<p>'+glossary.render(paragraph['text'],paragraph.get('emphasis',[]))+'</p>'
    text=escape(paragraph['text'])
    for emphasis in sorted(set(paragraph.get('emphasis',[])),key=len,reverse=True):
        text=text.replace(escape(emphasis),'<strong>'+escape(emphasis)+'</strong>')
    return '<p>'+text+'</p>'


def render_lesson(result,figures=None,*,sources=(),catalog=()):
    data=asdict(result) if not isinstance(result,dict) else result
    if not data['term'].get('en') and (data.get('provenance',{}).get('verified_identity') or {}).get('en'):
        from copy import deepcopy
        data=deepcopy(data);data['term']['en']=data['provenance']['verified_identity']['en']
    e=lambda value:escape(str(value),quote=True)
    by_block={b['id']:b for b in data['blocks']}
    glossary=InlineGlossary(data.get('glossary',[]),catalog,data['term'])
    sections=[]; nav=[]
    for key in ('real_question','operational_definition','plain_explanation','detailed_explanation','how_to_use','academic_expression'):
        block=by_block.get(key)
        if not block: continue
        title='你可能会问' if key=='real_question' else block['heading']
        nav.append(f'<a href="#{key}">{e(title)}</a>')
        body_glossary=glossary if key in {'operational_definition','plain_explanation','detailed_explanation','how_to_use'} else None
        sections.append(f'<section id="{key}" class="{"question" if key=="real_question" else "reading-block"}"><h2>{"❝ " if key=="real_question" else ""}{e(title)}</h2>'+''.join(_prose(p,body_glossary) for p in block['paragraphs'])+'</section>')
        if key=='plain_explanation' and figures:
            visual=data['visual']
            sections.append(f'<figure><picture><source media="(max-width: 650px)" srcset="figures/{Path(figures.mobile).name}"><img src="figures/{Path(figures.desktop).name}" alt="{e(figures.alt)}"></picture><figcaption><b>{e(visual["title"])}</b> · {e(visual["takeaway"])}<small>{"教学示意" if visual["origin"] in ("conceptual","teaching") else "依据原文绘制"}</small></figcaption></figure>')
    if data.get('formulas'):
        bits=[]
        for i,f in enumerate(data['formulas']):
            bits.append(f'<div class="formula"><div class="math" data-latex="{e(f["latex"])}">{e(f["latex"])}</div><dl>'+''.join(f'<div><dt class="symbol-math" data-latex="{e(s["symbol"])}">{e(s["symbol"])}</dt><dd>{e(s["meaning"])}</dd></div>' for s in f['symbols'])+'</dl></div>')
        position=next((i+1 for i,s in enumerate(sections) if s.startswith('<section id="detailed_explanation"')),len(sections))
        sections.insert(position,'<section id="formulas"><h2>公式与符号</h2>'+''.join(bits)+'</section>')
        nav_position=next((i+1 for i,s in enumerate(nav) if '#detailed_explanation' in s),len(nav))
        nav.insert(nav_position,'<a href="#formulas">公式与符号</a>')
    if data.get('limitations'):
        sections.append('<section id="evidence-scope" class="reading-block"><h2>现有证据的范围</h2>'+''.join('<p>'+e(n['text'])+'</p>' for n in data['limitations'])+'</section>')
        nav.append('<a href="#evidence-scope">现有证据的范围</a>')
    quiz=data.get('quiz')
    if quiz:
        buttons=''.join(f'<button class="quiz-option" type="button" data-option="{e(o["id"])}">{e(o["id"].upper())} · {e(o["text"])}</button>' for o in quiz['options'])
        # Escaping '<' prevents script closing, even if it occurs inside user/model strings.
        quiz_json=json.dumps(quiz,ensure_ascii=False).replace('<','\\u003c')
        sections.append('<section id="quiz" class="quiz"><h2>检验理解</h2><h3>'+e(quiz['question'])+'</h3>'+buttons+'<p id="quiz-feedback" role="status" aria-live="polite"></p><script type="application/json" id="quiz-data">'+quiz_json+'</script></section>')
        nav.append('<a href="#quiz">检验理解</a>')
    catalogue={t['id']:t for t in catalog}
    related=[]
    for relation in data.get('relations',[]):
        term=catalogue.get(relation['target'],{})
        label=term.get('zh',relation['target'])
        href=glossary.url(relation['target'])
        if href: label=f'<a href="{e(href)}">{e(label)}</a>'
        else: label=e(label)+'<small>待补充</small>'
        related.append('<li>'+label+'<p>'+e(relation['reason'])+'</p></li>')
    # Raw passages, offsets and reference metadata remain in private knowledge data,
    # never in hidden markup or the browser's note dictionary.
    used=used_source_ids(data)
    seen_titles=set(); seen_dois=set(); titles=[]
    for source in sources:
        if source.get('scope')=='metadata' or (source.get('id') and source['id'] not in used):continue
        title=source.get('title') or '未命名文献'
        title_key=''.join(title.split()).casefold(); doi=(source.get('doi') or '').strip().casefold()
        if title_key not in seen_titles and (not doi or doi not in seen_dois): titles.append('<li>'+e(title)+'</li>')
        seen_titles.add(title_key)
        if doi: seen_dois.add(doi)
    sections.append('<section id="sources"><h2>来源与核对</h2><ul>'+''.join(titles)+'</ul></section>')
    sections.append(glossary.markup())
    status='AI 生成 · 请结合原文核对' if data['status']=='complete' else '资料待补充 · 当前内容不完整'
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+e(data['term']['zh'])+' · 我的知识库</title><link rel="stylesheet" href="reader.css"><link rel="stylesheet" href="glossary.css"><link rel="stylesheet" href="vendor/katex/katex.min.css"><script defer src="vendor/katex/katex.min.js"></script><script defer src="reader.js"></script><script defer src="glossary.js"></script></head><body><header><a class="brand" href="https://cdst.site/psy-stats/index.html">心理统计学术语图鉴</a><span>我的知识库</span></header><div class="layout"><main><div class="title"><small>'+status+'</small><h1>'+e(data['term']['zh'])+'</h1><p class="english">'+e(data['term'].get('en',''))+'</p></div>'+''.join(sections)+'</main><aside><nav aria-label="本页导航">'+''.join(nav)+'</nav><h2>知识关联</h2><ul>'+''.join(related)+'</ul></aside></div><footer>个人本地生成内容 · 不含软件实操代码 · 图示为教学辅助</footer></body></html>'


def build_preview(result,figures,output_dir,*,sources=(),catalog=()):
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    available={t['id']:t for t in catalog}
    available.update({t['id']:t for t in classic_catalogue()})
    assets=Path(__file__).parent/'assets'
    for name in ('reader.css','reader.js','glossary.css','glossary.js'): shutil.copyfile(assets/name,output_dir/name)
    vendor=Path(__file__).resolve().parents[1]/'site/assets/vendor/katex'
    shutil.copytree(vendor,output_dir/'vendor/katex',dirs_exist_ok=True)
    (output_dir/'index.html').write_text(render_lesson(result,figures,sources=sources,catalog=list(available.values())),encoding='utf-8')
    return output_dir/'index.html'
