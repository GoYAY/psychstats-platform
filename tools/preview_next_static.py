"""Serve exported Next assets/routes under /psy-stats, loopback only."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote

def resolve_path(root,url):
    root=Path(root).resolve();path=unquote(urlsplit(url).path).replace('\\','/')
    if path.startswith('/psy-stats/'):path=path[len('/psy-stats/'):]
    elif path=='/psy-stats':path=''
    else:path=path.lstrip('/')
    if '..' in path.split('/') or '\x00' in path:return None
    target=(root/path).resolve()
    if not target.is_relative_to(root):return None
    if target.is_dir():target=target/'index.html'
    elif not target.is_file() and not target.suffix:target=target/'index.html'
    return target if target.is_file() else None

def make_handler(root):
    class Handler(SimpleHTTPRequestHandler):
        def translate_path(self,path):
            resolved=resolve_path(root,path)
            return str(resolved if resolved is not None else Path(root)/'__not_found__')
        def end_headers(self):
            self.send_header('Cache-Control','no-cache')
            super().end_headers()
    return Handler

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',default='site/next-preview/out');parser.add_argument('--port',type=int,default=8766);args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(Path(args.root).resolve()))
    print(f'Next static preview: http://127.0.0.1:{args.port}/psy-stats/',flush=True)
    server.serve_forever()
