import unittest

from sitegen.graph import build_backlinks, public_closure
from sitegen.model import TermMeta, validate_registry


def term(term_id, *, status="draft", **relations):
    relation_map = {
        "prerequisites": [],
        "components": [],
        "contrasts": [],
        "used_in": [],
        "next": [],
    }
    relation_map.update(relations)
    return TermMeta(
        id=term_id,
        zh=term_id,
        en=term_id.title(),
        aliases=(),
        type="concept",
        level="basic",
        topic="foundations",
        status=status,
        summary=f"{term_id} summary",
        relations=relation_map,
    )


class TermGraphTests(unittest.TestCase):
    def test_general_relation_cycles_are_allowed_and_backlinked(self):
        registry = {
            "a": term("a", contrasts=["b"]),
            "b": term("b", contrasts=["a"]),
        }
        self.assertEqual(validate_registry(registry), [])
        backlinks = build_backlinks(registry)
        self.assertEqual(backlinks["a"]["contrasts"], ["b"])
        self.assertEqual(backlinks["b"]["contrasts"], ["a"])

    def test_prerequisite_cycle_is_rejected(self):
        registry = {
            "a": term("a", prerequisites=["b"]),
            "b": term("b", prerequisites=["a"]),
        }
        errors = validate_registry(registry)
        self.assertTrue(any("prerequisite cycle" in error and "a" in error and "b" in error for error in errors))

    def test_missing_relation_target_is_rejected(self):
        errors = validate_registry({"a": term("a", next=["missing"])})
        self.assertTrue(any("a" in error and "missing" in error for error in errors))

    def test_public_term_cannot_depend_on_draft_prerequisite(self):
        registry = {
            "public": term("public", status="public", prerequisites=["draft"]),
            "draft": term("draft"),
        }
        errors = validate_registry(registry)
        self.assertTrue(any("public" in error and "draft" in error and "not public" in error for error in errors))

    def test_public_closure_adds_transitive_prerequisites(self):
        registry = {
            "anova": term("anova", prerequisites=["f-statistic"]),
            "f-statistic": term("f-statistic", prerequisites=["mean-square"]),
            "mean-square": term("mean-square"),
        }
        self.assertEqual(
            public_closure(registry, {"anova"}),
            {"anova", "f-statistic", "mean-square"},
        )

    def test_isolated_term_is_reported(self):
        registry = {
            "a": term("a", next=["b"]),
            "b": term("b"),
            "lonely": term("lonely"),
        }
        errors = validate_registry(registry)
        self.assertTrue(any("isolated" in error and "lonely" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
