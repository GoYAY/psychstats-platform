"""Composition of source routing, teaching compilation and private delivery."""
from copy import deepcopy
from dataclasses import asdict
from io import BytesIO
from .config import OnlineError
from .sources import parse_source,prepare_sources
from .worker import Worker
from .delivery import build_delivery
from ..contract import validate_request
from ..pipeline import PipelineReply,generate_prepared_lesson
from ..frameworks import validate_input,analyze_frameworks
from ..section_reading import memory_anchor

def visual_host_for_config(config):
    """Capabilities come from verified server files, never client packages."""
    if not config.visual_intent_enabled:return None
    import json,re,hashlib
    root=config.public_root
    try:
        report=json.loads((root/'library-build.json').read_bytes());directory=report.get('chartDirectory');entry=report.get('chartEntry')
        if type(report.get('visualPresentationVersion')) is not int or report['visualPresentationVersion']!=1 or not isinstance(directory,str) or not re.fullmatch(r'charts-[a-f0-9]{16}',directory):return None
        base=root/'assets'/directory
        if base.is_symlink() or not base.resolve().is_relative_to(root.resolve()):return None
        manifest=json.loads((base/'manifest.json').read_bytes())
        if manifest.get('version')!=1 or manifest.get('entry')!=entry or not isinstance(manifest.get('resources'),list) or not 1<=len(manifest['resources'])<=256:return None
        if directory!='charts-'+hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:16]:return None
        seen=set();total=0
        for row in manifest['resources']:
            name=row.get('file');expected=row.get('sha256')
            if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]*',name) or '..' in name.split('/') or name in seen:return None
            path=base/name
            if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):return None
            content=path.read_bytes();total+=len(content)
            if total>5000000 or hashlib.sha256(content).hexdigest()!=expected:return None
            seen.add(name)
        if not isinstance(entry,str) or entry not in seen or not entry.endswith(('.js','.mjs')):return None
        return dict(interactive_chart_types=['bar'])
    except (OSError,ValueError,TypeError,KeyError,AttributeError):return None

def advance_job(job,store,files,provider):
    try:return _advance_job(job,store,files,provider)
    except Exception as error:
        # Private hashes only. No article/model contents in diagnostics or logs.
        target=getattr(provider,'last_generation',None)
        if target:error.recovery_target=deepcopy(target)
        raise


def _advance_job(job,store,files,provider):
    config=provider.config;clock=provider.clock;worker=Worker(config,store,runner=None,clock=clock)
    manifest=job['manifest']
    if manifest.get('model_allowed') is not True:raise OnlineError('model_consent_required','请先确认本次资料发送范围及模型使用。',403)
    current=job;checkpoint=deepcopy(job.get('checkpoint') or {});visual_host=visual_host_for_config(config)
    def save(stage,**changes):
        nonlocal current
        checkpoint.update(changes)
        current=worker.publish(job,'running',{'stage':stage,'checkpoint':checkpoint})
    if job['kind']=='organize':
        value=validate_input(manifest['input']);save('organizing')
        result=analyze_frameworks(value,provider)
        import json
        data=json.dumps(result,ensure_ascii=False,allow_nan=False).encode()
        descriptor=files.put(job['id'],'organization.json',BytesIO(data),config.limits)
        return worker.publish(job,'complete',{'stage':'ready','result':descriptor,'usage':{'calls':provider.calls}})
    request=deepcopy(manifest['request']);request['network_allowed']=bool(manifest.get('network_allowed',False))
    if 'documents' not in checkpoint:
        documents=[]
        for descriptor in manifest.get('documents',[]):
            path=files.path_for(job['id'],descriptor['asset_id'])
            documents.append(parse_source(path,descriptor,config.limits))
        save('checking_sources',documents=documents)
    if 'decision' not in checkpoint or checkpoint['decision'].get('action')!='ready':
        decision=prepare_sources(request,checkpoint['documents'],provider,lambda value:save('reading',decision=value),state=checkpoint.get('decision'),limits=config.limits)
        checkpoint['decision']=decision
        if decision['action']!='ready':
            return worker.publish(job,'waiting_input',{'stage':'confirmation','question':decision['question'],'checkpoint':checkpoint})
    decision=checkpoint['decision'];sources=decision['sources']
    if 'lesson' not in checkpoint:
        save('compiling')
        validated=validate_request(dict(decision['request'],sources=sources))
        prepared=PipelineReply('ready_for_explanation',memory_anchor(validated),evidence=decision['evidence'])
        reply=generate_prepared_lesson(validated,provider,prepared,visual_host=visual_host,visual_policy_version=1 if config.visual_intent_enabled else 0)
        if reply.lesson is None or reply.lesson.status!='complete':raise OnlineError('lesson_incomplete','科普尚未达到交付要求，已有阅读记录保留。')
        save('rendering',lesson=asdict(reply.lesson))
    # Include user originals as distinct source records even when evidence used a
    # selected excerpt; never pretend excerpt coordinates refer to a full PDF.
    combined=deepcopy(sources);originals={}
    for doc,descriptor in zip(checkpoint['documents'],manifest.get('documents',[])):
        source=doc['source']
        if source['id'] not in {s['id'] for s in combined}:combined.append(source)
        originals[source['id']]=files.path_for(job['id'],descriptor['asset_id'])
    lesson=deepcopy(checkpoint['lesson'])
    lesson.setdefault('provenance',{})['document_readings']=[dict(source_id=doc['source']['id'],original_sha256=doc['sha256'],handled_sections=decision.get('readings',{}).get(doc['source']['id'],{}).get('next_section',0),total_sections=len(decision.get('readings',{}).get(doc['source']['id'],{}).get('sections',[])),source_mapping=decision.get('selections',{}).get(doc['source']['id'],{}).get('mapping',[])) for doc in checkpoint['documents']]
    save('rendering')
    result=build_delivery(job,decision['request'],lesson,combined,files,originals=originals,qa_dir=config.figure_qa_dir,font_path=config.cjk_font,provider=provider,on_visual_repair=lambda value:save('rendering',lesson=value),visual_host=visual_host,
        quality_state=checkpoint.get('visual_quality'),on_quality_checkpoint=lambda value:save('rendering',visual_quality=value),allow_quality_calls=config.visual_intent_enabled)
    return worker.publish(job,'complete',{'stage':'ready','result':result,'usage':{'calls':provider.calls},'question':None})
