"""Exercise trusted figures and safe local teaching output, without live inference."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from .helpers import result_payload, request_payload
from term_explainer.contract import validate_request, validate_result

try:
    figures=importlib.import_module('term_explainer.figures')
    reader=importlib.import_module('term_explainer.reader')
except ModuleNotFoundError:
    figures=reader=None


class DeliveryTests(unittest.TestCase):
    def test_story_vertical_edge_keeps_node_and_relation_labels_clear(self):
        scenes=[dict(title='最初的判断',objects=[dict(id='u',kind='person',label='研究者',state='neutral')],connections=[]),
                dict(title='反复互动',objects=[dict(id='u',kind='person',label='研究者',state='neutral')],connections=[]),
                dict(title='对外转述',objects=[dict(id='u',kind='person',label='研究者',state='selected'),dict(id='claim',kind='record',label='未核验说法',state='mismatch'),dict(id='g',kind='group',label='同行群体',state='neutral')],connections=[dict(from_='u')])]
        scenes[2]['connections']=[{'from':'u','to':'g','label':'转述未核验说法','relation':'association'}]
        spec=dict(kind='story',title='跨会话例子',takeaway='观察同一对象的变化。',alt='三个教学场景',origin='conceptual',refs=[],payload=dict(layout='scenes',ordered=True,scenes=scenes))
        assets=figures.render_visual(spec,self.folder,run_external_qa=True)
        audit=json.loads(Path(assets.audit).read_text(encoding='utf-8'))
        self.assertEqual(len(audit['external_qa']),4)
        self.assertTrue(all(q['exit_code']==0 for q in audit['external_qa']))
        self.assertEqual(json.loads(Path(assets.data).read_text(encoding='utf-8')),spec)

    def test_two_series_line_legend_cannot_intersect_baseline_or_grid(self):
        spec=dict(kind='statistical',title='跨回合教学轨迹',takeaway='观察教学轨迹与参照。',alt='两条教学折线',origin='teaching',refs=[],
            payload=dict(chart_type='line',x_label='互动回合',y_label='继续核验倾向',x_unit='次',y_unit='分',series=[
                dict(label='基线参照（示意）',x=list(range(1,11)),y=[80]*10),
                dict(label='持续互动轨迹（教学示例）',x=list(range(1,11)),y=[80,79,77,75,72,69,66,63,60,58])]))
        assets=figures.render_visual(spec,self.folder,run_external_qa=True)
        audit=json.loads(Path(assets.audit).read_text(encoding='utf-8'))
        self.assertEqual(len(audit['external_qa']),4)
        self.assertTrue(all(q['exit_code']==0 for q in audit['external_qa']))
        self.assertEqual(json.loads(Path(assets.data).read_text(encoding='utf-8')),spec)

    def test_reader_shows_nonblocking_research_limits_and_formula_before_usage(self):
        payload=result_payload()
        payload['limitations']=[dict(text='新的研究设计仍需检验。',refs=[dict(source_id='s1',start=0,end=18)])]
        payload['formulas']=[dict(latex='x',symbols=[dict(symbol='x',meaning='教学符号')],refs=[dict(source_id='s1',start=0,end=18)])]
        lesson=validate_result(payload,validate_request(request_payload()))
        html=reader.render_lesson(lesson)
        self.assertIn('现有证据的范围',html)
        self.assertIn('新的研究设计仍需检验。',html)
        self.assertNotIn('资料待补充',html)
        self.assertLess(html.index('id="detailed_explanation"'),html.index('id="formulas"'))
        self.assertLess(html.index('id="formulas"'),html.index('id="how_to_use"'))
        self.assertIn('symbol-math',html)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)

    def test_story_exports_responsive_vectors_and_preview_with_provenance(self):
        self.assertIsNotNone(figures,'trusted figure renderer is missing')
        spec=result_payload()['visual']
        assets=figures.render_visual(spec,self.folder,'#4263bd',run_external_qa=False)
        for key in ('desktop','mobile','preview','pdf'):
            self.assertTrue(Path(getattr(assets,key)).is_file())
        self.assertIn('整锅汤',Path(assets.desktop).read_text(encoding='utf-8'))
        self.assertIn('conceptual',Path(assets.audit).read_text(encoding='utf-8'))

    def test_unconnected_and_overlong_objects_are_rejected(self):
        self.assertIsNotNone(figures,'trusted figure validator is missing')
        for kind in ('endpoint','label'):
            spec=deepcopy(result_payload()['visual'])
            if kind=='endpoint': spec['payload']['scenes'][0]['connections']=[{'from':'pot','to':'unknown','label':''}]
            else: spec['payload']['scenes'][0]['objects'][0]['label']='长'*17
            with self.subTest(kind=kind),self.assertRaises(ValueError): figures.validate_visual(spec)

    def test_statistical_data_is_used_unchanged_and_invalid_values_are_rejected(self):
        self.assertIsNotNone(figures,'trusted figure validator is missing')
        spec=dict(kind='statistical',title='教学分数',takeaway='比较教学数值',alt='两组教学值',origin='teaching',refs=[],
            payload=dict(chart_type='bar',x_label='组别',y_label='分数',x_unit='',y_unit='分',
                series=[dict(label='示例',x=['甲','乙'],y=[2,5])]))
        original=deepcopy(spec)
        assets=figures.render_visual(spec,self.folder,'#4263bd',run_external_qa=False)
        self.assertEqual(spec,original)
        self.assertEqual(json.loads(Path(assets.data).read_text(encoding='utf-8')),original)
        for value in (float('nan'),float('inf')):
            bad=deepcopy(spec); bad['payload']['series'][0]['y'][0]=value
            with self.assertRaises(ValueError): figures.validate_visual(bad)

    def test_reader_escapes_prose_places_question_first_and_keeps_each_option_feedback(self):
        self.assertIsNotNone(reader,'local teaching reader is missing')
        payload=result_payload()
        payload['blocks'][1]['paragraphs'][0]['text']='<script>alert(1)</script>'
        payload['blocks'][1]['paragraphs'][0]['emphasis']=[]
        lesson=validate_result(payload,validate_request(request_payload()))
        html=reader.render_lesson(lesson,None)
        self.assertLess(html.index('你可能会问'),html.index('操作性定义'))
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',html)
        self.assertNotIn('<script>alert(1)</script>',html)
        self.assertIn('学校名称是标识信息',html)
        self.assertIn('aria-live',html)
        self.assertNotIn('怎么实操',html)

    def test_formula_without_symbol_meanings_cannot_pass_complete_teaching(self):
        payload=result_payload()
        payload['formulas']=[dict(latex='x',symbols=[],refs=[dict(source_id='s1',start=0,end=10)])]
        with self.assertRaises(ValueError): validate_result(payload,validate_request(request_payload()))

