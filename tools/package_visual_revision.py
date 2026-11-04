"""Package a new visual revision while preserving the accepted private archive."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from term_explainer.library_export import export_package

COLLECTIONS=('terms','revisions','works','sources','evidence','edges','annotations','assets')
def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def merge_revision(old,new):
    result=deepcopy(old)
    for kind in COLLECTIONS:
        rows={r['id']:r for r in result[kind]}
        for row in new[kind]:
            current=rows.get(row['id'])
            if current is None:
                result[kind].append(deepcopy(row));rows[row['id']]=result[kind][-1]
            elif kind=='terms':current['currentRevisionId']=row['currentRevisionId']
            elif kind=='sources':
                # Identity is content based. A revision without a fresh original
                # must retain the already archived bytes and their saved status.
                before={k:v for k,v in current.items() if k not in ('blobHash','originalStatus','fileName')}
                after={k:v for k,v in row.items() if k not in ('blobHash','originalStatus','fileName')}
                if before!=after:raise ValueError('Conflicting source identity')
                if current.get('originalStatus')!='saved':current.update(deepcopy(row))
            elif current!=row:raise ValueError('Conflicting immutable record: '+kind)
    result['packageId']='pkg-'+hashlib.sha256(encoded({k:v for k,v in result.items() if k!='packageId'})).hexdigest()[:32]
    return result

def package_revision(old_archive,revision,output):
    old_archive=Path(old_archive).resolve();revision=Path(revision).resolve();output=Path(output).resolve()
    if output==old_archive or output.is_relative_to(ROOT/'site'):raise ValueError('Preserve private input and keep output outside HTTP roots')
    if output.exists():raise ValueError('Revision archive already exists; do not overwrite')
    with zipfile.ZipFile(old_archive) as z:
        manifest=json.loads(z.read('manifest.json'));old=json.loads(z.read('library.json'))
        files={}
        for entry in manifest['files']:
            data=z.read(entry['path'])
            if len(data)!=entry['size'] or hashlib.sha256(data).hexdigest()!=entry['hash']:raise ValueError('Input archive hash mismatch')
            files[entry['path']]=data
    lesson=json.loads((revision/'lesson.json').read_text(encoding='utf-8'))
    request=json.loads((revision/'render-request.json').read_text(encoding='utf-8'))
    sources=json.loads((revision/'evidence.json').read_text(encoding='utf-8'))['sources']
    with tempfile.TemporaryDirectory(prefix='visual-revision-') as scratch:
        path=Path(scratch)/'new.zip'
        export_package(request,lesson,sources=sources,originals={},figures={role:revision/'figures'/name for role,name in [('desktop','figure.svg'),('mobile','figure-mobile.svg')]},term_id=lesson['term']['id'],output=path)
        with zipfile.ZipFile(path) as z:
            new=json.loads(z.read('library.json'))
            for entry in json.loads(z.read('manifest.json'))['files']:
                if entry['path']!='library.json':files[entry['path']]=z.read(entry['path'])
    merged=merge_revision(old,new);files['library.json']=encoded(merged)
    descriptors={entry['path']:entry for entry in manifest['files']}
    for asset in merged['assets']:descriptors[asset['path']]={'mime':asset['mime']}
    manifest={'schemaVersion':1,'kind':'personal-library-backup','packageId':merged['packageId'],'files':[{'path':name,'hash':hashlib.sha256(data).hexdigest(),'size':len(data),'mime':descriptors[name]['mime']} for name,data in sorted(files.items())]}
    files['manifest.json']=encoded(manifest)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):z.writestr(name,data)
    return {'output':str(output),'revisions':len(merged['revisions']),'originals':sum(n.startswith('originals/') for n in files),'model_calls':0,'old_preserved':True}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--old',type=Path,required=True);p.add_argument('--revision',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(package_revision(a.old,a.revision,a.output),ensure_ascii=False,indent=2))
