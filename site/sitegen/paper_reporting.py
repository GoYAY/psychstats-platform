"""Paper-style views of actual saved results; no statistical execution at build time."""
from __future__ import annotations
import hashlib
import json
import math
import re
from html import escape
from pathlib import Path
from .statistical_display import format_p, format_number, is_p_column, is_p_field, significant_columns, governing_p
from .paper_summaries import method_results, metric_summary

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    'lhs':'左侧变量', 'op':'关系', 'rhs':'右侧变量 / 指标', 'est':'参数估计',
    'estimate':'效应 / 参数估计', 'Estimate':'b', 'se':'SE', 'Std. Error':'SE',
    'ci.lower':'95% CI 下限', 'ci.upper':'95% CI 上限', 'ci_lower':'95% CI 下限',
    'ci_upper':'95% CI 上限','std.all':'全标准化参数', 'std.lv':'潜变量标准化',
    'pvalue':'p','p':'p','Pr(>|t|)':'p','t value':'t','z':'z','df':'df',
    'term':'参数','outcome':'结果变量','effect':'效应 / 检验','n':'n','N':'N',
    'label':'路径标记','index':'拟合指标','value':'数值','statistic':'t / 检验值',
    'r_squared':'R²','adjusted_r_squared':'调整 R²','slope':'简单斜率 b',
    'mean':'均值','sd':'SD','OR':'OR','d_z':'配对 Cohen dz','t':'t','model':'模型',
    'support_centered':'支持水平（中心化）','f2_marker_units':'调节变量水平（标记单位）',
    'probability':'概率','class':'类别','cluster':'组别','group':'组别',
}
TABLE_NAMES = {'parameters':'模型参数与效应','coefficients':'回归系数',
    'path_coefficients':'各段路径系数','model_summary':'模型解释率与样本量',
    'simple_slopes':'条件简单斜率','conditional_effects':'条件间接效应与调节中介指数',
    'interaction_effects':'间接与直接交互效应','fit':'模型拟合',
    'posthoc':'事后比较','profiles':'类别画像','loadings':'载荷矩阵',
    'confusion':'分类混淆矩阵','metrics':'主要结果与效应记录',
    'console_coefficients':'软件打印的回归系数','effect_summary':'主要效应及区间'}
TABLE_NAMES.update(reported_coefficients='回归系数及区间',odds_ratios='优势比及区间',
    standardized_profiles='标准化类别画像',standardized_effects='标准化效应量',
    descriptives='研究变量的描述统计',group_descriptives='各组描述统计',paired_change='配对变化及效应量',
    explained_variance='各结果变量与指标的解释率')
VARIABLES = {'stress':'压力','social_support':'社会支持','well_being':'幸福感',
    'x':'X','w':'W','x:w':'X × W','m':'M','y':'Y','f1':'F1','f2':'F2','f3':'F3',
    'interaction':'F1 × F2','(Intercept)':'截距','indirect':'间接效应',
    'total':'总效应','at_zero':'W = 0 的间接效应','at_low':'W = −1 的间接效应',
    'at_high':'W = +1 的间接效应','index':'调节中介指数',
    'support':'社会支持','sleep':'睡眠','wellbeing':'幸福感','i':'截距因子','s':'斜率因子',
    'retrieval':'练习回忆组（retrieval）','control':'对照组（control）'}
DESCRIPTIVE_HEADERS = {'variable':'研究变量','group':'组别',
    'n':'有效样本量 <em>n</em>','mean':'均值 <em>M</em>','sd':'标准差 <em>SD</em>',
    'median':'中位数 <em>Mdn</em>','iqr':'四分位距 <em>IQR</em>'}
DESCRIPTIVE_FIELDS = ('n','mean','sd','median','iqr')
CORE_FIT = {'chisq','df','pvalue','cfi','tli','rmsea','rmsea.ci.lower','rmsea.ci.upper',
    'srmr','aic','bic','chisq.scaled','df.scaled','pvalue.scaled','cfi.robust','tli.robust',
    'rmsea.robust','rmsea.ci.lower.robust','rmsea.ci.upper.robust'}

