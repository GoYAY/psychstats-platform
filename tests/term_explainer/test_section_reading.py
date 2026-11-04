"""Section boundaries, one-paper identity and evidence-carrying rolling memory."""
import importlib
import json
import unittest
from copy import deepcopy
from term_explainer.deepseek import DeepSeekClient
from .helpers import request_payload
from .test_pipeline import analysis_payload

try:
    reader=importlib.import_module('term_explainer.section_reading')
except ModuleNotFoundError:
    reader=None


class SectionReadingTests(unittest.TestCase):
    def test_reader_sends_actual_condition_reference_limit_to_model(self):
        reader.read_next_section(self.state(),self.request,self.source,self.client([self.analysis()]))
        context=json.loads(self.sent[0]['messages'][1]['content'])
        self.assertEqual(context['section_output_limits'],dict(claims=8,claim_evidence=2,
            key_conditions=4,key_condition_evidence=2,rolling_summary_chars=2000))

    def test_section_rejects_term_or_unread_document_as_source_relation(self):
        from term_explainer.pipeline import PipelineError
        for target in ('original-term', 's2', 's1'):
            with self.subTest(target=target):
                bad=self.analysis()
                bad['source_relations']=[dict(source='s1',target=target,type='background',
                    reason='A contribution is not a document-to-document relation.',
                    evidence=[dict(source_id='s1',span_id='s1#c0000')])]
                state=self.state()
                with self.assertRaises(PipelineError) as caught:
                    reader.read_next_section(state,self.request,self.source,self.client([bad]))
                self.assertEqual(caught.exception.code,'invalid_evidence_analysis')
                self.assertEqual(state['next_section'],0)
                self.assertEqual(state['readings'],[])
        good=self.state()
        reader.read_next_section(good,self.request,self.source,self.client([self.analysis()]))
        self.assertEqual(good['next_section'],1)

    def test_related_work_metadata_reaches_reader_without_becoming_citable_body(self):
        state=self.state();state['source_set_context']={'role':'reading_plan_not_evidence','sources':[{'id':'s1','title':'Target Paper'},{'id':'s2','title':'Comparator Paper'}],'title_mentions':[]}
        client=self.client([self.analysis()]);reader.read_next_section(state,self.request,self.source,client)
        context=json.loads(self.sent[0]['messages'][1]['content'])
        self.assertEqual(context['reading_memory']['source_set']['sources'][1]['title'],'Comparator Paper')
        self.assertEqual([s['id'] for s in context['sources']],['s1'])
        bad=self.analysis();bad['claims'][0]['evidence']=[{'source_id':'s2','start':0,'end':5}]
        other=self.state();other['source_set_context']=state['source_set_context']
        with self.assertRaises(Exception):reader.read_next_section(other,self.request,self.source,self.client([bad]))

    def setUp(self):
        self.assertIsNotNone(reader,'section reader is not implemented')
        self.request=request_payload(); self.request['network_allowed']=True
        self.source=deepcopy(self.request['sources'][0])
        self.source['text']='Intro\n'+('First section evidence. '*110)+'\n\nMethods\n'+('Second section evidence. '*110)
        self.methods_at=6+24*110+2
        self.headings=[{'title':'Intro','start':0},{'title':'Methods','start':self.methods_at}]

    def state(self,budget=2):
        return reader.create_reading_state(self.request,self.source,self.headings,max_calls=budget)

    def client(self,replies):
        self.sent=[]
        def transport(url,payload,headers,timeout):
            self.sent.append(payload)
            return {'model':'deepseek-flash','usage':{},'choices':[{'finish_reason':'stop',
                'message':{'content':json.dumps(replies.pop(0),ensure_ascii=False)}}]}
        return DeepSeekClient(api_key='not-a-real-key',max_calls=4,transport=transport)

    def analysis(self,memory='A compact cross-section context.'):
        data=analysis_payload(); data['rolling_summary']=memory; data['key_conditions']=[]
        for entry in data['reading_notes']+data['claims']+data['synthesis']:
            for ref in entry['evidence']: ref['span_id']='s1#c0000'
        return data

    def test_condition_ids_are_normalized_instead_of_blocking_the_section(self):
        data=self.analysis();data['key_conditions']=[
            dict(id='sec-4.5-cond-1',statement='Only CFA and criterion evidence here.',
                 evidence=[dict(source_id='s1',span_id='s1#c0000')]),
            dict(id='sec-4.5-cond-2',statement='Positive correlations are not causal.',
                 evidence=[dict(source_id='s1',span_id='s1#c0000')])]
        state=self.state(); client=self.client([deepcopy(data),self.analysis()])
        reader.read_next_section(state,self.request,self.source,client)
        conditions=state['readings'][0]['key_conditions']
        self.assertEqual([c['id'] for c in conditions],['sec-4-5-cond-1','sec-4-5-cond-2'])
        self.assertEqual(conditions[0]['statement'],'Only CFA and criterion evidence here.')
        self.assertEqual(conditions[0]['evidence'][0]['source_id'],'s1')
        audit=state['analysis_contracts'][state['sections'][0]['id']]
        self.assertEqual(audit['normalized_fields'],['key_conditions.id'])
        self.assertEqual(audit['normalization_reason'],'condition_id_normalized_for_host_schema')
        # Normalized IDs remain valid memory for the next section.
        reader.read_next_section(state,self.request,self.source,client)
        self.assertEqual([c['id'] for c in state['readings'][1]['key_conditions']],[])

    def test_sections_use_real_headings_and_cover_original_without_loss(self):
        state=self.state()
        self.assertEqual([(u['title'],u['start'],u['end'],u['section_ids']) for u in state['sections']],
            [('Intro',0,self.methods_at,['section-001']),('Methods',self.methods_at,len(self.source['text']),['section-002'])])
        self.assertEqual(state['paper_id'],'s1')
        self.assertEqual(state['next_section'],0)

    def test_false_heading_or_reversed_boundaries_are_rejected(self):
        for headings in ([{'title':'Invented','start':0}],list(reversed(self.headings))):
            with self.subTest(headings=headings),self.assertRaises(ValueError):
                reader.create_reading_state(self.request,self.source,headings,max_calls=2)

    def test_oversized_section_requests_subheadings_not_percentage_splitting(self):
        self.source['text']='Intro\n'+'x'*60001
        state=reader.create_reading_state(self.request,self.source,[{'title':'Intro','start':0}],max_calls=2)
        client=self.client([])
        reader.read_next_section(state,self.request,self.source,client)
        self.assertEqual(state['status'],'needs_subsections')
        self.assertEqual(client.calls,0)

    def test_next_section_receives_summary_not_previous_full_body(self):
        state=self.state(); client=self.client([self.analysis('First section compact summary.'),self.analysis()])
        reader.read_next_section(state,self.request,self.source,client)
        reader.read_next_section(state,self.request,self.source,client)
        context=json.loads(self.sent[1]['messages'][1]['content'])
        self.assertEqual(context['reading_memory']['summary'],'First section compact summary.')
        self.assertNotIn('First section evidence.',json.dumps(context))
        self.assertIn('Second section evidence.',json.dumps(context))
        self.assertEqual(state['status'],'read_all_requires_review')
        self.assertFalse(state['can_generate'])
        self.assertEqual(client.calls,2)

    def test_global_evidence_offsets_map_back_to_the_original_paper(self):
        state=self.state(); client=self.client([self.analysis(),self.analysis()])
        reader.read_next_section(state,self.request,self.source,client)
        reader.read_next_section(state,self.request,self.source,client)
        ref=state['readings'][1]['claims'][0]['evidence'][0]
        self.assertEqual(ref['source_id'],'s1')
        self.assertGreaterEqual(ref['start'],self.methods_at)
        self.assertLessEqual(ref['end'],len(self.source['text']))
        self.assertTrue(self.source['text'][ref['start']:ref['end']].strip())

    def test_summary_cannot_be_used_as_a_new_evidence_source(self):
        state=self.state(); bad=self.analysis()
        bad['claims'][0]['evidence']=[{'source_id':'reading_memory','start':0,'end':5}]
        with self.assertRaises(Exception):
            reader.read_next_section(state,self.request,self.source,self.client([bad]))
        self.assertEqual(state['next_section'],0)
        self.assertEqual(state['status'],'failed_requires_review')

    def test_budget_stop_keeps_completed_section_and_does_not_reread(self):
        state=self.state(budget=1); client=self.client([self.analysis()])
        reader.read_next_section(state,self.request,self.source,client)
        reader.read_next_section(state,self.request,self.source,client)
        self.assertEqual(state['status'],'needs_budget')
        self.assertEqual(state['next_section'],1)
        self.assertEqual(len(state['readings']),1)
        self.assertEqual(client.calls,1)

    def test_source_change_or_failed_checkpoint_cannot_silently_resume(self):
        state=self.state(); changed=deepcopy(self.source); changed['text']+='altered'
        with self.assertRaises(ValueError): reader.read_next_section(state,self.request,changed,self.client([]))
        state['status']='in_flight'
        with self.assertRaises(ValueError): reader.read_next_section(state,self.request,self.source,self.client([]))

    def test_oversized_memory_is_rejected_without_advancing_or_clipping(self):
        state=self.state(); client=self.client([self.analysis('x'*2001)])
        with self.assertRaises(ValueError): reader.read_next_section(state,self.request,self.source,client)
        self.assertEqual(state['next_section'],0)
        self.assertEqual(state['reserved_calls'],1)

    def test_reservation_checkpoint_precedes_the_paid_boundary(self):
        state=self.state(); saved=[]; client=self.client([self.analysis()])
        def checkpoint(value): saved.append((value['status'],value['reserved_calls'],client.calls))
        reader.read_next_section(state,self.request,self.source,client,checkpoint=checkpoint)
        self.assertEqual(saved[0],('in_flight',1,0))
        self.assertEqual(saved[-1][0],'reading')

    def test_network_refusal_prevents_model_call_even_with_an_unused_budget(self):
        state=self.state(); self.request['network_allowed']=False; client=self.client([])
        with self.assertRaises(ValueError): reader.read_next_section(state,self.request,self.source,client)
        self.assertEqual(client.calls,0)
        self.assertEqual(state['reserved_calls'],0)

    def test_summary_versions_remain_auditable_after_next_section(self):
        state=self.state(); client=self.client([self.analysis('First memory.'),self.analysis('Updated memory.')])
        reader.read_next_section(state,self.request,self.source,client)
        reader.read_next_section(state,self.request,self.source,client)
        self.assertEqual([r['rolling_summary'] for r in state['readings']],['First memory.','Updated memory.'])

    def test_new_client_does_not_reset_persistent_budget(self):
        state=self.state(budget=1)
        reader.read_next_section(state,self.request,self.source,self.client([self.analysis()]))
        fresh=self.client([])
        reader.read_next_section(state,self.request,self.source,fresh)
        self.assertEqual(fresh.calls,0)
        self.assertEqual(state['next_section'],1)

    def test_a_heading_word_inside_a_sentence_is_not_a_section_boundary(self):
        source=deepcopy(self.source); source['text']='A Methods reference in prose.'
        with self.assertRaises(ValueError):
            reader.create_reading_state(self.request,source,[{'title':'Methods','start':2}],max_calls=2)

