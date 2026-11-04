import unittest
from copy import deepcopy
from tools.qa_instant_chart_live import require_supported_bar
from unittest.mock import patch

def bar():
    return {'visual':{'kind':'statistical','origin':'teaching','title':'教学人数','alt':'两类人数','takeaway':'对比两类人数。','payload':{'chart_type':'bar','x_label':'类别','y_label':'人数','series':[{'label':'学生','x':['甲','乙'],'y':[2,3]}]}}}

class InstantCaseTests(unittest.TestCase):
    def test_supported_final_repaired_bar_is_accepted(self):
        lesson=bar()
        self.assertIs(require_supported_bar(lesson),lesson)

    def test_unsupported_or_invalid_repaired_visual_cannot_complete_case(self):
        for visual in ({'kind':'story','payload':{}},{'kind':'statistical','payload':{'chart_type':'line'}},{'kind':'statistical','payload':{'chart_type':'bar','x_label':'类别','y_label':'人数','series':[{'label':'组','x':['甲'],'y':[-1]}]}}):
            with self.subTest(visual=visual),self.assertRaises(ValueError):require_supported_bar({'visual':deepcopy(visual)})

    def test_repair_to_unsupported_visual_is_blocked_before_checkpoint_update(self):
        from tools.qa_instant_chart_live import build_supported_delivery
        saved=[]
        def repair(*args,on_visual_repair,**kwargs):
            on_visual_repair({'visual':{'kind':'story','payload':{}}});return {'asset_id':'lesson.zip'}
        with patch('tools.qa_instant_chart_live.build_delivery',side_effect=repair),self.assertRaises(ValueError):
            build_supported_delivery({}, {},bar(),[],None,on_visual_repair=saved.append)
        self.assertEqual(saved,[])

    def test_valid_repaired_bar_can_complete_and_update_checkpoint(self):
        from tools.qa_instant_chart_live import build_supported_delivery
        saved=[];repaired=bar();repaired['visual']['payload']['series'][0]['y']=[3,4]
        def repair(*args,on_visual_repair,**kwargs):
            on_visual_repair(repaired);return {'asset_id':'lesson.zip'}
        with patch('tools.qa_instant_chart_live.build_delivery',side_effect=repair):
            result=build_supported_delivery({}, {},bar(),[],None,on_visual_repair=saved.append)
        self.assertEqual(saved,[repaired]);self.assertEqual(result,{'asset_id':'lesson.zip'})
