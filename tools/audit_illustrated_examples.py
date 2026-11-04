"""Nature-figure audit runner; all reports are kept beside the final PDFs."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = Path.home() / '.codex/skills/nature-figure/scripts'
OUT = ROOT / 'logs/figure-v2'
sys.path.insert(0, str(ROOT / 'site'))
from sitegen.illustrated_examples import SLUGS


def main():
    checks = []
    required = [OUT / (slug+suffix+'.pdf') for slug in SLUGS for suffix in ('', '-mobile')]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        print('Missing required figure PDFs: '+', '.join(missing), flush=True)
        return True
    commands = [[str(SKILL/'validate_figure.py'), str(ROOT/'site/sitegen/illustrated_examples.py')]]
    for pdf in required:
        commands.extend([
            [str(SKILL/'audit_pdf_text.py'), str(pdf), '--min-pt', '5'],
            [str(SKILL/'audit_figure_collisions.py'), str(pdf), '--json-out', str(pdf.with_suffix('.collision.json')),
             '--overlay-pdf', str(pdf.with_suffix('.collision.pdf'))],
        ])
    for command in commands:
        result = subprocess.run([sys.executable, *command], capture_output=True, text=True, encoding='utf-8')
        checks.append({'command': command, 'returncode': result.returncode, 'output': result.stdout+result.stderr})
        print(Path(command[0]).name, Path(command[1]).name, result.returncode, flush=True)
    (OUT/'audit-summary.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
    failures = [c for c in checks if c['returncode'] != 0]
    for c in failures:
        print(c['output'], flush=True)
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())
