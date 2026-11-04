# -*- coding: utf-8 -*-
"""tools/extract_terms.py —— 候选术语库 + 教材/讲义双源覆盖矩阵（只读取证）。

铁律：
  * 检索命中只作【候选证据】，不是事实、不是 gold
  * 所有条目 verified=False / formula_verified=False / status=PENDING_HUMAN_REVIEW
  * 不改任何原始数据，只写 site/content/terms_draft.json 与 terms_coverage.md

用法（.venv）：
    .venv\\Scripts\\python.exe tools\\extract_terms.py [--k 6] [--only 调节效应]
"""
import os
import re
import sys
import json
import argparse
import collections
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "rag"))

from rag_multi import retrieve_multi, index_status  # noqa: E402

OUT_DRAFT = os.path.join(ROOT, "site", "content", "terms_draft.json")
OUT_MATRIX = os.path.join(ROOT, "site", "content", "terms_coverage.md")
COURSE_INDEX = os.path.join(ROOT, "rag", "rag_data", "index_course.pkl")

CATEGORIES = ["数据准备", "方差分析", "回归", "分类与聚类", "因素分析",
              "结构方程", "中介调节", "多层模型", "效应量与假设检验", "实验统计方法"]

# (中文名, 英文名, 分类, 期望章, [检索关键词])
TERMS = [
    # ---- 数据准备（第一章）----
    ("异常值", "Outlier", "数据准备", "第一章", ["异常值", "极端值", "outlier"]),
    ("多变量异常值", "Multivariate Outlier", "数据准备", "第一章", ["多变量异常值", "马氏距离"]),
    ("马氏距离", "Mahalanobis Distance", "数据准备", "第一章", ["马氏距离", "Mahalanobis"]),
    ("盒式图", "Box Plot", "数据准备", "第一章", ["盒式图", "箱线图", "boxplot"]),
    ("缺失数据", "Missing Data", "数据准备", "第一章", ["缺失数据", "缺失值"]),
    ("缺失机制", "Missing Data Mechanism", "数据准备", "第一章", ["缺失机制", "随机缺失", "MCAR"]),
    ("多重插补", "Multiple Imputation", "数据准备", "第一章", ["多重插补", "插补"]),
    ("数据标准化", "Standardization", "数据准备", "第一章", ["标准化", "标准分数", "z分数"]),
    ("数据中心化", "Centering", "数据准备", "第十二章", ["中心化", "中心化处理"]),
    # ---- 方差分析（第二章）----
    ("多元方差分析", "MANOVA", "方差分析", "第二章", ["多元方差分析", "MANOVA"]),
    ("一元方差分析", "ANOVA", "方差分析", "第二章", ["一元方差分析", "方差分析"]),
    ("Wilks 统计量", "Wilks' Lambda", "方差分析", "第二章", ["Wilks", "统计量"]),
    ("协变量", "Covariate", "方差分析", "第二章", ["协变量", "协方差分析"]),
    ("主效应", "Main Effect", "方差分析", "第二章", ["主效应"]),
    ("交互作用", "Interaction", "方差分析", "第二章", ["交互作用"]),
    ("简单斜率检验", "Simple Slope Test", "方差分析", "第十二章", ["简单斜率", "简单斜率检验"]),
    ("方差齐性", "Homogeneity of Variance", "方差分析", "第二章", ["方差齐性", "齐性"]),
    ("多元正态性", "Multivariate Normality", "方差分析", "第二章", ["多元正态", "正态性"]),
    ("球形假设", "Sphericity", "方差分析", "第十三章", ["球形", "球形假设"]),
    # ---- 回归（第三、四章）----
    ("多元回归", "Multiple Regression", "回归", "第三章", ["多元回归", "回归分析"]),
    ("回归系数", "Regression Coefficient", "回归", "第三章", ["回归系数"]),
    ("标准误", "Standard Error", "回归", "第三章", ["标准误"]),
    ("决定系数", "R-squared", "回归", "第三章", ["决定系数", "R2", "解释率"]),
    ("多重共线性", "Multicollinearity", "回归", "第三章", ["共线性", "多重共线性", "VIF"]),
    ("虚拟编码", "Dummy Coding", "回归", "第三章", ["虚拟编码", "虚拟变量"]),
    ("逐步回归", "Stepwise Regression", "回归", "第三章", ["逐步回归"]),
    ("残差", "Residual", "回归", "第三章", ["残差"]),
    ("Logistic 回归", "Logistic Regression", "回归", "第四章", ["Logistic", "logistic回归"]),
    ("优势比", "Odds Ratio", "回归", "第四章", ["优势比", "OR值"]),
    ("极大似然估计", "Maximum Likelihood", "回归", "第四章", ["极大似然", "似然"]),
    ("交互项乘积指标", "Product Indicator", "回归", "第十二章", ["乘积指标", "乘积项"]),
    # ---- 分类与聚类（第五、六章）----
    ("判别分析", "Discriminant Analysis", "分类与聚类", "第五章", ["判别分析", "判别函数"]),
    ("聚类分析", "Cluster Analysis", "分类与聚类", "第六章", ["聚类分析", "聚类"]),
    ("层次聚类", "Hierarchical Clustering", "分类与聚类", "第六章", ["层次聚类", "系统聚类"]),
    ("K 均值聚类", "K-means Clustering", "分类与聚类", "第六章", ["K均值", "快速聚类"]),
    ("欧氏距离", "Euclidean Distance", "分类与聚类", "第六章", ["欧氏距离", "距离"]),

    # ---- 因素分析（第七、八章）----
    ("探索性因素分析", "EFA", "因素分析", "第七章", ["探索性因素分析", "因素分析"]),
    ("验证性因素分析", "CFA", "因素分析", "第八章", ["验证性因素分析", "验证性"]),
    ("因素载荷", "Factor Loading", "因素分析", "第七章", ["因素载荷", "载荷"]),
    ("公共因素", "Common Factor", "因素分析", "第七章", ["公共因素", "共同因素"]),
    ("特征根", "Eigenvalue", "因素分析", "第七章", ["特征根", "特征值"]),
    ("碎石图", "Scree Plot", "因素分析", "第七章", ["碎石图", "碎石"]),
    ("因子旋转", "Factor Rotation", "因素分析", "第七章", ["旋转", "斜交", "正交"]),
    ("公共因素数确定", "Number of Factors", "因素分析", "第七章", ["因素个数", "平行分析", "保留"]),
    ("模型识别", "Model Identification", "因素分析", "第八章", ["模型识别", "识别"]),
    ("模型拟合指数", "Fit Indices", "因素分析", "第十章", ["拟合指数", "CFI", "TLI", "SRMR"]),
    ("RMSEA", "RMSEA", "因素分析", "第八章", ["RMSEA", "近似误差"]),
    ("修正指数", "Modification Index", "因素分析", "第八章", ["修正指数", "MI"]),
    # ---- 结构方程（第九、十章）----
    ("路径分析", "Path Analysis", "结构方程", "第九章", ["路径分析"]),
    ("结构方程模型", "SEM", "结构方程", "第十章", ["结构方程模型", "SEM"]),
    ("潜变量", "Latent Variable", "结构方程", "第十章", ["潜变量", "潜在变量"]),
    ("测量模型", "Measurement Model", "结构方程", "第十章", ["测量模型"]),
    ("结构模型", "Structural Model", "结构方程", "第十章", ["结构模型"]),
    ("非递归模型", "Non-recursive Model", "结构方程", "第十章", ["非递归", "递归模型"]),
    ("模型修正", "Model Modification", "结构方程", "第十章", ["模型修正", "修正"]),
    # ---- 中介调节（第十一、十二章）----
    ("中介效应", "Mediation Effect", "中介调节", "第十一章", ["中介效应", "中介"]),
    ("中介变量", "Mediator", "中介调节", "第十一章", ["中介变量"]),
    ("间接效应", "Indirect Effect", "中介调节", "第十一章", ["间接效应"]),
    ("Bootstrap 检验", "Bootstrap", "中介调节", "第十一章", ["Bootstrap", "偏差校正"]),
    ("Sobel 检验", "Sobel Test", "中介调节", "第十一章", ["Sobel"]),
    ("调节效应", "Moderation Effect", "中介调节", "第十二章", ["调节效应", "调节"]),
    ("调节变量", "Moderator", "中介调节", "第十二章", ["调节变量"]),
    ("有调节的中介", "Moderated Mediation", "中介调节", "第十二章", ["有调节的中介"]),
    ("有中介的调节", "Mediated Moderation", "中介调节", "第十二章", ["有中介的调节"]),
    ("交互作用图", "Interaction Plot", "中介调节", "第十二章", ["交互作用图", "调节图"]),
    # ---- 多层模型（第十三、十四章）----
    ("多层线性模型", "HLM", "多层模型", "第十三章", ["多层线性模型", "HLM"]),
    ("零模型", "Null Model", "多层模型", "第十三章", ["零模型"]),
    ("随机截距模型", "Random Intercept Model", "多层模型", "第十三章", ["随机截距"]),
    ("随机斜率模型", "Random Slope Model", "多层模型", "第十三章", ["随机斜率"]),
    ("组内相关系数", "ICC", "多层模型", "第十三章", ["ICC", "组内相关", "组间差异"]),
    ("固定效应", "Fixed Effect", "多层模型", "第十三章", ["固定效应"]),
    ("随机效应", "Random Effect", "多层模型", "第十三章", ["随机效应"]),
    ("增长模型", "Growth Model", "多层模型", "第十四章", ["增长模型", "发展模型"]),
    ("追踪研究数据", "Longitudinal Data", "多层模型", "第十四章", ["追踪", "纵向"]),
    # ---- 效应量与假设检验 ----
    ("效应量", "Effect Size", "效应量与假设检验", "第二章", ["效应量", "效应值"]),
    ("偏 η²", "Partial Eta Squared", "效应量与假设检验", "第二章", ["偏", "变异解释"]),
    ("统计检验力", "Statistical Power", "效应量与假设检验", "第二章", ["检验力"]),
    ("显著性水平", "Significance Level", "效应量与假设检验", "第二章", ["显著性水平", "显著"]),
    ("p 值", "p-value", "效应量与假设检验", "第二章", ["显著性", "概率"]),
    ("置信区间", "Confidence Interval", "效应量与假设检验", "第二章", ["置信区间"]),
    ("多重比较校正", "Multiple Comparison Correction", "效应量与假设检验", None, ["多重比较", "Bonferroni"]),
    # ---- 实验统计方法（第十四章）----
    ("t 检验", "t-test", "实验统计方法", "第十四章", ["t检验", "t 检验"]),
    ("卡方检验", "Chi-square Test", "实验统计方法", "第十四章", ["卡方", "检验"]),
    ("事后比较", "Post Hoc Comparison", "实验统计方法", "第十四章", ["事后比较", "两两比较"]),
    ("非参数检验", "Nonparametric Test", "实验统计方法", None, ["非参数"]),
    ("自由度", "Degrees of Freedom", "实验统计方法", None, ["自由度"]),
]

