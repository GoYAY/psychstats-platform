import json
import unittest
from pathlib import Path
from sitegen.render import render_term

ROOT = Path(__file__).resolve().parents[2]


class ContentCorrectionTests(unittest.TestCase):
    def read(self, slug):
        return json.loads((ROOT / 'site/content/drafts' / f'{slug}.json').read_text(encoding='utf-8'))

    def test_regression_interpretation_includes_gender_and_units(self):
        html = render_term(self.read('multiple-regression'), preview=True)
        self.assertIn('性别', html)
        self.assertIn('参考组', html)
        self.assertIn('未标准化', html)

    def test_efa_interpretation_matches_itemwise_maximum(self):
        html = render_term(self.read('efa'), preview=True)
        self.assertIn('逐题最大绝对载荷', html)
        self.assertNotIn('预设题组主要载荷', html)

    def test_logistic_download_matches_real_binary_event(self):
        html = render_term(self.read('logistic-regression'), preview=True)
        self.assertIn('../data/binary_outcome_teaching.csv', html)
        self.assertIn('模拟筛查', html)
        self.assertNotIn('high_wellbeing', html)


if __name__ == '__main__':
    unittest.main()
