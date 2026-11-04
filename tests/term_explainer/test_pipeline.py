import importlib
import json
import unittest
from copy import deepcopy
from .helpers import request_payload, result_payload
from term_explainer.contract import validate_request
from term_explainer.deepseek import ModelReply, DeepSeekError

try:
    pipeline = importlib.import_module('term_explainer.pipeline')
except ModuleNotFoundError:
    pipeline = None


def analysis_payload(source_ids=('s1',)):
    return {'anchor_conflicts': [], 'target_kind': 'concept', 'missing_evidence': [],
            'reading_notes': [{'source_id': sid, 'summary': '逐篇核对定义与使用含义。',
                'identity_check': {'status':'matches','reason':'测试夹具按同一资料构造；不代表真实模型身份核验。'},
                'evidence': [{'source_id': sid, 'span_id': f'{sid}#p0000'}]} for sid in source_ids],
            'synthesis': [{'source_id':sid,'role':'background','contribution':'该合成片段提供锚点的背景说明。',
                'related_source_ids':[],'relationship_reason':'这些测试材料各自提供背景，没有材料可据以认定发展或验证关系。',
                'evidence':[{'source_id':sid,'span_id':f'{sid}#p0000'}]} for sid in source_ids],
            'claims': [{'id': module, 'module': module, 'statement': text, 'stance': 'supports',
                'detail': 'overview', 'evidence': [{'source_id': 's1', 'span_id': 's1#p0000'}]}
                for module, text in [('definition', '区分目标对象与实际观测对象。'),
                                      ('application', '用于说明研究对象和招募范围。')]],
            'source_relations': [], 'reference_candidates': []}


class ExternalDouble:
    """Only the external model/retrieval boundary is substituted."""
    def __init__(self, replies=(), candidates=(), pages=None):
        self.replies = list(replies); self.candidates = list(candidates)
        self.pages = pages or {}; self.events = []

    def generate(self, messages, *args, **kwargs):
        self.events.append(('model', deepcopy(messages)))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return ModelReply(json.dumps(reply, ensure_ascii=False), 'test-model-not-live', {}, 'stop')

    def search(self, query):
        self.events.append(('search', query)); return deepcopy(self.candidates)

    def fetch(self, url, *, source_id, origin='search'):
        self.events.append(('fetch', url))
        if isinstance(self.pages[url], Exception):
            raise self.pages[url]
        return dict(id=source_id, title='测试抓取片段', doi='', url=url, scope='excerpt',
                    text=self.pages[url], origin=origin, references=[])


