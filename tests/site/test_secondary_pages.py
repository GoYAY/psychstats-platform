import json
import tempfile
import unittest
from pathlib import Path

from sitegen.build import build_site


ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "site" / "content"


class SecondaryPageTests(unittest.TestCase):
    def test_learning_paths_are_exactly_four_and_reference_registry_terms(self):
        paths = json.loads((CONTENT / "paths.json").read_text(encoding="utf-8"))["paths"]
        registry = json.loads((CONTENT / "registry.json").read_text(encoding="utf-8"))["terms"]
        ids = {item["id"] for item in registry}
        self.assertEqual(len(paths), 4)
        for path in paths:
            self.assertTrue(path["steps"])
            for step in path["steps"]:
                self.assertTrue(set(step["terms"]).issubset(ids))

    def test_preview_build_emits_topic_path_dataset_and_source_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            build_site("preview", output)
            self.assertTrue(list((output / "topics").glob("*.html")))
            for name in ("paths.html", "datasets.html", "sources.html"):
                self.assertTrue((output / name).exists(), name)
            sources = (output / "sources.html").read_text(encoding="utf-8")
            for forbidden in ("page_print", "page_pdf", "PDF 页"):
                self.assertNotIn(forbidden, sources)

    def test_dataset_download_links_resolve_to_build_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            build_site("preview", output)
            payload = json.loads((CONTENT / "datasets.json").read_text(encoding="utf-8"))
            for dataset in payload["datasets"]:
                if dataset.get("download"):
                    self.assertTrue((output / dataset["download"]).is_file(), dataset["id"])
                else:
                    self.assertEqual(dataset["status"], "planned")


if __name__ == "__main__":
    unittest.main()
