import importlib
import unittest
from .helpers import request_payload

try:
    evidence = importlib.import_module('term_explainer.evidence')
except ModuleNotFoundError:
    evidence = None


class EvidenceTests(unittest.TestCase):
    def test_bibliography_boundary_keeps_adjacent_body_evidence_usable(self):
        source=dict(id='s',scope='excerpt',text='Body evidence.\nReferences\nA citation.',locator_only_ranges=[dict(start=15,end=37)])
        spans=evidence.teaching_spans(source)
        self.assertTrue(spans[0]['evidence_eligible'])
        self.assertEqual(evidence.resolve_reference(dict(source_id='s',span_id=spans[0]['id']),[source])['end'],14)
        with self.assertRaises(ValueError):evidence.resolve_reference(dict(source_id='s',span_id=spans[-1]['id']),[source])

    def test_malformed_span_id_is_a_validation_error_not_an_attribute_crash(self):
        with self.assertRaises(ValueError):
            evidence.resolve_reference({'source_id':'s1','span_id':[]},request_payload()['sources'])

    def test_wrapped_lines_are_compact_but_keep_exact_source_offsets(self):
        data=request_payload(); data['sources'][0]['text']='\n'.join(['A wrapped line with readable context.']*100)
        context=evidence.prepare_context(data)
        spans=context['sources'][0]['spans']
        self.assertLess(len(spans),10)
        for span in spans:
            ref=evidence.resolve_reference({'source_id':'s1','span_id':span['id']},data['sources'])
            self.assertEqual(data['sources'][0]['text'][ref['start']:ref['end']],span['text'])

    def test_page_marker_cannot_be_cited_even_using_legacy_offsets(self):
        data=request_payload(); data['sources'][0]['text']='===== PDF PAGE 1 =====\nActual paragraph.'
        with self.assertRaises(ValueError):
            evidence.resolve_reference({'source_id':'s1','span_id':'s1#p0000'},data['sources'])

    def test_catalog_context_is_only_a_summary_not_unselected_private_content(self):
        data=request_payload(); data['catalog'][0]['private_full_text']='不得发送的非选定全文'
        data['known_terms']=[dict(id='personal',zh='个人概念',en='',aliases=[],kind='personal',private_full_text='另一个私人来源全文')]
        context=evidence.prepare_context(data)
        self.assertNotIn('private_full_text',context['catalog'][0])
        self.assertNotIn('private_full_text',context['known_terms'][0])
        self.assertEqual(context['catalog'][0]['zh'],'变量')

    def setUp(self): self.assertIsNotNone(evidence, 'evidence preparation is not implemented')

    def test_span_offsets_resolve_to_exact_source_text(self):
        spans = evidence.segment_source('s', '第一段。\n第二段。', chunk_size=8)
        self.assertEqual([s['text'] for s in spans], ['第一段。', '第二段。'])
        self.assertEqual(spans[1]['start'], 5)
        self.assertEqual(spans[1]['end'], 9)

    def test_context_preserves_definition_and_source_scope(self):
        context = evidence.prepare_context(request_payload())
        self.assertEqual(context['anchor']['definition'], '想研究的人与实际调查到的人。')
        self.assertEqual(context['sources'][0]['scope'], 'excerpt')
        self.assertTrue(context['sources'][0]['spans'])

    def test_longest_complete_term_wins_over_nested_short_word(self):
        catalog = [dict(id='variable', zh='变量', en='Variable', aliases=[], kind='classic'),
                   dict(id='latent-variable', zh='潜变量', en='Latent Variable', aliases=[], kind='classic')]
        self.assertIsNone(evidence.resolve_term('潜变量', catalog, 'latent-variable'))
        self.assertEqual(evidence.resolve_term('变量', catalog, 'latent-variable')['id'], 'variable')

    def test_alias_resolves_to_complete_meaning(self):
        catalog = [dict(id='factor-loading', zh='因子载荷', en='Factor Loading', aliases=['载荷'], kind='classic')]
        self.assertEqual(evidence.resolve_term('载荷', catalog, 'other')['id'], 'factor-loading')

    def test_span_citation_is_mapped_without_model_counting_characters(self):
        data = request_payload(); context = evidence.prepare_context(data)
        span = context['sources'][0]['spans'][0]
        ref = evidence.resolve_reference({'source_id': 's1', 'span_id': span['id']}, data['sources'])
        self.assertEqual(ref, {'source_id': 's1', 'start': 0, 'end': len(data['sources'][0]['text'])})


if __name__ == '__main__': unittest.main()
