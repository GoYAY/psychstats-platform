"""Safe figures plus the existing portable-library contract, never model HTML."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import hashlib,os
from ..contract import validate_request,validate_result,used_source_ids
from ..figures import COLLISION,LAYOUT_STRATEGIES,render_visual
from ..library_export import export_package

def build_delivery(job,request,lesson,sources,files,*,originals=None,external_qa=True,qa_dir=None,font_path=None,provider=None,on_visual_repair=None,visual_host=None,quality_state=None,on_quality_checkpoint=None,allow_quality_calls=True):
    used=used_source_ids(lesson)
    archives=[s for s in sources if s['id'] in (originals or {}) and s['id'] not in used]
    context=[s for s in sources if s not in archives]
    request=dict(request,sources=context);validated=validate_request(request)
    lesson=deepcopy(lesson);lesson.setdefault('provenance',{})['human_scientific_review']='pending'
    result=validate_result(lesson,validated)
    root=files.path_for(job['id'],'figures')
    def render(visual,repaired):
        # Mechanical layout strategies run before any model repair: each
        # candidate keeps its own artifacts, and the teaching JSON is untouched.
        base=files.path_for(job['id'],'figures-repaired' if repaired else 'figures')
        last=None
        from ..visual_versions import candidate_id
        cid=candidate_id(visual)[:16]
        base=files.path_for(job['id'],('figures-repaired' if repaired else 'figures')+'-v'+cid)
        last=None
        for strategy in LAYOUT_STRATEGIES:
            output=base if strategy==0 else files.path_for(job['id'],('figures-repaired' if repaired else 'figures')+f'-v{cid}-s{strategy}')
            try:
                return render_visual(visual,output,run_external_qa=external_qa,qa_dir=qa_dir,font_path=font_path,layout_strategy=strategy)
            except ValueError as error:
                if str(error)!=COLLISION:raise
                last=error
        # All deterministic layouts collided: enter a layout-pending state with
        # the concrete collisions preserved; never queue a model repair for it.
        raise ValueError('visual layout pending: '+str(last))
    if 'presentation' in result.visual:
        from .visual_quality import prepare_visual_delivery
        lesson,figures,quality=prepare_visual_delivery(request,asdict(result),context,provider if allow_quality_calls else None,render=render,state=quality_state,on_checkpoint=on_quality_checkpoint,visual_host=visual_host)
        lesson.setdefault('provenance',{})['visual_logic_review']='automatic_pass_pending_human'
        result=validate_result(lesson,validated)
    else:
        figures=None
    try:
        if figures is None:figures=render_visual(result.visual,root,run_external_qa=external_qa,qa_dir=qa_dir,font_path=font_path)
    except ValueError as error:
        if provider is None or str(error)!='Figure rendered QA requires correction; artifacts preserved for review':raise
        from .visual_repair import repair_visual
        lesson=repair_visual(request,asdict(result),context,provider,visual_host=visual_host)
        if on_visual_repair:on_visual_repair(lesson)
        result=validate_result(lesson,validated)
        root=files.path_for(job['id'],'figures-repaired')
        figures=render_visual(result.visual,root,run_external_qa=external_qa,qa_dir=qa_dir,font_path=font_path)
    target=files.path_for(job['id'],'lesson.zip');temporary=files.path_for(job['id'],'lesson-part.zip')
    export_package(request,asdict(result),sources=context,archive_sources=archives,originals=originals or {},figures={'desktop':figures.desktop,'mobile':figures.mobile},term_id=validated.term['id'],output=temporary)
    os.replace(temporary,target)
    return dict(asset_id='lesson.zip',sha256=hashlib.sha256(target.read_bytes()).hexdigest(),bytes=target.stat().st_size)
