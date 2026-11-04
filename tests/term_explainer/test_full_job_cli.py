import contextlib
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import test_full_job as fixtures

try:
    entry=importlib.import_module('tools.run_term_explainer')
except ModuleNotFoundError:
    entry=None


class FullJobCliTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.FullJobTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.folder=self.fixture.folder; self.input=self.folder/'input.json'; self.output=self.folder/'run'
        self.input.write_text(json.dumps(self.fixture.payload,ensure_ascii=False),encoding='utf-8')
    def call(self,*args,client=None):
        self.assertIsNotNone(entry,'whole document CLI is missing')
        out=io.StringIO(); err=io.StringIO()
        factory=dict(return_value=client) if client else dict(side_effect=AssertionError('must not construct provider'))
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err),patch.object(entry,'DeepSeekClient',**factory):
            code=entry.main(['--input',str(self.input),'--output',str(self.output),*args])
        return code,out.getvalue()+err.getvalue()
    def test_default_is_offline_estimate_and_never_creates_paid_task(self):
        code,text=self.call()
        self.assertEqual(code,0); self.assertIn('remaining_model_sections',text)
        self.assertFalse((self.output/'job.json').exists())
    def test_new_multi_literature_mode_estimates_without_creating_task(self):
        code,text=self.call('--multi-literature')
        self.assertEqual(code,0)
        plan=json.loads(text)
        self.assertTrue(plan['multi_literature'])
        self.assertEqual(plan['max_additional_works'],3)
        self.assertFalse(self.output.exists())
    def test_live_requires_explicit_completion_and_source_consent(self):
        code,text=self.call('--live')
        self.assertEqual(code,2)
        self.assertFalse((self.output/'job.json').exists())
    def test_existing_unrelated_output_files_are_not_overwritten(self):
        self.output.mkdir(); (self.output/'index.html').write_text('user file',encoding='utf-8')
        code,text=self.call('--live','--run-to-completion','--send-selected-sources')
        self.assertEqual(code,2)
        self.assertEqual((self.output/'index.html').read_text(encoding='utf-8'),'user file')
    def test_active_lock_is_not_removed(self):
        self.output.mkdir(); lock=self.output/'job.lock'; lock.write_text('active',encoding='utf-8')
        code,text=self.call('--live','--run-to-completion','--send-selected-sources')
        self.assertEqual(code,2); self.assertTrue(lock.exists())
