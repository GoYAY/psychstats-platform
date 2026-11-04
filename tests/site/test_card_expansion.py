import unittest
from html.parser import HTMLParser

from sitegen.render import page_shell, render_practice_reading, render_term
from tests.site.test_build import term


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class CardExpansionRenderingTests(unittest.TestCase):
    def test_topic_return_targets_the_current_term_in_its_own_topic(self):
        html = render_term(term('example', topic='regression'), preview=True, topic_label='回归分析')
        links = [attrs for tag, attrs in Elements(html).elements if tag == 'a']
        self.assertTrue(any(attrs.get('href') == '../index.html?topic=regression'
                            and attrs.get('data-collapse-term') == 'example' for attrs in links))

    def test_page_identity_assets_resolve_from_top_level_and_term_pages(self):
        for root in ('', '../'):
            html = page_shell('测试页', '<p>正文</p>', root=root)
            elements = Elements(html).elements
            self.assertIn('<title>心理统计学术语图鉴-轻松掌握心理统计和r语言数据分析</title>', html)
            icons = [attrs for tag, attrs in elements if tag == 'link' and attrs.get('rel') == 'icon']
            self.assertTrue(any(attrs['href'] == root + 'assets/favicon.svg' for attrs in icons))
            self.assertTrue(any(tag == 'img' and attrs.get('src') == root + 'assets/favicon.svg'
                                and attrs.get('width') == '28' for tag, attrs in elements))
            self.assertTrue(any(tag == 'script' and attrs.get('src') == root + 'assets/card-transition.js'
                                for tag, attrs in elements))

    def test_practice_reading_has_header_entry_and_keeps_inline_concept_links(self):
        html = render_practice_reading({'id': 'sample', 'zh': '样本', 'en': 'Sample',
                                       'plain_explanation': '可以先了解总体。', 'sections': []},
                                      {'population': ['总体']})
        links = [attrs for tag, attrs in Elements(html).elements if tag == 'a']
        self.assertTrue(any(attrs.get('data-expand-card') == 'practice'
                            and attrs.get('href') == 'terms/sample.html' for attrs in links))
        self.assertTrue(any(attrs.get('href') == 'terms/population.html' for attrs in links))
        self.assertNotIn('practice-full-link', html)
        self.assertIn('展开完整讲解', html)


if __name__ == '__main__':
    unittest.main()
