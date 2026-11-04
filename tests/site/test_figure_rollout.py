"""Catch data distortion and dropped records when rolling out figure styling."""
import unittest
from matplotlib import pyplot as plt


class FigureRolloutTests(unittest.TestCase):
    def test_error_table_uses_distinct_correct_and_error_signals(self):
        from sitegen.rollout_figures import make_figure
        from matplotlib.colors import to_rgb
        entry={'kind':'table','columns':['真相','决定'],
               'rows':[['无效应','正确不拒绝'],['无效应','第一类：误报']]}
        fig=make_figure('error-table',entry,'#244da4')
        try:
            values={t.get_text():to_rgb(t.get_color()) for t in fig.axes[0].texts}
            good,bad=values['正确不拒绝'],values['第一类：误报']
            self.assertGreater(good[1],max(good[0],good[2]))
            self.assertGreater(bad[0],max(bad[1],bad[2]))
        finally: plt.close(fig)
    def test_line_legend_shows_the_series_dash_and_marker(self):
        from sitegen.rollout_figures import make_figure
        entry={'kind':'lines','chart':{'x_label':'时间','y_label':'得分',
               'series':[{'label':'甲','values':[[0,2],[1,3]]},
                         {'label':'乙','values':[[0,1],[1,4]]}]}}
        fig=make_figure('legend-example',entry,'#244da4')
        try:
            swatches={a.get_gid():a for a in fig.artists if a.get_gid()}
            self.assertIn('legend-swatch-0',swatches)
            self.assertEqual(swatches['legend-swatch-1'].get_linestyle(),'--')
            self.assertEqual(swatches['legend-swatch-1'].get_marker(),'s')
        finally: plt.close(fig)

    def test_density_highlight_uses_only_the_requested_interval(self):
        from sitegen.rollout_figures import make_figure
        entry={'kind':'lines','chart':{'x_label':'小时','y_label':'密度',
               'highlight_interval':[6,8],
               'series':[{'label':'密度','values':[[4,0],[6,0.2],[7,0.3],[8,0.2],[10,0]]}]}}
        fig=make_figure('density-example',entry,'#244da4')
        try:
            shaded=[a for a in fig.axes[0].collections if a.get_gid()=='interval-area']
            self.assertEqual(len(shaded),1)
            xs=shaded[0].get_paths()[0].vertices[:,0]
            self.assertEqual((min(xs),max(xs)),(6,8))
        finally: plt.close(fig)

    def test_equivalence_reference_bounds_are_visible_at_each_interval(self):
        from sitegen.rollout_figures import make_figure
        entry={'kind':'intervals','x_label':'差异','reference_bounds':[-2,2],
               'rows':[{'label':'在内','low':-1,'mid':0,'high':1},
                       {'label':'跨界','low':-3,'mid':0,'high':3}]}
        fig=make_figure('equivalence-example',entry,'#244da4')
        try:
            bounds=[a for a in fig.axes[0].collections if (a.get_gid() or '').startswith('reference-bounds-')]
            self.assertEqual(len(bounds),2)
            self.assertEqual([s[0,0] for s in bounds[0].get_segments()],[-2,2])
        finally: plt.close(fig)
    def test_non_sample_scatter_keeps_every_observed_pair(self):
        from sitegen.rollout_figures import make_figure
        entry = {'kind':'scatter','chart':{'x_label':'压力','y_label':'幸福感','series':[
            {'label':'学生','values':[[1,7],[3,5],[5,4]]}]}}
        fig = make_figure('test-scatter',entry,'#244da4')
        try:
            points=fig.axes[0].collections[0].get_offsets().tolist()
            self.assertEqual(points,[[1,7],[3,5],[5,4]])
        finally: plt.close(fig)

    def test_histogram_bins_are_contiguous_and_keep_frequencies(self):
        from sitegen.rollout_figures import make_figure
        entry = {'kind':'histogram','chart':{'x_label':'时间（秒）','y_label':'人数','series':[
            {'label':'用时','values':[[5,8],[15,15],[25,9]]}]}}
        fig = make_figure('test-histogram',entry,'#244da4',True)
        try:
            bars=fig.axes[0].containers[0]
            self.assertEqual([p.get_height() for p in bars],[8,15,9])
            self.assertEqual([p.get_width() for p in bars],[10,10,10])
            self.assertAlmostEqual(bars[0].get_x()+bars[0].get_width(), bars[1].get_x())
        finally: plt.close(fig)

    def test_mobile_table_keeps_column_context_for_each_value(self):
        from sitegen.rollout_figures import make_figure
        entry={'kind':'table','columns':['学生','压力','睡眠'], 'rows':[['甲','7','6小时'],['乙','4','8小时']]}
        fig=make_figure('test-table',entry,'#006d70',True)
        try:
            text=' '.join(t.get_text() for a in fig.axes for t in a.texts)
            for required in ['学生','甲','乙','压力','睡眠','6小时','8小时']:
                self.assertIn(required,text)
        finally: plt.close(fig)

    def test_segment_lengths_use_original_amounts_not_equal_parts(self):
        from sitegen.rollout_figures import make_figure
        entry={'kind':'segments','legend':['解释','未解释'],'rows':[{'label':'总变异','values':[20,80]}]}
        fig=make_figure('test-segments',entry,'#006d70')
        try:
            parts=fig.axes[0].containers
            self.assertEqual([c[0].get_width() for c in parts],[20,80])
        finally: plt.close(fig)

    def test_network_retains_latent_observed_distinction(self):
        from sitegen.rollout_figures import make_figure
        entry={'kind':'network','nodes':[{'label':'焦虑','x':20,'y':50,'shape':'latent'},
               {'label':'题目','x':80,'y':50,'shape':'observed'}], 'edges':[{'from':0,'to':1,'label':'测量联系'}]}
        fig=make_figure('test-network',entry,'#6741ad',True)
        try:
            labels={p.get_gid():type(p).__name__ for p in fig.axes[0].patches if p.get_gid()}
            self.assertEqual(labels['node-0'],'Ellipse')
            self.assertEqual(labels['node-1'],'FancyBboxPatch')
        finally: plt.close(fig)
