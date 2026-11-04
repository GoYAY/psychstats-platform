from __future__ import annotations

from collections import defaultdict

from .model import RELATION_TYPES, TermMeta


def build_backlinks(
    registry: dict[str, TermMeta],
) -> dict[str, dict[str, list[str]]]:
    backlinks = {
        term_id: {relation: [] for relation in RELATION_TYPES}
        for term_id in registry
    }
    for source_id, term in registry.items():
        for relation in RELATION_TYPES:
            for target_id in term.relations.get(relation, ()):
                if target_id in backlinks:
                    backlinks[target_id][relation].append(source_id)
    for relations in backlinks.values():
        for values in relations.values():
            values.sort()
    return backlinks


def public_closure(
    registry: dict[str, TermMeta], approved_ids: set[str]
) -> set[str]:
    closure: set[str] = set()
    pending = list(approved_ids)
    while pending:
        term_id = pending.pop()
        if term_id in closure:
            continue
        if term_id not in registry:
            raise KeyError(f"unknown term id: {term_id}")
        closure.add(term_id)
        pending.extend(registry[term_id].relations.get("prerequisites", ()))
    return closure


def _prerequisite_cycles(registry: dict[str, TermMeta]) -> list[str]:
    colors: dict[str, int] = defaultdict(int)
    stack: list[str] = []
    errors: list[str] = []
    reported: set[frozenset[str]] = set()

    def visit(term_id: str) -> None:
        colors[term_id] = 1
        stack.append(term_id)
        for target_id in registry[term_id].relations.get("prerequisites", ()):
            if target_id not in registry:
                continue
            if colors[target_id] == 0:
                visit(target_id)
            elif colors[target_id] == 1:
                start = stack.index(target_id)
                cycle = stack[start:] + [target_id]
                identity = frozenset(cycle)
                if identity not in reported:
                    errors.append(f"prerequisite cycle: {' -> '.join(cycle)}")
                    reported.add(identity)
        stack.pop()
        colors[term_id] = 2

    for term_id in registry:
        if colors[term_id] == 0:
            visit(term_id)
    return errors


def validate_graph(registry: dict[str, TermMeta]) -> list[str]:
    errors: list[str] = []
    incoming: dict[str, int] = {term_id: 0 for term_id in registry}
    outgoing: dict[str, int] = {term_id: 0 for term_id in registry}

    for source_id, term in registry.items():
        for relation in RELATION_TYPES:
            for target_id in term.relations.get(relation, ()):
                outgoing[source_id] += 1
                if target_id not in registry:
                    errors.append(
                        f"{source_id}: relation {relation} targets missing term {target_id}"
                    )
                    continue
                incoming[target_id] += 1
                if (
                    relation == "prerequisites"
                    and term.status == "public"
                    and registry[target_id].status != "public"
                ):
                    errors.append(
                        f"{source_id}: prerequisite {target_id} is not public"
                    )

    errors.extend(_prerequisite_cycles(registry))
    for term_id in registry:
        if incoming[term_id] == 0 and outgoing[term_id] == 0:
            errors.append(f"isolated term: {term_id}")
    return errors
