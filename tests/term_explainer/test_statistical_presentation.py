from copy import deepcopy
import importlib
import json
from pathlib import Path
import tempfile
import unittest
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

def classroom():
    original=json.loads((Path(__file__).parents[2]/'site/content/plain_visuals/foundations.json').read_text(encoding='utf-8'))['central-tendency-and-dispersion']['chart']
    return dict(kind='statistical',title='同中心、不同分散',takeaway='两班均分80分，甲班更集中。',alt='两个班的完整分布',origin='teaching',refs=[],
        presentation=dict(version=1,focus='whole',numeric_role='relative',layout='facets',interaction='none'),
        payload=dict(chart_type='bar',x_label='成绩',x_unit='分',y_label='人数',y_unit='人',series=[dict(label=s['label'],x=[x for x,y in s['values']],y=[y for x,y in s['values']]) for s in original['series']]))

class StatisticalPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path('C:/Windows/Fonts/msyh.ttc')
        if path.is_file():
            font_manager.fontManager.addfont(str(path));cls.style=plt.rc_context({'font.family':font_manager.FontProperties(fname=path).get_name()});cls.style.__enter__()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'style'):cls.style.__exit__(None,None,None)
    def api(self):
        try:return importlib.import_module('term_explainer.statistical_visual').make_statistical_figure
        except ModuleNotFoundError:self.fail('Explicit statistical presentation renderer missing')

    def test_whole_distribution_facets_share_actual_axes(self):
        make=self.api();spec=classroom();before=deepcopy(spec)
        for mobile in (False,True):
            fig,height,audit=make(spec,360 if mobile else 760,mobile,'#4263bd')
            try:
                fig.canvas.draw();a,b=fig.axes
                self.assertEqual(a.get_xlim(),b.get_xlim());self.assertEqual(a.get_ylim(),b.get_ylim())
                self.assertEqual([p.get_height() for p in a.patches],[0,0,0,2,6,2,0,0,0])
                self.assertEqual([p.get_height() for p in b.patches],[2,0,2,0,2,0,2,0,2])
                if mobile:self.assertGreater(a.get_position().y0,b.get_position().y0)
                else:self.assertLess(a.get_position().x0,b.get_position().x0)
                self.assertEqual(spec,before)
            finally:plt.close(fig)

    def test_single_exact_labels_are_readable_but_relative_does_not_label_each_bar(self):
        make=self.api();spec=classroom();spec['payload']['series']=spec['payload']['series'][:1];spec['presentation'].update(layout='single',numeric_role='exact')
        fig,_,_=make(spec,760,False,'#4263bd')
        try:self.assertIn('6',[t.get_text() for t in fig.axes[0].texts])
        finally:plt.close(fig)
        spec['presentation']['numeric_role']='relative';fig,_,_=make(spec,760,False,'#4263bd')
        try:self.assertEqual(len(fig.axes[0].texts),0)
        finally:plt.close(fig)

    def test_real_render_visual_exports_facets_instead_of_flattening_data(self):
        from term_explainer.figures import render_visual
        with tempfile.TemporaryDirectory() as d:
            result=render_visual(classroom(),d,run_external_qa=False)
            audit=json.loads(Path(result.audit).read_text(encoding='utf-8'))
            self.assertIn('presentation',audit['layouts'][0],'Real export did not execute or record explicit layout')
            self.assertEqual([r['presentation']['layout'] for r in audit['layouts']],['facets','facets'])
            self.assertEqual([len(r['presentation']['axes']) for r in audit['layouts']],[2,2])

    def test_histogram_overlay_and_facets_preserve_actual_counts(self):
        make=self.api();spec=classroom();spec['payload']['chart_type']='histogram'
        spec['payload']['series']=[dict(label='甲',bin_edges=[0,1,2],counts=[2,3]),dict(label='乙',bin_edges=[0,1,2],counts=[1,4])]
        for layout,count in [('facets',2),('overlay',1)]:
            spec['presentation']['layout']=layout;fig,_,_=make(spec,760,False,'#4263bd')
            try:
                self.assertEqual(len(fig.axes),count)
                self.assertEqual([p.get_height() for a in fig.axes for p in a.patches],[2,3,1,4])
            finally:plt.close(fig)
        spec['presentation']['layout']='facets';spec['payload']['series'][1]['bin_edges']=[0,1,3]
        with self.assertRaises(ValueError):make(spec,760,False,'#4263bd')

    def test_exact_frequency_real_pdf_passes_grid_label_collision_audit(self):
        from term_explainer.figures import render_visual
        spec=classroom();spec['presentation'].update(focus='local',numeric_role='exact',layout='single',interaction='inspect')
        spec['payload']['series']=[dict(label='问卷',x=['非常不满意','不满意','满意','非常满意'],y=[12,23,68,17])]
        with tempfile.TemporaryDirectory() as d:
            assets=render_visual(spec,d,run_external_qa=True)
            audit=json.loads(Path(assets.audit).read_text(encoding='utf-8'))
            self.assertTrue(all(a['exit_code']==0 for a in audit['external_qa']))

    def test_categorical_mobile_and_facets_preserve_every_identity(self):
        spec=classroom();spec['payload']['series']=[dict(label='组',x=['甲','乙','丙','丁','戊','己'],y=[1,3,2,4,1,2])];spec['presentation'].update(focus='local',layout='single',numeric_role='relative')
        for facets in (False,True):
            if facets:spec['payload']['series'].append(dict(label='第二组',x=['甲','乙','丙','丁','戊','己'],y=[2,1,3,4,2,1]));spec['presentation']['layout']='facets'
            fig,_,_=self.api()(spec,360,True,'#4263bd')
            try:
                for ax in fig.axes:self.assertEqual([t.get_text() for t in ax.get_xticklabels()],['甲','乙','丙','丁','戊','己'])
            finally:plt.close(fig)

    def test_dense_categories_use_readable_horizontal_rows_not_missing_ticks(self):
        spec=classroom();categories=['类别'+str(i) for i in range(12)];spec['payload']['series']=[dict(label='组',x=categories,y=list(range(1,13)))];spec['presentation'].update(focus='local',layout='single',numeric_role='relative')
        fig,height,_=self.api()(spec,360,True,'#4263bd')
        try:
            self.assertEqual([t.get_text() for t in fig.axes[0].get_yticklabels()],categories)
            self.assertEqual([p.get_width() for p in fig.axes[0].patches],list(range(1,13)))
        finally:plt.close(fig)

    def test_dense_category_pdf_retains_axis_label_inside_page(self):
        from term_explainer.figures import render_visual
        spec=classroom();spec['payload']['series']=[dict(label='组',x=['类别'+str(i) for i in range(12)],y=list(range(1,13)))];spec['presentation'].update(focus='local',layout='single',numeric_role='relative')
        with tempfile.TemporaryDirectory() as d:render_visual(spec,d,run_external_qa=True)
