"""Targeted missing path extraction; never called by an ordinary website build."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
APPENDIX = ROOT / 'examples/r/output_reading/_paper_supplement.R'


def main():
    destination = ROOT / 'site/content/paper_results'
    destination.mkdir(parents=True, exist_ok=True)
    for slug in ('conditional-mediation', 'mediated-interaction', 'moderation',
                 'linear','linear-simple','logistic','ancova','selection',
                 'hierarchical','kmeans','lpa','t-tests','t-single',
                 'cfa','sem','path','mediation','latent-mediation','latent-interaction',
                 'feedback','growth','invariance','multigroup','reliability-omega'):
        case_path = ROOT / f'site/content/analysis_cases/{slug}.json'
        original = ROOT / f'site/content/analysis_results/{slug}.json'
        case = json.loads(case_path.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(prefix='psych-paper-') as directory:
            work = Path(directory)
            shutil.copy2(ROOT / case['script'], work / 'analysis.R')
            for name in ('_common.R', '_paper_supplement.R'):
                shutil.copy2(ROOT / 'examples/r/output_reading' / name, work / name)
            for name in case.get('data_files', []):
                shutil.copy2(ROOT / name, work / Path(name).name)
            wrapper = ('options(warn=1)\nsuppressWarnings(Sys.setlocale("LC_ALL","English_United States.utf8"))\n'
                       '.libPaths(c(.libPaths(),Sys.getenv("PSY_R_LIBRARY")))\n'
                       f'CASE_ID <- "{slug}"\nsource("analysis.R")\nsource("_paper_supplement.R")\n')
            (work / 'run.R').write_text(wrapper, encoding='utf-8')
            run = subprocess.run(['C:/Program Files/R/R-4.5.1/bin/Rscript.exe','--vanilla','run.R'],
                cwd=work, env=dict(os.environ,PSY_R_LIBRARY=str(ROOT/'examples/r/library'),
                                  LC_ALL='English_United States.utf8',LANG='English_United States.utf8'),
                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
            if run.returncode:
                raise RuntimeError(slug+': '+run.stderr)
            baseline = json.loads(original.read_text(encoding='utf-8'))
            repeated = json.loads((work/'result.json').read_text(encoding='utf-8'))
            for key, value in baseline['metrics'].items():
                if abs(value-repeated['metrics'][key]) > 1e-9:
                    raise ValueError(f'{slug}: original metric changed: {key}')
            extra = json.loads((work/'paper-result.json').read_text(encoding='utf-8'))
            extra.update(case_id=slug,original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                         extractor_sha256=hashlib.sha256(APPENDIX.read_bytes()).hexdigest())
            (destination/(slug+'.json')).write_text(json.dumps(extra,ensure_ascii=False,indent=2),encoding='utf-8')
            print(slug, 'verified against original metrics', flush=True)


if __name__ == '__main__':
    main()
