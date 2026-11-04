# -*- coding: utf-8 -*-
"""Create unverified v2 authoring skeletons from the term registry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = ROOT / "site"
if str(SITE_ROOT) not in sys.path:
    sys.path.insert(0, str(SITE_ROOT))

from sitegen.model import TermMeta, load_registry  # noqa: E402


REGISTRY = ROOT / "site" / "content" / "registry.json"
LEGACY_CANDIDATES = ROOT / "site" / "content" / "terms_draft.json"
OUT_DIR = ROOT / "site" / "content" / "drafts"


def _relations(meta: TermMeta) -> dict[str, list[str]]:
    return {name: list(targets) for name, targets in meta.relations.items()}


def _r_skeleton() -> dict[str, Any]:
    return {
        "packages": [],
        "data_shape": "",
        "example_code": "",
        "your_data_code": "",
        "assumption_checks": [],
        "key_output": [],
        "interpretation": "",
        "report_template": "",
        "common_errors": [],
        "verified": False,
        "validation_report": "",
    }


def make_draft(
    meta: TermMeta, candidate_evidence: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "id": meta.id,
        "zh": meta.zh,
        "en": meta.en,
        "aliases": list(meta.aliases),
        "type": meta.type,
        "level": meta.level,
        "topic": meta.topic,
        "status": "draft",
        "summary": meta.summary,
        "relations": _relations(meta),
        "real_question": "",
        "operational_definition": "",
        "plain_explanation": "",
        "problems_solved": [],
        "not_for": [],
        "decision_clues": [],
        "sections": [],
        "formula": {"latex": "", "note": "", "verified": False},
        "quiz": {"question": "", "options": [], "answer": 0, "explanation": ""},
        "sources": [],
        "r_practice": None if meta.type == "concept" else _r_skeleton(),
        "verified": False,
        "candidate_evidence": candidate_evidence or {},
        "authoring_todos": [
            "根据真实学习或研究场景填写 real_question",
            "用自己的话填写操作性定义与通俗解释，不复制教材长段落",
            "按条目类型补齐正文模块、适用边界和决策线索",
            "设计至少一道选择题并核对答案索引与解析",
            "记录可核验来源；详情页可保留定位信息",
            "如包含公式，人工复核后设置 formula.verified=true",
            "如包含 R 实操，运行验证后设置 r_practice.verified=true 并记录报告",
            "全部内容复核后设置 verified=true，再使用提升命令",
        ],
    }


def _legacy_evidence() -> dict[str, dict[str, Any]]:
    if not LEGACY_CANDIDATES.exists():
        return {}
    with LEGACY_CANDIDATES.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return {
        item["slug"]: item.get("evidence", {})
        for item in payload.get("terms", [])
    }


def _is_safe_v1_skeleton(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(value, dict)
        and "slug" in value
        and "id" not in value
        and not value.get("verified")
        and not str(value.get("question", "")).strip()
        and not str(value.get("definition", "")).strip()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="replace all existing drafts")
    parser.add_argument(
        "--migrate-v1",
        action="store_true",
        help="replace only empty, unverified v1 skeletons",
    )
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)

    registry = load_registry(REGISTRY)
    evidence = _legacy_evidence()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = skipped = 0
    values = list(registry.values())
    if args.limit is not None:
        values = values[: args.limit]

    for meta in values:
        path = OUT_DIR / f"{meta.id}.json"
        replace = args.force or (args.migrate_v1 and path.exists() and _is_safe_v1_skeleton(path))
        if path.exists() and not replace:
            skipped += 1
            continue
        path.write_text(
            json.dumps(make_draft(meta, evidence.get(meta.id)), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        written += 1

    print(f"drafts written={written} skipped={skipped} -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
