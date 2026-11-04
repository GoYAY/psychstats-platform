"""Loopback-only static preview with the deployed /psy-stats/ mount alias."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


def resolve_path(root, url):
    base = Path(root).resolve()
    path = unquote(urlsplit(url).path).replace('\\', '/')
    if path.startswith('/psy-stats/'):
        path = path[len('/psy-stats/'):]
    else:
        path = path.lstrip('/')
    if '..' in path.split('/') or '\x00' in path:
        return None
    candidate = (base / path).resolve()
    return candidate if candidate.is_relative_to(base) else None


def make_handler(root):
    class PreviewHandler(SimpleHTTPRequestHandler):
        def translate_path(self, path):
            resolved = resolve_path(root, path)
            return str(resolved if resolved is not None else Path(root)/'__blocked_path__')
    return PreviewHandler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='site/dist')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(Path(args.root).resolve()))
    print(f'Preview: http://127.0.0.1:{args.port}/psy-stats/index.html', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
