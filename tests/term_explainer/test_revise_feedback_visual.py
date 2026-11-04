import copy
import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from term_explainer.figures import render_visual
from tests.term_explainer.test_feedback_visual import feedback_example
try:
    from tools.revise_entanglement_visual import revise_lesson, revise_entanglement_visual
except ImportError:
    revise_lesson = revise_entanglement_visual = None


class ReviseFeedbackVisualTests(unittest.TestCase):
    def test_revision_has_directly_viewable_preview_with_local_images(self):
        # A revised ZIP alone leaves the previously delivered preview showing
        # the old visual. The revision must also deliver a working local page.
        class Images(HTMLParser):
            def __init__(self):
                super().__init__(); self.paths = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag in ('img', 'source'):
                    self.paths.append(attrs.get('src') or attrs.get('srcset'))
        original = {
            'content_id': 'lesson-preview', 'status': 'complete',
            'term': {'id': 'human-ai-entanglement', 'zh': '纠缠', 'en': 'Human–AI entanglement'},
            'blocks': [{'id': 'plain_explanation', 'heading': '通俗解释',
                        'paragraphs': [{'text': '观察同一组选择在互动中的变化。', 'emphasis': [], 'refs': []}]}],
            'visual': {'refs': []}, 'provenance': {}, 'relations': [],
        }
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'original'; source.mkdir()
            initial = json.dumps(original, ensure_ascii=False)
            (source/'lesson.json').write_text(initial, encoding='utf-8')
            target = Path(folder)/'revision'
            revise_entanglement_visual(source, target, run_external_qa=False)
            page = target/'preview/index.html'
            self.assertTrue(page.is_file(), 'The revised visual lacks a directly viewable page')
            images = Images(); images.feed(page.read_text(encoding='utf-8'))
            self.assertEqual(len(images.paths), 2)
            for relative in images.paths:
                path = page.parent/relative
                self.assertTrue(path.is_file(), f'Broken figure reference: {relative}')
                self.assertEqual(path.read_bytes(), (target/'figures'/path.name).read_bytes())
            self.assertEqual((source/'lesson.json').read_text(encoding='utf-8'), initial)

    def test_revision_preserves_prose_quiz_and_evidence_locations(self):
        self.assertTrue(callable(revise_lesson), 'Visual revision adapter is missing')
        original = {'content_id': 'lesson-one', 'blocks': [{'id': 'plain_explanation', 'paragraphs': [{'text': '先建立直觉，再用图观察对象。', 'refs': [{'source_id': 's1', 'start': 1, 'end': 12}]}]}], 'quiz': {'question': '测试问题'}, 'visual': {'refs': [{'source_id': 's1', 'start': 1, 'end': 12}]}, 'provenance': {}}
        before = copy.deepcopy(original); revised = revise_lesson(original)
        self.assertEqual(original, before)
        self.assertEqual(revised['blocks'], before['blocks'])
        self.assertEqual(revised['quiz'], before['quiz'])
        self.assertEqual(revised['visual']['refs'], before['visual']['refs'])
        self.assertNotEqual(revised['content_id'], before['content_id'])
        self.assertEqual(revised['visual']['payload']['layout'], 'feedback_trace')

    def test_output_cannot_overwrite_original_job_or_public_assets(self):
        self.assertTrue(callable(revise_entanglement_visual), 'Visual revision adapter is missing')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            for output in [path, path/'nested']:
                with self.subTest(output=output), self.assertRaises(ValueError):
                    revise_entanglement_visual(path, output)

    def test_actual_feedback_svg_contains_derived_count_marks(self):
        spec = dict(kind='story', title='可核对的反馈', alt='三个回合及可计数卡片', takeaway='对象和判断依据跨轮传递', origin='teaching', payload=feedback_example())
        with tempfile.TemporaryDirectory() as folder:
            try:
                assets = render_visual(spec, folder, run_external_qa=False)
            except (KeyError, UnboundLocalError) as error:
                self.fail('Trusted feedback renderer is not implemented: '+str(error))
            for name in [assets.desktop, assets.mobile]:
                svg = ElementTree.parse(name).getroot()
                marks = {g.attrib.get('id'): ''.join(g.itertext()).strip() for g in svg.iter() if g.attrib.get('id', '').startswith('compared-count-')}
                self.assertEqual([marks['compared-count-'+key] for key in ['t1', 't2', 't3']], ['3项', '2项', '1项'])
            self.assertTrue(Path(assets.pdf).is_file())

    def test_legal_multiline_criteria_fit_chips_and_export_scope(self):
        from term_explainer.feedback_visual import render_feedback
        import matplotlib.pyplot as plt
        payload=feedback_example()
        for criterion in payload['criteria']:criterion['label']='甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳'
        for mobile,width in [(False,1000),(True,360)]:
            fig,_,_=render_feedback(payload,width,mobile,'#4262bf')
            try:
                ax=fig.axes[0]
                for t in ax.texts:t.set_fontfamily('Microsoft YaHei')
                fig.canvas.draw();renderer=fig.canvas.get_renderer()
                labels=[t for t in ax.texts if t.get_text().replace('\n','')==payload['criteria'][0]['label']]
                self.assertTrue(labels)
                for t in labels:
                    box=t.get_window_extent(renderer)
                    chips=[p for p in ax.patches if hasattr(p,'get_bbox') and p.get_window_extent(renderer).contains(*ax.transData.transform(t.get_position()))]
                    self.assertTrue(any(p.get_window_extent(renderer).height>=box.height+4 for p in chips),'Criterion escapes chip')
                self.assertTrue(any(t.get_text().replace('\n','')==payload['scope_note'] for t in ax.texts),'Standalone exports omit scope note')
            finally:plt.close(fig)

    def test_preference_outside_response_points_to_group_not_arbitrary_choice(self):
        from term_explainer.feedback_visual import render_feedback
        import matplotlib.pyplot as plt
        payload=feedback_example();payload['turns'][0]['aiFocus']=['b']
        fig,_,_=render_feedback(payload,1000,False,'#4262bf')
        try:
            ax=fig.axes[0];arrow=next((p for p in ax.patches if p.get_gid()=='preference-transfer-t1'),None)
            self.assertIsNotNone(arrow,'Preference transfer needs inspectable identity')
            choice=next(p for p in ax.patches if p.get_gid()=='choice-t1-ai-b')
            self.assertLess(arrow._posA_posB[1][1],choice.get_y(),'No specific unprovided choice target')
        finally:plt.close(fig)

    def test_mobile_return_curves_do_not_cross_round_titles(self):
        self.assertTrue(callable(revise_lesson))
        lesson = revise_lesson({'content_id': 'visual-example', 'visual': {'refs': []}})
        with tempfile.TemporaryDirectory() as folder:
            try:
                render_visual(lesson['visual'], folder, run_external_qa=True)
            except ValueError as error:
                self.fail('Feedback geometry must pass rendered mobile collision audit: '+str(error))


if __name__ == '__main__': unittest.main()
