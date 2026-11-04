"""Generate redistributable license texts from the exact installed runtime.

Copies license files, not Python code or user data. Optional wheel inspection
adds platform-specific native dependency notices without installing binaries.
"""
import argparse
import hashlib
from importlib.metadata import distribution
import json
from pathlib import Path
import re
import zipfile


def collect(lock,output,wheels=None):
    output=Path(output)
    if output.exists():raise FileExistsError('Notice snapshot is immutable')
    entries=[];files={}
    for line in Path(lock).read_text(encoding='utf-8').splitlines():
        match=re.match(r'^([\w.-]+)==([^;\s]+)',line)
        if not match:continue
        name,wanted=match.groups()
        try:dist=distribution(name)
        except Exception:
            if 'platform_system == "Windows"' in line:continue
            raise
        if dist.version!=wanted:raise ValueError('Runtime version differs from lock: '+name)
        licenses=[]
        for relative in dist.files or []:
            # Keep complete trees of bundled native dependency license texts.
            parts=[p.casefold() for p in relative.parts]
            if not (any('license' in p or p=='copying' or p=='notice' for p in parts)):continue
            path=dist.locate_file(relative)
            if not path.is_file() or path.suffix in ('.py','.pyc','.so','.dll','.pyd'):continue
            safe=Path(str(relative).replace('..','_')).as_posix()
            target=name+'/'+safe;files[target]=path.read_bytes();licenses.append(target)
        if not licenses:
            # Some distributions store the full license in METADATA.
            value=dist.metadata.get('License','')
            if len(value)<300:raise ValueError('Full license text missing: '+name)
            target=name+'/LICENSE-METADATA.txt';files[target]=value.encode();licenses.append(target)
        entries.append(dict(name=name,version=dist.version,licenseExpression=dist.metadata.get('License-Expression',dist.metadata.get('License','').split('\n')[0]),files=licenses))
    if wheels:
        for path in sorted(Path(wheels).glob('*.whl')):
            with zipfile.ZipFile(path) as wheel:
                for name in wheel.namelist():
                    parts=Path(name).parts
                    if any(p in ('..','') for p in parts) or name.startswith('/'):raise ValueError('Unsafe wheel entry')
                    if not any('license' in p.casefold() or p.casefold() in ('copying','notice') for p in parts):continue
                    if name.endswith('/') or Path(name).suffix in ('.py','.pyc','.so','.dll','.pyd'):continue
                    files['linux-wheels/'+path.stem+'/'+name]=wheel.read(name)
    output.mkdir(parents=True)
    for name,raw in files.items():
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    inventory=dict(version=1,scope='Installed locked runtime plus optional Linux wheel notices; not a legal compliance opinion',packages=entries,files=[dict(path=n,sha256=hashlib.sha256(c).hexdigest(),bytes=len(c)) for n,c in sorted(files.items())])
    (output/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
    return dict(packages=len(entries),licenseFiles=len(files))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lock',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--wheels',type=Path);a=p.parse_args()
    print(json.dumps(collect(a.lock,a.output,a.wheels)))
