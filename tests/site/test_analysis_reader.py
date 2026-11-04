import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class AnalysisReaderTests(unittest.TestCase):
    def test_hierarchical_tree_uses_computed_merge_heights(self):
        case=json.loads((ROOT / 'site/content/analysis_cases/hierarchical.json').read_text(encoding='utf-8'))
        result=json.loads((ROOT / 'site/content/analysis_results/hierarchical.json').read_text(encoding='utf-8'))
        html=self.api().render_analysis_case(case,result,{})
        self.assertIn('class="analysis-dendrogram"',html)
        self.assertIn('Ward.D2',html)

    def test_download_instructions_include_actual_packages_and_working_directory(self):
        case,result=self.fixture()
        html=self.api().render_analysis_case(case,result,{})
        self.assertIn('jsonlite',html)
        self.assertIn('install.packages',html)
        self.assertIn('工作目录',html)
        case=json.loads((ROOT / 'site/content/analysis_cases/latent-interaction.json').read_text(encoding='utf-8'))
        result=json.loads((ROOT / 'site/content/analysis_results/latent-interaction.json').read_text(encoding='utf-8'))
        html=self.api().render_analysis_case(case,result,{})
        self.assertIn('semTools',html)
        self.assertIn('lavaan',html)

    def test_global_search_includes_method_name_and_case_unit_id(self):
        api = self.api()
        case, _ = self.fixture()
        catalog = {'units':[{'id':'describe','title':'描述统计与分布'}]}
        row = api.analysis_search_entries({'describe':case},catalog)[0]
        self.assertIn('描述统计与分布',row['aliases'])
        self.assertIn('describe',row['aliases'])

    def test_shared_term_report_uses_actual_artifact_and_rejects_stale_version(self):
        api = self.api()
        case, result = self.fixture()
        catalog = {'term_routes':[{'term_id':'test-term','mode':'tutorial','unit_ids':['describe']}]}
        self.assertEqual(api.report_text(case,result), api.analysis_report_for_term('test-term',catalog,{'describe':case},{'describe':result}))
        result['script_sha256'] = 'stale'
        with self.assertRaises(ValueError):
            api.analysis_report_for_term('test-term',catalog,{'describe':case},{'describe':result})

    def test_index_card_names_the_method_not_only_its_question(self):
        api = self.api()
        case, _ = self.fixture()
        catalog = {'units':[{'id':'describe','title':'描述统计与分布','group':'foundations','order':0}]}
        html = api.render_analysis_index(catalog, {'describe':case})
        self.assertIn('描述统计与分布', html)

    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('sitegen.analysis_reader'), 'reader missing')
        from sitegen import analysis_reader
        return analysis_reader

    def fixture(self):
        case = json.loads((ROOT / 'site/content/analysis_cases/describe.json').read_text(encoding='utf-8'))
        result = json.loads((ROOT / 'site/content/analysis_results/describe.json').read_text(encoding='utf-8'))
        return case, result

    def test_question_precedes_real_output_and_report_uses_real_numbers(self):
        api = self.api()
        case, result = self.fixture()
        html = api.render_analysis_case(case, result, {'quantile': '分位数'})
        self.assertLess(html.index('你可能会问'), html.index('真实运行输出'))
        self.assertIn(format(result['metrics']['mean'], '.2f'), html)
        self.assertIn('data-analysis-field="mean"', html)
        self.assertIn('data-analysis-meaning="mean"', html)
        self.assertIn('aria-pressed="false"', html)
        self.assertIn('完整控制台输出', html)
        self.assertIn('../terms/quantile.html', html)

    def test_missing_results_are_not_published_as_working_tutorials(self):
        api = self.api()
        case, result = self.fixture()
        with self.assertRaises(ValueError):
            api.render_analysis_case(case, {}, {})

    def test_parameter_tables_are_visible_without_opening_console(self):
        api = self.api()
        case, result = self.fixture()
        result['tables'] = {'parameters': [{'lhs':'factor_one','rhs':'item_one','estimate':0.7}]}
        html = api.render_analysis_case(case, result, {})
        self.assertIn('factor_one', html)
        self.assertLess(html.index('factor_one'), html.index('完整控制台输出'))

    def test_index_uses_cases_not_unfinished_catalog_placeholders(self):
        api = self.api()
        case, _ = self.fixture()
        catalog = {'units': [{'id':'describe','title':'描述','group':'foundations','order':0},
                             {'id':'sem','title':'结构方程','group':'structural-equation-modeling','order':1}]}
        html = api.render_analysis_index(catalog, {'describe':case})
        self.assertIn('analyses/describe.html', html)
        self.assertNotIn('analyses/sem.html', html)

    def test_untrusted_text_is_escaped_and_search_has_distinct_route(self):
        api = self.api()
        case, result = self.fixture()
        case['question'] = '<script>bad()</script>'
        self.assertNotIn('<script>bad()', api.render_analysis_case(case, result, {}))
        row = api.analysis_search_entries({'describe':case})[0]
        self.assertEqual('analysis', row['kind'])
        self.assertEqual('analyses/describe.html', row['url'])
