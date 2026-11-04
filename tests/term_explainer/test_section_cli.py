"""Exercise the real section CLI with only the provider HTTP boundary replaced."""
import contextlib
import hashlib
from copy import deepcopy
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from term_explainer.deepseek import DeepSeekClient, DeepSeekError
from term_explainer.section_reading import create_reading_state
from .helpers import request_payload
from .test_pipeline import analysis_payload

try:
    cli=importlib.import_module('tools.read_term_sections')
except ModuleNotFoundError:
    cli=None


class SectionCliTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(cli,'section CLI is not implemented')
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.input=self.folder/'input.json'; self.state=self.folder/'state.json'
        self.request=request_payload(); self.request['network_allowed']=True
        self.source=deepcopy(self.request['sources'][0])
        padding='本节为背景说明，用于模拟真实论文正文篇幅。'*120
        self.source['text']=('Intro\nFirst section evidence.\n'+padding
            +'\n\nMethods\nSecond section evidence.\n'+padding)
        self.payload=dict(request=self.request,source=self.source,
            headings=[{'title':'Intro','start':0},
                      {'title':'Methods','start':self.source['text'].index('Methods')}],remaining_model_calls=2)
        self.save_input()
        self.sent=[]

    def save_input(self):
        self.input.write_text(json.dumps(self.payload,ensure_ascii=False),encoding='utf-8')

    def client(self,summary='compressed context',failure=None,conditions=()):
        def transport(url,payload,headers,timeout):
            self.sent.append(payload)
            self.assertTrue(self.state.exists())
            persisted=json.loads(self.state.read_text(encoding='utf-8'))
            self.assertEqual(persisted['status'],'in_flight')
            if failure: raise failure
            analysis=analysis_payload(); analysis['rolling_summary']=summary; analysis['key_conditions']=deepcopy(list(conditions))
            for item in analysis['reading_notes']+analysis['claims']+analysis['synthesis']:
                for ref in item['evidence']: ref['span_id']='s1#c0000'
            return dict(model='deepseek-flash',usage={'prompt_tokens':20,'completion_tokens':30,'total_tokens':50},
                choices=[dict(finish_reason='stop',message=dict(content=json.dumps(analysis,ensure_ascii=False)))])
        return DeepSeekClient(api_key='not-real',max_calls=1,transport=transport)

    def call(self,*extra,client=None,key=True):
        factory=dict(return_value=client) if client else dict(side_effect=AssertionError('provider must not be constructed'))
        stdout=io.StringIO(); stderr=io.StringIO()
        with patch.object(cli,'DeepSeekClient',**factory), patch.dict('os.environ',{'DEEPSEEK_API_KEY':'not-real' if key else ''}), contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            code=cli.main([str(self.input),'--state',str(self.state),*extra])
        return code,json.loads((stdout.getvalue() or stderr.getvalue()).strip())

    def live(self,report,client=None):
        return self.call('--live-evidence','--max-api-calls','1','--send-selected-sources',
            '--report',str(self.folder/report),client=client)

    def test_default_preview_does_not_call_provider_or_create_checkpoint(self):
        code,result=self.call()
        self.assertEqual(code,0)
        self.assertEqual(result['execution'],'offline_section_preview')
        self.assertEqual(result['next_section']['title'],'Intro')
        self.assertEqual(result['api_calls'],0)
        self.assertFalse(self.state.exists())
        self.assertNotIn('First section evidence.',json.dumps(result))

    def test_live_needs_one_call_limit_consent_and_new_report(self):
        for args,error in [
            (('--live-evidence',),'budget_required'),
            (('--live-evidence','--max-api-calls','1'),'source_consent_required'),
            (('--live-evidence','--max-api-calls','1','--send-selected-sources'),'report_required')]:
            with self.subTest(error=error):
                code,result=self.call(*args)
                self.assertEqual(code,2)
                self.assertEqual(result['error']['code'],error)
                self.assertFalse(self.state.exists())

    def test_success_persists_reservation_summary_and_actual_usage(self):
        client=self.client()
        code,result=self.live('run1.json',client)
        self.assertEqual(code,0)
        saved=json.loads(self.state.read_text(encoding='utf-8'))
        self.assertEqual(saved['next_section'],1)
        self.assertEqual(saved['reserved_calls'],1)
        self.assertEqual(saved['confirmed_api_calls'],1)
        self.assertEqual(saved['rolling_summary'],'compressed context')
        self.assertEqual(result['api_calls'],1)
        self.assertEqual(result['api_events'][0]['usage']['total_tokens'],50)
        self.assertFalse(result['can_generate'])

    def test_resume_uses_new_report_same_checkpoint_and_compact_memory(self):
        self.live('run1.json',self.client('first compressed memory'))
        code,result=self.live('run2.json',self.client('updated memory'))
        context=json.loads(self.sent[-1]['messages'][1]['content'])
        self.assertEqual(context['reading_memory']['summary'],'first compressed memory')
        self.assertNotIn('First section evidence.',json.dumps(context))
        self.assertIn('Second section evidence.',json.dumps(context))
        self.assertEqual(code,0)
        self.assertEqual(result['confirmed_api_calls_total'],2)
        self.assertEqual(result['sections_done'],2)

    def test_persistent_budget_cannot_be_reset_by_another_invocation(self):
        self.payload['remaining_model_calls']=1; self.save_input()
        self.live('run1.json',self.client())
        code,result=self.live('run2.json')
        self.assertEqual(code,0)
        self.assertEqual(result['status'],'needs_budget')
        self.assertEqual(result['api_calls'],0)
        self.assertEqual(result['sections_done'],1)

    def test_failure_retains_phase_usage_counter_and_blocks_automatic_retry(self):
        client=self.client(failure=DeepSeekError('provider_http_504','timeout'))
        code,result=self.live('failed.json',client)
        self.assertEqual(code,2)
        self.assertEqual(result['api_calls'],1)
        self.assertEqual(result['api_events'][0]['kind'],'completions')
        self.assertEqual(result['status'],'failed_requires_review')
        self.assertEqual(json.loads(self.state.read_text(encoding='utf-8'))['next_section'],0)
        code,result=self.live('do-not-retry.json')
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'checkpoint_requires_review')
        self.assertEqual(len(self.sent),1)

    def test_existing_report_is_preserved_and_prevents_new_request(self):
        report=self.folder/'old.json'; report.write_text('old record',encoding='utf-8')
        code,result=self.live('old.json')
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'report_exists')
        self.assertEqual(report.read_text(encoding='utf-8'),'old record')

    def test_busy_checkpoint_is_not_unlocked_or_overwritten(self):
        lock=Path(str(self.state)+'.lock'); lock.write_text('other attempt',encoding='utf-8')
        code,result=self.live('busy.json')
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'checkpoint_locked')
        self.assertTrue(lock.exists())
        self.assertFalse(self.state.exists())

    def test_changed_source_or_budget_cannot_mutate_existing_checkpoint(self):
        self.live('run1.json',self.client())
        before=self.state.read_bytes()
        self.payload['source']['text']+='changed'; self.save_input()
        code,result=self.live('wrong-source.json')
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'checkpoint_mismatch')
        self.assertEqual(self.state.read_bytes(),before)

    def test_in_flight_checkpoint_requires_reconciliation_not_reexecution(self):
        state=create_reading_state(self.request,self.source,self.payload['headings'],max_calls=2)
        state.update(status='in_flight',reserved_calls=1)
        self.state.write_text(json.dumps(state),encoding='utf-8')
        code,result=self.live('interrupted.json')
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'checkpoint_requires_review')
        self.assertEqual(result['api_calls'],0)

    def test_path_collision_cannot_overwrite_the_input(self):
        original=self.input.read_bytes()
        code,result=self.call('--report',str(self.input))
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'path_collision')
        self.assertEqual(self.input.read_bytes(),original)

    def test_checkpoint_storage_failure_prevents_paid_boundary(self):
        client=self.client()
        with patch.object(cli,'atomic_write',side_effect=OSError('disk unavailable')):
            code,result=self.live('storage-failed.json',client)
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'storage_error')
        self.assertEqual(client.calls,0)

    def test_missing_key_does_not_reserve_or_consume_a_call(self):
        code,result=self.call('--live-evidence','--max-api-calls','1','--send-selected-sources',
            '--report',str(self.folder/'missing-key.json'),key=False)
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'missing_credentials')
        self.assertFalse(self.state.exists())

    def test_declared_backmatter_is_not_automatically_sent_to_model(self):
        self.payload['non_method_backmatter']=['Intro']; self.save_input()
        code,result=self.live('catalogue.json')
        self.assertEqual(code,0)
        self.assertEqual(result['status'],'needs_local_catalogue')
        self.assertEqual(result['api_calls'],0)

    def test_corrupt_checkpoint_has_a_structured_error_not_a_progress_crash(self):
        state=create_reading_state(self.request,self.source,self.payload['headings'],max_calls=2)
        state['next_section']='invalid'
        self.state.write_text(json.dumps(state),encoding='utf-8')
        code,result=self.live('corrupt.json')
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'checkpoint_mismatch')
        self.assertEqual(result['api_calls'],0)

    def test_invalid_checkpoint_status_is_not_echoed_as_private_prose(self):
        state=create_reading_state(self.request,self.source,self.payload['headings'],max_calls=2)
        state['status']='First section evidence.'
        self.state.write_text(json.dumps(state),encoding='utf-8')
        code,result=self.live('invalid-status.json')
        self.assertEqual(code,2)
        self.assertNotIn('First section evidence.',json.dumps(result))

    def test_report_cannot_collide_with_the_checkpoint_lock(self):
        code,result=self.live('state.json.lock')
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'path_collision')
        self.assertFalse(Path(str(self.state)+'.lock').exists())

    def test_save_failure_after_response_keeps_in_flight_disk_state_and_actual_count(self):
        original=cli.atomic_write
        writes=[]
        def fail_on_second(path,value):
            writes.append(1)
            if len(writes)==2: raise OSError('disk unavailable after provider response')
            return original(path,value)
        client=self.client()
        with patch.object(cli,'atomic_write',side_effect=fail_on_second):
            code,result=self.live('after-response.json',client)
        self.assertEqual(code,2)
        self.assertEqual(result['api_calls'],1)
        persisted=json.loads(self.state.read_text(encoding='utf-8'))
        self.assertEqual(persisted['status'],'in_flight')
        code,result=self.live('cannot-replay.json')
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'checkpoint_requires_review')
        self.assertEqual(len(self.sent),1)

    def test_editing_stored_budget_cannot_increase_input_authorization(self):
        state=create_reading_state(self.request,self.source,self.payload['headings'],max_calls=2)
        state['max_calls']=99
        self.state.write_text(json.dumps(state),encoding='utf-8')
        code,result=self.live('changed-budget.json')
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'checkpoint_mismatch')

    def test_done_label_with_unread_sections_does_not_allow_a_model_call(self):
        state=create_reading_state(self.request,self.source,self.payload['headings'],max_calls=2)
        state['status']='read_all_requires_review'
        self.state.write_text(json.dumps(state),encoding='utf-8')
        code,result=self.live('false-done.json')
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'checkpoint_mismatch')

    def test_explicit_identity_review_is_persisted_and_changes_cannot_replace_it(self):
        self.source['title']='First section evidence.'
        self.payload['identity_review']=dict(status='matches',source_id='s1',
            source_hash=hashlib.sha256(self.source['text'].encode()).hexdigest(),
            bibliography=dict(title='First section evidence.',authors=[],year=None,doi=''),
            reviewer='local_source_review',evidence=[dict(source_id='s1',start=6,end=29)])
        self.save_input()
        code,result=self.live('with-identity.json',self.client())
        self.assertEqual(code,0)
        original=self.state.read_bytes()
        self.payload['identity_review']['reviewer']='different_review'; self.save_input()
        code,result=self.live('changed-review.json')
        self.assertEqual(code,2)
        self.assertEqual(result['error']['code'],'checkpoint_mismatch')
        self.assertEqual(self.state.read_bytes(),original)

    def test_condition_registry_survives_cli_process_boundary(self):
        condition=dict(id='a',statement='The original condition.',evidence=[dict(source_id='s1',span_id='s1#c0000')])
        self.live('first-condition.json',self.client(conditions=[condition]))
        code,result=self.live('resumed-condition.json',self.client())
        context=json.loads(self.sent[-1]['messages'][1]['content'])
        self.assertEqual(context['reading_memory']['key_conditions'][0]['statement'],'The original condition.')
        self.assertEqual(code,0)
        self.assertEqual(result['confirmed_api_calls_total'],2)

    def test_corrupt_saved_condition_is_rejected_without_echo_or_provider(self):
        condition=dict(id='a',statement='Private condition text.',evidence=[dict(source_id='s1',span_id='s1#c0000')])
        self.live('first-condition.json',self.client(conditions=[condition]))
        state=json.loads(self.state.read_text(encoding='utf-8'))
        state['readings'][0]['key_conditions'][0]['evidence'][0]['end']=99999
        self.state.write_text(json.dumps(state),encoding='utf-8')
        code,result=self.live('corrupt-condition.json')
        self.assertEqual(code,2)
        self.assertEqual(result['api_calls'],0)
        self.assertNotIn('Private condition text.',json.dumps(result))

