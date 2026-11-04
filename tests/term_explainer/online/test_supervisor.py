from dataclasses import replace
import sys,time,threading
from term_explainer.online.supervisor import run_isolated
from term_explainer.online.worker import Worker
from .test_jobs import QueueFixture

class SupervisorTests(QueueFixture):
    def test_cpu_or_parser_hang_is_terminated_at_task_deadline(self):
        config,store,owner,job=self.queue();config=replace(config,limits=replace(config.limits,max_task_seconds=1));claim=Worker(config,store,runner=None,clock=lambda:self.now[0]).claim()
        before=time.monotonic();result=run_isolated(config,store,claim,[sys.executable,'-c','import time;time.sleep(30)'])
        self.assertLess(time.monotonic()-before,5);self.assertEqual(result['state'],'failed');self.assertEqual(result['progress']['error_code'],'task_timeout')

    def test_completed_child_is_not_overwritten_and_output_is_not_returned(self):
        config,store,owner,job=self.queue();claim=Worker(config,store,runner=None,clock=lambda:self.now[0]).claim()
        script="import json,sys;from term_explainer.online.store import OnlineStore;r=json.load(sys.stdin);s=OnlineStore("+repr(str(store.path))+");j=s.get_job(r['owner_id'],r['id']);s.transition(r['owner_id'],r['id'],j['version'],'complete',{'result':{'asset_id':'lesson.zip'}});print('PRIVATE_OUTPUT_NOT_FOR_HTTP')"
        result=run_isolated(config,store,claim,[sys.executable,'-c',script])
        self.assertEqual(result['state'],'complete');self.assertNotIn('PRIVATE_OUTPUT',str(result))

    def test_cancellation_stops_child_without_waiting_for_deadline(self):
        config,store,owner,job=self.queue();claim=Worker(config,store,runner=None,clock=lambda:self.now[0]).claim();marker=self.root/'child-ready'
        script='from pathlib import Path;import time;Path('+repr(str(marker))+').touch();time.sleep(30)'
        def cancel():
            deadline=time.monotonic()+3
            while not marker.exists() and time.monotonic()<deadline:time.sleep(.01)
            fresh=store.get_job(owner,job['id']);store.transition(owner,job['id'],fresh['version'],'cancelled',{})
        thread=threading.Thread(target=cancel);thread.start();before=time.monotonic()
        result=run_isolated(config,store,claim,[sys.executable,'-c',script]);thread.join()
        self.assertLess(time.monotonic()-before,5);self.assertEqual(result['state'],'cancelled')
