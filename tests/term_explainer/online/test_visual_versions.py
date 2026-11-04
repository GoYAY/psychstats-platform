from copy import deepcopy
import unittest
from term_explainer.visual_versions import candidate_id,append_version,restore_relations,version_record


def visual(title="t",label="a"):
    return dict(kind="story",title=title,payload=dict(scenes=[dict(title=title,objects=[dict(id="a",label=label,kind="person",state="neutral")],connections=[])]))


class VersionTests(unittest.TestCase):
    def test_candidate_id_is_content_fingerprint(self):
        self.assertEqual(candidate_id(visual()),candidate_id(visual()))
        self.assertNotEqual(candidate_id(visual()),candidate_id(visual(label="b")))

    def test_regression_never_replaces_baseline_or_accepted(self):
        state=dict()
        first=append_version(state,visual(),candidate=candidate_id(visual()),baseline=candidate_id(visual()),accepted=False)
        good=deepcopy(visual());good["payload"]["scenes"][0]["objects"][0]["state"]="selected"
        append_version(state,good,candidate=candidate_id(good),baseline=first["version_id"],accepted=True,review=dict(decision="pass"))
        regressed=deepcopy(visual());regressed["payload"]["scenes"]=regressed["payload"]["scenes"][:1]
        regressed["payload"]["scenes"][0]["objects"]=regressed["payload"]["scenes"][0]["objects"][:1]
        append_version(state,regressed,candidate=candidate_id(regressed),baseline=first["version_id"],accepted=False,regression="scene removed")
        self.assertEqual(state["accepted_version"],candidate_id(good))
        self.assertEqual(state["baseline_version"],first["version_id"])
        self.assertEqual(len(state["version_log"]),3)
        self.assertFalse(state["version_log"][-1]["accepted"])

    def test_relations_survive_restart_and_reject_unknown_ids(self):
        state=dict(version_log=[dict(version_id="v1")],candidate_version="v1",baseline_version="v1",accepted_version="vX")
        candidate,baseline,accepted=restore_relations(state)
        self.assertEqual((candidate,baseline,accepted),("v1","v1",None))
        self.assertEqual(restore_relations(dict(version_log=[])),(None,None,None))
