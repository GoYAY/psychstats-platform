"""One-start, private multi-literature enrichment of a completed teaching job."""
from pathlib import Path
import argparse,json,os,sys,webbrowser
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from term_explainer.expansion import create_enrichment,reconcile_truncation
from term_explainer.full_job import run_job,RecordedClient,JobError,fingerprint
from term_explainer.deepseek import DeepSeekClient,DeepSeekError
from term_explainer.pipeline import PipelineError
from tools.read_term_sections import load_json,atomic_write
from tools.run_term_explainer import summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--sources',type=Path)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--send-selected-sources',action='store_true')
    parser.add_argument('--open',action='store_true')
    parser.add_argument('--review-truncated-response',action='store_true')
    args=parser.parse_args(argv);lock=None
    try:
        original=load_json(args.job/'job.json',16777216);payload=load_json(args.job/'input.json')
        supplements=load_json(args.sources).get('sources',[]) if args.sources else []
        state,updated=create_enrichment(original,payload,supplements)
        if not args.live:
            print(json.dumps(dict(estimate_only=True,body_char_limit=updated['request']['max_body_chars'],
                max_additional_works=3,max_reference_depth=1,model_calls_estimate=[2,4],
                retrieval_calls_estimate=[0,3],previous_readings_reused=True,provider_calls=0),indent=2));return 0
        if not args.send_selected_sources:raise JobError('consent_required','需明确同意发送所选原文。')
        output=args.output.resolve();public=Path(__file__).resolve().parents[1]/'site'
        if output==args.job.resolve() or output==public or output.is_relative_to(public):
            raise JobError('private_output_required','增强任务必须使用独立私有目录，保留原版。')
        output.mkdir(parents=True,exist_ok=True)
        if not (output/'job.json').exists() and any(output.iterdir()):raise JobError('output_not_empty','输出目录有其他文件，未覆盖。')
        lock=(output/'job.lock').open('x',encoding='utf-8')
        if (output/'job.json').exists():
            state=load_json(output/'job.json',16777216)
            if state['input_hash']!=fingerprint(updated):raise JobError('input_changed','增强任务资料已改变。')
        def save(value):
            atomic_write(output/'job.json',value);atomic_write(output/'report.json',summary(value))
        if not (output/'input.json').exists():atomic_write(output/'input.json',updated);save(state)
        if args.review_truncated_response:
            reconcile_truncation(state,fingerprint(updated));save(state)
        if state['stage']=='complete':
            print(json.dumps(summary(state),ensure_ascii=False,indent=2));return 0
        if not os.environ.get('DEEPSEEK_API_KEY'):raise JobError('missing_credentials','当前进程没有模型密钥，未发起请求。')
        client=RecordedClient(DeepSeekClient(max_calls=None,max_tokens=16384,timeout=180),state,output/'responses',save)
        run_job(state,updated,client,save,output,progress=lambda m:print(m,flush=True))
        print(json.dumps(summary(state),ensure_ascii=False,indent=2))
        if args.open:webbrowser.open(Path(state['output_page']).as_uri())
        return 0
    except (JobError,DeepSeekError,PipelineError,ValueError,KeyError,TypeError,OSError) as error:
        print(json.dumps(dict(error=getattr(error,'code','local_error'),message=str(error)),ensure_ascii=False),file=sys.stderr);return 2
    finally:
        if lock is not None:lock.close();(args.output/'job.lock').unlink()


if __name__=='__main__':raise SystemExit(main())
