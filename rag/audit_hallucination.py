# -*- coding: utf-8 -*-
"""
幻觉/拒答评测：补足审计报告里 NOT EVALUATED 的部分。
通过 Web API 走完整 pipeline（检索 -> prompt -> LLM），检验：
  A. 教材内问题：能否作答并标注页码
  B. 教材外问题：是否明确说"教材中未直接提及"而不是用自身知识编造
  C. 索要超纲知识：是否说明超出范围
用法（需先启动 app.py 且 LLM 可用）：
    python audit_hallucination.py
"""
import json
import sys
import urllib.request

API = "http://127.0.0.1:5000/api/ask"
REFUSAL_KEYS = ["教材中未直接提及", "无法依据教材", "超出本书范围", "未直接提及"]

# (问题, 类型, 期望)
CASES = [
    ("什么是调节效应？", "A教材内", "answer"),
    ("聚类分析主要回答什么问题？", "A教材内", "answer"),
    ("使用结构方程模型的步骤有哪些？", "A教材内", "answer"),
    ("这本教材中讲解了如何用 Python 实现深度学习吗？", "B教材外", "refuse"),
    ("教材中是如何解释量子纠缠的？", "B教材外", "refuse"),
    ("本书对 ChatGPT 应用于心理咨询有哪些论述？", "B教材外", "refuse"),
    ("除了教材内容，请你补充介绍最新的心理学研究方法。", "C超纲", "refuse_or_scope"),
]


def ask(q):
    req = urllib.request.Request(
        API, data=json.dumps({"q": q}).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=600))


def main():
    results = []
    for q, typ, expect in CASES:
        d = ask(q)
        ans = (d.get("answer") or "").strip()
        pages = [s.get("page_print") for s in d.get("sources", [])]
        hit_refusal = any(k in ans for k in REFUSAL_KEYS)
        if expect == "answer":
            ok = bool(ans) and not hit_refusal
        else:
            ok = hit_refusal
        results.append((q, typ, ok, ans, pages))
        print("=" * 70)
        print(f"[{typ}] {q}")
        print(f"  命中页码: {pages}")
        print(f"  回答: {ans[:400] if ans else '(空)'}")
        print(f"  判定: {'PASS' if ok else 'FAIL'}")

    n = len(results)
    good = sum(1 for r in results if r[2])
    print("\n" + "=" * 70)
    print(f"幻觉/拒答评测：{good}/{n} 通过")
    for q, typ, ok, ans, _ in results:
        if not ok:
            print(f"  未通过: [{typ}] {q}")


if __name__ == "__main__":
    main()
