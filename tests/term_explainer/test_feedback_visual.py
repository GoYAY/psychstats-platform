import copy
import unittest

from term_explainer.figures import validate_visual
try:
    from term_explainer.feedback_visual import prepare_feedback
except ImportError:
    prepare_feedback = None


def feedback_example():
    return {
        'layout': 'feedback_trace', 'example_label': '教学情境与示例数据',
        'scope_note': '人数和候选项是教学构造；观察同一对象跨轮次的变化。',
        'choices': [{'id': 'a', 'label': '访谈'}, {'id': 'b', 'label': '问卷'}, {'id': 'c', 'label': '实验'}],
        'criteria': [{'id': 'depth', 'label': '体验深度'}, {'id': 'feasible', 'label': '实施便利'}],
        'turns': [
            {'id': 't1', 'userCompared': ['a', 'b', 'c'], 'userPreferred': 'a', 'aiFocus': ['a', 'b'], 'aiIntroduced': ['depth'], 'userAdopted': []},
            {'id': 't2', 'userCompared': ['a', 'b'], 'userPreferred': 'a', 'aiFocus': ['a'], 'aiIntroduced': ['feasible'], 'userAdopted': [{'criterion': 'depth', 'fromTurn': 't1'}]},
            {'id': 't3', 'userCompared': ['a'], 'userPreferred': 'a', 'aiFocus': ['a'], 'aiIntroduced': [], 'userAdopted': [{'criterion': 'depth', 'fromTurn': 't1'}, {'criterion': 'feasible', 'fromTurn': 't2'}]},
        ],
    }


class FeedbackVisualTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(prepare_feedback), 'Trusted feedback visual preparation is not implemented')

    def test_counts_and_traceable_transfers_are_derived_without_mutation(self):
        payload = feedback_example(); before = copy.deepcopy(payload)
        actual = prepare_feedback(payload)
        self.assertEqual(actual['compared_counts'], [3, 2, 1])
        self.assertEqual(actual['focus_counts'], [2, 1, 1])
        self.assertIn({'criterion': 'depth', 'fromTurn': 't1', 'toTurn': 't2'}, actual['transfers'])
        self.assertEqual(payload, before)

    def test_other_domain_can_expand_options_without_forced_deterioration(self):
        p = feedback_example()
        p['choices'] = [{'id': 'a', 'label': '步行'}, {'id': 'b', 'label': '骑车'}, {'id': 'c', 'label': '公交'}]
        p['criteria'][0]['label'] = '通勤时间'; p['criteria'][1]['label'] = '天气条件'
        p['turns'][0]['userCompared'] = ['a']
        p['turns'][1]['userCompared'] = ['a', 'b']
        p['turns'][2]['userCompared'] = ['a', 'b', 'c']
        self.assertEqual(prepare_feedback(p)['compared_counts'], [1, 2, 3])

    def test_unknown_choice_and_preference_outside_comparison_are_rejected(self):
        for field, value in [('userCompared', ['missing']), ('userPreferred', 'c')]:
            p = feedback_example(); p['turns'][2][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): prepare_feedback(p)

    def test_duplicate_ids_or_comparison_items_are_rejected(self):
        for kind in ['choice', 'turn', 'comparison']:
            p = feedback_example()
            if kind == 'choice': p['choices'][1]['id'] = 'a'
            elif kind == 'turn': p['turns'][1]['id'] = 't1'
            else: p['turns'][0]['userCompared'] = ['a', 'a']
            with self.subTest(kind=kind), self.assertRaises(ValueError): prepare_feedback(p)

    def test_same_round_future_and_unintroduced_criteria_are_rejected(self):
        for source in ['t2', 't3', 'missing']:
            p = feedback_example(); p['turns'][1]['userAdopted'][0]['fromTurn'] = source
            with self.subTest(source=source), self.assertRaises(ValueError): prepare_feedback(p)
        p = feedback_example(); p['turns'][1]['userAdopted'][0]['criterion'] = 'feasible'
        with self.assertRaises(ValueError): prepare_feedback(p)

    def test_derived_score_and_unknown_fields_cannot_be_supplied(self):
        for mutate in [lambda p: p.update(score=0.9), lambda p: p['turns'][0].update(compared_count=99)]:
            p = feedback_example(); mutate(p)
            with self.assertRaises(ValueError): prepare_feedback(p)

    def test_long_labels_and_missing_example_notice_are_rejected(self):
        p = feedback_example(); p['choices'][0]['label'] = '很长' * 40
        with self.assertRaises(ValueError): prepare_feedback(p)
        p = feedback_example(); p.pop('example_label')
        with self.assertRaises(ValueError): prepare_feedback(p)

    def test_feedback_layout_is_validated_and_non_feedback_is_not_forced_into_it(self):
        spec = dict(kind='story', title='观察来回影响', alt='可数的候选与跨轮判断依据', takeaway='每个传递对象有来源', origin='teaching', payload=feedback_example())
        self.assertEqual(validate_visual(spec), spec)
        p = feedback_example(); p['turns'] = []
        with self.assertRaises(ValueError): prepare_feedback(p)


if __name__ == '__main__': unittest.main()
