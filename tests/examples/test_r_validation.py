import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import validate_r_examples as module


class RValidationTests(unittest.TestCase):
    def test_missing_rscript_fails(self):
        with patch.object(module, "find_rscript", return_value=None):
            result = module.validate_example("data-cleaning")
        self.assertFalse(result.verified)
        self.assertIn("Rscript", " ".join(result.errors))

    def test_missing_package_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "needs_package.R"
            script.write_text("library(packageThatDoesNotExist)\n", encoding="ascii")
            spec = {"script": str(script), "required_packages": ["packageThatDoesNotExist"], "metrics": {}}
            with patch.object(module, "SPECS", {"needs-package": spec}):
                result = module.validate_example("needs-package")
        self.assertFalse(result.verified)
        self.assertIn("packageThatDoesNotExist", " ".join(result.errors))

    def test_nonzero_exit_and_missing_metrics_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            failed = root / "failed.R"
            failed.write_text("stop('bad model')\n", encoding="ascii")
            no_metrics = root / "no_metrics.R"
            no_metrics.write_text("cat('done')\n", encoding="ascii")
            specs = {
                "failed": {"script": str(failed), "required_packages": [], "metrics": {}},
                "no-metrics": {"script": str(no_metrics), "required_packages": [], "metrics": {"estimate": {"min": 0}}},
            }
            with patch.object(module, "SPECS", specs):
                self.assertFalse(module.validate_example("failed").verified)
                result = module.validate_example("no-metrics")
                self.assertFalse(result.verified)
                self.assertIn("estimate", " ".join(result.errors))

    def test_nonconvergence_wrong_direction_and_out_of_tolerance_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "bad.R"
            script.write_text(
                "write.table(data.frame(metric=c('converged','effect'),value=c(0,-2)),"
                "commandArgs(TRUE)[1],row.names=FALSE,sep='\\t',quote=FALSE)\n",
                encoding="ascii",
            )
            spec = {"script": str(script), "required_packages": [], "metrics": {"effect": {"min": 0, "target": 1, "tolerance": 0.2}}, "requires_convergence": True}
            with patch.object(module, "SPECS", {"bad": spec}):
                result = module.validate_example("bad")
        self.assertFalse(result.verified)
        joined = " ".join(result.errors)
        self.assertIn("converged", joined)
        self.assertIn("effect", joined)


if __name__ == "__main__":
    unittest.main()
