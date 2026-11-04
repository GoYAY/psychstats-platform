from copy import deepcopy
import unittest
from term_explainer.figures import validate_visual
from term_explainer.online.visual_review import requires_visual_review


def chart(values=(20,76,8),semantics=None):
    return dict(kind='statistical',origin='teaching',title='题目构成（教学示例）',alt='三个区间',takeaway='查看构成',refs=[],
        presentation=dict(version=1,focus='whole',numeric_role='exact',layout='single',interaction='none'),
        data_semantics=semantics or dict(type='partition',denominator=50,rounding_digits=0),
        payload=dict(chart_type='bar',x_label='区间',y_label='占比',y_unit='%',series=[dict(label='题目',x=['难','中','易'],y=list(values))]))


class TeachingGateTests(unittest.TestCase):
    def test_single_statistical_teaching_figure_cannot_skip_semantic_review(self):
        self.assertTrue(requires_visual_review(chart((20,72,8))))

    def test_mutually_exclusive_percentages_cannot_hide_source_inconsistency(self):
        with self.assertRaisesRegex(ValueError,'构成比例'):validate_visual(chart())

    def test_valid_partition_is_preserved(self):
        value=chart((20,72,8));self.assertEqual(validate_visual(value),value)

    def test_independent_multiple_choice_percentages_need_not_total_100(self):
        value=chart((70,80,90),dict(type='independent',denominator=50,rounding_digits=0))
        self.assertEqual(validate_visual(value)['payload']['series'][0]['y'],[70,80,90])

    def test_reasonable_rounding_and_legacy_data_remain_readable(self):
        validate_visual(chart((33,33,33),dict(type='partition',denominator=None,rounding_digits=0)))
        old=chart();old.pop('data_semantics');validate_visual(old)
