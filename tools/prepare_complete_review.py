"""Build a complete, explicitly unreviewed content edition without promoting it."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import os
from author_release_slice import make_example_code
from review_examples import RECIPES

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / 'site/content'
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

FORMULAS = {
 'standard-score': (r'z_i=\frac{x_i-\bar{x}}{s}', 'x_i 是观测值，样本均值为 x̄，样本标准差 s>0；标准化不改变分布形状。'),
 'descriptive-statistics': (r'\bar{x}=\frac{1}{n}\sum_{i=1}^{n}x_i,\quad s=\sqrt{\frac{\sum_{i=1}^{n}(x_i-\bar{x})^2}{n-1}}', 'n 是样本量，s 是样本标准差；n>1，均值和标准差须结合分布和异常值解释。'),
 'sampling-distribution': (r'\operatorname{SE}(\bar X)=\frac{\sigma}{\sqrt n}', '独立同分布且总体方差有限时，样本均值的标准误为总体标准差 σ 除以样本量平方根；未知 σ 时需估计。'),
 'standard-error': (r'\widehat{\operatorname{SE}}(\bar X)=\frac{s}{\sqrt n}', 's 是样本标准差，n 是独立观测的样本量；聚类或配对设计不能机械套用。'),
 'null-hypothesis': (r'H_0:\mu_1-\mu_2=0', '这是两个总体均值相等的零假设示例；实际零假设由研究问题与检验模型确定。'),
 'p-value': (r'p=\Pr_{H_0}\!\left(|T|\ge |t_{\mathrm{obs}}|\right)', '这是以统计量绝对值为极端程度的双侧检验示例：T 是零假设下的统计量，t_obs 是观测值。不是零假设为真的概率；其他检验需要不同的极端性规则。'),
 'confidence-interval': (r'\bar{x}\pm t_{1-\alpha/2,n-1}\frac{s}{\sqrt n}', '独立正态观测下总体均值的 t 区间；α 是长期不覆盖比例，t 是分位数。95%描述程序的长期覆盖，不是当前固定参数的概率。'),
 'effect-size': (r'd=\frac{\bar{x}_1-\bar{x}_2}{s_p},\quad s_p=\sqrt{\frac{(n_1-1)s_1^2+(n_2-1)s_2^2}{n_1+n_2-2}}', '独立组、共同方差口径下的 Cohen d；s_p 为合并标准差，顺序决定正负。不是配对或异方差设计的通用效应量。'),
 't-test': (r't=\frac{\bar{x}_1-\bar{x}_2}{\sqrt{s_1^2/n_1+s_2^2/n_2}}', '独立两组的 Welch t 统计量；分母是均值差标准误，自由度使用 Welch–Satterthwaite 近似。配对检验使用差值数据的另一公式。'),
 'anova': (r'F=\frac{MS_{\mathrm{between}}}{MS_{\mathrm{within}}},\quad df_1=k-1,\quad df_2=N-k', '独立组单因素经典方差分析：k 为组数，N 为总样本量；均方为平方和除以自由度。需要相应残差条件，不直接定位不同的组。'),
 'correlation-coefficient': (r'r=\frac{\sum_i(x_i-\bar{x})(y_i-\bar{y})}{\sqrt{\sum_i(x_i-\bar{x})^2\sum_i(y_i-\bar{y})^2}}', 'Pearson 样本相关系数；两变量需有非零变异，反映线性关系而非因果。异常值、非线性与样本选择会影响解读。'),
 'outlier': (r'IQR=Q_3-Q_1,\quad [Q_1-1.5IQR,\ Q_3+1.5IQR]', '箱线图的常见标记范围；Q1、Q3 为四分位数。超过范围只是待核查点，不是自动删除标准。')
}
FORMULAS.update({
 'cfa':(r'\mathbf x=\boldsymbol\nu+\mathbf\Lambda\boldsymbol\eta+\boldsymbol\epsilon', '连续指标的验证性因素测量模型：x 为观测向量，ν 为截距，Λ 为预设载荷结构，η 为潜在因素，ε 为测量残差。固定部分载荷及尺度用于识别；有序题需在潜在连续反应层结合阈值建模。'),
 'efa':(r'\mathbf\Sigma=\mathbf\Lambda\mathbf\Phi\mathbf\Lambda^{\mathsf T}+\mathbf\Psi', '共同因素模型的协方差分解：Σ 为指标协方差，Λ 为载荷，Φ 为因素协方差，Ψ 为独特部分协方差，通常假定为对角。旋转等价性意味着单一矩阵不能自动决定因素的内容意义。'),
 'common-factor':(r'x_i=\nu_i+\sum_{j=1}^{m}\lambda_{ij}\eta_j+\epsilon_i', '指标 i 由截距 ν_i、m 个共同因素 η_j 的加权贡献和独特残差 ε_i 构成；λ_ij 是载荷。这是线性测量模型，不表示共同因素已经被直接观测。'),
 'sem':(r'\boldsymbol\eta=\boldsymbol\alpha+\mathbf B\boldsymbol\eta+\mathbf\Gamma\boldsymbol\xi+\boldsymbol\zeta', '线性结构部分示例：η 为内生潜变量，ξ 为外生潜变量，B 和 Γ 为路径系数，α 为截距，ζ 为结构残差。SEM 还包括测量模型与识别条件；箭头和拟合不证明因果。'),
 'stepwise-regression':(r'AIC=-2\log\widehat L+2k', '示例 step 使用 AIC 比较候选模型：L̂ 是极大化似然，k 是软件计算的自由参数数目。只比较同一数据和相容似然口径下的模型；不是某个模型为真的概率。'),
 'dummy-coding':(r'D_{ig}=\begin{cases}1,&\text{个体 }i\text{ 属于组 }g\\0,&\text{其他}\end{cases}', '有截距的模型通常对 k 组设置 k−1 个虚拟变量；未编码的组是参照。系数按参照组及模型中的其他项解释，不把组编号当作连续分数。')
})

FLOW_LABELS = {
 'measurement-scales':['辨认记录方式','判断可做的运算','匹配描述与分析'],
 'population-and-sample':['界定目标群体','检查抽样来源','限定推广范围'],
 'parameter-and-statistic':['确定总体目标','计算样本统计量','表达估计不确定性'],
 'central-tendency-and-dispersion':['查看分布形态','选中心与离散指标','结合单位解读'],
 'normal-distribution':['识别模型用途','观察偏态与尾部','区分数据与残差'],
 'statistical-assumptions':['核对研究设计','检查模型条件','选择修正或替代'],
 'normality':['确定检查对象','检查图形与异常点','评估方法敏感性'],
 'linearity':['绘制关系图','检查残差模式','调整关系形式'],
 'independence':['辨认观测单位','寻找聚类或重复','匹配误差结构'],
 'covariance':['统一变量记录','计算共同变动','核对单位与尺度'],
 'multivariate-outlier':['选定变量组合','检查联合偏离','核查而非自动删除'],
 'mahalanobis-distance':['检查协方差条件','计算联合距离','结合设计核查个体'],
 'box-plot':['按组展示分布','阅读中位数与四分位','核查须外观测'],
 'missing-data-mechanism':['查看缺失模式','推理缺失来源','安排敏感性分析'],
 'multiple-imputation':['指定插补模型','生成多份数据','分析并合并估计'],
 'standardization':['选择参照均值与标准差','转换到标准差单位','保留转换参数'],
 'centering':['确定参照点','减去参照值','按新零点解释'],
 'exploratory-data-analysis':['检查记录与缺失','观察分布与关系','记录探索与分析决策'],
 'variable':['界定研究概念','确定测量与编码','核对分析角色'],
 'descriptive-statistics':['检查记录单位','汇总分布特征','结合图形与样本解释'],
 'standard-score':['选择参照群体','计算标准分数','解释相对位置'],
 'sampling-distribution':['明确统计量','重复抽样或模拟','观察估计波动'],
 'standard-error':['明确估计对象','匹配抽样设计','表达估计精度'],
 'null-hypothesis':['写出基准主张','确定检验与条件','限定证据含义'],
 'confidence-interval':['选择参数与方法','计算上下界','判断精度与实际意义'],
 'effect-size':['明确差异或关系','选择效应量口径','结合区间与领域标准'],
 't-test':['区分独立与配对','检查差值或残差','报告均值差与区间'],
 'anova':['明确组别与结果','检验整体差异','安排比较与效应量'],
 'missing-data':['识别缺失编码','检查模式与机制','选择处理并报告']
}

OUTPUT_GUIDANCE = {
 'multiple-regression':'stress_beta≈−0.370：控制支持与年龄后，压力每增加一单位对应幸福感约降低0.370单位；support_beta≈0.310是对应的支持系数。r_squared≈0.312表示本样本模型解释约31.2%的幸福感变异，不表示31.2%的因果影响。应补看系数区间、共线性与残差。',
 'logistic-regression':'stress_log_odds≈−0.085 是对数优势系数；将系数取指数后才是优势比。support_odds_ratio≈1.074表示固定其他项时支持每增加一单位，目标事件的优势乘以约1.074，不是概率提高7.4个百分点。先核对结果事件编码，并报告区间。',
 'efa':'示例 primary_loading≈0.644 为各预设题组主要载荷的平均值，不能替代逐题查看完整载荷矩阵；uniqueness_mean≈0.582 是独特方差比例的平均值。示例用连续近似的极大似然提取，五级题目正式分析应进一步考虑有序尺度、偏态、因素数与旋转。',
 'mediation-effect':'indirect_effect≈0.103 是控制年龄后支持→压力→幸福感两条回归系数的乘积。ci_lower≈0.062、ci_upper≈0.150 来自按人有放回抽样300次的百分位Bootstrap演示；正式分析应增加重复次数并说明区间方法。该横断面示例不能证明时间顺序、排除混杂或建立因果中介。',
 'moderation-effect':'interaction_beta≈−0.00076 表示支持每变化一单位，压力与幸福感关系的模型斜率变化约−0.00076。r_squared≈0.306 是含交互模型的解释比例，不是交互项独有贡献；本例未输出该项区间与p值，不能仅凭这个数宣称存在调节，应补看summary、confint和简单斜率。',
 'icc':'class_variance≈21.33、residual_variance≈60.84；icc≈0.260 是班级方差除以两者之和。在这个连续成绩的随机截距空模型中，约26%的模型方差位于班级层；不是班级因素造成了26%的差异，也不是所有设计通用的ICC定义。',
 'random-intercept-model':'motivation_beta≈0.361 是控制班级支持后的平均动机系数，teacher_beta≈0.066 是班级支持的系数；仅有点估计不能判定统计证据充分。模型允许班级起点不同但动机斜率相同，应另外查看VarCorr、区间和残差。动机未作组内组间分解，不能称此系数为纯组内关系。'
}

def prepare():
    registry = read(CONTENT/'registry.json')['terms']
    packs = {}
    for path in sorted((CONTENT/'review_batches').glob('*.json')):
        for slug, body in read(path)['terms'].items():
            if slug in packs:
                raise ValueError('duplicate '+slug)
            packs[slug] = body
    recipes = dict(RECIPES)
    for path in CONTENT.glob('review_r_*.json'):
        payload = read(path)
        recipes.update(payload.get('terms', payload))
    old_report = {x['term_id']:x for x in read(ROOT/'logs/r_validation.json')['results']}
    terms = []
    for meta in registry:
        slug = meta['id']
        public = CONTENT/'terms'/f'{slug}.json'
        term = read(public if public.exists() else CONTENT/'drafts'/f'{slug}.json')
        if not public.exists():
            if slug not in packs:
                raise ValueError('content missing: '+slug)
            term.update(packs[slug])
        if slug in FORMULAS:
            latex, note = FORMULAS[slug]
            term['formula'] = dict(latex=latex, note=note, verified=False)
        if slug in FLOW_LABELS:
            labels=FLOW_LABELS[slug]
            term['visual_steps']=[dict(label=labels[0],detail=term['problems_solved'][0]),dict(label=labels[1],detail=term['decision_clues'][0]),dict(label=labels[2],detail=term['not_for'][0])]
        elif not term.get('visual_steps'):
            term['visual_steps'] = [dict(label='明确研究需求',detail=term['real_question']), dict(label='对照适用条件',detail='；'.join(term['decision_clues'])),dict(label='判断与报告',detail=term['sections'][0]['body'])]
        if slug in recipes:
            term['r_practice'] = recipes[slug]
        elif slug in old_report and old_report[slug]['verified']:
            if not isinstance(term.get('r_practice'),dict) or not term['r_practice'].get('example_code'):
                term['r_practice'] = dict(packages=[], data_shape='一行一条观测；先下载教学 CSV。', example_code=make_example_code(slug), your_data_code=(ROOT/'examples/r/templates'/f'{slug}.R').read_text(encoding='utf-8'), assumption_checks=term['decision_clues'], key_output=list(old_report[slug]['metrics']), interpretation='示例输出字段：'+ '；'.join(f'{k}={v:.4g}' for k,v in old_report[slug]['metrics'].items())+'。先核对估计方向、单位与适用前提；这些数值仅来自教学合成数据，不是科研结论。',report_template='报告估计量、区间、研究设计和诊断。',common_errors=term['not_for'],verified=True,validation_report='logs/r_validation.json')
        else:
            term['r_practice'] = None
        if slug in OUTPUT_GUIDANCE and term['r_practice']:
            term['r_practice']['interpretation']=OUTPUT_GUIDANCE[slug]
        term.update(status='draft', verified=False, editorial_status='pending-human-review')
        term.pop('authoring_todos',None)
        # Retrieval candidates are not sources; prevent unreviewed evidence leakage.
        term.pop('candidate_evidence',None)
        terms.append(term)
    ids = {t['id'] for t in terms}
    for term in terms:
        for key in ['real_question','operational_definition','plain_explanation','plain_example','sections','sources','visual_steps']:
            if not term.get(key): raise ValueError(f'{term["id"]}: missing {key}')
        q = term['quiz']
        if len(q['options']) != 4 or len(q.get('option_explanations',[])) != 4 or q['answer'] not in range(4): raise ValueError('quiz '+term['id'])
        for relation,targets in term['relations'].items():
            if set(targets)-ids: raise ValueError('relation '+term['id'])
    visiting, done = set(),set()
    byid={t['id']:t for t in terms}
    def visit(slug):
        if slug in visiting: raise ValueError('prerequisite cycle '+slug)
        if slug in done:return
        visiting.add(slug)
        for dep in byid[slug]['relations'].get('prerequisites',[]):visit(dep)
        visiting.remove(slug);done.add(slug)
    for slug in ids:visit(slug)
    for term in terms:write(CONTENT/'drafts'/f'{term["id"]}.json',term)
    write(ROOT/'logs/complete_content_audit.json',dict(terms=len(terms),formulas=sum(bool(t.get('formula',{}).get('latex')) for t in terms),r_examples=sum(t['r_practice'] is not None for t in terms),pending_human_review=len(terms)))
    print('Prepared complete review:',len(terms),'terms;',sum(t['r_practice'] is not None for t in terms),'R examples')

def validate_r():
    results=[]
    env=os.environ.copy();env['R_LIBS_USER']=str(ROOT/'examples/r/library')
    exe=Path(r'C:\Program Files\R\R-4.5.1\bin\Rscript.exe')
    with tempfile.TemporaryDirectory(prefix='psych-review-') as temp:
        work=Path(temp)
        for path in (ROOT/'examples/data').glob('*.csv'):shutil.copy2(path,work/path.name)
        for path in sorted((CONTENT/'drafts').glob('*.json')):
            term=read(path);practice=term.get('r_practice')
            if not practice:continue
            script=work/'run.R'
            script.write_text('if (.Platform$OS.type=="windows") suppressWarnings(Sys.setlocale("LC_ALL","English_United States.utf8"))\n'+practice['example_code']+'\n'+practice.get('validation_code',''),encoding='utf-8')
            run=subprocess.run([str(exe),'--vanilla',str(script)],cwd=work,env=env,capture_output=True,text=True,errors='replace',timeout=90)
            template=work/'template.R';template.write_text(practice['your_data_code'],encoding='utf-8')
            parsed=subprocess.run([str(exe),'--vanilla','-e','invisible(parse("template.R"))'],cwd=work,env=env,capture_output=True,text=True,errors='replace',timeout=15)
            result=dict(term_id=term['id'],verified=run.returncode==0,template_syntax_valid=parsed.returncode==0,template_execution='not-run-user-data-required',stdout=run.stdout,stderr=run.stderr)
            results.append(result)
            print(term['id'],run.returncode,parsed.returncode,flush=True)
            practice.update(verified=result['verified'],validation_report='logs/review_r_validation.json',template_verified=False)
            write(path,term)
    write(ROOT/'logs/review_r_validation.json',dict(results=results))
    if any(not r['verified'] or not r['template_syntax_valid'] for r in results):raise ValueError('R validation failed; see logs/review_r_validation.json')
    rows=['# 完整版逐页人工审核清单','', '126 条内容均待人工学术审核。公式语法与 R 运行检查不替代人工审校。自己的数据模板只做语法检查；须修改列名并检查研究条件。','', '| 审核 | 术语 | 公式 | R 示例 |','|---|---|---|---|']
    for path in sorted((CONTENT/'drafts').glob('*.json')):
        t=read(path);rows.append(f'| [ ] | [{t["zh"]}](../site/dist/terms/{t["id"]}.html) | {"有" if t.get("formula",{}).get("latex") else "—"} | {"已执行" if t.get("r_practice") else "—"} |')
    (ROOT/'docs/human-review-checklist.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')

if __name__=='__main__':
    import sys
    validate_r() if '--validate-r' in sys.argv else prepare()
