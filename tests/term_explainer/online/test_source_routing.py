from copy import deepcopy
import json
from term_explainer.online.sources import prepare_sources,apply_answer
from term_explainer.online.config import OnlineError
from term_explainer.deepseek import DeepSeekClient
from tests.term_explainer.helpers import request_payload
from tests.term_explainer.test_pipeline import analysis_payload
import unittest

class RoutingTests(unittest.TestCase):
    def test_clarification_preserves_distinct_bibliography_and_retrieved_identity(self):
        from tests.term_explainer.test_pipeline import ExternalDouble
        request=request_payload();source=deepcopy(request['sources'][0]);request.update(sources=[],literature_prompted=True,network_allowed=True)
        source.update(title='Requested article A',url='https://example.org/requested',retrieved_title='Fetched article B',retrieved_url='https://example.org/actual')
        state=dict(version=1,action='waiting_input',request=request,sources=[source],readings={},selections={},question=dict(id='q',kind='scope'))
        resumed=apply_answer(state,dict(question_id='q',action='clarify',explanation='请核对这份资料与目标术语的关系，保留实际获取的来源身份。'),1)
        analysis=analysis_payload();analysis['reading_notes'][0]['identity_check']=dict(status='mismatch',reason='Requested and fetched titles differ.')
        client=ExternalDouble([analysis]);result=prepare_sources(request,[],client,lambda _:None,state=resumed)
        self.assertEqual(result['action'],'waiting_input')
        self.assertFalse(result.get('evidence',{}).get('can_generate',False))
        saved=result['sources'][0]
        for field in ('title','url','retrieved_title','retrieved_url','text'):self.assertEqual(saved[field],source[field],field)
        context=json.loads(client.events[0][1][-1]['content'])
        for field in ('retrieved_title','retrieved_url'):self.assertEqual(context['sources'][0][field],source[field],field)

    def test_no_upload_clarification_reuses_actual_fetched_text_without_search_or_fetch(self):
        from tests.term_explainer.test_pipeline import analysis_payload
        from term_explainer.deepseek import ModelReply
        request=request_payload();request.update(sources=[],literature_prompted=True,network_allowed=True)
        candidate=dict(id='s1',title='Primary Chapter',url='https://example.org/chapter',text='',scope='metadata',origin='search')
        state=dict(version=1,action='input',request=deepcopy(request),sources=[],candidates=[candidate],confirmed_candidate_id='s1',readings={},selections={},question=None)
        class Client:
            def __init__(self):self.fetches=0;self.analyses=0
            def search(self,q):raise AssertionError('Clarification must not discard acquired text and restart search')
            def fetch(self,url,**kw):
                self.fetches+=1
                if self.fetches>1:raise AssertionError('Already acquired text must not be fetched again')
                return dict(candidate,text='Primary Chapter\n\n总体是研究希望了解的目标对象集合。样本是实际获得观测的对象。',scope='excerpt')
            def generate(self,messages,*args,**kwargs):
                self.analyses+=1;ctx=json.loads(messages[-1]['content']);value=analysis_payload();source=ctx['sources'][0];ref=dict(source_id='s1',span_id=source['spans'][0]['id'])
                for row in value['claims']+value['reading_notes']+value['synthesis']:row['evidence']=[ref]
                value['reading_notes'][0]['identity_check']=dict(status='uncertain' if self.analyses==1 else 'matches',reason='Please clarify source identity.' if self.analyses==1 else 'Actual chapter title and URL match.')
                return ModelReply(json.dumps(value,ensure_ascii=False),'offline-test',{},'stop')
        client=Client();first=prepare_sources(request,[],client,lambda s:None,state=state)
        self.assertEqual(first['action'],'waiting_input');self.assertTrue(first['sources'],'Retain actual acquired text even when identity needs clarification')
        resumed=apply_answer(first,dict(question_id=first['question']['id'],action='clarify',explanation='保留这份已读取的章节，重点解释目标范围与实际观察对象。'),first['version'])
        second=prepare_sources(request,[],client,lambda s:None,state=resumed)
        self.assertEqual(second['action'],'ready');self.assertEqual(client.fetches,1);self.assertEqual(client.analyses,2)

    def test_paper_set_context_preserves_actual_title_mention_and_real_conflict(self):
        from tests.term_explainer.test_pipeline import ExternalDouble
        from term_explainer.online.config import load_config
        from .helpers import environment
        from tempfile import TemporaryDirectory
        request=request_payload();one=deepcopy(request['sources'][0]);one.update(title='Target Paper',scope='full_text',text='Intro\nTarget evidence.\nReferences\nComparator Paper.')
        two=deepcopy(one);two.update(id='s2',title='Comparator Paper',text='Introduction\nPRIVATE_OTHER_FULL_BODY')
        analysis=analysis_payload();analysis.update(rolling_summary='Current section summary.',key_conditions=[],anchor_conflicts=['Actual definition conflict, not a missing target word.'])
        for obj in analysis['claims']+analysis['reading_notes']+analysis['synthesis']:obj['evidence']=[{'source_id':'s1','span_id':'s1#c0000'}]
        client=ExternalDouble([analysis]);saved=[]
        docs=[dict(source=one,headings=[dict(title='Intro',start=0),dict(title='References',start=one['text'].index('References'))]),dict(source=two,headings=[dict(title='Introduction',start=0)])]
        with TemporaryDirectory() as folder:result=prepare_sources(request,docs,client,lambda v:saved.append(deepcopy(v)),limits=load_config(environment(folder)).limits)
        self.assertEqual(result['action'],'waiting_input');self.assertIn('Actual definition conflict',result['question']['messages'][0])
        plan=result['readings']['s1']['source_set_context'];self.assertEqual({s['id'] for s in plan['sources']},{'s1','s2'})
        mention=plan['title_mentions'][0];self.assertEqual(mention['source_id'],'s1');self.assertEqual(mention['mentioned_source_id'],'s2')
        self.assertEqual(one['text'][mention['start']:mention['end']],'Comparator Paper')
        self.assertNotIn('PRIVATE_OTHER_FULL_BODY',json.dumps(client.events,ensure_ascii=False))

    def test_offline_model_scope_review_keeps_a_core_gap_disclosed_instead_of_blocking(self):
        from tests.term_explainer.test_pipeline import ExternalDouble
        for core in (False,True):
            request=request_payload();request['network_allowed']=False
            analysis=analysis_payload();analysis['missing_evidence']=['定义尚缺关键含义。' if core else '尚无独立实证验证。']
            scope=dict(core_indices=[0] if core else [],research_indices=[] if core else [0],reasons=['目标定义缺失。' if core else '后续验证不妨碍解释已提供概念。'])
            client=ExternalDouble([analysis,scope])
            result=prepare_sources(request,[{'source':request['sources'][0],'headings':[]}],client,lambda v:None)
            # A core gap is disclosed in the delivered scope, never used to stall the page.
            self.assertEqual(result['action'],'ready')
            self.assertEqual(bool(result['evidence'].get('limited_delivery')),core)
            if core:self.assertIn('定义尚缺关键含义。',result['evidence']['delivery_scope']['evidence_gaps'])
            self.assertTrue(all(event[0]=='model' for event in client.events))

    def test_candidate_clarification_discards_old_hits_without_replacing_anchor(self):
        request=request_payload();request.update(sources=[],network_allowed=True)
        from tests.term_explainer.test_pipeline import ExternalDouble
        first=prepare_sources(request,[],ExternalDouble(candidates=[{'id':'candidate-1','title':'Other','url':'https://example.org/p','scope':'metadata','text':''}]),lambda v:None)
        resumed=apply_answer(first,dict(question_id=first['question']['id'],action='clarify',explanation='关注持续互动中的元认知及认知漂移。'),first['version'])
        self.assertFalse(resumed.get('candidates'));self.assertEqual(resumed['request']['term'],request['term'])

    def test_explicit_search_for_more_archives_acquired_sources_and_searches_again(self):
        request=request_payload();request.update(sources=[],network_allowed=True)
        old={'id':'old','title':'Insufficient','scope':'excerpt','text':'A short unrelated paragraph.'}
        state=dict(version=3,action='needs_sources',request=request,sources=[old],readings={},selections={},question=dict(id='q',kind='sources'),candidates=[old],confirmed_candidate_id='old')
        resumed=apply_answer(state,dict(question_id='q',action='continue',allow_network=True),3)
        self.assertEqual(resumed['sources'],[])
        self.assertEqual(resumed['acquisition_history'][0]['sources'],[old])
        self.assertNotIn('confirmed_candidate_id',resumed)
        class Search:
            calls=0
            def search(self,q):
                self.calls+=1
                return [dict(id='new',title='New source',url='https://example.org/new',scope='metadata',text='')]
        provider=Search();next_state=prepare_sources(request,[],provider,lambda _:None,state=resumed)
        self.assertGreater(provider.calls,0);self.assertEqual(next_state['question']['kind'],'concept')

    def test_web_search_can_be_authorized_explicitly_after_literature_prompt(self):
        request=request_payload();request.update(sources=[],literature_prompted=False,network_allowed=False)
        first=prepare_sources(request,[],object(),lambda v:None)
        answer={'question_id':first['question']['id'],'action':'continue','allow_network':True}
        resumed=apply_answer(first,answer,first['version'])
        self.assertTrue(resumed['request']['network_allowed']);self.assertTrue(resumed['request']['literature_prompted'])

    def test_no_source_prompts_then_respects_no_network(self):
        request=request_payload();request.update(sources=[],literature_prompted=False,network_allowed=False)
        class NoNetwork:
            def search(self,*a):raise AssertionError('Network must not run')
            def generate(self,*a):raise AssertionError('Model must not run')
        first=prepare_sources(request,[],NoNetwork(),lambda v:None)
        self.assertEqual(first['action'],'waiting_input');self.assertEqual(first['question']['kind'],'literature')
        answered=apply_answer(first,{'question_id':first['question']['id'],'action':'continue'},first['version'])
        second=prepare_sources(answered['request'],[],NoNetwork(),lambda v:None,state=answered)
        self.assertEqual(second['action'],'needs_sources')
        with self.assertRaises(OnlineError):apply_answer(first,{'question_id':'other','action':'continue'},first['version'])

    def test_search_candidates_require_explicit_identity_confirmation(self):
        request=request_payload();request.update(sources=[],network_allowed=True)
        class Search:
            calls=0
            def search(self,q):
                self.calls+=1
                return [{'id':'candidate-1','title':'Example','url':'https://example.org/paper','scope':'metadata','text':''}]
        provider=Search();decision=prepare_sources(request,[],provider,lambda v:None)
        self.assertEqual(decision['question']['kind'],'concept');self.assertGreater(provider.calls,0)
        with self.assertRaises(OnlineError):apply_answer(decision,{'question_id':decision['question']['id'],'candidate_id':'invented'},decision['version'])

    def test_excerpt_with_valid_evidence_is_ready_and_multi_source_does_not_collapse(self):
        request=request_payload();reply=analysis_payload();sent=[]
        def transport(url,payload,headers,timeout):
            sent.append(payload)
            return {'model':'deepseek-flash','usage':{'total_tokens':30},'choices':[{'finish_reason':'stop','message':{'content':json.dumps(reply,ensure_ascii=False)}}]}
        client=DeepSeekClient(api_key='offline',max_calls=2,transport=transport)
        doc={'source':deepcopy(request['sources'][0]),'headings':[]}
        decision=prepare_sources(request,[doc],client,lambda v:None)
        self.assertEqual(decision['action'],'ready');self.assertEqual(len(decision['sources']),1)
        self.assertTrue(decision['evidence']['can_generate'])

    def test_two_papers_keep_separate_identities_and_reading_contributions(self):
        from tests.term_explainer.test_pipeline import ExternalDouble
        request=request_payload();other=deepcopy(request['sources'][0]);other.update(id='s2',title='另一篇说明',text='第二份资料讨论实际取样所需的条件。')
        client=ExternalDouble([analysis_payload(('s1','s2'))])
        decision=prepare_sources(request,[{'source':request['sources'][0],'headings':[]},{'source':other,'headings':[]}],client,lambda v:None)
        self.assertEqual(decision['action'],'ready');self.assertEqual({s['id'] for s in decision['sources']},{'s1','s2'})
        self.assertEqual({s['source_id'] for s in decision['evidence']['synthesis']},{'s1','s2'})

    def test_source_identity_conflict_pauses_without_replacing_user_term(self):
        from tests.term_explainer.test_pipeline import ExternalDouble
        request=request_payload();analysis=analysis_payload();analysis['anchor_conflicts']=['两篇资料中的同名概念含义不同，请确认。']
        client=ExternalDouble([analysis]);decision=prepare_sources(request,[{'source':request['sources'][0],'headings':[]}],client,lambda v:None)
        self.assertEqual(decision['action'],'waiting_input');self.assertEqual(decision['question']['kind'],'scope')
        self.assertEqual(decision['request']['term'],request['term'])

    def test_whole_paper_reads_actual_sections_before_selecting_evidence(self):
        from tests.term_explainer.test_pipeline import ExternalDouble
        from term_explainer.online.config import load_config
        from .helpers import environment
        from tempfile import TemporaryDirectory
        request=request_payload();source=deepcopy(request['sources'][0]);source.update(scope='full_text',text='Intro\nDefinition and real-world use in one short unit.\nReferences\nAuthor (2020). A paper.')
        reading=analysis_payload();reading.update(rolling_summary='Short memory.',key_conditions=[])
        for obj in reading['claims']+reading['reading_notes']+reading['synthesis']:
            obj['evidence']=[{'source_id':'s1','span_id':'s1#c0000'}]
        evidence=analysis_payload(('s1-selected',))
        for claim in evidence['claims']:claim['evidence']=[{'source_id':'s1-selected','span_id':'s1-selected#c0000'}]
        for obj in evidence['reading_notes']+evidence['synthesis']:obj['evidence']=[{'source_id':'s1-selected','span_id':'s1-selected#c0000'}]
        client=ExternalDouble([reading,{'section_ids':['unit-001'],'reason':'Actual definition and use.'},evidence]);saved=[]
        with TemporaryDirectory() as folder:
            decision=prepare_sources(request,[{'source':source,'headings':[{'title':'Intro','start':0},{'title':'References','start':source['text'].index('References')}]}],client,lambda v:saved.append(deepcopy(v)),limits=load_config(environment(folder)).limits)
        self.assertEqual(decision['action'],'ready');self.assertEqual(decision['readings']['s1']['next_section'],2)
        self.assertEqual(decision['readings']['s1']['readings'][-1]['mode'],'local_catalogue')
        self.assertEqual(len(client.events),3);self.assertTrue(saved)
