import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReviewValidationTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'tools/validate_review_examples.py'
        self.assertTrue(path.exists(), 'Missing isolated preview validator')
        spec = importlib.util.spec_from_file_location('review_validator', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def practice(self, code='print(2)', template='x <- 1', validation=''):
        return dict(example_code=code, your_data_code=template,
                    validation_code=validation, packages=[])

    def test_actual_r_success_and_template_parse_only(self):
        result = self.module.validate_practice('fixture', self.practice())
        self.assertTrue(result['verified'])
        self.assertTrue(result['template_syntax_valid'])
        self.assertEqual(result['template_execution'], 'not-run-user-data-required')
        self.assertIn('2', result['stdout'])

    def test_failed_fit_is_not_verified(self):
        result = self.module.validate_practice('fixture', self.practice('stop("fit failed")'))
        self.assertFalse(result['verified'])
        self.assertIn('fit failed', result['stderr'])

    def test_nonfinite_metric_assertion_is_not_verified(self):
        result = self.module.validate_practice('fixture', self.practice(
            'estimate <- NaN', validation='stopifnot(is.finite(estimate))'))
        self.assertFalse(result['verified'])

    def test_invalid_template_does_not_pass(self):
        result = self.module.validate_practice('fixture', self.practice(template='x <-'))
        self.assertFalse(result['template_syntax_valid'])

    def test_missing_package_does_not_pass(self):
        practice = self.practice()
        practice['packages'] = ['psych_site_missing_package_fixture']
        self.assertFalse(self.module.validate_practice('fixture', practice)['verified'])

    def test_timeout_does_not_pass(self):
        result = self.module.validate_practice('fixture', self.practice('Sys.sleep(5)'), timeout=0.1)
        self.assertFalse(result['verified'])
        self.assertIn('timeout', result['stderr'])

    def test_source_change_invalidates_report(self):
        p = self.practice()
        result = self.module.validate_practice('fixture', p)
        self.assertTrue(self.module.report_matches(p, result))
        p['example_code'] = 'print(3)'
        self.assertFalse(self.module.report_matches(p, result))


if __name__ == '__main__':
    unittest.main()
