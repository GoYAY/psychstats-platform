"""Read one verified section per explicit invocation; offline preview by default."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from term_explainer.contract import validate_request
from term_explainer.deepseek import DeepSeekClient, DeepSeekError
from term_explainer.pipeline import PipelineError
from term_explainer.section_reading import create_reading_state, read_next_section
from term_explainer.section_quality import condition_memory, validate_identity_review


class EntryError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


def load_json(path, maximum=1048576):
    with path.open('rb') as stream:
        raw = stream.read(maximum+1)
    if len(raw) > maximum:
        raise EntryError('input_too_large', '本地输入超过读取上限，未发送。')
    def reject(value):
        raise ValueError('nonfinite JSON')
    value = json.loads(raw.decode('utf-8-sig'), parse_constant=reject)
    if not isinstance(value, dict):
        raise ValueError('an object is required')
    return value


def atomic_write(path, value):
    """Same-directory atomic replacement keeps the previous checkpoint on failure."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                prefix=path.name+'.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def validate_checkpoint(state, expected):
    for key in ('paper_id','source_hash','term_hash','sections','max_calls'):
        if state.get(key) != expected[key]:
            raise EntryError('checkpoint_mismatch', '原文、术语、小节清单或预算与现有断点不符，未覆盖或续读。')
    if state.get('identity_review') != expected.get('identity_review'):
        raise EntryError('checkpoint_mismatch','文献身份核对记录与现有断点不符，未自动替换。')
    index, reserved = state.get('next_section'), state.get('reserved_calls')
    readings = state.get('readings')
    actual = state.get('confirmed_api_calls',0)
    if (type(index) is not int or not 0 <= index <= len(expected['sections'])
            or type(reserved) is not int or not index <= reserved <= expected['max_calls']
            or type(actual) is not int or not 0 <= actual <= reserved
            or not isinstance(readings,list) or len(readings) != index
            or not isinstance(state.get('rolling_summary'),str) or len(state['rolling_summary']) > 2000
            or state.get('can_generate') is not False
            or state.get('status') not in ('reading','in_flight','failed_requires_review','needs_disambiguation',
                'read_all_requires_review','needs_budget','needs_subsections','needs_context_selection')):
        raise EntryError('checkpoint_mismatch', '断点进度或计数不完整，需先核查，未自动重跑。')
    if any(not isinstance(r,dict) or r.get('section_id') != expected['sections'][i]['id']
           for i,r in enumerate(readings)):
        raise EntryError('checkpoint_mismatch', '已读小节顺序与断点不符。')
    if (state['status'] == 'read_all_requires_review') != (index == len(expected['sections'])):
        raise EntryError('checkpoint_mismatch', '完成标志与实际已读小节不符。')


