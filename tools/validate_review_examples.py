"""Execute current draft R examples without regenerating content or promoting it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RSCRIPT = Path(os.environ.get('R_EXAMPLES_RSCRIPT', r'C:\Program Files\R\R-4.5.1\bin\Rscript.exe'))


def source_hash(practice: dict) -> str:
    keys = ('example_code', 'validation_code', 'your_data_code', 'packages')
    payload = {key: practice.get(key, [] if key == 'packages' else '') for key in keys}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def report_matches(practice: dict, result: dict) -> bool:
    return result.get('source_sha256') == source_hash(practice)


def validate_practice(term_id: str, practice: dict, *, timeout: float = 120) -> dict:
    result = dict(term_id=term_id, source_sha256=source_hash(practice), verified=False,
                  template_syntax_valid=False, template_execution='not-run-user-data-required',
                  stdout='', stderr='')
    env = os.environ.copy()
    env['R_LIBS_USER'] = str(ROOT / 'examples/r/library')
    with tempfile.TemporaryDirectory(prefix='psych-review-') as directory:
        work = Path(directory)
        for data in (ROOT / 'examples/data').glob('*.csv'):
            shutil.copy2(data, work / data.name)
        packages = '\n'.join('library(' + json.dumps(str(name)) + ')' for name in practice.get('packages', []))
        prefix = 'if (.Platform$OS.type=="windows") suppressWarnings(Sys.setlocale("LC_ALL","English_United States.utf8"))\n'
        (work / 'example.R').write_text(prefix + packages + '\n' + practice.get('example_code', '') + '\n' + practice.get('validation_code', ''), encoding='utf-8')
        (work / 'template.R').write_text(practice.get('your_data_code', ''), encoding='utf-8')
        try:
            run = subprocess.run([str(RSCRIPT), '--vanilla', 'example.R'], cwd=work, env=env,
                                 capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
            result.update(verified=run.returncode == 0, stdout=run.stdout, stderr=run.stderr)
        except subprocess.TimeoutExpired:
            result['stderr'] = 'example timeout'
        except OSError as error:
            result['stderr'] = str(error)
        try:
            parsed = subprocess.run([str(RSCRIPT), '--vanilla', '-e', 'invisible(parse("template.R"))'],
                                    cwd=work, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
            result['template_syntax_valid'] = parsed.returncode == 0
            if parsed.returncode:
                result['stderr'] += '\nTemplate parse: ' + parsed.stderr
        except (OSError, subprocess.TimeoutExpired) as error:
            result['stderr'] += '\nTemplate parse: ' + str(error)
    return result


def validate_terms(term_ids: list[str] | None) -> list[dict]:
    paths = sorted((ROOT / 'site/content/drafts').glob('*.json'))
    terms = {path.stem: json.loads(path.read_text(encoding='utf-8')) for path in paths}
    selected = term_ids if term_ids is not None else [slug for slug, term in terms.items() if term.get('r_practice')]
    results = []
    for slug in selected:
        if slug not in terms:
            raise ValueError(f'Unknown term: {slug}')
        practice = terms[slug].get('r_practice')
        if not practice:
            continue
        result = validate_practice(slug, practice)
        print(f"{slug}: example={result['verified']} template-parse={result['template_syntax_valid']}", flush=True)
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terms', nargs='+')
    parser.add_argument('--report', default='logs/content-depth-final-r.json')
    args = parser.parse_args()
    results = validate_terms(args.terms)
    report_path = (ROOT / args.report).resolve()
    if not report_path.is_relative_to(ROOT / 'logs'):
        parser.error('Report must stay inside workspace logs/')
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(dict(results=results), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if any(not row['verified'] or not row['template_syntax_valid'] for row in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
