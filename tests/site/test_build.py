import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sitegen import build


def relation_map(**changes):
    value = {
        "prerequisites": [],
        "components": [],
        "contrasts": [],
        "used_in": [],
        "next": [],
    }
    value.update(changes)
    return value


def term(term_id, *, status="public", relations=None, **changes):
    value = {
        "id": term_id,
        "zh": term_id,
        "en": term_id.title(),
        "aliases": [],
        "type": "concept",
        "level": "basic",
        "topic": "foundations",
        "status": status,
        "summary": f"{term_id} summary",
        "relations": relations or relation_map(),
        "real_question": f"什么时候需要 {term_id}？",
        "operational_definition": f"{term_id} 的操作性定义。",
        "plain_explanation": f"{term_id} 的通俗解释。",
        "problems_solved": ["解释研究问题"],
        "not_for": ["不能替代理论判断"],
        "decision_clues": ["根据研究设计判断"],
        "sections": [],
        "formula": {"latex": "", "note": "", "verified": False},
        "quiz": {
            "question": f"哪项属于 {term_id}？",
            "options": ["正确选项", "错误选项"],
            "answer": 0,
            "explanation": "第一项正确。",
            "option_explanations": ["第一项正确，因为它符合定义。", "第二项错误，因为它不符合定义。"],
        },
        "sources": [{"kind": "textbook", "title": "统计教材"}],
        "r_practice": None,
        "verified": status == "public",
    }
    value.update(changes)
    return value


def metadata(value):
    return {
        key: value[key]
        for key in (
            "id", "zh", "en", "aliases", "type", "level", "topic", "status",
            "summary", "relations",
        )
    }


class SiteBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.content = self.root / "content"
        self.output = self.root / "dist"
        (self.content / "terms").mkdir(parents=True)
        (self.content / "drafts").mkdir()

        self.alpha = term("alpha", relations=relation_map(next=["beta"]))
        self.beta = term("beta", relations=relation_map(contrasts=["alpha"]))
        self.draft = term(
            "gamma",
            status="draft",
            relations=relation_map(next=["alpha"]),
            verified=False,
        )
        self.write_inputs()
        self.paths = patch.object(build, "CONTENT_DIR", self.content)
        self.paths.start()
        self.addCleanup(self.paths.stop)

    def write_json(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def write_inputs(self):
        self.write_json(
            self.content / "registry.json",
            {
                "schema_version": "2.0",
                "terms": [metadata(self.alpha), metadata(self.beta), metadata(self.draft)],
            },
        )
        self.write_json(self.content / "terms" / "alpha.json", self.alpha)
        self.write_json(self.content / "terms" / "beta.json", self.beta)
        for value in (self.alpha, self.beta, self.draft):
            preview_value = dict(value)
            preview_value["status"] = "draft"
            self.write_json(self.content / "drafts" / f"{value['id']}.json", preview_value)
        self.write_json(self.content / "datasets.json", {"datasets": []})
        self.write_json(
            self.content / "topics.json",
            {"topics": [{"id": "foundations", "zh": "基础", "description": "基础主题"}]},
        )
        self.write_json(
            self.content / "paths.json",
            {"paths": [{"id": "start", "title": "入门", "description": "", "steps": []}]},
        )
        self.write_json(
            self.content / "source_policy.json",
            {
                "title": "来源说明",
                "version": "test",
                "sources": [],
                "review_rules": [],
                "boundaries": [],
            },
        )

    def test_public_excludes_drafts_and_asset_counts_match_html(self):
        report = build.build_site("public", self.output)
        self.assertEqual(report.term_count, 2)
        self.assertTrue((self.output / "terms" / "alpha.html").exists())
        self.assertFalse((self.output / "terms" / "gamma.html").exists())
        search = json.loads((self.output / "assets" / "data" / "search-index.json").read_text(encoding="utf-8"))
        graph = json.loads((self.output / "assets" / "data" / "graph.json").read_text(encoding="utf-8"))
        quizzes = json.loads((self.output / "assets" / "data" / "quiz-bank.json").read_text(encoding="utf-8"))
        self.assertEqual(len(search), report.term_count)
        self.assertEqual(len(graph["nodes"]), report.term_count)
        self.assertEqual(len(quizzes), report.question_count)
        disk_report = json.loads((self.output / "build_report.json").read_text(encoding="utf-8"))
        self.assertEqual(disk_report["input_hash"], report.input_hash)

    def test_preview_includes_all_content_without_draft_labels(self):
        report = build.build_site("preview", self.output)
        self.assertEqual(report.term_count, 3)
        html = (self.output / "terms" / "gamma.html").read_text(encoding="utf-8")
        self.assertNotIn("草稿预览", html)
        self.assertNotIn('class="draft-badge"', html)

    def test_site_identity_and_reviewed_presentation_are_consistent(self):
        build.build_site("preview", self.output)
        for path in self.output.rglob("*.html"):
            with self.subTest(page=path.name):
                html = path.read_text(encoding="utf-8")
                self.assertIn('心理统计学术语图鉴</span></a>', html)
                self.assertNotIn('class="draft-badge"', html)
                self.assertNotIn("草稿预览", html)
                self.assertNotIn("待人工审核", html)
        home = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertIn('<h1>心理统计学术语图鉴</h1>', home)
        self.assertIn('<title>心理统计学术语图鉴-轻松掌握心理统计和r语言数据分析</title>', home)
        detail = (self.output / "terms" / "gamma.html").read_text(encoding="utf-8")
        self.assertIn('<title>心理统计学术语图鉴-轻松掌握心理统计和r语言数据分析</title>', detail)

    def test_public_build_rejects_missing_or_unpublished_relation_target(self):
        broken = dict(self.alpha)
        broken["relations"] = relation_map(prerequisites=["missing"])
        self.write_json(self.content / "terms" / "alpha.json", broken)
        with self.assertRaisesRegex(build.BuildError, "missing"):
            build.build_site("public", self.output)

    def test_public_build_rejects_unverified_formula(self):
        broken = dict(self.alpha)
        broken["formula"] = {"latex": "x=1", "note": "", "verified": False}
        self.write_json(self.content / "terms" / "alpha.json", broken)
        with self.assertRaisesRegex(build.BuildError, "formula"):
            build.build_site("public", self.output)

    def test_public_build_rejects_unverified_r_practice(self):
        broken = dict(self.alpha)
        broken["r_practice"] = {"verified": False, "example_code": "mean(1:3)"}
        self.write_json(self.content / "terms" / "alpha.json", broken)
        with self.assertRaisesRegex(build.BuildError, "r_practice"):
            build.build_site("public", self.output)

    def test_public_build_rejects_missing_option_explanations(self):
        broken = dict(self.alpha)
        broken["quiz"] = {**broken["quiz"], "option_explanations": ["只解释第一项"]}
        self.write_json(self.content / "terms" / "alpha.json", broken)
        with self.assertRaisesRegex(build.BuildError, "option_explanations"):
            build.build_site("public", self.output)

    def test_rendering_escapes_user_authored_html(self):
        unsafe = dict(self.alpha)
        unsafe["plain_explanation"] = "<script>alert(1)</script>"
        self.write_json(self.content / "terms" / "alpha.json", unsafe)
        build.build_site("public", self.output)
        html = (self.output / "terms" / "alpha.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)


if __name__ == "__main__":
    unittest.main()
