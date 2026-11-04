from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
class ReaderCompatibility(unittest.TestCase):
    def test_shared_mounts_keep_static_initialization_and_disposal(self):
        for file,name in [('reader.js','mountPersonalQuiz'),('glossary.js','mountPersonalGlossary')]:
            code=(ROOT/'term_explainer/assets'/file).read_text(encoding='utf-8')
            self.assertIn(name,code)
            self.assertIn('DOMContentLoaded',code)
            self.assertIn('AbortController',code)
            self.assertIn('dispose',code)
