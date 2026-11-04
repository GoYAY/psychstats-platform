"""Isolate a complete visual preview without rerunning statistics or replacing dist."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]

def prepare(output):
    source = (ROOT / 'site/dist').resolve()
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT / 'site') or output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Preview must be isolated inside site, outside the accepted dist')
    shutil.copytree(source, output, dirs_exist_ok=True)
    relative = 'assets/navigation-motion.js'
    resource = ROOT / 'site' / relative
    shutil.copy2(resource, output / relative)
    version = hashlib.sha256(resource.read_bytes()).hexdigest()[:16]
    for page in output.rglob('*.html'):
        text = page.read_text(encoding='utf-8')
        updated = re.sub(r'(assets/navigation-motion\.js\?v=)[^"\s]+', lambda m:m.group(1)+version, text)
        if text != updated:
            page.write_text(updated, encoding='utf-8')
    return {'output':str(output),'motionHash':version,'statisticsRerun':False,'distPreserved':True}

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'site/body-motion-preview'));args=parser.parse_args()
    print(json.dumps(prepare(args.output),ensure_ascii=False))
