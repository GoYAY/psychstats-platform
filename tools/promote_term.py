# -*- coding: utf-8 -*-
"""Validate and promote one reviewed v2 term draft into the public term set."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = ROOT / "site"
if str(SITE_ROOT) not in sys.path:
    sys.path.insert(0, str(SITE_ROOT))

from sitegen.model import (  # noqa: E402
    load_registry,
    term_from_dict,
    validate_registry,
    validate_quiz_explanations,
    validate_term,
)


DRAFTS = ROOT / "site" / "content" / "drafts"
TERM_DIR = ROOT / "site" / "content" / "terms"
REGISTRY = ROOT / "site" / "content" / "registry.json"
TERMS = ROOT / "site" / "content" / "terms.json"

SOURCE_CATALOG_FIELDS = (
    "kind",
    "title",
    "authors",
    "year",
    "edition",
    "publisher",
    "url",
    "role",
)


@dataclass(frozen=True, slots=True)
class PromotionResult:
    slug: str
    ok: bool
    written: bool
    errors: tuple[str, ...]


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _published_ids(term_dir: Path) -> set[str]:
    published: set[str] = set()
    if not term_dir.exists():
        return published
    for path in term_dir.glob("*.json"):
        value = _read_json(path)
        if isinstance(value, dict) and value.get("status") == "public":
            published.add(str(value.get("id", path.stem)))
    return published


def validate_draft(
    value: dict[str, Any],
    *,
    registry_path: Path = REGISTRY,
    term_dir: Path = TERM_DIR,
) -> list[str]:
    errors: list[str] = []
    try:
        term = term_from_dict(value)
    except (TypeError, ValueError) as exc:
        return [str(exc)]
    errors.extend(validate_term(term))

    if not value.get("verified"):
        errors.append(f"{term.id}: verified must be true")

    formula = value.get("formula") or {}
    if str(formula.get("latex", "")).strip() and not formula.get("verified"):
        errors.append(f"{term.id}: formula.verified must be true when a formula is present")

    r_practice = value.get("r_practice")
    if r_practice is not None:
        if not isinstance(r_practice, dict) or not r_practice.get("verified"):
            errors.append(f"{term.id}: r_practice.verified must be true")

    quiz = value.get("quiz") or {}
    errors.extend(validate_quiz_explanations(quiz, term.id))
    options = quiz.get("options") or []
    answer = quiz.get("answer")
    if len(options) < 2:
        errors.append(f"{term.id}: quiz.options must contain at least two choices")
    elif not isinstance(answer, int) or isinstance(answer, bool) or not 0 <= answer < len(options):
        errors.append(f"{term.id}: quiz.answer is out of range")

    if not value.get("sources"):
        errors.append(f"{term.id}: sources must not be empty")

    try:
        registry = load_registry(registry_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"registry could not be loaded: {exc}")
        return errors

    registry_errors = [
        error for error in validate_registry(registry)
        if not error.startswith("isolated term:")
    ]
    errors.extend(f"registry: {error}" for error in registry_errors)
    meta = registry.get(term.id)
    if meta is None:
        errors.append(f"{term.id}: not present in registry")
        return errors

    for field in ("zh", "en", "type", "level", "topic"):
        if getattr(term, field) != getattr(meta, field):
            errors.append(f"{term.id}: {field} does not match registry")
    if term.relations != meta.relations:
        errors.append(f"{term.id}: relations do not match registry")

    published = _published_ids(term_dir)
    for prerequisite in term.relations.get("prerequisites", ()):
        if prerequisite not in published:
            errors.append(f"{term.id}: prerequisite {prerequisite} is not public")
    return errors


def _source_catalog(terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for term in terms:
        for source in term.get("sources", []):
            if not isinstance(source, dict):
                continue
            public_source = {
                field: source[field]
                for field in SOURCE_CATALOG_FIELDS
                if source.get(field) not in (None, "", [])
            }
            identity = json.dumps(public_source, ensure_ascii=False, sort_keys=True)
            unique[identity] = public_source
    return [unique[key] for key in sorted(unique)]


def aggregate_terms(term_dir: Path) -> dict[str, Any]:
    terms: list[dict[str, Any]] = []
    if term_dir.exists():
        for path in sorted(term_dir.glob("*.json")):
            value = _read_json(path)
            if not isinstance(value, dict):
                raise ValueError(f"{path}: term must be an object")
            if value.get("status") != "public":
                raise ValueError(f"{path}: aggregated term is not public")
            validation = validate_term(term_from_dict(value))
            if validation:
                raise ValueError(f"{path}: {'; '.join(validation)}")
            terms.append(value)
    terms.sort(key=lambda item: item["id"])
    return {
        "schema_version": "2.0",
        "terms": terms,
        "source_catalog": _source_catalog(terms),
    }


def promote(slug: str, preview: bool = False) -> PromotionResult:
    draft_path = DRAFTS / f"{slug}.json"
    if not draft_path.exists():
        return PromotionResult(slug, False, False, (f"draft not found: {slug}",))
    value = _read_json(draft_path)
    if not isinstance(value, dict):
        return PromotionResult(slug, False, False, ("draft must be an object",))

    errors = validate_draft(value, registry_path=REGISTRY, term_dir=TERM_DIR)
    if errors:
        return PromotionResult(slug, False, False, tuple(errors))
    if preview:
        return PromotionResult(slug, True, False, ())

    public_value = dict(value)
    public_value["status"] = "public"
    _write_json(TERM_DIR / f"{slug}.json", public_value)
    _write_json(TERMS, aggregate_terms(TERM_DIR))
    return PromotionResult(slug, True, True, ())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate drafts without writing")
    parser.add_argument("--slug", help="term ID to validate or promote")
    args = parser.parse_args(argv)

    slugs = [args.slug] if args.slug else sorted(path.stem for path in DRAFTS.glob("*.json"))
    if not args.check and not args.slug:
        parser.error("--slug is required unless --check is used")

    failures = 0
    for slug in slugs:
        result = promote(slug, preview=args.check)
        if result.ok:
            action = "eligible" if args.check else "promoted"
            print(f"{slug}: {action}")
        else:
            failures += 1
            print(f"{slug}: rejected — {'; '.join(result.errors)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
