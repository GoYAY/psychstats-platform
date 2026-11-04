"""Loopback HTTP wire fixture; never contacts a model or uses an environment key."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading

@contextmanager
def response_server(body,*,terminate=False,heartbeats=False,content_length_extra=None,chunk_length_extra=0):
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*args):pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']));requests.append(self.path)
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Connection','close')
            if content_length_extra is not None:self.send_header('Content-Length',str(len(body)+content_length_extra))
            else:self.send_header('Transfer-Encoding','chunked')
            self.end_headers()
            if content_length_extra is not None:self.wfile.write(body)
            else:
                chunks=([b'\n',b'\r\n'] if heartbeats else [])+[body]
                for i,chunk in enumerate(chunks):
                    declared=len(chunk)+(chunk_length_extra if i==len(chunks)-1 else 0)
                    self.wfile.write(format(declared,'x').encode()+b'\r\n'+chunk+b'\r\n')
                if terminate:self.wfile.write(b'0\r\n\r\n')
            self.wfile.flush();self.close_connection=True
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.02},daemon=True);thread.start()
    try:yield 'http://127.0.0.1:'+str(server.server_port)+'/chat/completions',requests
    finally:server.shutdown();server.server_close();thread.join(timeout=2)
