"""Story captions live in their own reserved band: many vertical links with
multi-line relation text must render, audit clean, and keep every label."""
from pathlib import Path
import json,shutil,tempfile,unittest

from term_explainer.figures import render_visual

CAPTIONS=("甲同学每天投入6小时 · 甲同学每天投入10小时\n投入从6小时增加到10小时",
          "乙同学每天投入6小时 · 乙同学每天投入10小时\n跟随同伴一起延长工作时间",
          "甲同学每天投入10小时 · 评比名额只有2个\n名次仍然回到原来的位置")


def stacked_vertical_story():
    def obj(id_,label,kind="person",state="neutral"):
        return dict(id=id_,label=label,kind=kind,state=state)
    scenes=[]
    for index,caption in enumerate(CAPTIONS):
        scenes.append(dict(title=f"第{index+1}步：名额固定下的加码",objects=[
            obj("a","甲同学每天投入6小时"),obj("b","乙同学每天投入6小时"),
            obj("c","甲同学每天投入10小时","person","selected"),obj("d","乙同学每天投入10小时","person","selected"),
            obj("e","评比名额只有2个","container"),obj("f","全组共6人一起竞争","group")],
            connections=[
                dict(**{"from":"a","to":"c"},label=caption.split("\n")[1],relation="sequence"),
                dict(**{"from":"b","to":"d"},label="跟随同伴一起延长工作时间",relation="association"),
                dict(**{"from":"c","to":"e"},label="名次仍然回到原来的位置",relation="comparison"),
                dict(**{"from":"e","to":"f"},label="名额固定而竞争加剧",relation="comparison")]))
    return dict(kind="story",origin="teaching",title="投入加码与名额固定",
        takeaway="名额固定时，人人延长工时只会抬高投入，位次回到原样。",
        alt="三列人物、名额与竞争者的示意图，每列含两条竖直关系说明",refs=[],
        presentation=dict(version=1,focus="process",numeric_role="relative",layout="story",interaction="none"),
        payload=dict(layout="scenes",ordered=False,scenes=scenes))


class StoryCaptionBandTests(unittest.TestCase):
    def setUp(self):
        self.tmp=Path(tempfile.mkdtemp())
        self.qa=Path(__file__).parents[2]/"term_explainer"/"figure_qa"

    def tearDown(self):
        shutil.rmtree(self.tmp,ignore_errors=True)

    def test_many_vertical_links_with_multiline_captions_audit_clean(self):
        # Three desktop columns leave ~15 characters per caption line, so the
        # captions below cannot fit on one line and the band must grow with them.
        columns=int((760/3-24-26)/13)
        self.assertGreater(len(CAPTIONS[0].split("\n")[0]),columns)
        visual=stacked_vertical_story();before=json.dumps(visual,sort_keys=True,ensure_ascii=False)
        assets=render_visual(visual,self.tmp/"figure",run_external_qa=True,qa_dir=self.qa,font_path="C:/Windows/Fonts/msyh.ttc")
        self.assertEqual(json.dumps(visual,sort_keys=True,ensure_ascii=False),before)
        for path in (assets.desktop,assets.mobile):
            self.assertTrue(Path(path).is_file(),path)
        svg=Path(assets.desktop).read_text(encoding="utf-8")
        for text in ("甲同学每天投入6小时","甲同学每天投入10小时","投入从6小时增加到10小时","名额固定而竞争加剧"):
            self.assertIn(text,svg,text)
        audit=json.loads(Path(assets.audit).read_text(encoding="utf-8"))
        self.assertTrue(audit["external_qa"])
        self.assertTrue(all(item["exit_code"]==0 for item in audit["external_qa"]),audit["external_qa"])
