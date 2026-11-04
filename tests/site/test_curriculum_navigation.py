import json
import tempfile
import unittest
from pathlib import Path
from sitegen.build import build_site

ROOT=Path(__file__).resolve().parents[2]

class CurriculumNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name);build_site('preview',self.out)

    def test_home_exposes_topics_in_learning_order_without_topic_dropdown(self):
        html=(self.out/'index.html').read_text(encoding='utf-8')
        self.assertIn('class="topic-nav"',html)
        self.assertNotIn('id="topic-filter"',html)
        self.assertLess(html.index('data-topic-link="hypothesis-testing"'),html.index('data-topic-link="data-preparation"'))
        self.assertLess(html.index('data-topic-link="data-preparation"'),html.index('data-topic-link="factor-analysis"'))

    def test_topic_contains_scoped_filters_and_prerequisite_first_cards(self):
        html=(self.out/'index.html').read_text(encoding='utf-8')
        for control in ('level-filter','type-filter','r-filter'):self.assertIn(f'id="{control}"',html)
        self.assertNotIn('id="topic-filter"',html)
        self.assertLess(html.index('data-id="simple-linear-regression"'),html.index('data-id="multiple-regression"'))
        self.assertIn('value="false"',html)
        self.assertIn('href="terms/simple-linear-regression.html"',html)

    def test_level_options_are_read_in_increasing_difficulty(self):
        html=(self.out/'index.html').read_text(encoding='utf-8')
        self.assertLess(html.index('value="basic"'),html.index('value="intermediate"'))
        self.assertLess(html.index('value="intermediate"'),html.index('value="advanced"'))

    def test_learning_map_has_direction_branches_and_shared_knowledge_links(self):
        html=(self.out/'paths.html').read_text(encoding='utf-8')
        self.assertIn('class="learning-network"',html)
        self.assertEqual(html.count('class="direction-map"'),6)
        self.assertIn('id="direction-measurement"',html)
        self.assertIn('href="#direction-mechanisms"',html)
        self.assertIn('href="terms/multiple-regression.html"',html)
        self.assertIn('<details',html)

    def test_every_registered_term_occurs_once_in_curriculum(self):
        manifest=json.loads((ROOT/'site/content/curriculum.json').read_text(encoding='utf-8'))
        ids=[slug for topic in manifest['topics'] for slug in topic['terms']]
        registry=json.loads((ROOT/'site/content/registry.json').read_text(encoding='utf-8'))['terms']
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(set(ids),{t['id'] for t in registry})

if __name__=='__main__':unittest.main()
