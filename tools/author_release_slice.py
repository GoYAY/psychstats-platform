# -*- coding: utf-8 -*-
"""Materialize the editorially reviewed first release slice; do not publish it."""

from __future__ import annotations

import json
import re
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "site" / "content"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_example_code(slug: str, root: Path = ROOT) -> str:
    path = root / "examples" / "r" / "analyses" / f"{slug}.R"
    code = path.read_text(encoding="utf-8")
    code = code.replace('source("examples/r/analyses/_common.R")\n', "")
    code = re.sub(
        r'read_data\("([a-z_]+)"\)',
        lambda match: f'read.csv("{match.group(1)}.csv", stringsAsFactors = FALSE)',
        code,
    )
    code = code.replace("emit(c(", "print(c(")
    if any(token in code for token in ("read_data(", "emit(", "source(")):
        raise ValueError(f"{slug}: example still requires the validation harness")
    return "# 将示例 CSV 放在 R 当前工作目录；也可使用完整路径\n" + code


def prepare() -> None:
    seed = read_json(CONTENT / "release_slice_seed.json")["terms"]
    registry_path = CONTENT / "registry.json"
    registry = read_json(registry_path)
    report = read_json(ROOT / "logs" / "r_validation.json")
    verified = {entry["term_id"] for entry in report["results"] if entry["verified"] and not entry["errors"]}
    by_id = {entry["id"]: entry for entry in registry["terms"]}
    for slug, body in seed.items():
        draft_path = CONTENT / "drafts" / f"{slug}.json"
        draft = read_json(draft_path)
        meta = by_id[slug]
        meta["summary"] = body["summary"]
        meta["relations"]["prerequisites"] = body["prerequisites"]
        draft["summary"] = body["summary"]
        draft["relations"] = meta["relations"]
        for key in ("real_question", "operational_definition", "plain_explanation", "plain_example", "problems_solved", "not_for", "decision_clues", "sections", "quiz"):
            draft[key] = body[key]
        draft["sources"] = [{
            "kind": body.get("source_kind", "basic_textbook"),
            "title": "高级心理统计" if body.get("source_kind") == "advanced_textbook" else "现代心理与教育统计学",
            "role": "概念与方法核对",
        }]
        draft["formula"] = {
            "latex": body.get("formula", ""),
            "note": "按页面所述前提使用；公式中的量须与研究设计一致。" if body.get("formula") else "",
            "verified": bool(body.get("formula")),
        }
        if slug in verified:
            own = (ROOT / "examples" / "r" / "templates" / f"{slug}.R").read_text(encoding="utf-8")
            draft["r_practice"] = {
                "packages": [],
                "data_shape": "CSV 的一行是一条观测；先下载示例数据并放到 R 当前工作目录。",
                "example_code": make_example_code(slug),
                "your_data_code": own,
                "assumption_checks": body["decision_clues"],
                "key_output": list(next(entry["metrics"] for entry in report["results"] if entry["term_id"] == slug)),
                "interpretation": body["output_interpretation"],
                "report_template": "报告所用方法、样本量、关键估计量及其不确定性，并交代适用条件。",
                "common_errors": body["not_for"],
                "verified": True,
                "validation_report": "logs/r_validation.json",
            }
        else:
            draft["r_practice"] = None
        draft["verified"] = True
        draft.pop("authoring_todos", None)
        write_json(draft_path, draft)
    write_json(registry_path, registry)
    print(f"Prepared {len(seed)} reviewed drafts; no terms were published.")


def mark_public() -> None:
    seed = read_json(CONTENT / "release_slice_seed.json")["terms"]
    registry_path = CONTENT / "registry.json"
    registry = read_json(registry_path)
    for slug in seed:
        path = CONTENT / "terms" / f"{slug}.json"
        if not path.exists() or read_json(path).get("status") != "public":
            raise ValueError(f"{slug}: no promoted public file")
    for entry in registry["terms"]:
        if entry["id"] in seed:
            entry["status"] = "public"
    write_json(registry_path, registry)
    print(f"Marked {len(seed)} promoted entries public in registry.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mark-public", action="store_true")
    args = parser.parse_args()
    mark_public() if args.mark_public else prepare()
