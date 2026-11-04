import csv
import json
import tempfile
import unittest
from pathlib import Path

from examples.data.validate import DATA_DIR, TRUTH_PATH, validate_dataset_contract


EXPECTED = {
    "cross_sectional_survey",
    "learning_experiment",
    "scale_items",
    "nested_classrooms",
    "longitudinal_growth",
    "messy_survey",
}


class DatasetContractTests(unittest.TestCase):
    def test_all_six_generated_datasets_pass_contracts(self):
        truth = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
        self.assertEqual(set(truth["datasets"]), EXPECTED)
        for dataset_id in EXPECTED:
            self.assertEqual(validate_dataset_contract(dataset_id), [], dataset_id)

    def mutated_copy(self, dataset_id, mutate_rows=None, mutate_truth=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        truth = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
        source = DATA_DIR / truth["datasets"][dataset_id]["file"]
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if mutate_rows:
            rows = mutate_rows(rows)
        target = root / source.name
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        if mutate_truth:
            mutate_truth(truth)
        truth_path = root / "truth.json"
        truth_path.write_text(json.dumps(truth, ensure_ascii=False), encoding="utf-8")
        return root, truth_path

    def test_missing_column_names_dataset_and_column(self):
        root, truth = self.mutated_copy(
            "cross_sectional_survey",
            lambda rows: [{k: v for k, v in row.items() if k != "stress"} for row in rows],
        )
        errors = validate_dataset_contract("cross_sectional_survey", root, truth)
        self.assertTrue(any("cross_sectional_survey" in error and "stress" in error for error in errors))

    def test_wrong_type_and_unknown_level_are_rejected(self):
        def mutate(rows):
            rows[0]["age"] = "not-a-number"
            rows[1]["gender"] = "unknown-level"
            return rows
        root, truth = self.mutated_copy("cross_sectional_survey", mutate)
        errors = validate_dataset_contract("cross_sectional_survey", root, truth)
        self.assertTrue(any("age" in error and "cross_sectional_survey" in error for error in errors))
        self.assertTrue(any("gender" in error and "unknown-level" in error for error in errors))

    def test_generation_parameter_drift_is_rejected(self):
        root, truth = self.mutated_copy(
            "learning_experiment",
            mutate_truth=lambda value: value["datasets"]["learning_experiment"].update(seed=999),
        )
        errors = validate_dataset_contract("learning_experiment", root, truth)
        self.assertTrue(any("learning_experiment" in error and "seed" in error for error in errors))

    def test_dirty_dataset_declares_its_injected_problems(self):
        truth = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
        issues = set(truth["datasets"]["messy_survey"]["intentional_issues"])
        self.assertTrue({"missing_values", "duplicate_ids", "inconsistent_categories", "outliers"}.issubset(issues))


if __name__ == "__main__":
    unittest.main()
