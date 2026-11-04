from __future__ import annotations

import csv
import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
TRUTH_PATH = DATA_DIR / "generation_truth.json"
GENERATOR_VERSION = "1.0"
EXPECTED_SEEDS = {
    "cross_sectional_survey": 20260901,
    "learning_experiment": 20260902,
    "scale_items": 20260903,
    "nested_classrooms": 20260904,
    "longitudinal_growth": 20260905,
    "messy_survey": 20260906,
}


def _missing(value: str) -> bool:
    return value.strip() in {"", "NA", "NaN"}


def validate_dataset_contract(
    dataset_id: str,
    data_dir: Path = DATA_DIR,
    truth_path: Path = TRUTH_PATH,
) -> list[str]:
    errors: list[str] = []
    try:
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{dataset_id}.truth: {exc}"]
    if truth.get("generator_version") != GENERATOR_VERSION:
        errors.append(f"{dataset_id}.generator_version drift")
    spec = truth.get("datasets", {}).get(dataset_id)
    if not spec:
        return errors + [f"{dataset_id}: missing truth contract"]
    if spec.get("seed") != EXPECTED_SEEDS.get(dataset_id):
        errors.append(f"{dataset_id}.seed drift: {spec.get('seed')}")
    path = data_dir / spec.get("file", "")
    if not path.is_file():
        return errors + [f"{dataset_id}.file missing: {path.name}"]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = set(reader.fieldnames or [])
    if len(rows) != spec.get("rows"):
        errors.append(f"{dataset_id}.rows expected {spec.get('rows')} got {len(rows)}")
    for column, rule in spec.get("columns", {}).items():
        if column not in fields:
            errors.append(f"{dataset_id}.{column}: missing column")
            continue
        for row_number, row in enumerate(rows, 2):
            raw = row.get(column, "")
            if _missing(raw):
                if not rule.get("allow_missing", False):
                    errors.append(f"{dataset_id}.{column}: missing value at row {row_number}")
                continue
            kind = rule.get("type")
            if kind in {"integer", "numeric"}:
                try:
                    value = float(raw)
                except ValueError:
                    errors.append(f"{dataset_id}.{column}: wrong {kind} at row {row_number}")
                    continue
                if kind == "integer" and not value.is_integer():
                    errors.append(f"{dataset_id}.{column}: wrong integer at row {row_number}")
                if "min" in rule and value < rule["min"]:
                    errors.append(f"{dataset_id}.{column}: below minimum at row {row_number}")
                if "max" in rule and value > rule["max"]:
                    errors.append(f"{dataset_id}.{column}: above maximum at row {row_number}")
            elif kind == "categorical" and raw not in rule.get("levels", []):
                errors.append(f"{dataset_id}.{column}: unknown-level {raw!r} at row {row_number}")
    return errors
