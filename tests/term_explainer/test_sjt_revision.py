import unittest
from tools.revise_generated_sjt import revise_lesson
from tests.term_explainer.helpers import result_payload


class SJTRevisionTests(unittest.TestCase):
    def test_existing_revision_is_preserved_and_new_visual_teaches_response_mechanism(self):
        original=result_payload();original['term']['zh']='情境判断测验';original['term']['en']=''
        revised=revise_lesson(original,[dict(id='s1',text='The situational judgement test presents situations.')])
        self.assertEqual(original['term']['en'],'')
        self.assertEqual(revised['provenance']['verified_identity']['en'],'situational judgement test')
        self.assertEqual(revised['visual']['origin'],'teaching')
        labels=[o['label'] for scene in revised['visual']['payload']['scenes'] for o in scene['objects']]
        self.assertIn('B：先问具体顾虑',labels)
        self.assertIn('选B → 2分',labels)
        self.assertNotIn('四舍五入',revised['visual']['takeaway'])
        self.assertEqual(original['blocks'],revised['blocks'])

    def test_no_verified_english_source_means_no_invented_name(self):
        original=result_payload();original['term']['zh']='情境判断测验';original['term']['en']=''
        with self.assertRaises(ValueError):revise_lesson(original,[dict(id='s1',text='Unrelated paper')])
