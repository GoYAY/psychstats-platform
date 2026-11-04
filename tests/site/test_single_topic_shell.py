import tempfile
import unittest
from pathlib import Path
from sitegen.build import build_site

class SingleTopicShellTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.output=Path(self.temp.name);build_site('preview',self.output)
    def test_all_topics_point_to_one_shell_with_shareable_selection(self):
        html=(self.output/'index.html').read_text(encoding='utf-8')
        self.assertIn('href="index.html?topic=foundations"',html)
        self.assertIn('href="index.html?topic=regression"',html)
        self.assertEqual(html.count('<h1>心理统计学术语图鉴</h1>'),1)
        self.assertIn('data-id="cfa"',html)
        self.assertIn('data-id="variable"',html)
        self.assertNotIn('data-theme-choice=',html)
    def test_old_topic_url_cannot_show_a_second_conflicting_interface(self):
        html=(self.output/'topics/foundations.html').read_text(encoding='utf-8')
        self.assertIn('../index.html?topic=foundations',html)
        self.assertIn('http-equiv="refresh"',html)
        self.assertNotIn('class="term-grid"',html)
    def test_learning_map_links_to_topic_state_not_another_listing(self):
        html=(self.output/'paths.html').read_text(encoding='utf-8')
        self.assertIn('href="index.html?topic=regression"',html)
        self.assertNotIn('href="topics/regression.html"',html)

if __name__=='__main__':unittest.main()
