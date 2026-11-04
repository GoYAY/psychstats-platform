# -*- coding: utf-8 -*-
"""tools/extract_concepts.py —— 按章拆解教材内容，产出「科普概念清单（候选）」+ 章节结构。

只读教材 OCR TXT 与 index.pkl；不做任何修改，也不宣称 OCR 正确。
抽取三类证据：
  1) 节标题：`第X节 …`（教材真实层级）
  2) 要点条目：章首「核心要点 / 内容要点」编号列表（教材自述本章目标）
  3) 定义候选：含「是指 / 称为 / 叫做 / 定义为 / 指的是 / 即为 / 表示」的句子（**候选，需人工核对**）

产出：
  docs/科普概念清单.md
  site/content/concepts_by_chapter.json
用法：.venv\\Scripts\\python.exe tools\\extract_concepts.py
"""
import os
import re
import sys
import json
import pickle
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "rag"))

TXT = os.path.join(ROOT, "data", "高级心理统计.txt")
INDEX = os.path.join(ROOT, "rag", "rag_data", "index.pkl")
OUT_MD = os.path.join(ROOT, "docs", "科普概念清单.md")
OUT_JSON = os.path.join(ROOT, "site", "content", "concepts_by_chapter.json")

CHAPS = ["第一章", "第二章", "第三章", "第四章", "第五章", "第六章", "第七章",
         "第八章", "第九章", "第十章", "第十一章", "第十二章", "第十三章", "第十四章"]
SEC_RE = re.compile(r"^(第[一二三四五六七八九十]+节)\s*(.{0,28})$")
BULLET_RE = re.compile(r"^\s*(?:\d{1,2}[\.、]|[（(]\d{1,2}[)）])\s*(.{4,60})$")
DEF_PAT = re.compile(r"(是指|称为|叫做|定义为|指的是|即为|是一种|表示)[^。；\n]{0,60}")
KEY_TITLE = re.compile(r"(核心要点|内容要点|本章要点|学习目标)")


def load_pages():
    with open(TXT, encoding="utf-8") as f:
        raw = f.read()
    parts = re.split(r"=== 第 (\d+) 页 ===", raw)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


def chapter_ranges():
    with open(INDEX, "rb") as f:
        chunks = pickle.load(f)["chunks"]
    rng = {}
    for c in chunks:
        ch = c.get("chapter_no") or ""
        if not ch:
            continue
        p = c["page_pdf"]
        lo, hi = rng.get(ch, (p, p))
        rng[ch] = (min(lo, p), max(hi, p))
    return rng


def clean(s):
    return re.sub(r"\s+", "", s).strip()


