from copy import deepcopy
import json
import unittest
from term_explainer.deepseek import ModelReply
from term_explainer.pipeline import PipelineError, _reference_candidates, resolve_reference_candidates
from term_explainer.online.diagnostics import describe_failure


TEXT = 'A verified method explains choices.\nReferences\nA verified method. https://doi.org/10.1000/test\n'
SOURCES = [dict(id='paper', title='Parent paper', text=TEXT, scope='full_text')]
BAD = dict(id='ref-one', parent_id='paper', title='A verified method', doi='10.1000/test',
           url='https://doi.org/10.1000/test', depth=1, priority=3, purpose='Background', module='background',
           reference_ref=dict(source_id='paper', start=0, end=34))
GOOD = dict(BAD, reference_ref=dict(source_id='paper', start=TEXT.index('A verified method.', 35), end=len(TEXT)))


class Replies:
    def __init__(self, value): self.value=value; self.messages=[]
    def generate(self, messages):
        self.messages.append(messages)
        return ModelReply(json.dumps(self.value), 'offline', {'total_tokens':10}, 'stop')


class ReferenceHardeningTests(unittest.TestCase):
    def repair(self, candidates):
        client=Replies({'reference_candidates':candidates})
        value=resolve_reference_candidates({'reference_candidates':[deepcopy(BAD)]},SOURCES,
                                           client=client,usage=[],anchor={'term':'Example'})
        return value,client

    def test_repair_receives_rejected_items_and_retrievable_source_spans(self):
        value,client=self.repair([deepcopy(GOOD)])
        prompt=json.loads(client.messages[0][-1]['content'])
        self.assertEqual(prompt['rejected_candidates'][0]['id'],'ref-one')
        source=prompt['sources'][0]
        self.assertTrue(any('10.1000/test' in s['text'] for s in source['spans']))
        self.assertEqual(value['reference_repair'],{'attempts':1,'rejected':1,'accepted':1})

    def test_repair_cannot_erase_required_candidates(self):
        with self.assertRaises(PipelineError) as caught:self.repair([])
        self.assertEqual(caught.exception.code,'invalid_reference_candidate')
        self.assertEqual(caught.exception.reference_repair,dict(attempts=1,rejected=1,accepted=0))

    def test_repair_cannot_replace_or_duplicate_reference_identity(self):
        for candidates in [[dict(GOOD,id='different')],[GOOD,GOOD],[dict(GOOD,parent_id='other')]]:
            with self.subTest(candidates=candidates),self.assertRaises(PipelineError):self.repair(candidates)

    def test_doi_wrong_span_exposes_safe_subreason(self):
        with self.assertRaises(PipelineError) as caught:_reference_candidates({'reference_candidates':[BAD]},SOURCES)
        self.assertEqual(caught.exception.subcode,'reference_doi_not_in_span')

    def test_known_code_does_not_authorize_echoing_untrusted_exception_text(self):
        error=PipelineError('invalid_reference_candidate','PRIVATE_PAPER_CONTENT')
        code,detail=describe_failure(error,stage='reading')
        self.assertEqual(code,'invalid_reference_candidate')
        self.assertNotIn('PRIVATE_PAPER_CONTENT',json.dumps(detail))

    def test_valid_candidate_costs_zero_repair_calls(self):
        client=Replies({})
        out=resolve_reference_candidates({'reference_candidates':[GOOD]},SOURCES,client=client,usage=[])
        self.assertEqual(client.messages,[])
        self.assertEqual(len(out['reference_candidates']),1)
