"""Behavior tests: user intent must survive discovery and multi-paper reading."""
from copy import deepcopy
import importlib
import unittest

try:
    literature = importlib.import_module('term_explainer.literature')
except ModuleNotFoundError:
    literature = None


def document(source_id='paper-a', doi='10.1234/dtp', text='定义。方法描述。研究结果。', **changes):
    result = dict(id=source_id, title='合成测试文献（非真实论文）', doi=doi, text=text,
                  scope='full_text', origin='user', references=[])
    result.update(changes)
    return result


class LiteratureTests(unittest.TestCase):
    def test_background_claim_is_retained_without_satisfying_core_evidence(self):
        from term_explainer.literature import assemble_evidence_bundle
        source=dict(id='s',title='Background paper',scope='excerpt',text='A background explanation.',origin='user')
        claim=dict(id='background-1',module='background',statement='A related concept has this meaning.',stance='supports',detail='overview',evidence=[dict(source_id='s',start=0,end=10)])
        bundle=assemble_evidence_bundle(dict(term='Target'),[source],[claim],[])
        self.assertFalse(bundle['can_generate']);self.assertIn('definition',bundle['missing_modules'])
        self.assertEqual(bundle['claims'][0]['module'],'background')

    def test_unclassified_fetched_excerpt_does_not_unlock_technical_claim(self):
        source=document('a',scope='excerpt',technical_evidence_eligible=False)
        claim=dict(id='c',module='method',statement='技术步骤',stance='supports',detail='technical',evidence=[dict(source_id='a',start=0,end=3)])
        matrix=literature.build_evidence_matrix([source],[claim])
        self.assertEqual(matrix[0]['evidence_status'],'needs_full_text')

    def test_content_relationship_requires_both_documents_to_be_readable(self):
        sources = [document('a'), document('b','10.1234/b','',scope='metadata')]
        edge = dict(source='a',target='b',type='validates',reason='声称验证另一文献',evidence=[dict(source_id='a',start=0,end=3)])
        with self.assertRaises(ValueError): literature.validate_source_relations(sources,[edge])

    def setUp(self):
        self.assertIsNotNone(literature, 'literature evidence foundation is not implemented')
        self.anchor = {'term': '优势特质剖面计分法', 'english': 'Dominant Trait Profile',
                       'definition': '用户给出的、待核验的具体含义。'}

    def decide(self, sources=None, **changes):
        request = dict(anchor=deepcopy(self.anchor), sources=sources or [],
                       literature_prompted=False, network_allowed=True,
                       candidates=[], confirmed_candidate_id=None, critical_conflicts=[])
        request.update(changes)
        return literature.plan_literature(request)

    def test_no_sources_first_offers_literature_without_starting_search(self):
        result = self.decide()
        self.assertEqual(result['action'], 'ask_for_literature')
        self.assertEqual(result['mode'], 'none')
        self.assertFalse(result['can_generate'])

    def test_after_offer_no_sources_searches_instead_of_repeating_upload_request(self):
        result = self.decide(literature_prompted=True)
        self.assertEqual(result['action'], 'search')
        self.assertEqual(result['anchor'], self.anchor)

    def test_definition_only_is_a_valid_intent_anchor(self):
        anchor = {'definition': '在多个必须作出取舍的描述之间选择后估计特质。'}
        result = self.decide(anchor=anchor, literature_prompted=True)
        self.assertEqual(result['action'], 'search')
        self.assertEqual(result['anchor'], anchor)

    def test_empty_anchor_is_rejected(self):
        with self.assertRaises(ValueError):
            self.decide(anchor={'term': ' ', 'definition': ''})

    def test_network_refusal_never_enqueues_search(self):
        result = self.decide(literature_prompted=True, network_allowed=False)
        self.assertEqual(result['action'], 'explain_available_scope')
        self.assertFalse(result['can_generate'])

    def test_discovered_candidate_requires_user_confirmation(self):
        candidate = document('found', origin='search')
        result = self.decide(literature_prompted=True, candidates=[candidate])
        self.assertEqual(result['action'], 'confirm_concept')
        self.assertFalse(result['can_generate'])
        self.assertEqual(result['anchor'], self.anchor)

    def test_confirmed_search_candidate_becomes_reading_input(self):
        candidate = document('found', origin='search')
        result = self.decide(literature_prompted=True, candidates=[candidate], confirmed_candidate_id='found')
        self.assertEqual(result['action'], 'read_and_synthesize')
        self.assertEqual(result['source_ids'], ['found'])
        self.assertFalse(result['can_generate'], 'reading plan is not completed evidence analysis')

    def test_confirmation_cannot_select_an_unknown_candidate(self):
        with self.assertRaises(ValueError):
            self.decide(literature_prompted=True, candidates=[document('found')], confirmed_candidate_id='other')

    def test_single_paper_and_multiple_papers_have_distinct_modes(self):
        self.assertEqual(self.decide([document()])['mode'], 'single')
        result = self.decide([document(), document('b', '10.1234/other', '另一份全文。')])
        self.assertEqual(result['mode'], 'multiple')
        self.assertEqual(result['action'], 'read_and_synthesize')

    def test_critical_conflict_prevents_silent_redefinition(self):
        result = self.decide([document()], critical_conflicts=['术语对应两个不同的计分过程'])
        self.assertEqual(result['action'], 'clarify_conflict')
        self.assertEqual(result['anchor'], self.anchor)

    def test_duplicate_doi_and_text_do_not_become_independent_papers(self):
        records = literature.deduplicate_sources([
            document('a', 'https://doi.org/10.1234/DTP'),
            document('b', 'doi:10.1234/dtp', origin='reference')])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['aliases'], ['b'])
        self.assertEqual(set(records[0]['origins']), {'user', 'reference'})

    def test_same_doi_different_text_preserves_versions(self):
        records = literature.deduplicate_sources([document('a'), document('b', text='更正后的方法描述。')])
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]['work_id'], records[1]['work_id'])
        self.assertNotEqual(records[0]['content_hash'], records[1]['content_hash'])

    def test_no_doi_text_copy_is_deduplicated(self):
        records = literature.deduplicate_sources([document('a', doi=''), document('b', doi='')])
        self.assertEqual(len(records), 1)

    def test_input_sources_are_not_mutated(self):
        records = [document()]
        before = deepcopy(records)
        self.decide(records)
        literature.deduplicate_sources(records)
        self.assertEqual(records, before)

    def test_reference_selection_is_bounded_and_requires_purpose(self):
        references = [dict(id=f'r{i}', parent_id='a', depth=1, priority=10-i,
                           purpose='补足原始定义', module='definition') for i in range(8)]
        chosen = literature.select_reference_reads(references, read_ids=set())
        self.assertEqual([r['id'] for r in chosen], ['r0', 'r1', 'r2'])

    def test_reference_selection_skips_deeper_irrelevant_or_already_read_papers(self):
        references = [
            dict(id='deep', parent_id='a', depth=2, priority=20, purpose='背景', module='definition'),
            dict(id='empty', parent_id='a', depth=1, priority=10, purpose='', module='definition'),
            dict(id='read', parent_id='a', depth=1, priority=9, purpose='原始方法', module='method'),
            dict(id='valid', parent_id='a', depth=1, priority=8, purpose='方法条件', module='method')]
        chosen = literature.select_reference_reads(references, read_ids={'read'})
        self.assertEqual([r['id'] for r in chosen], ['valid'])

    def test_search_queries_preserve_identity_and_do_not_invent_translations(self):
        queries = literature.build_search_queries(self.anchor)
        self.assertLessEqual(len(queries), 2)
        self.assertTrue(any('Dominant Trait Profile' in q for q in queries))
        self.assertTrue(any('优势特质剖面计分法' in q for q in queries))

    def test_metadata_only_citation_does_not_prove_content_relation(self):
        sources = [document('a'), document('b', '10.1234/b', '', scope='metadata')]
        edge = dict(source='a', target='b', type='extends', reason='发展其方法',
                    evidence=[dict(source_id='b', start=0, end=2)])
        with self.assertRaises(ValueError):
            literature.validate_source_relations(sources, [edge])

    def test_reference_list_citation_can_remain_unread_without_content_claim(self):
        sources = [document('a', references=['b']), document('b', '10.1234/b', '', scope='metadata')]
        edge = dict(source='a', target='b', type='cites', reason='参考文献表列出', evidence=[])
        result = literature.validate_source_relations(sources, [edge])
        self.assertEqual(result[0]['target_scope'], 'metadata')
        self.assertFalse(result[0]['content_verified'])

    def test_content_relation_requires_actual_locatable_reading_evidence(self):
        sources = [document('a'), document('b', '10.1234/b', '后续方法扩展原有模型。')]
        edge = dict(source='b', target='a', type='extends', reason='在原模型上扩展',
                    evidence=[dict(source_id='b', start=0, end=6)])
        result = literature.validate_source_relations(sources, [edge])
        self.assertEqual(result[0]['evidence_status'], 'located')
        self.assertFalse(result[0]['content_verified'], 'valid offsets do not prove the interpretation')

    def test_out_of_bounds_or_unrelated_source_evidence_is_rejected(self):
        sources = [document('a'), document('b', '10.1234/b')]
        for reference in [dict(source_id='b', start=0, end=999), dict(source_id='missing', start=0, end=2)]:
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                literature.validate_source_relations(sources, [dict(source='a', target='b', type='compares',
                    reason='比较计分方法', evidence=[reference])])

    def test_duplicate_papers_cannot_vote_a_claim_into_consensus(self):
        sources = [document('a'), document('copy', '10.1234/dtp')]
        claims = [dict(id='c', module='definition', statement='用于迫选计分',
                       stance='supports', detail='overview', evidence=[dict(source_id='a', start=0, end=2),
                       dict(source_id='copy', start=0, end=2)])]
        rows = literature.build_evidence_matrix(sources, claims)
        self.assertEqual(rows[0]['independent_work_count'], 1)
        self.assertEqual(rows[0]['evidence_status'], 'located')
        self.assertNotIn('consensus', rows[0])

    def test_abstract_cannot_support_claimed_technical_algorithm(self):
        sources = [document('a', text='提出一种迫选计分方法。', scope='abstract')]
        claims = [dict(id='c', module='method', statement='完整估计算法', stance='supports',
                       detail='technical', evidence=[dict(source_id='a', start=0, end=4)])]
        rows = literature.build_evidence_matrix(sources, claims)
        self.assertEqual(rows[0]['evidence_status'], 'needs_full_text')

    def test_opposing_results_remain_distinct_without_majority_resolution(self):
        sources = [document('a'), document('b', '10.1234/b')]
        claims = [dict(id='c1', module='validation', statement='同一命题', stance='supports', detail='overview',
                       evidence=[dict(source_id='a', start=0, end=2)]),
                  dict(id='c2', module='validation', statement='同一命题', stance='disputes', detail='overview',
                       evidence=[dict(source_id='b', start=0, end=2)])]
        rows = literature.build_evidence_matrix(sources, claims)
        self.assertEqual([r['stance'] for r in rows], ['supports', 'disputes'])

    def test_zero_reference_budget_performs_no_reference_reads(self):
        references = [dict(id='r', parent_id='a', depth=1, priority=1,
                           purpose='核验定义', module='definition')]
        result = literature.select_reference_reads(references, set(), literature.LiteraturePolicy(max_reference_reads=0))
        self.assertEqual(result, [])

    def test_metadata_only_user_paper_respects_network_refusal(self):
        result = self.decide([document(text='', scope='metadata')], network_allowed=False)
        self.assertEqual(result['action'], 'explain_available_scope')

    def test_long_definition_uses_api_compatible_search_query_without_mutating_anchor(self):
        anchor = {'definition': '测量与研究的问题' * 80}
        queries = literature.build_search_queries(anchor)
        self.assertTrue(all(len(q) <= 128 for q in queries))
        self.assertEqual(anchor['definition'], '测量与研究的问题' * 80)

    def test_negative_or_boolean_read_budget_is_rejected(self):
        for limit in (-1, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                literature.LiteraturePolicy(max_reference_reads=limit)

    def test_invalid_boolean_control_is_not_treated_as_consent(self):
        with self.assertRaises(ValueError):
            self.decide(literature_prompted=True, network_allowed='false')

    def test_exhausted_search_reports_missing_hint_instead_of_looping(self):
        result = self.decide(literature_prompted=True, search_exhausted=True)
        self.assertEqual(result['action'], 'request_source_hint')

    def test_provided_citation_without_text_requests_retrieval_without_claiming_read(self):
        result = self.decide([document(text='', scope='metadata')])
        self.assertEqual(result['action'], 'retrieve_sources')
        self.assertEqual(result['reading_status'], 'not_analyzed')

    def test_metadata_cannot_be_declared_full_text_without_body(self):
        with self.assertRaises(ValueError):
            self.decide([document(text='', scope='full_text')])

    def test_relation_to_unknown_document_is_rejected(self):
        with self.assertRaises(ValueError):
            literature.validate_source_relations([document('a')], [dict(source='a', target='missing',
                type='cites', reason='有引用', evidence=[])])

    def test_content_relation_cannot_be_supported_by_a_third_unrelated_paper(self):
        sources = [document('a'), document('b', '10.1234/b'), document('c', '10.1234/c')]
        with self.assertRaises(ValueError):
            literature.validate_source_relations(sources, [dict(source='a', target='b', type='extends',
                reason='扩展关系', evidence=[dict(source_id='c', start=0, end=2)])])

    def bundle(self, claims, **changes):
        values = dict(anchor=self.anchor, sources=[document()], claims=claims, relations=[])
        values.update(changes)
        return literature.assemble_evidence_bundle(**values)

    def claim(self, claim_id, module, stance='supports', detail='overview'):
        return dict(id=claim_id, module=module, statement='测试命题', stance=stance, detail=detail,
                    evidence=[dict(source_id='paper-a', start=0, end=2)])

    def test_evidence_bundle_requires_definition_and_application_before_generation(self):
        result = self.bundle([self.claim('c1', 'definition')])
        self.assertEqual(result['status'], 'needs_sources')
        self.assertFalse(result['can_generate'])
        self.assertIn('application', result['missing_modules'])

    def test_ready_bundle_keeps_original_anchor_and_distinguishes_traceability_from_truth(self):
        result = self.bundle([self.claim('c1', 'definition'), self.claim('c2', 'application')])
        self.assertEqual(result['status'], 'ready_for_explanation')
        self.assertEqual(result['anchor'], self.anchor)
        self.assertTrue(result['can_generate'])
        self.assertTrue(result['requires_semantic_review'])

    def test_bundle_retains_explicit_material_conflict_as_a_question(self):
        result = self.bundle([self.claim('c1', 'definition'), self.claim('c2', 'application')],
                             critical_conflicts=['用户定义与论文提出的方法不同'])
        self.assertEqual(result['status'], 'needs_disambiguation')
        self.assertFalse(result['can_generate'])

    def test_opposite_definition_claims_trigger_confirmation_even_without_majority(self):
        claims = [self.claim('c1', 'definition'), self.claim('c2', 'definition', stance='disputes'),
                  self.claim('c3', 'application')]
        result = self.bundle(claims)
        self.assertEqual(result['status'], 'needs_disambiguation')

    def test_validation_disagreement_is_preserved_not_silently_resolved(self):
        claims = [self.claim('c1', 'definition'), self.claim('c2', 'application'),
                  self.claim('c3', 'validation'), self.claim('c4', 'validation', stance='disputes')]
        result = self.bundle(claims)
        self.assertEqual(len(result['claims']), 4)
        self.assertEqual(result['status'], 'ready_for_explanation')
        self.assertEqual(len(result['research_differences']), 1)

    def test_abstract_technical_gap_blocks_ready_bundle(self):
        claims = [self.claim('c1', 'definition'), self.claim('c2', 'application'),
                  self.claim('c3', 'method', detail='technical')]
        result = self.bundle(claims, sources=[document(scope='abstract')])
        self.assertEqual(result['status'], 'needs_sources')
        self.assertEqual(result['unresolved_claims'], ['c3'])

    def test_generation_cannot_omit_definition_requirement(self):
        with self.assertRaises(ValueError):
            self.bundle([], required_modules=('application',))

    def test_evidence_bundle_does_not_mutate_sources_or_claims(self):
        sources, claims = [document()], [self.claim('c1', 'definition'), self.claim('c2', 'application')]
        before = deepcopy((sources, claims))
        self.bundle(claims, sources=sources)
        self.assertEqual((sources, claims), before)


if __name__ == '__main__':
    unittest.main()