def main():
    pages = load_pages()
    rng = chapter_ranges()
    out = {}
    for ch in CHAPS:
        lo, hi = rng.get(ch, (None, None))
        if lo is None:
            out[ch] = {"page_pdf_range": None, "sections": [], "bullets": [],
                       "definitions": []}
            continue
        sections, bullets, defs = [], [], []
        in_key = False
        pending_sec = None          # 节标记独占一行时，标题在下一非空行
        skip_next = False
        for p in range(lo, hi + 1):
            body = pages.get(p, "")
            for line in body.splitlines():
                s = clean(line)
                if not s:
                    in_key = False
                    continue
                if pending_sec and not s.startswith(("第", "图", "表")):
                    t = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9（）()、·\-]", "", s)
                    if 2 <= len(t) <= 30:
                        sections.append((p, pending_sec + t))
                    pending_sec = None
                    in_key = False
                    continue
                pending_sec = None
                if KEY_TITLE.search(s):
                    in_key = True
                    continue
                m = SEC_RE.match(s)
                if m and len(s) <= 32:
                    title = clean(m.group(2))
                    if title:
                        key = m.group(1) + title
                        if not sections or sections[-1][1] != key:
                            sections.append((p, key))
                    else:
                        pending_sec = m.group(1)
                    in_key = False
                    continue
                mb = BULLET_RE.match(s)
                if mb and in_key:
                    bullets.append((p, clean(mb.group(1))))
                    continue
                if len(s) >= 8:
                    d = DEF_PAT.search(s)
                    if d:
                        idx = max(0, d.start() - 18)
                        defs.append((p, clean(s[idx:idx + 70])))
        out[ch] = {
            "page_pdf_range": [lo, hi],
            "page_print_range": [max(lo - 13, 1), max(hi - 13, 1)],
            "n_sections": len(sections),
            "sections": [{"page_pdf": p, "title": t} for p, t in sections],
            "bullets": [{"page_pdf": p, "text": t} for p, t in bullets],
            "definitions": [{"page_pdf": p, "text": t, "status": "CANDIDATE"} for p, t in defs],
        }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"source": "教材 OCR 抽取（候选，未人工核对）",
                   "chapters": out}, f, ensure_ascii=False, indent=1)

    L = ["# 科普概念清单（按教材 14 章拆解，候选待核对）\n\n",
         "来源：`data/高级心理统计.txt`（只读）+ `index.pkl` 章节映射。\n\n",
         "> 页码为 **PDF 页**；教材印刷页 ≈ PDF 页 − 13（推断值）。\n",
         "> 「节标题」来自教材真实层级；「要点」来自章首核心要点/内容要点；\n",
         "> 「定义候选」是含「是指/称为/定义为…」的句子片段，**未经人工核对，不能直接引用**。\n\n",
         "| 章 | PDF 页范围 | 印刷页范围 | 节数 | 要点数 | 定义候选数 |\n|---|---|---|---|---|---|\n"]
    for ch in CHAPS:
        d = out[ch]
        if not d["page_pdf_range"]:
            L.append("| %s | — | — | 0 | 0 | 0 |\n" % ch)
            continue
        L.append("| %s | %d–%d | %d–%d | %d | %d | %d |\n"
                 % (ch, d["page_pdf_range"][0], d["page_pdf_range"][1],
                    d["page_print_range"][0], d["page_print_range"][1],
                    d["n_sections"], len(d["bullets"]), len(d["definitions"])))
    L.append("\n")
    for ch in CHAPS:
        d = out[ch]
        L.append("\n## %s（PDF %s；印刷约 %s）\n" % (
            ch, d["page_pdf_range"], d["page_print_range"]))
        L.append("\n**节标题**\n\n")
        if d["sections"]:
            for s in d["sections"]:
                L.append("- p%d %s\n" % (s["page_pdf"], s["title"]))
        else:
            L.append("- （未抽取到，需人工补）\n")
        L.append("\n**本章要点（教材自述）**\n\n")
        if d["bullets"]:
            for b in d["bullets"]:
                L.append("- p%d %s\n" % (b["page_pdf"], b["text"]))
        else:
            L.append("- （未抽取到）\n")
        L.append("\n**定义候选（未核对）**\n\n")
        seen = set()
        for x in d["definitions"]:
            key = x["text"][:24]
            if key in seen:
                continue
            seen.add(key)
            L.append("- p%d %s\n" % (x["page_pdf"], x["text"]))
            if len(seen) >= 25:
                break
    L.append("\n---\n\n**边界**：本清单为机械抽取结果，"
             "含 OCR 噪声（如符号丢失、错字）；术语名与定义必须人工核对教材原页后"
             "再进入站点（见 `tools/promote_term.py` 闸门）。\n")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.writelines(L)
    print("chapters:", len(out), "→", OUT_MD)
    for ch in CHAPS:
        d = out[ch]
        print("  %-6s pages=%-9s sections=%-3d bullets=%-3d defs=%d"
              % (ch, d["page_pdf_range"], d["n_sections"], len(d["bullets"]),
                 len(d["definitions"])))


if __name__ == "__main__":
    main()
