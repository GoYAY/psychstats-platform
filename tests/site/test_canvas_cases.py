import importlib
from pathlib import Path
import tempfile
import unittest

class CanvasCasesTest(unittest.TestCase):
    def prepare(self):
        try:return importlib.import_module('tools.prepare_canvas_cases').prepare_cases
        except ModuleNotFoundError:self.fail('Canvas cases preparer missing')
    def test_private_output_cannot_be_served(self):
        root=Path(__file__).resolve().parents[2]
        with self.assertRaises(ValueError):self.prepare()(root/'site/canvas-private')
    def test_actual_three_cases_keep_explicit_context_sources_and_negative_control(self):
        with tempfile.TemporaryDirectory() as d:
            result=self.prepare()(Path(d))
            case=result['human-ai'];self.assertEqual(len(case['records']['terms']),3)
            view=case['records']['graphViews'][0]
            self.assertEqual(len(view['contextRefs']),4)
            self.assertEqual({c['glossaryId'] for c in view['contextRefs']},{'g-behavioral-drift','g-metacognition','g-metacognitive-monitoring','g-metacognitive-control'})
            self.assertFalse(any(e['from']['id']=='dominant-trait-profile' and e['to']['space']=='personal' for e in case['records']['edges']))
            self.assertEqual(sum(e['from']['id']=='dominant-trait-profile' and e['to']['space']=='official' for e in case['records']['edges']),2)
            self.assertEqual(case['newTeachingRelations'],[])
            self.assertEqual(result['oracle']['factor-analysis']['coreCount'],26)
            self.assertEqual(result['oracle']['multilevel-longitudinal']['coreCount'],14)
