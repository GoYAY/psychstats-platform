"""Durable bounded quality gate. Provider receipts own retries and accounting."""
from copy import deepcopy
from pathlib import Path
import hashlib,json
from .config import OnlineError
from .visual_review import requires_visual_review,build_review_context,review_visual
from .visual_repair import repair_visual
from ..figures import validate_visual

COLLISION='Figure rendered QA requires correction; artifacts preserved for review'  # kept for compatibility; source of truth in figures.py
LAYOUT_PENDING='visual layout pending: '  # delivery.py wraps COLLISION once all deterministic layouts failed
def fingerprint(request,lesson,sources):
    return hashlib.sha256(json.dumps(build_review_context(request,lesson,sources),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def visual_fingerprint(visual):
    """Host-side content binding for pending issues; never model-asserted."""
    return hashlib.sha256(json.dumps(visual,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def prepare_visual_delivery(request,lesson,sources,provider,*,render,state,on_checkpoint,visual_host=None):
    original=deepcopy(lesson);validate_visual(original['visual'])
    if 'presentation' not in original['visual']:
        return original,render(original['visual'],False),state or {}
    binding=fingerprint(request,original,sources)
    state=deepcopy(state) if isinstance(state,dict) and state.get('input_fingerprint')==binding else dict(policy_version=1,review_policy_version=4,repair_policy_version=2,input_fingerprint=binding,phase='new',repairs_used=0,reviews={},version_log=[],baseline_version=None,accepted_version=None,candidate_version=None)
    state.setdefault("version_log",[]);state.setdefault("baseline_version",None);state.setdefault("accepted_version",None);state.setdefault("candidate_version",None)
    def save(**changes):
        state.update(changes)
        if on_checkpoint:on_checkpoint(deepcopy(state))
    def blocked(message):
        # stop_reason explains why delivery stopped; pending_issues keep the
        # concrete review/collision feedback so resume can act on it.
        save(phase='review_required',stop_reason=message)
        raise OnlineError('visual_review_required','图示尚未通过核对，已有内容和资料已保存。',409)
    if state.get('phase')=='blocked_manual_check':
        blocked('图示评审意见与当前版本不匹配（'+str(state.get('stop_reason') or '材料核对')+'）：已保留现场，不会自动调用修复；请人工核对材料后由管理员处理。')
    if state.get('phase')=='review_required':blocked(state.get('stop_reason') or state.get('failure') or 'manual review required')
    current=deepcopy(state.get('revised_lesson',original));artifacts=None
    def repair(issues):
        nonlocal current
        if provider is None or on_checkpoint is None:blocked('persistent provider context required')
        if state.get('issue_binding')=='unmatched':blocked('图示评审意见与当前图示版本不匹配，已停止自动修复；请人工核对材料后由管理员处理。')
        if issues and all(isinstance(i,dict) and i.get('kind')=='collision' for i in issues):
            save(pending_issues=deepcopy(issues),repair_issues=deepcopy(issues))
            blocked('图示排版问题待处理：碰撞明细与候选版本已保存，待排版策略更新后重试；不消耗模型教学修复。')
        if state.get('phase')!='repair_reserved':
            if state['repairs_used']>=1:blocked('single visual revision exhausted')
            save(phase='repair_reserved',repairs_used=1,repair_input=deepcopy(current),repair_issues=deepcopy(issues))
        from ..visual_preservation import build_preservation_manifest,validate_preserved_visual
        baseline=state.get('repair_input') or deepcopy(current)
        manifest=build_preservation_manifest(baseline.get('visual') if isinstance(baseline,dict) else {},state.get('repair_issues'))
        # Resume sends IDENTICAL messages through BudgetedProvider: received is
        # cached; unknown receipt stops there, rather than issuing another bill.
        try:revised=repair_visual(request,state['repair_input'],sources,provider,issues=state['repair_issues'],visual_policy_version=1,visual_host=visual_host,preservation=manifest,repair_policy_version=state.get('repair_policy_version',1))
        except ValueError as error:blocked(str(error))
        regression=None
        try:validate_preserved_visual(revised.get('visual') if isinstance(revised,dict) else None,manifest)
        except ValueError as check_error:
            # A regressed candidate never replaces the baseline; the concrete
            # teaching issues stay in pending_issues for the next continuation.
            regression=str(check_error)
        if regression is not None:
            from ..visual_versions import append_version,candidate_id
            append_version(state,revised.get('visual') or {},candidate=candidate_id(revised.get('visual') or {}),
                baseline=state.get('baseline_version'),accepted=False,regression=regression)
            blocked(f'修复后的图示丢失既有教学内容：{regression}')
        current=revised
        save(phase='repaired',revised_lesson=deepcopy(current))
    if state.get('phase')=='repair_reserved':repair(state['repair_issues'])
    while True:
        try:
            validate_visual(current['visual']);artifacts=render(current['visual'],bool(state['repairs_used']))
        except ValueError as error:
            # delivery.py wraps the collision marker once every deterministic
            # layout failed; that is still a layout problem, not a manual stop.
            if str(error)!=COLLISION and not str(error).startswith(LAYOUT_PENDING):blocked(str(error))
            repair([dict(kind='collision',reason=str(error),object_paths=[],visual_fingerprint=visual_fingerprint(current['visual']))]);continue
        hashes={}
        for name in ('desktop','mobile','audit'):
            path=getattr(artifacts,name,None)
            if path and Path(path).is_file():hashes[name]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        from ..visual_versions import append_version,candidate_id
        append_version(state,current.get('visual') or {},candidate=candidate_id(current.get('visual') or {}),
            baseline=state.get('baseline_version'),accepted=False,mechanical=dict(passed=True,artifact_hashes=hashes))
        save(mechanical=dict(passed=True,artifact_hashes=hashes),
             pending_issues=[p for p in state.get('pending_issues',[]) if p.get('kind')!='collision'])
        if not requires_visual_review(current['visual']):save(phase='passed');return current,artifacts,state
        if provider is None or on_checkpoint is None:blocked('persistent provider context required')
        key=fingerprint(request,current,sources)+':'+str(state['repairs_used'])
        if state.get('manual_recovery'):key+=':explicit-'+str(state['manual_recovery'])
        review_policy=state.get('review_policy_version',1)
        if review_policy in (2,3,4):key+=':v'+str(review_policy)+':'+hashlib.sha256(request.get('question','').encode()).hexdigest()
        review=state['reviews'].get(key)
        if review is None:
            save(phase='review_reserved',review_fingerprint=key)
            try:review=review_visual(request,current,sources,provider,policy_version=review_policy)
            except ValueError as error:blocked(str(error))
            state['reviews'][key]=review;save(phase='reviewed')
        if review['decision']=='pass':
            from ..visual_versions import append_version,candidate_id
            append_version(state,current.get('visual') or {},candidate=candidate_id(current.get('visual') or {}),
                baseline=state.get('baseline_version'),accepted=True,review=review)
            save(phase='passed',pending_issues=[]);return current,artifacts,state
        if review['decision']=='uncertain':blocked(review['reason'])
        issues=[dict(kind='teaching_review',reason=review['reason'],object_paths=review.get('object_paths',[]),
                     visual_fingerprint=visual_fingerprint(current['visual']),review_key=key)]
        save(pending_issues=issues)
        repair(issues)
