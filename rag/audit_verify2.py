# -*- coding: utf-8 -*-
"""验证 section 标签正确率：用「页眉（每页首行的第X章）+ 向后延续」构建真实的 page→章 映射，
再与 index 里 chunk 的 section 标签比对，得出实际误标率。"""
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
CHAP_RE = re.compile(r"^第[一二三四五六七八九十百]+章")
idxs = [(m.start(), m.end(), int(m.group(1))) for m in PAGE_RE.finditer(txt)]

# 1) 构建 page -> 章（用页眉，向后延续）
page_chap = {}
cur = None
for i, (s, e, num) in enumerate(idxs):
    end = idxs[i + 1][0] if i + 1 < len(idxs) else len(txt)
    body = txt[e:end]
    first = ""
    for line in body.splitlines():
        if line.strip():
            first = line.strip()
            break
    m = CHAP_RE.match(first)
    if m:
        cur = m.group(0)
    page_chap[num] = cur

covered = sum(1 for v in page_chap.values() if v)
print(f"页眉可确定章节的页数: {covered}/{len(page_chap)}")

# 2) 与 chunk 的 section 比对
d = pickle.load(open(rag_index(), "rb"))
chunks = d["chunks"]

chap_typed = 0   # section 是「第X章」
sec_typed = 0    # section 是「第X节」（无章）
empty = 0
mismatch = 0
checked = 0
examples = []

for c in chunks:
    sec = c["section"]
    truth = page_chap.get(c["page"])
    if not sec:
        empty += 1
        continue
    if CHAP_RE.match(sec):
        chap_typed += 1
        if truth and sec != truth:
            mismatch += 1
            checked += 1
            if len(examples) < 8:
                examples.append((c["page"], sec, truth))
        elif truth:
            checked += 1
    elif re.match(r"^第[一二三四五六七八九十百]+节", sec):
        sec_typed += 1

n = len(chunks)
print(f"\nchunk 总数: {n}")
print(f"  section 为空            : {empty} ({empty/n:.1%})")
print(f"  section 为『第X章』      : {chap_typed} ({chap_typed/n:.1%})")
print(f"  section 为『第X节』(无章): {sec_typed} ({sec_typed/n:.1%})  <- 无法判断属于哪一章")
print(f"\n在有真值可比的 {checked} 个『第X章』标签中，与页眉真值不一致: {mismatch} ({mismatch/max(checked,1):.1%})")
print("误标示例 (PDF页, 标注章节, 页眉真实章节):")
for ex in examples:
    print("   ", ex)

# 3) 相似文本跨章节区分能力测试
print("\n=== 相似文本是否能区分章节？ ===")
targets = ["核心要点", "小结", "内容要点"]
for t in targets:
    hits = [c for c in chunks if c["text"].strip().startswith(t)]
    if len(hits) >= 2:
        print(f"  以『{t}』开头的 chunk: {len(hits)} 个，样例(page, section):",
              [(h['page'], h['section']) for h in hits[:5]])
