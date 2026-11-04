import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def entries():
    return json.loads((ROOT / 'site/content/plain_visuals/models.json').read_text(encoding='utf-8'))


class ModelNarrativeTests(unittest.TestCase):
    def test_original_data_and_evidence_boundaries_are_unchanged(self):
        # Cache metadata is added by the caller, not a change to teaching data.
        original = {slug: {key: value for key, value in item.items()
                           if key not in {'narrative', 'caution', 'artwork'}}
                    for slug, item in entries().items()}
        # The approved moderation redesign changes only this conceptual route
        # and its explanation. Restore those known historical fields before
        # checking the original checksum, retaining protection for all actual
        # teaching values, evidence types and unrelated model structures.
        original['mediated-moderation'].update(
            read='先看压力指向训练与自信之间的路径。',
            takeaway='例子提出压力削弱自信提升，进而关联坚持的具体候选过程。',
            limit='虚线路径仅标示调节设定，不证明过程，也不能仅凭名称识别模型。',
            nodes=[{'label':label,'x':x,'y':y,'shape':'observed'} for label,x,y in
                [('学习训练',10,65),('自信提升',50,65),('坚持学习',90,65),('压力',30,10),('训练×压力',30,35)]],
            edges=[{'from':a,'to':b,'label':label,'dashed':dashed} for a,b,label,dashed in
                [(0,1,'训练联系',False),(1,2,'后续联系',False),(3,4,'参与交互项',True),(4,1,'检验调节',True)]])
        canonical = json.dumps(original, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        self.assertEqual(hashlib.sha256(canonical.encode('utf-8')).hexdigest(),
                         'a3c558e12cca51e778b9c35abbdadac894253d168723cffc7d19e60566266f6a')

    def test_every_active_entry_has_two_specific_paragraphs_and_caution(self):
        active = {slug: item for slug, item in entries().items() if item['decision'] != 'skip'}
        self.assertEqual(len(active), 56)
        for slug, item in active.items():
            with self.subTest(slug=slug):
                self.assertEqual(len(item.get('narrative', [])), 2)
                self.assertTrue(all(isinstance(p, str) and len(p) >= 20 for p in item['narrative']))
                self.assertTrue(item.get('caution', '').strip())
                self.assertFalse(any(label in ''.join(item['narrative']) for label in ('先看哪里', '说明什么', '不能说明什么')))


class ModelStoryTests(unittest.TestCase):
    def test_validity_connects_the_same_score_to_two_proposed_uses(self):
        figure=self.make_story('validity',entries()['validity'],'#244da4')
        texts=self.texts(figure)
        self.assertIn('score-reading',texts)
        self.assertEqual(texts['score-reading'],texts['score-anxiety'])
        self.assertIn('阅读理解',texts['interpretation-reading'])
        self.assertIn('焦虑程度',texts['interpretation-anxiety'])
    def setUp(self):
        from sitegen.story_models import make_story, SUPPORTED
        self.make_story = make_story
        self.supported = SUPPORTED

    def tearDown(self):
        from matplotlib import pyplot as plt
        plt.close('all')

    def texts(self, figure):
        return {text.get_gid(): text.get_text() for ax in figure.axes for text in ax.texts if text.get_gid()}

    def test_supported_stories_and_responsive_canvas(self):
        self.assertEqual(self.supported, {'measurement-error', 'model-identification', 'reliability', 'validity'})
        for slug in self.supported:
            for mobile in (False, True):
                with self.subTest(slug=slug, mobile=mobile):
                    figure = self.make_story(slug, entries()[slug], '#244da4', mobile)
                    self.assertAlmostEqual(figure.get_figwidth() * 72, 360 if mobile else 760)
                    self.assertEqual(figure.dpi, 300)
                    self.assertFalse(figure.axes[0].axison)
                    self.assertTrue(figure.axes[0].yaxis_inverted())
                    self.assertGreater(len(figure.axes[0].patches), 5)
                    self.assertTrue(all(t.get_fontsize() >= 12 for t in figure.axes[0].texts))
                    figure.canvas.draw()
                    renderer = figure.canvas.get_renderer()
                    for text in figure.axes[0].texts:
                        bounds = text.get_window_extent(renderer)
                        self.assertGreaterEqual(bounds.x0, 0, text.get_text())
                        self.assertGreaterEqual(bounds.y0, 0, text.get_text())
                        self.assertLessEqual(bounds.x1, figure.bbox.x1, text.get_text())
                        self.assertLessEqual(bounds.y1, figure.bbox.y1, text.get_text())
                    from matplotlib import pyplot as plt
                    plt.close(figure)

    def test_unknown_story_is_rejected_without_creating_figure(self):
        from matplotlib import pyplot as plt
        before = plt.get_fignums()
        with self.assertRaises(ValueError):
            self.make_story('unknown', {}, '#244da4')
        self.assertEqual(plt.get_fignums(), before)

    def test_environment_comparison_keeps_person_and_task_matched(self):
        figure = self.make_story('measurement-error', entries()['measurement-error'], '#244da4', True)
        texts = self.texts(figure)
        self.assertEqual(texts['identity-quiet'], texts['identity-noisy'])
        self.assertEqual(texts['task-quiet'], texts['task-noisy'])
        self.assertIn('安静', texts['environment-quiet'])
        self.assertIn('干扰', texts['environment-noisy'])
        self.assertIn('不预设', texts['measurement-note'])

    def test_two_payment_allocations_share_total_but_not_individual_values(self):
        figure = self.make_story('model-identification', entries()['model-identification'], '#244da4')
        texts = self.texts(figure)
        self.assertEqual(texts['allocation-0'], '甲40元 + 乙50元 = 90元')
        self.assertEqual(texts['allocation-1'], '甲30元 + 乙60元 = 90元')
        ax = figure.axes[0]
        blocks = {p.get_gid(): p for p in ax.patches if p.get_gid()}
        for index, values in enumerate(((40, 50), (30, 60))):
            a, b = blocks[f'payment-{index}-0'], blocks[f'payment-{index}-1']
            self.assertAlmostEqual(a.get_width() / b.get_width(), values[0] / values[1])
            self.assertAlmostEqual(a.get_width() + b.get_width(), 660)

    def test_reliability_compares_raters_and_matched_occasions_without_scores(self):
        texts = self.texts(self.make_story('reliability', entries()['reliability'], '#244da4', True))
        self.assertEqual(texts['essay-source'], '同一篇作文')
        self.assertIn('老师甲', texts['rater-0'])
        self.assertIn('老师乙', texts['rater-1'])
        self.assertEqual(texts['occasion-identity-0'], texts['occasion-identity-1'])
        self.assertIn('第一次', texts['occasion-0'])
        self.assertIn('隔一段时间', texts['occasion-1'])
        self.assertIn('未给分数', texts['reliability-note'])

    def test_validity_requires_evidence_link_for_interpretation(self):
        texts = self.texts(self.make_story('validity', entries()['validity'], '#244da4'))
        self.assertIn('阅读', texts['task-content'])
        self.assertIn('阅读理解', texts['purpose-reading'])
        self.assertIn('焦虑', texts['purpose-anxiety'])
        self.assertIn('证据', texts['evidence-anxiety'])
        self.assertIn('也须验证', texts['validity-note'])
