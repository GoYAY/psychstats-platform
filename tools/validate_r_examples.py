"""Run teaching R examples and check numerical result contracts."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "examples" / "r" / "analyses"
SPEC_PATH = ROOT / "examples" / "r" / "validation_specs.json"
REPORT_PATH = ROOT / "logs" / "r_validation.json"


def load_specs() -> dict:
    if not SPEC_PATH.exists():
        return {}
    with SPEC_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


SPECS = load_specs()


@dataclass(frozen=True)
class ValidationResult:
    term_id: str
    verified: bool
    errors: tuple[str, ...]
    metrics: dict[str, float]
    rscript: str | None


def find_rscript() -> Path | None:
    configured = os.environ.get("R_EXAMPLES_RSCRIPT")
    candidates = [Path(configured)] if configured else []
    candidates.append(Path(r"C:\Program Files\R\R-4.5.1\bin\Rscript.exe"))
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _installed_packages(rscript: Path, packages: list[str]) -> set[str]:
    if not packages:
        return set()
    query = "cat(paste(rownames(installed.packages()), collapse='\\n'))"
    completed = subprocess.run(
        [str(rscript), "-e", query], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30, check=False,
    )
    if completed.returncode:
        return set()
    return set(completed.stdout.splitlines())


def validate_example(term_id: str) -> ValidationResult:
    errors: list[str] = []
    metrics: dict[str, float] = {}
    rscript = find_rscript()
    if rscript is None:
        return ValidationResult(term_id, False, ("Rscript is unavailable",), metrics, None)
    spec = SPECS.get(term_id)
    if spec is None:
        return ValidationResult(term_id, False, (f"unknown example: {term_id}",), metrics, str(rscript))
    required = spec.get("required_packages", [])
    missing = set(required) - _installed_packages(rscript, required)
    if missing:
        return ValidationResult(term_id, False, (f"missing R package: {', '.join(sorted(missing))}",), metrics, str(rscript))
    script = Path(spec["script"])
    if not script.is_absolute():
        script = ROOT / script
    if not script.is_file():
        return ValidationResult(term_id, False, (f"script missing: {script}",), metrics, str(rscript))

    with tempfile.TemporaryDirectory(prefix=f"r-example-{term_id}-") as temporary:
        output = Path(temporary) / "metrics.tsv"
        try:
            completed = subprocess.run(
                [str(rscript), str(script), str(output), "examples/data"],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120, check=False,
            )
        except subprocess.TimeoutExpired:
            return ValidationResult(term_id, False, ("Rscript timed out",), metrics, str(rscript))
        if completed.returncode:
            errors.append(f"Rscript exited {completed.returncode}: {completed.stderr[-500:]}")
        if not output.is_file():
            errors.append("result file missing")
        else:
            try:
                with output.open("r", encoding="utf-8-sig", newline="") as handle:
                    for row in csv.DictReader(handle, delimiter="\t"):
                        metrics[row["metric"]] = float(row["value"])
            except (KeyError, ValueError, OSError) as exc:
                errors.append(f"invalid result file: {exc}")

    if spec.get("requires_convergence") and metrics.get("converged") != 1:
        errors.append("converged must equal 1")
    for metric, rule in spec.get("metrics", {}).items():
        value = metrics.get(metric)
        if value is None:
            errors.append(f"metric missing: {metric}")
            continue
        if "min" in rule and value < rule["min"]:
            errors.append(f"{metric} below minimum {rule['min']}: {value}")
        if "max" in rule and value > rule["max"]:
            errors.append(f"{metric} above maximum {rule['max']}: {value}")
        if "target" in rule and abs(value - rule["target"]) > rule.get("tolerance", 0):
            errors.append(f"{metric} outside tolerance: {value}")
    return ValidationResult(term_id, not errors, tuple(errors), metrics, str(rscript))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--term")
    args = parser.parse_args(argv)
    ids = sorted(SPECS) if args.all else [args.term] if args.term else []
    if not ids:
        parser.error("provide --all or --term ID")
    results = [validate_example(term_id) for term_id in ids]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps({"schema_version": "1.0", "results": [asdict(result) for result in results]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for result in results:
        print(f"{result.term_id}: {'PASS' if result.verified else 'FAIL'} {', '.join(result.errors)}")
    return 0 if all(result.verified for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
