# -*- coding: utf-8 -*-
"""验证：1) 教材印刷页码 vs PDF 页码偏差  2) 章节起始页 vs chunk 的 section 标签是否一致"""
import re
import pickle
import collections
try:
    from .paths import ocr_text, rag_index
except ImportError:
    from paths import ocr_text, rag_index

SRC = ocr_text()
txt = open(SRC, encoding="utf-8").read()
PAGE_RE = re.compile(r"=== 第 (\d+) 页 ===")
idxs = [(m.start(), m.end(), int(m.group(1))) for m in PAGE_RE.finditer(txt)]
pages = {}
for i, (s, e, num) in enumerate(idxs):
    end = idxs[i + 1][0] if i + 1 < len(idxs) else len(txt)
    pages[num] = txt[e:end]

# ---------- 1. 印刷页码 vs PDF 页码 ----------
# OCR 中残留形如 "128/" 或 "/ 367" 的印刷页码
pat = re.compile(r"(?m)^\s*/?\s*(\d{2,3})\s*/\s*$")
diffs = collections.Counter()
samples = []
for num, body in pages.items():
    for line in body.splitlines():
        m = pat.match(line)
        if m:
            printed = int(m.group(1))
            d = num - printed
            if 0 < d < 60:
                diffs[d] += 1
                if len(samples) < 12:
                    samples.append((num, printed, d))
print("=== 印刷页码 vs PDF 页码 ===")
print("样本(PDF页, 印刷页, 差):", samples)
print("最常见差值 top5:", diffs.most_common(5))

# ---------- 2. 章节起始 PDF 页 ----------
chap_titles = ["第一章数据的清理与准备", "第二章多元方差分析", "第三章多元回归分析",
               "第四章Logistic回归分析", "第五章判别分析", "第六章聚类分析",
               "第七章探索性因素分析", "第八章验证性因素分析", "第九章路径分析",
               "第十章结构方程模型", "第十一章中介分析", "第十二章调节效应",
               "第十三章多层线性模型简介", "第十四章多层线性模型在追踪研究中的应用"]
print("\n=== 章节标题首次出现的 PDF 页 ===")
starts = {}
for t in chap_titles:
    pos = txt.find(t)
    if pos == -1:
        print(f"  {t}: 未找到")
        continue
    pg = max([n for n, (s, e, _) in [(n, (a, b, c)) for n, (a, b, c) in
                                     zip([0], [(0, 0, 0)])]] or [0]) if False else None
    # 找该位置属于哪一页
    pg = None
    for i, (s, e, num) in enumerate(idxs):
        end = idxs[i + 1][0] if i + 1 < len(idxs) else len(txt)
        if s <= pos < end:
            pg = num
            break
    starts[t] = pg
    print(f"  {t}: PDF 第 {pg} 页")

# ---------- 3. 抽查：页 48 / 49 的实际章节归属 ----------
print("\n=== 抽查 PDF 页 47-50 首行（判断第二章实际起点） ===")
for n in (47, 48, 49, 50):
    if n in pages:
        ls = [l.strip() for l in pages[n].splitlines() if l.strip()]
        print(f"  p{n}: {ls[:2]}")

# ---------- 4. TOC chunk 内容 ----------
d = pickle.load(open(rag_index(), "rb"))
print("\n=== index chunk#2（疑似目录）page=%s ===" % d["chunks"][2]["page"])
print(d["chunks"][2]["text"][:400])
