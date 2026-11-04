from concurrent.futures import ThreadPoolExecutor
from term_explainer.online.config import load_config,OnlineError
from term_explainer.online.store import OnlineStore
from term_explainer.online.auth import InviteAuth
from term_explainer.online.worker import Worker
from .helpers import OnlineCase

class QueueFixture(OnlineCase):
    def queue(self):
        self.now=[1000];config=load_config(self.env);store=OnlineStore(self.root/'private'/'jobs.sqlite',clock=lambda:self.now[0])
        auth=InviteAuth(store,config,clock=lambda:self.now[0]);owner=auth.exchange(auth.create_invite('t')).owner_id
        job=store.create_job(owner,'one',{'kind':'lesson'});job=store.transition(owner,job['id'],job['version'],'queued',{})
        return config,store,owner,job

class QueueTests(QueueFixture):
    def test_targeted_claim_leaves_older_queued_job_unchanged(self):
        config,store,owner,older=self.queue();target=store.create_job(owner,'selected',{'kind':'lesson'});target=store.transition(owner,target['id'],target['version'],'queued',{})
        worker=Worker(config,store,runner=lambda j:None,clock=lambda:self.now[0])
        claim=worker.claim(job_id=target['id'])
        self.assertEqual(claim['id'],target['id']);self.assertEqual(store.get_job(owner,older['id']),older)
        self.assertIsNone(worker.claim(job_id=older['id']));self.assertEqual(store.get_job(owner,older['id']),older)

    def test_unknown_target_does_not_mutate_expired_or_queued_other_jobs(self):
        config,store,owner,job=self.queue();worker=Worker(config,store,runner=lambda j:None,clock=lambda:self.now[0]);old=worker.claim();self.now[0]+=500
        self.assertIsNone(worker.claim(job_id='not-present'));self.assertEqual(store.get_job(owner,job['id']),old)

    def test_only_one_worker_claims_and_revocation_blocks_claim(self):
        config,store,owner,job=self.queue()
        workers=[Worker(config,store,runner=lambda j:None,clock=lambda:self.now[0]) for _ in range(2)]
        with ThreadPoolExecutor(2) as pool:claims=list(pool.map(lambda w:w.claim(),workers))
        self.assertEqual(sum(c is not None for c in claims),1)
        claim=next(c for c in claims if c);self.assertEqual(claim['id'],job['id'])
        self.assertIsNone(workers[0].claim())
        store.transition(owner,job['id'],claim['version'],'cancelled',{})
        second=store.create_job(owner,'two',{'kind':'lesson'});store.transition(owner,second['id'],second['version'],'queued',{})
        InviteAuth(store,config,clock=lambda:self.now[0]).revoke_invite(owner)
        self.assertIsNone(workers[0].claim())

    def test_cancel_and_stale_lease_cannot_publish(self):
        config,store,owner,job=self.queue();worker=Worker(config,store,runner=lambda j:None,clock=lambda:self.now[0]);claim=worker.claim()
        store.transition(owner,job['id'],claim['version'],'cancelled',{})
        with self.assertRaises(OnlineError):worker.publish(claim,'complete',{'result':{'id':'x'}})
        self.assertEqual(store.get_job(owner,job['id'])['state'],'cancelled')

    def test_expired_lease_is_reclaimed_without_second_execution_of_unknown_send(self):
        config,store,owner,job=self.queue();worker=Worker(config,store,runner=lambda j:None,clock=lambda:self.now[0]);old=worker.claim()
        with store.transaction() as db:db.execute("INSERT INTO provider_calls(job_id,key,operation,state,day,reserved_tokens,output_bytes) VALUES(?,?,?,?,?,?,?)",(job['id'],'k','generate','sent','1970-01-01',100,0))
        self.now[0]+=500
        self.assertIsNone(worker.claim())
        self.assertEqual(store.get_job(owner,job['id'])['state'],'needs_reconciliation')

    def test_expired_lease_without_send_requeues_and_retains_checkpoint(self):
        config,store,owner,job=self.queue();worker=Worker(config,store,runner=lambda j:None,clock=lambda:self.now[0]);old=worker.claim()
        worker.publish(old,'running',{'checkpoint':{'next_section':2}})
        self.now[0]+=500;new=worker.claim()
        self.assertNotEqual(new['lease_token'],old['lease_token']);self.assertEqual(new['checkpoint'],{'next_section':2})

    def test_restart_recovers_a_saved_response_before_ledger_commit(self):
        from .test_budget import Provider
        from term_explainer.online.files import PrivateFiles
        from term_explainer.online.provider import BudgetedProvider
        config,store,owner,job=self.queue();worker=Worker(config,store,runner=lambda j:None,clock=lambda:self.now[0]);old=worker.claim()
        files=PrivateFiles(config.private_root/'tasks');under=Provider();messages=[{'role':'user','content':'test'}]
        BudgetedProvider(config,store,files,old,under,clock=lambda:self.now[0]).generate(messages)
        with store.transaction() as db:db.execute("UPDATE provider_calls SET state='sent'")
        self.now[0]+=500;new=worker.claim()
        self.assertIsNotNone(new,'A complete on-disk receipt must be reconciled, not require a new paid send')
        BudgetedProvider(config,store,files,new,under,clock=lambda:self.now[0]).generate(messages)
        self.assertEqual(under.calls,1)

    def test_runner_transport_failure_is_recorded_without_worker_crash(self):
        from term_explainer.deepseek import DeepSeekError
        config,store,owner,job=self.queue()
        def runner(claim):raise DeepSeekError('provider_timeout','never log this private string')
        worker=Worker(config,store,runner=runner,clock=lambda:self.now[0])
        result=worker.tick()
        self.assertEqual(result['state'],'needs_reconciliation')
        self.assertNotIn('private string',str(result))

    def test_confirmed_http_error_fails_the_job_instead_of_asking_for_reconciliation(self):
        from term_explainer.deepseek import DeepSeekError
        config,store,owner,job=self.queue()
        def runner(claim):raise DeepSeekError('provider_http_503','provider overloaded')
        worker=Worker(config,store,runner=runner,clock=lambda:self.now[0])
        self.assertEqual(worker.tick()['state'],'failed')
        with store.connection() as db:
            self.assertIn('provider_http_503',' '.join(r['body'] for r in db.execute('SELECT body FROM audit')))

    def test_revocation_during_runner_does_not_crash_or_publish_result(self):
        config,store,owner,job=self.queue()
        def runner(claim):
            InviteAuth(store,config,clock=lambda:self.now[0]).revoke_invite(owner)
            raise OnlineError('inactive_job','revoked',409)
        worker=Worker(config,store,runner=runner,clock=lambda:self.now[0]);result=worker.tick()
        self.assertEqual(result['state'],'cancelled');self.assertIsNone(result['result'])
