import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ModelVisualTests(unittest.TestCase):
    def renderer(self):
        spec = importlib.util.spec_from_file_location('model_visual_renderer', ROOT / 'tools/render_paper_results.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def test_sem_relationships_are_single_continuous_arrows(self):
        from sitegen.paper_reporting import paper_data
        from matplotlib.patches import FancyArrowPatch
        import matplotlib.pyplot as plt
        fig=self.renderer().model_figure(paper_data(*self.fixture('sem')), '#244da4')
        try:
            ax=fig.axes[0]
            self.assertFalse(ax.lines, 'A relationship must not be assembled from plotted line segments')
            # Nine loadings, nine measurement errors, one disturbance, two
            # structural paths and one covariance: exactly 22 relationships.
            self.assertEqual(sum(isinstance(p,FancyArrowPatch) for p in ax.patches),22)
        finally:plt.close(fig)

    def test_factor_arcs_share_ports_and_equal_span_shapes(self):
        from sitegen.paper_reporting import paper_data
        from matplotlib.path import Path as MplPath
        import matplotlib.pyplot as plt
        fig=self.renderer().model_figure(paper_data(*self.fixture('cfa')), '#6741ad')
        try:
            arrows=[p for p in fig.axes[0].patches if (p.get_gid() or '').startswith('factor-relation-')]
            self.assertEqual(len(arrows),3)
            curves=[]
            for arrow in arrows:
                curve=next(c for c,code in arrow.get_path().iter_bezier() if code==MplPath.CURVE4)
                curves.append(curve.control_points)
            curves.sort(key=lambda p:abs(p[-1,0]-p[0,0]))
            a,b,outer=curves
            self.assertAlmostEqual(a[1,1],b[1,1],places=6)
            self.assertGreater(outer[1,1],a[1,1])
            self.assertAlmostEqual(a[0,1],0.39,delta=.1)
            # Shared F1/F2/F3 ports are preserved before arrowhead mutation.
            ports=[p._path_original.vertices[[0,-1]] for p in arrows]
            self.assertEqual(len({tuple(point) for pair in ports for point in pair}),3)
        finally:plt.close(fig)

    def test_moderator_points_vertically_at_a_relationship(self):
        from sitegen.paper_reporting import paper_data
        from matplotlib.patches import FancyArrowPatch
        import matplotlib.pyplot as plt
        fig=self.renderer().model_figure(paper_data(*self.fixture('moderation')), '#953970')
        try:
            ax=fig.axes[0]
            arrows=[p for p in ax.patches if isinstance(p,FancyArrowPatch)]
            self.assertEqual(len(arrows),2, 'Show X→Y and W→the X→Y path')
            modifier=next(p for p in arrows if (p.get_gid() or '').startswith('moderates-'))
            vertices=modifier.get_path().vertices
            self.assertAlmostEqual(vertices[0,0],vertices[1,0],places=6)
            self.assertGreater(vertices[0,1],vertices[1,1])
            labels=[t.get_text() for t in ax.texts]
            self.assertTrue(any('b2' in t for t in labels),'Retain the fitted W main effect as a note')
        finally:plt.close(fig)

    def test_concept_modifier_lands_on_the_middle_of_its_target_edge(self):
        from sitegen.rollout_figures import make_figure
        from matplotlib.patches import FancyArrowPatch
        from matplotlib.path import Path as MplPath
        import matplotlib.pyplot as plt
        entry=json.loads((ROOT/'site/content/plain_visuals/models.json').read_text(encoding='utf-8'))['mediated-moderation']
        fig=make_figure('test-modifier',entry,'#953970',False)
        try:
            arrows=[p for p in fig.axes[0].patches if isinstance(p,FancyArrowPatch)]
            arrow=arrows[-1]
            path=arrow.get_path()
            vertices=path.vertices[path.codes!=MplPath.CLOSEPOLY]
            self.assertAlmostEqual(vertices[0,0],vertices[1,0],places=5)
            self.assertAlmostEqual(vertices[:,1].max(),arrows[0].get_path().vertices[0,1],delta=3)
        finally:plt.close(fig)

    def test_combined_models_use_a_triangle_and_one_internal_moderator(self):
        from sitegen.paper_reporting import paper_data
        from matplotlib.patches import FancyBboxPatch
        import matplotlib.pyplot as plt
        for slug in ('conditional-mediation','mediated-interaction'):
            with self.subTest(case=slug):
                fig=self.renderer().model_figure(paper_data(*self.fixture(slug)),'#953970')
                try:
                    ax=fig.axes[0]
                    boxes=[p for p in ax.patches if isinstance(p,FancyBboxPatch)]
                    self.assertEqual(len(boxes),4,'Exactly X, M, Y and one W')
                    centers=[(p.get_x()+p.get_width()/2,p.get_y()+p.get_height()/2) for p in boxes]
                    x,m,y,w=centers
                    self.assertGreater(m[1],x[1]+1)
                    self.assertAlmostEqual(x[1],y[1])
                    self.assertGreater(w[1],x[1])
                    self.assertLess(w[1],m[1])
                    self.assertEqual(len([p for p in ax.patches if (p.get_gid() or '').startswith('moderates-')]),
                                     2 if slug=='mediated-interaction' else 1)
                finally:plt.close(fig)

    def test_reused_branch_arrows_are_smooth_single_curves(self):
        from sitegen.reused_figures import make_reused_figure
        from matplotlib.patches import FancyArrowPatch
        from matplotlib.path import Path as MplPath
        import matplotlib.pyplot as plt
        fig=make_reused_figure(ROOT/'site/assets/diagrams/data-cleaning.svg','#006d70')
        try:
            arrows=[p for p in fig.axes[0].patches if isinstance(p,FancyArrowPatch)]
            self.assertEqual(len(arrows),6)
            for arrow in arrows[2:]:
                self.assertIn(MplPath.CURVE4,arrow.get_path().codes)
        finally:plt.close(fig)

    def test_feedback_arcs_stay_between_their_shared_node_ports(self):
        from sitegen.paper_reporting import paper_data
        from matplotlib.path import Path as MplPath
        from matplotlib.patches import FancyArrowPatch
        import matplotlib.pyplot as plt
        fig=self.renderer().model_figure(paper_data(*self.fixture('feedback')),'#244da4')
        try:
            curves=[c for p in fig.axes[0].patches if isinstance(p,FancyArrowPatch)
                    for c,code in p.get_path().iter_bezier() if code==MplPath.CURVE4]
            self.assertEqual(len(curves),2)
            for curve in curves:
                self.assertLessEqual(curve.control_points[:,1].max(),1.125+.01)
                self.assertGreaterEqual(curve.control_points[:,1].min(),-1.125-.01)
        finally:plt.close(fig)

    def test_concept_sem_uses_shared_factor_ports_and_single_cubic_arcs(self):
        from sitegen.rollout_figures import make_figure
        from matplotlib.patches import FancyArrowPatch
        from matplotlib.path import Path as MplPath
        import matplotlib.pyplot as plt
        entry=json.loads((ROOT/'site/content/plain_visuals/models.json').read_text(encoding='utf-8'))['sem']
        fig=make_figure('sem',entry,'#244da4',False)
        try:
            arrows=[p for p in fig.axes[0].patches if isinstance(p,FancyArrowPatch)][:3]
            self.assertTrue(all(MplPath.CURVE4 in p.get_path().codes for p in arrows))
            ports=[p._path_original.vertices[[0,-1]] for p in arrows]
            self.assertEqual(len({tuple(point) for pair in ports for point in pair}),3)
        finally:plt.close(fig)
    def fixture(self, slug):
        return tuple(json.loads((ROOT / f'site/content/{folder}/{slug}.json').read_text(encoding='utf-8'))
                     for folder in ('analysis_cases', 'analysis_results'))

    def test_information_criteria_keep_decimal_numbers_in_all_presentations(self):
        from sitegen.paper_reporting import formatted
        from sitegen.statistical_display import console_html, format_number
        for key, row in [('AIC', {}), ('bic', {}), ('value', {'index': 'aic'}),
                         ('value', {'field_id': 'bic'})]:
            self.assertEqual(formatted(12345.6789, key, row), '12345.68')
            self.assertEqual(format_number(12345.6789, key, row), '12345.68')
        self.assertEqual(formatted(-12500.25, 'BIC', {}), '-12500.25')
        self.assertEqual(formatted(1e-10, 'p', {}), '<0.001')
        self.assertIn('12345.68', console_html('AIC: 1.23456789e+04\n'))

    def test_sem_exposes_every_measurement_loading_and_variance(self):
        from sitegen.paper_reporting import paper_data
        case, result = self.fixture('sem')
        data = paper_data(case, result)
        self.assertEqual(len(data.get('measurement', [])), 9)
        self.assertEqual({r['rhs'] for r in data['measurement']}, {f'x{i}' for i in range(1, 10)})
        self.assertTrue(any(r['lhs'] == 'f1' and r['rhs'] == 'f2' for r in data['covariances']))
        self.assertTrue(all(any(r['lhs'] == f'x{i}' and r['rhs'] == f'x{i}'
                                for r in data['variances']) for i in range(1, 10)))
        actual = next(r for r in result['tables']['parameters'] if r['op'] == '=~')
        self.assertEqual(data['measurement'][0]['std.all'], actual['std.all'])

    def test_regression_views_include_source_traceable_predictions(self):
        from sitegen.paper_reporting import paper_data
        for slug in ('linear-simple', 'linear', 'logistic', 'ancova', 'selection'):
            with self.subTest(case=slug):
                data = paper_data(*self.fixture(slug))
                self.assertGreater(len(data['predictions']), 30)
                for row in data['predictions']:
                    self.assertLessEqual(row['ci_lower'], row['estimate'])
                    self.assertLessEqual(row['estimate'], row['ci_upper'])
                    if slug == 'logistic':
                        self.assertGreaterEqual(row['ci_lower'], 0)
                        self.assertLessEqual(row['ci_upper'], 1)
                self.assertTrue(data['prediction_spec']['x_label'])
                if slug == 'linear-simple':
                    self.assertEqual(len(data['observations']), 360)
                    self.assertEqual(data['observations'][0], {'x':43.3, 'y':47.7})

    def test_sem_figure_contains_indicators_and_error_nodes(self):
        from sitegen.paper_reporting import paper_data
        spec = importlib.util.spec_from_file_location('model_visual_renderer', ROOT / 'tools/render_paper_results.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        import matplotlib.pyplot as plt
        fig = module.model_figure(paper_data(*self.fixture('sem')), '#244da4')
        try:
            labels = [t.get_text() for ax in fig.axes for t in ax.texts]
            for i in range(1, 10):
                self.assertIn(f'x{i}', labels)
                self.assertIn(f'e{i}', labels)
            self.assertTrue(any('λ' in t for t in labels))
        finally:
            plt.close(fig)

    def test_logistic_view_shows_full_sigmoid_and_exact_sample_segment(self):
        from sitegen.paper_reporting import paper_data
        import numpy as np
        import matplotlib.pyplot as plt
        fig=self.renderer().slopes_figure(paper_data(*self.fixture('logistic')),'#8a5200')
        try:
            lines={line.get_gid():line for line in fig.axes[0].lines}
            self.assertIn('logistic-function',lines)
            self.assertIn('logistic-sample',lines)
            full=lines['logistic-function'];z=full.get_xdata();p=full.get_ydata()
            self.assertLess(z[0],-5);self.assertGreater(z[-1],5)
            np.testing.assert_allclose(p,1/(1+np.exp(-z)),rtol=1e-12)
            saved=json.loads((ROOT/'site/content/prediction_results/logistic.json').read_text(encoding='utf-8'))
            sample=lines['logistic-sample'];actual=sorted(saved['predictions'],key=lambda r:r['estimate'])
            np.testing.assert_allclose(sample.get_ydata(),[r['estimate'] for r in actual])
            np.testing.assert_allclose(sample.get_xdata(),[np.log(r['estimate']/(1-r['estimate'])) for r in actual])
        finally:plt.close(fig)

    def test_analysis_card_and_return_use_shared_expansion_hooks(self):
        from sitegen.analysis_reader import render_analysis_index, render_analysis_case
        case, result = self.fixture('logistic')
        catalog = {'units': [{'id': case['unit_id'], 'title': '逻辑回归', 'group': 'regression'}]}
        index = render_analysis_index(catalog, {case['id']: case})
        self.assertIn('data-expand-card', index)
        self.assertIn('data-analysis-id="logistic"', index)
        self.assertIn('data-collapse-analysis', render_analysis_case(case, result, {}))
