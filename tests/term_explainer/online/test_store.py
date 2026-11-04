from concurrent.futures import ThreadPoolExecutor
from term_explainer.online.store import OnlineStore
from term_explainer.online.config import OnlineError
from .helpers import OnlineCase

class StoreTests(OnlineCase):
    def store(self):return OnlineStore(self.root/'private'/'jobs.sqlite')

    def test_jobs_survive_reopen_and_are_owner_scoped_and_idempotent(self):
        store=self.store();manifest={'kind':'lesson','term':{'name':'样本'}}
        job=store.create_job('owner-a','key-1',manifest)
        self.assertEqual(store.create_job('owner-a','key-1',manifest)['id'],job['id'])
        self.assertNotEqual(store.create_job('owner-b','key-1',manifest)['id'],job['id'])
        with self.assertRaises(OnlineError) as c:store.get_job('owner-b',job['id'])
        self.assertEqual(c.exception.code,'not_found')
        with self.assertRaises(OnlineError) as c:store.create_job('owner-a','key-1',{'kind':'lesson','term':{'name':'变量'}})
        self.assertEqual(c.exception.code,'idempotency_conflict')
        self.assertEqual(self.store().get_job('owner-a',job['id'])['state'],'draft')
        self.assertEqual(len(self.store().list_jobs('owner-a')),1)

    def test_compare_and_swap_and_terminal_states_prevent_stale_resurrection(self):
        store=self.store();job=store.create_job('a','k',{'kind':'lesson'})
        next_=store.transition('a',job['id'],job['version'],'queued',{})
        with self.assertRaises(OnlineError):store.transition('a',job['id'],job['version'],'queued',{})
        cancelled=store.transition('a',job['id'],next_['version'],'cancelled',{})
        with self.assertRaises(OnlineError):store.transition('a',job['id'],cancelled['version'],'running',{})
        with self.assertRaises(OnlineError):store.transition('a',job['id'],cancelled['version'],'cancelled',{'owner_id':'b'})

    def test_concurrent_duplicate_creation_returns_one_job(self):
        store=self.store()
        with ThreadPoolExecutor(4) as pool:
            ids=list(pool.map(lambda _:store.create_job('a','shared',{'kind':'lesson'})['id'],range(12)))
        self.assertEqual(len(set(ids)),1)

    def test_audit_rejects_content_and_secrets(self):
        store=self.store()
        for key in ['text','prompt','api_key','response','invitation','document']:
            with self.subTest(key=key),self.assertRaises(OnlineError):store.audit('j',{key:'private'})
        store.audit('j',{'stage':'reading','calls':1,'total_tokens':30})
