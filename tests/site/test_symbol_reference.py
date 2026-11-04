import importlib
import json
import unittest
import subprocess
from pathlib import Path

from sitegen import render


ROOT = Path(__file__).resolve().parents[2]


class SymbolReferenceTests(unittest.TestCase):
    def test_search_preserves_single_letter_case_and_accepts_greek_aliases(self):
        asset = ROOT / 'site/assets/symbols.js'
        self.assertTrue(asset.is_file(), 'Lookup needs local search behavior')
        script = """
const assert = require('node:assert/strict');
const {matches} = require(process.argv[1]);
const row = {tokens:['N','total sample size'],search:'N 总样本量',kind:'statistic'};
assert.equal(matches(row,'N',''),true);
assert.equal(matches(row,'n',''),false);
assert.equal(matches(row,'总样本',''),true);
assert.equal(matches(row,'','output'),false);
assert.equal(matches({tokens:['α','alpha'],search:'α 显著性水平',kind:'statistic'},'ALPHA',''),true);
assert.equal(matches({tokens:['Pr(>|t|)'],search:'Pr(>|t|) p 值',kind:'output'},'Pr(>|t|)',''),true);
"""
        result = subprocess.run(['node', '-e', script, str(asset)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def module(self):
        self.assertTrue((ROOT / 'site/sitegen/symbol_reference.py').is_file(),
                        'Symbols need a shared curated renderer')
        return importlib.import_module('sitegen.symbol_reference')

    def test_statistical_letters_are_italic_but_greek_and_acronyms_are_not(self):
        module = self.module()
        self.assertIn('<i', module.symbol_html({'symbol': 'df', 'italic': True}))
        self.assertNotIn('<i', module.symbol_html({'symbol': 'α', 'italic': False}))
        self.assertNotIn('<i', module.symbol_html({'symbol': 'CI', 'italic': False}))
        self.assertIn('<sup>2</sup>', module.symbol_html({'symbol': 'R', 'italic': True, 'sup': '2'}))
        self.assertIn('&lt;', module.symbol_html({'symbol': '<script>', 'italic': False}))

    def test_aliases_do_not_merge_alpha_meanings(self):
        module = self.module()
        entries = module.load_reference(ROOT / 'site/content/symbol_reference.json')
        alpha = [e for e in entries if e['symbol'] == 'α']
        self.assertEqual({e['id'] for e in alpha}, {'significance-alpha', 'cronbach-alpha'})
        self.assertTrue(all(e['context'] and e['note'] for e in entries))
        registry = json.loads((ROOT / 'site/content/registry.json').read_text(encoding='utf-8'))
        ids = {t['id'] for t in registry['terms']}
        for entry in entries:
            self.assertTrue(set(entry['terms']) <= ids, entry['id'])
            self.assertTrue(set(entry.get('card_terms', [])) <= set(entry['terms']), entry['id'])

    def test_lookup_page_links_only_to_available_terms(self):
        module = self.module()
        entries = [{'id': 'degrees-of-freedom', 'symbol': 'df', 'italic': True,
                    'label': '自由度', 'context': '检验', 'note': '不同检验有不同计算方式。',
                    'aliases': ['degrees of freedom'], 'kind': 'statistic',
                    'terms': ['degrees-of-freedom', 't-test']}]
        html = module.render_reference(entries, {'degrees-of-freedom': {'zh': '自由度'}})
        self.assertIn('terms/degrees-of-freedom.html', html)
        self.assertNotIn('terms/t-test.html', html)
        self.assertIn('id="symbol-query"', html)
        self.assertIn('id="degrees-of-freedom"', html)
        self.assertIn('aria-current="page">符号速查', html)

    def test_card_symbols_are_independent_links_not_nested_in_expand_link(self):
        term = {'id': 'degrees-of-freedom', 'zh': '自由度', 'en': 'Degrees of Freedom',
                'topic': 'foundations', 'type': 'concept', 'level': 'basic', 'summary': '信息余量。',
                'card_symbols': [{'id': 'degrees-of-freedom', 'symbol': 'df', 'italic': True, 'label': '自由度'}]}
        html = render._term_cards([term], preview=True, topic_names={})
        self.assertIn('symbols.html#degrees-of-freedom', html)
        self.assertLess(html.index('</div></a>'), html.index('class="term-symbol-badge"'))
        self.assertIn('class="term-symbols"', html)


if __name__ == '__main__':
    unittest.main()
