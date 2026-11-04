"""Generation boundary regressions from real output failures; no network calls."""
import importlib
import json
import unittest
from copy import deepcopy
from term_explainer.contract import validate_request
from term_explainer.pipeline import prepare_evidence,generate_prepared_lesson,PipelineError
from .helpers import request_payload,result_payload
from .test_pipeline import ExternalDouble,analysis_payload

try:
    output=importlib.import_module('term_explainer.generation_output')
except ModuleNotFoundError:
    output=None


class GenerationOutputTests(unittest.TestCase):
    def test_scalar_chart_arrays_report_specific_paths(self):
        value=result_payload();value['visual'].update(kind='statistical',origin='teaching',payload=dict(chart_type='bar',x_label='类别',y_label='人数',series=[dict(label='组',x='满意',y=68)]))
        with self.assertRaises(ValueError) as caught:self.boundary(value)
        self.assertIn('/visual/payload/series/0/x',{i['path'] for i in caught.exception.issues})
        self.assertIn('/visual/payload/series/0/y',{i['path'] for i in caught.exception.issues})

    def test_required_new_policy_is_repaired_once_and_fixed_legacy_is_exempt(self):
        prepared=prepare_evidence(self.request,ExternalDouble([analysis_payload()]))
        good=result_payload();good['visual']['presentation']=dict(version=1,focus='structure',numeric_role='none',layout='story',interaction='none')
        client=ExternalDouble([result_payload(),good])
        reply=generate_prepared_lesson(self.request,client,prepared,visual_policy_version=1)
        self.assertEqual(reply.repair_count,1);self.assertEqual(len(client.events),2)
        self.assertIn('/visual/presentation',client.events[1][1][-1]['content'])
        context=json.loads(client.events[0][1][1]['content']);self.assertEqual(context['generation_requirements']['visual_policy_version'],1)
        fixed=result_payload()['visual'];client=ExternalDouble([result_payload()])
        reply=generate_prepared_lesson(self.request,client,prepared,visual_policy_version=1,fixed_modules=dict(visual=fixed))
        self.assertEqual(reply.lesson.visual,fixed);self.assertEqual(len(client.events),1)
        client=ExternalDouble([result_payload(),result_payload()])
        with self.assertRaises(PipelineError):generate_prepared_lesson(self.request,client,prepared,visual_policy_version=1)
        self.assertEqual(len(client.events),2)

    def test_real_scalar_frequency_shape_gets_one_lossless_model_repair(self):
        prepared=prepare_evidence(self.request,ExternalDouble([analysis_payload()]));good=result_payload()
        good['visual'].update(kind='statistical',origin='teaching',presentation=dict(version=1,focus='local',numeric_role='exact',layout='single',interaction='inspect'),payload=dict(chart_type='bar',x_label='类别',y_label='人数',series=[dict(label='问卷',x=['非常不满意','不满意','满意','非常满意'],y=[12,23,68,17])]))
        bad=deepcopy(good);bad['visual']['payload']['series']=[dict(label=x,x=x,y=y) for x,y in zip(good['visual']['payload']['series'][0]['x'],[12,23,68,17])]
        client=ExternalDouble([bad,good]);reply=generate_prepared_lesson(self.request,client,prepared,visual_policy_version=1,visual_host=dict(interactive_chart_types=['bar']))
        self.assertEqual(len(client.events),2);self.assertEqual(reply.lesson.visual['payload']['series'][0]['y'],[12,23,68,17]);self.assertIn('/visual/payload/series/0/x',client.events[1][1][-1]['content'])

    def setUp(self):
        self.request=validate_request(request_payload())

    def boundary(self,value,request=None):
        self.assertIsNotNone(output,'shared generation-output boundary is missing')
        return output.validate_generated_lesson(value,request or self.request)

    def test_single_emphasis_is_losslessly_normalized_without_mutating_response(self):
        value=result_payload();p=value['blocks'][1]['paragraphs'][0]
        p['emphasis']='总体';before=deepcopy(value)
        lesson,changes=self.boundary(value)
        self.assertEqual(lesson.blocks[1]['paragraphs'][0]['emphasis'],['总体'])
        self.assertEqual(value,before)
        self.assertEqual(len(changes),1)
        self.assertEqual(changes[0]['path'],'/blocks/1/paragraphs/0/emphasis')

    def test_model_filled_unsupplied_definition_is_discarded_without_changing_user_anchor(self):
        data=request_payload();data['term']['definition']='';request=validate_request(data)
        value=result_payload();value['term']['definition']='A model-proposed definition.'
        lesson,changes=self.boundary(value,request)
        self.assertEqual(lesson.term['definition'],'')
        self.assertEqual(value['term']['definition'],'A model-proposed definition.')
        self.assertTrue(any(c['path']=='/term/definition' for c in changes))
        value['term']['zh']='An unrelated concept'
        with self.assertRaises(ValueError):self.boundary(value,request)

    def test_selected_markdown_emphasis_becomes_only_semantic_emphasis(self):
        value=result_payload();p=value['blocks'][1]['paragraphs'][0]
        p['text']='**总体**是研究目标对象。';p['emphasis']=['总体']
        lesson,changes=self.boundary(value)
        self.assertEqual(lesson.blocks[1]['paragraphs'][0]['text'],'总体是研究目标对象。')
        self.assertEqual(lesson.blocks[1]['paragraphs'][0]['emphasis'],['总体'])
        self.assertTrue(changes)

    def test_relation_alias_and_span_are_resolved_then_strictly_checked(self):
        data=request_payload();data['sources'][0]['references']=['s2']
        data['sources'].append(dict(id='s2',title='Related work',text='Related real text.',scope='excerpt',doi='10.1234/bg'))
        value=result_payload();value['source_relations']=[dict(source='s1',target='s2',type='cites',reason='Actual listed citation.',refs=[dict(source_id='s1',span_id='s1#c0000')])]
        lesson,changes=self.boundary(value,validate_request(data))
        ref=lesson.source_relations[0]['evidence'][0]
        self.assertEqual((ref['source_id'],ref['start'],ref['end']),('s1',0,len(data['sources'][0]['text'])))
        self.assertNotIn('refs',lesson.source_relations[0])
        self.assertTrue(changes)

    def test_unknown_span_or_conflicting_relation_aliases_are_not_repaired(self):
        data=request_payload();data['sources'][0]['references']=['s2']
        data['sources'].append(dict(id='s2',title='Related',text='Other text.',scope='excerpt'))
        for bad in ['unknown_span','conflicting_aliases']:
            value=result_payload();edge=dict(source='s1',target='s2',type='cites',reason='Listed.',refs=[dict(source_id='s1',span_id='s1#c9999' if bad=='unknown_span' else 's1#c0000')])
            if bad=='conflicting_aliases':edge['evidence']=[dict(source_id='s1',start=0,end=3)]
            value['source_relations']=[edge]
            with self.subTest(bad=bad),self.assertRaises(ValueError):self.boundary(value,validate_request(data))

    def test_diagnostics_report_missing_limit_source_and_invalid_emphasis_together(self):
        value=result_payload();value['limitations']=[dict(text='A stated limit.',refs=[])]
        value['blocks'][1]['paragraphs'][0]['emphasis']={'invalid':'shape'}
        try:self.boundary(value)
        except ValueError as error:
            paths={item['path'] for item in error.issues}
            self.assertIn('/limitations/0/refs',paths)
            self.assertIn('/blocks/1/paragraphs/0/emphasis',paths)
        else:self.fail('independent structural errors must block generation')

    def test_normalization_does_not_change_anchor_or_invent_source_evidence(self):
        for kind in ['anchor','factual_source','emphasis']:
            value=result_payload()
            if kind=='anchor':value['term']['zh']='A different concept'
            elif kind=='factual_source':value['blocks'][1]['paragraphs'][0]['refs']=[]
            else:value['blocks'][1]['paragraphs'][0]['emphasis']='Not in text'
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.boundary(value)

    def test_repair_request_contains_all_detected_errors_in_one_attempt(self):
        prepared=prepare_evidence(self.request,ExternalDouble([analysis_payload()]))
        bad=result_payload();bad['limitations']=[dict(text='Limit',refs=[])]
        bad['blocks'][1]['paragraphs'][0]['emphasis']={'invalid':'shape'}
        client=ExternalDouble([bad,result_payload()])
        reply=generate_prepared_lesson(self.request,client,prepared)
        self.assertEqual(reply.repair_count,1)
        repair=client.events[1][1][-1]['content']
        self.assertIn('/limitations/0/refs',repair)
        self.assertIn('/blocks/1/paragraphs/0/emphasis',repair)
        self.assertEqual(len(client.events),2)

    def multi(self):
        data=request_payload();data['sources'].append(dict(id='s2',title='Background',text='The background explains a real use condition.',scope='excerpt',doi='10.1234/bg'))
        request=validate_request(data)
        prepared=prepare_evidence(request,ExternalDouble([analysis_payload(('s1','s2'))]))
        prepared.evidence['multi_literature']=True
        return request,prepared

    def test_second_work_only_in_limits_cannot_pass_multiliterature_body_gate(self):
        request,prepared=self.multi();value=result_payload()
        value['limitations']=[dict(text='A background limit.',refs=[dict(source_id='s2',start=0,end=10)])]
        with self.assertRaises(PipelineError):
            generate_prepared_lesson(request,ExternalDouble([value,value]),prepared)

    def test_two_works_in_actual_factual_teaching_paragraphs_pass(self):
        request,prepared=self.multi();value=result_payload()
        value['blocks'][3]['paragraphs'].append(dict(text='背景材料说明此条件如何用于理解概念。',emphasis=[],kind='factual',refs=[dict(source_id='s2',start=0,end=10)]))
        reply=generate_prepared_lesson(request,ExternalDouble([value]),prepared)
        self.assertEqual(reply.lesson.provenance['teaching_body_independent_works'],2)
        self.assertEqual(reply.repair_count,0)

    def test_generation_request_names_the_actual_contributing_source_ids(self):
        request,prepared=self.multi();value=result_payload()
        value['blocks'][3]['paragraphs'].append(dict(text='说明背景的具体贡献。',emphasis=[],kind='factual',refs=[dict(source_id='s2',start=0,end=10)]))
        client=ExternalDouble([value]);generate_prepared_lesson(request,client,prepared)
        context=json.loads(client.events[0][1][1]['content'])
        requirements=context['generation_requirements']
        self.assertEqual(requirements['minimum_teaching_body_works'],2)
        self.assertEqual({s['source_id'] for s in requirements['contributing_sources']},{'s1','s2'})

    def test_irrelevant_third_work_cannot_replace_an_actual_contribution(self):
        data=request_payload()
        data['sources']+= [dict(id='s2',title='Useful background',text='A useful prerequisite.',scope='excerpt',doi='10.1234/useful'),dict(id='s3',title='Unrelated work',text='An unrelated concept.',scope='excerpt',doi='10.1234/unrelated')]
        request=validate_request(data);analysis=analysis_payload(('s1','s2','s3'))
        analysis['synthesis'][2]['role']='irrelevant'
        prepared=prepare_evidence(request,ExternalDouble([analysis]));prepared.evidence['multi_literature']=True
        value=result_payload();value['blocks'][3]['paragraphs'].append(dict(text='不相关资料仅用于此拦截测试。',emphasis=[],kind='factual',refs=[dict(source_id='s3',start=0,end=10)]))
        with self.assertRaises(PipelineError):generate_prepared_lesson(request,ExternalDouble([value,value]),prepared)

    def test_one_repair_receives_body_gate_and_shape_issues_together(self):
        request,prepared=self.multi();bad=result_payload()
        bad['blocks'][1]['paragraphs'][0]['emphasis']={'invalid':'shape'}
        good=result_payload();good['blocks'][3]['paragraphs'].append(dict(text='使用另一文献的真实贡献。',emphasis=[],kind='factual',refs=[dict(source_id='s2',start=0,end=10)]))
        client=ExternalDouble([bad,good]);reply=generate_prepared_lesson(request,client,prepared)
        self.assertEqual(reply.repair_count,1)
        repair=client.events[1][1][-1]['content']
        self.assertIn('/blocks/1/paragraphs/0/emphasis',repair)
        self.assertIn('multi-literature teaching body',repair)

    def test_mismatched_evidence_bundle_anchor_stops_before_any_model_request(self):
        prepared=prepare_evidence(self.request,ExternalDouble([analysis_payload()]))
        prepared.evidence['anchor']['term']='A different concept'
        client=ExternalDouble([result_payload()])
        with self.assertRaises(PipelineError):generate_prepared_lesson(self.request,client,prepared)
        self.assertEqual(client.events,[])
