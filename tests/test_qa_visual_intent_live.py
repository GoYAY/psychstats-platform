import unittest
from tests.term_explainer.test_pipeline import ExternalDouble
from term_explainer.deepseek import ModelReply

class DiagnosticTests(unittest.TestCase):
    def test_policy_file_change_cannot_reset_phase_allowance(self):
        from tools.qa_visual_intent_live import phase_caps
        from term_explainer.online.config import OnlineError
        calls=[dict(job_id='old-policy',diagnostic='visual-intent-v1',operation='generate',reserved_tokens=1000) for _ in range(9)]
        self.assertEqual(phase_caps(calls,'new-policy'),dict(max_job_calls=3,max_job_tokens=241000))
        self.assertEqual(phase_caps(calls,'old-policy'),dict(max_job_calls=12,max_job_tokens=250000))
        with self.assertRaises(OnlineError):phase_caps(calls+calls,'new-policy')
    def test_control_protocol_failure_is_recorded_not_retried_or_passed(self):
        from unittest.mock import patch
        from tools.qa_visual_intent_live import control_review
        with patch('tools.qa_visual_intent_live.review_visual',side_effect=ValueError('invalid object pointer')) as mock:
            result=control_review({}, {}, [], object());self.assertEqual(result['protocol_status'],'invalid');self.assertNotIn('decision',result);self.assertEqual(mock.call_count,1)
    def test_malformed_whole_sample_uses_one_bounded_repair_not_new_job(self):
        from tools.qa_visual_intent_live import bounded_visual
        class Client(ExternalDouble):
            def generate(self,messages,*args,**kwargs):
                if not self.events:self.events.append(('generate',messages.copy()));return ModelReply('{"visual":{}}}','deepseek-flash',dict(total_tokens=10),'stop')
                return super().generate(messages)
        c=Client([dict(visual=dict(title='图'))])
        self.assertEqual(bounded_visual([dict(role='user',content='same benchmark')],c,lambda v:None),dict(title='图'));self.assertEqual(len(c.events),2)
        c=ExternalDouble([dict(wrong=True),dict(wrong=True)])
        with self.assertRaises(ValueError):bounded_visual([],c,lambda v:None)
        self.assertEqual(len(c.events),2)
