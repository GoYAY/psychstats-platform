import json
import tempfile
import unittest
from pathlib import Path

from sitegen.model import load_registry, load_term, validate_registry, validate_term


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def meta(term_id="mean", **changes):
    value = {
        "id": term_id,
        "zh": "平均数",
        "en": "Mean",
        "aliases": ["算术平均数"],
        "type": "concept",
        "level": "basic",
        "topic": "descriptive-statistics",
        "status": "draft",
        "summary": "描述一组数值的典型水平。",
        "relations": {
            "prerequisites": [],
            "components": [],
            "contrasts": [],
            "used_in": [],
            "next": [],
        },
    }
    value.update(changes)
    return value


def full_term(**changes):
    value = meta(**{key: changes.pop(key) for key in list(changes) if key in meta()})
    value.update(
        {
            "real_question": "怎样用一个数概括这组得分的典型水平？",
            "operational_definition": "全部观测值之和除以有效观测数。",
            "plain_explanation": "把总量平均分给每个观测。",
            "problems_solved": ["概括连续变量的中心位置"],
            "not_for": ["严重偏态分布的唯一概括"],
            "decision_clues": ["变量至少达到等距尺度"],
            "quiz": {
                "question": "哪项最准确？",
                "options": ["平均数使用全部观测", "平均数不受极端值影响"],
                "answer": 0,
                "explanation": "平均数使用全部有效观测。",
            },
            "sources": [{"kind": "textbook", "title": "现代心理与教育统计学"}],
        }
    )
    value.update(changes)
    return value


class TermModelTests(unittest.TestCase):
    def write_json(self, payload):
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name) / "data.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        self.addCleanup(temp.cleanup)
        return path

    def test_loads_and_validates_a_complete_term(self):
        term = load_term(self.write_json(full_term()))
        self.assertEqual(term.id, "mean")
        self.assertEqual(validate_term(term), [])

    def test_term_requires_real_question(self):
        term = load_term(self.write_json(full_term(real_question="")))
        self.assertTrue(any("real_question" in error for error in validate_term(term)))

    def test_term_rejects_unknown_type_and_level(self):
        term = load_term(self.write_json(full_term(type="procedure", level="expert")))
        errors = validate_term(term)
        self.assertTrue(any("type" in error and "procedure" in error for error in errors))
        self.assertTrue(any("level" in error and "expert" in error for error in errors))

    def test_registry_reports_zh_en_and_alias_conflicts_with_both_ids(self):
        entries = [
            meta("mean"),
            meta(
                "arithmetic-mean",
                zh="平均数",
                en="MEAN",
                aliases=["算术平均数"],
            ),
        ]
        registry = load_registry(self.write_json({"schema_version": "2.0", "terms": entries}))
        errors = validate_registry(registry)
        for field in ("zh", "en", "alias"):
            matches = [error for error in errors if field in error]
            self.assertTrue(matches, field)
            self.assertTrue(all("mean" in error and "arithmetic-mean" in error for error in matches))

    def test_project_registry_migrates_candidates_and_bridge_terms_as_drafts(self):
        registry = load_registry(PROJECT_ROOT / "site" / "content" / "registry.json")
        legacy = json.loads(
            (PROJECT_ROOT / "site" / "content" / "terms_draft.json").read_text(
                encoding="utf-8"
            )
        )
        legacy_ids = {item["slug"] for item in legacy["terms"]}
        bridge_ids = {
            "variable", "standard-score", "null-hypothesis",
            "data-cleaning",
            "exploratory-data-analysis",
            "descriptive-statistics",
            "measurement-scales",
            "population-and-sample",
            "parameter-and-statistic",
            "central-tendency-and-dispersion",
            "normal-distribution",
            "sampling-distribution",
            "null-and-alternative-hypotheses",
            "type-i-and-type-ii-errors",
            "statistical-assumptions",
            "normality",
            "linearity",
            "independence",
            "covariance",
            "correlation-coefficient",
            "simple-linear-regression",
            "influential-point",
            "sum-of-squares",
            "mean-square",
            "f-statistic",
            "repeated-measures",
            "measurement-error",
            "communality",
            "kmo",
            "bartlett-test",
            "pca",
            "factor-extraction",
            "direct-effect",
            "total-effect",
            "conditional-effect",
            "nested-data",
            "level-one",
            "level-two",
            "reml",
            "time-coding",
        }
        self.assertEqual(len(legacy_ids), 86)
        depth_ids = {
            'reliability', 'internal-consistency', 'cronbach-alpha', 'mcdonald-omega',
            'validity', 'measurement-invariance', 'parallel-analysis', 'polychoric-correlation',
            'spearman-correlation', 'partial-correlation', 'sample-size-planning', 'sesoi',
            'equivalence-testing', 'reverse-scoring', 'scale-scoring', 'heteroscedasticity',
            'robust-standard-errors', 'cross-validation', 'welch-anova', 'planned-contrast',
            'confounding', 'sensitivity-analysis', 'fisher-exact-test',
        }
        supporting_ids = {'intercept', 'path-coefficient', 'model-fit', 'causal-relationship'}
        supporting_ids |= {'histogram','qq-plot','skewness','extreme-value','quantile','probability-density','continuous-variable','vector','matrix','matrix-transpose','covariance-matrix','likelihood','convergence','overfitting'}
        supporting_ids |= {'data-rank', 'matrix-rank', 'linear-dependence', 'design-matrix',
                           'matrix-inverse', 'determinant', 'wilcoxon-rank-sum', 'wilcoxon-signed-rank'}
        mixture_ids = {"latent-profile-analysis", "latent-class-analysis", "ancova", "mancova"}
        self.assertEqual(set(registry), legacy_ids | bridge_ids | depth_ids | supporting_ids | mixture_ids)
        public_ids = {
            term["id"]
            for term in json.loads((PROJECT_ROOT / "site" / "content" / "terms.json").read_text(encoding="utf-8"))["terms"]
        }
        self.assertEqual(len(public_ids), 15)
        self.assertTrue(all(term.status == ("public" if term.id in public_ids else "draft") for term in registry.values()))
        self.assertEqual(validate_registry(registry), [])

    def test_project_topics_use_stable_unique_ids(self):
        payload = json.loads(
            (PROJECT_ROOT / "site" / "content" / "topics.json").read_text(
                encoding="utf-8"
            )
        )
        ids = [topic["id"] for topic in payload["topics"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 8)


if __name__ == "__main__":
    unittest.main()
