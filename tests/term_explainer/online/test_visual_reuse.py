from copy import deepcopy
import json,unittest
from unittest.mock import patch
from tests.term_explainer.helpers import request_payload,result_payload


class RepairReuseTests(unittest.TestCase):
    def case(self):
        r=request_payload();l=result_payload()
        l["visual"]["presentation"]=dict(version=1,focus="process",numeric_role="relative",layout="story",interaction="none")
        return r,l

    def test_repair_round_reuses_finished_lesson_without_rereading(self):
        from term_explainer.online.visual_quality import prepare_visual_delivery
        r,l=self.case()
        l["visual"]["refs"]=[dict(source_id="s1",start=0,end=18)]
        fingerprint_before=json.dumps([l["blocks"],l.get("quiz"),l.get("formulas")],ensure_ascii=False,sort_keys=True)
        seen={}
        def repair(request,lesson,sources,provider,*,visual_host=None,issues=None,visual_policy_version=0,preservation=None,repair_policy_version=1):
            seen["lesson"]=deepcopy(lesson);seen["sources"]=deepcopy(sources);seen["issues"]=deepcopy(issues)
            seen["preservation_keys"]=sorted((preservation or {}).keys())
            revised=deepcopy(lesson)
            revised["visual"]["payload"]["scenes"][0]["objects"][0]["state"]="selected"
            return revised
        with patch("term_explainer.online.visual_quality.review_visual",side_effect=[
                dict(decision="revise",reason="第二幕缺中间状态",object_paths=["/payload/scenes","/payload/scenes/0/objects/0"],refs=[]),
                dict(decision="pass",reason="ok",object_paths=[],refs=[])]), \
             patch("term_explainer.online.visual_quality.repair_visual",side_effect=repair):
            out,_,state=prepare_visual_delivery(r,l,r["sources"],object(),render=lambda *a:"a",state=None,on_checkpoint=lambda s:None)
        self.assertEqual(seen["lesson"]["blocks"],l["blocks"])
        fingerprint_after=json.dumps([seen["lesson"]["blocks"],seen["lesson"].get("quiz"),seen["lesson"].get("formulas")],ensure_ascii=False,sort_keys=True)
        self.assertEqual(fingerprint_before,fingerprint_after)
        self.assertEqual(seen["sources"],r["sources"])
        self.assertEqual([i["reason"] for i in seen["issues"]],["第二幕缺中间状态"])
        self.assertIn("scenes",seen["preservation_keys"])
        self.assertEqual(state["phase"],"passed")

    def test_legacy_visual_state_migrates_conservatively(self):
        from term_explainer.online.recovery import reserve_recovery
        legacy=dict(phase="review_required",failure="single visual revision exhausted",
            revised_lesson=dict(blocks=[],visual=dict(kind="story")),repairs_used=1,reviews={})
        job=dict(id="j",state="waiting_input",progress={"error_code":"visual_review_required"},
            checkpoint=dict(visual_quality=legacy,lesson=dict(blocks=[])),manifest={"documents":[]})
        checkpoint=reserve_recovery(job)
        q=checkpoint["visual_quality"]
        self.assertEqual(q["phase"],"blocked_manual_check")
        self.assertEqual(q["issue_binding"],"unmatched")
        self.assertNotIn("repair_issues",q)
        self.assertEqual(checkpoint["recovery_resumes"],0)
        self.assertEqual(len(q["recovery_history"]),1)
