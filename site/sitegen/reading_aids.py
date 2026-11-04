"""Offline reading aids: display formatting and annotated mathematical atoms."""
from __future__ import annotations
import json
import re
from functools import lru_cache
from pathlib import Path


def leading_zero(text: str) -> str:
    # Preserve URLs, identifiers, file paths and dotted versions.
    chunks = re.split(r'(https?://[^\s<>"\u3002]+)', text)
    return ''.join(chunk if i % 2 else re.sub(r'(?<![A-Za-z0-9_./])\.(?=\d)', '0.', chunk)
                   for i, chunk in enumerate(chunks))


def display_payload(value):
    if isinstance(value,str): return leading_zero(value)
    if isinstance(value,list): return [display_payload(item) for item in value]
    if isinstance(value,dict): return {key:display_payload(item) for key,item in value.items()}
    return value


@lru_cache(maxsize=1)
def reading_metadata() -> dict:
    path = Path(__file__).resolve().parents[1]/'content/reading_aids.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


GREEK = dict(alpha='α',beta='β',gamma='γ',delta='δ',Delta='Δ',theta='θ',Lambda='Λ',
             mu='μ',nu='ν',eta='η',epsilon='ε',varepsilon='ε',sigma='σ',Sigma='Σ',omega='ω',
             rho='ρ',tau='τ',Phi='Φ',Psi='Ψ',xi='ξ',Gamma='Γ',zeta='ζ',chi='χ',ell='ℓ',pi='π',**{'lambda':'λ'})
MEANINGS = {
 'n':'用于此计算的有效观测数；独立性与缺失规则须与设计匹配。','N':'样本总数；有效分析样本以所用模型为准。',
 'i':'观测或个体索引；同一 i 的变量来自同一条观测。','j':'变量、条目或组的索引，具体以本式说明为准。',
 'k':'组、变量或成分的编号/数量，具体含义见本式适用条件。','m':'本式的项数或重复次数，见本式条件。',
 's':'样本标准差，衡量个体分数的离散程度。','s^2':'样本方差，即样本标准差的平方。',
 'df':'对应统计量的自由度；不是所有方法共用同一个数。','SE':'标准误，描述估计量的抽样波动。',
 'F':'均方比统计量；需结合分子、分母自由度和检验设计。','r':'样本相关系数，描述所指定变量的关系。',
 'p':'本式的概率或 p 值，按该页定义解读。','P':'概率运算：括号内事件发生的概率。','Pr':'概率运算：括号内事件发生的概率。',
 'E':'期望运算（均值）；在给定条件下概括平均结果。','Var':'方差运算：计算括号内量的离散程度。',
 'Cor':'相关运算：计算两个指定量的相关。','Cov':'协方差运算：组合估计之间共同变动的量。',
 'rank':'矩阵秩：最多能选出多少个彼此不冗余的列；只在选出的列之间检查能否按固定倍数相加拼出，不是数值的排序位置。','diag':'构造对角矩阵，把指定量放在主对角线上。',
 'log':'取对数；logit与似然表达通常使用自然对数。','max':'取所列数值的最大者。','min':'取所列数值的最小者。',
 'arg':'寻找使目标达到最优的参数取值。','SS':'平方和：指定来源的离差平方汇总。','MS':'均方：对应平方和除以自由度。',
 'IQR':'四分位距：第三四分位数减第一四分位数。','CI':'置信区间，按指定程序构造的上下界。',
 'IE':'指定路径的间接效应，不自动具有因果解释。','IMM':'有调节的中介指数：指定间接效应随调节变量变化的速率。',
 'OR':'优势比：比较两个条件的优势，而不是直接比较概率。','ICC':'组内相关，当前随机截距模型中的组间方差占比。',
 'KMO':'简单相关相对于简单与偏相关组合的比例指标。','VIF':'方差膨胀因子，反映预测项线性重叠对估计方差的影响。',
 'RMSEA':'近似误差均方根：按自由度和样本量缩放的失配指标。','RMSE':'均方根预测误差，与结果变量单位一致。',
 'AIC':'信息准则，结合模型似然与自由参数数目比较相容模型。',
 '+':'把各项贡献相加；不能把有相关性的方差任意直接相加。','-':'按指定方向相减；交换前后项会改变符号。',
 '=':'等号两侧表示本模型或定义下相同的量。','\\ne':'不相等；这里排除两侧相同的情况。',
 '\\ge':'大于或等于；保留边界值。','\\le':'小于或等于；保留边界值。',
 '\\pm':'分别取加号与减号，得到区间上界与下界。','\\sum':'把索引规定范围内的各项加总。',
 '\\sqrt':'开平方；将平方尺度还原为原量纲。','\\mid':'给定右侧条件后再解释左侧量。',
 '\\longrightarrow':'理论设定的方向，不因箭头存在就证明因果。','\\sim':'服从右侧给定分布，是模型假设而不是检验结果。',
 '\\cap':'两个事件同时发生。','\\approx':'近似等于，不是精确恒等式。',
 '\\Pr':'概率运算：以所指定的参考分布计算事件概率。','\\partial':'偏导数符号：其他条件固定时对指定变量的变化率。',
 '\\exp':'指数运算：e的指定次方；自然对数的逆运算。','π':'圆周率常数，约3.14159。',
 '\\in':'属于所指定的集合。','\\times':'乘法，把两侧量相乘。','\\cdot':'按本式取乘积或作为控制变量的分隔标记。',
}
GROUPS = {'mathbf','boldsymbol','mathrm','operatorname','mathsf','text','bar','hat','widehat','overline','begin','end'}
OPS = {'sum','int','pm','mid','ge','le','ne','longrightarrow','sim','cap','approx','log','max','min','Pr','partial','exp','in'}
ABBREVIATIONS = ['RMSEA','RMSE','IQR','VIF','ICC','KMO','IMM','AIC','SS','MS','SE','IE','CI','df']


