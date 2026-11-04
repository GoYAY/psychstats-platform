import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from sitegen.build import build_site
from sitegen.render import render_term
from tests.site.test_rendered_pages import sample_term


ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ("data-cleaning", "p-value", "correlation-coefficient")


class DiagramTests(unittest.TestCase):
    def test_cleaning_first_step_label_clears_number_badge(self):
        root = ET.parse(ROOT / "site/assets/diagrams/data-cleaning.svg").getroot()
        ns = {"svg": "http://www.w3.org/2000/svg"}
        title = next(node for node in root.findall(".//svg:text", ns) if node.text == "保留原始数据")
        badge = next(node for node in root.findall(".//svg:circle", ns) if node.get("cx") == "47")
        estimated_left = float(title.get("x")) - len(title.text) * float(title.get("font-size")) / 2
        badge_right_with_gap = float(badge.get("cx")) + float(badge.get("r")) + 8
        self.assertGreaterEqual(estimated_left, badge_right_with_gap)

    def test_term_visual_has_image_text_alternative_and_caption(self):
        visual = {
            "file": "data-cleaning.svg",
            "mobile_file": "data-cleaning-mobile.svg",
            "alt": "从保留原始数据到输出分析数据与日志的流程。",
            "caption": "异常值不应自动删除。",
            "width": 760,
            "height": 300,
        }
        html = render_term(sample_term(), preview=False, visual=visual)
        self.assertIn('<section class="term-visual"><h2>图解</h2>', html)
        self.assertIn('<div class="diagram-scroll">', html)
        self.assertIn('<source media="(max-width: 600px)" srcset="../assets/diagrams/data-cleaning-mobile.svg">', html)
        self.assertNotIn('图解可横向滑动查看完整内容', html)
        self.assertIn('src="../assets/diagrams/data-cleaning.svg"', html)
        self.assertIn('alt="从保留原始数据到输出分析数据与日志的流程。"', html)
        self.assertIn('width="760" height="300"', html)
        self.assertIn('<figcaption>异常值不应自动删除。</figcaption>', html)

    def test_public_build_links_and_copies_only_three_sample_diagrams(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            build_site("public", output)
            for slug in SAMPLES:
                html = (output / "terms" / f"{slug}.html").read_text(encoding="utf-8")
                self.assertIn('class="term-visual"', html, slug)
                self.assertIn(f'assets/diagrams/{slug}-glass.svg', html, slug)
                asset = output / "assets" / "diagrams" / f"{slug}-glass.svg"
                self.assertTrue(asset.is_file(), slug)
                self.assertEqual(ET.parse(asset).getroot().tag, "{http://www.w3.org/2000/svg}svg")
                mobile = output / "assets" / "diagrams" / f"{slug}-mobile-glass.svg"
                self.assertTrue(mobile.is_file(), slug)
                self.assertEqual(ET.parse(mobile).getroot().tag, "{http://www.w3.org/2000/svg}svg")
            plain = (output / "terms" / "anova.html").read_text(encoding="utf-8")
            self.assertNotIn('class="term-visual"', plain)
            self.assertEqual(len(list((output / "assets" / "diagrams").glob("*.svg"))), 6)

    def test_diagram_samples_explain_limits_without_color_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            build_site("public", output)
            cleaning = (output / "terms" / "data-cleaning.html").read_text(encoding="utf-8")
            p_value = (output / "terms" / "p-value.html").read_text(encoding="utf-8")
            correlation = (output / "terms" / "correlation-coefficient.html").read_text(encoding="utf-8")
            self.assertIn("异常值不应自动删除", cleaning)
            self.assertIn("双侧、对称", p_value)
            self.assertIn("不是零假设为真的概率", p_value)
            self.assertIn("不证明压力导致幸福感变化", correlation)


if __name__ == "__main__":
    unittest.main()
