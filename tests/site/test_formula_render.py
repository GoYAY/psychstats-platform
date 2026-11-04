import unittest

from sitegen.math_render import render_formulas


class FormulaRenderTests(unittest.TestCase):
    def test_equation_has_visual_layout_and_accessible_mathml(self):
        rendered = render_formulas({"se": r"SE(\bar{x})=\frac{s}{\sqrt{n}}"})
        self.assertIn('<math', rendered["se"])
        self.assertIn('katex-html', rendered["se"])
        self.assertIn('aria-hidden="true"', rendered["se"])

    def test_invalid_formula_is_rejected_with_its_term_id(self):
        with self.assertRaisesRegex(ValueError, "broken"):
            render_formulas({"broken": r"\frac{"})

