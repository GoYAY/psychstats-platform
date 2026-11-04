import importlib
import json
import unittest
from term_explainer.deepseek import DeepSeekClient
try:
    api=importlib.import_module('term_explainer.frameworks')
except ModuleNotFoundError:
    api=None

def payload():
    return {'schemaVersion':1,'terms':[{'ref':{'space':'personal','id':i},'name':name,'definition':definition,'summary':'','revisionId':'rev-'+i} for i,name,definition in [('drift','认知漂移','互动中判断标准与思维方式逐步变化。'),('entanglement','纠缠','人与AI的相互适应影响后续互动。'),('dtp','优势特质剖面','根据强迫选择作答估计个体的优势特质。')]],'frameworks':[],'relations':[{'from':{'space':'personal','id':'entanglement'},'to':{'space':'personal','id':'drift'},'type':'next'}]}

def output():
    return {'groups':[{'targetFrameworkId':None,'title':'人–AI交互','description':'互动与认知变化','members':[{'ref':{'space':'personal','id':i},'reason':'共同涉及持续互动中的变化'} for i in ['drift','entanglement']]}],'unassigned':[{'space':'personal','id':'dtp'}]}

class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(api,'Framework analysis API missing')
    def test_validation_preserves_ids_and_rejects_unknown_fields_and_oversize(self):
        p=payload(); before=json.dumps(p,ensure_ascii=False)
        actual=api.validate_input(p)
        self.assertEqual(actual['terms'][0]['ref'],{'space':'personal','id':'drift'})
        self.assertEqual(json.dumps(p,ensure_ascii=False),before)
        for bad in [dict(p,evidence='private'),dict(p,terms=p['terms']*80)]:
            with self.assertRaises(api.FrameworkError):api.validate_input(bad)
        p['terms'][0]['summary']='甲'*1501
        with self.assertRaises(api.FrameworkError):api.validate_input(p)
    def test_real_adapter_records_one_call_and_normalized_groups_without_semantic_edges(self):
        sent=[]
        def transport(url,body,headers,timeout):
            sent.append(body)
            return {'model':'deepseek-flash','usage':{'prompt_tokens':30,'completion_tokens':20,'total_tokens':50},'choices':[{'message':{'content':json.dumps(output(),ensure_ascii=False)},'finish_reason':'stop'}]}
        client=DeepSeekClient(api_key='test-only',max_calls=1,transport=transport)
        result=api.analyze_frameworks(payload(),client)
        self.assertEqual(result['calls'],1);self.assertEqual(result['usage']['total_tokens'],50)
        self.assertEqual(result['unassigned'],[{'space':'personal','id':'dtp'}]);self.assertNotIn('edges',result)
        self.assertEqual(len(sent),1);self.assertEqual(len(result['inputHash']),64)
    def test_model_cannot_add_unknown_ids_duplicate_members_or_executable_fields(self):
        for mutate in [lambda x:x['groups'][0]['members'].append({'ref':{'space':'personal','id':'unknown'},'reason':'猜测'}),lambda x:x['groups'][0]['members'].append(x['groups'][0]['members'][0]),lambda x:x['groups'][0].update(html='<script>'),lambda x:x['groups'][0].update(targetFrameworkId='unknown')]:
            candidate=output();mutate(candidate)
            with self.assertRaises(api.FrameworkError):api.validate_output(candidate,payload())
    def test_every_input_term_has_group_or_unassigned_and_identity_can_overlap_frames(self):
        candidate=output();candidate['unassigned']=[]
        with self.assertRaises(api.FrameworkError):api.validate_output(candidate,payload())
        candidate=output();candidate['groups'].append({**candidate['groups'][0],'title':'第二个角度'})
        self.assertEqual(len(api.validate_output(candidate,payload())['groups']),2)
    def test_input_hash_does_not_depend_on_dictionary_insertion_order(self):
        p=payload();q=dict(reversed(list(p.items())))
        self.assertEqual(api.input_hash(p),api.input_hash(q))
    def test_unhashable_target_is_a_validation_error(self):
        for target in ([],{}):
            candidate=output();candidate['groups'][0]['targetFrameworkId']=target
            with self.assertRaises(api.FrameworkError):api.validate_output(candidate,payload())

if __name__=='__main__':unittest.main()
