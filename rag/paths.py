"""Project-relative defaults and explicit, portable external input paths."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def input_path(variable, default):
    configured = os.environ.get(variable, '').strip()
    value = Path(os.path.expandvars(configured)).expanduser() if configured else Path(default)
    return value if value.is_absolute() else ROOT / value


def ocr_text():
    return input_path('PSY_STATS_OCR_TEXT', 'data/高级心理统计.txt')


def rag_index():
    return input_path('PSY_STATS_RAG_INDEX', 'rag/rag_data/index.pkl')


def basic_pdf():
    return input_path('PSY_STATS_BASIC_PDF', 'data/basic-textbook.pdf')


def advanced_pdf():
    return input_path('PSY_STATS_ADVANCED_PDF', 'data/高级心理统计.pdf')
