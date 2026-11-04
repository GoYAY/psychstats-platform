"""Reference chasing and limited-evidence delivery.

The page has to exist even when the material is thin: a citation that printed
only a title is looked up once, and a lesson built from an incomplete evidence
set is delivered with an explicit scope note instead of stalling the task.
"""
import importlib
import json
import unittest
from copy import deepcopy

from .helpers import request_payload, result_payload
from .test_pipeline import ExternalDouble, analysis_payload
from term_explainer.contract import validate_request

try:
    pipeline = importlib.import_module('term_explainer.pipeline')
except ModuleNotFoundError:
    pipeline = None


TITLE = 'Team Involution Scale Development'
HIT = dict(id='hit-a', title=TITLE, doi='10.1234/team', url='https://doi.org/10.1234/team',
           scope='metadata', text='', origin='search', references=[])


def request_with_citation(*, limited=True, network=True):
    data = request_payload()
    data['sources'][0]['text'] += '\n参考文献：' + TITLE
    data['network_allowed'] = network
    data['allow_limited_delivery'] = limited
    data['optional_reference_reads'] = True
    data['max_reference_reads'] = 3
    return data


def title_only_candidate():
    return dict(id='ref-a', parent_id='s1', doi='', url='', title=TITLE, depth=1, priority=5,
                purpose='核验操作性定义', module='definition',
                reference_ref={'source_id': 's1', 'span_id': 's1#p0001'})


def definition_only_analysis(source_ids=('s1',)):
    """Only the definition module is covered, so the bundle cannot be complete."""
    payload = analysis_payload(source_ids)
    payload['claims'] = [c for c in payload['claims'] if c['module'] == 'definition']
    return payload


def lesson_with_scope_note():
    payload = result_payload()
    payload['limitations'] = [{
        'text': '本次只依据所给教学说明作答，一般性定义的跨研究范围未覆盖，补充文献可获得更完整解释。',
        'refs': [{'source_id': 's1', 'start': 0, 'end': 18}]}]
    return payload


class ReferenceChasingTests(unittest.TestCase):
    def test_title_only_citation_is_looked_up_then_read(self):
        data = request_with_citation()
        analysis = analysis_payload()
        analysis['reference_candidates'] = [title_only_candidate()]
        client = ExternalDouble([analysis, analysis_payload(('s1', 'ref-a')), result_payload()],
                                candidates=[HIT], pages={HIT['url']: '参考文献摘要中的实际片段。'})
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual([e[0] for e in client.events], ['model', 'search', 'fetch', 'model', 'model'])
        self.assertEqual(reply.action, 'complete')
        read = [s for s in reply.evidence['sources'] if s['origin'] == 'reference']
        self.assertEqual(len(read), 1)
        self.assertTrue(read[0]['text'])

    def test_lookup_of_a_different_paper_is_refused_without_fetch(self):
        data = request_with_citation()
        analysis = analysis_payload()
        analysis['reference_candidates'] = [title_only_candidate()]
        other = dict(HIT, title='A Completely Different Construct', url='https://doi.org/10.1234/other')
        client = ExternalDouble([analysis], candidates=[other],
                                pages={'https://doi.org/10.1234/other': '不应取得的片段。'})
        reply = pipeline.prepare_evidence(validate_request(data), client)
        self.assertFalse(any(e[0] == 'fetch' for e in client.events))
        self.assertEqual(reply.evidence['status'], 'ready_for_explanation')
        self.assertTrue(any(TITLE in n for n in reply.evidence['reference_access_notes']))
        self.assertFalse(reply.evidence.get('limited_delivery'))

    def test_lookup_failure_abandons_the_reference_and_still_generates(self):
        data = request_with_citation()
        analysis = definition_only_analysis()
        analysis['reference_candidates'] = [title_only_candidate()]
        client = ExternalDouble([analysis, definition_only_analysis(), lesson_with_scope_note()],
                                candidates=[])
        reply = pipeline.prepare_evidence(validate_request(data), client)
        self.assertFalse(any(e[0] == 'fetch' for e in client.events))
        self.assertEqual(reply.evidence['status'], 'ready_for_explanation')
        self.assertTrue(reply.evidence['limited_delivery'])
        client.replies = [deepcopy(analysis), lesson_with_scope_note()]
        lesson = pipeline.generate_prepared_lesson(validate_request(data), client, reply)
        self.assertEqual(lesson.action, 'complete')


class LimitedDeliveryTests(unittest.TestCase):
    def test_incomplete_evidence_is_delivered_with_a_scope_note(self):
        data = request_with_citation(limited=True, network=False)
        client = ExternalDouble([definition_only_analysis(), lesson_with_scope_note()])
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual(reply.action, 'complete')
        scope = reply.evidence['delivery_scope']
        self.assertTrue(scope['based_on'])
        self.assertIn('application', scope['missing_modules'])
        self.assertTrue(scope['note'])
        self.assertTrue(reply.lesson.limitations)

    def test_scope_note_is_required_before_a_limited_lesson_is_accepted(self):
        data = request_with_citation(limited=True, network=False)
        client = ExternalDouble([definition_only_analysis(), result_payload(), lesson_with_scope_note()])
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual(reply.action, 'complete')
        self.assertEqual(reply.repair_count, 1)
        self.assertIn('/limitations', json.dumps(client.events[-1][1], ensure_ascii=False))

    def test_reported_gap_is_delivered_when_it_blocks_no_module(self):
        data = request_with_citation(limited=True, network=False)
        analysis = analysis_payload()
        analysis['missing_evidence'] = ['原文只给出本领域的操作性定义。']
        review = dict(core_indices=[0], research_indices=[], reasons=['讲清概念所需的一般定义缺失。'])
        client = ExternalDouble([analysis, review, lesson_with_scope_note()])
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual(reply.action, 'complete')
        self.assertTrue(reply.evidence['limited_delivery'])
        self.assertEqual(reply.evidence['delivery_scope']['evidence_gaps'],
                         ['原文只给出本领域的操作性定义。'])
        self.assertTrue(reply.lesson.limitations)

    def test_incomplete_evidence_still_asks_when_limited_delivery_is_off(self):
        data = request_with_citation(limited=False, network=False)
        client = ExternalDouble([definition_only_analysis()])
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertEqual(reply.action, 'needs_sources')
        self.assertEqual(len(client.events), 1)

    def test_without_any_readable_text_no_lesson_is_attempted(self):
        data = request_payload()
        data['sources'][0]['text'] = ''
        data['sources'][0]['scope'] = 'metadata'
        data['allow_limited_delivery'] = True
        client = ExternalDouble([dict(analysis_payload(), claims=[])], candidates=[])
        reply = pipeline.generate_lesson(validate_request(data), client)
        self.assertNotEqual(reply.action, 'complete')
        self.assertIsNone(reply.lesson)
        self.assertFalse(any(e[0] == 'model' and len(e[1]) > 2 for e in client.events))


if __name__ == '__main__':
    unittest.main()
