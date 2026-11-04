import json
import copy
import unittest
from pathlib import Path
from tools.export_next_preview import Tree

ROOT = Path(__file__).resolve().parents[2]


class PaperReportingTests(unittest.TestCase):
    def fixture(self, slug):
        return tuple(json.loads((ROOT / f'site/content/{folder}/{slug}.json').read_text(encoding='utf-8'))
                     for folder in ('analysis_cases', 'analysis_results'))

    def test_mediation_paths_preserve_actual_coefficients(self):
        from sitegen.paper_reporting import paper_data
        case, result = self.fixture('mediation')
        data = paper_data(case, result)
        paths = data['paths']
        self.assertEqual(len(paths), 3)
        self.assertAlmostEqual(paths[0]['estimate'], result['tables']['parameters'][0]['est'])
        self.assertTrue(any(p['label'] == 'c′' for p in paths))
        self.assertTrue(any(t['name'] == 'parameters' for t in data['tables']))

    def test_every_case_has_traceable_summary(self):
        from sitegen.paper_reporting import paper_data, render_paper_result
        for path in (ROOT / 'site/content/analysis_cases').glob('*.json'):
            case, result = self.fixture(path.stem)
            data = paper_data(case, result)
            self.assertTrue(data['tables'], path.stem)
            html = render_paper_result(case, result)
            self.assertIn('paper-results', html)
            self.assertIn('三线表', html)
            self.assertIn('analysis-logs/', html)

    def test_descriptive_summary_has_one_variable_row_and_statistic_columns(self):
        from sitegen.paper_reporting import paper_data
        case, result = self.fixture('describe')
        original = copy.deepcopy(result)
        data = paper_data(case, result)
        tables = [t for t in data['tables'] if t['name'] == 'descriptives']
        self.assertEqual(len(tables), 1, 'Description must not fall back to a vertical metrics log')
        self.assertEqual(tables[0]['columns'], ['variable', 'n', 'mean', 'sd', 'median', 'iqr'])
        self.assertEqual(tables[0]['rows'], [{'variable': '压力分数（stress）', 'n': 360,
            'mean': 48.61055555555556, 'sd': 8.064544619092855, 'median': 49,
            'iqr': 10.525000000000006}])
        self.assertFalse(any(t['name'] == 'metrics' for t in data['tables']))
        self.assertEqual(result, original, 'Rendering must not transpose or rewrite saved R output')

    def test_descriptive_table_renders_identical_values_and_layout_in_term_and_tutorial(self):
        from sitegen.paper_reporting import render_paper_result
        for source_page in (False, True):
            with self.subTest(source_page=source_page):
                html = render_paper_result(*self.fixture('describe'), source_page=source_page)
                primary = Tree(html).root.find(lambda n:'paper-primary' in n.attrs.get('class','').split())[0]
                self.assertEqual(len(primary.find(lambda n:n.tag == 'tbody')[0].find(lambda n:n.tag == 'tr')), 1)
                headers = primary.find(lambda n:n.tag == 'thead')[0].find(lambda n:n.tag == 'th')
                self.assertEqual(len(headers), 6)
                self.assertIn('研究变量', html)
                self.assertIn('48.61', html)
                self.assertIn('8.06', html)
                self.assertIn('10.53', html)
                self.assertEqual(len(primary.find(lambda n:n.tag == 'th' and n.attrs.get('scope') == 'row')), 1)
                for symbol in ('n','M','SD','Mdn','IQR'):
                    self.assertIn('<em>'+symbol+'</em>', html)
                if source_page:
                    self.assertEqual({n.attrs['data-analysis-locate'] for n in primary.find(lambda n:'data-analysis-locate' in n.attrs)}, {'n','mean','sd','median','iqr'})

    def test_group_descriptives_name_the_variable_without_transposing_groups(self):
        from sitegen.paper_reporting import paper_data, render_paper_result
        case, result = self.fixture('t-tests')
        table = next(t for t in paper_data(case, result)['tables'] if t['name'] == 'group_descriptives')
        self.assertEqual(table['columns'], ['variable','group','n','mean','sd'])
        self.assertEqual([r['variable'] for r in table['rows']], ['成绩增量（gain）'] * 2)
        self.assertEqual([r['group'] for r in table['rows']], ['retrieval','control'])
        self.assertEqual([r['n'] for r in table['rows']], [90,90])
        html = render_paper_result(case, result)
        self.assertIn('练习回忆组（retrieval）', html)
        self.assertIn('对照组（control）', html)

    def test_no_case_uses_vertical_statistic_value_paper_records(self):
        from sitegen.paper_reporting import paper_data
        for path in (ROOT/'site/content/analysis_cases').glob('*.json'):
            with self.subTest(case=path.stem):
                for table in paper_data(*self.fixture(path.stem))['tables']:
                    self.assertNotEqual(table['columns'], ['effect','value'])
                    self.assertNotEqual(table['columns'], ['index','value'])

    def test_correlations_separate_methods_and_keep_intervals_with_pearson(self):
        from sitegen.paper_reporting import paper_data, render_paper_result
        data=paper_data(*self.fixture('correlation'))
        table=next((t for t in data['tables'] if t['name']=='correlations'), None)
        self.assertIsNotNone(table,'Both correlation methods need their own result row')
        pearson,spearman=table['rows']
        self.assertEqual(pearson['method'],'Pearson r')
        self.assertEqual(spearman['method'],'Spearman ρ')
        self.assertAlmostEqual(spearman['coefficient'],-0.4337536367183371)
        self.assertEqual(spearman['p'],'<2.2e-16')
        self.assertIsNone(spearman.get('ci_lower'))
        self.assertIsNone(spearman.get('ci_upper'))
        self.assertAlmostEqual(pearson['ci_lower'],-0.5316812080277982)
        html=render_paper_result(*self.fixture('correlation'),source_page=True)
        self.assertIn('data-analysis-locate="rho"',html)
        self.assertIn('&lt;0.001',html)
        primary=Tree(html).root.find(lambda n:'paper-primary' in n.attrs.get('class','').split())[0]
        self.assertIn('analysis-numeric',primary.find(lambda n:n.tag=='thead')[0].find(lambda n:n.tag=='th')[-1].attrs.get('class',''))

    def test_partial_kendall_and_binary_correlations_have_distinct_test_rows(self):
        from sitegen.paper_reporting import paper_data
        table=next((t for t in paper_data(*self.fixture('correlation-types'))['tables'] if t['name']=='correlations'),None)
        self.assertIsNotNone(table)
        partial,kendall,point,phi=table['rows']
        self.assertEqual([r['method'] for r in table['rows']], ['偏相关 r（控制年龄）','Kendall τ','点二列相关 r','φ 系数'])
        self.assertEqual(partial['df'],357)
        self.assertAlmostEqual(partial['p'],1.4179015762027236e-19)
        self.assertEqual(kendall['p'],'<2.2e-16')
        for row in (kendall,point,phi):
            self.assertIsNone(row.get('df'),'Partial correlation df must not leak to other methods')
        for row in (point,phi):
            self.assertIsNone(row.get('p'),'No binary-correlation significance test was saved')
        self.assertAlmostEqual(point['coefficient'],-0.055213874296739816)

    def test_repeated_and_independent_rank_tests_do_not_share_a_p_value(self):
        from sitegen.paper_reporting import paper_data
        for slug,count in [('ranks',3),('friedman-sign',2)]:
            with self.subTest(case=slug):
                table=next((t for t in paper_data(*self.fixture(slug))['tables'] if t['name']=='tests'),None)
                self.assertIsNotNone(table)
                self.assertEqual(len(table['rows']),count)
        rows=next(t for t in paper_data(*self.fixture('ranks'))['tables'] if t['name']=='tests')['rows']
        self.assertEqual([r['p'] for r in rows],[0.0773185604444636,0.21016997022425016,3.3738958929743724e-05])

    def test_model_fit_has_one_model_row_and_fit_index_columns(self):
        from sitegen.paper_reporting import paper_data
        table=next(t for t in paper_data(*self.fixture('sem'))['tables'] if t['name']=='fit')
        self.assertEqual(len(table['rows']),1)
        self.assertIn('cfi',table['columns'])
        self.assertIn('rmsea',table['columns'])
        self.assertNotIn('value',table['columns'])

    def test_model_sample_summary_identifies_the_model_not_a_bare_count(self):
        from sitegen.paper_reporting import paper_data
        for slug in ('kmeans','hierarchical','lpa','linear-simple'):
            case,result=self.fixture(slug)
            table=next(t for t in paper_data(case,result)['tables'] if t['name']=='model_summary')
            self.assertIn('model',table['columns'])
            self.assertEqual(table['rows'][0]['model'],case['title'])

    def test_moderation_keeps_non_significant_interaction(self):
        from sitegen.paper_reporting import paper_data
        case, result = self.fixture('moderation')
        data = paper_data(case, result)
        interaction = next(p for p in data['paths'] if p['source'] == 'x:w')
        self.assertAlmostEqual(interaction['estimate'], result['metrics']['interaction'])
        self.assertGreater(interaction['p'], 0.05)

    def test_small_p_and_numeric_alignment(self):
        from sitegen.paper_reporting import render_paper_result
        html = render_paper_result(*self.fixture('mediation'))
        self.assertIn('&lt;0.001', html)
        self.assertIn('stat-significant', html)
        self.assertIn('analysis-numeric', html)

    def test_conditional_models_export_all_paths(self):
        from sitegen.paper_reporting import paper_data
        for slug in ('conditional-mediation', 'mediated-interaction'):
            data = paper_data(*self.fixture(slug))
            self.assertTrue(any(p['source'] == 'x:w' and p['target'] == 'm' for p in data['paths']))
            self.assertTrue(any(p['source'] == 'm' and p['target'] == 'y' for p in data['paths']))
            self.assertTrue(any(t['name'] == 'path_coefficients' for t in data['tables']))

    def test_equivalence_keeps_ninety_percent_interval(self):
        from sitegen.paper_reporting import render_paper_result
        html=render_paper_result(*self.fixture('equivalence'))
        self.assertIn('90% CI 下限',html)
        self.assertNotIn('95% CI 下限',html)

    def test_logistic_primary_interval_is_on_or_scale(self):
        from sitegen.paper_reporting import paper_data
        case,result=self.fixture('logistic')
        row=paper_data(case,result)['tables'][0]['rows'][0]
        self.assertEqual(row['estimate'],result['metrics']['odds_ratio'])
        self.assertEqual(row['ci_lower'],result['metrics']['ci_lower'])

    def test_standardized_profiles_keep_original_means_separate(self):
        from sitegen.paper_reporting import paper_data
        data=paper_data(*self.fixture('kmeans'))
        raw=next(t for t in data['tables'] if t['name']=='profiles')
        scaled=next(t for t in data['tables'] if t['name']=='standardized_profiles')
        self.assertNotEqual(raw['rows'][0]['stress'],scaled['rows'][0]['stress'])
        self.assertLess(abs(scaled['rows'][0]['stress']),3)

    def test_t_tests_include_standardized_effect_and_paired_change(self):
        from sitegen.paper_reporting import paper_data
        names={t['name'] for t in paper_data(*self.fixture('t-tests'))['tables']}
        self.assertTrue({'standardized_effects','group_descriptives','paired_change'}<=names)

    def test_named_p_metrics_use_same_threshold(self):
        from sitegen.paper_reporting import formatted
        for field in ('a_p','interaction_p','bartlett_p','comparison_p'):
            self.assertEqual(formatted(1e-10,'value',{'field_id':field}),'<0.001')

    def test_model_sample_counts_come_from_fitted_object(self):
        from sitegen.paper_reporting import paper_data
        data=paper_data(*self.fixture('multigroup'))
        rows=next(t for t in data['tables'] if t['name']=='model_summary')['rows']
        self.assertEqual([r['n'] for r in rows],[250,250])
        self.assertTrue(any(t['name']=='explained_variance' for t in data['tables']))

    def test_multiple_group_loading_figures_label_both_groups(self):
        for slug in ('invariance','multigroup'):
            svg=(ROOT/f'site/assets/paper-results/{slug}-loadings.svg').read_text(encoding='utf-8')
            self.assertIn('组1',svg)
            self.assertIn('组2',svg)

    def test_console_p_inequality_is_bold_when_significance_is_known(self):
        from sitegen.paper_reporting import paper_significant_columns
        self.assertTrue({'Estimate','p'}<=paper_significant_columns({'Estimate':1.0,'p':'< 2.2e-16'}))
        self.assertFalse(paper_significant_columns({'Estimate':1.0,'p':'> 0.001'}))


if __name__ == '__main__':
    unittest.main()
