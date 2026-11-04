"""Worked examples derive their visible records; arrows require a declared meaning."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from term_explainer.figures import render_visual,validate_visual
from .helpers import result_payload


def comparison_spec():
    return dict(kind='story',title='一份选择怎样变成匹配记录',origin='teaching',refs=[],
        learning_goal='逐对比较同一份记录与参照。',adds_beyond_prose='展示两对具体选项的不同匹配结果。',
        takeaway='跟随甲的同一份选择记录。',alt='两对选项中一对不同、一对相同。',
        payload=dict(layout='pairwise_match',items=[dict(id='A',label='方案一',detail='第一种方案'),
            dict(id='B',label='方案二',detail='第二种方案'),dict(id='C',label='方案三',detail='第三种方案')],
            example_label='甲的排序（更偏好在前）',order=['B','A','C'],reference_label='示例参照',observed_label='甲实际选择',
            rows=[dict(pair=['A','B'],reference='A'),dict(pair=['A','C'],reference='A')],
            scope_note='只演示这两对选项。',output_label='匹配记录',next_label='后续处理'))


class VisualLogicTests(unittest.TestCase):
    def test_valid_pairwise_example_is_not_forced_into_unrelated_story_nodes(self):
        spec=comparison_spec()
        self.assertEqual(validate_visual(spec),spec)

    def test_pairwise_export_derives_both_rows_from_the_same_order(self):
        spec=comparison_spec(); original=deepcopy(spec)
        with tempfile.TemporaryDirectory() as folder:
            assets=render_visual(spec,folder,run_external_qa=False)
            audit=json.loads(Path(assets.audit).read_text(encoding='utf-8'))
            self.assertEqual(audit['worked_example']['observed'],['B','A'])
            self.assertEqual(audit['worked_example']['matches'],[0,1])
            self.assertEqual(audit['worked_example']['references'],['A','A'])
            self.assertEqual(json.loads(Path(assets.data).read_text(encoding='utf-8')),original)
            for name in ('figure.svg','figure-mobile.svg'):
                text=(Path(folder)/name).read_text(encoding='utf-8')
                for label in ('方案一','示例参照','甲实际选择','匹配记录','后续处理'):
                    self.assertIn(label,text)
        self.assertEqual(spec,original)

    def test_pairwise_payload_cannot_supply_made_up_match_results(self):
        spec=comparison_spec();spec['payload']['matches']=[1,1]
        with self.assertRaises(ValueError):validate_visual(spec)

    def test_six_long_choice_ids_fit_mobile_canvas_and_do_not_cover_labels(self):
        from term_explainer.figure_qa.audit_figure_collisions import extract_pdf_geometry
        spec=comparison_spec();payload=spec['payload'];ids=['AAAA','BBBB','CCCC','DDDD','EEEE','FFFF']
        payload['items']=[dict(id=key,label='方案'+str(i+1),detail='教学选项') for i,key in enumerate(ids)]
        payload['order']=[ids[1],ids[0],*ids[2:]]
        payload['rows']=[dict(pair=ids[:2],reference=ids[0]),dict(pair=[ids[0],ids[2]],reference=ids[0])]
        with tempfile.TemporaryDirectory() as folder:
            render_visual(spec,folder,run_external_qa=False)
            page=extract_pdf_geometry(Path(folder)/'figure-mobile.pdf')[0]
            for span in page.traces:
                x0,y0,x1,y1=span.bbox
                self.assertGreaterEqual(x0,0)
                self.assertLessEqual(x1,page.bbox[2])
            choice=next(s for s in page.texts if s.text=='AAAA')
            # Matplotlib may emit the Chinese label and digit as separate PDF
            # text objects; the left edge of 方案 is the spacing under test.
            label=next(s for s in page.texts if s.text=='方案')
            self.assertGreater(label.bbox[0],choice.bbox[2]+3)

    def test_invalid_pair_reference_duplicate_order_and_duplicate_pair_are_rejected(self):
        changes=[dict(order=['A','A','C']),dict(rows=[dict(pair=['A','B'],reference='C')]),
            dict(rows=[dict(pair=['A','B'],reference='A'),dict(pair=['B','A'],reference='A')])]
        for changeset in changes:
            spec=comparison_spec();spec['payload'].update(changeset)
            with self.subTest(changes=changeset),self.assertRaises(ValueError):validate_visual(spec)

    def test_single_scene_is_allowed_when_it_suffices(self):
        spec=result_payload()['visual'];spec['payload']['scenes']=spec['payload']['scenes'][:1]
        self.assertEqual(validate_visual(spec),spec)

    def test_unordered_mobile_scenes_remain_separate_without_transition_arrows(self):
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as folder:
            render_visual(result_payload()['visual'],folder,run_external_qa=False)
            root=ET.parse(Path(folder)/'figure-mobile.svg').getroot()
            positions={}
            for node in root.iter('{http://www.w3.org/2000/svg}text'):
                if node.text in ('整锅汤','这一勺'):positions[node.text]=float(node.attrib['y'])
            self.assertGreater(positions['这一勺']-positions['整锅汤'],40)

    def test_relation_type_and_ordering_must_have_supported_meanings(self):
        for change in ('relation','ordering'):
            spec=result_payload()['visual'];scene=spec['payload']['scenes'][0]
            scene['objects'].append(dict(id='other',kind='record',label='另一对象',state='neutral'))
            scene['connections']=[dict(from_='pot',to='other',label='比较',relation='invented')]
            scene['connections'][0]['from']=scene['connections'][0].pop('from_')
            if change=='ordering':
                scene['connections'][0]['relation']='comparison';spec['payload']['ordered']='yes'
            with self.subTest(change=change),self.assertRaises(ValueError):validate_visual(spec)

    def test_connection_marks_follow_semantic_type_not_every_line_is_an_arrow(self):
        import term_explainer.figures as figures
        self.assertTrue(hasattr(figures,'connection_mark'),'renderer needs a shared semantic connector decision')
        for kind,style,dash in [('comparison','-', 'solid'),('association','-', 'dashed'),('sequence','-|>', 'solid')]:
            mark=figures.connection_mark(dict(relation=kind,label='示例关系'))
            self.assertEqual((mark['arrowstyle'],mark['linestyle']),(style,dash))
        self.assertEqual(figures.connection_mark(dict(label='旧连接'))['arrowstyle'],'-')


if __name__=='__main__':unittest.main()
