"""Synthetic layout regressions; no article text or live model requests."""
from copy import deepcopy
import json
import unittest
from types import SimpleNamespace
from term_explainer.online.sources import _pdf_structure,prepare_sources
from term_explainer.online.config import OnlineError
from term_explainer.full_job import select_evidence,JobError
from term_explainer.deepseek import ModelReply
from tests.term_explainer.helpers import request_payload
from tests.term_explainer.test_pipeline import ExternalDouble,analysis_payload
from term_explainer.section_reading import create_reading_state


def layout(rows):
    return [dict(blocks=[dict(lines=[dict(spans=[dict(text=label,size=size,flags=0)])]) for label,size in rows])],['\n'.join(r[0] for r in rows)+'\n']


class LayoutTests(unittest.TestCase):
    def test_terminal_english_abstract_never_erases_chinese_body(self):
        pages,parts=layout([('1    引言',14),('正文内容。'*80,10),('2.2    研究方法',10),('方法内容。'*80,10),('6    讨论',14),('讨论内容。'*80,10),('Abstract',10),('English summary.',10)])
        headings,_=_pdf_structure(pages,parts,[])
        titles=[h['title'] for h in headings]
        for title in ('1    引言','2.2    研究方法','6    讨论','Abstract'):self.assertIn(title,titles)
        for row in headings:self.assertTrue('\n'.join(parts).startswith(row['title'],row['start']))

    def test_same_size_two_character_and_spaced_inline_abstract_are_located(self):
        pages,parts=layout([('摘    要    摘要段落内容。',9),('引言',10),('研究背景。'*80,10),('方法',10),('方法正文。'*80,10),('参    考    文    献',10),('Author 2025.',10)])
        headings,_=_pdf_structure(pages,parts,[])
        for title in ('摘    要','引言','方法','参    考    文    献'):self.assertIn(title,[r['title'] for r in headings])
        for row in headings:self.assertTrue(parts[0].startswith(row['title'],row['start']))

    def test_numbered_body_sentences_table_labels_and_equations_are_not_sections(self):
        pages,parts=layout([('Introduction',10),('正文。'*100,10),('41 岁(20 岁以下 3 人, 21~25 岁 11 人)',10),('1 所示, 本研究抽取出 61 个码号。',10),('1  心理压力',8),('1 + exp z',10),('2.2    研究方法',10),('方法。'*100,10)])
        headings,_=_pdf_structure(pages,parts,[])
        self.assertEqual([r['title'] for r in headings],['Introduction','2.2    研究方法'])

    def test_same_size_numeric_table_rows_are_not_sections(self):
        pages,parts=layout([('Methods',10),('正文内容。'*80,10),('1  心理压力  0.82',10),('2  焦虑  0.74',10),('后续正文内容。'*80,10)])
        headings,_=_pdf_structure(pages,parts,[])
        self.assertEqual([r['title'] for r in headings],['Methods'])

    def test_title_authors_and_abstract_only_are_rejected_as_a_complete_upload_set(self):
        for title in ('This Is An Abstract Only Paper','认知负荷'):
            with self.subTest(title=title):
                pages,parts=layout([(title,16),('Alice Smith and Bob Jones',10),('Abstract',10),('Only a summary. '*40,10)])
                headings,_=_pdf_structure(pages,parts,[])
                r=request_payload();source=deepcopy(r['sources'][0]);source.update(id='abstract-only',scope='full_text',text=parts[0])
                valid=deepcopy(source);valid.update(id='valid',text='Methods\n实际正文。')
                class Never:
                    def generate(self,messages,*args,**kwargs):raise AssertionError('Article-title metadata is not body evidence')
                with self.assertRaises(OnlineError) as caught:prepare_sources(r,[dict(source=valid,headings=[dict(title='Methods',start=0)]),dict(source=source,headings=headings)],Never(),lambda _:None,limits=SimpleNamespace(max_job_calls=60))
                self.assertEqual(caught.exception.code,'source_needs_structure')


