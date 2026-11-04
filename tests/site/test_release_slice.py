import json
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from sitegen.model import load_registry, load_term, validate_term


ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "site" / "content"
REQUIRED = {
    "data-cleaning", "outlier", "missing-data", "variable", "standard-score",
    "descriptive-statistics", "sampling-distribution", "standard-error",
    "null-hypothesis", "p-value", "confidence-interval", "effect-size",
    "t-test", "anova", "correlation-coefficient",
}
ANALYSIS = {"data-cleaning", "outlier", "missing-data", "standard-score", "descriptive-statistics", "standard-error", "p-value", "confidence-interval", "effect-size", "t-test", "anova", "correlation-coefficient"}


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag in {"a", "link", "script"}:
            attributes = dict(attrs)
            target = attributes.get("href") or attributes.get("src")
            if target:
                self.links.append(target)


class ReleaseSliceTests(unittest.TestCase):
    def test_required_public_terms_form_closed_prerequisite_graph(self):
        registry = load_registry(CONTENT / "registry.json")
        files = {path.stem: path for path in (CONTENT / "terms").glob("*.json")}
        self.assertTrue(REQUIRED.issubset(files), sorted(REQUIRED - set(files)))
        published = {term_id: load_term(path) for term_id, path in files.items()}
        for term_id in REQUIRED:
            term = published[term_id]
            self.assertEqual(term.status, "public")
            self.assertEqual(registry[term_id].status, "public")
            self.assertEqual(validate_term(term), [], term_id)
            self.assertTrue(set(term.relations["prerequisites"]).issubset(published), term_id)
            self.assertEqual(len(term.quiz["options"]), 4)
            self.assertEqual(len(term.quiz["option_explanations"]), 4)
            self.assertTrue(all(term.quiz["option_explanations"]))
            self.assertTrue(term.sources)
        self.assertEqual({published[item].type for item in REQUIRED}, {"concept", "method", "indicator", "workflow"})

    def test_real_questions_ask_about_research_needs_without_answering_a_definition_quiz(self):
        terms = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in (CONTENT / "terms").glob("*.json")}
        for slug in ("standard-error", "null-hypothesis", "p-value", "confidence-interval", "t-test", "anova"):
            question = terms[slug]["real_question"]
            self.assertNotIn("是不是", question, slug)
            self.assertNotIn("t 检验", question, slug)
            self.assertNotIn("p=", question, slug)
            self.assertNotIn("置信区间", question, slug)

    def test_analysis_pages_have_validated_r_practice(self):
        report = json.loads((ROOT / "logs" / "r_validation.json").read_text(encoding="utf-8"))
        verified = {row["term_id"] for row in report["results"] if row["verified"]}
        for term_id in ANALYSIS:
            value = json.loads((CONTENT / "terms" / f"{term_id}.json").read_text(encoding="utf-8"))
            self.assertIn(term_id, verified)
            self.assertTrue(value["r_practice"]["verified"])
            self.assertTrue(value["r_practice"]["example_code"])
            self.assertTrue(value["r_practice"]["your_data_code"])

    def test_public_html_has_no_broken_local_links(self):
        dist = (ROOT / "site" / "dist").resolve()
        for page in dist.rglob("*.html"):
            collector = LinkCollector()
            collector.feed(page.read_text(encoding="utf-8"))
            for href in collector.links:
                parsed = urlsplit(href)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                target = (page.parent / unquote(parsed.path)).resolve()
                self.assertTrue(target.is_relative_to(dist), f"{page}: unsafe link {href}")
                self.assertTrue(target.is_file(), f"{page}: broken link {href}")


if __name__ == "__main__":
    unittest.main()
