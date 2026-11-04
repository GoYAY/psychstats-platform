import unittest
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from tools.author_release_slice import make_example_code
from tools import author_release_slice


ROOT = Path(__file__).resolve().parents[2]


class AuthorReleaseSliceTests(unittest.TestCase):
    def test_prepare_keeps_output_guidance_separate_from_plain_explanation(self):
        with tempfile.TemporaryDirectory() as temporary:
            content = Path(temporary)
            (content / "drafts").mkdir()
            for name in ("registry.json", "release_slice_seed.json"):
                shutil.copy2(ROOT / "site/content" / name, content / name)
            seed_path = content / "release_slice_seed.json"
            seed = json.loads(seed_path.read_text(encoding="utf-8"))
            seed["terms"]["p-value"]["output_interpretation"] = "阅读 p_value、t_statistic 与 df。"
            seed["terms"]["p-value"]["plain_example"] = "例如，比较两组学生的学习进步。"
            seed_path.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")
            for slug in seed["terms"]:
                shutil.copy2(ROOT / "site/content/drafts" / f"{slug}.json", content / "drafts" / f"{slug}.json")
            with patch.object(author_release_slice, "CONTENT", content):
                author_release_slice.prepare()
            value = json.loads((content / "drafts/p-value.json").read_text(encoding="utf-8"))
            self.assertEqual(value["r_practice"]["interpretation"], "阅读 p_value、t_statistic 与 df。")
            self.assertEqual(value["plain_example"], "例如，比较两组学生的学习进步。")
            self.assertNotEqual(value["r_practice"]["interpretation"], value["plain_explanation"])

    def test_example_code_is_self_contained(self):
        code = make_example_code("t-test", ROOT)
        self.assertIn('read.csv("learning_experiment.csv"', code)
        self.assertIn("print(c(", code)
        self.assertNotIn("source(", code)
        self.assertNotIn("read_data(", code)
        self.assertNotIn("emit(", code)

    def test_simulation_example_needs_no_csv(self):
        code = make_example_code("sampling-distribution", ROOT)
        self.assertIn("replicate(2000", code)
        self.assertNotIn("read.csv(", code)

    def test_all_published_example_code_runs_without_project_helpers(self):
        report = json.loads((ROOT / "logs/r_validation.json").read_text(encoding="utf-8"))
        seed = json.loads((ROOT / "site/content/release_slice_seed.json").read_text(encoding="utf-8"))["terms"]
        passed = {row["term_id"] for row in report["results"] if row["verified"]}
        rscript = next(row["rscript"] for row in report["results"] if row["verified"])
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for csv in (ROOT / "examples/data").glob("*.csv"):
                shutil.copy2(csv, folder / csv.name)
            for slug in seed.keys() & passed:
                script = folder / f"{slug}.R"
                script.write_text(make_example_code(slug), encoding="utf-8")
                result = subprocess.run([rscript, str(script)], cwd=folder, text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, f"{slug}: {result.stdout}\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