PRIMARY_ESTIMATES = {'correlation':('r','Pearson r'), 'linear':('beta','压力的回归系数 b'),
    'linear-simple':('slope','压力的回归系数 b'), 'logistic':('odds_ratio','睡眠时长的 OR'),
    't-tests':('difference','组间均值差'), 't-single':('mean','样本均值'),
    'intervals':('estimate','总体均值估计'), 'intervals-variance':('variance','总体方差估计'),
    'equivalence':('difference','组间均值差'), 'contrasts':('difference','计划对比'),
    'sampling':('mean','分层加权均值'), 'sampling-cluster':('mean','整群抽样均值'),
    'proportions':('difference','两组比例差'), 'diagnostics':('beta','压力系数（HC3 区间）'),
    'missing':('pooled','多重插补合并系数'), 'mediation':('indirect','间接效应 a × b'),
    'latent-mediation':('indirect','潜变量间接效应 a × b'),
    'conditional-mediation':('index','调节中介指数 a3 × b'),
    'mediated-interaction':('indirect','间接交互效应 a3 × b')}


def console_coefficients(console):
    """Recover printed lm/glm coefficients at their actual console precision."""
    rows=[]; active=False; model=0
    number=r'[<>]?\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?'
    for line in console.splitlines():
        if 'Estimate' in line and 'Std. Error' in line and 'Pr(' in line:
            active=True; model+=1; continue
        if not active: continue
        match=re.match(r'^\s*(\S+)\s+('+number+r')\s+('+number+r')\s+('+number+r')\s+('+number+r')',line,re.I)
        if match:
            values=match.groups()
            # A printed inequality is retained as an inequality, never an exact p.
            p=values[4].strip()
            rows.append({'model':model,'term':values[0],'Estimate':float(values[1]),
                'Std. Error':float(values[2]),'statistic':float(values[3]),
                'p':p if p.startswith(('<','>')) else float(p)})
        elif rows: active=False
    return rows


def supplement(slug):
    path = ROOT / 'content/paper_results' / (slug+'.json')
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding='utf-8'))
    original = ROOT / 'content/analysis_results' / (slug+'.json')
    extractor = ROOT.parent / 'examples/r/output_reading/_paper_supplement.R'
    if value['original_sha256'] != hashlib.sha256(original.read_bytes()).hexdigest() or value['extractor_sha256'] != hashlib.sha256(extractor.read_bytes()).hexdigest():
        raise ValueError('stale paper supplement: '+slug)
    return value


def prediction_supplement(slug):
    path = ROOT / 'content/prediction_results' / (slug + '.json')
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding='utf-8'))
    original = ROOT / 'content/analysis_results' / (slug + '.json')
    extractor = ROOT.parent / 'examples/r/output_reading/_prediction_supplement.R'
    if value['original_sha256'] != hashlib.sha256(original.read_bytes()).hexdigest() or value['extractor_sha256'] != hashlib.sha256(extractor.read_bytes()).hexdigest():
        raise ValueError('stale prediction supplement: ' + slug)
    return value


