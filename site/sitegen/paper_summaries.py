"""Research-unit rows built from saved evidence, never from newly fitted models."""
import re


def printed_p(console, title):
    """Read only the named test block; retain printed upper bounds as bounds."""
    block=next((b for b in console.split('\n\n\t') if title in b), '')
    match=re.search(r'p-value\s*([<=>])\s*([0-9.eE+-]+)', block)
    if not match:
        return None
    return match[1]+match[2] if match[1]!='=' else float(match[2])


def method_results(case, result):
    m=result['metrics'];slug=case['id'];console=result.get('stdout','')
    pair='压力（stress）与幸福感（well_being）'
    if slug=='correlation':
        rows=[{'variables':pair,'method':'Pearson r','coefficient':m['r'],'n':m['n'],
               'ci_lower':m['ci_lower'],'ci_upper':m['ci_upper'],'p':m['p']},
              {'variables':pair,'method':'Spearman ρ','coefficient':m['rho'],'n':m['n'],
               'p':printed_p(console,"Spearman's rank correlation rho")}]
        sources=[{'coefficient':'r','n':'n','ci_lower':'ci_lower','ci_upper':'ci_upper','p':'p'},
                 {'coefficient':'rho','n':'n'}]
    elif slug=='correlation-types':
        rows=[{'variables':pair,'method':'偏相关 r（控制年龄）','coefficient':m['partial_r'],
               'df':m['df'],'p':m['partial_p']},
              {'variables':pair,'method':'Kendall τ','coefficient':m['kendall_tau'],
               'p':printed_p(console,"Kendall's rank correlation tau")},
              {'variables':'二元响应（binary）与幸福感（well_being）','method':'点二列相关 r','coefficient':m['point_biserial']},
              {'variables':'二元响应（binary）与二元响应（another）','method':'φ 系数','coefficient':m['phi']}]
        sources=[{'coefficient':'partial_r','df':'df','p':'partial_p'},
                 {'coefficient':'kendall_tau'},{'coefficient':'point_biserial'},{'coefficient':'phi'}]
    elif slug=='ranks':
        rows=[{'variables':'独立组 a 与 b','method':'Wilcoxon 秩和检验','statistic_name':'W',
               'statistic':m['W'],'estimate':m['shift'],'p':m['p']},
              {'variables':'独立组 a、b、c','method':'Kruskal–Wallis 检验','p':m['kw_p']},
              {'variables':'同一人的 before 与 after','method':'Wilcoxon 符号秩检验','p':m['paired_p']}]
        sources=[{'statistic':'W','estimate':'shift','p':'p'},{'p':'kw_p'},{'p':'paired_p'}]
    elif slug=='friedman-sign':
        rows=[{'variables':'同一人的三种条件','method':'Friedman 检验','statistic_name':'χ²',
               'statistic':m['chi_squared'],'df':m['df'],'p':m['p']},
              {'variables':'同一人的 B − A','method':'符号检验','n':m['nonzero_pairs'],'p':m['sign_p']}]
        sources=[{'statistic':'chi_squared','df':'df','p':'p'},{'n':'nonzero_pairs','p':'sign_p'}]
    else:
        return None
    correlation=slug in {'correlation','correlation-types'}
    order=['variables','method','coefficient','n','df','ci_lower','ci_upper','p'] if correlation else ['variables','method','statistic_name','statistic','df','n','estimate','p']
    columns=[k for k in order if any(k in r for r in rows)]
    return {'name':'correlations' if correlation else 'tests',
            'title':'各变量对与相关方法的结果' if correlation else '各研究比较与检验结果',
            'columns':columns,'rows':rows,'source_fields':sources}


def metric_summary(case, records):
    """A fallback has a case/model row and separate columns, not one row per number."""
    labels={r['field_id']:r['effect'] for r in records}
    values={r['field_id']:r['value'] for r in records}
    return {'name':'metrics','title':'本次分析的统计指标汇总',
            'columns':['analysis',*values], 'rows':[{'analysis':case['title'],**values}],
            'column_labels':labels,'source_fields':[{k:k for k in values}]}
