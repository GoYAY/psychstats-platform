import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag import paths


class PortablePathsTests(unittest.TestCase):
    def test_defaults_resolve_from_project_when_working_directory_changes(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            try:
                os.chdir(folder)
                self.assertEqual(paths.ocr_text(), paths.ROOT / 'data' / '高级心理统计.txt')
                self.assertEqual(paths.rag_index(), paths.ROOT / 'rag' / 'rag_data' / 'index.pkl')
                self.assertEqual(paths.basic_pdf(), paths.ROOT / 'data' / 'basic-textbook.pdf')
                self.assertEqual(paths.advanced_pdf(), paths.ROOT / 'data' / '高级心理统计.pdf')
            finally:
                os.chdir(previous)

    def test_relative_configuration_resolves_against_project_root(self):
        with patch.dict(os.environ, {'PSY_STATS_OCR_TEXT': 'materials/custom.txt'}):
            self.assertEqual(paths.ocr_text(), paths.ROOT / 'materials' / 'custom.txt')

    def test_absolute_external_input_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'user-supplied.pdf'
            with patch.dict(os.environ, {'PSY_STATS_BASIC_PDF': str(file)}):
                self.assertEqual(paths.basic_pdf(), file)

    def test_empty_configuration_uses_documented_default(self):
        with patch.dict(os.environ, {'PSY_STATS_RAG_INDEX': '   '}):
            self.assertEqual(paths.rag_index(), paths.ROOT / 'rag' / 'rag_data' / 'index.pkl')

    def test_paper_can_be_configured_without_moving_it(self):
        with patch.dict(os.environ, {'PSY_STATS_DRIFT_PDF': 'data/custom-paper.pdf'}):
            self.assertEqual(paths.input_path('PSY_STATS_DRIFT_PDF', 'data/papers/drift.pdf'), paths.ROOT / 'data/custom-paper.pdf')
