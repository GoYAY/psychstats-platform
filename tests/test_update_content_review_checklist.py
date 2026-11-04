import importlib.util
from pathlib import Path
import unittest
from tools.validate_review_examples import source_hash

ROOT = Path(__file__).resolve().parents[1]


class ReviewChecklistTests(unittest.TestCase):
    def setUp(self):
        path = ROOT/'tools/update_content_review_checklist.py'
        self.assertTrue(path.exists(),'Missing current-content review checklist tool')
        spec = importlib.util.spec_from_file_location('review_checklist',path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_current_execution_is_not_academic_approval(self):
        practice = dict(example_code='print(1)',your_data_code='d <- read.csv("your.csv")')
        term = dict(id='fixture',zh='示例',r_practice=practice)
        report = dict(term_id='fixture',source_sha256=source_hash(practice),verified=True,template_syntax_valid=True)
        text = self.module.render_checklist([term],[report])
        self.assertIn('待人工学术审核',text)
        self.assertIn('已执行通过',text)
        self.assertIn('仅语法通过',text)
        self.assertNotIn('学术已审核',text)

    def test_changed_source_does_not_reuse_success(self):
        term = dict(id='fixture',zh='示例',r_practice=dict(example_code='print(2)',your_data_code='x <- 1'))
        report = dict(term_id='fixture',source_sha256='stale',verified=True,template_syntax_valid=True)
        text = self.module.render_checklist([term],[report])
        self.assertIn('未验证／报告过期',text)
        self.assertNotIn('已执行通过',text)

    def test_no_practice_is_not_claimed_executed(self):
        text = self.module.render_checklist([dict(id='fixture',zh='示例')],[])
        self.assertNotIn('已执行通过',text)