def paper_data(case, result):
    extra = supplement(case['id'])
    prediction = prediction_supplement(case['id'])
    original_tables = result.get('tables') if isinstance(result.get('tables'),dict) else {}
    merged = {**original_tables, **extra.get('tables',{})}
    if not any(key in merged for key in ('parameters','coefficients','path_coefficients')):
        printed=console_coefficients(result.get('stdout',''))
        if printed: merged['console_coefficients']=printed
    tables = []
    primary=PRIMARY_ESTIMATES.get(case['id']); m=result['metrics']
    descriptive_fields = DESCRIPTIVE_FIELDS if case['id']=='describe' else ()
    method_table=method_results(case,result)
    if method_table:
        tables.append(method_table)
    if descriptive_fields and 'descriptives' not in merged:
        merged = {'descriptives':[{'variable':'压力分数（stress）',
            **{key:m[key] for key in descriptive_fields}}], **merged}
    if not method_table and primary and all(k in m for k in (primary[0],'ci_lower','ci_upper')):
        row={'effect':primary[1],'estimate':m[primary[0]],'ci_lower':m['ci_lower'],'ci_upper':m['ci_upper']}
        for key in ('n','se','df','t','p'):
            if key in m:row[key]=m[key]
        if case['id']=='diagnostics':row['se']=m['hc3_se']
        if case['id']=='equivalence':row['p']=m['tost_p']
        tables.append({'name':'effect_summary','title':'主要效应及区间',
                       'columns':list(row),'rows':[row]})
    for name, rows in merged.items():
        if name in {'dendrogram_merges','leaf_order'} or not isinstance(rows,list) or not rows or not isinstance(rows[0],dict):
            continue
        if name == 'fit':
            rows = [r for r in rows if r.get('index') in CORE_FIT] or rows
            row={'model':case['title'], **{r['index']:r.get('value') for r in rows}}
            tables.append({'name':name,'title':'模型拟合指标','columns':list(row),'rows':[row]})
            continue
        if name in {'coefficients','console_coefficients'} and 'reported_coefficients' in merged:
            continue
        if name == 'group_descriptives' and case['id'] == 't-tests':
            rows = [{'variable':'成绩增量（gain）', **row} for row in rows]
        if name == 'model_summary' and not any(k in rows[0] for k in ('model','outcome','group')):
            rows = [{'model':case['title'], **row} for row in rows]
        columns = list(dict.fromkeys(k for row in rows for k in row if k != '_row'))
        # Exclude redundant labels only; retain every estimate, uncertainty and test.
        if 'std.lv' in columns and 'std.all' in columns:
            columns.remove('std.lv')
        tables.append({'name':name,'title':case.get('table_labels',{}).get(name,TABLE_NAMES.get(name,name)),
                       'columns':columns,'rows':rows})
    metrics = [{'effect':a['label'], 'value':result['metrics'][a['field_id']],
                'field_id':a['field_id']} for a in case.get('annotations',[]) if a['field_id'] in result['metrics']]
    known={r['field_id'] for r in metrics}
    metrics.extend({'effect':LABELS.get(k,VARIABLES.get(k,k)),'value':v,'field_id':k}
                   for k,v in result['metrics'].items() if k not in known)
    metrics = [row for row in metrics if row['field_id'] not in descriptive_fields]
    if metrics and not method_table:
        tables.append(metric_summary(case,metrics))
    if not tables:
        tables.append({'name':'diagnostic','title':'诊断记录','columns':['说明'],
                       'rows':[{'说明':case.get('invalid_reason','本例未形成可报告的参数结果')} ]})
    paths = []
    for row in merged.get('parameters',[]):
        if row.get('op') != '~':
            continue
        label = row.get('label') or ''
        if case['id'] in {'mediation','latent-mediation'} and label == 'c': label = 'c′'
        paths.append({'source':row['rhs'],'target':row['lhs'],'label':label,
                      'estimate':row['est'],'p':row.get('pvalue'),'beta':row.get('std.all'),
                      'group':row.get('group')})
    for row in merged.get('path_coefficients',merged.get('coefficients',[])):
        term = row.get('term',row.get('_row'))
        if not term or term == '(Intercept)': continue
        if case['id'] not in {'moderation','conditional-mediation','mediated-interaction'}: continue
        target=row.get('outcome','well_being')
        label=({'x':'a1','w':'a2','x:w':'a3'}.get(term,'') if target=='m' else
               {'x':'c1′','w':'c2′','x:w':'c3′','m':'b'}.get(term,'') if case['id']!='moderation' else
               {'x':'b1','w':'b2','x:w':'b3'}.get(term,''))
        paths.append({'source':term,'target':target,'label':label,
            'estimate':row.get('estimate',row.get('Estimate')),'p':row.get('p',row.get('Pr(>|t|)')),'beta':None})
    return {'case_id':case['id'],'title':case['title'],'design':case['design'],
            'provenance':{'script':case['script'],'script_sha256':result.get('script_sha256'),
                'data_sha256':result.get('data_sha256'),
                'supplement_sha256':extra.get('extractor_sha256'),
                'prediction_sha256':prediction.get('extractor_sha256')},
            'tables':tables,'paths':paths,
            'measurement':[r for r in merged.get('parameters',[]) if r.get('op') == '=~'],
            'variances':[r for r in merged.get('parameters',[]) if r.get('op') == '~~' and r['lhs'] == r['rhs']],
            'covariances':[r for r in merged.get('parameters',[]) if r.get('op') == '~~' and r['lhs'] != r['rhs']],
            'model_scale':'standardized' if all(isinstance(r.get('std.all'),(int,float)) for r in merged.get('parameters',[]) if r.get('op') in {'=~','~','~~'}) else 'raw',
            'predictions':prediction.get('predictions',extra.get('prediction_grid',[])),
            'prediction_spec':prediction.get('specification',{}),
            'prediction_coefficients':prediction.get('coefficients',{}),
            'observations':prediction.get('observations',[]),'valid':result['status']=='valid'}


