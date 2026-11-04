"""Exercise the real adapter with only its external HTTP boundary replaced."""
import importlib
import json
import unittest
from unittest.mock import patch

try:
    api = importlib.import_module('term_explainer.deepseek')
except ModuleNotFoundError:
    api = None


class DeepSeekTests(unittest.TestCase):
    def test_substantive_teaching_chapter_can_support_located_procedure_without_paper_sections(self):
        from tests.fixtures.teaching_chapter import CHAPTER
        client=self.client({'content':CHAPTER})
        source=client.fetch('https://example.org/chapter',source_id='s1')
        self.assertTrue(source['technical_evidence_eligible'])
        self.assertEqual(source['scope'],'excerpt','A chapter is not the full book or research article')
        self.assertEqual(source['scope_basis'],'teaching_chapter_body_detected')
        for text in ['Prerequisites\nLearning Objectives\nBrief navigation only.', 'Abstract\n'+CHAPTER]:
            source=self.client({'content':text}).fetch('https://example.org/chapter',source_id='s1')
            self.assertFalse(source['technical_evidence_eligible'])

    def test_interrupted_http_response_is_safe_diagnostic_without_retry(self):
        from http.client import IncompleteRead
        for failure in (IncompleteRead(b'private partial body',100),ConnectionResetError('private transport detail')):
            with self.subTest(failure=type(failure).__name__),patch('term_explainer.deepseek.build_opener') as opener:
                opener.return_value.open.return_value.__enter__.return_value.read.side_effect=failure
                client=api.DeepSeekClient(api_key='private-key',max_calls=1)
                with self.assertRaises(api.DeepSeekError) as error:client.generate([{'role':'user','content':'JSON'}])
                self.assertEqual(error.exception.code,'provider_connection_interrupted')
                self.assertNotIn('private',str(error.exception))
                self.assertEqual(client.calls,1);self.assertEqual(opener.return_value.open.call_count,1)
                self.assertEqual(client.metrics[0]['error_code'],'provider_connection_interrupted')

    def test_length_stop_retains_safe_usage_and_actual_finish_reason(self):
        client=self.client({'model':'deepseek-flash','usage':{'prompt_tokens':12,'completion_tokens':8192,
            'completion_tokens_details':{'reasoning_tokens':7900},'private_text':'must-not-log'},
            'choices':[{'finish_reason':'length','message':{'content':'private partial answer'}}]})
        with self.assertRaises(api.DeepSeekError) as error: client.generate([{'role':'user','content':'json'}])
        self.assertEqual(error.exception.code,'model_truncated')
        self.assertEqual(client.metrics[0]['finish_reason'],'length')
        self.assertEqual(client.metrics[0]['usage']['completion_tokens'],8192)
        self.assertEqual(client.metrics[0]['usage']['reasoning_tokens'],7900)
        self.assertNotIn('private',json.dumps(client.metrics))

    def test_other_non_stop_finish_is_not_misreported_as_length_truncation(self):
        client=self.client({'model':'deepseek-flash','usage':{},
            'choices':[{'finish_reason':'content_filter','message':{'content':''}}]})
        with self.assertRaises(api.DeepSeekError) as error: client.generate([{'role':'user','content':'json'}])
        self.assertEqual(error.exception.code,'model_incomplete')
        self.assertEqual(client.metrics[0]['finish_reason'],'content_filter')

    def test_failed_request_records_stage_attempt_and_elapsed_without_private_input(self):
        sent=[]
        def transport(*args):
            sent.append(args)
            raise api.DeepSeekError('provider_http_504', '供应商请求失败（HTTP 504）。')
        client=api.DeepSeekClient(api_key='private-key', max_calls=1, transport=transport)
        with self.assertRaises(api.DeepSeekError):
            client.fetch('https://example.com/private-paper', source_id='a')
        self.assertEqual(client.calls,1)
        self.assertEqual(len(sent),1)
        event=client.metrics[0]
        self.assertEqual(event['kind'],'fetch')
        self.assertEqual(event['attempt'],1)
        self.assertEqual(event['outcome'],'failed')
        self.assertEqual(event['error_code'],'provider_http_504')
        self.assertGreaterEqual(event['elapsed_ms'],0)
        self.assertNotIn('private-key',json.dumps(event))
        self.assertNotIn('private-paper',json.dumps(event))
        with self.assertRaises(api.DeepSeekError): client.search('secret query')
        self.assertEqual(len(client.metrics),1)

    def test_received_response_event_does_not_claim_semantic_success(self):
        client=self.client({'title':'Example','content':'# Abstract\nShort summary.'})
        client.fetch('https://example.com/paper',source_id='a')
        self.assertEqual(client.metrics[0]['outcome'],'response_received')
        self.assertGreaterEqual(client.metrics[0]['elapsed_ms'],0)

    def test_invalid_response_structure_is_a_recorded_failure(self):
        client=self.client([])
        with self.assertRaises(api.DeepSeekError): client.search('example')
        self.assertEqual(client.metrics[0]['error_code'],'invalid_provider_response')

    def test_query_parameter_doi_does_not_swallow_other_url_parameters(self):
        url='https://crossmark.crossref.org:443/dialog?doi=10.1177%2F00131644251360386&domain=journals.sagepub.com&uri_scheme=https%3A&cm_version=v2.0'
        result=self.client({'results':[{'title':'Document is current','url':url}]}).search('DTP')
        self.assertEqual(result[0]['doi'],'10.1177/00131644251360386')
        self.assertEqual(result[0]['scope'],'metadata')

    def test_explicit_doi_in_search_title_remains_only_a_metadata_hint(self):
        result=self.client({'results':[{'title':'Example method - PubMed\ndoi: 10.1234/example. Online ahead of print.',
            'url':'https://pubmed.ncbi.nlm.nih.gov/12345678/'}]}).search('Example method')
        self.assertEqual(result[0]['doi'],'10.1234/example')
        self.assertEqual(result[0]['doi_basis'],'search_metadata_unverified')
        self.assertEqual(result[0]['text'],'')

    def test_unrelated_query_value_is_not_mistaken_for_article_doi(self):
        url='https://example.com/search?redirect=https%3A%2F%2Fdoi.org%2F10.1234%2Funrelated'
        result=self.client({'results':[{'title':'A search page','url':url}]}).search('example')
        self.assertEqual(result[0]['doi'],'')

    def test_decoded_ampersand_inside_doi_is_not_split_like_a_query_separator(self):
        url='https://example.com/article?doi=10.1234%2Fpart%26appendix&tracking=abc'
        result=self.client({'results':[{'title':'Example method','url':url}]}).search('example')
        self.assertEqual(result[0]['doi'],'10.1234/part&appendix')

    def test_conflicting_title_and_url_doi_are_not_silently_selected(self):
        result=self.client({'results':[{'title':'Example method doi: 10.1234/other',
            'url':'https://doi.org/10.1234/original'}]}).search('example')
        self.assertEqual(result[0]['doi'],'')
        self.assertTrue(result[0]['doi_conflict'])

    def test_abstract_without_paywall_marker_remains_abstract(self):
        client=self.client({'title':'A paper','content':'# Abstract\nWe introduce a new estimator.'})
        source=client.fetch('https://example.com/paper',source_id='a')
        self.assertEqual(source['scope'],'abstract')
        self.assertFalse(source['technical_evidence_eligible'])

    def test_unclassified_fetched_text_cannot_automatically_support_technical_detail(self):
        client=self.client({'title':'A paper','content':'Page text with unclear article coverage.'})
        source=client.fetch('https://example.com/paper',source_id='a')
        self.assertFalse(source['technical_evidence_eligible'])

    def test_clearly_present_body_sections_can_remain_body_excerpt(self):
        client=self.client({'title':'A paper','content':'# Abstract\nOverview.\n## Methods\nThe scoring rules are described here.\n## Results\nThe observed comparisons are described here.'})
        source=client.fetch('https://example.com/paper',source_id='a')
        self.assertEqual(source['scope'],'excerpt')
        self.assertTrue(source['technical_evidence_eligible'])

    def setUp(self):
        self.assertIsNotNone(api, 'DeepSeek adapter is not implemented')

    def client(self, response, limit=4):
        self.calls = []
        def transport(url, payload, headers, timeout):
            self.calls.append(dict(url=url, payload=payload, headers=headers, timeout=timeout))
            return response
        return api.DeepSeekClient(api_key='test-key-not-real', max_calls=limit, transport=transport)

    def test_model_output_is_parsed_with_actual_model_and_usage(self):
        reply = dict(model='deepseek-flash', usage={'prompt_tokens': 10, 'completion_tokens': 20},
                     choices=[{'finish_reason': 'stop', 'message': {'content': '{"status":"needs_sources"}'}}])
        client = self.client(reply)
        value = client.generate([{'role': 'user', 'content': '请输出 json'}])
        self.assertEqual(value.content, '{"status":"needs_sources"}')
        self.assertEqual(value.usage['completion_tokens'], 20)
        self.assertEqual(self.calls[0]['url'], 'https://api.deepseek.com/chat/completions')
        self.assertEqual(self.calls[0]['payload']['response_format'], {'type': 'json_object'})

    def test_search_returns_candidates_not_claimed_full_text(self):
        self.result = {'rerank_score': 2.4, 'title': 'A method', 'url': 'https://example.com/paper',
                       'snippet': '摘要片段', 'summary': '检索摘要', 'content': '', 'site_name': 'Publisher',
                       'site_icon': None, 'date': None, 'authority': 3}
        client = self.client({'results': [self.result]})
        result = client.search('Dominant Trait Profile')
        self.assertEqual(result[0]['title'], 'A method')
        self.assertEqual(result[0]['scope'], 'metadata')
        self.assertEqual(result[0]['text'], '')
        self.assertEqual(result[0]['search_summary'], '检索摘要')
        self.assertFalse(self.calls[0]['payload']['need_content'])
        self.assertEqual(self.calls[0]['url'], 'https://api.deepseek.com/v1/tools/search')

    def test_long_search_is_rejected_before_consuming_a_call(self):
        client = self.client({'results': []})
        with self.assertRaises(ValueError): client.search('x' * 129)
        self.assertEqual(self.calls, [])

    def test_fetch_returns_readable_excerpt_without_claiming_complete_article(self):
        client = self.client({'title': 'A paper', 'content': '# A paper\n正文中取得的内容。'})
        source = client.fetch('https://example.com/paper', source_id='read-a')
        self.assertEqual(source['scope'], 'excerpt')
        self.assertEqual(source['origin'], 'search')
        self.assertEqual(source['id'], 'read-a')
        self.assertEqual(self.calls[0]['url'], 'https://api.deepseek.com/v1/tools/fetch')

    def test_restricted_abstract_page_is_not_promoted_to_full_text(self):
        client = self.client({'title': 'Paper', 'content': '# Abstract\n研究摘要。\nGet full access to this article'})
        self.assertEqual(client.fetch('https://example.com/paper', source_id='a')['scope'], 'abstract')

    def test_private_or_credential_urls_are_rejected_without_network(self):
        client = self.client({'title': 'x', 'content': 'text'})
        for url in ['http://127.0.0.1/x', 'https://localhost/a', 'https://192.168.1.1/',
                    'https://user:pass@example.com/', 'file:///C:/secret', 'https://host.internal/a']:
            with self.subTest(url=url), self.assertRaises(ValueError): client.fetch(url, source_id='a')
        self.assertEqual(self.calls, [])

    def test_shared_call_budget_limits_search_fetch_and_model_requests(self):
        client = self.client({'results': []}, limit=1)
        client.search('a')
        with self.assertRaises(api.DeepSeekError) as error: client.fetch('https://example.com/', source_id='a')
        self.assertEqual(error.exception.code, 'call_budget_exhausted')
        self.assertEqual(len(self.calls), 1)

    def test_missing_credentials_does_not_silently_mock_success(self):
        with patch.dict('os.environ', {}, clear=True):
            client = api.DeepSeekClient(api_key='', max_calls=1)
            with self.assertRaises(api.DeepSeekError) as error: client.search('a')
        self.assertEqual(error.exception.code, 'missing_credentials')

    def test_model_truncation_is_reported_without_retry(self):
        client = self.client({'model': 'deepseek-flash', 'usage': {},
            'choices': [{'finish_reason': 'length', 'message': {'content': '{"cut":'}}]})
        with self.assertRaises(api.DeepSeekError) as error: client.generate([{'role': 'user', 'content': 'json'}])
        self.assertEqual(error.exception.code, 'model_truncated')
        self.assertEqual(len(self.calls), 1)

    def test_empty_search_is_valid_and_empty_fetch_is_not_reading(self):
        self.assertEqual(self.client({'results': []}).search('a'), [])
        with self.assertRaises(api.DeepSeekError):
            self.client({'title': '', 'content': ''}).fetch('https://example.com/', source_id='a')

    def test_captcha_content_is_not_read_or_bypassed(self):
        client = self.client({'title': 'Checking your browser', 'content': 'reCAPTCHA: checking your browser'})
        with self.assertRaises(api.DeepSeekError) as error: client.fetch('https://example.com/', source_id='a')
        self.assertEqual(error.exception.code, 'source_access_blocked')


if __name__ == '__main__': unittest.main()
