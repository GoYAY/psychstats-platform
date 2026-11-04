"""Offline regressions for the observed section-reader quality failures."""
from copy import deepcopy
import hashlib
import importlib
import json
import unittest

from term_explainer.deepseek import DeepSeekClient
from term_explainer.section_reading import create_reading_state, read_next_section
from .helpers import request_payload
from .test_pipeline import analysis_payload

try:
    quality = importlib.import_module('term_explainer.section_quality')
except ModuleNotFoundError:
    quality = None


class SectionQualityTests(unittest.TestCase):
    def test_other_explicit_identity_reason_still_stops_verified_upload(self):
        state=create_reading_state(self.request,self.source,self.headings,max_calls=1,identity_review=self.review())
        data=self.analysis(identity=dict(status='uncertain',reason_code='conflicting_edition',reason='版本归属不明确。'))
        read_next_section(state,self.request,self.source,self.client([data]))
        self.assertEqual(state['status'],'needs_disambiguation')

    def test_generic_uncertainty_is_an_observation_not_a_revocation_of_file_proof(self):
        state=create_reading_state(self.request,self.source,self.headings,max_calls=1,identity_review=self.review())
        data=self.analysis(identity=dict(status='uncertain',reason='无法仅凭当前片段再次核实全部书目。'))
        read_next_section(state,self.request,self.source,self.client([data]))
        self.assertEqual(state['next_section'],1)
        self.assertEqual(state['readings'][0]['identity_observations'][0]['reason'],'无法仅凭当前片段再次核实全部书目。')

    def test_verified_identity_survives_uncertain_interior_note_without_magic_code(self):
        state=create_reading_state(self.request,self.source,self.headings,max_calls=1,identity_review=self.review())
        data=self.analysis(identity=dict(status='uncertain',reason='本小节未重印题名作者和DOI。'))
        read_next_section(state,self.request,self.source,self.client([data]))
        self.assertEqual(state['next_section'],1)
        self.assertEqual(state['readings'][0]['identity_observations'][0]['status'],'uncertain')

    def setUp(self):
        self.request = request_payload()
        self.request['network_allowed'] = True
        self.source = deepcopy(self.request['sources'][0])
        padding='本节为背景说明，用于模拟真实论文正文篇幅。'*120
        self.source.update(title='Test Paper', doi='10.1234/test', authors=['A. Author'],
            year=2025, origin='user', scope='full_text',
            text=('Intro\nTest Paper DOI:10.1234/test\nOnly under condition A.\n'+padding
                  +'\n\nMethods\nNew material.\n'+padding))
        self.headings = [{'title':'Intro','start':0},
                         {'title':'Methods','start':self.source['text'].index('Methods')}]
        self.sent = []

    def review(self):
        return dict(status='matches', source_id='s1',
            source_hash=hashlib.sha256(self.source['text'].encode()).hexdigest(),
            bibliography=dict(title='Test Paper', doi='10.1234/test', authors=['A. Author'],year=2025),
            reviewer='local_source_review', evidence=[dict(source_id='s1',start=6,end=31)])

    def analysis(self, *, conditions=None, identity=None, summary='Brief context.'):
        data = analysis_payload()
        data.update(rolling_summary=summary, key_conditions=conditions or [])
        if identity:
            data['reading_notes'][0]['identity_check'] = identity
        for item in data['reading_notes'] + data['claims'] + data['synthesis']:
            item['evidence'] = [dict(source_id='s1',span_id='s1#c0000')]
        return data

    def client(self, replies):
        def transport(url,payload,headers,timeout):
            self.sent.append(payload)
            return dict(model='deepseek-flash',usage={},choices=[dict(finish_reason='stop',
                message=dict(content=json.dumps(replies.pop(0),ensure_ascii=False)))])
        return DeepSeekClient(api_key='offline-test-only',max_calls=3,transport=transport)

    def test_intake_identity_is_separate_from_unverified_summary_on_resume(self):
        state = create_reading_state(self.request,self.source,self.headings,max_calls=2,
                                     identity_review=self.review())
        client = self.client([self.analysis(),self.analysis()])
        read_next_section(state,self.request,self.source,client)
        read_next_section(state,self.request,self.source,client)
        context = json.loads(self.sent[1]['messages'][1]['content'])
        self.assertEqual(context['document_identity']['status'],'matches')
        self.assertEqual(context['document_identity']['source_id'],'s1')
        self.assertNotIn('evidence',context['document_identity'])
        self.assertNotIn('Only under condition A.',json.dumps(context))
        self.assertNotIn('document_identity',context['reading_memory'])
        self.assertFalse(state['can_generate'])

    def test_upload_origin_alone_does_not_certify_document_identity(self):
        state = create_reading_state(self.request,self.source,self.headings,max_calls=1)
        read_next_section(state,self.request,self.source,self.client([self.analysis()]))
        context = json.loads(self.sent[0]['messages'][1]['content'])
        self.assertEqual(context.get('document_identity',{}).get('status'),'not_reviewed')

    def test_identity_review_rejects_changed_text_metadata_and_unrelated_position(self):
        for field in ('source_hash','bibliography','evidence'):
            record = self.review()
            if field == 'source_hash': record[field] = '0'*64
            elif field == 'bibliography': record[field]['doi'] = '10.1234/other'
            else: record[field] = [dict(source_id='s1',start=32,end=55)]
            with self.subTest(field=field),self.assertRaises(ValueError):
                create_reading_state(self.request,self.source,self.headings,max_calls=1,identity_review=record)

    def test_real_identity_mismatch_stops_even_for_previously_reviewed_upload(self):
        state = create_reading_state(self.request,self.source,self.headings,max_calls=1,
                                     identity_review=self.review())
        data = self.analysis(identity=dict(status='mismatch',reason='实际正文出现另一个 DOI。'))
        read_next_section(state,self.request,self.source,self.client([data]))
        self.assertEqual(state['status'],'needs_disambiguation')
        self.assertEqual(state['next_section'],0)

    def test_absent_interior_header_does_not_erase_bound_intake_review(self):
        state = create_reading_state(self.request,self.source,self.headings,max_calls=2,
                                     identity_review=self.review())
        first=self.analysis()
        second=self.analysis(identity=dict(status='uncertain',reason_code='not_repeated_in_section',
                                            reason='本小节未重复标题与 DOI。'))
        read_next_section(state,self.request,self.source,self.client([first,second]))
        read_next_section(state,self.request,self.source,self.client([second]))
        self.assertEqual(state['next_section'],2)
        self.assertEqual(state['identity_review']['status'],'matches')
        self.assertEqual(state['readings'][1]['identity_observations'][0]['status'],'uncertain')

    def test_missing_header_without_review_is_not_accepted_as_confirmed_identity(self):
        state=create_reading_state(self.request,self.source,self.headings,max_calls=1)
        data=self.analysis(identity=dict(status='uncertain',reason_code='not_repeated_in_section',reason='无题名。'))
        read_next_section(state,self.request,self.source,self.client([data]))
        self.assertEqual(state['status'],'needs_disambiguation')

    def test_key_condition_survives_later_summary_omission_with_original_evidence(self):
        state=create_reading_state(self.request,self.source,self.headings,max_calls=2)
        condition=dict(id='a',statement='Only valid under condition A.',
                       evidence=[dict(source_id='s1',span_id='s1#c0000')])
        client=self.client([self.analysis(conditions=[condition]),self.analysis(summary='Only new material.')])
        read_next_section(state,self.request,self.source,client)
        read_next_section(state,self.request,self.source,client)
        context=json.loads(self.sent[1]['messages'][1]['content'])
        pinned=context['reading_memory']['key_conditions'][0]
        self.assertEqual(pinned['statement'],'Only valid under condition A.')
        self.assertFalse(pinned['content_verified'])
        self.assertEqual(pinned['id'],'unit-001--a')
        self.assertIn('Only under condition A.',quality.recall_conditions(state,self.source,[pinned['id']])[0]['excerpt'])
        self.assertEqual(state['readings'][1]['rolling_summary'],'Only new material.')

    def test_condition_cannot_cite_memory_in_place_of_original_source(self):
        state=create_reading_state(self.request,self.source,self.headings,max_calls=1)
        bad=dict(id='a',statement='A condition.',evidence=[dict(source_id='reading_memory',start=0,end=2)])
        with self.assertRaises(Exception):
            read_next_section(state,self.request,self.source,self.client([self.analysis(conditions=[bad])]))
        self.assertEqual(state['next_section'],0)

    def test_unknown_condition_cannot_retrieve_arbitrary_private_source(self):
        self.assertIsNotNone(quality,'section quality helpers are missing')
        state=create_reading_state(self.request,self.source,self.headings,max_calls=0)
        with self.assertRaises(ValueError): quality.recall_conditions(state,self.source,['invented'])

    def test_oversized_retained_condition_context_stops_before_paid_boundary(self):
        self.assertIsNotNone(quality,'section quality helpers are missing')
        state=create_reading_state(self.request,self.source,self.headings,max_calls=2)
        conditions=[dict(id=f'a{i}',statement='条件'*200,
                         evidence=[dict(source_id='s1',span_id='s1#c0000')]) for i in range(4)]
        read_next_section(state,self.request,self.source,self.client([self.analysis(conditions=conditions)]))
        client=self.client([])
        read_next_section(state,self.request,self.source,client,context_limit=100)
        self.assertEqual(client.calls,0)
        self.assertEqual(state['reserved_calls'],1)
        self.assertEqual(state['status'],'needs_context_selection')

    def test_cross_page_incomplete_citation_is_flagged_without_rewriting_it(self):
        self.assertIsNotNone(quality,'section quality helpers are missing')
        text='Intro\nPrior studies were more informative and\n\n===== PDF PAGE 2 =====\nTable 1. Example.\nprovided accurate scores.'
        source=dict(self.source,text=text)
        claim=dict(id='c',statement='More informative and accurate.',evidence=[dict(source_id='s1',
                   start=text.index('Table'),end=len(text))])
        original=deepcopy(claim)
        flags=quality.citation_warnings(source,[claim],start=0,end=len(text))
        self.assertEqual(flags[0]['code'],'preceding_span_may_complete_sentence')
        self.assertEqual(flags[0]['claim_id'],'c')
        self.assertEqual(claim,original)

    def test_cut_word_suggests_following_span_but_never_certifies_entailment(self):
        self.assertIsNotNone(quality,'section quality helpers are missing')
        text='Intro\nA dominant stan-\n\n===== PDF PAGE 2 =====\ndard (criterion).'
        claim=dict(id='c',evidence=[dict(source_id='s1',start=0,end=text.index('\n\n'))])
        flags=quality.citation_warnings(dict(self.source,text=text),[claim],start=0,end=len(text))
        self.assertEqual(flags[0]['code'],'following_span_may_complete_sentence')
        self.assertEqual(flags[0]['adjacent_evidence']['start'],text.index('dard'))

    def test_complete_sentence_control_has_no_boundary_warning(self):
        self.assertIsNotNone(quality,'section quality helpers are missing')
        text='Intro\nA complete statement.\n\n===== PDF PAGE 2 =====\nAnother complete statement.'
        claim=dict(id='c',evidence=[dict(source_id='s1',start=0,end=text.index('\n\n'))])
        self.assertEqual(quality.citation_warnings(dict(self.source,text=text),[claim],start=0,end=len(text)),[])

    def test_identity_observations_are_derived_not_model_supplied(self):
        state=create_reading_state(self.request,self.source,self.headings,max_calls=1)
        data=self.analysis()
        data['identity_observations']=[dict(status='invented',reason='An untrusted extra field.')]
        read_next_section(state,self.request,self.source,self.client([data]))
        self.assertEqual(state['readings'][0]['identity_observations'],[])

    def test_model_cannot_mark_a_retained_condition_as_reviewed(self):
        state=create_reading_state(self.request,self.source,self.headings,max_calls=1)
        condition=dict(id='a',statement='A condition.',content_verified=True,
                       evidence=[dict(source_id='s1',span_id='s1#c0000')])
        read_next_section(state,self.request,self.source,self.client([self.analysis(conditions=[condition])]))
        self.assertFalse(state['readings'][0]['key_conditions'][0].get('content_verified',False))

    def test_explicit_anchor_conflict_is_never_suppressed_by_a_missing_header_code(self):
        state=create_reading_state(self.request,self.source,self.headings,max_calls=1,
                                   identity_review=self.review())
        data=self.analysis(identity=dict(status='uncertain',reason_code='not_repeated_in_section',reason='No header.'))
        data['anchor_conflicts']=['用户所指方法版本与正文所述方法版本不同。']
        read_next_section(state,self.request,self.source,self.client([data]))
        self.assertEqual(state['status'],'needs_disambiguation')
        self.assertEqual(state['next_section'],0)

    def test_saved_condition_cannot_point_into_an_unread_section(self):
        state=create_reading_state(self.request,self.source,self.headings,max_calls=2)
        condition=dict(id='a',statement='A condition.',evidence=[dict(source_id='s1',span_id='s1#c0000')])
        read_next_section(state,self.request,self.source,self.client([self.analysis(conditions=[condition])]))
        state['readings'][0]['key_conditions'][0]['evidence']=[dict(source_id='s1',
            start=self.source['text'].index('Methods'),end=len(self.source['text']))]
        fresh=self.client([])
        with self.assertRaises(ValueError): read_next_section(state,self.request,self.source,fresh)
        self.assertEqual(fresh.calls,0)

    def test_recall_refuses_oversized_evidence_instead_of_clipping_it(self):
        state=create_reading_state(self.request,self.source,self.headings,max_calls=1)
        condition=dict(id='a',statement='A condition.',evidence=[dict(source_id='s1',span_id='s1#c0000')])
        read_next_section(state,self.request,self.source,self.client([self.analysis(conditions=[condition])]))
        with self.assertRaises(ValueError): quality.recall_conditions(state,self.source,['section-001--a'],max_chars=1)