# 章 → 预期讲义 slug（依据讲义关键词实测确认；不确定的章留空，避免产生假告警）
# 实测：w07-regression「回归」164 次、w06-efa「因素分析」15 次、w01-ch1-intro 覆盖第1章
CHAPTER_TO_COURSE = {
    "第一章": ["w01-ch1-intro"],
    "第三章": ["w07-regression"], "第四章": ["w07-regression"],
    "第七章": ["w06-efa"],
    "第八章": ["w10-cfa"], "第十章": ["w10-cfa"],
    "第十一章": ["w09-mediation", "w02-week2"],
    "第十二章": ["w08-moderation", "w02-week2"],
    "第十四章": ["ch14-expstats"],
}


def to_slug(en, zh):
    s = re.sub(r"[^a-z0-9]+", "-", (en or "").lower()).strip("-")
    if not s:
        s = "term-%d" % (abs(hash(zh)) % 100000)
    return s


def snippet(t, n=90):
    return re.sub(r"\s+", " ", t).strip()[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    import pickle
    with open(COURSE_INDEX, "rb") as f:
        co_index = pickle.load(f)
    risk_by_chunk = {c["chunk_id"]: c.get("numeric_risk", 0) for c in co_index["chunks"]}

    used_slugs = collections.Counter()
    entries = []
    st = index_status()
    for zh, en, cat, chap, kws in TERMS:
        if args.only and args.only not in (zh, en):
            continue
        rows = retrieve_multi("%s %s" % (zh, en), k=args.k)
        tb = [r for r in rows if r["source"] == "textbook"][:3]
        co = [r for r in rows if r["source"] == "course"][:3]
        exp_docs = CHAPTER_TO_COURSE.get(chap, []) if chap else []
        chap_ok = any((r["path"] or "").startswith(chap) for r in tb) if chap else None
        doc_ok = any(r["doc"] in exp_docs for r in co) if exp_docs else None
        flags = []
        if not tb:
            flags.append("NO_TEXTBOOK_EVIDENCE")
        elif chap and not chap_ok:
            flags.append("CHAPTER_MISMATCH")
        if co and exp_docs and not doc_ok:
            flags.append("COURSE_NOT_EXPECTED_DOC")
        if not co:
            flags.append("NO_COURSE_EVIDENCE")
        if any(risk_by_chunk.get(r["chunk_id"], 0) >= 5 for r in co):
            flags.append("COURSE_NUMERIC_RISK")
        if tb and co:
            coverage = "textbook+course"
        elif tb:
            coverage = "textbook_only"
        elif co:
            coverage = "course_only"
        else:
            coverage = "none"
        slug = to_slug(en, zh)
        used_slugs[slug] += 1
        if used_slugs[slug] > 1:
            slug = "%s-%d" % (slug, used_slugs[slug])
        entries.append({
            "slug": slug,
            "zh": zh, "en": en,
            "category": cat,
            "expected_chapter": chap or "",
            "aliases": [],
            "status": "PENDING_HUMAN_REVIEW",
            "verified": False,
            "formula_verified": False,
            "coverage": coverage,
            "flags": flags,
            "evidence": {
                "textbook": [{
                    "chunk_id": r["chunk_id"], "page_print": r["page_print"],
                    "page_pdf": r["page_pdf"], "path": r["path"],
                    "sim": r["sim"], "snippet": snippet(r["text"]),
                } for r in tb],
                "course": [{
                    "chunk_id": r["chunk_id"], "doc": r["doc"],
                    "page_course": r["page_course"],
                    "block_source": r["block_source"], "xref": r["xref"],
                    "numeric_risk": risk_by_chunk.get(r["chunk_id"], 0),
                    "sim": r["sim"], "snippet": snippet(r["text"]),
                } for r in co],
            },
            "candidate_evidence_only": True,
            "note": "检索命中仅为候选证据；术语定义、公式与数值必须人工核对教材原页",
        })

    draft = {
        "schema_version": "1.0",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "generator": "tools/extract_terms.py",
        "status": "DRAFT_CANDIDATES_PENDING_HUMAN_REVIEW",
        "warning": "本文件所有条目未经人工确认，不得直接用于站点发布或作为事实依据",
        "index_status": st,
        "categories": CATEGORIES,
        "counts": {
            "total": len(entries),
            "by_category": dict(collections.Counter(e["category"] for e in entries)),
            "by_coverage": dict(collections.Counter(e["coverage"] for e in entries)),
            "flagged": dict(collections.Counter(
                f for e in entries for f in e["flags"])),
        },
        "terms": entries,
    }
    os.makedirs(os.path.dirname(OUT_DRAFT), exist_ok=True)
    with open(OUT_DRAFT, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, indent=1)
    write_matrix(entries, draft["counts"])
    print("terms:", len(entries), draft["counts"]["by_coverage"])
    print("flagged:", draft["counts"]["flagged"])
    print("->", OUT_DRAFT)


def write_matrix(entries, counts):
    L = ["# 候选术语覆盖矩阵（自动生成，未人工确认）\n\n",
         "来源：`tools/extract_terms.py`（教材索引 + 讲义索引双源检索取证，仅作候选）\n\n",
         "| 分类 | 术语数 | 教材有证据 | 讲义有证据 | 双源 | 仅教材 | 仅讲义 | 无证据 |\n",
         "|---|---|---|---|---|---|---|---|\n"]
    for cat in CATEGORIES:
        es = [e for e in entries if e["category"] == cat]
        if not es:
            continue
        tb = sum(1 for e in es if e["evidence"]["textbook"])
        co = sum(1 for e in es if e["evidence"]["course"])
        both = sum(1 for e in es if e["evidence"]["textbook"] and e["evidence"]["course"])
        onc = sum(1 for e in es if not e["evidence"]["textbook"] and e["evidence"]["course"])
        non = sum(1 for e in es if not e["evidence"]["textbook"] and not e["evidence"]["course"])
        L.append("| %s | %d | %d | %d | %d | %d | %d | %d |\n"
                 % (cat, len(es), tb, co, both, tb - both, onc, non))
    L.append("\n**合计**：%d 条；%s\n\n" % (len(entries), counts["by_coverage"]))
    L.append("## 需要人工重点确认的条目\n\n")
    for flag in ("NO_TEXTBOOK_EVIDENCE", "CHAPTER_MISMATCH", "COURSE_NOT_EXPECTED_DOC",
                 "COURSE_NUMERIC_RISK", "NO_COURSE_EVIDENCE"):
        hit = [e for e in entries if flag in e["flags"]]
        if not hit:
            continue
        L.append("- **%s**（%d 条）：%s\n" % (flag, len(hit),
                                          "、".join(e["zh"] for e in hit[:18])))
    L.append("\n## 免责与已知检测盲区\n\n")
    L.append("- **上表「有证据」比例虚高**：检索每次必返回 top-%d，任何术语都会命中若干块，"
             "因此「双源 78/86」**不构成覆盖度证明**；真正有判别力的是 "
             "`CHAPTER_MISMATCH` / `NO_TEXTBOOK_EVIDENCE` 等告警与人工核对。\n" % 8)
    L.append("- 命中≠教材讲了该术语；**未命中≠教材没讲**（OCR 符号丢失、写法差异都会漏检）。\n")
    L.append("- **图片主导的讲义**（Week2/4/6、第14章）内容多为统计软件结果截图，"
             "OCR 后以数字与界面标签为主、中文关键词少 → 关键词式覆盖检测会**系统性低估**"
             "讲义覆盖度（例：ch14 全文 7.4 万字但「t检验」仅 2 次命中）。\n")
    L.append("- `η` 在教材 OCR 中 0 次出现 → 与 η²/偏 η² 相关的术语只能靠人工确认。\n")
    L.append("- 所有条目 `verified=false`，须人工核对教材原页后填写，方可进入站点。\n")
    with open(OUT_MATRIX, "w", encoding="utf-8") as f:
        f.writelines(L)


if __name__ == "__main__":
    main()
