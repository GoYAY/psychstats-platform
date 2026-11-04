"""Local operator command. Never deploy this tool under the static web root."""
import argparse,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from term_explainer.online.config import load_config,OnlineError
from term_explainer.online.store import OnlineStore
from term_explainer.online.auth import InviteAuth

def main(argv=None):
    parser=argparse.ArgumentParser(description='创建或撤销内测邀请；仅在服务器管理员终端运行。')
    commands=parser.add_subparsers(dest='action',required=True)
    create=commands.add_parser('create');create.add_argument('--label',required=True)
    revoke=commands.add_parser('revoke');revoke.add_argument('invite_id')
    commands.add_parser('list')
    args=parser.parse_args(argv)
    try:
        config=load_config(os.environ);store=OnlineStore(config.private_root/'jobs.sqlite');auth=InviteAuth(store,config)
        if args.action=='create':print(auth.create_invite(args.label))
        elif args.action=='revoke':auth.revoke_invite(args.invite_id);print('邀请已撤销。')
        else:
            with store.connection() as db:
                for row in db.execute('SELECT id,label,expires,revoked FROM invites ORDER BY created DESC'):print(dict(row))
    except OnlineError as error:
        print(error.code+': '+error.message,file=sys.stderr);return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
