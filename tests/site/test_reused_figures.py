import tempfile
import unittest
from pathlib import Path
from matplotlib import pyplot as plt


class ReusedFigureTests(unittest.TestCase):
    def test_original_path_arrowhead_is_not_lost(self):
        from sitegen.reused_figures import make_reused_figure
        from matplotlib.patches import FancyArrowPatch
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'arrow.svg'
            p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 200"><path d="M20 20 H80" fill="none" stroke="#244da4" marker-end="url(#arrow)"/></svg>',encoding='utf-8')
            fig=make_reused_figure(p,'#244da4')
            try:
                self.assertIsInstance(fig.axes[0].patches[0],FancyArrowPatch)
                self.assertGreater(len(fig.axes[0].patches[0].get_path().vertices),2)
            finally: plt.close(fig)
    def test_adapter_keeps_original_scatter_geometry_and_text(self):
        from sitegen.reused_figures import make_reused_figure
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'original.svg'
            p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 200"><g fill="#244da4"><circle cx="20" cy="50" r="7"/><text x="40" y="80" font-size="14">负相关</text></g></svg>',encoding='utf-8')
            fig=make_reused_figure(p,'#6741ad')
            try:
                mark=fig.axes[0].patches[0]
                self.assertEqual(mark.center,(20,50))
                self.assertEqual(mark.radius,7)
                self.assertLess(mark.get_facecolor()[3],0.65)
                self.assertEqual(fig.axes[0].texts[0].get_text(),'负相关')
            finally: plt.close(fig)

    def test_path_adapter_keeps_horizontal_vertical_and_curve_vertices(self):
        from sitegen.reused_figures import _path
        path=_path('M10 20 H50 V60 Q70 80 90 100 Z')
        self.assertEqual(path.vertices.tolist(),[[10,20],[50,20],[50,60],[70,80],[90,100],[10,20]])
