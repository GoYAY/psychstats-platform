"""Run the private, loopback-only framework organizer."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from term_explainer.framework_server import make_server

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8781);parser.add_argument('--origin',action='append',default=None);args=parser.parse_args()
    server=make_server(port=args.port,allowed_origins=args.origin or ['http://127.0.0.1:8773'])
    print('Local framework service: http://127.0.0.1:'+str(server.server_port),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
