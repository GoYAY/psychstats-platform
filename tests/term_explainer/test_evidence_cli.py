"""The planning entry is offline by default and cannot spend an implicit budget."""
import json
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tools import prepare_term_evidence as cli
from term_explainer.deepseek import DeepSeekClient, DeepSeekError
from .helpers import request_payload


ROOT=Path(__file__).resolve().parents[2]
ENTRY=ROOT/'tools/prepare_term_evidence.py'


class EvidenceCliTests(unittest.TestCase):
    def test_one_call_fetch_retains_text_for_later_analysis_without_second_http(self):
        sent=[]
        text='# Abstract\nA short teaching summary, not a full article.'
        def transport(*args):
            sent.append(args)
            return {'title':'A teaching document','content':text}
        client=DeepSeekClient(api_key='private-key',max_calls=1,transport=transport)
        data=request_payload(); data['network_allowed']=True
        data['sources'][0].update(scope='metadata',text='',url='https://example.com/paper')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.json'; report=Path(folder)/'report.json'
            path.write_text(json.dumps(data),encoding='utf-8')
            with patch.object(cli,'DeepSeekClient',return_value=client), contextlib.redirect_stdout(io.StringIO()):
                code=cli.main([str(path),'--report',str(report),'--live-evidence',
                    '--max-api-calls','1','--send-selected-sources'])
            result=json.loads(report.read_text(encoding='utf-8'))
        self.assertEqual(code,0)
        self.assertEqual(result['api_calls'],1)
        self.assertEqual(result['action'],'needs_budget')
        self.assertEqual(result['evidence']['sources'][0]['text'],text)
        self.assertEqual(result['evidence']['sources'][0]['scope'],'abstract')
        self.assertEqual(len(sent),1)

    def test_direct_report_saves_offline_result_without_provider_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            report=Path(folder)/'report.json'
            result=self.call(request_payload(),'--report',str(report))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(report.read_text(encoding='utf-8')),json.loads(result.stdout))

    def test_live_failure_report_keeps_actual_call_count_and_failure_stage(self):
        sent=[]
        def transport(*args):
            sent.append(args)
            if len(sent)==1:
                return {'title':'A teaching document','content':'# Abstract\nA short teaching summary, not a full article.'}
            raise DeepSeekError('provider_http_504','供应商请求失败（HTTP 504）。')
        client=DeepSeekClient(api_key='private-key',max_calls=2,transport=transport)
        data=request_payload()
        data['network_allowed']=True
        data['sources'][0].update(scope='metadata',text='',url='https://example.com/paper')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.json'; report=Path(folder)/'report.json'
            path.write_text(json.dumps(data),encoding='utf-8')
            with patch.object(cli,'DeepSeekClient',return_value=client), contextlib.redirect_stderr(io.StringIO()):
                code=cli.main([str(path),'--report',str(report),'--live-evidence',
                    '--max-api-calls','2','--send-selected-sources'])
            result=json.loads(report.read_text(encoding='utf-8'))
        self.assertEqual(code,2)
        self.assertEqual(result['api_calls'],2)
        self.assertEqual(result['api_events'][0]['kind'],'fetch')
        self.assertEqual(result['api_events'][1]['kind'],'completions')
        self.assertEqual(result['api_events'][1]['error_code'],'provider_http_504')
        self.assertEqual(len(sent),2)
        self.assertNotIn('private-key',json.dumps(result))

    def test_existing_report_prevents_paid_request_and_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            report=Path(folder)/'report.json'; report.write_text('previous record',encoding='utf-8')
            result=self.call(request_payload(),'--report',str(report),'--live-evidence',
                '--max-api-calls','2','--send-selected-sources')
            self.assertEqual(result.returncode,2)
            self.assertEqual(json.loads(result.stderr)['error']['code'],'report_exists')
            self.assertEqual(report.read_text(encoding='utf-8'),'previous record')

    def test_invalid_request_is_also_written_to_report(self):
        data=request_payload(); data['sources'][0]['scope']='invalid'
        with tempfile.TemporaryDirectory() as folder:
            report=Path(folder)/'report.json'
            result=self.call(data,'--report',str(report))
            self.assertEqual(result.returncode,2)
            saved=json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(saved['error']['code'],'invalid_request')
            self.assertEqual(saved['api_calls'],0)

    def call(self,data,*options):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.json'
            path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
            return subprocess.run([sys.executable,'-X','utf8',str(ENTRY),str(path),*options],
                cwd=ROOT,text=True,encoding='utf-8',capture_output=True,timeout=10)

    def test_default_entry_only_plans_and_does_not_echo_selected_paper_body(self):
        result=self.call(request_payload())
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['action'],'read_and_synthesize')
        self.assertEqual(data['mode'],'single')
        self.assertNotIn(request_payload()['sources'][0]['text'],result.stdout)

    def test_no_source_after_prompt_returns_search_plan_without_network(self):
        data=request_payload(); data.update(sources=[],network_allowed=True,literature_prompted=True)
        result=self.call(data)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['action'],'search')

    def test_live_mode_needs_explicit_budget_and_selected_source_consent(self):
        for options,code in [(('--live-evidence',),'budget_required'),(('--live-evidence','--max-api-calls','2'),'source_consent_required')]:
            with self.subTest(options=options):
                result=self.call(request_payload(),*options)
                self.assertEqual(result.returncode,2)
                self.assertEqual(result.stdout,'')
                self.assertEqual(json.loads(result.stderr)['error']['code'],code)

    def test_invalid_source_position_data_is_rejected_as_input_not_sent_anywhere(self):
        data=request_payload(); data['sources'][0]['scope']='made-up'
        result=self.call(data)
        self.assertEqual(result.returncode,2)
        self.assertEqual(json.loads(result.stderr)['error']['code'],'invalid_request')
        self.assertNotIn(data['sources'][0]['text'],result.stderr)