class PipelineTests(unittest.TestCase):
    def test_received_teaching_excerpt_keeps_text_when_scope_metadata_is_reclassified(self):
        from tests.fixtures.teaching_chapter import CHAPTER
        source=dict(id='s1',title='Teaching chapter',url='https://example.org/chapter',retrieved_url='https://example.org/chapter',scope='excerpt',text=CHAPTER,scope_basis='unclassified_fetched_text',technical_evidence_eligible=False)
        merged=pipeline._merge_fetched(source,source)
        self.assertTrue(merged['technical_evidence_eligible']);self.assertEqual(merged['text'],CHAPTER)
        self.assertEqual(merged['title'],'Teaching chapter');self.assertEqual(merged['scope'],'excerpt')

    def test_missing_web_identity_has_one_bounded_repair_without_changing_evidence(self):
        for rewrite in (False,True):
            with self.subTest(rewrite=rewrite):
                r=request_payload();r['sources'][0].update(retrieved_url='https://example.org/chapter',retrieved_title='Primary Chapter')
                first=analysis_payload();first['reading_notes'][0].pop('identity_check');second=deepcopy(first);second['reading_notes'][0]['identity_check']=dict(status='matches',reason='The actual title and text match.')
                if rewrite:second['claims'][0]['statement']='A different claim not authorized by the structure repair.'
                client=ExternalDouble([first,second])
                if rewrite:
                    with self.assertRaises(pipeline.PipelineError):pipeline._analyse(validate_request(r),client,[])
                else:
                    result=pipeline._analyse(validate_request(r),client,[])
                    self.assertEqual(result['reading_notes'][0]['identity_check']['status'],'matches')
                    self.assertEqual(result['claims'][0]['statement'],first['claims'][0]['statement'])
                self.assertEqual(len(client.events),2)

    def test_missing_fetch_title_uses_actual_heading_without_inventing_bibliography(self):
        source=dict(id='s1',title='',url='https://example.org/chapter',scope='metadata',text='')
        fetched=dict(id='s1',title='已取得的来源片段',url=source['url'],scope='excerpt',text='Histograms\n\nLearning Objectives\nCreate a grouped frequency distribution.',technical_evidence_eligible=False)
        merged=pipeline._merge_fetched(source,fetched)
        self.assertEqual(merged['title'],'Histograms');self.assertEqual(merged['retrieved_title'],'Histograms')
        self.assertFalse(merged['technical_evidence_eligible']);self.assertEqual(merged['text'],fetched['text'])
        original=dict(source,title='User Supplied Paper')
        self.assertEqual(pipeline._merge_fetched(original,fetched)['title'],'User Supplied Paper')

    def test_trusted_bar_host_capability_reaches_generation_but_request_field_does_not(self):
        client=ExternalDouble([analysis_payload(),result_payload()])
        prepared=pipeline.prepare_evidence(self.request,client)
        reply=pipeline.generate_prepared_lesson(self.request,client,prepared,visual_host={'interactive_chart_types':['bar']})
        self.assertEqual(reply.action,'complete')
        host=json.loads(client.events[-1][1][1]['content'])['visual_host']
        self.assertEqual(host,dict(static_visuals=True,interactive_visuals=True,interactive_chart_types=['bar'],model_code_allowed=False))
        payload=request_payload();payload['visual_host']={'interactive_chart_types':['bar'],'model_code_allowed':True}
        client=ExternalDouble([analysis_payload(),result_payload()]);pipeline.generate_lesson(validate_request(payload),client)
        self.assertFalse(json.loads(client.events[-1][1][1]['content'])['visual_host']['interactive_visuals'])

    def test_scope_shape_gets_one_bounded_repair_without_dropping_a_core_gap(self):
        analysis=analysis_payload();analysis['missing_evidence']=['真实定义缺失。']
        bad=dict(core_indices=[],research_indices=[0,1],reasons=['Research','Extra invented item'])
        good=dict(core_indices=[0],research_indices=[],reasons=['原文没有给出定义。'])
        client=ExternalDouble([bad,good])
        pipeline._review_scope(analysis,self.request,client,[])
        self.assertEqual(len(client.events),2)
        self.assertEqual(analysis['missing_evidence'],['真实定义缺失。'])

    def test_gap_scope_reviewer_receives_actual_concept_learning_question(self):
        from dataclasses import replace
        analysis=analysis_payload();analysis['missing_evidence']=['No universal diagnostic threshold.']
        request=replace(self.request,question='理解作者所称概念，不申请诊断量尺。')
        client=ExternalDouble([dict(core_indices=[],research_indices=[0],reasons=['Outside the stated learning purpose.'])])
        pipeline._review_scope(analysis,request,client,[])
        context=json.loads(client.events[0][1][1]['content'])
        self.assertEqual(context['question'],'理解作者所称概念，不申请诊断量尺。')
        self.assertEqual(context['target_kind'],'concept')
        self.assertEqual(context['observed_anchor_conflicts'],[])

    def test_analysis_exposes_actual_reference_policy_and_concept_teaching_scope(self):
        from dataclasses import replace
        client=ExternalDouble([analysis_payload()])
        request=replace(self.request,max_reference_reads=0,network_allowed=False)
        pipeline.prepare_evidence(request,client)
        messages=client.events[0][1]
        context=json.loads(messages[1]['content'])
        self.assertEqual(context['reading_policy']['max_reference_reads'],0)
        self.assertFalse(context['reading_policy']['network_allowed'])
        self.assertEqual(context['reading_policy']['already_read_source_ids'],['s1'])
        self.assertIn('没有统一量表',messages[0]['content'])
        self.assertIn('application',messages[0]['content'])

    def test_generation_uses_packaged_skill_and_contract_in_actual_model_request(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'references').mkdir()
            (root/'SKILL.md').write_text('---\nname: test-policy\ndescription: Test only\n---\nPOLICY_SENTINEL_CLICK_ONLY',encoding='utf-8')
            (root/'references/lesson-contract.md').write_text('CONTRACT_SENTINEL_JSON',encoding='utf-8')
            (root/'references/instant-visuals.md').write_text('VISUAL_POLICY_SENTINEL_STATIC_FALLBACK',encoding='utf-8')
            client=ExternalDouble([analysis_payload(),result_payload()])
            with patch.object(pipeline,'LESSON_SKILL_ROOT',root,create=True):
                reply=pipeline.generate_lesson(self.request,client)
        self.assertEqual(reply.action,'complete')
        system=client.events[1][1][0]['content']
        self.assertIn('POLICY_SENTINEL_CLICK_ONLY',system)
        self.assertIn('CONTRACT_SENTINEL_JSON',system)
        self.assertIn('VISUAL_POLICY_SENTINEL_STATIC_FALLBACK',system)
        self.assertEqual(json.loads(client.events[1][1][1]['content'])['visual_host'],
            dict(static_visuals=True,interactive_visuals=False,model_code_allowed=False))

    def test_missing_visual_policy_stops_before_paid_teaching_request(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        client=ExternalDouble([analysis_payload(),result_payload()])
        prepared=pipeline.prepare_evidence(self.request,client)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'references').mkdir()
            (root/'SKILL.md').write_text('Policy',encoding='utf-8')
            (root/'references/lesson-contract.md').write_text('Contract',encoding='utf-8')
            with patch.object(pipeline,'LESSON_SKILL_ROOT',root):
                with self.assertRaises(pipeline.PipelineError) as error:
                    pipeline.generate_prepared_lesson(self.request,client,prepared)
        self.assertEqual(error.exception.code,'teaching_policy_unavailable')
        self.assertEqual(len(client.events),1)

    def test_missing_skill_stops_before_teaching_request_without_silent_old_policy(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        client=ExternalDouble([analysis_payload(),result_payload()])
        prepared=pipeline.prepare_evidence(self.request,client)
        with tempfile.TemporaryDirectory() as directory,patch.object(pipeline,'LESSON_SKILL_ROOT',Path(directory),create=True):
            with self.assertRaises(pipeline.PipelineError) as error:
                pipeline.generate_prepared_lesson(self.request,client,prepared)
        self.assertEqual(error.exception.code,'teaching_policy_unavailable')
        self.assertEqual(len(client.events),1)

    def test_reported_evidence_gap_disables_inner_generation_flag_as_well(self):
        analysis=analysis_payload(); analysis['missing_evidence']=['必要方法说明尚未取得。']
        reply=pipeline.prepare_evidence(self.request,ExternalDouble([analysis]))
        self.assertEqual(reply.action,'needs_sources')
        self.assertFalse(reply.evidence['can_generate'])
        self.assertEqual(reply.evidence['status'],'needs_sources')

    def test_doi_prefix_is_not_treated_as_the_cited_complete_doi(self):
        data=request_payload(); data['network_allowed']=True
        data['sources'][0]['text']+='\n参考文献：Real Method. doi:10.1234/reference'
        analysis=analysis_payload(); analysis['reference_candidates']=[dict(id='ref',parent_id='s1',title='Real Method',doi='10.1234/ref',
            url='https://doi.org/10.1234/ref',depth=1,priority=1,purpose='核对定义',module='definition',reference_ref={'source_id':'s1','span_id':'s1#p0001'})]
        with self.assertRaises(pipeline.PipelineError) as error:
            pipeline.prepare_evidence(validate_request(data),ExternalDouble([analysis,analysis]))
        self.assertEqual(error.exception.code,'invalid_reference_candidate')

    def test_retrieved_source_identity_conflict_requires_confirmation(self):
        data=request_payload(); data['network_allowed']=True
        data['sources'][0].update(text='',scope='metadata',url='https://example.com/paper')
        analysis=analysis_payload(); analysis['reading_notes'][0]['identity_check']={'status':'mismatch','reason':'实际页面讨论的是另一份资料。'}
        client=ExternalDouble([analysis],pages={'https://example.com/paper':self.request.sources[0]['text']})
        reply=pipeline.prepare_evidence(validate_request(data),client)
        self.assertEqual(reply.action,'needs_disambiguation')
        self.assertIsNone(reply.lesson)
        self.assertTrue(any('实际页面' in q for q in reply.questions))

    def test_model_invented_doi_is_not_authorized_by_a_real_cited_title(self):
        data=request_payload(); data['network_allowed']=True; data['sources'][0]['text']+='\n参考文献：Real Method.'
        analysis=analysis_payload(); analysis['reference_candidates']=[dict(id='ref',parent_id='s1',title='Real Method',doi='10.1234/invented',
            url='https://example.com/unrelated',depth=1,priority=1,purpose='核对定义',module='definition',reference_ref={'source_id':'s1','span_id':'s1#p0001'})]
        client=ExternalDouble([analysis,analysis])
        with self.assertRaises(pipeline.PipelineError) as error: pipeline.prepare_evidence(validate_request(data),client)
        self.assertEqual(error.exception.code,'invalid_reference_candidate')
        self.assertFalse(any(e[0]=='fetch' for e in client.events))

    def test_verified_doi_does_not_authorize_an_unrelated_fetch_url(self):
        data=request_payload(); data['network_allowed']=True; data['sources'][0]['text']+='\n参考文献：Real Method. doi:10.1234/real'
        analysis=analysis_payload(); analysis['reference_candidates']=[dict(id='ref',parent_id='s1',title='Real Method',doi='10.1234/real',
            url='https://example.com/unrelated',depth=1,priority=1,purpose='核对定义',module='definition',reference_ref={'source_id':'s1','span_id':'s1#p0001'})]
        client=ExternalDouble([analysis,analysis])
        with self.assertRaises(pipeline.PipelineError): pipeline.prepare_evidence(validate_request(data),client)
        self.assertFalse(any(e[0]=='fetch' for e in client.events))

    def test_doi_url_and_prefix_are_normalized_for_fetch_not_overwritten_in_input(self):
        for original in ['https://doi.org/10.1234/real','doi:10.1234/real']:
            data=request_payload(); data['network_allowed']=True
            data['sources'][0].update(text='',scope='metadata',doi=original,url='')
            client=ExternalDouble([analysis_payload()],pages={'https://doi.org/10.1234/real':self.request.sources[0]['text']})
            with self.subTest(original=original):
                reply=pipeline.prepare_evidence(validate_request(data),client)
                self.assertEqual(reply.action,'ready_for_explanation')
                self.assertEqual(client.events[0],('fetch','https://doi.org/10.1234/real'))
                self.assertEqual(reply.evidence['sources'][0]['doi'],original)

    def test_reading_context_shows_retrieved_identity_instead_of_hiding_it(self):
        data=request_payload(); data['network_allowed']=True
        data['sources'][0].update(text='',scope='metadata',url='https://example.com/paper')
        client=ExternalDouble([analysis_payload()],pages={'https://example.com/paper':self.request.sources[0]['text']})
        pipeline.prepare_evidence(validate_request(data),client)
        source=json.loads(client.events[1][1][1]['content'])['sources'][0]
        self.assertEqual(source['retrieved_title'],'测试抓取片段')
        self.assertEqual(source['retrieved_url'],'https://example.com/paper')

    def test_repeated_reference_has_two_citation_edges_but_one_fetch(self):
        data=request_payload(); data['network_allowed']=True
        data['sources'][0]['text']+='\n参考文献：Reference. doi:10.1234/ref'
        data['sources'].append(dict(id='s2',title='第二篇教学材料',scope='excerpt',text='相关说明。\n参考文献：Reference. doi:10.1234/ref'))
        analysis=analysis_payload(('s1','s2'))
        analysis['reference_candidates']=[dict(id='ref',parent_id=parent,title='Reference',doi='10.1234/ref',url='https://doi.org/10.1234/ref',
            depth=1,priority=5,purpose='核对定义',module='definition',reference_ref={'source_id':parent,'span_id':parent+'#p0001'}) for parent in ['s1','s2']]
        client=ExternalDouble([analysis,analysis_payload(('s1','s2','ref'))],pages={'https://doi.org/10.1234/ref':'引用文献的可读片段。'})
        reply=pipeline.prepare_evidence(validate_request(data),client)
        self.assertEqual({(r['source'],r['target']) for r in reply.evidence['source_relations']},{('s1','ref'),('s2','ref')})
        self.assertEqual(len([e for e in client.events if e[0]=='fetch']),1)

    def test_reference_using_an_existing_source_id_still_records_citation(self):
        data=request_payload(); data['network_allowed']=True
        data['sources'][0]['text']+='\n参考文献：Reference. doi:10.1234/ref'
        data['sources'].append(dict(id='s2',title='Reference',scope='excerpt',text='引用文献实际片段。',doi='10.1234/ref'))
        analysis=analysis_payload(('s1','s2')); analysis['reference_candidates']=[dict(id='s2',parent_id='s1',title='Reference',doi='10.1234/ref',
            url='https://doi.org/10.1234/ref',depth=1,priority=5,purpose='核对定义',module='definition',reference_ref={'source_id':'s1','span_id':'s1#p0001'})]
        reply=pipeline.prepare_evidence(validate_request(data),ExternalDouble([analysis]))
        self.assertEqual([(r['source'],r['target']) for r in reply.evidence['source_relations']],[('s1','s2')])

    def test_malformed_status_can_be_repaired_once_without_unclassified_crash(self):
        bad=result_payload(); bad['status']=[]
        reply=pipeline.generate_lesson(self.request,ExternalDouble([analysis_payload(),bad,result_payload()]))
        self.assertEqual(reply.action,'complete')
        self.assertEqual(reply.repair_count,1)

    def test_multiple_sources_need_explicit_synthesis_not_just_reading_notes(self):
        data=request_payload(); data['network_allowed']=True
        data['sources'].append(dict(id='s2',title='第二篇材料',scope='excerpt',text='独立补充说明。'))
        analysis=analysis_payload(('s1','s2')); analysis.pop('synthesis',None)
        client=ExternalDouble([analysis,deepcopy(analysis)])
        with self.assertRaises(pipeline.PipelineError) as error:
            pipeline.prepare_evidence(validate_request(data),client)
        self.assertEqual(error.exception.code,'invalid_evidence_analysis')
        self.assertEqual(len(client.events),2)

    def test_distinct_contributions_may_be_explained_without_fabricating_relations(self):
        data=request_payload(); data['network_allowed']=True
        data['sources'].append(dict(id='s2',title='第二篇材料',scope='excerpt',text='独立补充说明。'))
        analysis=analysis_payload(('s1','s2'))
        analysis['synthesis']=[dict(source_id=sid,role='background',contribution='围绕锚点提供背景说明。',
            related_source_ids=[],relationship_reason='现有片段提供各自的说明，尚不能判断直接发展或验证关系。',
            evidence=[{'source_id':sid,'span_id':sid+'#p0000'}]) for sid in ['s1','s2']]
        reply=pipeline.prepare_evidence(validate_request(data),ExternalDouble([analysis]))
        self.assertEqual(reply.action,'ready_for_explanation')
        self.assertEqual(len(reply.evidence['synthesis']),2)
        self.assertEqual(reply.evidence['source_relations'],[])

    def test_budget_exhausted_during_reference_read_preserves_completed_notes(self):
        data=request_payload(); data['network_allowed']=True
        data['sources'][0]['text']+='\n参考文献：Reference. doi:10.1234/ref'
        analysis=analysis_payload()
        analysis['reference_candidates']=[dict(id='ref',parent_id='s1',title='Reference',doi='10.1234/ref',url='https://doi.org/10.1234/ref',
            depth=1,priority=5,purpose='核对定义',module='definition',reference_ref={'source_id':'s1','span_id':'s1#p0001'})]
        client=ExternalDouble([analysis],pages={'https://doi.org/10.1234/ref':DeepSeekError('call_budget_exhausted','达到预算')})
        reply=pipeline.prepare_evidence(validate_request(data),client)
        self.assertEqual(reply.action,'needs_budget')
        self.assertEqual(reply.evidence['reading_notes'][0]['source_id'],'s1')
        self.assertFalse(reply.evidence['can_generate'])

    def test_budget_exhausted_before_reanalysis_preserves_read_but_unanalyzed_source(self):
        data=request_payload(); data['network_allowed']=True
        data['sources'][0]['text']+='\n参考文献：Reference. doi:10.1234/ref'
        analysis=analysis_payload()
        analysis['reference_candidates']=[dict(id='ref',parent_id='s1',title='Reference',doi='10.1234/ref',url='https://doi.org/10.1234/ref',
            depth=1,priority=5,purpose='核对定义',module='definition',reference_ref={'source_id':'s1','span_id':'s1#p0001'})]
        client=ExternalDouble([analysis,DeepSeekError('call_budget_exhausted','达到预算')],pages={'https://doi.org/10.1234/ref':'取得的引用原文。'})
        reply=pipeline.prepare_evidence(validate_request(data),client)
        self.assertEqual(reply.action,'needs_budget')
        self.assertIn('ref',reply.evidence['not_analyzed_source_ids'])
        self.assertEqual(next(s for s in reply.evidence['sources'] if s['id']=='ref')['scope'],'excerpt')
        self.assertFalse(reply.evidence['can_generate'])

    def test_evidence_can_be_prepared_and_inspected_before_any_lesson_generation(self):
        self.assertTrue(callable(getattr(pipeline,'prepare_evidence',None)), 'separate evidence stage is missing')
        client=ExternalDouble([analysis_payload()])
        reply=pipeline.prepare_evidence(self.request,client)
        self.assertEqual(reply.action,'ready_for_explanation')
        self.assertIsNone(reply.lesson)
        self.assertEqual(len(client.events),1)
        self.assertTrue(reply.evidence['requires_semantic_review'])

    def test_malformed_per_paper_note_is_reported_as_evidence_error(self):
        analysis=analysis_payload(); analysis['reading_notes']=['not-an-object']
        client=ExternalDouble([analysis])
        with self.assertRaises(pipeline.PipelineError) as error:
            pipeline.generate_lesson(self.request,client)
        self.assertEqual(error.exception.code,'invalid_evidence_analysis')

    def test_nonfinite_model_json_is_rejected_before_using_evidence(self):
        analysis=analysis_payload(); analysis['unexpected_metric']=float('nan')
        client=ExternalDouble([analysis])
        with self.assertRaises(pipeline.PipelineError) as error:
            pipeline.generate_lesson(self.request,client)
        self.assertEqual(error.exception.code,'invalid_model_json')

    def test_author_year_doi_and_original_definition_survive_pipeline_search(self):
        data = request_payload(); data.update(sources=[], network_allowed=True)
        data['term'].update(author='Example Author', year=2025, doi='10.1234/anchored')
        client = ExternalDouble()
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual(reply.anchor['author'], 'Example Author')
        self.assertEqual(reply.anchor['year'], 2025)
        self.assertEqual(reply.anchor['doi'], '10.1234/anchored')
        self.assertEqual(client.events[0], ('search', '10.1234/anchored Example Author 2025'))

    def test_fetch_keeps_user_bibliography_separate_from_web_page_heading(self):
        data = request_payload(); data['network_allowed'] = True
        data['sources'][0].update(title='用户核对的论文名', authors=['Example Author'], year=2025,
                                 text='', scope='metadata', doi='10.1234/original', url='https://example.com/paper')
        client = ExternalDouble([analysis_payload(), result_payload()], pages={'https://example.com/paper': self.request.sources[0]['text']})
        reply = pipeline.generate_lesson(validate_request(data), client)
        source = reply.evidence['sources'][0]
        self.assertEqual(source['title'], '用户核对的论文名')
        self.assertEqual(source['authors'], ['Example Author'])
        self.assertEqual(source['year'], 2025)
        self.assertEqual(source['retrieved_title'], '测试抓取片段')

    def test_one_unavailable_provided_paper_does_not_discard_other_reading(self):
        data = request_payload(); data['network_allowed'] = True
        data['sources'].append(dict(id='s2', title='无法读取的文献', text='', scope='metadata', doi='', url='https://example.com/unavailable'))
        client = ExternalDouble([analysis_payload()], pages={'https://example.com/unavailable': DeepSeekError('source_unavailable', '未取到正文')})
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual(reply.action, 'needs_sources')
        self.assertEqual(reply.evidence['reading_notes'][0]['source_id'], 's1')
        self.assertTrue(any('无法读取的文献' in q for q in reply.questions))
        self.assertEqual(next(s for s in reply.evidence['sources'] if s['id']=='s2')['scope'], 'metadata')

    def test_reference_to_already_supplied_paper_records_link_without_refetch(self):
        data = request_payload(); data['network_allowed'] = True
        data['sources'][0]['text'] += '\n参考文献：Related Method. doi:10.1234/related'
        data['sources'].append(dict(id='s2', title='Related Method', text='相关方法实际正文。', scope='excerpt', doi='10.1234/related'))
        analysis = analysis_payload(('s1', 's2'))
        analysis['reference_candidates'] = [dict(id='ref-alias', parent_id='s1', title='Related Method', doi='10.1234/related',
            url='https://doi.org/10.1234/related', depth=1, priority=5, purpose='核对提出来源', module='definition',
            reference_ref={'source_id':'s1','span_id':'s1#p0001'})]
        client = ExternalDouble([analysis, result_payload()])
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual(reply.action, 'complete')
        self.assertEqual([(r['source'],r['target'],r['type']) for r in reply.evidence['source_relations']], [('s1','s2','cites')])
        self.assertFalse(any(e[0]=='fetch' for e in client.events))

    def test_unread_reference_is_kept_as_citation_not_content_evidence(self):
        data = request_payload(); data['network_allowed'] = True
        data['sources'][0]['text'] += '\n参考文献：Missing Method. doi:10.1234/missing'
        analysis = analysis_payload()
        analysis['reference_candidates'] = [dict(id='ref-missing', parent_id='s1', title='Missing Method', doi='10.1234/missing',
            url='https://doi.org/10.1234/missing', depth=1, priority=5, purpose='核对方法条件', module='method',
            reference_ref={'source_id':'s1','span_id':'s1#p0001'})]
        client = ExternalDouble([analysis], pages={'https://doi.org/10.1234/missing':DeepSeekError('source_unavailable','未取到正文')})
        reply = pipeline.generate_lesson(validate_request(data), client)
        source = next(s for s in reply.evidence['sources'] if s['id']=='ref-missing')
        self.assertEqual(source['scope'], 'metadata')
        self.assertEqual(reply.evidence['source_relations'][0]['type'], 'cites')
        self.assertEqual(reply.action, 'needs_sources')

    def setUp(self):
        self.assertIsNotNone(pipeline, 'generation pipeline is not implemented')
        data = request_payload(); data['network_allowed'] = True
        self.request = validate_request(data)

    def test_no_paper_prompts_once_without_contacting_model(self):
        data = request_payload(); data.update(sources=[], literature_prompted=False)
        client = ExternalDouble()
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual(reply.action, 'ask_for_literature')
        self.assertEqual(client.events, [])

    def test_no_paper_after_prompt_searches_and_asks_confirmation(self):
        data = request_payload(); data.update(sources=[], literature_prompted=True, network_allowed=True)
        candidate = {'id': 'found-a', 'title': '待确认的相关论文', 'doi': '', 'url': 'https://example.com/paper',
                     'scope': 'metadata', 'text': '', 'origin': 'search', 'references': []}
        client = ExternalDouble(candidates=[candidate])
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual(reply.action, 'confirm_concept')
        self.assertEqual(reply.candidates[0]['id'], 'found-a')
        self.assertTrue(all(e[0] == 'search' for e in client.events))
        self.assertEqual(reply.anchor['definition'], data['term']['definition'])

    def test_provided_source_is_analyzed_before_teaching_generation(self):
        client = ExternalDouble([analysis_payload(), result_payload()])
        reply = pipeline.generate_lesson(self.request, client)
        self.assertEqual(reply.action, 'complete')
        self.assertEqual(reply.lesson.term['definition'], self.request.term['definition'])
        self.assertIn('reading_notes', client.events[0][1][0]['content'])
        self.assertIsNotNone(reply.evidence)

    def test_all_provided_papers_need_locatable_reading_notes(self):
        data = request_payload(); data['network_allowed'] = True
        data['sources'].append(dict(id='s2', title='第二篇测试资料', text='另一种适用条件。', scope='excerpt', doi=''))
        client = ExternalDouble([analysis_payload()])
        with self.assertRaises(pipeline.PipelineError) as error:
            pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual(error.exception.code, 'invalid_evidence_analysis')

    def test_multiple_papers_are_analyzed_together_without_replacing_anchor(self):
        data = request_payload(); data['network_allowed'] = True
        data['sources'].append(dict(id='s2', title='第二篇测试资料', text='另一种适用条件。', scope='excerpt', doi=''))
        client = ExternalDouble([analysis_payload(('s1', 's2')), result_payload()])
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual(reply.action, 'complete')
        self.assertEqual(len(reply.evidence['sources']), 2)

    def test_anchor_conflict_asks_before_generating_the_wrong_concept(self):
        analysis = analysis_payload(); analysis['anchor_conflicts'] = ['所给定义与论文对象不同，请确认。']
        client = ExternalDouble([analysis])
        reply = pipeline.generate_lesson(self.request, client)
        self.assertEqual(reply.action, 'needs_disambiguation')
        self.assertEqual(len(client.events), 1)
        self.assertIsNone(reply.lesson)

    def test_source_gap_is_not_hidden_by_a_fake_complete_lesson(self):
        analysis = analysis_payload(); analysis['missing_evidence'] = ['缺少模型适用条件正文。']
        client = ExternalDouble([analysis])
        reply = pipeline.generate_lesson(self.request, client)
        self.assertEqual(reply.action, 'needs_sources')
        self.assertEqual(len(client.events), 1)

    def test_confirmed_discovery_fetches_and_reads_before_generating(self):
        candidate = dict(id='found-a', title='候选', doi='', url='https://example.com/paper',
                         scope='metadata', text='', origin='search', references=[])
        data = request_payload(); data.update(sources=[], network_allowed=True)
        analysis = analysis_payload(('found-a',))
        for claim in analysis['claims']: claim['evidence'] = [{'source_id': 'found-a', 'span_id': 'found-a#p0000'}]
        result = result_payload()
        for block in result['blocks']:
            for paragraph in block['paragraphs']: paragraph['refs'] = [{'source_id': 'found-a', 'start': 0, 'end': 18}]
        for relation in result['relations']: relation['refs'] = [{'source_id': 'found-a', 'start': 0, 'end': 18}]
        client = ExternalDouble([analysis, result], pages={'https://example.com/paper': self.request.sources[0]['text']})
        reply = pipeline.generate_lesson(validate_request(data), client, candidates=[candidate], confirmed_candidate_id='found-a')
        self.assertEqual([e[0] for e in client.events], ['fetch', 'model', 'model'])
        self.assertEqual(reply.action, 'complete')

    def test_reference_body_is_retrieved_only_with_locatable_bibliographic_basis(self):
        data = request_payload(); data['network_allowed'] = True
        data['sources'][0]['text'] += '\n参考文献：Ref Method. doi:10.1234/ref'
        analysis = analysis_payload()
        analysis['reference_candidates'] = [dict(id='ref-a', parent_id='s1', doi='10.1234/ref',
            url='https://doi.org/10.1234/ref', title='Ref Method', depth=1, priority=5,
            purpose='核验原始定义', module='definition',
            reference_ref={'source_id': 's1', 'span_id': 's1#p0001'})]
        second = analysis_payload(('s1', 'ref-a'))
        client = ExternalDouble([analysis, second, result_payload()], pages={'https://doi.org/10.1234/ref': '参考文献中取得的实际片段。'})
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual([e[0] for e in client.events], ['model', 'fetch', 'model', 'model'])
        self.assertEqual(reply.action, 'complete')
        self.assertTrue(any(s['origin'] == 'reference' for s in reply.evidence['sources']))

    def test_made_up_reference_location_never_triggers_fetch(self):
        analysis = analysis_payload(); analysis['reference_candidates'] = [dict(id='ref-a', parent_id='s1',
            doi='10.1234/ref', url='https://doi.org/10.1234/ref', title='Unmentioned Paper', depth=1,
            priority=5, purpose='核验定义', module='definition',
            reference_ref={'source_id': 's1', 'span_id': 's1#p0000'})]
        client = ExternalDouble([analysis,analysis])
        with self.assertRaises(pipeline.PipelineError): pipeline.generate_lesson(self.request, client)
        self.assertFalse(any(e[0] == 'fetch' for e in client.events))

    def test_format_repair_is_bounded_and_not_evidence_expansion(self):
        bad = result_payload(); bad['quiz']['correct_option'] = 'missing'
        client = ExternalDouble([analysis_payload(), bad, result_payload()])
        reply = pipeline.generate_lesson(self.request, client)
        self.assertEqual(reply.repair_count, 1)
        self.assertEqual(len(client.events), 3)

    def test_failed_reference_gap_survives_successful_read_of_another_reference(self):
        data = request_payload(); data['network_allowed'] = True
        data['sources'][0]['text'] += '\n参考文献：Missing. doi:10.1234/missing\n参考文献：Readable. doi:10.1234/readable'
        analysis = analysis_payload()
        analysis['reference_candidates'] = [dict(id=source_id, parent_id='s1', doi='10.1234/' + suffix,
            url='https://doi.org/10.1234/' + suffix, title=title, depth=1, priority=5,
            purpose='核验原始定义', module='definition', reference_ref={'source_id': 's1', 'span_id': f's1#p000{index}'})
            for source_id, suffix, title, index in [('ref-missing','missing','Missing',1), ('ref-read','readable','Readable',2)]]
        client = ExternalDouble([analysis, analysis_payload(('s1', 'ref-read')), result_payload()], pages={
            'https://doi.org/10.1234/missing': DeepSeekError('source_unavailable', '不可读'),
            'https://doi.org/10.1234/readable': '可取得的参考文献片段。'})
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual(reply.action, 'needs_sources')
        self.assertTrue(any('Missing' in q for q in reply.questions))

    def test_generation_prompt_does_not_repeat_complete_source_bodies_in_bundle(self):
        client = ExternalDouble([analysis_payload(), result_payload()])
        pipeline.generate_lesson(self.request, client)
        lesson_context = json.loads(client.events[1][1][1]['content'])
        self.assertNotIn('sources', lesson_context['evidence_bundle'])
        self.assertNotIn('works', lesson_context['evidence_bundle'])
        self.assertEqual(client.events[1][1][1]['content'].count(self.request.sources[0]['text']), 1)

    def test_gateway_timeout_on_fetch_is_a_gap_not_a_failed_lesson(self):
        # A 504 while fetching one source is "that page is unreachable now", not a
        # reason to discard a whole run: same treatment as a 404.
        data = request_payload(); data['network_allowed'] = True
        data['sources'].append(dict(id='s2', title='网关超时的文献', text='', scope='metadata',
                                    doi='', url='https://example.com/gateway-timeout'))
        client = ExternalDouble([analysis_payload()], pages={
            'https://example.com/gateway-timeout': DeepSeekError('provider_http_504', '供应商请求失败（HTTP 504）。')})
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual(reply.action, 'needs_sources')
        self.assertTrue(any('网关超时的文献' in q for q in reply.questions))
        self.assertEqual(next(s for s in reply.evidence['sources'] if s['id'] == 's2')['scope'], 'metadata')

    def test_gateway_timeout_on_generation_is_still_fatal(self):
        # Only retrieval faults are absorbed; a model request that never produced
        # content must still stop the run.
        client = ExternalDouble([DeepSeekError('provider_http_504', '供应商请求失败（HTTP 504）。')])
        with self.assertRaises(DeepSeekError):
            pipeline.generate_lesson(self.request, client)


if __name__ == '__main__': unittest.main()
