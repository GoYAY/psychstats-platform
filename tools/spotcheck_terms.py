# -*- coding: utf-8 -*-
"""tools/spotcheck_terms.py —— 对 20 条术语按「统一核查要点」做结构化抽审（只读）。

自动采集：你可能会问/操作性定义/通俗解释 文本、各模块存在性、公式符号数、
R 代码、选择题选项数与答案、Agent 提示、相关链接、小数前导0 疑似违规。
内容质量（定义准确/真正通俗/不重叠/用途条件）由人/AI 依据采集文本判断。

用法：.venv\\Scripts\\python.exe tools\\spotcheck_terms.py
"""
import os
import re
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TERMS = os.path.join(ROOT, "site", "dist", "terms")

SLUGS = ["variable", "correlation-coefficient", "p-value", "effect-size",
         "partial-eta-squared", "t-test", "anova", "wilks-lambda",
         "standard-error", "multicollinearity", "odds-ratio", "outlier",
         "mahalanobis-distance", "kmo", "parallel-analysis", "rmsea",
         "sem", "mediation-effect", "moderation-effect", "icc"]


def text_between(html, marker, end="</p>"):
    i = html.find(marker)
    if i < 0:
        return ""
    i = html.find(">", i) + 1
    j = html.find(end, i)
    return re.sub(r"<[^>]+>", "", html[i:j]).strip() if j > i else ""


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s).strip()


def main():
    out = []
    for slug in SLUGS:
        p = os.path.join(TERMS, slug + ".html")
        if not os.path.exists(p):
            out.append({"slug": slug, "missing": True})
            continue
        h = open(p, encoding="utf-8").read()
        r = {"slug": slug}
        r["question"] = text_between(h, 'class="real-question"')
        # 操作性定义：<h2>操作性定义</h2> 后的第一个 <p>
        r["definition"] = text_between(h, ">操作性定义</h2>")
        r["plain"] = text_between(h, ">通俗解释</h2>")[:160]
        r["has_plain"] = "通俗解释" in h
        r["has_detail"] = "详细讲解" in h or ">读法" in h
        r["has_output"] = "如何理解输出" in h
        r["has_not_conclude"] = "不要据此下结论" in h or "哪些结论不能直接推出" in h
        r["has_report_example"] = "报告示例" in h
        r["report_says_teaching"] = "教学数据" in h or "不是实际研究" in h
        r["n_formula_keys"] = len(re.findall(r'class="formula-key"', h))
        r["has_katex"] = "katex" in h.lower() or 'class="formula"' in h
        r["has_r_code"] = "language-r" in h or "class=\"language-r\"" in h
        r["has_copy_code"] = "复制代码" in h
        r["has_agent"] = bool(re.search(r"Agent|问 AI|提示词|告诉 AI", h))
        q = re.search(r'class="quiz" data-answer="(\d+)"', h)
        r["quiz_answer"] = q.group(1) if q else None
        r["n_quiz_opt"] = len(re.findall(r'class="opt"|data-idx="\d+"', h))
        r["has_quiz_explain"] = "解析" in h or "explain" in h.lower()
        r["n_related_links"] = len(re.findall(r'class="related[^"]*"\s+href|related', h))
        r["has_page_number"] = bool(re.search(r"教材第\s*\d+\s*页|第\s*\d+\s*页.*PDF", h))
        # 小数前导0 疑似违规：空白/等号/≈/括号后紧跟 ".数字"
        r["decimal_no_lead"] = len(re.findall(r"(?<![0-9A-Za-z/])\.\d", h))
        out.append(r)

    with open(os.path.join(ROOT, "logs", "spotcheck_terms.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("checked:", len(out))
    for r in out:
        print("  %-22s q=%s def=%s formula=%s r=%s agent=%s quiz_opt=%s ans=%s deci=%s page=%s"
              % (r["slug"], "Y" if r["question"] else "N",
                 "Y" if r["definition"] else "N", r["n_formula_keys"],
                 "Y" if r["has_r_code"] else "N", "Y" if r["has_agent"] else "N",
                 r["n_quiz_opt"], r["quiz_answer"], r["decimal_no_lead"],
                 "Y" if r["has_page_number"] else "N"))


if __name__ == "__main__":
    main()
