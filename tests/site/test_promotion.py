import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import make_term_drafts, promote_term
from sitegen.model import TermMeta


def relations(prerequisites=None):
    return {
        "prerequisites": prerequisites or [],
        "components": [],
        "contrasts": [],
        "used_in": [],
        "next": [],
    }


def draft(term_id="mean", *, term_type="concept", prerequisites=None, **changes):
    value = {
        "id": term_id,
        "zh": "平均数",
        "en": "Mean",
        "aliases": [],
        "type": term_type,
        "level": "basic",
        "topic": "foundations",
        "status": "draft",
        "summary": "描述一组数值的典型水平。",
        "relations": relations(prerequisites),
        "real_question": "怎样用一个数概括典型水平？",
        "operational_definition": "全部观测之和除以有效观测数。",
        "plain_explanation": "把总量平均分给每个观测。",
        "problems_solved": ["概括中心位置"],
        "not_for": ["不能单独概括严重偏态分布"],
        "decision_clues": ["变量达到等距尺度"],
        "quiz": {
            "question": "哪项正确？",
            "options": ["使用全部观测", "不受极端值影响"],
            "answer": 0,
            "explanation": "平均数使用全部有效观测。",
            "option_explanations": ["正确。平均数使用全部有效观测。", "错误。平均数会受极端值影响。"],
        },
        "sources": [
            {
                "kind": "textbook",
                "title": "现代心理与教育统计学",
                "page_print": 42,
                "page_pdf": 55,
                "chunk_id": 12,
            }
        ],
        "formula": {"latex": "", "note": "", "verified": False},
        "verified": True,
        "r_practice": None,
    }
    value.update(changes)
    return value


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.drafts = self.root / "drafts"
        self.terms = self.root / "terms"
        self.drafts.mkdir()
        self.terms.mkdir()
        self.registry = self.root / "registry.json"
        self.aggregate = self.root / "terms.json"
        self.patch_paths = patch.multiple(
            promote_term,
            DRAFTS=self.drafts,
            TERM_DIR=self.terms,
            REGISTRY=self.registry,
            TERMS=self.aggregate,
        )
        self.patch_paths.start()
        self.addCleanup(self.patch_paths.stop)

    def write_registry(self, *entries):
        payload = {"schema_version": "2.0", "terms": []}
        for item in entries:
            payload["terms"].append(
                {
                    key: item[key]
                    for key in (
                        "id", "zh", "en", "aliases", "type", "level", "topic",
                        "status", "summary", "relations",
                    )
                }
            )
        self.registry.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def write_draft(self, item):
        (self.drafts / f"{item['id']}.json").write_text(
            json.dumps(item, ensure_ascii=False), encoding="utf-8"
        )

    def assert_rejected(self, item, expected):
        self.write_registry(item)
        self.write_draft(item)
        result = promote_term.promote(item["id"], preview=True)
        self.assertFalse(result.ok)
        self.assertTrue(any(expected in error for error in result.errors), result.errors)

    def test_rejects_unreviewed_content(self):
        self.assert_rejected(draft(verified=False), "verified")

    def test_rejects_unreviewed_formula(self):
        self.assert_rejected(
            draft(formula={"latex": "M=\\sum X/n", "note": "", "verified": False}),
            "formula",
        )

    def test_rejects_unverified_r_practice(self):
        self.assert_rejected(
            draft(
                term_type="method",
                r_practice={"verified": False, "example_code": "mean(1:3)"},
            ),
            "r_practice",
        )

    def test_rejects_empty_sources(self):
        self.assert_rejected(draft(sources=[]), "sources")

    def test_rejects_out_of_range_quiz_answer(self):
        item = draft()
        item["quiz"]["answer"] = 2
        self.assert_rejected(item, "quiz.answer")

    def test_rejects_missing_per_option_explanation(self):
        item = draft()
        item["quiz"]["option_explanations"] = ["仅有一个解析"]
        self.assert_rejected(item, "option_explanations")

    def test_rejects_unpublished_prerequisite(self):
        prerequisite = draft("variable", zh="变量", en="Variable")
        item = draft("mean", prerequisites=["variable"])
        self.write_registry(prerequisite, item)
        self.write_draft(item)
        result = promote_term.promote("mean", preview=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("variable" in error and "not public" in error for error in result.errors))

    def test_valid_concept_and_analysis_term_pass_preview(self):
        concept = draft("mean")
        analysis = draft(
            "t-test",
            zh="t 检验",
            en="t-test",
            term_type="method",
            r_practice={"verified": True, "example_code": "t.test(extra ~ group, sleep)"},
        )
        self.write_registry(concept, analysis)
        self.write_draft(concept)
        self.write_draft(analysis)
        self.assertTrue(promote_term.promote("mean", preview=True).ok)
        self.assertTrue(promote_term.promote("t-test", preview=True).ok)
        self.assertEqual(list(self.terms.iterdir()), [])

    def test_promotion_writes_only_requested_term_and_sanitized_source_catalog(self):
        item = draft("mean")
        other = draft("median", zh="中位数", en="Median")
        self.write_registry(item, other)
        self.write_draft(item)
        self.write_draft(other)

        result = promote_term.promote("mean")

        self.assertTrue(result.ok)
        self.assertTrue(result.written)
        self.assertTrue((self.terms / "mean.json").exists())
        self.assertFalse((self.terms / "median.json").exists())
        aggregate = json.loads(self.aggregate.read_text(encoding="utf-8"))
        self.assertEqual([term["id"] for term in aggregate["terms"]], ["mean"])
        catalog_text = json.dumps(aggregate["source_catalog"], ensure_ascii=False)
        for forbidden in ("page_print", "page_pdf", "chunk_id"):
            self.assertNotIn(forbidden, catalog_text)

    def test_v2_draft_skeleton_uses_registry_metadata_and_stays_unverified(self):
        metadata = TermMeta(
            id="data-cleaning",
            zh="数据清理",
            en="Data Cleaning",
            aliases=(),
            type="workflow",
            level="basic",
            topic="data-preparation",
            status="draft",
            summary="形成可分析数据的工作流程。",
            relations={key: tuple(value) for key, value in relations().items()},
        )
        result = make_term_drafts.make_draft(metadata, candidate_evidence={"textbook": []})
        self.assertEqual(result["id"], "data-cleaning")
        self.assertEqual(result["real_question"], "")
        self.assertFalse(result["verified"])
        self.assertIsInstance(result["r_practice"], dict)
        self.assertFalse(result["r_practice"]["verified"])
        self.assertEqual(result["candidate_evidence"], {"textbook": []})


if __name__ == "__main__":
    unittest.main()
