"""Semantic and layout checks for the concrete foundation teaching stories."""
import json
from pathlib import Path
import unittest

from matplotlib import pyplot as plt
from matplotlib.figure import Figure

from sitegen.story_foundations import SUPPORTED, make_story


MANIFEST = Path(__file__).resolve().parents[2] / 'site/content/plain_visuals/foundations.json'
SLUGS = {
    'continuous-variable', 'extreme-value', 'independence', 'missing-data-mechanism',
    'missing-data', 'null-hypothesis', 'outlier', 'p-value', 'parameter-and-statistic',
    'partial-correlation', 'sample-size-planning', 'sesoi', 'significance-level',
    'statistical-assumptions', 'statistical-power',
}


class StoryFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = json.loads(MANIFEST.read_text(encoding='utf-8'))

    def make(self, slug, mobile=False):
        fig = make_story(slug, self.entries[slug], '#244da4', mobile)
        self.addCleanup(plt.close, fig)
        return fig

    def gids(self, slug):
        return {artist.get_gid(): artist for ax in self.make(slug).axes
                for artist in ax.get_children() if artist.get_gid()}

    def test_supported_set_and_unknown_slug(self):
        self.assertEqual(SUPPORTED, SLUGS)
        with self.assertRaises(ValueError):
            make_story('not-a-story', {}, '#244da4')

    def test_all_stories_render_with_readable_text_inside_canvas(self):
        for slug in sorted(SLUGS):
            for mobile in (False, True):
                with self.subTest(slug=slug, mobile=mobile):
                    fig = self.make(slug, mobile)
                    self.assertIsInstance(fig, Figure)
                    self.assertEqual(round(fig.get_figwidth()*72), 360 if mobile else 760)
                    self.assertEqual(fig.dpi, 300)
                    fig.canvas.draw()
                    renderer = fig.canvas.get_renderer()
                    for ax in fig.axes:
                        for text in ax.texts:
                            self.assertGreaterEqual(text.get_fontsize(), 12)
                            box = text.get_window_extent(renderer)
                            self.assertGreaterEqual(box.x0, -1, text.get_text())
                            self.assertGreaterEqual(box.y0, -1, text.get_text())
                            self.assertLessEqual(box.x1, fig.bbox.x1+1, text.get_text())
                            self.assertLessEqual(box.y1, fig.bbox.y1+1, text.get_text())
                    plt.close(fig)

    def test_missing_response_does_not_become_zero(self):
        gids = self.gids('missing-data')
        self.assertEqual(gids['missing-value'].get_text(), '缺失')
        self.assertEqual(gids['observed-zero'].get_text(), '0 小时')
        self.assertIn('missing-cell', gids)

    def test_continuous_example_shows_whole_person_count_change(self):
        for mobile in (False, True):
            with self.subTest(mobile=mobile):
                fig = self.make('continuous-variable', mobile)
                ax = fig.axes[0]
                from matplotlib.patches import Circle
                before = [p for p in ax.patches if isinstance(p, Circle)
                          and (p.get_gid() or '').startswith('count-before-')]
                after = [p for p in ax.patches if isinstance(p, Circle)
                         and (p.get_gid() or '').startswith('count-after-')]
                self.assertEqual(len(before), 2)
                self.assertEqual(len(after), 3)
                texts = ' '.join(t.get_text() for t in ax.texts)
                self.assertIn('7小时15分钟', texts)
                self.assertIn('增加1个', texts)
                self.assertNotIn('2.25', texts)

    def test_p_value_example_difference_has_visible_operands(self):
        fig = self.make('p-value')
        texts = ' '.join(t.get_text() for t in fig.axes[0].texts)
        self.assertIn('平均进步8分', texts)
        self.assertIn('平均进步3分', texts)
        self.assertIn('8 − 3 = 5', texts)

    def test_missing_mechanism_highlight_does_not_reach_explanation(self):
        from matplotlib.colors import to_rgba
        for mobile in (False, True):
            with self.subTest(mobile=mobile):
                fig = self.make('missing-data-mechanism', mobile)
                fig.canvas.draw()
                renderer = fig.canvas.get_renderer()
                ax = fig.axes[0]
                labels = [t for t in ax.texts if t.get_text() in (
                    '漏发位置不按压力挑选', '留下的回答可能更偏向轻松者')]
                markers = [p for p in ax.patches
                           if (p.get_gid() or '').startswith('missing-cell-')]
                self.assertTrue(markers)
                for text in labels:
                    for marker in markers:
                        self.assertFalse(text.get_window_extent(renderer).overlaps(
                            marker.get_window_extent(renderer)))

    def test_repeated_records_keep_the_same_person_identity(self):
        gids = self.gids('independence')
        self.assertEqual(gids['record-today'].get_text(), '甲 · 今天 · 压力6分')
        self.assertEqual(gids['record-tomorrow'].get_text(), '甲 · 明天 · 压力7分')
        self.assertIn('shared-exam', gids)
        gids = self.gids('statistical-assumptions')
        self.assertEqual(gids['repeated-identities'].get_text(), '甲 → 甲 → 甲')
        self.assertEqual(gids['different-identities'].get_text(), '甲     乙     丙')

    def test_p_value_marks_extreme_region_without_fabricated_probability(self):
        gids = self.gids('p-value')
        self.assertEqual(gids['observed-difference'].get_text(), '样本相差5分')
        self.assertIn('same-or-more-extreme', gids)
        self.assertIn('null-reference', gids)
        texts = '\n'.join(t.get_text() for ax in self.make('p-value').axes for t in ax.texts)
        self.assertNotRegex(texts, r'p\s*[=<>]\s*\d')

    def test_parameter_remains_unknown(self):
        gids = self.gids('parameter-and-statistic')
        self.assertEqual(gids['sample-statistic'].get_text(), '样本平均 = 7小时')
        self.assertEqual(gids['population-parameter'].get_text(), '全校真实平均 = ?')

    def test_null_comparison_receives_two_groups_of_sample_records(self):
        from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch
        for mobile in (False, True):
            with self.subTest(mobile=mobile):
                fig = self.make('null-hypothesis', mobile)
                artists = {a.get_gid(): a for ax in fig.axes for a in ax.get_children()
                           if a.get_gid()}
                for group in ('training', 'waiting'):
                    self.assertIsInstance(artists[f'null-{group}-person'], Circle)
                    self.assertIsInstance(artists[f'null-{group}-records'], FancyBboxPatch)
                    self.assertIsInstance(artists[f'null-{group}-to-comparison'], FancyArrowPatch)
                self.assertEqual(artists['comparison-under-null'].get_text(),
                                 '按总体平均进步相同的基准比较')

    def test_alpha_applies_fixed_rule_under_true_null_then_branches(self):
        from matplotlib.patches import FancyArrowPatch
        for mobile in (False, True):
            with self.subTest(mobile=mobile):
                fig = self.make('significance-level', mobile)
                artists = {a.get_gid(): a for ax in fig.axes for a in ax.get_children()
                           if a.get_gid()}
                self.assertEqual(artists['null-is-true'].get_text(), '条件：零假设成立')
                self.assertEqual(artists['fixed-alpha-rule'].get_text(), '同一规则：α = 0.05')
                self.assertEqual(artists['alpha-reject'].get_text(), '拒绝')
                self.assertEqual(artists['alpha-retain'].get_text(), '不拒绝')
                self.assertEqual(artists['alpha-false-rejection'].get_text(), '第一类错误')
                for gid in ('truth-to-rule', 'rule-to-reject', 'rule-to-retain'):
                    self.assertIsInstance(artists[gid], FancyArrowPatch)
                branch_a = artists['rule-to-reject']._posA_posB
                branch_b = artists['rule-to-retain']._posA_posB
                self.assertEqual(branch_a[0], branch_b[0])
                self.assertNotEqual(branch_a[1], branch_b[1])
                text = '\n'.join(t.get_text() for ax in fig.axes for t in ax.texts)
                self.assertNotRegex(text, r'\d+次拒绝|\d+次研究|\d+/\d+')

    def test_planning_and_power_do_not_invent_results(self):
        for slug in ('sample-size-planning', 'statistical-power'):
            gids = self.gids(slug)
            self.assertIn('target-effect', gids)
            texts = '\n'.join(t.get_text() for ax in self.make(slug).axes for t in ax.texts)
            self.assertNotRegex(texts, r'\d+%|n\s*=\s*\d')
            self.assertIn('概念示意', texts)

    def test_every_non_skip_entry_has_specific_prose(self):
        for slug, entry in self.entries.items():
            if entry['decision'] == 'skip':
                continue
            with self.subTest(slug=slug):
                self.assertEqual(len(entry.get('narrative', [])), 2)
                self.assertTrue(all(len(p) > 20 for p in entry['narrative']))
                self.assertTrue(entry.get('caution'))
                self.assertTrue(entry['limit'])
                for paragraph in entry['narrative']:
                    self.assertNotIn('先看哪里', paragraph)
                    self.assertNotIn('说明什么', paragraph)


if __name__ == '__main__':
    unittest.main()
