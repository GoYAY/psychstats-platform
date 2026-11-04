"""Validated, precomputed analysis examples; never execute R during a build."""
from __future__ import annotations

import json
import math
import hashlib
import re
from pathlib import Path
from string import Formatter


def artifact_fingerprints(case: dict, root: Path) -> dict:
    def path(name):
        p = (root / name).resolve()
        if not p.is_relative_to(root.resolve()):
            raise ValueError('analysis files must stay inside workspace')
        return p
    helper = root / 'examples/r/output_reading/_common.R'
    content = path(case['script']).read_bytes() + (helper.read_bytes() if helper.exists() else b'')
    return {'script_sha256': hashlib.sha256(content).hexdigest(),
            'config_sha256': hashlib.sha256(json.dumps(case, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            'data_sha256': {name: hashlib.sha256(path(name).read_bytes()).hexdigest()
                            for name in case.get('data_files', [])}}


def load_analysis_catalog(path: Path, term_ids: set[str]) -> dict:
    value = json.loads(path.read_text(encoding='utf-8'))
    units = value.get('units', [])
    ids = [u['id'] for u in units]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate analysis unit')
    routes = value.get('term_routes', [])
    routed = [r['term_id'] for r in routes]
    if len(routed) != len(set(routed)) or set(routed) != term_ids:
        raise ValueError('term routes must cover each available term exactly once')
    for route in routes:
        if route.get('mode') not in {'tutorial', 'branch', 'field', 'no-output'}:
            raise ValueError('invalid route mode')
        if not set(route.get('unit_ids', [])) <= set(ids):
            raise ValueError('missing route target')
        if not route.get('reason'):
            raise ValueError('route explanation is required')
    return value


def validate_catalog_cases(catalog: dict, cases: dict) -> None:
    claimed = []
    for unit in catalog.get('units', []):
        for slug in unit.get('case_ids', []):
            if slug not in cases or cases[slug].get('unit_id') != unit['id']:
                raise ValueError('missing or mismatched catalog case: ' + slug)
            claimed.append(slug)
    if len(claimed) != len(set(claimed)) or set(claimed) != set(cases):
        raise ValueError('catalog must list every case exactly once')


def load_analysis_cases(directory: Path) -> dict[str, dict]:
    cases = {}
    for path in sorted(directory.glob('*.json')):
        case = json.loads(path.read_text(encoding='utf-8'))
        slug = case['id']
        if slug != path.stem or slug in cases:
            raise ValueError('duplicate or mismatched analysis case ID')
        cases[slug] = case
    return cases


def select_analysis_examples(term_id: str, route: dict, cases: dict) -> list[dict]:
    matches=[c for c in cases.values() if c['unit_id'] in route.get('unit_ids',[])]
    preferred={'simple-linear-regression':'linear-simple',
               'spearman-correlation':'correlation','correlation-coefficient':'correlation',
               'partial-correlation':'correlation-types','multiple-regression':'linear',
               'cronbach-alpha':'reliability','internal-consistency':'reliability',
               'mcdonald-omega':'reliability-omega','reliability':'reliability',
               'fisher-exact-test':'categorical','interaction':'factorial-blocks',
               'robust-standard-errors':'diagnostics','sensitivity-analysis':'diagnostics',
               'data-cleaning':'diagnostics','repeated-measures':'repeated',
               'sphericity':'repeated','stepwise-regression':'selection',
               't-test':'t-tests','confidence-interval':'intervals',
               'wilcoxon-rank-sum':'ranks','wilcoxon-signed-rank':'ranks'}.get(term_id)
    return sorted(matches,key=lambda c:(c['id']!=preferred if preferred else c['id'] not in route.get('unit_ids',[]),c['id']))


def analysis_dependencies(case: dict, root: Path) -> list[str]:
    path = (root / case['script']).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('analysis files must stay inside workspace')
    code = path.read_text(encoding='utf-8')
    packages = {'jsonlite'} | set(re.findall(r'\b([A-Za-z][A-Za-z0-9.]*)::',code))
    packages.update(re.findall(r'\blibrary\(\s*[\"\x27]?([A-Za-z][A-Za-z0-9.]*)',code))
    if 'oblimin' in code:
        packages.add('GPArotation')
    return sorted(packages - {'base','stats','utils','graphics','grDevices','methods'})


def validate_result(case: dict, result: dict) -> list[str]:
    errors = []
    if result.get('case_id') != case['id']:
        errors.append('case ID mismatch')
    for key in ('script_sha256', 'config_sha256', 'session_info', 'stdout'):
        if not result.get(key):
            errors.append('missing execution evidence: ' + key)
    if not isinstance(result.get('data_sha256'), dict):
        errors.append('missing data fingerprints')
    if result.get('status') not in {'valid', 'diagnostic-demo'} or result.get('exit_code') != 0:
        errors.append('analysis did not complete successfully')
    if result.get('status') == 'diagnostic-demo' and not case.get('invalid_reason'):
        errors.append('diagnostic demonstration requires an invalidity explanation')
    metrics = result.get('metrics', {})
    if not isinstance(metrics, dict):
        errors.append('metrics must be an object')
        metrics = {}
    for key, number in metrics.items():
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            errors.append(key + ': metric must be finite')
    for key in metrics:
        if key.endswith('ci_lower'):
            upper = key[:-8] + 'ci_upper'
            if upper in metrics and all(isinstance(metrics[k], (int, float)) for k in (key,upper)) and metrics[key] > metrics[upper]:
                errors.append(key + ': inverted interval')
    tables = result.get('tables', {})
    if tables != [] and not isinstance(tables, dict):
        errors.append('tables must be an object or an empty list')
    if isinstance(tables, dict):
        for name, rows in tables.items():
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                errors.append(str(name) + ': table rows must be objects')
                continue
            for row in rows:
                for key, value in row.items():
                    if isinstance(value, float) and not math.isfinite(value):
                        errors.append(str(name) + ': nonfinite table cell ' + key)
                    elif value is not None and not isinstance(value, (str, int, float, bool)):
                        errors.append(str(name) + ': nonscalar table cell ' + key)
                for lower, upper in [('ci_lower','ci_upper'),('ci.lower','ci.upper'),('lwr','upr')]:
                    values = [row.get(lower),row.get(upper)]
                    if all(isinstance(v,(int,float)) for v in values) and values[0]>values[1]:
                        errors.append(str(name) + ': inverted table interval')
    fields = [a.get('field_id') for a in case.get('annotations', [])]
    if len(fields) != len(set(fields)) or any(not f for f in fields):
        errors.append('duplicate or empty annotation field')
    for field in fields:
        if field not in metrics:
            errors.append('missing annotated metric: ' + field)
    try:
        for _, field, _, _ in Formatter().parse(case.get('report_template', '')):
            if field and (field not in metrics or any(c in field for c in '.[')):
                errors.append('missing or unsafe report metric: ' + field)
    except ValueError:
        errors.append('invalid report template')
    return errors
