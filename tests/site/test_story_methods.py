import json
from pathlib import Path
import unittest

from matplotlib import pyplot as plt


ROOT = Path(__file__).resolve().parents[2]


class MethodStoryTests(unittest.TestCase):
    def test_likelihood_displays_the_same_observations_in_both_candidates(self):
        from sitegen.story_methods import make_story
        fig=make_story('likelihood',self.entries['likelihood'],'#244da4')
        try:
            ax=fig.axes[0]
            points={a.get_gid():a for a in ax.patches if a.get_gid()}
            for group in range(2):
                self.assertTrue(all(f'candidate-observation-{group}-{i}' in points for i in range(3)))
                observed=[points[f'candidate-observation-{group}-{i}'].center[0] for i in range(3)]
                self.assertEqual(observed,sorted(observed))
                if group==0: first=observed
                else: self.assertEqual(observed,first)
            text=' '.join(t.get_text() for t in ax.texts)
            for value in ('6小时','6.5小时','7小时'):
                self.assertIn(value,text)
        finally: plt.close(fig)
    def setUp(self):
        self.entries = json.loads((ROOT / 'site/content/plain_visuals/methods.json').read_text(encoding='utf-8'))

    def test_all_method_captions_have_two_natural_paragraphs(self):
        for slug, entry in self.entries.items():
            if entry['decision'] == 'skip':
                continue
            with self.subTest(slug=slug):
                self.assertEqual(len(entry['narrative']), 2)
                self.assertTrue(all(isinstance(p, str) and len(p) > 20 for p in entry['narrative']))
                self.assertTrue(entry['caution'])
                self.assertEqual(entry['caution'], entry['limit'])
                self.assertFalse(any(label in ''.join(entry['narrative']) for label in ('先看哪里', '说明什么', '不能说明什么')))

    def test_supported_story_contract_and_readable_mobile_canvas(self):
        from sitegen.story_methods import SUPPORTED, make_story
        expected = {slug for slug, entry in self.entries.items() if entry.get('kind') == 'story'}
        self.assertEqual(SUPPORTED, expected)
        self.assertEqual(len(SUPPORTED), 11)
        for slug in sorted(SUPPORTED):
            for mobile in (False, True):
                with self.subTest(slug=slug, mobile=mobile):
                    fig = make_story(slug, self.entries[slug], '#244da4', mobile)
                    try:
                        self.assertAlmostEqual(fig.get_figwidth() * 72, 360 if mobile else 760)
                        self.assertEqual(fig.dpi, 300)
                        self.assertEqual(len(fig.axes), 1)
                        ax = fig.axes[0]
                        self.assertGreater(ax.get_ylim()[0], ax.get_ylim()[1])
                        self.assertFalse(ax.axison)
                        self.assertTrue(all(t.get_fontsize() >= 12 for t in ax.texts))
                        gids = {artist.get_gid() for artist in ax.get_children()}
                        self.assertIn('conceptual-only', gids)
                        self.assertGreaterEqual(len(ax.patches), 8)
                    finally:
                        plt.close(fig)

    def test_common_cause_has_both_outgoing_paths(self):
        from sitegen.story_methods import make_story
        fig = make_story('confounding', self.entries['confounding'], '#244da4')
        try:
            gids = {p.get_gid() for p in fig.axes[0].patches}
            self.assertIn('resources-to-tutoring', gids)
            self.assertIn('resources-to-grades', gids)
        finally:
            plt.close(fig)

    def test_clustering_keeps_the_same_four_students_after_grouping(self):
        from sitegen.story_methods import make_story
        for mobile in (False, True):
            with self.subTest(mobile=mobile):
                fig = make_story('cluster-analysis', self.entries['cluster-analysis'], '#244da4', mobile)
                try:
                    ax = fig.axes[0]
                    inputs = {t.get_text() for t in ax.texts
                              if t.get_gid() and t.get_gid().startswith('input-student-')}
                    grouped = {t.get_text() for t in ax.texts
                               if t.get_gid() and t.get_gid().startswith('group-student-')}
                    marks = [p for p in ax.patches
                             if p.get_gid() and p.get_gid().startswith('cluster-member-')]
                    self.assertEqual(inputs, {'甲', '乙', '丙', '丁'})
                    self.assertEqual(grouped, inputs)
                    self.assertEqual(len(marks), len(inputs))
                finally:
                    plt.close(fig)

    def test_k_means_shows_assignment_and_center_updates(self):
        from sitegen.story_methods import make_story
        fig = make_story('k-means-clustering', self.entries['k-means-clustering'], '#244da4')
        try:
            gids = [p.get_gid() for p in fig.axes[0].patches]
            self.assertEqual(sum(bool(gid and gid.startswith('assignment-')) for gid in gids), 9)
            self.assertEqual(sum(bool(gid and gid.startswith('center-update-')) for gid in gids), 3)
            text = '\n'.join(t.get_text() for t in fig.axes[0].texts)
            self.assertIn('未运行算法', text)
        finally:
            plt.close(fig)

    def test_likelihood_keeps_data_fixed_and_original_candidates(self):
        from sitegen.story_methods import make_story
        fig = make_story('likelihood', self.entries['likelihood'], '#244da4')
        try:
            text = '\n'.join(t.get_text() for t in fig.axes[0].texts)
            self.assertIn('平均6小时', text)
            self.assertIn('平均8小时', text)
            self.assertIn('同一批睡眠记录', text)
            self.assertIn('无似然值', text)
        finally:
            plt.close(fig)

    def test_product_indicator_combines_specific_question_pair(self):
        from sitegen.story_methods import make_story
        fig = make_story('product-indicator', self.entries['product-indicator'], '#244da4', True)
        try:
            text = '\n'.join(t.get_text() for t in fig.axes[0].texts)
            self.assertIn('经常担忧', text)
            self.assertIn('困难时有人帮助', text)
            self.assertIn('p1 × s1', text)
            self.assertIn('其他题对', text)
        finally:
            plt.close(fig)

    def test_unsupported_story_fails_explicitly(self):
        from sitegen.story_methods import make_story
        with self.assertRaises(ValueError):
            make_story('not-a-method', {}, '#244da4')

    def test_rendered_text_stays_in_canvas_without_overlapping_other_text(self):
        from sitegen.story_methods import SUPPORTED, make_story
        for slug in sorted(SUPPORTED):
            for mobile in (False, True):
                with self.subTest(slug=slug, mobile=mobile):
                    fig = make_story(slug, self.entries[slug], '#244da4', mobile)
                    try:
                        fig.canvas.draw()
                        renderer = fig.canvas.get_renderer()
                        boxes = [(t.get_text(), t.get_window_extent(renderer))
                                 for t in fig.axes[0].texts if t.get_text()]
                        canvas = fig.bbox
                        for text, box in boxes:
                            self.assertGreaterEqual(box.x0, canvas.x0 - 1, text)
                            self.assertLessEqual(box.x1, canvas.x1 + 1, text)
                            self.assertGreaterEqual(box.y0, canvas.y0 - 1, text)
                            self.assertLessEqual(box.y1, canvas.y1 + 1, text)
                        for index, (first, a) in enumerate(boxes):
                            for second, b in boxes[index + 1:]:
                                overlap_x = min(a.x1, b.x1) - max(a.x0, b.x0)
                                overlap_y = min(a.y1, b.y1) - max(a.y0, b.y0)
                                self.assertFalse(overlap_x > 1 and overlap_y > 1,
                                                 f'{first!r} overlaps {second!r}')
                    finally:
                        plt.close(fig)
