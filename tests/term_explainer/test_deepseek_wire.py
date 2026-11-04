"""Actual HTTP framing, not mocked response.read behavior."""
import json,unittest
from term_explainer.deepseek import DeepSeekClient,DeepSeekError,_transport
from .http_response_fixture import response_server

def complete_envelope():
    return dict(id='offline-completion-1',object='chat.completion',model='deepseek-flash',usage=dict(prompt_tokens=12,completion_tokens=8,total_tokens=20),choices=[dict(index=0,finish_reason='stop',message=dict(role='assistant',content='{"ok":true}'))])

def local_client(url):
    return DeepSeekClient(api_key='offline-only',max_calls=1,transport=lambda ignored,payload,headers,timeout:_transport(url,payload,headers,timeout),timeout=2)

class WireTests(unittest.TestCase):
    def test_complete_model_body_inside_unfinished_chunk_is_not_lost_in_nested_error(self):
        body=json.dumps(complete_envelope()).encode()
        for heartbeats in (False,True):
            with self.subTest(heartbeats=heartbeats),response_server(body,heartbeats=heartbeats,chunk_length_extra=20) as (url,requests):
                receipts=[];reply=local_client(url).generate([dict(role='user',content='JSON')],receipt=receipts.append)
                self.assertEqual(reply.content,'{"ok":true}');self.assertEqual(len(requests),1)
                self.assertEqual(receipts[0]['_transport_recovery']['kind'],'IncompleteRead')

    def test_genuinely_partial_nested_chunk_is_preserved_but_never_accepted(self):
        body=json.dumps(complete_envelope()).encode()[:-5]
        with response_server(body,chunk_length_extra=20) as (url,requests):
            receipts=[]
            with self.assertRaises(DeepSeekError) as caught:local_client(url).generate([dict(role='user',content='JSON')],receipt=receipts.append)
            error=caught.exception;self.assertEqual(error.code,'provider_connection_interrupted')
            self.assertEqual(error.transport_info['partial_bytes'],len(body)+2)
            self.assertEqual(error.partial_response,body+b'\r\n');self.assertEqual(receipts,[]);self.assertEqual(len(requests),1)

    def test_oversized_content_length_body_is_not_misclassified_as_connection_loss(self):
        with response_server(b'x'*(4*1024*1024+2),content_length_extra=0) as (url,requests):
            with self.assertRaises(DeepSeekError) as caught:local_client(url).generate([dict(role='user',content='JSON')])
            self.assertEqual(caught.exception.code,'response_too_large')

    def test_normal_chunked_keepalive_does_not_change_model_answer(self):
        body=json.dumps(complete_envelope()).encode()
        with response_server(body,terminate=True,heartbeats=True) as (url,requests):
            reply=local_client(url).generate([dict(role='user',content='JSON')])
            self.assertEqual(reply.content,'{"ok":true}');self.assertEqual(reply.usage['total_tokens'],20);self.assertEqual(len(requests),1)

    def test_complete_model_receipt_survives_missing_last_http_chunk_without_resend(self):
        body=json.dumps(complete_envelope()).encode();receipts=[]
        with response_server(body,heartbeats=True) as (url,requests):
            reply=local_client(url).generate([dict(role='user',content='JSON')],receipt=receipts.append)
            self.assertEqual(reply.content,'{"ok":true}');self.assertEqual(len(requests),1)
            self.assertEqual(receipts[0]['_transport_recovery']['kind'],'IncompleteRead')
            self.assertEqual(receipts[0]['usage']['total_tokens'],20)

    def test_complete_receipt_with_short_content_length_is_marked_not_silently_normal(self):
        body=json.dumps(complete_envelope()).encode();receipts=[]
        with response_server(body,content_length_extra=10) as (url,requests):
            local_client(url).generate([dict(role='user',content='JSON')],receipt=receipts.append)
            self.assertEqual(receipts[0]['_transport_recovery']['kind'],'IncompleteRead');self.assertEqual(len(requests),1)

    def test_incomplete_json_never_becomes_receipt(self):
        body=json.dumps(complete_envelope()).encode()[:-5];receipts=[]
        for framing in ({},{'content_length_extra':10}):
            with self.subTest(framing=framing),response_server(body,**framing) as (url,requests):
                with self.assertRaises(DeepSeekError) as caught:local_client(url).generate([dict(role='user',content='JSON')],receipt=receipts.append)
                self.assertEqual(caught.exception.code,'provider_connection_interrupted');self.assertEqual(len(requests),1)
        self.assertEqual(receipts,[])

    def test_complete_json_without_valid_completion_and_usage_stays_unknown(self):
        examples=[dict(ok=True),dict(complete_envelope(),usage=dict(total_tokens=20)),dict(complete_envelope(),usage=dict(prompt_tokens=12,completion_tokens=8,total_tokens=1))]
        for value in examples:
            with self.subTest(value=value),response_server(json.dumps(value).encode()) as (url,requests):
                with self.assertRaises(DeepSeekError) as caught:local_client(url).generate([dict(role='user',content='JSON')])
                self.assertEqual(caught.exception.code,'provider_connection_interrupted');self.assertEqual(len(requests),1)
