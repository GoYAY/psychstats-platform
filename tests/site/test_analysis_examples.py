import json
import unittest
from pathlib import Path
from sitegen.analysis_catalog import load_analysis_cases, validate_result

ROOT = Path(__file__).resolve().parents[2]


class AnalysisExampleTests(unittest.TestCase):
    def test_coverage_requires_corrected_and_actual_followup_outputs(self):
        cases=load_analysis_cases(ROOT / 'site/content/analysis_cases')
        self.assertIn('mixed-design',cases)
        self.assertIn('categorical-gof',cases)
        hierarchy=json.loads((ROOT / 'site/content/analysis_results/hierarchical.json').read_text(encoding='utf-8'))
        self.assertTrue({'dendrogram_merges','leaf_order'}<=hierarchy['tables'].keys())
        proportions=json.loads((ROOT / 'site/content/analysis_results/proportions.json').read_text(encoding='utf-8'))
        self.assertTrue({'single_ci_lower','single_ci_upper'}<=proportions['metrics'].keys())
        for slug,metrics,tables in (
            ('repeated',{'gg_epsilon','gg_p','gg_df1','gg_df2','mauchly_p'}, {'sphericity_corrections','paired_comparisons'}),
            ('mixed-design',{'interaction_F','interaction_gg_p','group_F'}, {'mixed_effects','change_comparison'}),
            ('manova',{'adjusted_pillai','adjusted_F'}, {'univariate_followup','adjusted_pairwise_comparisons','coefficients'}),
            ('ancova',set(),{'adjusted_means'}),
            ('categorical-gof',{'p'}, {'observed_expected'})):
            with self.subTest(case=slug):
                result=json.loads((ROOT / 'site/content/analysis_results' / (slug+'.json')).read_text(encoding='utf-8'))
                self.assertTrue(metrics<=result['metrics'].keys())
                self.assertTrue(tables<=result['tables'].keys())

    def test_lpa_checks_a_second_initialization_and_welch_posthoc_is_not_pooled(self):
        lpa=json.loads((ROOT / 'site/content/analysis_results/lpa.json').read_text(encoding='utf-8'))
        self.assertTrue({'restart_same_structure','restart_bic_gap','restart_ari'} <= lpa['metrics'].keys())
        welch=json.loads((ROOT / 'site/content/analysis_results/welch.json').read_text(encoding='utf-8'))
        self.assertIn('pairwise_welch_holm',welch['tables'])

    def test_efa_distinguishes_pattern_structure_and_screening_diagnostics(self):
        result = json.loads((ROOT / 'site/content/analysis_results/efa.json').read_text(encoding='utf-8'))
        self.assertTrue({'kmo','bartlett_p'} <= result['metrics'].keys())
        self.assertTrue({'loadings','structure','factor_correlations'} <= result['tables'].keys())

    def test_necessary_method_variants_are_not_hidden_by_group_coverage(self):
        cases = load_analysis_cases(ROOT / 'site/content/analysis_cases')
        required = {'intervals-variance', 'correlation-types', 't-single',
                    'binary-paired', 'factorial-blocks', 'friedman-sign',
                    'reliability-omega', 'selection-blocks', 'linear-simple',
                    'sampling-cluster', 'design-invalid'}
        self.assertTrue(required <= cases.keys(), 'missing variants: ' + str(sorted(required-cases.keys())))

    def test_mixture_methods_have_complete_linkable_glossary_entries(self):
        for slug in ('latent-profile-analysis', 'latent-class-analysis', 'ancova', 'mancova'):
            with self.subTest(term=slug):
                path = ROOT / 'site/content/drafts' / (slug + '.json')
                self.assertTrue(path.is_file(), 'missing glossary entry')
                value = json.loads(path.read_text(encoding='utf-8'))
                self.assertTrue(value['plain_example'] and value['sections'])
                self.assertEqual(4, len(value['quiz']['option_explanations']))

    def test_every_catalog_method_has_a_runnable_verified_walkthrough(self):
        catalog = json.loads((ROOT / 'site/content/analysis_catalog.json').read_text(encoding='utf-8'))
        cases = load_analysis_cases(ROOT / 'site/content/analysis_cases')
        represented = {case['unit_id'] for case in cases.values()}
        missing = {unit['id'] for unit in catalog['units']} - represented
        self.assertFalse(missing, 'unimplemented methods: ' + ', '.join(sorted(missing)))
        for slug, case in cases.items():
            with self.subTest(case=slug):
                path = ROOT / 'site/content/analysis_results' / (slug + '.json')
                self.assertTrue(path.exists(), 'real R artifact missing')
                result = json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual([], validate_result(case, result))
                self.assertTrue(case['question'] and case['diagnostics'] and case['annotations'])
                self.assertTrue((ROOT / case['script']).exists())