def _group_end(text: str, start: int) -> int:
    depth = 0
    for i in range(start,len(text)):
        if text[i]=='{': depth += 1
        elif text[i]=='}':
            depth -= 1
            if depth==0: return i+1
    return start+1


def formula_atoms(latex: str) -> list[tuple[int,int,str]]:
    """Locate complete symbols, retaining accents and indexes as a single target."""
    result=[]; i=0
    while i<len(latex):
        start=i; end=i+1; atom=None
        if latex[i]=='\\':
            match=re.match(r'\\([A-Za-z]+)',latex[i:])
            if not match: i+=2; continue
            cmd=match.group(1); end=i+len(match.group())
            if cmd in GROUPS:
                while end<len(latex) and latex[end].isspace(): end+=1
                if end<len(latex) and latex[end]=='{':
                    end=_group_end(latex,end)
                elif end<len(latex) and latex[end]=='\\':
                    nested=re.match(r'\\[A-Za-z]+',latex[end:]); end+=len(nested.group()) if nested else 1
                else: end+=1
                if cmd not in {'text','begin','end'}: atom=latex[start:end]
            elif cmd in GREEK or cmd in OPS:
                if cmd!='sqrt': atom=latex[start:end]
        elif latex[i].isalpha() and latex[i].isascii():
            abbr=next((a for a in ABBREVIATIONS if latex.startswith(a,i)),None)
            end=i+len(abbr) if abbr else i+1; atom=latex[start:end]
        if atom and atom not in {'\\sqrt'}:
            while end<len(latex) and latex[end]=="'": end+=1
            while end<len(latex) and latex[end] in '_^':
                end+=1
                if end<len(latex) and latex[end]=='{': end=_group_end(latex,end)
                elif end<len(latex) and latex[end]=='\\':
                    m=re.match(r'\\[A-Za-z]+',latex[end:]); end+=len(m.group()) if m else 1
                else: end+=1
            atom=latex[start:end]
        if atom: result.append((start,end,atom))
        i=end
    return result


def symbol_label(token: str) -> str:
    value=token
    for command in ['mathbf','boldsymbol','mathrm','operatorname','mathsf']:
        value=re.sub(r'\\'+command+r'\{([^{}]+)\}',r'\1',value)
    value=re.sub(r'\\(?:mathbf|boldsymbol|mathrm|operatorname|mathsf)\s*','',value)
    for name,char in GREEK.items(): value=re.sub(r'\\'+name+r'(?![A-Za-z])',char,value)
    value=re.sub(r'\\(?:widehat|hat)\s*(?:\{([^{}]+)\}|([A-Za-zα-ωΑ-Ω]))',lambda m:(m[1] or m[2])+'̂',value)
    value=re.sub(r'\\(?:bar|overline)\s*(?:\{([^{}]+)\}|([A-Za-zα-ωΑ-Ω]))',lambda m:(m[1] or m[2])+'̄',value)
    value=value.replace('\\sum','∑').replace('\\sqrt','√').replace('\\pm','±').replace('\\mid','|').replace('\\ge','≥').replace('\\le','≤').replace('\\ne','≠').replace('\\sim','∼').replace('\\cap','∩').replace('\\approx','≈').replace('\\longrightarrow','→')
    value=value.replace('\\int','∫')
    value=re.sub(r'\\cdot\s*','·',value)
    value=re.sub(r'_\{([^{}]+)\}',r'_\1',value).replace('{','').replace('}','').replace('\\','')
    return value


