import json
from pathlib import Path
import unittest
from tests.site.test_frontend_assets import run_node
from sitegen.build import _search_index
from sitegen.render import render_term
from sitegen.math_render import render_formulas

ROOT = Path(__file__).resolve().parents[2]


class SearchNavigationV4Tests(unittest.TestCase):
    def test_density_integral_with_bounds_can_be_rendered(self):
        try:
            markup = render_formulas({'probability-density':r'P(a<X<b)=\int_a^b f(x)\,dx'})
        except ValueError as error:
            self.fail(str(error))
        self.assertIn('katex',markup['probability-density'])

    def test_search_index_contains_readable_body_but_not_r_source(self):
        term = {'id':'a','zh':'甲','sections':[{'heading':'如何判断','body':'用 Q-Q 图检查残差'}],
                'formula':{'note':'不能由拟合推断因果'}, 'r_practice':{'example_code':'SECRET_CODE'}}
        item = _search_index([term])[0]
        self.assertIn('Q-Q 图', item.get('body_text',''))
        self.assertIn('因果', item['body_text'])
        self.assertNotIn('SECRET_CODE', item['body_text'])

    def test_global_search_ranks_names_ahead_of_mentions_and_allows_topic_body_search(self):
        result = run_node("""
          const s=require('./site/assets/search.js');
          const terms=[{id:'n',zh:'正态分布',topic:'foundations',body_text:'查看直方图'},
                       {id:'h',zh:'直方图',en:'Histogram',topic:'data-preparation',body_text:'分布形状'},
                       {id:'r',zh:'回归',topic:'regression',body_text:'检查直方图'}];
          console.log(JSON.stringify({global:s.searchTerms('直方图',{},terms).map(t=>t.id),
          scoped:s.searchTerms('直方图',{topic:'foundations'},terms).map(t=>t.id),
          empty:s.searchTerms('不存在',{},terms)}));
        """)
        self.assertEqual(result, {'global':['h','n','r'],'scoped':['n'],'empty':[]})

    def test_search_includes_visible_reading_aids_and_r_checks(self):
        terms = [json.loads((ROOT/'site/content/drafts'/f'{slug}.json').read_text(encoding='utf-8'))
                 for slug in ('bartlett-test','box-plot')]
        body = ' '.join(item['body_text'] for item in _search_index(terms))
        self.assertIn('先计算相关矩阵行列式的对数', body)
        self.assertIn('上下铰链为', body)
        item = _search_index([{'id':'a','r_practice':{'assumption_checks':['检查独立观测'],
                                                   'example_code':'SECRET_CODE'}}])[0]
        self.assertIn('检查独立观测', item['body_text'])
        self.assertNotIn('SECRET_CODE', item['body_text'])

    def test_topic_body_search_recognizes_known_aliases(self):
        result = run_node("""
          const s=require('./site/assets/search.js');
          const terms=[{id:'normal',zh:'正态分布',topic:'foundations',body_text:'查看 Q-Q 图'},
                       {id:'qq',zh:'Q-Q 图',aliases:['QQ图'],topic:'data-preparation'}];
          console.log(JSON.stringify(s.searchTerms('QQ图',{topic:'foundations'},terms).map(t=>t.id)));
        """)
        self.assertEqual(result, ['normal'])

    def test_term_has_topic_breadcrumb_and_ordered_neighbors(self):
        term = json.loads((ROOT/'site/content/drafts/significance-level.json').read_text(encoding='utf-8'))
        html = render_term(term, preview=True, topic_label='效应量与假设检验',
                           previous_term={'id':'null-hypothesis','zh':'零假设'},
                           next_term={'id':'p-value','zh':'p 值'})
        self.assertIn('href="../index.html?topic=hypothesis-testing"', html)
        self.assertIn('aria-label="当前位置"', html)
        self.assertIn('data-direction="previous" href="null-hypothesis.html"', html)
        self.assertIn('data-direction="next" href="p-value.html"', html)
        self.assertLess(html.index('lang="en"'), html.index('aria-label="当前位置"'))

    def test_common_supporting_concepts_have_explanation_targets(self):
        names = {name for p in (ROOT/'site/content/drafts').glob('*.json')
                 for t in [json.loads(p.read_text(encoding='utf-8'))]
                 for name in [t['zh'],*t.get('aliases',[])]}
        for name in ['直方图','Q-Q 图','偏态','极端值','分位数','概率密度','向量','矩阵','转置','协方差矩阵','收敛','似然','过拟合']:
            self.assertIn(name,names)


if __name__ == '__main__':
    unittest.main()
