from term_explainer.online.render_setup import check_renderer
from term_explainer.online.config import load_config,OnlineError
from term_explainer.figures import render_visual
from tests.term_explainer.helpers import result_payload
from .helpers import OnlineCase

class RenderSetupTests(OnlineCase):
    def test_project_renderer_is_usable_in_permissive_only_environment(self):
        from pathlib import Path
        from dataclasses import replace
        config=replace(load_config(self.env),figure_qa_dir=Path('term_explainer/figure_qa').resolve(),cjk_font=Path('C:/Windows/Fonts/msyh.ttc'))
        self.assertTrue(check_renderer(config))

    def test_missing_renderer_setup_blocks_online_enable_before_model_cost(self):
        with self.assertRaises(OnlineError) as c:check_renderer(load_config(self.env))
        self.assertEqual(c.exception.code,'renderer_unavailable')

    def test_explicit_missing_qa_directory_never_falls_back_to_author_machine(self):
        with self.assertRaises(ValueError) as c:render_visual(result_payload()['visual'],self.root/'figure',qa_dir=self.root/'missing')
        self.assertIn('QA',str(c.exception));self.assertFalse((self.root/'figure').exists())
