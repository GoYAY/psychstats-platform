"""Rendered targets, not merely absence of collisions, define a valid arrow."""
import json
from pathlib import Path
import unittest
from matplotlib import pyplot as plt
from matplotlib.patches import FancyArrowPatch
from sitegen.story_foundations import make_story
from sitegen.illustrated_examples import make_figure
from sitegen.story_models import make_story as model_story

ROOT = Path(__file__).resolve().parents[2]
FOUNDATIONS = json.loads((ROOT/'site/content/plain_visuals/foundations.json').read_text(encoding='utf-8'))
MODELS = json.loads((ROOT/'site/content/plain_visuals/models.json').read_text(encoding='utf-8'))


class StoryConnectionTests(unittest.TestCase):
    def tearDown(self):
        plt.close('all')

    def assert_points_to_text(self, fig, arrow, target):
        fig.canvas.draw()
        box = target.get_window_extent(fig.canvas.get_renderer()).transformed(fig.axes[0].transData.inverted())
        x, y = arrow._posA_posB[1]
        self.assertGreaterEqual(x, box.xmin-25, target.get_text())
        self.assertLessEqual(x, box.xmax+25, target.get_text())
        self.assertLessEqual(min(abs(y-box.ymin), abs(y-box.ymax)), 30, target.get_text())

    def test_parameter_computation_arrow_reaches_displayed_sample_mean(self):
        for mobile in (False, True):
            with self.subTest(mobile=mobile):
                fig = make_story('parameter-and-statistic', FOUNDATIONS['parameter-and-statistic'], '#244da4', mobile)
                ax=fig.axes[0]
                target=next(t for t in ax.texts if t.get_gid()=='sample-statistic')
                arrow=[p for p in ax.patches if isinstance(p,FancyArrowPatch)][-1]
                self.assert_points_to_text(fig,arrow,target)

    def test_cleaning_phone_checks_receive_their_arrows(self):
        fig=make_figure('data-cleaning',True)
        ax=fig.axes[0]
        for arrow, phrase in zip([p for p in ax.patches if isinstance(p,FancyArrowPatch)],
                                ('原始问卷确认：20岁','核对提交时间与有效版本','原问卷确认各自填写单位')):
            target=next(t for t in ax.texts if t.get_text()==phrase)
            self.assert_points_to_text(fig,arrow,target)

    def test_validity_phone_task_arrow_reaches_the_response_sheet(self):
        fig=model_story('validity',MODELS['validity'],'#244da4',True)
        ax=fig.axes[0]
        paper=next(p for p in ax.patches if p.get_gid()=='response-record')
        arrow=next(p for p in ax.patches if isinstance(p,FancyArrowPatch))
        x,y=arrow._posA_posB[1]
        self.assertGreaterEqual(x,paper.get_x()-12)
        self.assertLessEqual(x,paper.get_x()+paper.get_width()+12)
        self.assertLessEqual(abs(y-paper.get_y()),15)

    def test_independence_person_links_to_both_actual_records(self):
        for mobile in (False,True):
            fig=make_story('independence',FOUNDATIONS['independence'],'#244da4',mobile)
            ax=fig.axes[0]
            arrows=[p for p in ax.patches if isinstance(p,FancyArrowPatch) and p._posA_posB[1][1]<310]
            self.assertEqual(len(arrows),2)
            for arrow,gid in zip(arrows,('record-today','record-tomorrow')):
                target=next(t for t in ax.texts if t.get_gid()==gid)
                self.assert_points_to_text(fig,arrow,target)

    def test_population_and_sample_keep_a_distinct_sample_color(self):
        fig=make_figure('population-and-sample')
        from matplotlib.patches import Circle
        heads=[p for p in fig.axes[0].patches if isinstance(p,Circle) and p.radius==7]
        self.assertNotEqual(heads[0].get_facecolor()[:3],heads[-1].get_facecolor()[:3])

    def test_foundation_groups_and_statuses_use_distinct_meaningful_hues(self):
        for slug, labels in (
            ('p-value', ('训练甲样本\n平均进步8分','训练乙样本\n平均进步3分')),
            ('null-hypothesis', ('训练组总体','等待组总体')),
            ('missing-data', ('缺失','0 小时')),
            ('parameter-and-statistic', ('全校真实平均 = ?','样本平均 = 7小时')),
            ('significance-level', ('第一类错误','正确不拒绝')),
        ):
            with self.subTest(slug=slug):
                fig=make_story(slug,FOUNDATIONS[slug],'#244da4')
                texts={t.get_text():t for t in fig.axes[0].texts}
                self.assertNotEqual(texts[labels[0]].get_color(),texts[labels[1]].get_color())

    def test_payment_people_are_distinguishable_and_keep_their_colors(self):
        fig=make_figure('degrees-of-freedom')
        from matplotlib.patches import Rectangle
        blocks=[p for p in fig.axes[0].patches if isinstance(p,Rectangle)]
        colors=[p.get_facecolor()[:3] for p in blocks]
        self.assertEqual(len(set(colors)),3)
        self.assertEqual(colors[0],colors[1])
        self.assertEqual(colors[2],colors[4])
