"""Run one durable worker; model calls only after an explicit queued consent."""
import argparse,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from term_explainer.online.config import load_config
from term_explainer.online.store import OnlineStore
from term_explainer.online.files import PrivateFiles,cleanup_jobs
from term_explainer.online.worker import Worker,require_lease
from term_explainer.online.provider import BudgetedProvider
from term_explainer.online.orchestrator import advance_job
from term_explainer.deepseek import DeepSeekClient
from term_explainer.online.render_setup import check_renderer
from term_explainer.online.supervisor import run_isolated

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--child',action='store_true');args=parser.parse_args(argv)
    config=load_config(os.environ)
    if not config.generation_enabled:raise SystemExit('Generation is disabled; worker not started.')
    check_renderer(config)
    if not os.environ.get('DEEPSEEK_API_KEY'):raise SystemExit('DEEPSEEK_API_KEY is required; worker not started.')
    store=OnlineStore(config.private_root/'jobs.sqlite');files=PrivateFiles(config.private_root/'tasks')
    def run(job):
        client=DeepSeekClient(model='deepseek-flash',max_calls=config.limits.max_job_calls,max_tokens=config.limits.max_output_tokens,timeout=config.limits.request_timeout)
        provider=BudgetedProvider(config,store,files,job,client)
        return advance_job(job,store,files,provider)
    if args.child:
        ref=json.load(sys.stdin)
        with store.transaction() as db:job=require_lease(db,store,ref,time.time())
        Worker(config,store,runner=run).execute(job);return
    command=[sys.executable,'-X','utf8',str(Path(__file__).resolve()),'--child']
    worker=Worker(config,store,runner=lambda job:run_isolated(config,store,job,command));last_cleanup=0
    try:
        while True:
            now=time.time()
            if now-last_cleanup>=60:
                errors=cleanup_jobs(store,files,now)
                if errors:print('private_cleanup_retry_required',len(errors),flush=True)
                last_cleanup=now
            worker.tick();time.sleep(.5)
    except KeyboardInterrupt:return

if __name__=='__main__':main()