class SelectionTests(unittest.TestCase):
    def test_missing_evidence_can_be_supplemented_without_reselecting_same_empty_paper(self):
        r=request_payload();source=deepcopy(r['sources'][0]);source.update(scope='full_text',text='Methods\n'+source['text'])
        headings=[dict(title='Methods',start=0)]
        reading=create_reading_state(r,source,headings,max_calls=60)
        reading.update(status='read_all_requires_review',next_section=1,readings=[dict(section_id='section-001',title='Methods',claims=[],reading_notes=[])])
        state=dict(version=1,action='input',request=r,sources=[],readings={'s1':reading},selections={},question=None)
        first=prepare_sources(r,[dict(source=source,headings=headings)],ExternalDouble([dict(section_ids=[],reason='本文不含目标定义。')]),lambda _:None,state=state,limits=SimpleNamespace(max_job_calls=60))
        self.assertEqual(first['action'],'waiting_input')
        self.assertEqual(first['question']['kind'],'sources')
        extra=deepcopy(r['sources'][0]);extra['id']='s2'
        a=analysis_payload(('s2',))
        for claim in a['claims']:claim['evidence']=[dict(source_id='s2',span_id='s2#p0000')]
        second=prepare_sources(r,[dict(source=source,headings=headings),dict(source=extra,headings=[])],ExternalDouble([a]),lambda _:None,state=first,limits=SimpleNamespace(max_job_calls=60))
        self.assertEqual(second['action'],'ready')

    def test_large_pre_abstract_content_is_read_not_silently_catalogued(self):
        r=request_payload();source=deepcopy(r['sources'][0]);source.update(scope='full_text',text='正文内容。'*1000+'\nAbstract\nSummary.\nMethods\nActual method.')
        headings=[dict(title=t,start=source['text'].index(t)) for t in ('Abstract','Methods')]
        class Observed(Exception):pass
        class Probe:
            def generate(self,messages,*args,**kwargs):
                payload=json.loads(messages[-1]['content'])
                memory=payload['reading_memory']
                if memory['current_section']!='首个标题前的内容':raise AssertionError('Body was skipped')
                raise Observed()
        with self.assertRaises(Observed):prepare_sources(r,[dict(source=source,headings=headings)],Probe(),lambda _:None,limits=SimpleNamespace(max_job_calls=60))

    def case(self,title='Methods'):
        source=dict(id='s1',title='Teaching fixture',text=title+'\nActual body evidence.',scope='full_text',authors=[],year=None,doi='',url='')
        section=dict(id='section-001',title=title,start=0,end=len(source['text']))
        return dict(stage='selection',reading=dict(sections=[section],readings=[dict(claims=[],reading_notes=[])])),dict(request=request_payload(),source=source)

    def test_abstract_only_candidates_are_rejected_before_model_request(self):
        state,payload=self.case('Abstract')
        class Never:
            def generate(self,messages,*args,**kwargs):raise AssertionError('No provider call when no body is available')
        with self.assertRaises(JobError) as caught:select_evidence(state,payload,Never(),lambda _:None)
        self.assertEqual(caught.exception.code,'source_needs_structure')

    def test_empty_selection_with_reason_is_missing_evidence_not_invalid_identifier(self):
        state,payload=self.case()
        class Empty:
            def generate(self,messages,*args,**kwargs):return ModelReply(json.dumps(dict(section_ids=[],reason='已读正文没有目标概念的定义。')),'offline',{},'stop')
        with self.assertRaises(JobError) as caught:select_evidence(state,payload,Empty(),lambda _:None)
        self.assertEqual(caught.exception.code,'no_relevant_evidence')

    def test_unknown_section_identifier_still_fails_strictly(self):
        state,payload=self.case()
        class Unknown:
            def generate(self,messages,*args,**kwargs):return ModelReply('{"section_ids":["invented"],"reason":"test"}','offline',{},'stop')
        with self.assertRaises(JobError) as caught:select_evidence(state,payload,Unknown(),lambda _:None)
        self.assertEqual(caught.exception.code,'invalid_selection')

    def test_structure_preflight_catches_bad_second_document_before_any_reading(self):
        r=request_payload();one=deepcopy(r['sources'][0]);one.update(scope='full_text',text='Methods\n正文。')
        two=dict(one,id='s2',text='Abstract\nOnly summary.')
        docs=[dict(source=one,headings=[dict(title='Methods',start=0)]),dict(source=two,headings=[dict(title='Abstract',start=0)])]
        class Never:
            def generate(self,messages,*args,**kwargs):raise AssertionError('All uploaded structures must pass before spending')
        with self.assertRaises(OnlineError) as caught:prepare_sources(r,docs,Never(),lambda _:None,limits=SimpleNamespace(max_job_calls=60))
        self.assertEqual(caught.exception.code,'source_needs_structure')
