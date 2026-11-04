import unittest
import re
from pathlib import Path

from sitegen.render import render_index, render_term


ROOT = Path(__file__).resolve().parents[2]


def relations():
    return {
        "prerequisites": ["variable"],
        "components": ["standard-error"],
        "contrasts": ["median"],
        "used_in": ["anova"],
        "next": ["multiple-regression"],
    }


def sample_term():
    return {
        "id": "mean",
        "zh": "平均数",
        "en": "Mean",
        "aliases": ["算术平均数"],
        "type": "method",
        "level": "basic",
        "topic": "foundations",
        "status": "public",
        "summary": "概括连续变量的中心位置。",
        "relations": relations(),
        "real_question": "怎样用一个数概括典型水平？",
        "operational_definition": "总和除以有效观测数。",
        "plain_explanation": "把总量平均分给每个观测。",
        "problems_solved": ["概括中心位置"],
        "not_for": ["严重偏态时不能单独使用"],
        "decision_clues": ["连续变量"],
        "sections": [{"heading": "怎样解释", "body": "结合分布形状解释。"}],
        "formula": {"latex": "\\bar{x}=\\sum x_i/n", "note": "样本平均数", "verified": True},
        "quiz": {
            "question": "哪项正确？",
            "options": ["使用全部观测", "不受极端值影响"],
            "answer": 0,
            "explanation": "平均数使用全部有效观测。",
        },
        "sources": [{"kind": "textbook", "title": "统计教材", "page_pdf": 10}],
        "r_practice": {
            "verified": True,
            "example_code": "mean(c(1, 2, 3))",
            "your_data_code": "mean(your_data$score, na.rm = TRUE)",
        },
        "verified": True,
    }


