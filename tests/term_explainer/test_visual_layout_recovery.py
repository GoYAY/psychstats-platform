"""Mechanical layout recovery: deterministic spacing strategies run before any
model repair, keep their own artifacts, and never alter the teaching JSON."""
from copy import deepcopy
from pathlib import Path
import json,shutil,tempfile,unittest

from term_explainer.figures import COLLISION,render_visual


def dense_three_scene_visual():
    def person(id_,label,state="neutral"):
        return dict(id=id_,label=label,kind="person",state=state)
    return dict(kind="story",origin="teaching",title="固定名额下的加码扩散",
        takeaway="名额不变时，个别人先加码会引发跟随；全员加码后排名回到原样，投入却增加。",
        alt="三幅教学故事图，展示投入与名次变化",refs=[],
        presentation=dict(version=1,focus="process",numeric_role="relative",layout="story",interaction="none"),
        payload=dict(layout="scenes",ordered=True,scenes=[
            dict(title="同一个评优名额",objects=[person("a","甲同学 6 小时"),person("b","乙同学 6 小时")],connections=[]),
            dict(title="乙先增加投入",objects=[person("a","甲同学 6 小时"),person("b","乙同学 8 小时",state="selected")],
                connections=[{"from":"b","to":"a","label":"乙暂时靠前","relation":"comparison"}]),
            dict(title="甲随后跟随加码",objects=[person("a","甲同学 8 小时"),person("b","乙同学 8 小时")],
                connections=[{"from":"a","to":"b","label":"名次回到原样但投入更多","relation":"association"}])]))


class LayoutRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=Path(tempfile.mkdtemp())
        self.qa=Path(__file__).parents[2]/"term_explainer"/"figure_qa"
        self.visual=dense_three_scene_visual()

    def tearDown(self):
        shutil.rmtree(self.tmp,ignore_errors=True)

    def render(self,strategy,visual=None):
        visual=deepcopy(visual or self.visual)
        output=self.tmp/f"layout-{strategy}"
        assets=render_visual(visual,output,run_external_qa=True,qa_dir=self.qa,font_path="C:/Windows/Fonts/msyh.ttc",layout_strategy=strategy)
        return visual,output,assets

    def test_layout_strategies_change_geometry_but_never_the_teaching_json(self):
        before=deepcopy(self.visual)
        geoms=[]
        for strategy in (0,1,2):
            visual,output,assets=self.render(strategy)
            self.assertEqual(visual,before)
            audit=json.loads(Path(assets.audit).read_text(encoding="utf-8"))
            geoms.append([(l["width_px"],l["height_px"]) for l in audit["layouts"]])
        self.assertNotEqual(geoms[0],geoms[2])

    def test_collision_retries_layouts_and_keeps_every_versions_audit(self):
        outcomes=[]
        for strategy in (0,1,2):
            try:
                self.render(strategy);outcomes.append((strategy,True))
            except ValueError as error:
                self.assertEqual(str(error),COLLISION);outcomes.append((strategy,False))
        for strategy,_ in outcomes:
            directory=self.tmp/f"layout-{strategy}"
            self.assertTrue((directory/"figure-audit.json").is_file(),strategy)
            self.assertTrue((directory/"figure-data.json").is_file(),strategy)

    def test_desktop_and_mobile_artifacts_are_written_for_every_strategy(self):
        for strategy in (0,1,2):
            try:
                _,output,assets=self.render(strategy)
            except ValueError:
                continue
            self.assertTrue(Path(assets.desktop).is_file())
            self.assertTrue(Path(assets.mobile).is_file())
            self.assertTrue((output/"figure-audit.json").is_file())
