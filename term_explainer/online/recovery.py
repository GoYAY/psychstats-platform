"""Explicit bounded continuation, never resurrection of terminal/uncertain work."""
from .config import OnlineError
from .worker import active_runtime

RECOVERABLE=frozenset({'invalid_reference_candidate','invalid_model_json','invalid_scope_review',
                       'invalid_evidence_analysis','visual_review_required','lesson_incomplete','invalid_lesson'})
MAX_RESUMES=2


def require_recoverable(job,store,files,config):
    if (job['state']!='waiting_input' or (job.get('question') or {}).get('kind')!='recovery'
        or (job.get('progress') or {}).get('error_code') not in RECOVERABLE):
        raise OnlineError('invalid_transition','当前任务不支持此继续操作。',409)
    if (job.get('checkpoint') or {}).get('recovery_resumes',0)>=MAX_RESUMES:
        raise OnlineError('recovery_exhausted','继续次数已达上限，已有进度保留，请联系管理员。',409)
    checkpoint=job.get('checkpoint') or {}
    if not checkpoint.get('recovery_target') and not checkpoint.get('visual_quality'):
        raise OnlineError('recovery_material_missing','没有可执行的局部修复步骤，请联系管理员。',409)
    if active_runtime(job,store.clock())>=config.limits.max_task_seconds:
        raise OnlineError('task_timeout','本轮运行时间已达到安全上限。',409)
    with store.connection() as db:
        rows=db.execute('SELECT key,state,reserved_tokens FROM provider_calls WHERE job_id=?',(job['id'],)).fetchall()
    if any(r['state'] not in {'received','failed_known'} for r in rows):
        raise OnlineError('needs_reconciliation','此前请求的回执需核对，不能自动继续。',409)
    if len(rows)>=config.limits.max_job_calls or sum(r['reserved_tokens'] for r in rows)>=config.limits.max_job_tokens:
        raise OnlineError('budget_exhausted','当前任务预算已用完，已有进度保留。',429)
    for r in rows:
        if not files.path_for(job['id'],'response-'+r['key']+'.json').is_file():
            raise OnlineError('recovery_material_missing','必要回执已清理，请联系管理员核对，系统不会自动重发。',409)
    for descriptor in job['manifest'].get('documents',[]):
        if not descriptor.get('uploaded') or not files.path_for(job['id'],descriptor['asset_id']).is_file():
            raise OnlineError('recovery_material_missing','本次原始材料已不可用，不能从断点继续。',409)


def reserve_recovery(job):
    from copy import deepcopy
    checkpoint=deepcopy(job.get('checkpoint') or {})
    attempt=checkpoint.get('recovery_resumes',0)+1
    checkpoint['recovery_resumes']=attempt
    code=job['progress']['error_code']
    quality=checkpoint.get('visual_quality')
    if code=='visual_review_required' and isinstance(quality,dict):
        from .visual_quality import visual_fingerprint
        stop=quality.get('stop_reason') or quality.get('failure')
        quality.setdefault('recovery_history',[]).append(dict(attempt=attempt,phase=quality['phase'],stop_reason=stop))
        bound=quality.get('revised_lesson') or checkpoint.get('lesson') or {}
        fingerprint=visual_fingerprint(bound.get('visual') or {}) if isinstance(bound,dict) else ''
        matched=[dict(issue,issue_binding='matched') for issue in (quality.get('pending_issues') or [])
                 if issue.get('visual_fingerprint')==fingerprint]
        if matched:
            issues=matched
        elif (not quality.get('pending_issues') and stop
              and 'single visual revision exhausted' not in stop):
            # Legacy pre-pending_issues state: the stored failure text is the
            # only concrete feedback available.  Migrate it verbatim as a
            # legacy review issue so resume keeps working; preservation still
            # guards the visual and unmatched fingerprints stay blocked.
            issues=[dict(kind='review',reason=stop,object_paths=[],
                refs=[],issue_binding='legacy')]
        else:
            # Legacy state or fingerprint mismatch: never silently reuse a stale
            # review.  Stop before queueing any repair and keep the allowance —
            # the model must not be called on unmatched feedback.
            quality.update(phase='blocked_manual_check',stop_reason=stop,
                issue_binding='unmatched',manual_recovery=attempt)
            checkpoint['recovery_resumes']=attempt-1
            return checkpoint
        quality.update(phase='repair_reserved',manual_recovery=attempt,
            repair_input=deepcopy(bound),repair_issues=issues)
    else:
        target=checkpoint.get('recovery_target')
        if target:
            checkpoint.setdefault('recovery_requests',{})[target['base_key']]=dict(attempt=attempt,prior_key=target['key'],code=code)
    return checkpoint
