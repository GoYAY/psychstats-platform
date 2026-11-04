import json
from pathlib import Path
import unittest
from sitegen.render import render_term, _linked_text
from sitegen.math_render import render_formulas
from sitegen.reading_aids import symbol_label, formula_aid
from sitegen.build import _quiz_bank

ROOT = Path(__file__).resolve().parents[2]


class ReadingInteractionTests(unittest.TestCase):
    def test_common_arithmetic_is_not_an_interactive_statistical_symbol(self):
        annotated, entries = formula_aid(r'y=b_0+b_1x-\frac{a}{\sqrt{n}}\times z\cdot w', 'test')
        self.assertFalse({'+','-','=','√','分数线','times','·'} & {e['label'] for e in entries})
        self.assertIn(r'\sqrt', annotated)
        self.assertIn(r'\frac', annotated)

    def test_formula_meanings_link_without_nested_interactive_controls(self):
        html = render_term(self.term('simple-linear-regression'), preview=True, available_names={'intercept':'截距'})
        import re
        buttons = re.findall(r'<button\b[^>]*>.*?</button>', html, re.S)
        self.assertTrue(all('<a ' not in button for button in buttons))
        formula = html.split('<ol class="formula-keys">')[1].split('</ol>')[0]
        self.assertIn('href="intercept.html"', formula)

    def test_fit_alias_does_not_link_fitted_values_or_fit_indices(self):
        result = _linked_text('拟合、拟合值、拟合指数、模型拟合', '', {'model-fit':['模型拟合','拟合']})
        self.assertEqual(result.count('href="model-fit.html"'), 2)

    def test_four_supporting_terms_are_full_pages_in_curriculum(self):
        curriculum = json.loads((ROOT/'site/content/curriculum.json').read_text(encoding='utf-8'))
        all_ids = [slug for topic in curriculum['topics'] for slug in topic['terms']]
        for slug in ['path-coefficient','intercept','model-fit','causal-relationship']:
            self.assertIn(slug, all_ids)
            term = self.term(slug)
            for field in ['real_question','plain_example','sections','quiz','sources','visual_steps']:
                self.assertTrue(term.get(field), (slug,field))

    def term(self, slug):
        return json.loads((ROOT/'site/content/drafts'/f'{slug}.json').read_text(encoding='utf-8'))

    def test_regression_has_specific_copyable_agent_prompt(self):
        html = render_term(self.term('simple-linear-regression'), preview=True)
        self.assertIn('你可以这样告诉 AI Agent', html)
        self.assertIn('id="agent-prompt"', html)
        self.assertIn('data-copy="#agent-prompt"', html)
        self.assertIn('不能推断因果', html)

    def test_emphasis_is_not_literal_markup_and_retains_links(self):
        t = self.term('simple-linear-regression')
        t['sections'] = [{'heading':'怎样读','body':'检查残差，不能推断因果。', 'emphasis':['不能推断因果']}]
        html = render_term(t,preview=True,available_names={'residual':'残差'})
        self.assertIn('<strong class="key-point">不能推断因果</strong>', html)
        self.assertIn('href="residual.html"', html)

    def test_display_decimals_gain_zero_but_urls_and_versions_do_not_change(self):
        t = self.term('simple-linear-regression')
        t['plain_explanation'] = 'p=.05，r=−.37；版本1.2.3，网址https://example.org/.5。'
        t['plain_example'] = ''
        html = render_term(t,preview=True)
        self.assertIn('p=0.05，r=−0.37',html)
        self.assertIn('1.2.3',html)
        self.assertIn('https://example.org/.5',html)

    def test_formula_has_symbol_targets_and_meaning_for_both_coefficients(self):
        t = self.term('simple-linear-regression')
        markup = render_formulas({t['id']:t['formula']['latex']})[t['id']]
        html = render_term(t,preview=True,formula_markup=markup)
        self.assertIn('formula-symbol',html)
        self.assertIn('formula-key',html)
        self.assertIn('截距',html)
        self.assertIn('斜率',html)
        self.assertIn('formula-reading.js',html)

    def test_every_formula_and_r_page_has_appropriate_reading_aids(self):
        for path in (ROOT/'site/content/drafts').glob('*.json'):
            t = json.loads(path.read_text(encoding='utf-8'))
            html = render_term(t,preview=True)
            if t.get('formula',{}).get('latex'):
                self.assertIn('formula-key',html,t['id'])
                self.assertIn('formula-logic',html,t['id'])
            if t.get('r_practice'):
                self.assertIn('id="agent-prompt"',html,t['id'])

    def test_short_latex_root_and_fraction_remain_renderable(self):
        try:
            result=render_formulas({'root':r'\frac{\sigma}{\sqrt n}','short':r'\frac1m\sum_i Q_i'})
        except ValueError as error:
            self.fail(str(error))
        self.assertEqual(set(result),{'root','short'})

    def test_cases_environment_is_not_annotated_as_variable_letters(self):
        t=self.term('dummy-coding')
        try:
            markup=render_formulas({t['id']:t['formula']['latex']})[t['id']]
        except ValueError as error:
            self.fail(str(error))
        self.assertIn('katex',markup)

    def test_symbol_labels_preserve_greek_indices_and_vector_notation(self):
        self.assertEqual(symbol_label(r'\beta_1'),'β_1')
        self.assertEqual(symbol_label(r'\mathbf X'),'X')
        self.assertEqual(symbol_label(r'\boldsymbol\eta'),'η')
        self.assertEqual(symbol_label(r'\hat\beta_3'),'β̂_3')

    def test_direct_and_total_effect_prime_are_distinct_symbols(self):
        entries=formula_aid("c=c'+ab",'total-effect')[1]
        self.assertEqual([e['label'] for e in entries if e['label'].startswith('c')],['c',"c'"])

    def test_practice_bank_also_formats_decimals(self):
        t=self.term('simple-linear-regression')
        t['quiz']['options'][0]='p=.05'
        self.assertEqual(_quiz_bank([t])[0]['options'][0],'p=0.05')

    def test_contextual_variable_count_and_partial_correlations_are_specific(self):
        t=self.term('bartlett-test')
        entries=formula_aid(t['formula']['latex'],t['id'],t['formula']['note'])[1]
        self.assertIn('变量个数',next(e['meaning'] for e in entries if e['label']=='p'))
        t=self.term('partial-correlation')
        entries=formula_aid(t['formula']['latex'],t['id'],t['formula']['note'])[1]
        self.assertIn('控制Z',entries[0]['meaning'])
        self.assertEqual(symbol_label(r'r_{XY\cdot Z}'),'r_XY·Z')

    def test_copyable_r_code_preserves_filenames_and_string_literals(self):
        t=self.term('simple-linear-regression')
        t['r_practice']['example_code']='path <- ".5.csv"\nlabel <- "p=.05"'
        html=render_term(t,preview=True)
        self.assertIn('path &lt;- &quot;.5.csv&quot;',html)
        self.assertIn('label &lt;- &quot;p=.05&quot;',html)

    def test_sobel_denominator_uses_squared_path_standard_errors(self):
        t=self.term('sobel-test')
        entries=formula_aid(t['formula']['latex'],t['id'],t['formula']['note'])[1]
        for label in ['s_a^2','s_b^2']:
            self.assertIn('标准误的平方',next(e['meaning'] for e in entries if e['label']==label))

    def test_likelihood_hat_distinguishes_estimate_from_candidate_parameters(self):
        t=self.term('maximum-likelihood')
        entries=formula_aid(t['formula']['latex'],t['id'],t['formula']['note'])[1]
        self.assertIn('估计',next(e['meaning'] for e in entries if e['label']=='θ̂'))

    def test_output_and_report_emphasis_is_rendered_without_modifying_code(self):
        t=self.term('sem')
        html=render_term(t,preview=True)
        self.assertIn('class="output-interpretation"',html)
        self.assertIn('class="report-example"',html)
        self.assertIn('class="question-quote"',html)
        self.assertIn('0.997',html)

    def test_multiple_regression_report_includes_its_coefficient_interval(self):
        html=render_term(self.term('multiple-regression'),preview=True)
        report=html.split('class="report-example"',1)[1].split('</aside>',1)[0]
        self.assertIn('−0.467',report)
        self.assertIn('−0.273',report)
        self.assertNotIn('见 confint',report)
