#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build a separate editor-time index from the basic textbook text layer."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pickle
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
try:
    from .paths import basic_pdf
except ImportError:
    from paths import basic_pdf


HERE = Path(__file__).resolve().parent
DEFAULT_PDF = basic_pdf()
DEFAULT_OUT = HERE / "rag_data" / "index_basic.pkl"
CHAPTER_RE = re.compile(r"^(第[一二三四五六七八九十百]+章)\s*(.{0,24})$")
SECTION_RE = re.compile(r"^(第[一二三四五六七八九十百]+节)\s*(.{0,24})$")


@dataclass(frozen=True, slots=True)
class PdfInspection:
    page_count: int
    nonempty_pages: int
    character_count: int
    src_sha256: str
    extraction_method: str = "text-layer"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _worker_extract(pdf_path: Path, output_path: Path) -> None:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    output_path.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")


def _extractor_python() -> Path:
    candidates = []
    configured = os.environ.get("PDF_TEXT_PYTHON")
    if configured:
        candidates.append(Path(configured))
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        candidates.append(
            Path(user_profile)
            / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "pypdf is unavailable; set PDF_TEXT_PYTHON to a Python executable containing pypdf"
    )


def extract_pages(pdf_path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        with tempfile.TemporaryDirectory(prefix="basic-pdf-text-") as temporary:
            output = Path(temporary) / "pages.json"
            completed = subprocess.run(
                [str(_extractor_python()), str(Path(__file__).resolve()), "--extract-worker", str(pdf_path), str(output)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            if completed.returncode:
                raise RuntimeError(f"text-layer extraction failed: {completed.stderr.strip()}")
            return json.loads(output.read_text(encoding="utf-8"))
    return [(page.extract_text() or "") for page in PdfReader(str(pdf_path)).pages]


def inspect_pdf(pdf_path: Path) -> PdfInspection:
    pages = extract_pages(pdf_path)
    return PdfInspection(
        page_count=len(pages),
        nonempty_pages=sum(bool(page.strip()) for page in pages),
        character_count=sum(len(page) for page in pages),
        src_sha256=_sha256(pdf_path),
    )


def _printed_page(page_pdf: int, text: str) -> int | None:
    for line in text.splitlines()[:8]:
        if re.fullmatch(r"\s*\d{1,3}\s*", line):
            value = int(line.strip())
            if 0 < page_pdf - value < 30:
                return value
    return None


def make_chunks(
    pages: list[str], *, src_sha256: str, target: int = 650, maxlen: int = 950
) -> list[dict]:
    chunks = []
    chapter = "前置页"
    section = ""
    for page_pdf, raw in enumerate(pages, 1):
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        cleaned = []
        for line in lines:
            chapter_match = CHAPTER_RE.match(line)
            section_match = SECTION_RE.match(line)
            if chapter_match and len(line) <= 32:
                chapter = (chapter_match.group(1) + " " + chapter_match.group(2)).strip()
                section = ""
            elif section_match and len(line) <= 32:
                section = (section_match.group(1) + " " + section_match.group(2)).strip()
            if re.fullmatch(r"\d{1,3}", line):
                continue
            cleaned.append(line)

        buffer = []
        length = 0
        page_parts = []
        for line in cleaned:
            buffer.append(line)
            length += len(line)
            if length >= target:
                page_parts.append("\n".join(buffer))
                buffer, length = [], 0
        if buffer:
            page_parts.append("\n".join(buffer))

        for text in page_parts:
            if len(text) > maxlen:
                pieces = [text[start : start + maxlen] for start in range(0, len(text), maxlen)]
            else:
                pieces = [text]
            for piece in pieces:
                if not piece.strip():
                    continue
                chunks.append(
                    {
                        "chunk_id": len(chunks),
                        "source": "basic",
                        "chapter": chapter,
                        "section": section,
                        "path": " > ".join(item for item in (chapter, section) if item),
                        "page_pdf": page_pdf,
                        "page_print": _printed_page(page_pdf, raw),
                        "src_sha256": src_sha256,
                        "block_type": "prose",
                        "text": piece.strip(),
                    }
                )
    return chunks


def build_index(pdf_path: Path = DEFAULT_PDF, output_path: Path = DEFAULT_OUT) -> dict:
    pages = extract_pages(pdf_path)
    source_hash = _sha256(pdf_path)
    chunks = make_chunks(pages, src_sha256=source_hash)
    sys.path.insert(0, str(HERE))
    from rag_core import EMBED_MODEL, embed_texts

    embeddings = embed_texts([chunk["text"] for chunk in chunks])
    payload = {
        "version": "basic-1.0",
        "source": "basic",
        "embed_model": EMBED_MODEL,
        "src": str(pdf_path.resolve()),
        "src_sha256": source_hash,
        "page_count": len(pages),
        "nonempty_pages": sum(bool(page.strip()) for page in pages),
        "extraction_method": "text-layer",
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "chunks": chunks,
        "embeddings": embeddings,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        pickle.dump(payload, handle)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--extract-worker", nargs=2, metavar=("PDF", "OUTPUT"))
    args = parser.parse_args(argv)
    if args.extract_worker:
        _worker_extract(Path(args.extract_worker[0]), Path(args.extract_worker[1]))
        return 0
    if args.inspect:
        print(json.dumps(asdict(inspect_pdf(args.pdf)), ensure_ascii=False, indent=2))
        return 0
    payload = build_index(args.pdf, args.out)
    print(f"basic index: pages={payload['page_count']} chunks={len(payload['chunks'])} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
