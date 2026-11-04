import copy
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class AnalysisCatalogTests(unittest.TestCase):
    def test_nonfinite_and_inverted_displayed_table_cells_are_rejected(self):
        case={'id':'test','annotations':[],'report_template':''}
        base={'case_id':'test','status':'valid','exit_code':0,'script_sha256':'a','config_sha256':'b','data_sha256':{},'session_info':'R','stdout':'ran','metrics':{}}
        for tables in ({'parameters':[{'est':math.inf}]},{'slopes':[{'ci_lower':2,'ci_upper':1}]},{'parameters':['not a row']}):
            with self.subTest(tables=tables):
                self.assertTrue(self.api().validate_result(case,{**base,'tables':tables}))

    def test_catalog_case_membership_rejects_missing_and_wrong_unit(self):
        api = self.api()
        catalog = {'units':[{'id':'a','case_ids':['one']}], 'term_routes':[]}
        for cases in ({}, {'one':{'id':'one','unit_id':'b'}}, {'one':{'id':'one','unit_id':'a'},'two':{'id':'two','unit_id':'a'}}):
            with self.subTest(cases=cases), self.assertRaises(ValueError):
                api.validate_catalog_cases(catalog,cases)

    def test_malformed_metric_payload_returns_validation_errors(self):
        case = {'id':'test','annotations':[],'report_template':''}
        for metrics in (None, {'ci_lower':'not numeric','ci_upper':2}):
            with self.subTest(metrics=metrics):
                self.assertTrue(self.api().validate_result(case, {'case_id':'test','metrics':metrics}))

    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('sitegen.analysis_catalog'),
                             'analysis catalog implementation is missing')
        from sitegen import analysis_catalog
        return analysis_catalog

    def test_catalog_routes_every_existing_term_and_covers_advanced_models(self):
        api = self.api()
        ids = {p.stem for p in (ROOT / 'site/content/drafts').glob('*.json')}
        catalog = api.load_analysis_catalog(ROOT / 'site/content/analysis_catalog.json', ids)
        self.assertEqual(ids, {r['term_id'] for r in catalog['term_routes']})
        units = {u['id'] for u in catalog['units']}
        self.assertTrue({'sem', 'lpa', 'lca', 'manova', 'growth', 'latent-interaction'} <= units)
        self.assertNotIn('latent-variable', units)

    def test_duplicate_units_are_rejected(self):
        api = self.api()
        value = {'units': [{'id': 'a'}, {'id': 'a'}], 'term_routes': []}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'catalog.json'
            p.write_text(json.dumps(value), encoding='utf-8')
            with self.assertRaises(ValueError):
                api.load_analysis_catalog(p, set())

    def test_invalid_result_is_not_treated_as_verified(self):
        api = self.api()
        case = {'id': 'test', 'annotations': [], 'report_template': '平均 {mean:.2f}'}
        bad = {'case_id': 'test', 'exit_code': 0, 'status': 'valid', 'metrics': {'mean': math.nan}}
        errors = api.validate_result(case, bad)
        self.assertTrue(errors)
        self.assertTrue(any('finite' in e for e in errors))

    def test_missing_report_metric_and_inverted_interval_are_rejected(self):
        api = self.api()
        case = {'id': 'test', 'annotations': [], 'report_template': '{estimate:.2f}'}
        result = {'case_id': 'test', 'exit_code': 0, 'status': 'valid',
                  'script_sha256': 'a', 'config_sha256': 'b', 'data_sha256': {},
                  'session_info': 'R actual', 'stdout': 'actual output',
                  'metrics': {'ci_lower': 2, 'ci_upper': 1}}
        errors = api.validate_result(case, result)
        self.assertTrue(any('estimate' in e for e in errors))
        self.assertTrue(any('interval' in e for e in errors))
