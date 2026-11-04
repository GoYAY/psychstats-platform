"""Portable private-library packages from already validated teaching artefacts."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import mimetypes
from pathlib import Path
import re
import zipfile
from .contract import validate_request,validate_result
from .literature import _sources,work_identity

def _bytes(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def public_catalogue(site):
    """Project official metadata only where the actual public page exists."""
    site=Path(site);path=site/'assets/data/search-index.json'
    entries=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
    terms=[]
    for item in entries:
        key=item.get('id','')
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',key) or not (site/'terms'/(key+'.html')).is_file():continue
        terms.append(dict(id=key,zh=item['zh'],en=item.get('en',''),aliases=item.get('aliases',[]),published=True,path='terms/'+key+'.html',url='https://cdst.site/psy-stats/terms/'+key+'.html'))
    return dict(catalogueVersion=hashlib.sha256(_bytes(terms)).hexdigest()[:16],terms=terms)
def _hash(value):return hashlib.sha256(value).hexdigest()
def _id(prefix,value):return prefix+'-'+_hash(_bytes(value))[:32]

def _no_credentials(value):
    forbidden={'apikey','authorization','accesstoken','refreshtoken','password','orders','balance','clientsecret','apisecret','bearertoken'}
    if isinstance(value,dict):
        if any(re.sub(r'[^a-z0-9]','',str(k).lower()) in forbidden for k in value):raise ValueError('Credential/account data cannot enter a personal library package')
        for item in value.values():_no_credentials(item)
    elif isinstance(value,list):
        for item in value:_no_credentials(item)

def export_package(request,lesson,*,sources,originals,figures,term_id,output,archive_sources=()):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}',term_id):raise ValueError('Invalid stable personal term ID')
    reading=validate_request(dict(request,sources=sources))
    result=asdict(validate_result(lesson,reading));_no_credentials(result)
    archives=_sources(list(archive_sources))
    if len(archives)>10 or any(s['scope']!='full_text' or len(s['text'])>120000 for s in archives) or sum(len(s['text']) for s in archives)>1200000:raise ValueError('Original archive text exceeds explicit limits')
    all_sources=_sources(reading.sources+archives)
    if set(originals)-{s['id'] for s in all_sources}:raise ValueError('An original must belong to an explicit provided source')
    revision_id=_id('rev',result)
    package=dict(schemaVersion=1,packageId='',terms=[],revisions=[],works=[],sources=[],evidence=[],edges=[],annotations=[],assets=[])
    files={};mime={};source_map={};work_ids=set();evidence_ids=[]
    for source in all_sources:
        source=deepcopy(source);_no_credentials(source)
        work_key=work_identity(source)
        work_id=_id('work',work_key)
        if work_id not in work_ids:
            package['works'].append(dict(id=work_id,title=source['title'],doi=source.get('doi',''),authors=source.get('authors',[]),year=source.get('year'),url=source.get('url','')));work_ids.add(work_id)
        source_id=_id('source',dict(work=work_id,text=source.get('text',''),scope=source.get('scope'),localId=source['id']))
        source_map[source['id']]=source_id
        record=dict(id=source_id,localId=source['id'],workId=work_id,scope=source['scope'],origin=source.get('origin','user'),blobHash=None,originalStatus='missing',fileName=None)
        if source['id'] in originals:
            path=Path(originals[source['id']]);data=path.read_bytes()
            if len(data)>128*1024*1024:raise ValueError('Original exceeds 128 MiB package limit')
            if data.startswith(b'%PDF-'):extension='.pdf';original_mime='application/pdf'
            elif path.suffix.lower()=='.txt':
                data.decode('utf-8-sig')
                if b'\x00' in data:raise ValueError('Text original contains binary content')
                extension='.txt';original_mime='text/plain'
            else:raise ValueError('Selected original is not a PDF or UTF-8 text')
            digest=_hash(data);name='originals/'+digest+extension;files[name]=data;mime[name]=original_mime
            record.update(blobHash=digest,originalStatus='saved',fileName=path.with_suffix(extension).name)
        package['sources'].append(record)
        eid=_id('evidence',dict(source=source_id,revision=revision_id,data=source))
        package['evidence'].append(dict(id=eid,sourceId=source_id,revisionId=revision_id,data=source));evidence_ids.append(eid)
    asset_ids=[]
    for role,filename in sorted(figures.items()):
        path=Path(filename);suffix=path.suffix.lower()
        if suffix not in {'.svg','.png','.jpg','.jpeg','.pdf'}:raise ValueError('Unsupported figure type')
        data=path.read_bytes();digest=_hash(data);name='assets/'+digest+suffix;files[name]=data
        mime[name]=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        aid=_id('asset',dict(hash=digest,role=role));asset_ids.append(aid)
        package['assets'].append(dict(id=aid,role=role,path=name,blobHash=digest,mime=mime[name],size=len(data),alt=(result.get('visual') or {}).get('alt','')))
    identity=result.get('provenance',{}).get('verified_identity') or {}
    package['terms'].append(dict(id=term_id,zh=result['term']['zh'],en=result['term'].get('en') or identity.get('en',''),aliases=result['term'].get('aliases',[]),anchor=deepcopy(request['term']),tags=[],currentRevisionId=revision_id,trashed=False))
    target_spaces={t['id']:{'classic':'official','personal':'personal','pending':'pending'}[t['kind']] for t in reading.catalog+reading.known_terms}
    package['revisions'].append(dict(id=revision_id,termId=term_id,lesson=result,sourceIds=list(source_map.values()),sourceMap=source_map,evidenceIds=evidence_ids,assetIds=asset_ids,provenance=deepcopy(result['provenance']),targetSpaces=target_spaces))
    catalog={t['id']:t for t in reading.catalog+reading.known_terms}
    for relation in result['relations']:
        target=catalog[relation['target']]
        edge=dict(from_={'space':'personal','id':term_id},to={'space':{'classic':'official','personal':'personal','pending':'pending'}[target['kind']],'id':target['id']},type=relation['type'],reason=relation['reason'],refs=relation['refs'],status='suggested',origin='model',revisionId=revision_id)
        edge['from']=edge.pop('from_');edge['id']=_id('edge',edge);package['edges'].append(edge)
    package['packageId']=_id('pkg',package)
    files['library.json']=_bytes(package);mime['library.json']='application/json'
    manifest=dict(schemaVersion=1,kind='personal-library-backup',packageId=package['packageId'],files=[dict(path=name,hash=_hash(data),size=len(data),mime=mime[name]) for name,data in sorted(files.items())])
    files['manifest.json']=_bytes(manifest)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix(output.suffix+'.pending')
    try:
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in sorted(files.items()):
                info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o600<<16
                archive.writestr(info,data)
        temporary.replace(output)
    finally:
        if temporary.exists():temporary.unlink()
    return dict(packageId=package['packageId'],terms=1,revisions=1,works=len(package['works']),originals=len([x for x in files if x.startswith('originals/')]),missingOriginals=len([s for s in package['sources'] if s['originalStatus']=='missing']),files=len(files),output=str(output))
