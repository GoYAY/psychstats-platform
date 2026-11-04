from copy import deepcopy
import json
import unittest
from term_explainer import frameworks as api
from term_explainer.deepseek import DeepSeekClient
from tests.term_explainer.test_frameworks import payload as old_payload

def payload():
    p=old_payload();p['schemaVersion']=2
    for e in p['relations']:e['basis']='literature'
    return p
def output():
    return {'schemaVersion':2,'groups':[{'targetFrameworkId':None,'title':'人–AI互动','description':'互动中的判断变化','scope':'研究反复互动中的判断变化','members':[{'ref':{'space':'personal','id':i},'role':'core','reason':'定义直接涉及持续互动中的变化'} for i in ['drift','entanglement']]+[{'ref':{'space':'new','id':'control'},'role':'supporting','reason':'理解如何调整判断过程'}]}],'contexts':[{'localId':'control','name':'元认知控制','aliases':[],'definition':'根据对当前思考的检查调整判断过程。','reason':'帮助理解互动中的判断调整'}],'relations':[{'from':{'space':'new','id':'control'},'to':{'space':'personal','id':'drift'},'type':'used_in','reason':'可用于理解个体如何调节判断变化。'}],'reviews':[],'unassigned':[{'space':'personal','id':'dtp'}]}

class SemanticFrameworkTests(unittest.TestCase):
    def test_v2_returns_typed_groups_briefs_and_inference_in_one_actual_adapter_call(self):
        sent=[]
        def transport(url,body,headers,timeout):
            sent.append(body)
            return {'model':'deepseek-flash','usage':{'prompt_tokens':12,'completion_tokens':20,'total_tokens':32},'choices':[{'message':{'content':json.dumps(output(),ensure_ascii=False)},'finish_reason':'stop'}]}
        client=DeepSeekClient(api_key='test-only',max_calls=1,transport=transport)
        result=api.analyze_frameworks(payload(),client)
        self.assertEqual(result['schemaVersion'],2);self.assertEqual(result['calls'],1)
        self.assertEqual(result['contexts'][0]['name'],'元认知控制');self.assertEqual(len(sent),1)
        self.assertEqual(result['unassigned'],[{'space':'personal','id':'dtp'}])
    def test_bad_identity_role_unlinked_brief_and_fake_citation_fail_closed(self):
        edits=[lambda o:o['relations'][0]['to'].update(id='unknown'),lambda o:o['groups'][0]['members'][0].update(role='causal'),lambda o:o.update(relations=[]),lambda o:o['relations'][0].update(refs=[{'excerpt':'invented'}]),lambda o:o['contexts'][0].update(definition='<script>x</script>'),lambda o:o['groups'][0]['members'].append(o['groups'][0]['members'][0])]
        for edit in edits:
            o=output();edit(o)
            with self.subTest(edit=edit):
                with self.assertRaises(api.FrameworkError):api.validate_output(o,payload())
    def test_self_loops_and_combined_prerequisite_cycles_rejected(self):
        o=output();o['relations'][0]['to']=deepcopy(o['relations'][0]['from'])
        with self.assertRaises(api.FrameworkError):api.validate_output(o,payload())
        o=output();a={'space':'personal','id':'drift'};b={'space':'personal','id':'entanglement'}
        o['relations'] += [{'from':a,'to':b,'type':'prerequisites','reason':'需要前置'},{'from':b,'to':a,'type':'prerequisites','reason':'反向前置'}]
        with self.assertRaises(api.FrameworkError):api.validate_output(o,payload())
    def test_input_privacy_limits_and_review_target_checked(self):
        p=payload();p['evidence']='private'
        with self.assertRaises(api.FrameworkError):api.validate_input(p)
        o=output();o['reviews']=[{'frameworkId':'missing','ref':{'space':'personal','id':'drift'},'action':'remove','reason':'定义不符'}]
        with self.assertRaises(api.FrameworkError):api.validate_output(o,payload())
    def test_all_unassigned_allowed_but_no_unknown_new_term_can_escape_groups(self):
        o={'schemaVersion':2,'groups':[],'contexts':[],'relations':[],'reviews':[],'unassigned':[t['ref'] for t in payload()['terms']]}
        self.assertEqual(len(api.validate_output(o,payload())['unassigned']),3)
        o['contexts']=output()['contexts']
        with self.assertRaises(api.FrameworkError):api.validate_output(o,payload())

if __name__=='__main__':unittest.main()
