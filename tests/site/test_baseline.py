from __future__ import annotations

import hashlib
import importlib.util
import gc
import re
import unittest
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "site" / "dist"
EXPECTED_PAGES = {
    Path("index.html"),
    Path("terms/variable.html"),
    Path("terms/data-cleaning.html"),
    Path("terms/t-test.html"),
    Path("sources.html"),
}


def load_build_module():
    module_path = ROOT / "site" / "build.py"
    spec = importlib.util.spec_from_file_location("psych_stats_site_build", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hash_dist() -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in DIST.rglob("*") if p.is_file()):
        digest.update(path.relative_to(DIST).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


class BaselineBuildTests(unittest.TestCase):
    def test_check_mode_returns_zero_without_mutating_dist(self):
        before = hash_dist()
        build = load_build_module()

        result = build.main(["--check"])

        self.assertEqual(result, 0)
        self.assertEqual(hash_dist(), before)

    def test_current_dist_contains_expected_pages_without_placeholders(self):
        pages = {path.relative_to(DIST) for path in DIST.rglob("*.html")}
        self.assertTrue(EXPECTED_PAGES.issubset(pages))
        for name in EXPECTED_PAGES:
            html = (DIST / name).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\{\{[A-Z0-9_]+\}\}", html), str(name))

    def test_check_mode_closes_every_opened_file(self):
        build = load_build_module()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            build.main(["--check"])
            gc.collect()

        leaked = [item for item in caught if item.category is ResourceWarning]
        self.assertEqual(leaked, [])


if __name__ == "__main__":
    unittest.main()
