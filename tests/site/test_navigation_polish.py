import json
import re
import tempfile
import unittest
from pathlib import Path
from sitegen.build import build_site

class NavigationPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name)
        build_site('preview', cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_each_page_has_exactly_one_correct_primary_navigation_selection(self):
        for page, label in [('index.html','术语'),('terms/anova.html','术语'),('paths.html','学习路径'),('practice.html','练习'),('datasets.html','示例数据'),('sources.html','来源说明')]:
            with self.subTest(page=page):
                html = (self.out/page).read_text(encoding='utf-8')
                nav = re.search(r'<nav aria-label="主导航">(.*?)</nav>', html, re.S).group(1)
                selected = re.findall(r'<a[^>]*aria-current="page"[^>]*>(.*?)</a>', nav)
                self.assertEqual(selected, [label])

    def test_initial_and_switchable_topic_overviews_omit_book_names(self):
        html = (self.out/'index.html').read_text(encoding='utf-8')
        overview = re.search(r'id="topic-basis"[^>]*>(.*?)</p>',html).group(1)
        self.assertEqual(overview, '绪论、统计图表、集中与差异量数、相关关系、概率分布')
        payload = (self.out/'assets/data/site-data.js').read_text(encoding='utf-8')
        topics = json.loads(payload.split(' = ',1)[1].strip().rstrip(';'))['topics']
        for topic in topics:
            with self.subTest(topic=topic['id']):
                self.assertTrue(topic.get('overview'))
                self.assertNotIn('现代心理与教育统计学', topic['overview'])
                self.assertNotIn('高级心理统计', topic['overview'])

if __name__ == '__main__': unittest.main()
