import importlib
import unittest
from .helpers import request_payload, result_payload

try:
    contract = importlib.import_module('term_explainer.contract')
except ModuleNotFoundError:
    contract = None


class ContractTests(unittest.TestCase):
    def test_research_limits_do_not_block_otherwise_complete_teaching(self):
        data=result_payload()
        data['limitations']=[dict(text='进一步推广需检验新的研究设计。',refs=[dict(source_id='s1',start=0,end=18)])]
        result=contract.validate_result(data,self.request)
        self.assertEqual(result.status,'complete')
        self.assertEqual(result.limitations[0]['text'],'进一步推广需检验新的研究设计。')

    def test_real_missing_method_evidence_still_blocks_complete_status(self):
        data=result_payload(); data['missing_evidence']=['尚无可读计分规则。']
        data['limitations']=[dict(text='其他研究范围仍待扩展。',refs=[dict(source_id='s1',start=0,end=18)])]
        with self.assertRaises(ValueError): contract.validate_result(data,self.request)

    def test_limitations_require_locatable_original_evidence(self):
        for refs in ([],[dict(source_id='unknown',start=0,end=2)]):
            data=result_payload(); data['limitations']=[dict(text='推广范围仍需研究。',refs=refs)]
            with self.subTest(refs=refs),self.assertRaises(ValueError): contract.validate_result(data,self.request)

    def test_malformed_paragraph_kind_is_a_validation_error(self):
        data=result_payload(); data['blocks'][0]['paragraphs'][0]['kind']=[]
        with self.assertRaises(ValueError): contract.validate_result(data,self.request)

    def test_malformed_status_and_source_relation_are_validation_errors(self):
        for field,value in [('status',[]),('source_relations',['bad'])]:
            data=result_payload(); data[field]=value
            with self.subTest(field=field), self.assertRaises(ValueError): contract.validate_result(data,self.request)

    def test_malformed_nested_model_objects_are_validation_errors_not_crashes(self):
        for field, malformed in [('formulas',['bad']),('quiz','bad'),('relations',['bad'])]:
            data = result_payload(); data[field] = malformed
            with self.subTest(field=field), self.assertRaises(ValueError):
                contract.validate_result(data, self.request)

    def test_partial_result_may_omit_unsubstantiated_modules(self):
        data = {k:v for k,v in result_payload().items() if k in {'schema_version','content_id','term','provenance'}}
        data.update(status='needs_sources',missing_evidence=['缺少方法适用条件的可读正文。'])
        result = contract.validate_result(data, self.request)
        self.assertEqual(result.status,'needs_sources')
        self.assertEqual(result.blocks,[])
        self.assertIsNone(result.visual)

    def test_bad_optional_identity_hints_are_rejected_at_input(self):
        for key,value in [('author',{'nested':'value'}),('year',True),('doi','not-a-doi')]:
            data=request_payload(); data['term'][key]=value
            with self.subTest(key=key), self.assertRaises(ValueError): contract.validate_request(data)

    def setUp(self):
        self.assertIsNotNone(contract, 'teaching contract is not implemented')
        self.request = contract.validate_request(request_payload())

    def test_valid_teaching_result_preserves_user_definition(self):
        result = contract.validate_result(result_payload(), self.request)
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.term['definition'], '想研究的人与实际调查到的人。')

    def test_generated_result_cannot_change_target_or_definition(self):
        for field, value in [('id', 'different'), ('definition', '悄悄改成另一个定义')]:
            data = result_payload(); data['term'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                contract.validate_result(data, self.request)

    def test_required_teaching_block_cannot_be_omitted(self):
        data = result_payload(); data['blocks'] = data['blocks'][:-1]
        with self.assertRaises(ValueError):
            contract.validate_result(data, self.request)

    def test_each_option_requires_its_own_explanation(self):
        data = result_payload(); data['quiz']['options'][1]['explanation'] = ''
        with self.assertRaises(ValueError):
            contract.validate_result(data, self.request)

    def test_correct_answer_must_be_one_of_four_distinct_options(self):
        data = result_payload(); data['quiz']['correct_option'] = 'e'
        with self.assertRaises(ValueError):
            contract.validate_result(data, self.request)

    def test_complete_requires_a_visual_not_decorative_empty_payload(self):
        data = result_payload(); data['visual'] = None
        with self.assertRaises(ValueError):
            contract.validate_result(data, self.request)

    def test_missing_sources_is_an_explicit_partial_result(self):
        data = result_payload(); data.update(status='needs_sources', blocks=[], visual=None, quiz=None,
                                            missing_evidence=['需要方法正文'])
        self.assertEqual(contract.validate_result(data, self.request).status, 'needs_sources')

    def test_unknown_source_and_wrong_offsets_are_rejected(self):
        for ref in [{'source_id': 'unknown', 'start': 0, 'end': 2}, {'source_id': 's1', 'start': 0, 'end': 999}]:
            data = result_payload(); data['blocks'][0]['paragraphs'][0]['refs'] = [ref]
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                contract.validate_result(data, self.request)

    def test_inline_emphasis_must_refer_to_existing_text(self):
        data = result_payload(); data['blocks'][0]['paragraphs'][0]['emphasis'] = ['另一个结论']
        with self.assertRaises(ValueError):
            contract.validate_result(data, self.request)

    def test_no_executable_code_fields_or_code_blocks_are_accepted(self):
        for change in ('field', 'fence'):
            data = result_payload()
            if change == 'field': data['r_code'] = 'lm(y~x)'
            else: data['blocks'][1]['paragraphs'][0]['text'] = '```r\nlibrary(lavaan)\n```'
            with self.subTest(change=change), self.assertRaises(ValueError):
                contract.validate_result(data, self.request)

    def test_invalid_formula_commands_are_rejected(self):
        data = result_payload(); data['formulas'] = [dict(latex=r'\href{https://example.com}{x}', symbols=[], refs=[])]
        with self.assertRaises(ValueError):
            contract.validate_result(data, self.request)

    def test_pending_relation_is_not_a_fake_classic_link(self):
        data = result_payload(); data['relations'][0]['target'] = 'unknown-term'
        with self.assertRaises(ValueError):
            contract.validate_result(data, self.request)

    def test_metadata_is_not_readable_source_text(self):
        data = request_payload(); data['sources'][0].update(scope='metadata', text='')
        request = contract.validate_request(data)
        with self.assertRaises(ValueError):
            contract.validate_result(result_payload(), request)

    def test_result_is_assigned_a_stable_server_content_id(self):
        data = result_payload(); data['content_id'] = 'model-created-id'
        result = contract.validate_result(data, self.request)
        self.assertEqual(result.content_id, 'lesson-test-001')

    def test_definition_only_request_has_no_invented_name(self):
        data = request_payload(); data['term']['zh'] = ''; data['term']['en'] = ''
        self.assertEqual(contract.validate_request(data).term['zh'], '')

    def test_source_text_limit_is_enforced_without_truncation(self):
        data = request_payload(); data['sources'][0]['text'] = '字' * 60001
        with self.assertRaises(ValueError):
            contract.validate_request(data)


if __name__ == '__main__': unittest.main()
