"""Safe failure description. Never echoes exception text, locals or model output."""
from pathlib import Path
import re
import traceback

_ANALYSIS_SUBCODE=re.compile(r'analysis_[a-z0-9_]{1,64}')

GENERIC_MESSAGE = '任务执行失败，已保留现场；请稍后重试或联系管理者。'
PUBLIC_MESSAGES = {
    'invalid_reference_candidate':'参考文献的身份或引文定位未通过校验，已有阅读记录保留。',
    'invalid_model_json':'模型响应格式未通过校验，已有进度保留。',
    'invalid_evidence_analysis':'模型输出的结构或证据定位未通过校验，已有进度保留；可按页面提示继续局部修复。',
    'visual_review_required':'图示尚未通过教学核对，已有内容与资料保留。',
    'budget_exhausted':'本轮预算已达到安全上限，已有进度保留。',
    'needs_reconciliation':'此前请求的回执待核对，系统不会自动重复发送。',
    'source_needs_structure':'尚未识别到可供阅读的正文小节。请补充有清晰章节标题的 PDF 或 UTF-8 文字材料。',
    'invalid_selection':'证据选择的章节编号或范围未通过校验，已有阅读记录保留，请联系管理员核对。',
    'no_relevant_evidence':'已读正文尚未提供该术语的必要证据，请补充相关文献或澄清目标含义。',
}

# Domain codes that are fixed application templates and safe to expose.
SAFE_CODES = frozenset({
    'invalid_config', 'invalid_file', 'file_too_large', 'source_unreadable',
    'source_needs_structure', 'source_too_large', 'invalid_source',
    'network_consent_required', 'model_consent_required', 'budget_exhausted',
    'task_timeout', 'call_budget_exhausted', 'inactive_job', 'not_found',
    'unauthorized', 'rate_limited', 'needs_reconciliation', 'response_too_large',
    'invalid_usage', 'usage_exceeded_reservation', 'lesson_incomplete',
    'model_truncated', 'model_incomplete', 'empty_model_response',
    'invalid_provider_response', 'provider_http_403', 'provider_http_404', 'visual_review_required',
    'source_unavailable', 'source_access_blocked', 'invalid_model_json',
    'invalid_evidence_analysis', 'invalid_reference_candidate',
    'invalid_scope_review', 'invalid_selection', 'invalid_evidence', 'no_relevant_evidence',
    'evidence_not_ready', 'invalid_lesson', 'invalid_fixed_modules',
    'teaching_policy_unavailable', 'source_budget_exceeded', 'reference_limit',
    'cache_mismatch', 'request_requires_reconciliation', 'input_changed',
    'job_needs_review', 'reading_stopped', 'reading_paused',
    'needs_disambiguation', 'section_failed', 'stage_failed', 'lesson_failed',
    'lesson_partial', 'invalid_patch', 'invalid_transition', 'job_failed',
})


def _location(error):
    frames = traceback.extract_tb(error.__traceback__)
    if not frames:
        return None
    frame = frames[-1]
    return '%s:%d:%s' % (Path(frame.filename).name, frame.lineno, frame.name)


def describe_failure(error, *, stage=None):
    """Return (public_code, diagnostics). Unknown errors never leak their text."""
    code = getattr(error, 'code', None)
    known = isinstance(code, str) and code in SAFE_CODES
    detail = {
        'error_type': type(error).__name__,
        'stage': stage,
        'location': _location(error),
        'public_message': PUBLIC_MESSAGES.get(code,GENERIC_MESSAGE) if known else GENERIC_MESSAGE,
    }
    subcode=getattr(error,'subcode',None)
    if subcode in {'reference_doi_not_in_span','reference_url_not_in_span','reference_title_not_in_span','reference_parent_mismatch','reference_locator_invalid','analysis_repair_changed_existing_data','analysis_repair_incomplete'}:
        detail['error_subcode']=subcode
    elif isinstance(subcode,str) and _ANALYSIS_SUBCODE.fullmatch(subcode):
        # Fixed internal check names, never model text or file paths.
        detail['error_subcode']=subcode
    return (code if known else 'job_failed'), detail
