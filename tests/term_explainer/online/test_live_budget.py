from .test_jobs import QueueFixture
from term_explainer.online.worker import Worker
from term_explainer.online.config import OnlineError

class LiveBudgetTests(QueueFixture):
    def test_explicit_continuation_caps_keep_old_unknown_sends_and_block_next_reserved_send(self):
        from tools.qa_online_generation_live import check_live_budget
        config,store,owner,job=self.queue();Worker(config,store,runner=None)
        with store.transaction() as db:
            for n in range(81):db.execute('INSERT INTO provider_calls VALUES(?,?,?,?,?,?,?)',(job['id'],str(n),'generate','sent' if n==0 else 'received','2026-10-22',100,0))
        caps=dict(model=110,network=10,tokens=1814277)
        report=check_live_budget(store,caps=caps)
        self.assertEqual(report['modelRequests'],81);self.assertEqual(report['uncertainRequests'],1)
        with self.assertRaises(OnlineError):check_live_budget(store,caps=dict(model=80,network=10,tokens=1814277))
        with self.assertRaises(ValueError):check_live_budget(store,caps=dict(model=111,network=10,tokens=1814277))

    def test_public_engineering_document_reads_count_in_same_network_cap(self):
        from tools.qa_online_generation_live import check_live_budget
        config,store,owner,job=self.queue();Worker(config,store,runner=None)
        with store.transaction() as db:
            db.execute('CREATE TABLE live_external_verifications(id TEXT PRIMARY KEY,operation TEXT,reference TEXT)')
            db.execute('INSERT INTO live_external_verifications VALUES(?,?,?)',('official-doc','fetch','https://api-docs.deepseek.com/quick_start/rate_limit/'))
            for n in range(12):db.execute('INSERT INTO provider_calls VALUES(?,?,?,?,?,?,?)',(job['id'],str(n),'fetch','received','2026-10-23',0,0))
        with self.assertRaises(OnlineError):check_live_budget(store)

    def test_explicit_replay_reuses_received_reply_without_new_charge_and_checks_live_lease(self):
        from tools.qa_online_generation_live import InheritedReplies
        from term_explainer.online.provider import BudgetedProvider
        from term_explainer.online.files import PrivateFiles
        from term_explainer.deepseek import ModelReply
        config,store,owner,job=self.queue();worker=Worker(config,store,runner=None,clock=lambda:self.now[0]);old=worker.claim();files=PrivateFiles(config.private_root/'tasks')
        class External:
            def generate(self,messages,*args,**kwargs):return ModelReply('{"ok":true}','offline',dict(total_tokens=10),'stop')
        provider=BudgetedProvider(config,store,files,old,External(),clock=lambda:self.now[0]);messages=[dict(role='user',content='test')];provider.generate(messages)
        fresh=store.get_job(owner,job['id']);store.transition(owner,job['id'],fresh['version'],'cancelled',{})
        new=store.create_job(owner,'retry',{'kind':'lesson'});store.enqueue(owner,new['id'],new['version'],{},max_queue=10);claim=worker.claim()
        class Never:
            def generate(self,*a,**kw):raise AssertionError('Replay must not send')
        current=BudgetedProvider(config,store,files,claim,Never(),clock=lambda:self.now[0]);replay=InheritedReplies(current,[old['id']])
        self.assertEqual(replay.generate(messages).content,'{"ok":true}');self.assertEqual(current.calls,0)
        fresh=store.get_job(owner,new['id']);store.transition(owner,new['id'],fresh['version'],'cancelled',{})
        with self.assertRaises(OnlineError):replay.generate(messages)

    def test_live_budget_does_not_reset_at_utc_midnight(self):
        from tools.qa_online_generation_live import check_live_budget
        config,store,owner,job=self.queue();Worker(config,store,runner=None)
        with store.transaction() as db:
            for n in range(81):
                db.execute('INSERT INTO provider_calls VALUES(?,?,?,?,?,?,?)',(job['id'],str(n),'generate','received','2026-10-22' if n<80 else '2026-10-23',1,0))
        with self.assertRaises(OnlineError):check_live_budget(store)

    def test_model_and_network_counts_and_unknown_token_reservations_are_bounded(self):
        from tools.qa_online_generation_live import check_live_budget
        config,store,owner,job=self.queue();Worker(config,store,runner=None)
        with store.transaction() as db:
            db.execute('INSERT INTO provider_calls VALUES(?,?,?,?,?,?,?)',(job['id'],'one','generate','sent','2026-10-23',2000001,0))
        with self.assertRaises(OnlineError):check_live_budget(store)
        with store.transaction() as db:
            db.execute('DELETE FROM provider_calls')
            for n in range(12):db.execute('INSERT INTO provider_calls VALUES(?,?,?,?,?,?,?)',(job['id'],str(n),'fetch','received','2026-10-23',0,0))
        self.assertEqual(check_live_budget(store)['networkRequests'],12)
        with store.transaction() as db:db.execute('INSERT INTO provider_calls VALUES(?,?,?,?,?,?,?)',(job['id'],'extra','search','sent','2026-10-23',0,0))
        with self.assertRaises(OnlineError):check_live_budget(store)
