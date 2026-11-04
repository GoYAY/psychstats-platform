"""Offline checks for the bounded paid-review harness. No private files."""
import json,unittest
from tests.term_explainer.helpers import request_payload,result_payload
from term_explainer.online.visual_review import build_review_context,review_targets,validate_review

class CalibrationTests(unittest.TestCase):
    def cases(self):
        from tools.qa_visual_review_calibration import controls
        r=request_payload();l=result_payload()
        return controls(dict(checkpoint=dict(decision=dict(request=r,sources=r['sources']),lesson=l)))

    def test_controls_keep_question_focus_and_numeric_role_consistent(self):
        cases=self.cases();self.assertEqual(len(cases),3)
        by_name={name:(r,l,s) for name,r,l,s in cases}
        r,l,s=by_name['whole-grouped']
        self.assertIn('整体',r['question']);self.assertEqual(l['visual']['presentation']['focus'],'whole')
        self.assertEqual(l['visual']['presentation']['numeric_role'],'relative')
        r,l,s=by_name['category-grouped']
        self.assertIn('每个',r['question']);self.assertEqual(l['visual']['presentation']['focus'],'local')
        self.assertEqual(l['visual']['presentation']['numeric_role'],'exact')
        self.assertEqual(l['visual']['payload']['x_label'],'满意度选项')
        self.assertEqual(l['visual']['payload']['x_unit'],'')
        self.assertIn('满意',l['visual']['alt'])
        self.assertNotIn('成绩',json.dumps(l['visual'],ensure_ascii=False))
        self.assertNotIn('expected',json.dumps(cases))

    def test_old_invalid_scalar_stays_invalid_not_silently_coerced(self):
        _,r,l,s=self.cases()[0]
        context=build_review_context(r,l,s)
        context['review_targets']=review_targets(l['visual'])
        old=dict(decision='pass',reason='对象清楚。',object_paths=['/payload/scenes/0/objects/0/id'],refs=[])
        with self.assertRaises(ValueError):validate_review(old,context,s)
