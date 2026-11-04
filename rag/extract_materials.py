# -*- coding: utf-8 -*-
"""
从本地 RAG 中提取「核心方法」主题的教材原文素材，作为撰写科普内容的依据与引用来源。
输出：psy-stats-site/materials/<slug>.md，每条带教材印刷页码 + 章节路径。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rag_core import retrieve  # noqa: E402

# 输出到「项目根目录下 site/materials」，相对计算，便于整体搬迁
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "site", "materials")

TOPICS = [
    ("多元回归分析", "regression", [
        "多元回归分析主要回答什么问题？",
        "使用多元回归分析的前提假设有哪些？",
        "多元回归分析的类型有哪些？",
    ]),
    ("调节效应", "moderation", [
        "什么是调节效应？",
        "调节效应的检验方法有哪些？",
        "简单斜率检验是什么？",
    ]),
    ("中介效应", "mediation", [
        "什么是中介效应？",
        "中介效应的检验方法有哪些？",
        "Bootstrap 在中介效应检验中起什么作用？",
    ]),
    ("探索性因素分析", "efa", [
        "什么是探索性因素分析？",
        "探索性因素分析的步骤有哪些？",
        "如何确定公共因素的数量？",
    ]),
    ("验证性因素分析", "cfa", [
        "什么是验证性因素分析？",
        "验证性因素分析与探索性因素分析有什么区别？",
        "验证性因素分析中模型识别分为哪几种情况？",
    ]),
    ("结构方程模型", "sem", [
        "结构方程模型适合解决什么问题？",
        "使用结构方程模型的步骤有哪些？",
        "结构方程模型的组成部分有哪些？",
    ]),
    ("多层线性模型", "hlm", [
        "多层线性模型适合分析什么样的数据？",
        "多层线性模型的分析步骤是什么？",
        "零模型在多层线性模型中回答什么问题？",
    ]),
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for title, slug, queries in TOPICS:
        seen, blocks = set(), []
        for q in queries:
            for s in retrieve(q, k=6):
                key = s["chunk_id"]
                if key in seen:
                    continue
                seen.add(key)
                blocks.append((q, s))
        path = os.path.join(OUT_DIR, slug + ".md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {title} —— 教材原文素材\n\n")
            f.write("> 由本地 RAG 检索生成，页码为教材印刷页码。用于撰写科普内容时核对事实与标注出处。\n\n")
            cur_q = None
            for q, s in blocks:
                if q != cur_q:
                    f.write(f"\n## 检索问题：{q}\n")
                    cur_q = q
                f.write(f"\n**教材第{s['page_print']}页**（PDF {s['page_pdf']}） · {s['path'] or '—'}\n\n")
                f.write(s["text"].strip() + "\n")
        print(f"{title}: {len(blocks)} 段 -> {path}")


if __name__ == "__main__":
    main()
