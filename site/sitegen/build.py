from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .model import RELATION_TYPES, term_from_dict, validate_term, validate_quiz_explanations
from .math_render import render_formulas
from .reading_aids import display_payload, leading_zero, reading_metadata, formula_aid
from .curriculum import order_terms
from .plain_visuals import load_visuals, render_svg
from .symbol_reference import load_reference, attach_card_symbols, render_reference
from .cache_bust import add_cache_busting
from .analysis_catalog import load_analysis_catalog, load_analysis_cases, validate_catalog_cases, validate_result, artifact_fingerprints, select_analysis_examples
from .analysis_reader import render_analysis_index, render_analysis_case, analysis_search_entries, analysis_report_for_term
from .output_guides import source_map
from .paper_reporting import render_paper_result, validate_paper_assets
from .render import (
    LEVEL_LABELS,
    TYPE_LABELS,
    render_datasets,
    render_index,
    render_paths,
    render_practice,
    render_practice_reading,
    render_sources,
    render_term,
    render_topic,
    topic_overview,
)


SITE_ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = SITE_ROOT / "content"
ASSET_DIR = SITE_ROOT / "assets"
VALIDATOR_VERSION = "2.0"


class BuildError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BuildReport:
    mode: str
    input_hash: str
    term_count: int
    page_count: int
    question_count: int
    dataset_count: int
    validator_version: str = VALIDATOR_VERSION


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_term_files(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    values = []
    for path in sorted(directory.glob("*.json")):
        value = _read_json(path)
        if not isinstance(value, dict):
            raise BuildError(f"{path}: term must be an object")
        values.append(value)
    return values


def _input_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _public_errors(terms: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    ids = {str(term.get("id", "")) for term in terms}
    for value in terms:
        term = term_from_dict(value)
        errors.extend(validate_term(term))
        errors.extend(validate_quiz_explanations(term.quiz, term.id))
        if term.status != "public":
            errors.append(f"{term.id}: status is not public")
        if not value.get("verified"):
            errors.append(f"{term.id}: verified must be true")
        formula = value.get("formula") or {}
        if str(formula.get("latex", "")).strip() and not formula.get("verified"):
            errors.append(f"{term.id}: formula is not verified")
        r_practice = value.get("r_practice")
        if r_practice is not None and (
            not isinstance(r_practice, dict) or not r_practice.get("verified")
        ):
            errors.append(f"{term.id}: r_practice is not verified")
        for relation in ("prerequisites",):
            for target in term.relations.get(relation, ()):
                if target not in ids:
                    errors.append(
                        f"{term.id}: relation {relation} target {target} is missing or unpublished"
                    )
    return errors


def _search_index(terms: list[dict[str, Any]], topic_names: dict[str, str] | None = None) -> list[dict[str, Any]]:
    topic_names = topic_names or {}
    def body_text(term):
        fields = [term.get(key, '') for key in ('real_question','operational_definition','plain_explanation','plain_example')]
        fields += [str(section.get(key, '')) for section in term.get('sections', []) for key in ('heading','body','h','md')]
        fields += [str(item.get(key, '')) for item in term.get('concepts', []) for key in ('zh','definition','example')]
        fields += [(term.get('formula') or {}).get('note', '')]
        fields += [str(item.get(key, '')) for item in term.get('visual_steps', []) for key in ('label','detail')]
        fields += [str(value) for key,value in (term.get('r_practice') or {}).items() if key in ('assumption_checks','key_output','interpretation','report_template','report_example','report_limits','common_errors')]
        aid = reading_metadata().get(str(term.get('id')), {})
        fields += [aid.get(key, '') for key in ('formula_logic','report_example','agent_prompt')]
        formula = term.get('formula') or {}
        if formula.get('latex'):
            _, symbols = formula_aid(formula['latex'], str(term.get('id')), str(formula.get('note') or ''))
            fields += [symbol.get('meaning', '') for symbol in symbols]
        return leading_zero(' '.join(str(field) for field in fields if field))
    return [
        {
            "id": term.get("id"),
            "zh": term.get("zh"),
            "en": term.get("en"),
            "aliases": term.get("aliases", []),
            "concepts": {name:concept['id'] for concept in term.get('concepts',[]) for name in concept.get('names',[concept['zh']])},
            "type": term.get("type"),
            "level": term.get("level"),
            "topic": term.get("topic"),
            "topic_label": topic_names.get(term.get("topic"), term.get("topic")),
            "type_label": TYPE_LABELS.get(term.get("type"), term.get("type")),
            "level_label": LEVEL_LABELS.get(term.get("level"), term.get("level")),
            "summary": term.get("summary"),
            "body_text": body_text(term),
            "problems_solved": term.get("problems_solved", []),
            "search_terms": term.get("search_terms", []) + ([term.get("real_question")] if term.get("real_question") else []),
            "r_functions": term.get("r_practice", {}).get("functions", []) if isinstance(term.get("r_practice"), dict) else [],
            "has_r": isinstance(term.get("r_practice"), dict),
        }
        for term in terms
    ]


def _quiz_bank(terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    quizzes = []
    names = {term['id']:[term.get('zh'),*term.get('aliases',[])] for term in terms}
    names.update({term['id']+'#'+concept['id']:concept.get('names',[concept['zh']])
                  for term in terms for concept in term.get('concepts',[])})
    for term in terms:
        quiz = term.get("quiz")
        if not isinstance(quiz, dict) or len(quiz.get("options") or []) < 2:
            continue
        quizzes.append(display_payload({"id": f"{term.get('id')}-1", "term_id": term.get("id"), **quiz,
                                       "reading_html":render_practice_reading(term,names)}))
    return quizzes


def _graph(terms: list[dict[str, Any]]) -> dict[str, Any]:
    ids = {term.get("id") for term in terms}
    nodes = [
        {
            "id": term.get("id"),
            "zh": term.get("zh"),
            "topic": term.get("topic"),
            "type": term.get("type"),
            "level": term.get("level"),
        }
        for term in terms
    ]
    edges = []
    for term in terms:
        for relation in RELATION_TYPES:
            for target in (term.get("relations") or {}).get(relation, []):
                if target in ids:
                    edges.append(
                        {"source": term.get("id"), "target": target, "type": relation}
                    )
    return {"nodes": nodes, "edges": edges}


def _prepare_output(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    if resolved == Path(resolved.anchor):
        raise BuildError("refusing to build into a filesystem root")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "terms").mkdir(parents=True)
    (output_dir / "assets" / "data").mkdir(parents=True)


def build_site(
    mode: Literal["preview", "public"], output_dir: Path
) -> BuildReport:
    if mode not in ("preview", "public"):
        raise ValueError(f"unknown build mode: {mode}")
    source_dir = CONTENT_DIR / ("drafts" if mode == "preview" else "terms")
    source_paths = sorted(source_dir.glob("*.json")) if source_dir.exists() else []
    terms = _load_term_files(source_dir)
    terms.sort(key=lambda item: str(item.get("id", "")))

    if mode == "public":
        errors = _public_errors(terms)
        if errors:
            raise BuildError("public build rejected:\n- " + "\n- ".join(errors))

    topics_payload = _read_json(CONTENT_DIR / "topics.json")
    curriculum_path = CONTENT_DIR / "curriculum.json"
    curriculum = _read_json(curriculum_path).get("topics", []) if curriculum_path.is_file() else []
    curriculum_by_id = {item["id"]: item for item in curriculum}
    topic_rank = {item["id"]: i for i, item in enumerate(curriculum)}
    topics = sorted(topics_payload.get("topics", []), key=lambda t: topic_rank.get(t["id"], 999))
    topics = [{**topic, **{k:v for k,v in curriculum_by_id.get(topic["id"], {}).items() if k != "terms"}} for topic in topics]
    topics = [{**topic, "overview": topic_overview(topic.get("basis", ""))} for topic in topics]
    terms = order_terms(terms, curriculum)
    symbols_path = CONTENT_DIR / 'symbol_reference.json'
    symbol_entries = load_reference(symbols_path)
    known_ids = {term['id'] for term in terms}
    symbol_entries = [entry for entry in symbol_entries if known_ids.intersection(entry['terms'])]
    attach_card_symbols(terms, symbol_entries)
    topic_names = {topic["id"]: topic["zh"] for topic in topics_payload.get("topics", [])}
    visuals_path = CONTENT_DIR / "diagram_samples.json"
    visuals = _read_json(visuals_path) if visuals_path.is_file() else {}
    if not isinstance(visuals, dict):
        raise BuildError("diagram_samples.json must be an object")
    if mode == "public":
        visuals = {slug: visual for slug, visual in visuals.items()
                   if not (isinstance(visual, dict) and visual.get("preview_only"))}
    for slug, visual in visuals.items():
        if slug not in {term["id"] for term in terms}:
            continue
        if not isinstance(visual, dict):
            raise BuildError(f"{slug}: invalid diagram metadata")
        for filename in (visual.get("file"), visual.get("mobile_file")):
            if not isinstance(filename, str) or not re.fullmatch(r"[a-z0-9-]+\.svg", filename):
                raise BuildError(f"{slug}: invalid diagram filename")
            if not (ASSET_DIR / "diagrams" / filename).is_file():
                raise BuildError(f"{slug}: diagram asset is missing: {filename}")
    formulas = render_formulas({
        term["id"]: term["formula"]["latex"] for term in terms
        if (term.get("formula") or {}).get("latex", "").strip()
    })
    try:
        plain_visuals = load_visuals(CONTENT_DIR / 'plain_visuals')
    except (ValueError, KeyError, TypeError) as error:
        raise BuildError(f'Invalid plain visual: {error}') from error
    for slug, entry in plain_visuals.items():
        if entry['decision'] == 'reuse' and slug in {term['id'] for term in terms}:
            if entry['reuse'] not in visuals:
                # Preview-only reference should not leak into a public build.
                if mode == 'public':
                    continue
                raise BuildError(f'{slug}: missing/mismatched reusable diagram')
    analysis_path = CONTENT_DIR / 'analysis_catalog.json'
    registry_ids = {t['id'] for t in _read_json(CONTENT_DIR / 'registry.json')['terms']}
    analysis_catalog = load_analysis_catalog(analysis_path, registry_ids) if analysis_path.exists() else {'units': [], 'term_routes': []}
    analysis_cases = load_analysis_cases(CONTENT_DIR / 'analysis_cases')
    validate_catalog_cases(analysis_catalog, analysis_cases)
    analysis_results = {}
    for slug, case in analysis_cases.items():
        result_path = CONTENT_DIR / 'analysis_results' / (slug + '.json')
        if not result_path.exists():
            raise BuildError('missing analysis artifact: ' + slug)
        result = _read_json(result_path)
        errors = validate_result(case, result)
        if any(result.get(k) != v for k, v in artifact_fingerprints(case, SITE_ROOT.parent).items()):
            errors.append('stale analysis artifact')
        if errors:
            raise BuildError(slug + ': ' + '; '.join(errors))
        source_map(case, result)
        validate_paper_assets(case, result)
        analysis_results[slug] = result
    _prepare_output(output_dir)
    routes = {r['term_id']: r for r in analysis_catalog.get('term_routes', [])}
    def tutorials_for(term):
        route = routes.get(term['id'], {})
        if route.get('mode') == 'no-output':
            return []
        examples = select_analysis_examples(term['id'],route,analysis_cases)
        return examples[:3]
    (output_dir / "index.html").write_text(
        render_index(terms, preview=mode == "preview", topic_names=topic_names, topics=topics), encoding="utf-8"
    )
    for index,term in enumerate(terms):
        route = routes.get(term['id'], {})
        examples = tutorials_for(term) if route.get('mode') == 'tutorial' else []
        if examples:
            example = examples[0]
            term = {**term, 'paper_result_html': render_paper_result(example,analysis_results[example['id']])}
        if term['id'] in {'latent-profile-analysis','latent-class-analysis','ancova','mancova'}:
            term = {**term, 'r_practice': {**term['r_practice'], 'report_example': analysis_report_for_term(term['id'],analysis_catalog,analysis_cases,analysis_results)}}
        (output_dir / "terms" / f"{term['id']}.html").write_text(
            render_term(
                term,
                preview=mode == "preview",
                available_ids={value["id"] for value in terms},
                available_names={value["id"]: value["zh"] for value in terms},
                available_aliases={value["id"]: value.get("aliases", []) for value in terms},
                available_concepts={value['id']+'#'+concept['id']:concept.get('names',[concept['zh']]) for value in terms for concept in value.get('concepts',[])},
                visual=visuals.get(plain_visuals.get(term['id'], {}).get('reuse', term['id'])),
                plain_visual=plain_visuals.get(term['id']),
                formula_markup=formulas.get(term["id"]),
                topic_label=topic_names.get(term.get('topic'), ''),
                previous_term=terms[index-1] if index else None,
                next_term=terms[index+1] if index+1 < len(terms) else None,
                analysis_examples=tutorials_for(term),
            ), encoding="utf-8"
        )
    for slug, visual in visuals.items():
        if slug not in {term["id"] for term in terms}:
            continue
        for filename in (visual["file"], visual["mobile_file"]):
            target = output_dir / "assets" / "diagrams" / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ASSET_DIR / "diagrams" / filename, target)

    example_dir = output_dir / 'assets' / 'examples'
    for term in terms:
        entry = plain_visuals.get(term['id'], {})
        if entry.get('decision') != 'draw':
            continue
        example_dir.mkdir(parents=True, exist_ok=True)
        for mobile in (False, True):
            name = term['id'] + ('-mobile' if mobile else '') + '.svg'
            (example_dir / name).write_text(render_svg(entry, mobile), encoding='utf-8')
    _write_json(output_dir / 'plain-visual-coverage.json', {term['id']: plain_visuals.get(term['id'], {'decision': 'skip', 'reason': '尚未审查'}) for term in terms})

    (output_dir / "topics").mkdir(exist_ok=True)
    for topic in topics:
        members = [term for term in terms if term.get("topic") == topic.get("id")]
        (output_dir / "topics" / f"{topic['id']}.html").write_text(
            render_topic(topic, members, topics=topics, preview=mode == "preview"), encoding="utf-8"
        )

    paths_payload = _read_json(CONTENT_DIR / "paths.json")
    terms_by_id = {str(term.get("id")): term for term in terms}
    (output_dir / "paths.html").write_text(
        render_paths(paths_payload.get("paths", []), terms_by_id, network=paths_payload.get("network")), encoding="utf-8"
    )
    datasets_path = CONTENT_DIR / "datasets.json"
    datasets_payload = _read_json(datasets_path)
    (output_dir / "datasets.html").write_text(
        render_datasets(datasets_payload.get("datasets", [])), encoding="utf-8"
    )
    policy_path = CONTENT_DIR / "source_policy.json"
    policy_payload = _read_json(policy_path)
    (output_dir / "sources.html").write_text(
        render_sources(policy_payload), encoding="utf-8"
    )
    (output_dir / "practice.html").write_text(render_practice(), encoding="utf-8")
    (output_dir / 'symbols.html').write_text(render_reference(symbol_entries, terms_by_id), encoding='utf-8')
    (output_dir / 'analysis.html').write_text(render_analysis_index(analysis_catalog, analysis_cases), encoding='utf-8')
    if analysis_cases:
        (output_dir / 'analyses').mkdir(exist_ok=True)
        (output_dir / 'analysis-code').mkdir(exist_ok=True)
        (output_dir / 'analysis-logs').mkdir(exist_ok=True)
        names = {slug: term['zh'] for slug, term in terms_by_id.items()}
        term_topics = {slug: term['topic'] for slug, term in terms_by_id.items()}
        unit_topics = {unit['id']: unit['group'] for unit in analysis_catalog['units']}
        for slug, case in analysis_cases.items():
            (output_dir / 'analysis-logs' / (slug+'.txt')).write_text(analysis_results[slug]['stdout'], encoding='utf-8')
            (output_dir / 'analyses' / (slug + '.html')).write_text(render_analysis_case(case, analysis_results[slug], names, term_topics, unit_topics.get(case['unit_id'], 'foundations')), encoding='utf-8')
            shutil.copy2(SITE_ROOT.parent / case['script'], output_dir / 'analysis-code' / Path(case['script']).name)
            for filename in case.get('data_files', []):
                (output_dir / 'data').mkdir(exist_ok=True)
                shutil.copy2(SITE_ROOT.parent / filename, output_dir / 'data' / Path(filename).name)
        shutil.copy2(SITE_ROOT.parent / 'examples/r/output_reading/_common.R', output_dir / 'analysis-code/_common.R')
        shutil.copy2(SITE_ROOT.parent / 'examples/r/output_reading/_paper_supplement.R', output_dir / 'analysis-code/_paper_supplement.R')
        shutil.copy2(SITE_ROOT.parent / 'examples/r/output_reading/_prediction_supplement.R', output_dir / 'analysis-code/_prediction_supplement.R')
        shutil.copytree(ASSET_DIR / 'paper-results', output_dir / 'assets/paper-results')

    project_root = SITE_ROOT.parent
    for dataset in datasets_payload.get("datasets", []):
        download = dataset.get("download")
        source_file = dataset.get("source_file")
        if not download or not source_file:
            continue
        source_path = project_root / source_file
        if not source_path.is_file():
            raise BuildError(f"dataset source is missing: {source_file}")
        target_path = output_dir / download
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    search = _search_index(terms, topic_names) + analysis_search_entries(analysis_cases, analysis_catalog)
    quizzes = _quiz_bank(terms)
    graph = _graph(terms)
    _write_json(output_dir / "assets" / "data" / "search-index.json", search)
    _write_json(output_dir / "assets" / "data" / "quiz-bank.json", quizzes)
    (output_dir / "assets" / "data" / "site-data.js").write_text(
        "window.PsychSiteData = " + json.dumps({"search": search, "quizzes": [{key:value for key,value in q.items() if key != 'reading_html'} for q in quizzes], "topics": topics}, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    (output_dir / "assets" / "data" / "practice-data.js").write_text(
        "window.PsychPracticeData = " + json.dumps(quizzes, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    _write_json(output_dir / "assets" / "data" / "graph.json", graph)

    dataset_count = len(datasets_payload.get("datasets", []))
    source_paths.extend([CONTENT_DIR / "topics.json", CONTENT_DIR / "paths.json", datasets_path, policy_path])
    if analysis_path.exists():
        source_paths.append(analysis_path)
    source_paths.extend(sorted((CONTENT_DIR / 'analysis_cases').glob('*.json')))
    source_paths.extend(sorted((CONTENT_DIR / 'analysis_results').glob('*.json')))
    source_paths.extend(sorted((CONTENT_DIR / 'paper_results').glob('*.json')))
    source_paths.extend(sorted((CONTENT_DIR / 'prediction_results').glob('*.json')))
    source_paths.append(SITE_ROOT.parent / 'examples/r/output_reading/_prediction_supplement.R')
    if analysis_cases:
        source_paths.append(SITE_ROOT.parent / 'examples/r/output_reading/_common.R')
        for case in analysis_cases.values():
            source_paths.extend(SITE_ROOT.parent / p for p in [case['script'], *case.get('data_files', [])])
    if curriculum_path.is_file():
        source_paths.append(curriculum_path)
    if symbols_path.is_file():
        source_paths.append(symbols_path)
    if visuals_path.is_file():
        source_paths.append(visuals_path)
    source_paths.extend(ASSET_DIR / "diagrams" / filename for slug, visual in visuals.items() if slug in terms_by_id for filename in (visual["file"], visual["mobile_file"]))
    source_paths.extend(sorted((CONTENT_DIR / 'plain_visuals').glob('*.json')))
    source_paths.extend(ASSET_DIR / 'examples-v2' / filename
                        for slug, entry in plain_visuals.items() if slug in terms_by_id and entry.get('artwork')
                        for filename in (slug+'.svg', slug+'-mobile.svg'))
    reading_aids_path = CONTENT_DIR / "reading_aids.json"
    guides_path = CONTENT_DIR / 'analysis_guides.json'
    if guides_path.is_file():
        source_paths.append(guides_path)
    support_path = CONTENT_DIR / 'analysis_support.json'
    if support_path.is_file():
        source_paths.append(support_path)
    if reading_aids_path.is_file():
        source_paths.append(reading_aids_path)
    registry_path = CONTENT_DIR / "registry.json"
    if registry_path.exists():
        source_paths.append(registry_path)
    report = BuildReport(
        mode=mode,
        input_hash=_input_hash(source_paths),
        term_count=len(terms),
        page_count=len(list(output_dir.rglob('*.html'))),
        question_count=len(quizzes),
        dataset_count=dataset_count,
    )
    _write_json(output_dir / "build_report.json", asdict(report))

    for asset_name in ("site.css", "site.js", "search.js", "search-ui.js", "symbols.js", "practice.js", "theme.js", "filter-menu.js", "cursor.js", "favorites.js", "formula-reading.js", "card-transition.js", "navigation-policy.js", "page-runtime.js", "navigation-motion.js", "soft-navigation.js", "favicon.svg", "favicon.ico"):
        source = ASSET_DIR / asset_name
        if source.exists():
            shutil.copy2(source, output_dir / "assets" / asset_name)
    if (ASSET_DIR / 'analysis-reader.js').exists():
        shutil.copy2(ASSET_DIR / 'analysis-reader.js', output_dir / 'assets/analysis-reader.js')
        shutil.copy2(ASSET_DIR / 'analysis-reader.css', output_dir / 'assets/analysis-reader.css')
    vendor = ASSET_DIR / "vendor" / "katex"
    if vendor.is_dir():
        target = output_dir / "assets" / "vendor" / "katex"
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vendor / "katex.min.css", target / "katex.min.css")
        shutil.copy2(vendor / "LICENSE", target / "LICENSE")
        shutil.copytree(vendor / "fonts", target / "fonts")
    add_cache_busting(output_dir)
    return report
