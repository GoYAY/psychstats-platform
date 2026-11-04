from copy import deepcopy
import unittest
from term_explainer.contract import validate_request
from term_explainer.pipeline import prepare_evidence,generate_prepared_lesson,PipelineError
from tests.term_explainer.helpers import request_payload,result_payload
from tests.term_explainer.test_pipeline import analysis_payload,ExternalDouble


class IdentityTests(unittest.TestCase):
    def setup_input(self,en=''):
        raw=request_payload();raw['term']['en']=en
        raw['sources'][0]['text']+='\nThe sample is also called a Sample.'
        analysis=analysis_payload()
        analysis['term_identity']={'en':'Sample','refs':[{'source_id':'s1','span_id':'s1#p0001'}]}
        return raw,analysis

    def test_source_supported_english_is_compiled_without_replacing_user_anchor(self):
        raw,analysis=self.setup_input();request=validate_request(raw)
        prepared=prepare_evidence(request,ExternalDouble([analysis]))
        value=result_payload();value['term']['en']=''
        result=generate_prepared_lesson(request,ExternalDouble([value]),prepared)
        self.assertEqual(result.lesson.provenance['verified_identity']['en'],'Sample')
        self.assertEqual(result.lesson.term['en'],'')
        self.assertEqual(result.lesson.provenance['original_anchor'],raw['term'])

    def test_invented_english_without_literal_source_support_is_rejected(self):
        raw,analysis=self.setup_input();analysis['term_identity']['en']='Invented Official English'
        with self.assertRaises(PipelineError):prepare_evidence(validate_request(raw),ExternalDouble([analysis]))

    def test_existing_user_english_is_not_overridden(self):
        raw,analysis=self.setup_input('User supplied name')
        prepared=prepare_evidence(validate_request(raw),ExternalDouble([analysis]))
        self.assertIsNone(prepared.evidence.get('term_identity'))

    def test_no_english_evidence_does_not_force_fabricated_translation(self):
        raw,analysis=self.setup_input();analysis.pop('term_identity')
        prepared=prepare_evidence(validate_request(raw),ExternalDouble([analysis]))
        self.assertIsNone(prepared.evidence.get('term_identity'))
