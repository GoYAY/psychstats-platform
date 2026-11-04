"""Operator-only provisioning must preserve identity, expiry and old tasks."""
from contextlib import closing
from io import StringIO
import json,os,subprocess,sys
from pathlib import Path
from term_explainer.online.auth import InviteAuth
from term_explainer.online.config import load_config,OnlineError
from term_explainer.online.store import OnlineStore
from .helpers import OnlineCase


class PrivateBetaProvisionTests(OnlineCase):
    def provision(self):
        try:from tools.provision_private_beta import provision_code
        except ImportError:self.fail('Operator provisioner must support a supplied code without frontend changes')
        return provision_code

    def test_code_logs_in_but_only_hash_is_saved(self):
        provision=self.provision();store=OnlineStore(self.root/'private/jobs.sqlite')
        row=provision(store,'654321',clock=lambda:1000)
        auth=InviteAuth(store,load_config(self.env),clock=lambda:1001)
        self.assertEqual(auth.exchange('654321').owner_id,row['id'])
        self.assertTrue(row['created']);self.assertEqual(row['expiresAt'],1000+7*86400)
        self.assertNotIn('654321',json.dumps(row))
        self.assertNotIn(b'654321',store.path.read_bytes())

    def test_repeat_reuses_owner_without_extending_expiry_or_touching_tasks(self):
        provision=self.provision();store=OnlineStore(self.root/'private/jobs.sqlite')
        first=provision(store,'654321',clock=lambda:1000)
        job=store.create_job(first['id'],'existing',dict(kind='lesson'))
        again=provision(store,'654321',clock=lambda:2000)
        self.assertEqual(again['id'],first['id']);self.assertFalse(again['created'])
        self.assertEqual(again['expiresAt'],first['expiresAt'])
        self.assertEqual(store.get_job(first['id'],job['id']),job)

    def test_expired_revoked_or_conflicting_identity_is_never_revived(self):
        provision=self.provision();store=OnlineStore(self.root/'private/jobs.sqlite')
        row=provision(store,'654321',clock=lambda:1000)
        with self.assertRaises(OnlineError):provision(store,'654321',label='different',clock=lambda:1001)
        with self.assertRaises(OnlineError):provision(store,'654321',clock=lambda:row['expiresAt'])
        with store.transaction() as db:db.execute('UPDATE invites SET revoked=1 WHERE id=?',(row['id'],))
        with self.assertRaises(OnlineError):provision(store,'654321',clock=lambda:1001)
        with store.connection() as db:self.assertEqual(db.execute('SELECT revoked FROM invites').fetchone()[0],1)

    def test_invalid_codes_do_not_write_or_echo_secrets(self):
        provision=self.provision();store=OnlineStore(self.root/'private/jobs.sqlite')
        for value in ['1','654321\nextra',' 654321','abcdef',None]:
            with self.subTest(value=value),self.assertRaises(OnlineError):provision(store,value)
        with store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM invites').fetchone()[0],0)

    def test_cli_reads_stdin_and_outputs_no_code(self):
        self.provision();OnlineStore(self.root/'private/jobs.sqlite')
        script=Path(__file__).resolve().parents[3]/'tools/provision_private_beta.py'
        process=subprocess.run([sys.executable,'-X','utf8',str(script),'--code-stdin'],input='654321\n',capture_output=True,text=True,env={**os.environ,**self.env},timeout=10)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertNotIn('654321',process.stdout+process.stderr)
        self.assertTrue(json.loads(process.stdout)['created'])

    def test_concurrent_retries_create_one_identity(self):
        from concurrent.futures import ThreadPoolExecutor
        provision=self.provision();store=OnlineStore(self.root/'private/jobs.sqlite')
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows=list(pool.map(lambda _:provision(store,'654321'),range(8)))
        self.assertEqual(len({r['id'] for r in rows}),1)
        self.assertEqual(sum(r['created'] for r in rows),1)

    def test_cli_refuses_formal_target_and_does_not_create_missing_database(self):
        self.provision();script=Path(__file__).resolve().parents[3]/'tools/provision_private_beta.py'
        for prefix in ['/psy-stats/api/term-explainer/','/psy-stats-test/api/term-explainer/']:
            with self.subTest(prefix=prefix):
                env={**os.environ,**self.env,'TERM_API_PREFIX':prefix}
                proc=subprocess.run([sys.executable,'-X','utf8',str(script),'--code-stdin'],input='654321',text=True,capture_output=True,env=env,timeout=10)
                self.assertNotEqual(proc.returncode,0)
                self.assertNotIn('654321',proc.stderr+proc.stdout)
                self.assertFalse((self.root/'private/jobs.sqlite').exists())

    def test_cli_rejects_empty_or_unrelated_database_without_changing_bytes(self):
        import sqlite3
        self.provision();script=Path(__file__).resolve().parents[3]/'tools/provision_private_beta.py'
        path=self.root/'private/jobs.sqlite';path.parent.mkdir()
        for kind in ['empty','unrelated']:
            if kind=='empty':path.touch()
            else:
                with closing(sqlite3.connect(path)) as db:
                    db.execute('CREATE TABLE unrelated(value TEXT)');db.commit()
            before=path.read_bytes()
            proc=subprocess.run([sys.executable,'-X','utf8',str(script),'--code-stdin'],input='654321',text=True,capture_output=True,env={**os.environ,**self.env},timeout=10)
            self.assertNotEqual(proc.returncode,0,kind)
            self.assertEqual(path.read_bytes(),before,kind)
            self.assertNotIn('654321',proc.stderr+proc.stdout)