class RenderedPageTests(unittest.TestCase):
    def test_home_has_topic_scoped_filters_but_not_real_question(self):
        item = sample_term()
        html = render_index([item], preview=False)
        self.assertNotIn(item["real_question"], html)
        for control in ("level-filter", "type-filter", "r-filter"):
            self.assertIn(f'id="{control}"', html)
        self.assertIn('data-type="method"', html)
        self.assertIn('data-level="basic"', html)
        self.assertIn("含 R 实操", html)
        self.assertIn("方法", html)
        self.assertIn("基础", html)
        self.assertNotIn('>method</span>', html)
        self.assertNotIn('>basic</span>', html)

    def test_home_uses_fixed_accent_and_keeps_native_filter_fallback(self):
        html = render_index([sample_term()], preview=False)
        self.assertNotIn('data-theme-choice=', html)
        self.assertIn('<select id="level-filter"', html)
        self.assertIn('src="assets/theme.js"', html)

    def test_detail_exposes_topic_for_color_coding(self):
        html = render_term(sample_term(), preview=False)
        self.assertIn('class="term-content" data-topic="foundations"', html)

    def test_global_navigation_has_no_ai_entry(self):
        html = render_index([sample_term()], preview=False)
        for label in ("术语", "学习路径", "练习", "示例数据", "来源说明"):
            self.assertIn(label, html)
        self.assertNotIn("AI 问答", html)
        self.assertIn('placeholder="搜索全站术语"', html)

    def test_term_has_real_question_relations_and_stable_internal_links(self):
        item = sample_term()
        html = render_term(item, preview=False)
        self.assertIn(item["real_question"], html)
        for relation in relations():
            self.assertIn(f'data-relation="{relation}"', html)
        self.assertIn('href="variable.html"', html)
        self.assertIn("你可能会问", html)

    def test_research_need_is_first_section_before_learning_content(self):
        item = sample_term()
        item["plain_example"] = "例如，汇总一个班级的考试焦虑分数。"
        html = render_term(item, preview=False)
        article = html.split('<article class="term-content"', 1)[1].split('</article>', 1)[0]
        self.assertTrue(article.split('<section', 1)[1].startswith(' class="real-question"'))
        self.assertLess(article.index(item["real_question"]), article.index("操作性定义"))
        self.assertIn(item["plain_example"], article)
        from html import unescape
        import re
        readable = unescape(re.sub(r'<[^>]+>', '', article))
        self.assertLess(readable.index(item["plain_explanation"]), readable.index(item["plain_example"]))
        self.assertLess(article.index(item["plain_example"]), article.index("详细讲解"))

    def test_detailed_explanation_groups_tailored_headings_and_links(self):
        item = sample_term()
        item["sections"] = [{"heading": "怎么看：别只看一个平均数", "body": "结合描述统计查看数据。"}]
        html = render_term(item, preview=False, available_names={"descriptive-statistics": "描述统计"})
        self.assertIn('<h2>详细讲解</h2>', html)
        self.assertIn('<h3>怎么看：别只看一个平均数</h3>', html)
        self.assertIn('<a href="descriptive-statistics.html" class="term-inline-link">描述统计</a>', html)

    def test_question_has_scenario_heading_and_four_option_explanations(self):
        item = sample_term()
        item["quiz"]["options"] = ["甲", "乙", "丙", "丁"]
        item["quiz"]["option_explanations"] = ["甲正确，因为…", "乙错误，因为…", "丙错误，因为…", "丁错误，因为…"]
        html = render_term(item, preview=False)
        self.assertIn("你可能会问", html)
        self.assertNotIn("<h2>真实问题</h2>", html)
        self.assertEqual(html.count('class="option-feedback"'), 4)
        self.assertIn("乙错误，因为…", html)

    def test_related_term_mentions_link_to_named_public_pages(self):
        item = sample_term()
        item["plain_explanation"] = "先做数据清理，再查看 <原始值>。"
        item["relations"]["prerequisites"] = ["data-cleaning"]
        html = render_term(
            item,
            preview=False,
            available_ids={"mean", "data-cleaning"},
            available_names={"data-cleaning": "数据清理"},
        )
        self.assertIn('<a href="data-cleaning.html" class="term-inline-link">数据清理</a>', html)
        self.assertIn("&lt;原始值&gt;", html)

    def test_detail_hides_empty_relation_groups(self):
        item = sample_term()
        item["relations"] = {"prerequisites": ["variable"], "components": [], "contrasts": [], "used_in": [], "next": []}
        html = render_term(item, preview=False, available_ids={"mean", "variable"}, available_names={"variable": "变量"})
        self.assertIn('data-relation="prerequisites"', html)
        self.assertNotIn('data-relation="components"', html)
        self.assertNotIn('data-relation="contrasts"', html)

    def test_detail_hides_sidebar_when_no_published_relation_exists(self):
        item = sample_term()
        item["relations"] = {"prerequisites": [], "components": [], "contrasts": [], "used_in": [], "next": ["draft-only"]}
        html = render_term(item, preview=False, available_ids={"mean"})
        self.assertNotIn('class="knowledge-sidebar"', html)
        self.assertIn('class="term-layout term-layout--single"', html)

    def test_r_practice_has_two_tabs_copy_controls_and_escaped_code(self):
        html = render_term(sample_term(), preview=False)
        self.assertIn('data-tab="example"', html)
        self.assertIn('data-tab="your-data"', html)
        self.assertGreaterEqual(html.count("data-copy="), 2)
        self.assertIn("your_data$score", html)

    def test_r_practice_links_its_teaching_data_and_explains_checks(self):
        item = sample_term()
        item["r_practice"]["example_code"] = 'd <- read.csv("learning_experiment.csv")'
        item["r_practice"]["assumption_checks"] = ["检查独立性"]
        item["r_practice"]["interpretation"] = "结合区间解释差异"
        html = render_term(item, preview=False)
        self.assertIn('href="../data/learning_experiment.csv"', html)
        self.assertIn("检查独立性", html)
        self.assertIn("结合区间解释差异", html)

    def test_first_quiz_option_remains_a_valid_answer(self):
        html = render_term(sample_term(), preview=False)
        self.assertIn('data-answer="0"', html)

    def test_css_defines_sidebar_layout_mobile_order_and_scrollable_code(self):
        css = (ROOT / "site" / "assets" / "site.css").read_text(encoding="utf-8")
        self.assertIn(".term-layout", css)
        self.assertIn(".knowledge-sidebar", css)
        self.assertIn("position: sticky", css)
        self.assertIn("@media (max-width: 800px)", css)
        self.assertIn("overflow-x: auto", css)

    def test_visual_system_is_self_contained_and_flat_for_regular_content(self):
        css = (ROOT / "site" / "assets" / "site.css").read_text(encoding="utf-8")
        self.assertNotIn("@import", css)
        self.assertIn("--color-link", css)
        self.assertIn("--color-success", css)
        self.assertIn("--color-danger", css)
        card_rule = re.search(r"\.term-card\s*\{([^}]*)\}", css)
        self.assertIsNotNone(card_rule)
        self.assertNotIn("box-shadow:", card_rule.group(1))

    def test_white_theme_uses_colored_term_accents_and_hover_elevation(self):
        css = (ROOT / "site" / "assets" / "site.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"--color-page:\s*#fff(?:fff)?;")
        self.assertIn("[data-topic=foundations]", css)
        self.assertIn(".term-card:hover", css)
        self.assertIn("box-shadow", css.split(".term-card:hover", 1)[1].split("}", 1)[0])
        self.assertNotIn(".term-card a:hover h2", css)
        self.assertIn(".cursor-dot", css)

    def test_cursor_color_is_fixed_black_ring_with_transparent_center(self):
        css = (ROOT / "site" / "assets" / "site.css").read_text(encoding="utf-8")
        dot = re.search(r"\.cursor-dot\s*\{([^}]*)\}", css)
        self.assertIsNotNone(dot)
        self.assertRegex(dot.group(1), r"background:\s*transparent;")
        self.assertRegex(dot.group(1), r"width:\s*15px;")
        self.assertRegex(dot.group(1), r"height:\s*15px;")
        ring = re.search(r"\.cursor-dot::before\s*\{([^}]*)\}", css)
        self.assertIsNotNone(ring)
        self.assertRegex(ring.group(1), r"border:\s*2px solid #000;")
        self.assertRegex(ring.group(1), r"background:\s*transparent;")
        self.assertNotIn("var(--theme-color)", ring.group(1))
        self.assertNotIn("var(--theme-color)", dot.group(1))


if __name__ == "__main__":
    unittest.main()
