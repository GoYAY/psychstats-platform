# -*- coding: utf-8 -*-
"""OCR 原文质量审计：抽样 + 页眉页脚/重复行/异常字符统计。"""
import re
import random
import collections
try:
    from .paths import ocr_text
except ImportError:
    from paths import ocr_text

SRC = ocr_text()
txt = open(SRC, encoding="utf-8").read()
lines = txt.splitlines()
print("chars:", len(txt), " lines:", len(lines))

PAGE_RE = re.compile(r"=== 第 (\d+) 页 ===")
idxs = [(m.start(), m.end(), int(m.group(1))) for m in PAGE_RE.finditer(txt)]
page_blocks = []
for i, (s, e, num) in enumerate(idxs):
    end = idxs[i + 1][0] if i + 1 < len(idxs) else len(txt)
    page_blocks.append((num, txt[e:end]))
print("pages:", len(page_blocks))

# ---- 异常字符 ----
print("U+FFFD 替换字符:", txt.count("\ufffd"))
print("控制字符(非\\n\\r\\t):", sum(1 for c in txt if ord(c) < 32 and c not in "\n\r\t"))
odd = collections.Counter(
    c for c in txt if 0x2190 <= ord(c) <= 0x21FF or 0x2200 <= ord(c) <= 0x22FF
)
print("数学/箭头符号:", odd.most_common(12))
print("全角括号「）」出现:", txt.count("）"), " 半角:", txt.count(")"))

# ---- 连续空行 ----
runs = 0
cur = 0
for l in lines:
    if not l.strip():
        cur += 1
    else:
        if cur >= 3:
            runs += 1
        cur = 0
print("连续>=3空行的段落数:", runs)

# ---- 疑似页码残留：形如 "123/" 或纯数字行 ----
pat_slash = re.compile(r"^\s*\d{1,3}\s*/\s*$")
pat_num = re.compile(r"^\s*\d{1,4}\s*$")
n_slash = sum(1 for l in lines if pat_slash.match(l))
n_num = sum(1 for l in lines if pat_num.match(l))
print("形如 '123/' 的行:", n_slash, "  纯数字行:", n_num)

# ---- 重复页眉/页脚 ----
first_lines = collections.Counter()
last_lines = collections.Counter()
for num, body in page_blocks:
    ls = [l.strip() for l in body.splitlines() if l.strip()]
    if ls:
        first_lines[ls[0]] += 1
        last_lines[ls[-1]] += 1
print("\n--- 高频首页行（疑似页眉） ---")
for l, c in first_lines.most_common(15):
    if c >= 8:
        print(f"{c}\t{l[:60]}")
print("\n--- 高频末页行（疑似页脚） ---")
for l, c in last_lines.most_common(15):
    if c >= 8:
        print(f"{c}\t{l[:60]}")

# ---- 章节结构 ----
chap = re.findall(r"第[一二三四五六七八九十百]+章[^\n]{0,22}", txt)
seen = []
for c in chap:
    if c not in seen:
        seen.append(c)
print("\n--- 章节候选（前 45） ---")
for c in seen[:45]:
    print(" ", c)

# ---- 随机抽样 6 页 ----
random.seed(42)
print("\n########## 随机抽样页 ##########")
for num, body in random.sample(page_blocks, 6):
    print(f"\n===== 第 {num} 页 =====\n{body[:650]}")
