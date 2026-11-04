import unittest
import xml.etree.ElementTree as ET
import json
import tempfile
from pathlib import Path
from sitegen.render import render_term
from tests.site.test_rendered_pages import sample_term


class PlainVisualTests(unittest.TestCase):
    def test_example_is_inside_plain_explanation_not_separate_duplicate(self):
        visual = {'decision': 'reuse', 'title': '观察关系', 'read': '看点的位置',
                  'takeaway': '表示一起变化', 'limit': '不能证明因果', 'basis': 'synthetic'}
        diagram = {'file': 'correlation-coefficient.svg', 'mobile_file': 'correlation-coefficient-mobile.svg',
                   'alt': '压力和幸福感', 'width': 760, 'height': 330, 'caption': '教学示意'}
        html = render_term(sample_term(), preview=False, visual=diagram, plain_visual=visual)
        self.assertEqual(html.count('src="../assets/diagrams/correlation-coefficient.svg"'), 1)
        self.assertIn('class="plain-example-visual"', html)
        self.assertLess(html.index('观察关系'), html.index('详细讲解'))
        self.assertIn('不能证明因果', html)
        self.assertEqual(html.count('<figcaption>'), 1)

    def test_svg_is_accessible_escaped_and_mobile_reflowed(self):
        from sitegen.plain_visuals import render_svg
        entry = {'kind': 'story', 'title': '三人分担 <90>', 'read': '看第三人', 'takeaway': '总额约束',
                 'panels': [{'title': '第一人', 'icon': 'coins', 'lines': ['20 元']},
                            {'title': '第二人', 'icon': 'coins', 'lines': ['30 元']},
                            {'title': '第三人', 'icon': 'coins', 'lines': ['只能付 40 元']}]}
        desktop = ET.fromstring(render_svg(entry))
        mobile = ET.fromstring(render_svg(entry, mobile=True))
        self.assertEqual(desktop.get('role'), 'img')
        self.assertIn('三人分担 <90>', ''.join(desktop.itertext()))
        self.assertGreater(float(mobile.get('height')), float(desktop.get('height')))
        self.assertFalse(desktop.findall('.//{http://www.w3.org/2000/svg}script'))

    def test_rejects_nonfinite_chart(self):
        from sitegen.plain_visuals import validate_entry
        entry = {'decision': 'draw', 'kind': 'scatter', 'title': '关系', 'basis': 'synthetic',
                 'read': '横轴', 'takeaway': '一起变化', 'limit': '不是因果',
                 'chart': {'x_label': '小时', 'y_label': '分', 'series': [{'label': '学生', 'values': [[1, float('nan')]]}]}}
        with self.assertRaises(ValueError):
            validate_entry('example', entry)

    def test_boxplot_has_quartile_box_and_separate_outlier(self):
        from sitegen.plain_visuals import render_svg
        entry = {'kind':'boxplot','title':'睡眠分布','rows':[{'label':'学生','low':5,'q1':6,'median':7,'q3':8,'high':9,'outliers':[11]}],'x_label':'小时'}
        root = ET.fromstring(render_svg(entry, mobile=True))
        self.assertTrue(root.findall('.//{http://www.w3.org/2000/svg}circle'))
        self.assertIn('Q1', ''.join(root.itertext()))
        self.assertIn('Q3', ''.join(root.itertext()))

    def test_every_existing_term_has_one_review_decision(self):
        from sitegen.plain_visuals import load_visuals, render_svg
        root = Path(__file__).resolve().parents[2] / 'site/content'
        entries = load_visuals(root / 'plain_visuals')
        ids = {json.loads(path.read_text(encoding='utf-8'))['id'] for path in (root/'drafts').glob('*.json')}
        self.assertEqual(set(entries), ids)
        for slug, entry in entries.items():
            if entry['decision'] == 'draw':
                for mobile in (False, True):
                    svg = ET.fromstring(render_svg(entry, mobile))
                    self.assertEqual(svg.tag, '{http://www.w3.org/2000/svg}svg', slug)
                    self.assertTrue(svg.find('{http://www.w3.org/2000/svg}desc').text, slug)
            elif entry['decision'] == 'skip':
                self.assertTrue(entry['reason'], slug)

    def test_duplicate_manifest_fails_instead_of_overwriting(self):
        from sitegen.plain_visuals import load_visuals
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('a','b'):
                (Path(tmp)/f'{name}.json').write_text(json.dumps({'example':{'decision':'skip','reason':'有理由'}}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                load_visuals(Path(tmp))