def validate_paper_assets(case,result):
    """Block stale source views or failed figures before clearing the build output."""
    data=paper_data(case,result)
    path=ROOT/'assets/paper-results'/(case['id']+'.json')
    if not path.exists() or json.loads(path.read_text(encoding='utf-8'))!=data:
        raise ValueError('missing/stale paper source data: '+case['id'])
    records_path=ROOT.parent/'logs/paper-results/export-records.json'
    records=json.loads(records_path.read_text(encoding='utf-8'))
    source=hashlib.sha256((ROOT.parent/'tools/render_paper_results.py').read_bytes()+Path(__file__).read_bytes()).hexdigest()
    payload=json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)
    fingerprint=hashlib.sha256((source+payload).encode('utf-8')).hexdigest()
    for kind in ('model','slopes','estimates','loadings','profiles'):
        stem=case['id']+'-'+kind; svg=ROOT/'assets/paper-results'/(stem+'.svg')
        if not svg.exists():continue
        record=records.get(stem,{})
        if record.get('failed') or record.get('fingerprint')!=fingerprint:
            raise ValueError('failed/stale paper figure audit: '+stem)
        for extension in ('svg','pdf'):
            asset=svg.with_suffix('.'+extension)
            if not asset.exists() or record.get(extension+'_sha256')!=hashlib.sha256(asset.read_bytes()).hexdigest():
                raise ValueError('changed paper figure asset: '+stem)


def formatted(value, key, row):
    if value is None or isinstance(value,float) and not math.isfinite(value): return '—'
    if isinstance(value,(int,float)):
        if is_p_field(key) or str(key).startswith('pvalue.') or key == governing_p(row) or key == 'value' and is_p_field(row.get('field_id','')):
            return format_p(value)
        return format_number(value, key, row)
    if is_p_field(key) and str(value).startswith('<'):
        try:
            if float(str(value)[1:].strip()) < 0.001: return '<0.001'
        except ValueError: pass
    return VARIABLES.get(str(value),str(value))


def paper_significant_columns(row):
    """A printed p upper bound can establish significance without claiming exact p."""
    numeric=dict(row)
    for key,value in row.items():
        if is_p_column(key) and isinstance(value,str) and value.lstrip().startswith('<'):
            try:
                upper=float(value.lstrip()[1:].strip())
                if 0<upper<=1:numeric[key]=math.nextafter(upper,0)
            except ValueError:
                pass
    return significant_columns(numeric)


