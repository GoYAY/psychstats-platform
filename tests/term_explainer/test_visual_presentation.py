import importlib
import json
from copy import deepcopy
from pathlib import Path
import unittest
import tempfile
import zipfile
from term_explainer.figures import validate_visual
from .helpers import result_payload
from .helpers import request_payload

VECTORS=json.loads((Path(__file__).parents[1]/'fixtures/visual-presentation.json').read_text(encoding='utf-8'))

class PresentationTests(unittest.TestCase):
    def test_inspection_bounds_match_text_and_category_constraints(self):
        validate=self.api();base=deepcopy(VECTORS['visuals']['bar1']);base['presentation']=dict(version=1,focus='local',numeric_role='exact',layout='single',interaction='inspect')
        for key,limit in [('title',120),('takeaway',400),('alt',1000)]:
            v=deepcopy(base);v[key]='字'*(limit+1)
            with self.subTest(key=key),self.assertRaises(ValueError):validate(v)
        v=deepcopy(base);v['payload']['series'][0]['x']=[1.0,'1']
        with self.assertRaises(ValueError):validate(v)
        v['payload']['series'][0]['x']=[1e-6,'0.000001']
        with self.assertRaises(ValueError):validate(v)

    def api(self):
        try:return importlib.import_module('term_explainer.visual_presentation').validate_presentation
        except ModuleNotFoundError:self.fail('Executable presentation validator missing')

    def test_shared_vectors_and_input_immutability(self):
        validate=self.api()
        for case in VECTORS['cases']:
            with self.subTest(case=case['name']):
                visual=deepcopy(VECTORS['visuals'][case['base']])
                if 'presentation' in case:visual['presentation']=deepcopy(case['presentation'])
                if 'override_payload' in case:visual['payload']=deepcopy(case['override_payload'])
                original=deepcopy(visual)
                if case['ok']:
                    actual=validate(visual,required=case.get('required',False))
                    self.assertEqual(actual,case.get('presentation'))
                    if actual is not None:actual['focus']='changed';self.assertEqual(visual,original)
                else:
                    with self.assertRaises(ValueError):validate(visual,required=case.get('required',False))
                self.assertEqual(visual,original)

    def test_real_figure_boundary_rejects_invalid_metadata_not_only_standalone_validator(self):
        visual=result_payload()['visual'];visual['presentation']={'version':2}
        with self.assertRaisesRegex(ValueError,'presentation'):validate_visual(visual)

    def test_new_presentation_survives_package_roundtrip(self):
        from term_explainer.library_export import export_package
        request=request_payload();lesson=result_payload()
        policy={'version':1,'focus':'structure','numeric_role':'none','layout':'story','interaction':'none'}
        lesson['visual']['presentation']=policy
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'lesson.zip'
            export_package(request,lesson,sources=request['sources'],originals={},figures={},term_id=request['term']['id'],output=target)
            with zipfile.ZipFile(target) as archive:restored=json.loads(archive.read('library.json'))
        self.assertEqual(restored['revisions'][0]['lesson']['visual']['presentation'],policy)
