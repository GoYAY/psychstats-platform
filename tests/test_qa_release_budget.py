import tempfile,unittest
from pathlib import Path
from term_explainer.online.store import OnlineStore
from term_explainer.online.worker import Worker
from term_explainer.online.config import OnlineError

class ReleaseBudgetTests(unittest.TestCase):
    def api(self):
        try:from tools import qa_release_budget;return qa_release_budget
        except ImportError:self.fail('Bounded continuation ledger missing')
    def store(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        store=OnlineStore(Path(temp.name)/'jobs.sqlite');Worker(None,store,runner=None);return store
    def add(self,store,key,operation='generate',tokens=1):
        with store.connection() as db:db.execute('INSERT INTO provider_calls(job_id,key,operation,state,day,reserved_tokens) VALUES(?,?,?,?,?,?)',('job',key,operation,'sent','2026-10-24',tokens))
    def test_restart_does_not_grant_fresh_calls_or_refund_uncertain_reservations(self):
        api=self.api();store=self.store();self.add(store,'historical',tokens=700)
        first=api.authorize_phase(store)
        for i in range(20):self.add(store,str(i))
        self.assertEqual(api.authorize_phase(store),first)
        self.assertEqual(api.check_phase(store)['delta']['modelRequests'],20)
        self.add(store,'excess')
        with self.assertRaises(OnlineError):api.check_phase(store)
    def test_pending_token_and_network_reservations_are_hard_limits(self):
        api=self.api()
        for kind in ['tokens','network']:
            with self.subTest(kind=kind):
                store=self.store();api.authorize_phase(store)
                if kind=='tokens':self.add(store,'large',tokens=400001)
                else:
                    for i in range(7):self.add(store,str(i),operation='fetch',tokens=0)
                with self.assertRaises(OnlineError):api.check_phase(store)

    def test_harness_selects_only_its_owner_queued_jobs_from_real_store(self):
        from tools import qa_online_release_server as harness
        store=self.store();mine=store.create_job('mine','a',dict(kind='lesson'));other=store.create_job('other','b',dict(kind='lesson'));draft=store.create_job('mine','c',dict(kind='lesson'))
        store.transition('mine',mine['id'],mine['version'],'queued',{});store.transition('other',other['id'],other['version'],'queued',{})
        self.assertEqual(harness.queued_ids(store,'mine'),[mine['id']])
        self.assertEqual(store.get_job('mine',draft['id'])['state'],'draft')
