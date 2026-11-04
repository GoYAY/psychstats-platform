"""Single-start private whole-document teaching task; offline estimate by default."""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import webbrowser

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from term_explainer.deepseek import DeepSeekClient,DeepSeekError
from term_explainer.full_job import (create_job,estimate_job,run_job,RecordedClient,JobError,fingerprint)
from term_explainer.pipeline import PipelineError
from tools.read_term_sections import atomic_write,load_json


def load_catalogue(payload):
    if payload['request'].get('catalog'): return
    path=Path(__file__).resolve().parents[1]/'site/content/terms.json'
    if not path.is_file(): return
    data=json.loads(path.read_text(encoding='utf-8'))
    payload['request']['catalog']=[dict(id=t['id'],zh=t['zh'],en=t.get('en',''),aliases=t.get('aliases',[]),kind='classic')
        for t in data['terms'] if t.get('status')=='public' and t['id']!=payload['request']['term']['id']]


def summary(state):
    events=state.get('events',[])
    usage={key:sum(e.get('usage',{}).get(key,0) for e in events) for key in ('prompt_tokens','completion_tokens','total_tokens')}
    return dict(stage=state['stage'],sections_done=state['reading']['next_section'],
        sections_total=len(state['reading']['sections']),new_request_attempts=len(events),
        confirmed_new_api_calls=sum(e.get('api_calls',0) for e in events),
        unresolved_request_intents=sum(e.get('status')=='in_flight' for e in events),
        inherited_section_calls=state['inherited_section_calls'],financial_call_cap=None,
        successful_responses=sum(e.get('status')=='response_received' for e in events),usage=usage,
        output_page=state.get('output_page'),requires_human_review=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description='整篇按节续读、证据整理、科普和图示生成；默认只估算，不调用模型。')
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--seed',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--run-to-completion',action='store_true',help='用户明确授权本次完整任务，不设财务调用上限；恢复次数仍有界。')
    parser.add_argument('--send-selected-sources',action='store_true')
    parser.add_argument('--open',action='store_true')
    parser.add_argument('--multi-literature',action='store_true',help='新任务复用参考文献追读并整合多源证据；旧任务使用独立增强入口。')
    args=parser.parse_args(argv)
    state=None; lock=None; lock_path=None
    try:
        payload=load_json(args.input)
        if args.multi_literature:payload['multi_literature']=True
        seed=load_json(args.seed,16777216) if args.seed else None
        load_catalogue(payload)
        plan=estimate_job(payload,seed)
        if payload.get('multi_literature'):
            plan.update(multi_literature=True,max_additional_works=3,max_reference_depth=1,
                additional_retrieval_calls_estimate=[0,3],note=plan['note']+' Multi-source analysis may add a bounded synthesis pass.')
        if not args.live:
            print(json.dumps(plan,ensure_ascii=False,indent=2)); return 0
        if not args.run_to_completion or not args.send_selected_sources:
            raise JobError('consent_required','真实执行需明确完整任务授权及发送本次原文/笔记的同意。')
        output=args.output.resolve()
        protected=Path(__file__).resolve().parents[1]/'site'
        if output==protected or output.is_relative_to(protected):
            raise JobError('private_output_required','个人文献任务须写入独立私有目录，不能写入公共站点产物。')
        if output.exists() and not (output/'job.json').exists() and any(output.iterdir()):
            raise JobError('output_not_empty','输出目录有其他文件，未覆盖。请选择新的专用目录。')
        output.mkdir(parents=True,exist_ok=True)
        lock_path=output/'job.lock'
        try: lock=lock_path.open('x',encoding='utf-8')
        except FileExistsError: raise JobError('job_locked','该任务正在执行或曾中断。请先核对，勿并发运行。') from None
        task=output/'job.json'
        state=load_json(task,16777216) if task.exists() else create_job(payload,seed)
        if state.get('input_hash')!=fingerprint(payload): raise JobError('input_changed','输入资料或术语目录与既有任务不符。')
        def save(value):
            atomic_write(task,value)
            atomic_write(output/'report.json',summary(value))
        if state['stage']=='complete':
            print(json.dumps(summary(state),ensure_ascii=False,indent=2))
            if args.open: webbrowser.open(Path(state['output_page']).as_uri())
            return 0
        if not task.exists():
            atomic_write(output/'input.json',payload)
            save(state)
        if not os.environ.get('DEEPSEEK_API_KEY',''):
            raise JobError('missing_credentials','当前终端未配置模型密钥，未发起模型请求。请在已配置密钥的终端运行同一命令。')
        print('开始完整任务：每节自动保存；普通小节无需再次确认。',flush=True)
        print(json.dumps(plan,ensure_ascii=False),flush=True)
        provider=DeepSeekClient(max_calls=None,max_tokens=16384,timeout=180)
        client=RecordedClient(provider,state,output/'responses',save)
        run_job(state,payload,client,save,output,progress=lambda message:print(message,flush=True))
        print(json.dumps(summary(state),ensure_ascii=False,indent=2))
        if args.open and state.get('output_page'): webbrowser.open(Path(state['output_page']).as_uri())
        return 0
    except (JobError,PipelineError,DeepSeekError) as error:
        if state is not None:
            state['last_error']=dict(code=error.code,message=error.message)
            if lock is not None:
                atomic_write(args.output/'job.json',state)
                atomic_write(args.output/'report.json',dict(summary(state),error=state['last_error']))
        print(json.dumps(dict(error=error.code,message=error.message),ensure_ascii=False),file=sys.stderr)
        return 2
    except (ValueError,TypeError,KeyError,OSError) as error:
        if state is not None and lock is not None:
            state['last_error']=dict(code='local_validation_or_storage_error',message=str(error))
            try: atomic_write(args.output/'job.json',state)
            except OSError: pass
        print(json.dumps(dict(error='local_validation_or_storage_error',message=str(error)),ensure_ascii=False),file=sys.stderr)
        return 2
    finally:
        if lock is not None:
            lock.close()
            try: lock_path.unlink()
            except OSError: pass


if __name__=='__main__': raise SystemExit(main())
