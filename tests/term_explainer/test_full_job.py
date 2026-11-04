"""One command, many real stages; only external model HTTP is substituted."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from term_explainer.deepseek import DeepSeekClient
from term_explainer.section_reading import create_reading_state
from .helpers import request_payload,result_payload
from .test_pipeline import analysis_payload

try:
    jobs=importlib.import_module('term_explainer.full_job')
except ModuleNotFoundError:
    jobs=None


class FullJobTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.request=request_payload(); self.request['network_allowed']=True
        self.source=deepcopy(self.request['sources'][0])
        self.source['scope']='full_text'
        self.source['text']='Intro\nFirst evidence.\n\nReferences\nA. Author (2025). Example.\n\nAppendix\nLast evidence.'
        self.headings=[dict(title=t,start=self.source['text'].index(t)) for t in ['Intro','References','Appendix']]
        self.payload=dict(request=self.request,source=self.source,headings=self.headings,
                          remaining_model_calls=0,non_method_backmatter=['References'])

    def client(self,replies):
        self.sent=[]
        def transport(url,payload,headers,timeout):
            self.sent.append(payload)
            return dict(model='deepseek-flash',usage=dict(prompt_tokens=20,completion_tokens=30,total_tokens=50),
                choices=[dict(finish_reason='stop',message=dict(content=json.dumps(replies.pop(0),ensure_ascii=False)))])
        return DeepSeekClient(api_key='offline-not-real',max_calls=50,transport=transport)

    def reading(self):
        data=analysis_payload(); data.update(rolling_summary='Cumulative note.',key_conditions=[])
        for obj in data['claims']+data['reading_notes']+data['synthesis']:
            obj['evidence']=[dict(source_id='s1',span_id='s1#c0000')]
        return data

    def test_estimate_counts_catalogue_without_charging_model_calls(self):
        self.assertIsNotNone(jobs,'full document orchestration is missing')
        plan=jobs.estimate_job(self.payload,None)
        self.assertEqual(plan['sections_total'],3)
        self.assertEqual(plan['remaining_model_sections'],2)
        self.assertEqual(plan['remaining_local_sections'],1)

    def test_explicit_no_financial_cap_still_counts_each_request(self):
        client=DeepSeekClient(api_key='not-real',max_calls=None,transport=lambda *args:dict(
            model='deepseek-flash',usage={},choices=[dict(finish_reason='stop',message=dict(content='{}'))]))
        client.generate([dict(role='user',content='a')])
        client.generate([dict(role='user',content='b')])
        self.assertEqual(client.calls,2)

    def test_full_task_can_use_larger_response_window_without_changing_default(self):
        sent=[]
        def transport(url,payload,headers,timeout):
            sent.append((payload['max_tokens'],timeout))
            return dict(model='deepseek-flash',usage={},choices=[dict(finish_reason='stop',message=dict(content='{}'))])
        client=DeepSeekClient(api_key='not-real',max_calls=None,max_tokens=16384,timeout=180,transport=transport)
        client.generate([dict(role='user',content='x')])
        self.assertEqual(sent,[(16384,180)])

    def test_all_structural_units_are_processed_and_resume_does_not_reread(self):
        self.assertIsNotNone(jobs,'full document orchestration is missing')
        client=self.client([self.reading(),self.reading()])
        state=jobs.create_job(self.payload,None)
        jobs.read_all(state,self.payload,client,lambda value:None)
        self.assertEqual(state['reading']['next_section'],3)
        self.assertEqual(state['reading']['readings'][1]['mode'],'local_catalogue')
        self.assertEqual(client.calls,2)
        self.assertEqual(state['stage'],'selection')
        jobs.read_all(state,self.payload,client,lambda value:None)
        self.assertEqual(client.calls,2)

    def test_seed_readings_and_paid_counts_survive_new_job(self):
        self.assertIsNotNone(jobs,'full document orchestration is missing')
        seed=create_reading_state(self.request,self.source,self.headings,max_calls=1)
        from term_explainer.section_reading import read_next_section
        read_next_section(seed,self.request,self.source,self.client([self.reading()]))
        state=jobs.create_job(self.payload,seed)
        self.assertEqual(state['reading']['readings'],seed['readings'])
        self.assertEqual(state['reading']['reserved_calls'],1)
        self.assertEqual(state['reading']['next_section'],1)

    def test_successful_provider_reply_is_replayed_after_restart_without_new_charge(self):
        self.assertIsNotNone(jobs,'durable model response cache is missing')
        raw=self.client([{'ok':True}]); state=jobs.create_job(self.payload,None)
        client=jobs.RecordedClient(raw,state,self.folder,lambda value:None)
        client.phase='a'
        first=client.generate([dict(role='user',content='test')])
        fresh=jobs.RecordedClient(self.client([]),state,self.folder,lambda value:None); fresh.phase='a'
        second=fresh.generate([dict(role='user',content='test')])
        self.assertEqual(first.content,second.content)
        self.assertEqual(fresh.provider.calls,0)
        self.assertEqual(len(state['events']),1)

    def test_inflight_unknown_request_is_not_silently_rebilled(self):
        self.assertIsNotNone(jobs,'durable model request reservations are missing')
        state=jobs.create_job(self.payload,None)
        provider=self.client([])
        client=jobs.RecordedClient(provider,state,self.folder,lambda value:None); client.phase='a'
        state['events']=[dict(phase='a',status='in_flight',request_hash=client.request_hash([dict(role='user',content='x')]))]
        with self.assertRaises(Exception): client.generate([dict(role='user',content='x')])
        self.assertEqual(provider.calls,0)

    def test_one_run_reaches_reviewed_evidence_lesson_and_html_without_repeated_reading(self):
        self.assertIsNotNone(jobs,'complete workflow is missing')
        evidence=dict(target_kind='concept',critical_gaps=[],questions=[],review_notes=[],
            claims=[dict(id='d',module='definition',statement='A definition.',stance='supports',detail='overview',
                evidence=[dict(source_id='s1-selected',span_id='s1-selected#c0000')]),
                dict(id='a',module='application',statement='An application.',stance='supports',detail='overview',
                evidence=[dict(source_id='s1-selected',span_id='s1-selected#c0000')])])
        lesson=result_payload()
        for block in lesson['blocks']:
            for paragraph in block['paragraphs']:
                paragraph['refs']=[dict(source_id='s1-selected',start=0,end=10)]
        lesson['relations'][0]['refs']=[dict(source_id='s1-selected',start=0,end=10)]
        replies=[self.reading(),self.reading(),dict(section_ids=['unit-001','unit-003'],reason='Definitions and use.'),evidence,lesson]
        provider=self.client(replies); state=jobs.create_job(self.payload,None)
        from tools.read_term_sections import atomic_write
        save=lambda value:atomic_write(self.folder/'job.json',value)
        client=jobs.RecordedClient(provider,state,self.folder/'responses',save)
        jobs.run_job(state,self.payload,client,save,self.folder,external_qa=False)
        self.assertEqual(state['stage'],'complete')
        self.assertTrue(Path(state['output_page']).is_file())
        self.assertEqual(provider.calls,5)
        self.assertTrue(state['requires_human_review'])
        self.assertEqual(state['reading']['readings'][1]['mode'],'local_catalogue')
        jobs.run_job(state,self.payload,client,save,self.folder,external_qa=False)
        self.assertEqual(provider.calls,5)

    def test_source_gap_stops_before_lesson_generation_instead_of_fake_completion(self):
        self.assertIsNotNone(jobs,'complete workflow is missing')
        state=jobs.create_job(self.payload,None)
        provider=self.client([self.reading(),self.reading(),
            dict(section_ids=['unit-001'],reason='Definition.'),
            dict(target_kind='concept',critical_gaps=['The concept is not identified.'],questions=[],review_notes=[],claims=[])])
        with self.assertRaises(jobs.JobError): jobs.run_job(state,self.payload,provider,lambda value:None,self.folder,external_qa=False)
        self.assertEqual(state['stage'],'needs_sources')
        self.assertEqual(provider.calls,4)
        self.assertFalse((self.folder/'preview/index.html').exists())

    def test_oversized_structural_unit_stops_without_index_error_or_model_call(self):
        self.source['text']='Intro\n'+'x'*60001
        self.payload['headings']=[dict(title='Intro',start=0)]
        state=jobs.create_job(self.payload,None); provider=self.client([])
        with self.assertRaises(jobs.JobError): jobs.read_all(state,self.payload,provider,lambda value:None)
        self.assertEqual(provider.calls,0)

    def test_invalid_selection_has_one_automatic_repair_without_rereading_paper(self):
        state=jobs.create_job(self.payload,None)
        provider=self.client([self.reading(),self.reading(),dict(section_ids=['invented']),
            dict(section_ids=['unit-001'],reason='Corrected selection.'),
            dict(target_kind='concept',critical_gaps=['Missing definition.'],questions=[],review_notes=[],claims=[])])
        with self.assertRaises(jobs.JobError): jobs.run_job(state,self.payload,provider,lambda value:None,self.folder,external_qa=False)
        self.assertEqual(state['stage'],'needs_sources')
        self.assertEqual(state['reading']['next_section'],3)
        self.assertEqual(provider.calls,5)

    def test_missing_credentials_are_not_counted_as_sent_requests(self):
        state=jobs.create_job(self.payload,None)
        provider=DeepSeekClient(api_key='',max_calls=None)
        client=jobs.RecordedClient(provider,state,self.folder/'responses',lambda value:None); client.phase='a'
        with self.assertRaises(Exception): client.generate([dict(role='user',content='x')])
        self.assertEqual(provider.calls,0)
        self.assertEqual(state['events'][0].get('api_calls'),0)

    def test_network_failure_is_not_retried_by_section_or_later_stages(self):
        from term_explainer.deepseek import DeepSeekError
        for stage in ('reading','selection','evidence'):
            with self.subTest(stage=stage):
                state=jobs.create_job(self.payload,None)
                if stage!='reading':
                    jobs.read_all(state,self.payload,self.client([self.reading(),self.reading()]),lambda v:None)
                if stage=='evidence':
                    jobs.select_evidence(state,self.payload,self.client([dict(section_ids=['unit-001'],reason='Selected.')]),lambda v:None)
                def transport(*args): raise DeepSeekError('provider_timeout','timeout')
                raw=DeepSeekClient(api_key='offline-test',max_calls=None,transport=transport)
                proxy=jobs.RecordedClient(raw,state,self.folder/stage,lambda v:None)
                with self.assertRaises(DeepSeekError):
                    jobs.run_job(state,self.payload,proxy,lambda v:None,self.folder,external_qa=False)
                self.assertEqual(raw.calls,1)
                self.assertEqual(state['stage'],stage)
                with self.assertRaises(jobs.JobError):
                    jobs.run_job(state,self.payload,proxy,lambda v:None,self.folder,external_qa=False)
                self.assertEqual(raw.calls,1)

    def test_invalid_seed_index_or_counter_cannot_skip_whole_reading(self):
        for key,value in [('next_section',-1),('next_section',True),('reserved_calls',-1)]:
            seed=create_reading_state(self.request,self.source,self.headings,max_calls=1)
            seed[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                jobs.create_job(self.payload,seed)

    def test_whole_document_identity_offsets_do_not_leak_into_selected_source_context(self):
        import hashlib
        self.source['title']='Intro'
        self.payload['identity_review']=dict(status='matches',source_id=self.source['id'],
            source_hash=hashlib.sha256(self.source['text'].encode()).hexdigest(),
            bibliography={k:self.source.get(k,[] if k=='authors' else None if k=='year' else '')
                          for k in ('title','authors','year','doi')},reviewer='local review',
            evidence=[dict(source_id=self.source['id'],start=0,end=5)])
        state=jobs.create_job(self.payload,None)
        client=self.client([self.reading(),self.reading(),dict(section_ids=['unit-001'],reason='Selected.'),
            dict(target_kind='concept',critical_gaps=['Not enough evidence.'],questions=[],review_notes=[],claims=[])])
        with self.assertRaises(jobs.JobError):
            jobs.run_job(state,self.payload,client,lambda v:None,self.folder,external_qa=False)
        context=json.loads(self.sent[-1]['messages'][-1]['content'])
        identity=context['coverage']['original_document_identity']
        self.assertNotIn('evidence',identity)
        self.assertEqual(identity['role'],'document_identity_only_not_method_evidence')

