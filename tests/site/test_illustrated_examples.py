import unittest
from sitegen.render import render_term
from sitegen.plain_visuals import dimensions
from sitegen.plain_visuals import load_visuals, render_svg, validate_entry, ARTWORK_DIR
from pathlib import Path
import copy
import tempfile
from tests.site.test_rendered_pages import sample_term


class IllustratedExampleTests(unittest.TestCase):
    def cached_example(self):
        return load_visuals(Path(__file__).resolve().parents[2] / 'site/content/plain_visuals')['skewness']

    def test_cached_svg_rejects_path_traversal(self):
        visual = copy.deepcopy(self.cached_example())
        visual['artwork']['file'] = '../private.svg'
        with self.assertRaises(ValueError):
            validate_entry('skewness', visual)
        with self.assertRaises(ValueError):
            render_svg(visual)

    def test_missing_cached_svg_fails_validation(self):
        from unittest.mock import patch
        visual = self.cached_example()
        with tempfile.TemporaryDirectory() as directory:
            with patch('sitegen.plain_visuals.ARTWORK_DIR', Path(directory)):
                with self.assertRaisesRegex(ValueError, 'missing cached artwork'):
                    validate_entry('skewness', visual)

    def test_cached_svg_content_changes_input_hash(self):
        from sitegen.build import _input_hash
        original = ARTWORK_DIR / 'skewness.svg'
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / original.name
            target.write_bytes(original.read_bytes())
            before = _input_hash([target])
            target.write_bytes(original.read_bytes()+b'\n<!--updated-->')
            self.assertNotEqual(before, _input_hash([target]))

    def test_narrative_caption_replaces_generic_instruction_labels(self):
        visual = {'decision':'draw','kind':'story','title':'付款与余额','read':'旧阅读提示',
                  'takeaway':'旧结论','limit':'旧局限','basis':'conceptual', 'panels':[],
                  'artwork': {'file':'degrees-of-freedom.svg','width':760,'height':700,'mobile_height':1000},
                  'narrative':['总额先定为90元，前两人各自选择付款。','轮到第三人，剩下40元。'],
                  'caution':'约束直觉并非所有自由度的计算公式。'}
        html=render_term(sample_term(),preview=True,plain_visual=visual)
        self.assertNotIn('<dt>先看哪里</dt>',html)
        self.assertNotIn('<dt>说明什么</dt>',html)
        self.assertIn('总额先定为90元',html)
        self.assertIn('约束直觉并非所有自由度的计算公式',html)
        self.assertEqual(dimensions(visual),(760,700))
        self.assertEqual(dimensions(visual,True),(360,1000))

    def test_comparison_chart_preserves_counts_and_common_scale(self):
        from sitegen.illustrated_examples import make_figure
        from matplotlib import pyplot as plt
        fig=make_figure('central-tendency-and-dispersion')
        try:
            plots=[a for a in fig.axes if a.get_gid()=='data-panel']
            self.assertEqual(len(plots),2)
            self.assertEqual([p.get_height() for p in plots[0].containers[0]], [0,0,0,2,6,2,0,0,0])
            self.assertEqual([p.get_height() for p in plots[1].containers[0]], [2,0,2,0,2,0,2,0,2])
            self.assertEqual(plots[0].get_ylim(),plots[1].get_ylim())
            self.assertLess(plots[0].containers[0][4].get_facecolor()[3],0.65)
        finally:
            plt.close(fig)

    def test_payment_story_encodes_each_remaining_amount(self):
        from sitegen.illustrated_examples import make_figure
        from matplotlib import pyplot as plt
        fig=make_figure('degrees-of-freedom',True)
        try:
            gids={t.get_gid():t.get_text() for ax in fig.axes for t in ax.texts if t.get_gid()}
            self.assertEqual(gids['remaining-0'],'还差 90 元')
            self.assertEqual(gids['remaining-1'],'还差 70 元')
            self.assertEqual(gids['remaining-2'],'还差 40 元')
            self.assertEqual(gids['remaining-3'],'正好 90 元')
        finally:
            plt.close(fig)
