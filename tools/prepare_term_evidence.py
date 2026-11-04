"""Inspect the literature foundation locally. Default mode never calls a provider."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from term_explainer.contract import validate_request
from term_explainer.deepseek import DeepSeekClient, DeepSeekError
from term_explainer.evidence import prepare_context
from term_explainer.literature import plan_literature
from term_explainer.pipeline import PipelineError, prepare_evidence


def failure(code, message):
    print(json.dumps({'error': {'code': code, 'message': message}}, ensure_ascii=False), file=sys.stderr)
    return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description='准备术语的文献证据；默认仅输出离线处理计划。')
    parser.add_argument('input', type=Path, help='UTF-8 JSON 请求文件；此阶段只接受元数据/已提取文本。')
    parser.add_argument('--live-evidence', action='store_true', help='真实检索和阅读，不生成正文；需预算与发送授权。')
    parser.add_argument('--max-api-calls', type=int, default=0, help='搜索、抓取和模型共用调用上限，默认 0。')
    parser.add_argument('--send-selected-sources', action='store_true', help='同意将本次选定来源发给 DeepSeek。')
    parser.add_argument('--report', type=Path, help='直接保存 UTF-8 JSON（含失败诊断）；已有文件会拒绝执行。')
    args = parser.parse_args(argv)
    if args.report is None:
        return execute(args)
    try:
        # Reserve before any provider call, so a prior/interrupted attempt cannot be overwritten.
        stream = args.report.open('x', encoding='utf-8')
    except FileExistsError:
        return failure('report_exists', '已有结果或进行中记录，请先检查，不要重复调用。')
    except OSError:
        return failure('report_unavailable', '无法创建结果记录，未调用供应商。')
    with stream:
        try:
            json.dump(dict(status='started', reserved_max_calls=args.max_api_calls if args.live_evidence else 0), stream)
            stream.flush()
        except OSError:
            return failure('report_unavailable', '无法写入开始记录，未调用供应商。')
        return execute(args, stream)


def execute(args, report=None):
    client = None

    def finish(result, *, error=False):
        if error or client is not None:
            result.update(api_calls=client.calls if client else 0,
                          api_events=client.metrics if client else [])
        serialized = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)
        if report is not None:
            try:
                report.seek(0)
                report.write(serialized + '\n')
                report.truncate()
                report.flush()
            except OSError:
                # Still print counters: a local save failure never authorizes an automatic rerun.
                print(json.dumps(dict(error=dict(code='report_write_failed', message='结果保存失败，请保留此输出，不要自动重试。'),
                    api_calls=client.calls if client else 0, api_events=client.metrics if client else []), ensure_ascii=False), file=sys.stderr)
                return 2
        print(serialized, file=sys.stderr if error else sys.stdout)
        return 2 if error else 0

    def fail(code, message):
        return finish({'error': {'code': code, 'message': message}}, error=True)

    if args.live_evidence and args.max_api_calls <= 0:
        return fail('budget_required', '真实证据准备需指定正整数调用上限。')
    if args.live_evidence and not args.send_selected_sources:
        return fail('source_consent_required', '需明确同意发送选定来源；默认不会联网。')
    try:
        with args.input.open('rb') as stream:
            raw = stream.read(1048577)
        if len(raw) > 1048576:
            return fail('request_too_large', '输入超过 1 MiB，未读取或发送。')
        def reject_constant(value):
            raise ValueError('nonfinite JSON')
        payload = json.loads(raw.decode('utf-8-sig'), parse_constant=reject_constant)
        request = validate_request(payload)
        anchor = prepare_context(request)['anchor']
        candidates = payload.get('candidates', [])
        confirmed = payload.get('confirmed_candidate_id')
        if not args.live_evidence:
            result = plan_literature(dict(anchor=anchor, sources=request.sources,
                literature_prompted=request.literature_prompted, network_allowed=request.network_allowed,
                candidates=candidates, confirmed_candidate_id=confirmed))
            result['execution'] = 'offline_plan_no_provider_calls'
        else:
            client = DeepSeekClient(max_calls=args.max_api_calls)
            reply = prepare_evidence(request, client, candidates=candidates, confirmed_candidate_id=confirmed)
            result = asdict(reply)
            result.update(execution='live_evidence_requires_semantic_review', api_calls=client.calls)
        return finish(result)
    except (DeepSeekError, PipelineError) as error:
        return fail(error.code, error.message)
    except (ValueError, TypeError, KeyError, UnicodeError):
        return fail('invalid_request', '请求或证据字段无效；未输出文献正文。')
    except OSError:
        return fail('input_unavailable', '无法读取输入文件。')


if __name__ == '__main__':
    raise SystemExit(main())
