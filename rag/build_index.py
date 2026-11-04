#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_index.py  v2 —— 依据 RAG 审计报告修复后重建索引。

修复清单：
  [CRITICAL] 引用页码：从 OCR 残留（"128/"、"/ 367"）提取【教材印刷页码】page_print，
              与 PDF 页 page_pdf 同时记录，引用改用印刷页码。
  [HIGH]     元数据：用「页眉」构建真实的 page→章/节 映射（替代"最近匹配"启发式），
              补齐 chapter_no/chapter_title/section_no/section_title/path/chunk_id/offset。
  [HIGH]     噪声：剥离页眉、页码残留、书名页脚；按中文占比标记 block_type(prose/noise)。
  [HIGH]     切块：改为「页内切分」，不再跨页、不再跨主题；保留段内重叠。
  [HIGH]     版本：写入 src_sha256 / chunk_ver / embed_model，供启动一致性校验。

用法：
    python build_index.py
    python build_index.py --src "<txt>" --target 600 --overlap 100
"""
import os
import re
import argparse
import pickle
import hashlib
import datetime
import collections

import numpy as np

from rag_core import EMBED_MODEL, embed_texts

HERE = os.path.dirname(os.path.abspath(__file__))
# 默认读取「项目根目录下 data/」的副本。路径按脚本位置相对计算，
# 因此整个文件夹拷到任何位置都能直接跑，无需修改代码。
DEFAULT_SRC = os.path.join(os.path.dirname(HERE), "data", "高级心理统计.txt")
DEFAULT_OUT = os.path.join(HERE, "rag_data", "index.pkl")

PAGE_RE = re.compile(r"=== 第 (\d+) 页 ===")
CHAP_RE = re.compile(r"^(第[一二三四五六七八九十百]+章)(.*)$")
SEC_RE = re.compile(r"^(第[一二三四五六七八九十百]+节)(.*)$")
PAGENUM_RE = re.compile(r"^\s*/?\s*\d{1,3}\s*/?\s*$")
BOOKTITLE = "高级心理统计"
CJK = re.compile(r"[\u4e00-\u9fff]")

CHUNK_VER = "2.0"
NOISE_CJK_RATIO = 0.30  # 中文占比低于此值视为表格/数字噪声


def parse_pages(path):
    pages, cur, buf = [], None, []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = PAGE_RE.match(line.strip())
            if m:
                if cur is not None:
                    pages.append((cur, "\n".join(buf)))
                cur, buf = int(m.group(1)), []
            elif cur is not None:
                buf.append(line.rstrip("\n"))
    if cur is not None:
        pages.append((cur, "\n".join(buf)))
    return pages


def extract_printed_page(body):
    """从单页 OCR 文本里提取教材印刷页码。"""
    for s in (l.strip() for l in body.splitlines()):
        m = re.match(r"^(\d{1,3})\s*/\s*$", s) or re.match(r"^/\s*(\d{1,3})\s*$", s)
        if m:
            return int(m.group(1))
    # 兜底：形如 "第十三章多层线性模型简介 / 367"
    for s in (l.strip() for l in body.splitlines()):
        if "章" in s or "节" in s or BOOKTITLE in s:
            m = re.search(r"/\s*(\d{1,3})\s*$", s)
            if m:
                return int(m.group(1))
    return None


def build_print_map(pages):
    """PDF 页 -> 印刷页。能提取的直接用，缺失的用相邻锚点插值。"""
    raw = {}
    for num, body in pages:
        p = extract_printed_page(body)
        if p is not None and 0 < num - p < 40:
            raw[num] = p
    nums = [n for n, _ in pages]
    out = {}
    last_known = None
    for n in nums:
        if n in raw:
            out[n] = raw[n]
            last_known = (n, raw[n])
        elif last_known:
            out[n] = last_known[1] + (n - last_known[0])
        else:
            out[n] = max(n - 13, 1)
    return out, len(raw)


def clean_lines(body):
    """剥离：页码残留行、书名页脚行、页首的章标题页眉（章信息已进 metadata）。"""
    out, skipping = [], True
    for ln in body.splitlines():
        s = ln.strip()
        if not s:
            continue
        if PAGENUM_RE.match(s):
            continue
        if s == BOOKTITLE:
            continue
        if skipping and CHAP_RE.match(s):
            continue          # 章标题页眉（每页重复）
        skipping = False
        out.append(s)
    return out


def page_chunks(lines, target=600, maxlen=900, overlap=100):
    """页内切块：不跨页；记录块起始处生效的小节。"""
    buf, buf_len, buf_sec, out = [], 0, ("", ""), []
    cur_sec = ("", "")

    def flush():
        nonlocal buf, buf_len, buf_sec
        if buf:
            t = "\n".join(buf).strip()
            if t:
                out.append((t, buf_sec[0], buf_sec[1]))
        buf, buf_len = [], 0

    for ln in lines:
        m = SEC_RE.match(ln)
        if m and len(ln) <= 30:
            cur_sec = (m.group(1).strip(), m.group(2).strip()[:30])
        if not buf:
            buf_sec = cur_sec
        buf.append(ln)
        buf_len += len(ln)
        if buf_len >= maxlen:
            flush()
    flush()

    # 页内相邻块之间补重叠，降低知识点被切断的风险
    if overlap > 0 and len(out) > 1:
        merged = []
        for i, (t, sn, st) in enumerate(out):
            if i > 0:
                t = out[i - 1][0][-overlap:] + t
            merged.append((t, sn, st))
        out = merged
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--target", type=int, default=600)
    ap.add_argument("--maxlen", type=int, default=900)
    ap.add_argument("--overlap", type=int, default=100)
    args = ap.parse_args()

    src_abs = os.path.abspath(args.src)
    with open(src_abs, "rb") as f:
        src_sha = hashlib.sha256(f.read()).hexdigest()

    print(f"[1/5] 解析分页：{args.src}")
    pages = parse_pages(args.src)
    print(f"      共 {len(pages)} 页")

    print("[2/5] 建立 印刷页码 映射 + 章/节 映射 ...")
    print_map, n_extract = build_print_map(pages)
    print(f"      印刷页码：直接提取 {n_extract} 页，其余插值（共 {len(pages)} 页）")

    print("[3/5] 清洗 + 页内切块 ...")
    chunks = []
    chapter_no = chapter_title = ""
    offset = 0
    for num, body in pages:
        raw_first = ""
        for l in body.splitlines():
            if l.strip():
                raw_first = l.strip()
                break
        m = CHAP_RE.match(raw_first)
        if m:                       # 页眉给出本章
            chapter_no = m.group(1).strip()
            chapter_title = m.group(2).strip()[:30]

        lines = clean_lines(body)
        for text, sec_no, sec_title in page_chunks(lines, args.target, args.maxlen, args.overlap):
            cjk = len(CJK.findall(text))
            ratio = cjk / max(len(text), 1)
            # 前附页（目录/前言）与后附页（参考文献/书讯）单独标记，避免挤占 Top-K
            if num < 16:
                btype = "front"
            elif num >= 421:
                btype = "back"
            else:
                btype = "noise" if ratio < NOISE_CJK_RATIO else "prose"
            chunks.append({
                "text": text,
                "page_pdf": num,
                "page_print": print_map.get(num, num),
                "chapter_no": chapter_no,
                "chapter_title": chapter_title,
                "section_no": sec_no,
                "section_title": sec_title,
                "path": " > ".join(x for x in
                                   [f"{chapter_no}{chapter_title}", f"{sec_no}{sec_title}"]
                                   if x.strip()),
                "block_type": btype,
                "cjk_ratio": round(ratio, 3),
                "offset": offset,
            })
            offset += len(text)
    for i, c in enumerate(chunks):
        c["chunk_id"] = i

    types = collections.Counter(c["block_type"] for c in chunks)
    no_chap = sum(1 for c in chunks if not c["chapter_no"])
    print(f"      生成 {len(chunks)} 块  {dict(types)}  无章节 {no_chap} ({no_chap/len(chunks):.1%})")

    print(f"[4/5] 向量化（fastembed {EMBED_MODEL}）...")
    vecs = embed_texts([c["text"] for c in chunks])

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    data = {
        "version": CHUNK_VER,
        "embed_model": EMBED_MODEL,
        "src": src_abs,
        "src_sha256": src_sha,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "params": {"target": args.target, "maxlen": args.maxlen, "overlap": args.overlap},
        "chunks": chunks,
        "embeddings": vecs,
    }
    with open(args.out, "wb") as f:
        pickle.dump(data, f)
    print(f"[5/5] 索引已保存：{args.out}")
    print(f"      块数={len(chunks)} 维度={vecs.shape[1]} "
          f"大小={os.path.getsize(args.out)/1048576:.2f}MB  chunk_ver={CHUNK_VER}")


if __name__ == "__main__":
    main()
