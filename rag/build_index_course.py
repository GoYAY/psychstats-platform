#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build_index_course.py —— 课程讲义索引（不修改既有 index.pkl 与 rag_core.py）。

输入：data/course/<slug>.txt（由 tools/ingest_course_pdfs.py 采集）
      site/content/course_manifest.json
输出：rag/rag_data/index_course.pkl

与教材索引的差异（chunk 元数据）：
  source      = "course"（固定）
  doc         = 讲义 slug
  page_course = 讲义页号
  block_source= TEXT_LAYER | IMAGE_OCR | TABLE_CANDIDATE
  xref        = 图片 xref（IMAGE_OCR 时）
  numeric_risk= 该块包含的数值高风险行数（用于人工核对队列）

切块策略：页内 + 段内（不跨页、不跨来源块），滑动窗口 target/maxlen/overlap 与教材一致。
"""
import os
import re
import json
import pickle
import hashlib
import argparse
import datetime

import numpy as np

from rag_core import EMBED_MODEL, embed_texts

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC_DIR = os.path.join(ROOT, "data", "course")
MANIFEST = os.path.join(ROOT, "site", "content", "course_manifest.json")
OUT = os.path.join(HERE, "rag_data", "index_course.pkl")

CHUNK_VER = "course-1.0"
PAGE_RE = re.compile(r"^=== 讲义页 (\d+) ===$")
SEC_RE = re.compile(r"^--- (.+?) ---$")
NUM_RE = re.compile(r"\d+\.\d+|\d+%|=\s*[-+]?\d|<\s*\.\d+|>\s*\.\d+")


def parse_course_txt(path):
    """→ [(page_no, block_source, xref, table_candidate, text_lines)]"""
    blocks, page, cur = [], None, None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            m = PAGE_RE.match(line.strip())
            if m:
                if cur:
                    blocks.append(cur)
                page, cur = int(m.group(1)), None
                continue
            s = SEC_RE.match(line.strip())
            if s and page is not None:
                if cur:
                    blocks.append(cur)
                tag = s.group(1)
                src = "TEXT_LAYER" if tag.startswith("TEXT_LAYER") else (
                    "TABLE_CANDIDATE" if "TABLE_CANDIDATE" in tag else "IMAGE_OCR")
                xr = re.search(r"xref=(\d+)", tag)
                cur = {"page": page, "source": src,
                       "xref": int(xr.group(1)) if xr else None, "lines": []}
                continue
            if cur is not None:
                s = line.strip()
                # 排除采集器自注入的标注行，避免污染检索（如「```` 表格候选…」围栏）
                if s.startswith("````") or s.startswith("表格候选（几何重建"):
                    continue
                cur["lines"].append(line)
    if cur:
        blocks.append(cur)
    return blocks


def page_chunks(lines, target, maxlen, overlap):
    """段内滑动窗口切块（与教材侧同参数思路）。"""
    buf, n, out = [], 0, []

    def flush():
        nonlocal buf, n
        if buf:
            t = "\n".join(buf).strip()
            if t:
                out.append(t)
        buf, n = [], 0

    for ln in lines:
        if not ln.strip():
            continue
        buf.append(ln)
        n += len(ln)
        if n >= maxlen:
            flush()
    flush()
    if overlap > 0 and len(out) > 1:
        out = [(out[i - 1][-overlap:] + x if i > 0 else x) for i, x in enumerate(out)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=600)
    ap.add_argument("--maxlen", type=int, default=900)
    ap.add_argument("--overlap", type=int, default=100)
    args = ap.parse_args()

    if not os.path.exists(MANIFEST):
        raise SystemExit("缺少 manifest，请先运行 tools/ingest_course_pdfs.py")
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    man_sha = hashlib.sha256(open(MANIFEST, "rb").read()).hexdigest()

    chunks, offset = [], 0
    for entry in manifest["files"]:
        slug = entry["slug"]
        path = os.path.join(SRC_DIR, slug + ".txt")
        if not os.path.exists(path):
            print("  ! 缺少 %s，跳过" % path)
            continue
        blocks = parse_course_txt(path)
        n_before = len(chunks)
        for b in blocks:
            marker = ("[讲义 %s 第%d页]" % (slug, b["page"]))
            for text in page_chunks(b["lines"], args.target, args.maxlen, args.overlap):
                if len(text) < 20:
                    continue
                chunks.append({
                    "text": marker + "\n" + text,
                    "source": "course",
                    "doc": slug,
                    "page_course": b["page"],
                    "block_source": b["source"],
                    "xref": b["xref"],
                    "numeric_risk": len(NUM_RE.findall(text)),
                    "offset": offset,
                    "chunk_id": len(chunks),
                })
                offset += len(text)
        print("  %-16s blocks=%-4d chunks=+%d" % (slug, len(blocks), len(chunks) - n_before))

    print("[向量化] %d chunks ..." % len(chunks))
    vecs = embed_texts([c["text"] for c in chunks])
    data = {
        "version": CHUNK_VER,
        "embed_model": EMBED_MODEL,
        "source": "course",
        "manifest_sha256": man_sha,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "params": {"target": args.target, "maxlen": args.maxlen, "overlap": args.overlap},
        "chunks": chunks,
        "embeddings": vecs,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as f:
        pickle.dump(data, f)
    print("索引已保存：%s  blocks=%d dim=%d size=%.2fMB"
          % (OUT, len(chunks), vecs.shape[1], os.path.getsize(OUT) / 1048576))


if __name__ == "__main__":
    main()
