"""Run the private API behind a same-origin HTTPS reverse proxy."""
import argparse,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from term_explainer.online.config import load_config
from term_explainer.online.store import OnlineStore
from term_explainer.online.files import PrivateFiles,cleanup_jobs
from term_explainer.online.api import create_app
from term_explainer.online.render_setup import check_renderer
from term_explainer.online.config import OnlineError

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8782);args=parser.parse_args(argv)
    config=load_config(os.environ);store=OnlineStore(config.private_root/'jobs.sqlite');files=PrivateFiles(config.private_root/'tasks')
    cleanup_jobs(store,files,store.clock())
    available=config.generation_enabled and bool(os.environ.get('DEEPSEEK_API_KEY'))
    try:check_renderer(config)
    except OnlineError as error:available=False;print(error.code+': '+error.message,file=sys.stderr)
    app=create_app(config,store,files,provider_enabled=available)
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=args.port,root_path=config.api_prefix.rstrip('/'),proxy_headers=True,forwarded_allow_ips='127.0.0.1',access_log=False,limit_concurrency=8,timeout_keep_alive=5)

if __name__=='__main__':main()
