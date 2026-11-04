"""Private, reproducible canvas cases and separately specified evaluation assertions."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.official_knowledge_graph import official_graph
from tools.read_term_sections import atomic_write
from tools.package_visual_revision import merge_revision,encoded

def prepare_cases(output):
    output=Path(output).resolve()
    if output.is_relative_to(ROOT/'site'):raise ValueError('Private cases must stay outside HTTP roots')
    output.mkdir(parents=True,exist_ok=True)
    source=ROOT/'logs/local-library/private-fixtures/three-case-library.zip'
    files={};descriptors={}
    def read_archive(path):
        with zipfile.ZipFile(path) as z:
            manifest=json.loads(z.read('manifest.json'))
            for entry in manifest['files']:
                data=z.read(entry['path'])
                if len(data)!=entry['size'] or hashlib.sha256(data).hexdigest()!=entry['hash']:raise ValueError('Private input hash mismatch')
                if entry['path']!='library.json':
                    if entry['path'] in files and files[entry['path']]!=data:raise ValueError('Conflicting asset bytes')
                    files[entry['path']]=data;descriptors[entry['path']]=entry
            return json.loads(z.read('library.json'))
    # Use original accepted exports: the browser-made combined backup adds
    # resolved targetSpace metadata to old immutable revision IDs.
    fixture_root=source.parent
    records=merge_revision(read_archive(fixture_root/'dtp.zip'),read_archive(fixture_root/'cognitive-drift.zip'))
    revised=ROOT/'logs/operational-teaching-visuals/private/human-ai-entanglement-operational-final.zip'
    if revised.is_file():records=merge_revision(records,read_archive(revised))
    else:records=merge_revision(records,read_archive(fixture_root/'human-ai-entanglement.zip'))
    records['schemaVersion']=2;records['graphViews']=[]
    term=next(t for t in records['terms'] if t['id']=='human-ai-entanglement')
    revision=next(r for r in records['revisions'] if r['id']==term['currentRevisionId'])
    glossary={g['id']:g for g in revision['lesson']['glossary']}
    contexts=[dict(id='ctx-'+identifier,revisionId=revision['id'],glossaryId=identifier) for identifier in ['g-behavioral-drift','g-metacognition','g-metacognitive-monitoring','g-metacognitive-control']]
    for c in contexts:
        if c['glossaryId'] not in glossary:raise ValueError('Expected accepted glossary entry missing')
    members=[{'space':'personal','id':i} for i in ['human-ai-entanglement','cognitive-drift']]+[{'space':'pending','id':c['id']} for c in contexts]
    view=dict(id='human-ai',title='人–AI交互框架',frameworkId='human-ai',mode='structure',nodes=[],groups=[dict(id='human-ai-group',title='人–AI交互框架',origin='model',members=members,sourceRef={'kind':'revision','id':revision['id']})],contextRefs=contexts,excludedRefs=[],viewport=dict(x=20,y=20,scale=1),updatedAt='2026-10-20T00:00:00.000Z')
    records['graphViews']=[view]
    records['packageId']='canvas-cases-'+hashlib.sha256(encoded({k:v for k,v in records.items() if k!='packageId'})).hexdigest()[:32]
    files['library.json']=encoded(records);descriptors['library.json']={'mime':'application/json'}
    manifest={'schemaVersion':2,'kind':'personal-library-backup','packageId':records['packageId'],'files':[{'path':name,'hash':hashlib.sha256(data).hexdigest(),'size':len(data),'mime':descriptors[name]['mime']} for name,data in sorted(files.items())]}
    with zipfile.ZipFile(output/'three-case-canvas-v2.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted({**files,'manifest.json':encoded(manifest)}.items()):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
    oracle={
      'human-ai':{'personalIds':['human-ai-entanglement','cognitive-drift','dominant-trait-profile'],'contextCount':4,'edge':['human-ai-entanglement','next','cognitive-drift'],'isolated':'dominant-trait-profile','unpublishedContexts':True},
      'factor-analysis':{'coreCount':26,'distinct':['efa','pca'],'contrasts':['efa','cfa'],'prerequisites':['efa','correlation-coefficient'],'components':['efa','factor-extraction'],'sharedBridge':'icc'},
      'multilevel-longitudinal':{'coreCount':14,'distinct':['random-intercept-model','intercept'],'sharedBridge':'icc','componentsCount':11,'preserveNext':True}
    }
    public=official_graph(ROOT/'site/paper-table-audit-preview',ROOT/'site/content/registry.json')
    inputs=[fixture_root/'dtp.zip',fixture_root/'cognitive-drift.zip',revised if revised.is_file() else fixture_root/'human-ai-entanglement.zip']
    case={'records':records,'viewId':'human-ai','sourceHashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'newTeachingRelations':[],'warnings':['辅助词选入只代表框架分组；未另造语义边。']}
    result={'human-ai':case,'factor-analysis':{'frameworkId':'factor-analysis'},'multilevel-longitudinal':{'frameworkId':'multilevel-longitudinal'},'oracle':oracle}
    for key,value in result.items():atomic_write(output/(key+'.json'),value)
    atomic_write(output/'official-audit.json',{'frameworks':public['frameworks'],'warnings':public['warnings'],'sourceHashes':public['sourceHashes']})
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'logs/knowledge-canvas/private-cases');a=p.parse_args();r=prepare_cases(a.output)
    print(json.dumps({'cases':list(r),'modelCalls':0,'privateOutput':str(a.output)},ensure_ascii=False))
