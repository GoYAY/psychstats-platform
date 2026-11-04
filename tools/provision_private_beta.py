"""Operator-only, zero-model provisioning. Never serve under a public web root.

Run from a separate operations directory with --backend-root pointing at the
verified backend. Code arrives on stdin, never argv. An existing identity is
reused, never revived, relabelled, renewed or granted a new quota.
"""
import argparse,json,re,sqlite3,sys,time
from contextlib import closing,contextmanager
from pathlib import Path


def _validate_schema(db):
    from term_explainer.online.config import OnlineError
    try:
        for query in ('SELECT id,hash,label,created,expires,revoked FROM invites LIMIT 0',
                      'SELECT hash,invite_id,csrf,expires FROM sessions LIMIT 0',
                      'SELECT id,owner_id,idem,input_hash,body FROM jobs LIMIT 0',
                      'SELECT id,job_id,at,body FROM audit LIMIT 0'):
            db.execute(query)
    except sqlite3.Error:
        raise OnlineError('invalid_database','既有内测数据库结构无效；未初始化或创建表。') from None


class _ExistingInviteStore:
    """No DDL and no create permission, unlike OnlineStore's app bootstrap."""
    def __init__(self,path):
        self.path=Path(path)
        with closing(sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=10)) as db:
            _validate_schema(db)

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw',uri=True,timeout=10,isolation_level=None)) as db:
            db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON')
            _validate_schema(db)  # A replaced/invalid file also fails before BEGIN.
            db.execute('BEGIN IMMEDIATE')
            try:yield db;db.commit()
            except BaseException:db.rollback();raise


def provision_code(store,code,*,label='operator-private-beta',clock=time.time):
    from term_explainer.online.auth import hashed
    from term_explainer.online.config import OnlineError
    from term_explainer.online.store import identifier
    if not isinstance(code,str) or not re.fullmatch(r'[0-9]{6}',code):
        raise OnlineError('invalid_private_code','私人内测码必须是六位数字。')
    if not isinstance(label,str) or not 1<=len(label)<=100:
        raise OnlineError('invalid_private_label','私人内测备注无效。')
    now=clock()
    with store.transaction() as db:
        row=db.execute('SELECT id,label,expires,revoked FROM invites WHERE hash=?',(hashed(code),)).fetchone()
        if row:
            if row['label']!=label:raise OnlineError('invite_conflict','该凭证已属于其他邀请；未修改。',409)
            if row['revoked'] or row['expires']<=now:
                raise OnlineError('invite_unavailable','该邀请已撤销或过期；不会自动恢复。',409)
            return dict(id=row['id'],created=False,expiresAt=row['expires'],label=label)
        identity=identifier('invite');expires=now+7*86400
        db.execute('INSERT INTO invites(id,hash,label,created,expires) VALUES(?,?,?,?,?)',(identity,hashed(code),label,now,expires))
        return dict(id=identity,created=True,expiresAt=expires,label=label)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--code-stdin',action='store_true',required=True)
    args=parser.parse_args(argv)
    backend=args.backend_root.resolve()
    if not (backend/'term_explainer/online/auth.py').is_file():
        print('Verified backend directory is required.',file=sys.stderr);return 1
    sys.path.insert(0,str(backend))
    import os
    from term_explainer.online.config import load_config,OnlineError
    try:
        config=load_config(os.environ)
        if config.origin!='https://cdst.site' or config.api_prefix!='/psy-stats-test/api/term-explainer/':
            raise OnlineError('invalid_target','只允许测试站既有配置。')
        path=config.private_root/'jobs.sqlite'
        if not path.is_file() or path.is_symlink():raise OnlineError('missing_database','既有内测数据库未找到或路径不安全；未创建新库。')
        # Bound input before parsing; only a terminal newline is removed.
        value=sys.stdin.read(130).removesuffix('\n').removesuffix('\r')
        result=provision_code(_ExistingInviteStore(path),value)
        print(json.dumps(result,ensure_ascii=False));return 0
    except OnlineError as error:
        print(error.code+': '+error.message,file=sys.stderr);return 1
    except Exception:
        print('Private invite provisioning failed; inspect protected operator logs.',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
