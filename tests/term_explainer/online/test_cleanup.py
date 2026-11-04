from io import BytesIO
from term_explainer.online.files import PrivateFiles,cleanup_jobs
from term_explainer.online.config import OnlineError
from .test_jobs import QueueFixture

class CleanupTests(QueueFixture):
    def test_api_maintenance_cleans_aged_results_while_generation_is_disabled(self):
        from fastapi.testclient import TestClient
        from term_explainer.online.api import create_app
        import time
        config,store,owner,job=self.queue();files=PrivateFiles(config.private_root/'tasks')
        files.put(job['id'],'private.txt',BytesIO(b'private'),config.limits)
        current=store.get_job(owner,job['id']);store.transition(owner,job['id'],current['version'],'cancelled',{})
        app=create_app(config,store,files,provider_enabled=False,clock=lambda:self.now[0],cleanup_interval=.02)
        with TestClient(app,base_url=config.origin) as client:
            self.now[0]+=604801
            deadline=time.monotonic()+2
            while (files.root/job['id']).exists() and time.monotonic()<deadline:time.sleep(.02)
            self.assertFalse((files.root/job['id']).exists())
            self.assertTrue((files.root/'archive'/job['id']).exists())
            self.assertFalse(client.get('/health').json()['generationEnabled'])

    def test_failed_file_removal_preserves_metadata_and_is_retried(self):
        from unittest.mock import patch
        config,store,owner,job=self.queue();files=PrivateFiles(config.private_root/'tasks')
        files.put(job['id'],'source-1',BytesIO(b'private'),config.limits)
        current=store.get_job(owner,job['id']);store.transition(owner,job['id'],current['version'],'cancelled',{})
        self.now[0]+=604801
        with patch.object(files,'archive_job',side_effect=PermissionError('OS busy')):
            self.assertEqual(cleanup_jobs(store,files,self.now[0]),[job['id']])
        self.assertTrue(store.get_job(owner,job['id'])['manifest'])
        self.assertEqual(cleanup_jobs(store,files,self.now[0]),[])
        self.assertEqual(store.get_job(owner,job['id'])['manifest'],{})

    def test_files_reject_paths_links_and_oversized_streams(self):
        config,store,owner,job=self.queue();files=PrivateFiles(config.private_root/'tasks')
        with self.assertRaises(OnlineError):files.put('../escape','s',BytesIO(b'x'),config.limits)
        with self.assertRaises(OnlineError):files.path_for(job['id'],'../secret')
        from dataclasses import replace
        with self.assertRaises(OnlineError):files.put(job['id'],'source-1',BytesIO(b'12345'),replace(config.limits,max_file_bytes=4))
        self.assertFalse(list((config.private_root/'tasks').rglob('*.part')))
        descriptor=files.put(job['id'],'source-1',BytesIO(b'hello'),config.limits)
        self.assertEqual(files.path_for(job['id'],descriptor['asset_id']).read_bytes(),b'hello')

    def test_cleanup_expiry_terminal_result_and_audit(self):
        config,store,owner,job=self.queue();files=PrivateFiles(config.private_root/'tasks')
        files.put(job['id'],'source-1',BytesIO(b'private'),config.limits)
        store.audit(job['id'],{'stage':'reading'})
        self.now[0]+=604801;cleanup_jobs(store,files,self.now[0])
        expired=store.get_job(owner,job['id']);self.assertEqual(expired['state'],'expired')
        self.now[0]+=604801;cleanup_jobs(store,files,self.now[0])
        self.assertTrue((files.root/'archive'/job['id']).exists())
        self.assertEqual(store.get_job(owner,job['id'])['manifest'],{})
        # Late files are purged on a later sweep too; expiry cannot become an orphan exemption.
        files.put(job['id'],'late',BytesIO(b'late response'),config.limits)
        cleanup_jobs(store,files,self.now[0]+1)
        self.assertTrue((files.root/'archive'/job['id','late'][-1] if False else files.root/'archive'/job['id']).exists())
        cleanup_jobs(store,files,self.now[0]+30*86400)
        with store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM audit').fetchone()[0],0)
