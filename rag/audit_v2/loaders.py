# -*- coding: utf-8 -*-
"""audit_v2.loaders —— 只读加载 PDF / OCR TXT / index.pkl，并计算指纹。

明确禁止：本模块不写入任何被加载的文件。
"""
import os
import hashlib
import pickle
import json
try:
    from ..paths import advanced_pdf, ocr_text, rag_index
except ImportError:
    from paths import advanced_pdf, ocr_text, rag_index

HERE = os.path.dirname(os.path.abspath(__file__))
RAG_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(RAG_DIR)

DEFAULT_SRC = str(ocr_text())
DEFAULT_INDEX = str(rag_index())
DEFAULT_PDF = str(advanced_pdf())
OUT_DIR = os.path.join(RAG_DIR, "audit_v2_out")


def sha256_file(path, chunk=1 << 20):
    if not path or not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_index(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def load_all(src=DEFAULT_SRC, index_path=DEFAULT_INDEX, pdf=DEFAULT_PDF):
    txt = read_text(src)
    d = load_index(index_path)
    meta = {
        "src": os.path.abspath(src),
        "src_sha256": sha256_file(src),
        "index_path": os.path.abspath(index_path),
        "index_sha256": sha256_file(index_path),
        "pdf_path": pdf if os.path.exists(pdf) else None,
        "pdf_sha256": sha256_file(pdf),
        "pdf_bytes": os.path.getsize(pdf) if os.path.exists(pdf) else None,
    }
    return txt, d, meta


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
