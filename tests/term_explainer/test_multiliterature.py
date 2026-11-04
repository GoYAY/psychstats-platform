"""Actual integration boundaries; only external provider responses are replaced."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from term_explainer.contract import validate_request,validate_result
from term_explainer.reader import render_lesson
from term_explainer.pipeline import prepare_evidence,generate_prepared_lesson,PipelineReply
from term_explainer.full_job import RecordedClient,JobError,compile_evidence
from term_explainer.deepseek import DeepSeekClient,DeepSeekError
from .helpers import request_payload,result_payload
from .test_pipeline import ExternalDouble,analysis_payload


class MultiLiteratureTests(unittest.TestCase):
    def test_multi_source_generation_cannot_claim_success_using_only_primary(self):
        from term_explainer.pipeline import PipelineError
        data=request_payload();data['sources'].append(dict(id='s2',title='Background',text='Relevant background.',scope='excerpt',doi='10.1234/bg'))
        request=validate_request(data)
        prepared=prepare_evidence(request,ExternalDouble([analysis_payload(('s1','s2'))]))
        prepared.evidence['multi_literature']=True
        with self.assertRaises(PipelineError):
            generate_prepared_lesson(request,ExternalDouble([result_payload(),result_payload()]),prepared)

    def test_known_block_identifier_alias_is_canonicalized_without_accepting_unknown(self):
        data=result_payload();data['blocks'][0]['id']='real-question'
        self.assertEqual(validate_result(data,validate_request(request_payload())).blocks[0]['id'],'real_question')
        data['blocks'][0]['id']='unknown-block'
        with self.assertRaises(ValueError):validate_result(data,validate_request(request_payload()))

    def test_source_local_span_id_is_unambiguous_but_unknown_span_still_fails(self):
        from term_explainer.evidence import resolve_reference
        source=request_payload()['sources'][0]
        self.assertEqual(resolve_reference(dict(source_id='s1',span_id='c0000'),[source]),dict(source_id='s1',start=0,end=len(source['text'])))
        with self.assertRaises(ValueError):resolve_reference(dict(source_id='s1',span_id='c9999'),[source])

    def test_scope_review_preserves_core_gaps_and_separates_research_questions(self):
        from term_explainer.pipeline import _review_scope
        analysis=analysis_payload();analysis['missing_evidence']=['Definition unknown.','Independent replication needed.']
        client=ExternalDouble([dict(core_indices=[0],research_indices=[1],reasons=['Cannot define the target.','Research validation rather than concept teaching.'])])
        _review_scope(analysis,validate_request(request_payload()),client,[])
        self.assertEqual(analysis['missing_evidence'],['Definition unknown.'])
        self.assertEqual(analysis['research_questions'][0]['text'],'Independent replication needed.')
        self.assertFalse(analysis['research_questions'][0]['fact_verified'])

    def test_received_truncated_reply_keeps_its_real_token_usage(self):
        from tools.run_term_explainer import summary
        def transport(*args):return dict(model='test',usage=dict(prompt_tokens=10,completion_tokens=20,total_tokens=30),choices=[dict(finish_reason='length',message=dict(content='incomplete'))])
        with tempfile.TemporaryDirectory() as tmp:
            state=dict(events=[],stage='evidence',reading=dict(next_section=0,sections=[]),inherited_section_calls=0)
            proxy=RecordedClient(DeepSeekClient(api_key='offline',max_calls=1,transport=transport),state,tmp,lambda s:None)
            with self.assertRaises(DeepSeekError):proxy.generate([dict(role='user',content='test')])
            self.assertEqual(summary(state)['usage']['total_tokens'],30)

    def test_explicit_truncation_recovery_is_once_and_rejects_unknown_timeout(self):
        from term_explainer.expansion import reconcile_truncation
        state=dict(stage='evidence',input_hash='expected',events=[dict(error_code='model_truncated',api_calls=1,metrics=dict(finish_reason='length'))])
        for wrong in ('wrong',None):
            with self.assertRaises(ValueError):reconcile_truncation(deepcopy(state),wrong)
        timeout=deepcopy(state);timeout['events'][0]['error_code']='provider_timeout'
        with self.assertRaises(ValueError):reconcile_truncation(timeout,'expected')
        reconcile_truncation(state,'expected')
        self.assertEqual(state['stage_attempts']['evidence'],1)
        with self.assertRaises(ValueError):reconcile_truncation(state,'expected')

    def test_enrichment_preserves_approved_nonprose_modules(self):
        request=validate_request(request_payload())
        prepared=prepare_evidence(request,ExternalDouble([analysis_payload()]))
        prior=result_payload();changed=deepcopy(prior)
        changed['visual']=None;changed['quiz']=None
        fixed={k:prior[k] for k in ('visual','quiz','formulas','relations')}
        reply=generate_prepared_lesson(request,ExternalDouble([changed]),prepared,fixed_modules=fixed)
        self.assertEqual(reply.lesson.visual,prior['visual'])
        self.assertEqual(reply.lesson.quiz,prior['quiz'])

    def test_enrichment_forks_complete_job_and_keeps_old_usage_unchanged(self):
        from term_explainer.expansion import create_enrichment
        from term_explainer.full_job import fingerprint
        payload=dict(request=request_payload(),source=request_payload()['sources'][0])
        state=dict(stage='complete',lesson=result_payload(),events=[dict(phase='old',api_calls=1)],input_hash=fingerprint(payload),selected_source=deepcopy(payload['source']))
        old=deepcopy(state)
        new,updated=create_enrichment(state,payload,[])
        self.assertEqual(state,old)
        self.assertEqual(new['events'],[])
        self.assertEqual(new['prior_events'],old['events'])
        self.assertEqual(new['stage'],'evidence')
        self.assertEqual(updated['request']['max_body_chars'],114)
        self.assertTrue(updated['multi_literature'])

    def test_many_unread_candidates_remain_private_without_breaking_delivery(self):
        from term_explainer.full_job import deliver
        data=request_payload();data.update(network_allowed=False)
        data['sources'][0]['text']+='\n'+'\n'.join(f'Reference {i}. doi:10.1234/ref{i}' for i in range(10))
        analysis=analysis_payload()
        analysis['reference_candidates']=[dict(id=f'r{i}',parent_id='s1',title=f'Reference {i}',doi=f'10.1234/ref{i}',url=f'https://doi.org/10.1234/ref{i}',depth=1,priority=1,purpose='Context',module='application',reference_ref=dict(source_id='s1',span_id=f's1#p{i+1:04d}')) for i in range(10)]
        payload=dict(request=data,multi_literature=True,source=data['sources'][0])
        state=dict(stage='evidence',selected_source=deepcopy(data['sources'][0]),reading={'readings':[],'sections':[],'source_hash':'test'},source_mapping=[])
        client=ExternalDouble([analysis,result_payload()])
        compile_evidence(state,payload,client,lambda s:None)
        self.assertEqual(len(state['evidence']['sources']),11)
        self.assertEqual(len(state['reader_sources']),1)
        with tempfile.TemporaryDirectory() as tmp:
            deliver(state,payload,client,lambda s:None,tmp,external_qa=False)
            self.assertEqual(state['stage'],'complete')
            page=Path(state['output_page']).read_text(encoding='utf-8')
            self.assertNotIn('<li>Reference ',page)

    def test_bibliography_locator_cannot_become_technical_or_teaching_evidence(self):
        from term_explainer.evidence import resolve_reference
        from term_explainer.literature import build_evidence_matrix
        source=dict(request_payload()['sources'][0],text='Body.\nReference entry.',locator_only_ranges=[dict(start=6,end=22)])
        ref=dict(source_id='s1',start=6,end=22)
        with self.assertRaisesRegex(ValueError,'locator'):
            resolve_reference(ref,[source])
        with self.assertRaisesRegex(ValueError,'locator'):
            build_evidence_matrix([source],[dict(id='bad',module='method',statement='A fake technical detail',stance='supports',detail='technical',evidence=[ref])])

    def test_known_unavailable_source_is_replayed_without_refetching(self):
        def transport(*args):raise DeepSeekError('source_unavailable','not accessible')
        with tempfile.TemporaryDirectory() as tmp:
            state=dict(events=[]);provider=DeepSeekClient(api_key='offline-test',max_calls=5,transport=transport)
            proxy=RecordedClient(provider,state,tmp,lambda s:None)
            for attempt in range(2):
                with self.assertRaises(DeepSeekError) as error:proxy.fetch('https://example.com/paper',source_id='r1')
                self.assertEqual(error.exception.code,'source_unavailable')
            self.assertEqual(provider.calls,1)

    def test_optional_background_access_failure_does_not_erase_primary_evidence(self):
        data=request_payload();data.update(network_allowed=True,optional_reference_reads=True)
        data['sources'][0]['text']+='\nReference source. doi:10.1234/ref'
        analysis=analysis_payload()
        analysis['reference_candidates']=[dict(id='r1',parent_id='s1',title='Reference source',doi='10.1234/ref',url='https://doi.org/10.1234/ref',depth=1,priority=1,purpose='Context',module='application',reference_ref=dict(source_id='s1',span_id='s1#p0001'))]
        client=ExternalDouble([analysis],pages={'https://doi.org/10.1234/ref':DeepSeekError('source_unavailable','not accessible')})
        reply=prepare_evidence(validate_request(data),client)
        self.assertEqual(reply.action,'ready_for_explanation')
        self.assertEqual(reply.evidence['sources'][-1]['scope'],'metadata')
        self.assertTrue(reply.evidence['reference_access_notes'])
        self.assertFalse(reply.evidence['reported_gaps'])

    def test_body_budget_is_enforced_without_cutting_modules(self):
        data=request_payload();data['max_body_chars']=100
        with self.assertRaisesRegex(ValueError,'body.*100'):
            validate_result(result_payload(),validate_request(data))
        for bad in (True,0,-1,'100',12001):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                validate_request(dict(data,max_body_chars=bad))

    def test_body_budget_excludes_figures_and_quiz_but_counts_all_prose(self):
        data=request_payload();lesson=result_payload()
        limit=sum(len(p['text']) for b in lesson['blocks'] for p in b['paragraphs'])
        data['max_body_chars']=limit
        self.assertEqual(validate_result(lesson,validate_request(data)).status,'complete')
        lesson['blocks'][-1]['paragraphs'][0]['text']+='多'
        with self.assertRaisesRegex(ValueError,'body'):
            validate_result(lesson,validate_request(data))

    def test_provided_local_sources_can_be_integrated_without_network_permission(self):
        data=request_payload()
        data['sources'].append(dict(id='s2',title='Background source',text='Additional context.',scope='excerpt',doi='10.1234/context'))
        a=analysis_payload(('s1','s2'))
        reply=prepare_evidence(validate_request(data),ExternalDouble([a]))
        self.assertEqual(reply.action,'ready_for_explanation')
        self.assertEqual(len(reply.evidence['synthesis']),2)

    def test_sources_list_excludes_unread_and_unused_candidates(self):
        sources=deepcopy(request_payload()['sources'])
        sources.extend([dict(id='unused',title='UNUSED_BACKGROUND',text='Unused.',scope='excerpt'),
                        dict(id='unread',title='UNREAD_METADATA',text='',scope='metadata')])
        page=render_lesson(result_payload(),sources=sources)
        self.assertIn('经核对的教学说明',page)
        self.assertNotIn('UNUSED_BACKGROUND',page)
        self.assertNotIn('UNREAD_METADATA',page)

    def test_retrieval_responses_are_cached_and_do_not_rebill(self):
        sent=[]
        def transport(url,payload,headers,timeout):
            sent.append(url)
            return dict(title='Source',content='Introduction\nA real introductory passage.\nMethods\nMethod evidence.')
        with tempfile.TemporaryDirectory() as tmp:
            state=dict(events=[])
            provider=DeepSeekClient(api_key='offline-test',max_calls=5,transport=transport)
            first=RecordedClient(provider,state,tmp,lambda s:None)
            fetched=first.fetch('https://example.com/paper',source_id='r1',origin='reference')
            second=RecordedClient(provider,state,tmp,lambda s:None)
            second.phase='another-phase'
            self.assertEqual(second.fetch('https://example.com/paper',source_id='r1',origin='reference'),fetched)
            self.assertEqual(len(sent),1)
            self.assertEqual(state['events'][0]['api_calls'],1)

    def test_unknown_retrieval_failure_cannot_rebill_after_phase_change(self):
        def transport(*args):raise DeepSeekError('provider_timeout','timeout')
        with tempfile.TemporaryDirectory() as tmp:
            state=dict(events=[]);provider=DeepSeekClient(api_key='offline-test',max_calls=5,transport=transport)
            proxy=RecordedClient(provider,state,tmp,lambda s:None)
            with self.assertRaises(DeepSeekError):proxy.fetch('https://example.com/paper',source_id='r1')
            proxy.phase='retry-phase'
            with self.assertRaises(JobError):proxy.fetch('https://example.com/paper',source_id='r1')
            self.assertEqual(provider.calls,1)

    def test_whole_job_uses_multi_source_pipeline_and_preserves_contributions(self):
        request=request_payload();request['network_allowed']=False
        request['sources'].append(dict(id='s2',title='Background',text='Relevant source.',scope='excerpt',doi='10.1234/bg'))
        payload=dict(request=request,multi_literature=True,source=request['sources'][0])
        state=dict(stage='evidence',selected_source=deepcopy(request['sources'][0]),reading={'readings':[],'sections':[]})
        client=ExternalDouble([analysis_payload(('s1','s2'))])
        compile_evidence(state,payload,client,lambda s:None)
        self.assertEqual(state['stage'],'lesson')
        self.assertEqual({s['id'] for s in state['reader_sources']},{'s1','s2'})
        self.assertEqual(len(state['evidence']['synthesis']),2)

    def test_length_repair_is_bounded_and_preserves_full_teaching_modules(self):
        request=request_payload();request['max_body_chars']=200
        prepared=prepare_evidence(validate_request(request),ExternalDouble([analysis_payload()]))
        oversized=result_payload();oversized['blocks'][0]['paragraphs'][0]['text']='字'*201
        client=ExternalDouble([oversized,result_payload()])
        reply=generate_prepared_lesson(validate_request(request),client,prepared)
        self.assertEqual(reply.repair_count,1)
        self.assertEqual(len(reply.lesson.blocks),5)
        context=__import__('json').loads(client.events[0][1][-1]['content'])
        self.assertEqual(context['max_body_chars'],200)
