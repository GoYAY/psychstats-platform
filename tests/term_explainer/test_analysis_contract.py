"""Missing model fields must neither discard evidence nor halt safe reading."""
from copy import deepcopy
import json
import unittest

from term_explainer import pipeline
from term_explainer.contract import validate_request
from term_explainer.section_reading import create_reading_state,read_next_section
from .helpers import request_payload
from .test_pipeline import analysis_payload,ExternalDouble


class AnalysisContractTests(unittest.TestCase):
    def request(self,**changes):
        payload=request_payload();payload.update(changes)
        return validate_request(payload)

    def test_disabled_references_missing_field_completes_without_second_call(self):
        for policy in (dict(network_allowed=False),dict(network_allowed=True,max_reference_reads=0)):
            with self.subTest(policy=policy):
                first=analysis_payload();del first['reference_candidates']
                client=ExternalDouble([first]);usage=[]
                result=pipeline._analyse(self.request(**policy),client,usage)
                self.assertEqual(result['reference_candidates'],[])
                self.assertEqual(len(client.events),1)
                self.assertEqual(len(usage),1)
                self.assertEqual(result['analysis_contract']['normalized_fields'],['reference_candidates'])
                self.assertEqual(result['analysis_contract']['repair_attempts'],0)

    def test_allowed_references_missing_field_has_one_bounded_field_only_repair(self):
        first=analysis_payload();del first['reference_candidates']
        candidate=dict(id='ref-1',parent_id='s1',title='A reference',doi='',url='',depth=1,
            priority=1,purpose='Background',module='background',reference_ref=dict(source_id='s1',span_id='s1#c0000'))
        second=dict(first,reference_candidates=[candidate])
        client=ExternalDouble([first,second]);usage=[]
        result=pipeline._analyse(self.request(network_allowed=True),client,usage)
        self.assertEqual(result['reference_candidates'],[candidate])
        self.assertEqual(len(client.events),2)
        self.assertEqual(len(usage),2)
        self.assertEqual(result['analysis_contract']['repaired_fields'],['reference_candidates'])

    def test_repair_may_not_rewrite_existing_evidence_or_remove_missing_evidence(self):
        for field in ('claims','missing_evidence'):
            with self.subTest(field=field):
                first=analysis_payload();first['missing_evidence']=['A real unresolved evidence gap.']
                del first['reference_candidates'];second=deepcopy(first);second['reference_candidates']=[]
                if field=='claims':second['claims'][0]['statement']='Unauthorized rewritten claim.'
                else:second['missing_evidence']=[]
                client=ExternalDouble([first,second])
                with self.assertRaises(pipeline.PipelineError) as caught:
                    pipeline._analyse(self.request(network_allowed=True),client,[])
                self.assertEqual(caught.exception.code,'invalid_evidence_analysis')
                self.assertEqual(caught.exception.analysis_contract['repair_status'],'rejected')
                self.assertEqual(len(client.events),2)

    def test_still_missing_after_one_repair_stops_without_third_request(self):
        first=analysis_payload();del first['reference_candidates']
        client=ExternalDouble([first,deepcopy(first)])
        with self.assertRaises(pipeline.PipelineError) as caught:
            pipeline._analyse(self.request(network_allowed=True),client,[])
        self.assertEqual(len(client.events),2)
        self.assertEqual(caught.exception.analysis_contract['repair_attempts'],1)

    def test_present_but_invalid_reference_field_is_not_defaulted_or_repaired(self):
        for value in (None,'',{},False):
            with self.subTest(value=value):
                first=analysis_payload();first['reference_candidates']=value
                client=ExternalDouble([first])
                with self.assertRaises(pipeline.PipelineError):
                    pipeline._analyse(self.request(max_reference_reads=0),client,[])
                self.assertEqual(len(client.events),1)

    def test_normalization_does_not_make_invalid_evidence_pass(self):
        first=analysis_payload();del first['reference_candidates']
        first['claims'][0]['evidence']=[dict(source_id='unknown',start=0,end=2)]
        client=ExternalDouble([first])
        with self.assertRaises(pipeline.PipelineError):
            pipeline._analyse(self.request(max_reference_reads=0),client,[])
        self.assertEqual(len(client.events),1)

    def test_top_level_and_web_identity_omissions_share_one_repair(self):
        payload=request_payload();payload.update(network_allowed=True)
        payload['sources'][0]['retrieved_url']='https://example.org/article'
        first=analysis_payload();del first['claims'];first['reading_notes'][0].pop('identity_check',None)
        second=analysis_payload();second['reading_notes'][0]['identity_check']=dict(status='matches',reason='The actual source matches.')
        client=ExternalDouble([first,second])
        result=pipeline._analyse(validate_request(payload),client,[])
        self.assertTrue(result['claims'])
        self.assertEqual(len(client.events),2)

    def test_section_checkpoint_persists_normalization_without_model_supplied_audit(self):
        payload=request_payload();payload.update(network_allowed=True,max_reference_reads=0)
        source=deepcopy(payload['sources'][0]);source['text']='Introduction\nReal located evidence.'
        state=create_reading_state(payload,source,[dict(title='Introduction',start=0)],max_calls=2)
        first=analysis_payload();first.update(rolling_summary='Brief summary.',key_conditions=[],
            analysis_contract=dict(normalized_fields=['claims'],repair_attempts=99))
        del first['reference_candidates']
        for item in first['claims']+first['reading_notes']+first['synthesis']:
            item['evidence']=[dict(source_id='s1',span_id='s1#c0000')]
        snapshots=[];client=ExternalDouble([first])
        read_next_section(state,payload,source,client,checkpoint=lambda s:snapshots.append(deepcopy(s)))
        self.assertEqual(state['next_section'],1)
        audit=snapshots[-1]['readings'][0]['analysis_contract']
        self.assertEqual(audit['normalized_fields'],['reference_candidates'])
        self.assertEqual(audit['repair_attempts'],0)
        self.assertEqual(len(client.events),1)

    def test_primary_request_is_identical_with_or_without_missing_reply_field(self):
        first=analysis_payload();missing=deepcopy(first);del missing['reference_candidates']
        a=ExternalDouble([first]);b=ExternalDouble([missing])
        request=self.request(max_reference_reads=0)
        pipeline._analyse(request,a,[]);pipeline._analyse(request,b,[])
        self.assertEqual(a.events[0],b.events[0])

    def test_normalization_audit_reaches_prepared_evidence(self):
        first=analysis_payload();del first['reference_candidates']
        result=pipeline.prepare_evidence(self.request(max_reference_reads=0),ExternalDouble([first]))
        self.assertEqual(result.evidence['analysis_contracts'][0]['normalized_fields'],['reference_candidates'])

    def test_failed_section_repair_audit_is_checkpointed_without_advancing(self):
        payload=request_payload();payload.update(network_allowed=True,max_reference_reads=0)
        source=deepcopy(payload['sources'][0]);source['text']='Introduction\nReal located evidence.'
        state=create_reading_state(payload,source,[dict(title='Introduction',start=0)],max_calls=2)
        first=analysis_payload();first.update(rolling_summary='Brief summary.',key_conditions=[])
        del first['claims']
        for item in first['reading_notes']+first['synthesis']:
            item['evidence']=[dict(source_id='s1',span_id='s1#c0000')]
        snapshots=[]
        with self.assertRaises(pipeline.PipelineError):
            read_next_section(state,payload,source,ExternalDouble([first,deepcopy(first)]),checkpoint=lambda s:snapshots.append(deepcopy(s)))
        self.assertEqual(state['next_section'],0)
        self.assertEqual(snapshots[-1]['analysis_contract_failure']['section_id'],'unit-001')
        self.assertEqual(snapshots[-1]['analysis_contract_failure']['repair_attempts'],1)

    def test_budget_stop_retains_repair_attempt_without_claiming_completed_evidence(self):
        from term_explainer.deepseek import DeepSeekError
        first=analysis_payload();del first['claims']
        client=ExternalDouble([first,DeepSeekError('call_budget_exhausted','Offline budget cap')])
        result=pipeline.prepare_evidence(self.request(network_allowed=True),client)
        self.assertEqual(result.action,'needs_budget')
        self.assertEqual(result.evidence['analysis_contract_failure']['repair_attempts'],1)
        self.assertFalse(result.evidence['can_generate'])

    def test_section_audit_survives_conflict_or_post_analysis_validation_failure(self):
        for failure in ('conflict','summary'):
            with self.subTest(failure=failure):
                payload=request_payload();payload.update(network_allowed=True,max_reference_reads=0)
                source=deepcopy(payload['sources'][0]);source['text']='Introduction\nReal located evidence.'
                state=create_reading_state(payload,source,[dict(title='Introduction',start=0)],max_calls=2)
                first=analysis_payload();first.update(rolling_summary='Brief summary.',key_conditions=[])
                del first['reference_candidates']
                for item in first['claims']+first['reading_notes']+first['synthesis']:
                    item['evidence']=[dict(source_id='s1',span_id='s1#c0000')]
                if failure=='conflict':first['anchor_conflicts']=['A real concept conflict.']
                else:first['rolling_summary']=''
                snapshots=[]
                if failure=='summary':
                    with self.assertRaises(ValueError):
                        read_next_section(state,payload,source,ExternalDouble([first]),checkpoint=lambda s:snapshots.append(deepcopy(s)))
                else:read_next_section(state,payload,source,ExternalDouble([first]),checkpoint=lambda s:snapshots.append(deepcopy(s)))
                self.assertEqual(state['next_section'],0)
                self.assertEqual(snapshots[-1]['analysis_contracts']['unit-001']['normalized_fields'],['reference_candidates'])

    def test_prepared_evidence_validation_failure_retains_completion_audit(self):
        first=analysis_payload();del first['reference_candidates']
        first['claims'][0]['module']='invalid-module'
        with self.assertRaises(pipeline.PipelineError) as caught:
            pipeline.prepare_evidence(self.request(max_reference_reads=0),ExternalDouble([first]))
        self.assertEqual(caught.exception.code,'invalid_evidence_analysis')
        self.assertEqual(caught.exception.analysis_contract['normalized_fields'],['reference_candidates'])
        self.assertEqual(len(caught.exception.analysis_contracts),1)