def main(argv=None):
    parser = argparse.ArgumentParser(description='按真实小节断点续读；默认离线预览，每次最多一个小节。')
    parser.add_argument('input', type=Path)
    parser.add_argument('--state', type=Path, required=True, help='同一任务始终使用同一断点文件。')
    parser.add_argument('--live-evidence', action='store_true')
    parser.add_argument('--max-api-calls', type=int, default=0, help='真实单节执行须显式设为 1。')
    parser.add_argument('--send-selected-sources', action='store_true')
    parser.add_argument('--report', type=Path, help='真实执行须提供全新 JSON 记录；已有文件拒绝重跑。')
    args = parser.parse_args(argv)
    client = state = report = lock = None
    state_verified = False
    lock_path = Path(str(args.state)+'.lock')

    def finish(error=None):
        nonlocal lock
        warning = None
        if lock is not None:
            lock.close(); lock = None
            try:
                lock_path.unlink()
            except OSError:
                warning = '本次锁文件清理失败，下一次执行前须核查，不要自动删除活动锁。'
        # Never summarize arbitrary or corrupt checkpoint fields into diagnostic output.
        current = state if state_verified else {}
        index = current.get('next_section',0)
        sections = current.get('sections',[])
        next_item = sections[index] if index < len(sections) else None
        result = dict(execution='live_section_requires_semantic_review' if args.live_evidence else 'offline_section_preview',
            status=current.get('status','not_started'), sections_done=index, sections_total=len(sections),
            next_section=dict(id=next_item['id'],title=next_item['title'],chars=next_item['end']-next_item['start']) if next_item else None,
            can_generate=False, requires_semantic_review=True,
            reserved_calls=current.get('reserved_calls',0), max_total_calls=current.get('max_calls',0),
            confirmed_api_calls_total=current.get('confirmed_api_calls',0),
            memory_chars=len(current.get('rolling_summary','')),
            api_calls=client.calls if client else 0, api_events=deepcopy(client.metrics) if client else [])
        if warning:
            result['storage_warning'] = warning
        if error:
            result['error'] = dict(code=error[0],message=error[1])
        serialized = json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2)
        if report is not None:
            try:
                report.seek(0); report.write(serialized+'\n'); report.truncate(); report.flush()
            except OSError:
                result['error'] = dict(code='report_write_failed',message='结果记录保存失败，请保留计数并核查断点，不自动重试。')
                serialized = json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2)
                error = True
        print(serialized,file=sys.stderr if error else sys.stdout)
        return 2 if error else 0

    try:
        paths = [args.input.resolve(),args.state.resolve(),lock_path.resolve()]
        if args.report:
            paths.append(args.report.resolve())
        if len(paths) != len(set(paths)) or args.state.suffix.lower() != '.json':
            raise EntryError('path_collision','输入、断点和报告必须是不同文件，断点须为 JSON。')
        if args.live_evidence:
            if args.max_api_calls != 1:
                raise EntryError('budget_required','本入口每次只读一节，须显式指定 --max-api-calls 1。')
            if not args.send_selected_sources:
                raise EntryError('source_consent_required','需明确同意发送本节正文与此前压缩笔记。')
            if args.report is None:
                raise EntryError('report_required','真实执行须提供全新 --report 文件。')
        if args.report:
            try:
                report = args.report.open('x',encoding='utf-8')
            except FileExistsError:
                raise EntryError('report_exists','已有结果或开始记录，请检查，不重复运行。') from None
            json.dump(dict(status='started',max_api_calls=1 if args.live_evidence else 0),report)
            report.flush()
        payload = load_json(args.input)
        request, source = payload['request'],payload['source']
        validate_request(dict(request,sources=[]))
        expected = create_reading_state(request,source,payload['headings'],max_calls=payload['remaining_model_calls'],
                                        identity_review=payload.get('identity_review'))
        if args.live_evidence:
            try:
                lock = lock_path.open('x',encoding='utf-8')
            except FileExistsError:
                raise EntryError('checkpoint_locked','断点有活动或中断锁，请先核查，不自动删除。') from None
        state = load_json(args.state,4194304) if args.state.exists() else expected
        validate_checkpoint(state,expected)
        validate_identity_review(state.get('identity_review'),source)
        condition_memory(state,source)
        state_verified = True
        if not args.live_evidence:
            return finish()
        if state['status'] in ('in_flight','failed_requires_review','needs_disambiguation'):
            raise EntryError('checkpoint_requires_review','上次调用中断、失败或需确认，请先核查；不自动重跑。')
        if state['next_section'] >= len(state['sections']):
            return finish()
        section = state['sections'][state['next_section']]
        if section['title'] in payload.get('non_method_backmatter',[]):
            state['status'] = 'needs_local_catalogue'
            return finish()
        if state['reserved_calls'] >= state['max_calls']:
            state['status'] = 'needs_budget'; atomic_write(args.state,state)
            return finish()
        if section['end']-section['start'] > 60000:
            state['status'] = 'needs_subsections'; atomic_write(args.state,state)
            return finish()
        if not request.get('network_allowed',True):
            raise EntryError('network_not_allowed','本请求未允许模型联网处理，未发送资料。')
        if not os.environ.get('DEEPSEEK_API_KEY',''):
            raise EntryError('missing_credentials','当前终端未配置模型密钥，未预留或调用。')
        client = DeepSeekClient(max_calls=1)
        confirmed_before = state.get('confirmed_api_calls',0)
        def checkpoint(value):
            value['confirmed_api_calls'] = confirmed_before + client.calls
            value['last_run'] = dict(api_calls=client.calls,api_events=deepcopy(client.metrics))
            atomic_write(args.state,value)
        read_next_section(state,request,source,client,checkpoint=checkpoint)
        return finish()
    except (EntryError,DeepSeekError,PipelineError) as error:
        return finish((error.code,error.message))
    except (ValueError,TypeError,KeyError,UnicodeError):
        return finish(('invalid_input','输入或分析结果未通过校验；请检查记录，不自动重试。'))
    except OSError:
        return finish(('storage_error','本地文件读取或断点保存失败，未自动重试；请检查报告中的实际调用数。'))
    finally:
        if lock is not None:
            lock.close()
        if report is not None:
            report.close()


if __name__ == '__main__':
    raise SystemExit(main())
