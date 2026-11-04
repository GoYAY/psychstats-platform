"""Run finite, local teaching analyses; normal website builds never run this."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'site'))
from sitegen.analysis_catalog import load_analysis_cases, validate_result, artifact_fingerprints


def local_path(value: str) -> Path:
    p = (ROOT / value).resolve()
    if not p.is_relative_to(ROOT):
        raise ValueError('analysis files must stay inside workspace')
    return p


def fingerprints(case: dict) -> dict:
    return artifact_fingerprints(case, ROOT)


def is_current(case: dict, result: dict) -> bool:
    try:
        return all(result.get(key) == value for key, value in fingerprints(case).items())
    except OSError:
        return False


def run_case(case: dict, *, rscript: Path, timeout: int = 180) -> dict:
    script = local_path(case['script'])
    result = {'case_id': case['id'], 'status': 'failed', 'exit_code': None,
              'session_info': '', 'stdout': '', 'stderr': '', 'metrics': {},
              'warnings': [], 'tables': [], 'figures': []}
    result.update(fingerprints(case))
    with tempfile.TemporaryDirectory(prefix='psych-output-') as directory:
        work = Path(directory)
        shutil.copy2(script, work / 'analysis.R')
        helper = ROOT / 'examples/r/output_reading/_common.R'
        if helper.exists():
            shutil.copy2(helper, work / '_common.R')
        names = set()
        for file in case.get('data_files', []):
            p = local_path(file)
            if p.name in names:
                raise ValueError('duplicate data basename')
            names.add(p.name)
            shutil.copy2(p, work / p.name)
        wrapper = '''options(warn=1)
suppressWarnings(Sys.setlocale("LC_ALL", "English_United States.utf8"))
.libPaths(c(.libPaths(), Sys.getenv("PSY_R_LIBRARY")))
tryCatch({ source("analysis.R", echo=FALSE)
  writeLines(capture.output(sessionInfo()), "session.txt")
}, error=function(e) { writeLines(conditionMessage(e), stderr()); quit(status=1) })
'''
        (work / 'run.R').write_text(wrapper, encoding='utf-8')
        try:
            environment = dict(os.environ, PSY_R_LIBRARY=str(ROOT / 'examples/r/library'),
                               LC_ALL='English_United States.utf8', LANG='English_United States.utf8')
            proc = subprocess.run([str(rscript), '--vanilla', 'run.R'], cwd=work, env=environment,
                                  capture_output=True, text=True, encoding='utf-8',
                                  errors='replace', timeout=timeout)
            result.update(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
            session = work / 'session.txt'
            if session.exists():
                result['session_info'] = session.read_text(encoding='utf-8', errors='replace')
            payload = work / 'result.json'
            if proc.returncode == 0 and payload.exists():
                data = json.loads(payload.read_text(encoding='utf-8'))
                for key in ('metrics', 'tables', 'figures'):
                    result[key] = data.get(key, {} if key == 'metrics' else [])
                result['status'] = 'valid' if data.get('valid', True) else 'diagnostic-demo' if case.get('invalid_reason') else 'failed'
            result['warnings'] = [line for line in proc.stderr.splitlines() if 'warning' in line.lower()]
        except (OSError, subprocess.TimeoutExpired, ValueError) as e:
            result['stderr'] = str(e)
    errors = validate_result(case, result)
    if errors:
        result['validation_errors'] = errors
        result['status'] = 'failed'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', action='append')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--only-stale', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    cases = load_analysis_cases(ROOT / 'site/content/analysis_cases')
    selected = args.case or list(cases)
    destination = ROOT / 'site/content/analysis_results'
    rscript = Path(os.environ.get('R_EXAMPLES_RSCRIPT', 'C:/Program Files/R/R-4.5.1/bin/Rscript.exe'))
    bad = []
    for slug in selected:
        if slug not in cases:
            parser.error('unknown analysis case: ' + slug)
        case = cases[slug]
        path = destination / (slug + '.json')
        existing = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        current = is_current(case, existing) and not validate_result(case, existing)
        if args.check or (args.only_stale and current):
            print(slug + ': ' + ('current' if current else 'missing/stale/invalid'), flush=True)
            if not current:
                bad.append(slug)
            continue
        result = run_case(case, rscript=rscript)
        destination.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(slug + ': ' + result['status'], flush=True)
        if result['status'] == 'failed':
            print(result['stderr'][-700:], flush=True)
            bad.append(slug)
    return int(bool(bad))


if __name__ == '__main__':
    raise SystemExit(main())
