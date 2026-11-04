import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R = Path('C:/Program Files/R/R-4.5.1/bin/Rscript.exe')


class AnalysisRunnerTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.run_analysis_examples'), 'runner missing')
        from tools import run_analysis_examples
        return run_analysis_examples

    def case(self, script):
        return {'id': 'test', 'script': str(script), 'data_files': [], 'annotations': [],
                'report_template': '{mean:.2f}'}

    def test_real_execution_and_script_change_invalidates_artifact(self):
        api = self.api()
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as directory:
            p = Path(directory) / 'test.R'
            p.write_text('cat("REAL EXECUTION\\n"); jsonlite::write_json(list(metrics=list(mean=2)), "result.json", auto_unbox=TRUE)', encoding='utf-8')
            case = self.case(p)
            result = api.run_case(case, rscript=R)
            self.assertEqual('valid', result['status'])
            self.assertEqual(2, result['metrics']['mean'])
            self.assertIn('REAL EXECUTION', result['stdout'])
            self.assertTrue(api.is_current(case, result))
            p.write_text('stop("changed")', encoding='utf-8')
            self.assertFalse(api.is_current(case, result))

    def test_failure_does_not_become_success(self):
        api = self.api()
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as directory:
            p = Path(directory) / 'fail.R'
            p.write_text('stop("intentional failure")', encoding='utf-8')
            result = api.run_case(self.case(p), rscript=R)
            self.assertEqual('failed', result['status'])
            self.assertIn('intentional failure', result['stderr'])

    def test_missing_executable_is_recorded(self):
        api = self.api()
        result = api.run_case(self.case(ROOT / 'examples/r/output_reading/describe.R'), rscript=ROOT / 'no-R.exe')
        self.assertEqual('failed', result['status'])

    def test_timeout_missing_package_and_invalid_fit_cannot_report_success(self):
        api = self.api()
        scripts = [
            ('Sys.sleep(3)', 1, None, 'failed'),
            ('library(psych_reader_deliberately_absent_package)', 10, None, 'failed'),
            ('jsonlite::write_json(list(metrics=list(mean=2),valid=FALSE),"result.json",auto_unbox=TRUE)', 10, '模型未收敛，不能报告成功', 'diagnostic-demo'),
        ]
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as directory:
            p = Path(directory) / 'edge.R'
            for code, timeout, reason, expected in scripts:
                with self.subTest(expected=expected,code=code):
                    p.write_text(code,encoding='utf-8')
                    case = self.case(p)
                    if reason:
                        case['invalid_reason'] = reason
                    self.assertEqual(expected,api.run_case(case,rscript=R,timeout=timeout)['status'])

    def test_data_changes_invalidate_artifact(self):
        api = self.api()
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as directory:
            p = Path(directory) / 'data.R'
            csv = Path(directory) / 'values.csv'
            p.write_text('d<-read.csv("values.csv");jsonlite::write_json(list(metrics=list(mean=mean(d$x))),"result.json",auto_unbox=TRUE)',encoding='utf-8')
            csv.write_text('x\n1\n3\n',encoding='utf-8')
            case = self.case(p); case['data_files']=[str(csv)]
            result = api.run_case(case,rscript=R)
            self.assertEqual('valid',result['status'])
            csv.write_text('x\n1\n9\n',encoding='utf-8')
            self.assertFalse(api.is_current(case,result))

    def test_outside_workspace_script_is_rejected(self):
        api = self.api()
        with self.assertRaises(ValueError):
            api.run_case(self.case(Path('C:/Windows/unknown.R')), rscript=R)