def symbol_meaning(token: str, slug: str, note: str) -> str:
    custom=reading_metadata().get(slug,{}).get('symbols',{})
    label=symbol_label(token)
    if label in custom: return custom[label]
    # Derive contextual definitions only from the current page's authored note.
    key=label.replace('̂','').replace('̄','')
    canonical=re.sub(r'[_^].*','',key)
    unicode_key=re.sub(r'_([0-9ij]+)',lambda m:m[1].translate(str.maketrans('0123456789ij','₀₁₂₃₄₅₆₇₈₉ᵢⱼ')),key).replace('^2','²')
    if token.startswith(r'\sum'): return '求和：把下标所规定的对象与范围逐项加总；未写上限时按当前分析集合求和。'
    if token.startswith(r'\int'): return '积分：在下限与上限所指定的范围内累计密度曲线下的面积，得到该区间的概率。'
    for clause in re.split('[；;。]',note):
        for part in re.split('[，,]',clause):
            if any(re.search(re.escape(alias)+r'\s*(?:是|为|表示)',part) for alias in (unicode_key,key,key.replace('_',''))):
                return part.strip()+'。'
    meaning=MEANINGS.get(token) or MEANINGS.get(label) or MEANINGS.get(canonical)
    if meaning: return meaning
    role={'x':'变量或观测分数','y':'结果变量或观测值','X':'预测变量或设计矩阵','Y':'结果变量','W':'调节变量或群组预测变量',
          'Z':'另一个解释变量或随机效应设计矩阵','M':'中介变量','b':'模型中的回归/路径系数','β':'模型系数',
          'γ':'多层模型的固定系数','a':'中介模型中预测变量到中介的路径系数','c':'所指定的参照量或效应',
          'e':'观测残差或模型误差','ε':'误差或残差','u':'随机效应偏差','σ':'总体标准差或方差参数',
          'μ':'总体均值或中心','ν':'指标截距','λ':'载荷或特征根','Λ':'载荷矩阵或Wilks指标',
          'η':'潜变量或效应量参数','Φ':'因素协方差矩阵','Ψ':'独特部分协方差矩阵','Σ':'协方差矩阵',
          'θ':'模型参数或残差方差','α':'显著性水平、信度系数或模型截距','τ':'群组方差参数',
          'Q':'估计量或分位点','R':'相关矩阵、秩或模型关系指标','T':'统计量、真实分数或总方差',
          'H':'假设或效应矩阵','L':'下界或似然','U':'上界或套内方差','B':'路径矩阵或套间方差',
          'G':'随机效应协方差矩阵','V':'协方差矩阵','C':'对比估计、聚类分组或常数','D':'距离或虚拟编码',
          'A':'矩阵或事件','f':'模型密度函数或因素','v':'特征向量','w':'指定条件取值或权重',
          'z':'标准分、成分分数或检验统计量','t':'时间编码、统计量或分位数','ξ':'外生潜变量','ζ':'结构残差',
          'ℓ':'对数似然准则'}
    base=role.get(canonical,'本式所定义的量')
    modifiers=[]
    if '̂' in label: modifiers.append('帽号表示由数据得到的估计/预测')
    if '̄' in label: modifiers.append('横线表示所指定参照下的平均值')
    if '_' in label: modifiers.append('下标区分对象、组、路径或条件')
    if '^2' in label: modifiers.append('上标2表示平方')
    return base+'；'+('；'.join(modifiers)+'；' if modifiers else '')+'按下方本式条件确认具体角色。'


def formula_aid(latex: str, slug: str, note: str='') -> tuple[str,list[dict]]:
    latex=leading_zero(latex)
    latex=re.sub(r'\\sqrt\s+([A-Za-z])',r'\\sqrt{\1}',latex)
    latex=re.sub(r'\\frac\s*([0-9A-Za-z])\s*([0-9A-Za-z])',r'\\frac{\1}{\2}',latex)
    atoms=formula_atoms(latex); keys={}; entries=[]; output=[]; cursor=0
    for start,end,token in atoms:
        if token not in keys:
            key=f'fs-{len(entries)}'; keys[token]=key
            entries.append(dict(key=key,token=token,label=symbol_label(token),meaning=symbol_meaning(token,slug,note)))
        output.extend([latex[cursor:start],r'\htmlClass{formula-symbol '+keys[token]+'}{'+token+'}'])
        cursor=end
    output.append(latex[cursor:])
    return ''.join(output),entries
