import json
from html.parser import HTMLParser
from pathlib import Path
import unittest

from sitegen.render import _linked_text, _reading_text, render_term

ROOT = Path(__file__).resolve().parents[2]


class Links(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.links = []
        self.active = None
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.active = [dict(attrs).get('href'), '']

    def handle_data(self, value):
        if self.active is not None:
            self.active[1] += value

    def handle_endtag(self, tag):
        if tag == 'a' and self.active is not None:
            self.links.append(tuple(self.active))
            self.active = None


class TermLinkResolutionTests(unittest.TestCase):
    names = {'latent-variable': ['潜变量'], 'variable': ['变量'],
             'factor-loading': ['因素载荷', '因子载荷', '载荷']}

    def test_self_term_is_consumed_before_shorter_term_matching(self):
        result = _linked_text('潜变量与变量，载荷。', 'latent-variable', self.names)
        self.assertEqual(Links(result).links,
                         [('variable.html', '变量'), ('factor-loading.html', '载荷')])

    def test_other_full_term_is_linked_as_a_whole(self):
        result = _linked_text('潜变量与因子载荷。', 'variable', self.names)
        self.assertEqual(Links(result).links,
                         [('latent-variable.html', '潜变量'), ('factor-loading.html', '因子载荷')])

    def test_self_alias_is_not_linked_or_split(self):
        result = _linked_text('因素载荷、因子载荷、载荷。', 'factor-loading', self.names)
        self.assertEqual(Links(result).links, [])

    def test_emphasis_cannot_split_self_term_into_a_link(self):
        result = _reading_text('潜变量与变量。', 'latent-variable', self.names, ['潜'])
        self.assertEqual(Links(result).links, [('variable.html', '变量')])
        self.assertIn('<strong class="key-point">潜变量</strong>', result)

    def test_emphasis_cannot_split_another_complete_term(self):
        result = _reading_text('潜变量与变量。', 'other', self.names, ['变量'])
        self.assertEqual(Links(result).links,
                         [('latent-variable.html', '潜变量'), ('variable.html', '变量')])

    def test_english_alias_has_word_boundaries(self):
        result = _linked_text('SEM 与 SEMantic，以及 EFA / CFA。', '',
                              {'sem': ['结构方程模型', 'SEM'],
                               'efa': ['探索性因素分析', 'EFA'],
                               'cfa': ['验证性因素分析', 'CFA']})
        self.assertEqual(Links(result).links,
                         [('sem.html', 'SEM'), ('efa.html', 'EFA'), ('cfa.html', 'CFA')])

    def test_plain_html_is_escaped_and_local_concept_anchor_survives(self):
        result = _linked_text('<潜变量>及共同度', 'latent-variable',
                              {**self.names, 'efa#communality': ['共同度']})
        self.assertIn('&lt;潜变量&gt;', result)
        self.assertEqual(Links(result).links, [('efa.html#communality', '共同度')])

    def test_real_latent_page_links_loading_without_splitting_its_title(self):
        drafts = [json.loads(p.read_text(encoding='utf-8'))
                  for p in (ROOT/'site/content/drafts').glob('*.json')]
        terms = {t['id']: t for t in drafts}
        html = render_term(terms['latent-variable'], preview=True,
                           available_names={k: t['zh'] for k, t in terms.items()},
                           available_aliases={k: t.get('aliases', []) for k, t in terms.items()})
        self.assertIn(('factor-loading.html', '载荷'), Links(html).links)
        self.assertNotIn('潜<a ', html)

    def test_factor_loading_aliases_are_searchable_metadata(self):
        term = json.loads((ROOT/'site/content/drafts/factor-loading.json').read_text(encoding='utf-8'))
        self.assertTrue({'因子载荷', '载荷'} <= set(term['aliases']))

    def test_all_page_names_and_aliases_remain_whole_when_emphasized(self):
        terms = [json.loads(p.read_text(encoding='utf-8'))
                 for p in (ROOT/'site/content/drafts').glob('*.json')]
        names = {t['id']: [t['zh'], *t.get('aliases', [])] for t in terms}
        for term in terms:
            for label in names[term['id']]:
                with self.subTest(term=term['id'], label=label):
                    result = _reading_text(label, term['id'], names, [label[-1:]])
                    self.assertEqual(Links(result).links, [])

    def test_canonical_term_wins_over_identical_embedded_concept(self):
        result = _linked_text('潜变量', 'other',
                              {'latent-variable': ['潜变量'], 'cfa#latent': ['潜变量']})
        self.assertEqual(Links(result).links, [('latent-variable.html', '潜变量')])


if __name__ == '__main__':
    unittest.main()
