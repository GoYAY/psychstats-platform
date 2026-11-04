import importlib
import math
import unittest
from matplotlib import pyplot as plt

class OperationalExamplesTests(unittest.TestCase):
    def test_preview_uses_updated_plot_and_caption_without_changing_baseline(self):
        from tools.prepare_local_library_preview import overlay_operational_examples
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);(out/'terms').mkdir()
            page='<main><figure class="plain-example-visual illustrated-example"><h3>旧说明</h3><picture><img src="../assets/examples/p-value.svg?v=old"></picture><figcaption>旧图注</figcaption></figure><p>不改其他内容</p></main>'
            (out/'terms/p-value.html').write_text(page,encoding='utf8')
            overlay_operational_examples(out)
            current=(out/'terms/p-value.html').read_text(encoding='utf8')
            self.assertIn('2/20=0.10',current);self.assertNotIn('旧图注',current)
            self.assertIn('不改其他内容',current)
            self.assertNotIn('?v=old',current)
            self.assertIn('permutation-allocations',(out/'assets/examples/p-value.svg').read_text(encoding='utf8'))
    def api(self):
        try:return importlib.import_module('sitegen.story_operational')
        except ModuleNotFoundError:self.fail('Operational teaching example renderer missing')
    def test_permutation_marks_are_all_twenty_allocations_and_two_extremes(self):
        result=self.api().permutation_example([6,8,10],[1,3,5])
        self.assertEqual(result['observed'],5)
        self.assertEqual(len(result['differences']),20)
        self.assertEqual(sum(result['extreme']),2)
        self.assertAlmostEqual(result['p'],0.1)
    def test_likelihood_is_product_of_heights_for_the_same_three_records(self):
        result=self.api().likelihood_example([6,6.5,7],[6,8],1)
        self.assertEqual(result['observations'],[6,6.5,7])
        self.assertAlmostEqual(result['likelihoods'][0],(2*math.pi)**(-1.5)*math.exp(-.625))
        self.assertAlmostEqual(result['likelihoods'][1],(2*math.pi)**(-1.5)*math.exp(-3.625))
        self.assertEqual(result['mle'],6.5)
    def test_reliability_pairs_preserve_same_essay_and_expose_constant_two_point_offset(self):
        result=self.api().agreement_example([70,80,85,90],[72,82,87,92])
        self.assertEqual(result['differences'],[2,2,2,2]);self.assertTrue(result['same_order'])
    def test_real_dispatch_renders_data_marks_for_desktop_and_mobile(self):
        from sitegen.rollout_figures import make_figure
        expected={'p-value':('permutation-allocations',20),'likelihood':('observed-sleep',3),'maximum-likelihood':('mle-location',1),'reliability':('rater-pairs',4)}
        for mobile in [False,True]:
            for slug,(gid,count) in expected.items():
                with self.subTest(slug=slug,mobile=mobile):
                    fig=make_figure(slug,{'kind':'story'},'#6741ad',mobile)
                    try:
                        marks=[a for ax in fig.axes for a in ax.collections if a.get_gid()==gid]
                        self.assertEqual(len(marks),1,f'{slug} missing quantified marks')
                        self.assertEqual(len(marks[0].get_offsets()),count)
                        if slug=='p-value':self.assertTrue(any('0.10' in t.get_text() for t in fig.texts))
                    finally:plt.close(fig)

if __name__=='__main__':unittest.main()
