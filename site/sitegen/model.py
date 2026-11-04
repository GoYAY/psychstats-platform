from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TERM_TYPES = frozenset({"concept", "method", "indicator", "workflow"})
LEVELS = frozenset({"basic", "intermediate", "advanced"})
STATUSES = frozenset({"draft", "public"})
RELATION_TYPES = (
    "prerequisites",
    "components",
    "contrasts",
    "used_in",
    "next",
)


@dataclass(slots=True)
class TermMeta:
    id: str
    zh: str
    en: str
    aliases: tuple[str, ...]
    type: str
    level: str
    topic: str
    status: str
    summary: str
    relations: dict[str, tuple[str, ...]]


@dataclass(slots=True)
class Term(TermMeta):
    real_question: str
    operational_definition: str
    plain_explanation: str
    problems_solved: tuple[str, ...]
    not_for: tuple[str, ...]
    decision_clues: tuple[str, ...]
    quiz: dict[str, Any]
    sources: tuple[dict[str, Any], ...]
    r_practice: dict[str, Any] | None = None


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _relations(value: Any) -> dict[str, tuple[str, ...]]:
    source = value if isinstance(value, dict) else {}
    return {
        relation: tuple(str(item) for item in source.get(relation, []))
        for relation in RELATION_TYPES
    }


def _meta_from_dict(value: dict[str, Any]) -> TermMeta:
    return TermMeta(
        id=str(value.get("id", "")).strip(),
        zh=str(value.get("zh", "")).strip(),
        en=str(value.get("en", "")).strip(),
        aliases=tuple(str(item).strip() for item in value.get("aliases", [])),
        type=str(value.get("type", "")).strip(),
        level=str(value.get("level", "")).strip(),
        topic=str(value.get("topic", "")).strip(),
        status=str(value.get("status", "")).strip(),
        summary=str(value.get("summary", "")).strip(),
        relations=_relations(value.get("relations")),
    )


def load_registry(path: Path) -> dict[str, TermMeta]:
    payload = _load_json(path)
    values = payload.get("terms", []) if isinstance(payload, dict) else payload
    if not isinstance(values, list):
        raise ValueError("registry must contain a terms list")

    registry: dict[str, TermMeta] = {}
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("each registry term must be an object")
        item = _meta_from_dict(value)
        if item.id in registry:
            raise ValueError(f"duplicate term id: {item.id}")
        registry[item.id] = item
    return registry


def term_from_dict(value: dict[str, Any]) -> Term:
    if not isinstance(value, dict):
        raise ValueError("term must be an object")
    meta = _meta_from_dict(value)
    return Term(
        id=meta.id,
        zh=meta.zh,
        en=meta.en,
        aliases=meta.aliases,
        type=meta.type,
        level=meta.level,
        topic=meta.topic,
        status=meta.status,
        summary=meta.summary,
        relations=meta.relations,
        real_question=str(value.get("real_question", "")).strip(),
        operational_definition=str(value.get("operational_definition", "")).strip(),
        plain_explanation=str(value.get("plain_explanation", "")).strip(),
        problems_solved=tuple(str(item) for item in value.get("problems_solved", [])),
        not_for=tuple(str(item) for item in value.get("not_for", [])),
        decision_clues=tuple(str(item) for item in value.get("decision_clues", [])),
        quiz=value.get("quiz", {}),
        sources=tuple(value.get("sources", [])),
        r_practice=value.get("r_practice"),
    )


def load_term(path: Path) -> Term:
    return term_from_dict(_load_json(path))


def _validate_meta(term: TermMeta) -> list[str]:
    errors: list[str] = []
    for field in ("id", "zh", "en", "topic", "summary"):
        if not getattr(term, field):
            errors.append(f"{term.id or '<missing-id>'}: {field} is required")
    if term.type not in TERM_TYPES:
        errors.append(f"{term.id}: invalid type {term.type!r}")
    if term.level not in LEVELS:
        errors.append(f"{term.id}: invalid level {term.level!r}")
    if term.status not in STATUSES:
        errors.append(f"{term.id}: invalid status {term.status!r}")
    unknown_relations = set(term.relations) - set(RELATION_TYPES)
    if unknown_relations:
        errors.append(f"{term.id}: unknown relations {sorted(unknown_relations)}")
    return errors


def validate_term(term: Term) -> list[str]:
    errors = _validate_meta(term)
    for field in ("real_question", "operational_definition", "plain_explanation"):
        if not getattr(term, field):
            errors.append(f"{term.id}: {field} is required")
    if not isinstance(term.quiz, dict) or not term.quiz:
        errors.append(f"{term.id}: quiz is required")
    if not term.sources:
        errors.append(f"{term.id}: sources are required")
    return errors


def validate_quiz_explanations(quiz: dict[str, Any], term_id: str) -> list[str]:
    options = quiz.get("options") or []
    explanations = quiz.get("option_explanations") or []
    if len(explanations) != len(options) or any(not str(item).strip() for item in explanations):
        return [f"{term_id}: quiz.option_explanations must explain every option"]
    return []


def _conflicts(registry: dict[str, TermMeta], field: str) -> list[str]:
    seen: dict[str, str] = {}
    errors: list[str] = []
    for term in registry.values():
        value = getattr(term, field)
        key = value.casefold().strip()
        if key and key in seen:
            errors.append(f"{field} conflict: {seen[key]} and {term.id} both use {value!r}")
        elif key:
            seen[key] = term.id
    return errors


def validate_registry(registry: dict[str, TermMeta]) -> list[str]:
    from .graph import validate_graph

    errors: list[str] = []
    for key, term in registry.items():
        if key != term.id:
            errors.append(f"registry key {key!r} does not match term id {term.id!r}")
        errors.extend(_validate_meta(term))
    errors.extend(_conflicts(registry, "zh"))
    errors.extend(_conflicts(registry, "en"))

    seen_aliases: dict[str, str] = {}
    for term in registry.values():
        for alias in term.aliases:
            key = alias.casefold().strip()
            if key and key in seen_aliases and seen_aliases[key] != term.id:
                errors.append(
                    f"alias conflict: {seen_aliases[key]} and {term.id} both use {alias!r}"
                )
            elif key:
                seen_aliases[key] = term.id

    errors.extend(validate_graph(registry))
    return errors
