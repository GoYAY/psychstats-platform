"""Extract five inexpensive prediction grids in isolated R sessions.

Original teaching results are never overwritten. Coefficients and metrics must
agree with saved R evidence before an appendix is accepted.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
APPENDIX = ROOT / 'examples/r/output_reading/_prediction_supplement.R'
CASES = ('linear-simple', 'linear', 'logistic', 'ancova', 'selection')


def main():
    destination = ROOT / 'site/content/prediction_results'
    destination.mkdir(parents=True, exist_ok=True)
    for slug in CASES:
        case = json.loads((ROOT / f'site/content/analysis_cases/{slug}.json').read_text(encoding='utf-8'))
        original = ROOT / f'site/content/analysis_results/{slug}.json'
        baseline = json.loads(original.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(prefix='psych-prediction-') as directory:
            work = Path(directory)
            shutil.copy2(ROOT / case['script'], work / 'analysis.R')
            for name in ('_common.R', '_prediction_supplement.R'):
                shutil.copy2(ROOT / 'examples/r/output_reading' / name, work / name)
            for file in case.get('data_files', []):
                shutil.copy2(ROOT / file, work / Path(file).name)
            wrapper = ('options(warn=1)\nsuppressWarnings(Sys.setlocale("LC_ALL","English_United States.utf8"))\n'
                       '.libPaths(c(.libPaths(),Sys.getenv("PSY_R_LIBRARY")))\n'
                       f'CASE_ID <- "{slug}"\nsource("analysis.R")\nsource("_prediction_supplement.R")\n')
            (work / 'run.R').write_text(wrapper, encoding='utf-8')
            run = subprocess.run(['C:/Program Files/R/R-4.5.1/bin/Rscript.exe', '--vanilla', 'run.R'],
                cwd=work, env=dict(os.environ, PSY_R_LIBRARY=str(ROOT / 'examples/r/library')),
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
            if run.returncode:
                raise RuntimeError(slug + ': ' + run.stderr)
            repeated = json.loads((work / 'result.json').read_text(encoding='utf-8'))
            if any(not math.isclose(value, repeated['metrics'][key], rel_tol=1e-10, abs_tol=1e-9)
                   for key,value in baseline['metrics'].items()):
                raise ValueError(slug + ': saved metrics disagree')
            payload = json.loads((work / 'prediction-result.json').read_text(encoding='utf-8'))
            saved = json.loads((ROOT / f'site/content/paper_results/{slug}.json').read_text(encoding='utf-8'))
            for row in saved['tables']['reported_coefficients']:
                if not math.isclose(payload['coefficients'][row['term']], row['estimate'], rel_tol=1e-10, abs_tol=1e-9):
                    raise ValueError(slug + ': coefficient differs: ' + row['term'])
            payload.update(case_id=slug, original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                           extractor_sha256=hashlib.sha256(APPENDIX.read_bytes()).hexdigest())
            (destination / (slug + '.json')).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            print(slug, 'prediction grid agrees with saved coefficients', flush=True)


if __name__ == '__main__':
    main()