def render_paper_result(case, result, *, root='../', source_page=False):
    data = paper_data(case,result)
    image_dir = ROOT / 'assets/paper-results'
    figures = {}
    for kind, title in [('model','完整测量与结构模型' if data['measurement'] else '模型与路径效应'),('slopes','预测概率函数' if case['id']=='logistic' else '回归预测函数' if data['prediction_spec'] else '调节效应：条件预测'),('estimates','效应估计与 95% CI'),('loadings','成分载荷' if case['id']=='pca' else '固定时间载荷' if case['id']=='growth' else '测量载荷'),('profiles','标准化类别画像')]:
        stem = case['id']+'-'+kind
        if (image_dir/(stem+'.svg')).exists():
            explanation={'model':'箭头标明各段原量纲系数 b；β 表示全标准化回归系数。SE、区间、检验和方差／协方差见参数表。',
                'slopes':'线条表示低、平均和高支持水平的条件均值；淡色带表示条件均值的 95% CI。',
                'estimates':'圆点为效应估计，横线为对应区间；区间计算及 p 值校正方法见表下注。',
                'loadings':('显示增长模型中设定的固定载荷：截距因子均为 1，斜率因子按时间为 0、1、2、3。因子的均值、变异与协方差见表。' if case['id']=='growth' else '数字表示载荷；CFA / SEM 采用全标准化载荷，EFA 采用模式矩阵，PCA 采用成分载荷。空格表示未设定该测量路径。'),
                'profiles':'各指标按本例全体样本的均值和 SD 标准化后再显示组画像；纵轴为标准差单位，原量纲均值保留在表中。'}[kind]
            if kind=='model' and case['id'] in {'conditional-mediation','mediated-interaction'}:
                explanation+=' X 为自变量，W 为调节变量，M 为中介变量，Y 为结果变量。X、M、Y 构成中介三角形；内部的 W 指向被调节的边，标注 X × W 的交互系数。X 的路径系数对应 W = 0，W 的主效应另列在图内。'
            if kind=='model' and case['id']=='moderation':
                explanation+=' W 的竖直箭头落在 X → Y 路径上，b3 为 X × W 的交互系数；b1 对应 W = 0 时的 X 斜率，b2 为 W 的主效应。'
            summary=next((t for t in data['tables'] if t['name']=='model_summary'),None)
            sample=(f' n = {summary["rows"][0]["n"]}。' if summary and summary['rows'][0].get('n') else '')
            if summary and len(summary['rows'])>1 and all('group' in r and 'n' in r for r in summary['rows']):
                sample=f' 总 n = {sum(r["n"] for r in summary["rows"])}；'+ '，'.join(f'组 {r["group"]} n = {r["n"]}' for r in summary['rows'])+'。'
            if not sample and result['metrics'].get('n'):sample=f' n = {result["metrics"]["n"]}。'
            if not sample and result['metrics'].get('people'):sample=f' 参与者数 = {result["metrics"]["people"]}；观测数 = {result["metrics"].get("observations",result["metrics"]["people"])}。'
            if kind == 'model' and case['id'] in {'mediation', 'latent-mediation'}:
                explanation = 'a、b、c′ 对应箭头上的原量纲路径系数；间接效应与 Bootstrap 区间列在图下方。'
            if kind == 'model' and data['measurement']:
                scale='全标准化载荷与 β 路径；θ、ψ、φ 也在标准化尺度上' if data['model_scale']=='standardized' else '原量纲载荷与 b 路径；θ、ψ、φ 沿用模型定标的原量纲'
                explanation = '椭圆是潜变量／因子，矩形是实际观测指标。图中采用'+scale+'。λ 表示载荷，e、ζ 分别表示测量残差与潜变量扰动，θ、ψ 为相应方差，φ 为潜变量协方差。多组数值按组标注，完整估计与区间保留在参数表。'
                if case['id']=='latent-mediation':
                    explanation += '间接效应 a×b 的 Delta 方法区间保留在补充参数表。'
            if kind == 'slopes' and data['prediction_spec']:
                spec=data['prediction_spec']
                fixed='，'.join(VARIABLES.get(k,k)+' = '+format(v,'.2f') for k,v in (spec['fixed'] or {}).items())
                explanation='实线为本次拟合模型的条件预测；淡色带为 '+spec['confidence']+'。'
                if fixed:explanation+=' 其他变量固定为样本均值：'+fixed+'。'
                if data['observations']:explanation+=' 每个浅色点是一条实际教学记录，保留全部拟合观测。'
                if case['id']=='ancova':explanation+=' 三条线对应各教学条件在相同前测水平下的后测预测。'
                if case['id']=='logistic':
                    coefficients=data['prediction_coefficients']
                    constant=coefficients['(Intercept)']+sum(coefficients[k]*v for k,v in spec['fixed'].items())
                    slope=coefficients[spec['x']]
                    ordered=sorted(data['predictions'],key=lambda row:row['x'])
                    left,right=ordered[0],ordered[-1]
                    explanation='横轴 z 是各预测变量加权相加后的线性预测子，纵轴是 p = 1 / (1 + exp(−z)) 转换得到的筛查阳性概率。灰线展示完整 S 型函数及两端趋近 0、1 的形状；主题色线段与淡色置信带对应本例实际睡眠范围。'+f' 固定压力与年龄后，本例 z = {constant:.3f} {"−" if slope<0 else "+"} {abs(slope):.3f} × 睡眠小时数。睡眠从 {left["x"]:.1f} 增至 {right["x"]:.1f} 小时，z 从 {constant+slope*left["x"]:.3f} 降至 {constant+slope*right["x"]:.3f}，预测概率从 {left["estimate"]:.3f} 降至 {right["estimate"]:.3f}，因此原图只显示了完整 S 曲线中的一小段。淡色带为 '+spec['confidence']+'。'
                    if fixed:explanation+=' 其他变量固定为样本均值：'+fixed+'。'
            if kind == 'slopes' and case['id'] == 'moderation':
                rows=next((t['rows'] for t in data['tables'] if t['name']=='path_coefficients'),[])
                interaction=next((r for r in rows if r.get('term')=='x:w'),None)
                if interaction:
                    explanation+=f' 交互项 b = {interaction["estimate"]:.4f}，95% CI [{interaction["ci_lower"]:.4f}, {interaction["ci_upper"]:.4f}]，p = {formatted(interaction["p"],"p",interaction)}。'
            figures[kind] = f'<figure class="paper-figure"><img src="{root}assets/paper-results/{stem}.svg" alt="{escape(title)}：{escape(case["title"])}" loading="lazy"><figcaption>{escape(title)}。{explanation}{sample} <a href="{root}assets/paper-results/{stem}.pdf" download>下载矢量 PDF</a></figcaption></figure>'
    sections = {}
    for table in data['tables']:
        columns=table['columns']; rows=table['rows']
        descriptive = table['name'] in {'descriptives','group_descriptives'}
        def numeric_cell(value,key):
            return isinstance(value,(int,float)) or is_p_field(key) and isinstance(value,str) and bool(re.fullmatch(r'[<>]\s*[0-9.eE+-]+',value))
        numeric={key for key in columns if any(numeric_cell(r.get(key),key) for r in rows)
                 and all(r.get(key) is None or numeric_cell(r.get(key),key) for r in rows)}
        labels={**LABELS}
        labels.update(analysis='研究对象 / 分析情境',variables='研究变量 / 比较对象',
                      method='方法',coefficient='相关系数',statistic_name='统计量类型')
        labels.update(table.get('column_labels',{}))
        if table['name'] in {'path_coefficients','reported_coefficients'}:labels['estimate']='b'
        if case['id']=='equivalence':labels.update(ci_lower='90% CI 下限',ci_upper='90% CI 上限',p='TOST p')
        heading=''.join(f'<th scope="col" class="{"analysis-numeric" if key in numeric else "analysis-text"}">{DESCRIPTIVE_HEADERS.get(key,escape(labels.get(key,key))) if descriptive else escape(labels.get(key,key))}</th>' for key in columns)
        body=[]
        for index,row in enumerate(rows):
            emphasized=({k for k,v in row.items() if (is_p_field(k) or k.startswith('pvalue.')) and isinstance(v,(int,float)) and v<0.05} if table['name'] in {'metrics','fit'} else paper_significant_columns(row))
            if table['name']=='correlations' and emphasized:
                emphasized=emphasized|{'coefficient'}
            bootstrap_table=table['name'] in {'conditional_effects','interaction_effects','standardized_effects'} or table['name']=='effect_summary' and case['id'] in {'mediation','latent-mediation','conditional-mediation','mediated-interaction'}
            if bootstrap_table and isinstance(row.get('ci_lower'),(int,float)) and isinstance(row.get('ci_upper'),(int,float)) and (row['ci_lower']>0 or row['ci_upper']<0):
                emphasized=emphasized|{'estimate','ci_lower','ci_upper'}
            cells=[]
            for key in columns:
                value = row.get(key)
                content=escape(format(value,'.2f') if descriptive and key in {'mean','sd','median','iqr'} and isinstance(value,(int,float)) else formatted(value,key,row))
                if key in emphasized or key=='value' and is_p_field(row.get('field_id','')) and row['value']<0.05:
                    content='<strong class="stat-significant">'+content+'</strong>'
                mappings=table.get('source_fields',[])
                field=(mappings[index].get(key) if index<len(mappings) else None)
                if table['name']=='descriptives' and case['id']=='describe' and key in DESCRIPTIVE_FIELDS:
                    field=key
                if source_page and field and any(a['field_id']==field for a in case['annotations']):
                    label = next(a['label'] for a in case['annotations'] if a['field_id']==field)
                    content=f'<button type="button" class="paper-locate" data-analysis-locate="{escape(field)}" aria-label="定位 {escape(label)} 的原始输出">{content} ⟵</button>'
                tag = 'th' if key==columns[0] and key in {'variable','variables','analysis','model'} else 'td'
                scope = ' scope="row"' if tag=='th' else ''
                cells.append(f'<{tag}{scope} class="{"analysis-numeric" if key in numeric else "analysis-text"}">{content}</{tag}>')
            body.append('<tr>'+''.join(cells)+'</tr>')
        sections[table['name']] = f'<div class="paper-table-scroll"><table class="paper-table"><caption>{escape(table["title"])} · 三线表</caption><thead><tr>{heading}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
    # One main display answers the model's central question. Full source records
    # remain available without making each record a competing main display.
    figure_order = ('slopes','model','profiles','loadings','estimates')
    if case['id'] in {'efa','pca','growth'}:
        figure_order = ('loadings','model','profiles','slopes','estimates')
    primary_figure = next((kind for kind in figure_order if kind in figures), None)
    table_order = ('descriptives','correlations','tests','odds_ratios','reported_coefficients','path_coefficients',
                   'console_coefficients','coefficients','effect_summary','parameters','metrics')
    primary_table = None if primary_figure else next((name for name in table_order if name in sections), next(iter(sections)))
    primary = figures[primary_figure] if primary_figure else sections[primary_table]
    additional = ''.join(value for kind,value in figures.items() if kind != primary_figure)
    additional += ''.join(value for name,value in sections.items() if name != primary_table and name != 'metrics')
    additional_html = ('<details class="paper-supplement"><summary>补充参数与其他结果呈现</summary>'+additional+'</details>') if additional else ''
    diagnostic='<p class="paper-note">本例用于诊断模型问题，下面保存诊断时的输出。</p>' if not data['valid'] else ''
    interval_note = ('中介效应区间来自 300 次教学 Bootstrap 百分位法；路径系数的 SE 与检验见表。' if case['id']=='mediation' else
        '回归系数使用 t 分布 95% CI；条件间接效应及调节中介指数使用 300 次教学 Bootstrap 百分位区间。W = ±1 表示中心化后的一单位。' if case['id'] in {'conditional-mediation','mediated-interaction'} else
        '简单斜率及预测带采用 t 分布 95% CI；支持水平取中心化后的均值及 ±1 SD。' if case['id']=='moderation' else
        '等效检验以 ±3 为界限，使用 90% CI 和两个单侧 Welch 检验；TOST p 取两个单侧 p 的较大者。' if case['id']=='equivalence' else
        'Tukey 表与区间图使用家族范围 95% 同时置信区间及调整后的 p 值。' if case['id']=='anova' else
        '后续比较的 p 使用 Holm 校正；图中区间为各比较的未校正 95% CI。' if case['id'] in {'manova','repeated'} else
        '多重插补的合并区间使用 Rubin 合并规则和相应自由度；FIML 参数单列保存。' if case['id']=='missing' else
        '压力系数的区间采用 HC3 标准误及正态临界值；控制台回归表同时保留模型默认标准误。' if case['id']=='diagnostics' else
        '标准化效应量的区间使用 1000 次教学 Bootstrap 百分位法；Hedges g 以两组的合并 SD 标准化并作小样本校正，配对 dz 以变化分数的 SD 标准化。' if case['id']=='t-tests' else
        '单样本 Cohen d 以 7 为参照均值，使用样本 SD 标准化；d 的区间使用 1000 次教学 Bootstrap 百分位法。均值区间沿用单样本 t 检验。' if case['id']=='t-single' else
        'log-odds 系数与 OR 的区间均采用 Wald 法；OR 是系数及其区间端点取指数后的结果。' if case['id']=='logistic' else
        '区间、校正方式及检验定义沿用本例的 R 输出与运行代码。')
    origin=(f'<p class="paper-note">配套教学示例：<a href="{root}analyses/{escape(case["id"])}.html">{escape(case["title"])}</a>。以下图表由该示例的代码运行生成；请按链接下载配套代码复现。</p>' if not source_page else '')
    return (f'<section class="paper-results" id="paper-results"><h2>论文式结果图表</h2>{diagnostic}{origin}'
        +'<div class="paper-primary">'+primary+'</div>'+additional_html+f'<p class="paper-note">{interval_note}'
        +f' <a href="{root}analysis-logs/{escape(case["id"])}.txt" download>原始运行日志</a> · <a href="{root}assets/paper-results/{escape(case["id"])}.json" download>图表源数据</a>'
        +(f' · <a href="{root}analyses/{escape(case["id"])}.html#paper-results">对应分析示例与输出解读</a>' if not source_page else '')+'</p>'
        +(f'<details class="paper-reproduction"><summary>复现补充图表统计量</summary><p class="paper-note">运行本例原始代码后，在同一目录下载并运行 <a href="{root}analysis-code/_paper_supplement.R" download>补充结果提取脚本</a>。它会保存 paper-result.json；原始分析结果保持不变。</p><pre><code>CASE_ID &lt;- "{escape(case["id"])}"\nsource("_paper_supplement.R")</code></pre></details>' if supplement(case['id']) else '')
        +(f'<details class="paper-reproduction"><summary>复现预测函数与置信带</summary><p class="paper-note">运行本例原始代码后，在同一目录运行 <a href="{root}analysis-code/_prediction_supplement.R" download>预测结果提取脚本</a>，保存 prediction-result.json；其他变量的固定值与区间算法随预测记录一起保存。</p><pre><code>CASE_ID &lt;- "{escape(case["id"])}"\nsource("_prediction_supplement.R")</code></pre></details>' if data['prediction_spec'] else '')+'</section>')
