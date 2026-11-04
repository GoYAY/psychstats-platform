# -*- coding: utf-8 -*-
"""tools/make_review_checklist.py —— 生成【人工查验用】的概念清单文档与逐条 CSV。

目的：让人能对照教材原页逐条确认「概念是否有缺漏 / 错误 / 多余」，并留下可审计的查验记录。
不做任何判定：所有 human_* 列留空等待人工填写。

产出：
  docs/概念清单_人工查验.md    （按章：节标题核对表 + 概念核对表 + 核对指引）
  docs/概念清单_人工查验.csv   （逐条可填，Excel 可打开）
用法：.venv\\Scripts\\python.exe tools/make_review_checklist.py
"""
import os
import re
import csv
import json
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONCEPTS_JSON = os.path.join(ROOT, "site", "content", "concepts_by_chapter.json")
OUT_MD = os.path.join(ROOT, "docs", "概念清单_人工查验.md")
OUT_CSV = os.path.join(ROOT, "docs", "概念清单_人工查验.csv")

CHAP_TITLES = {
    "第一章": "数据清理与准备", "第二章": "多元方差分析", "第三章": "多元回归分析",
    "第四章": "Logistic 回归分析", "第五章": "判别分析", "第六章": "聚类分析",
    "第七章": "探索性因素分析", "第八章": "验证性因素分析", "第九章": "路径分析",
    "第十章": "结构方程模型", "第十一章": "中介分析", "第十二章": "调节效应",
    "第十三章": "多层线性模型简介", "第十四章": "多层线性模型在追踪研究中的应用",
}

# (章, 概念名, [检索关键词])  —— 由 RAG 章节结构与教材要点归纳，供人工逐条确认
CONCEPTS = [
    ("第一章", "数据清理与准备的目的", ["清理", "准备", "目的"]),
    ("第一章", "单变量异常值", ["单变量异常值"]),
    ("第一章", "多变量异常值", ["多变量异常值"]),
    ("第一章", "马氏距离", ["马氏距离"]),
    ("第一章", "盒式图（箱线图）", ["盒式图", "箱线图"]),
    ("第一章", "异常值检验方法（标准差法 / 盒式图 / 马氏距离）", ["标准差", "异常值"]),
    ("第一章", "异常值处理策略", ["异常值", "处理"]),
    ("第一章", "缺失数据", ["缺失数据"]),
    ("第一章", "缺失类型（完全随机 / 随机 / 非随机缺失）", ["缺失", "随机缺失"]),
    ("第一章", "缺失诊断（缺失比例与模式）", ["缺失模式", "缺失比例"]),
    ("第一章", "缺失处理方法（成列删除 / 单一插补 / 多重插补 / 极大似然）", ["插补", "删除"]),
    ("第一章", "数据变换与标准化", ["标准化", "变换"]),
    ("第一章", "多元正态性", ["多元正态"]),
    ("第一章", "方差齐性", ["方差齐性", "齐性"]),
    ("第一章", "线性与误差独立性假设", ["线性", "独立"]),

    ("第二章", "多元方差分析（MANOVA）", ["多元方差分析"]),
    ("第二章", "一元方差分析（对比）", ["一元方差分析"]),
    ("第二章", "主效应", ["主效应"]),
    ("第二章", "交互作用", ["交互作用"]),
    ("第二章", "多元检验统计量（Wilks' Λ / Pillai / Hotelling / Roy）", ["Wilks", "Pillai", "统计量"]),
    ("第二章", "MANOVA 的假设条件", ["假设"]),
    ("第二章", "事后检验", ["事后检验", "事后"]),
    ("第二章", "多元协方差分析（MANCOVA）与协变量", ["协变量", "协方差分析"]),

    ("第三章", "多元回归分析的目的", ["多元回归"]),
    ("第三章", "标准回归", ["标准回归"]),
    ("第三章", "序列（分层）回归", ["序列", "分层"]),
    ("第三章", "逐步回归", ["逐步"]),
    ("第三章", "回归系数与回归方程", ["回归系数", "回归方程"]),
    ("第三章", "整体显著性检验", ["显著性检验", "整体"]),
    ("第三章", "自变量重要性（标准化系数 / R² 变化）", ["标准化系数", "重要性"]),
    ("第三章", "多重共线性（VIF / 容忍度）", ["共线性", "容忍度", "VIF"]),
    ("第三章", "虚拟编码", ["虚拟"]),
    ("第三章", "交互项与中心化", ["交互", "中心化"]),
    ("第三章", "异常值对回归的影响", ["异常值"]),
    ("第三章", "回归分析的局限性", ["局限"]),

    ("第四章", "Logistic 回归适用情境", ["logistic", "Logistic"]),
    ("第四章", "Logistic 模型与 logit 变换", ["模型", "系数"]),
    ("第四章", "回归系数含义", ["系数"]),
    ("第四章", "优势比（OR）", ["优势", "OR"]),
    ("第四章", "整体检验与拟合优度", ["拟合", "检验"]),
    ("第四章", "预测分类与注意事项", ["预测", "注意"]),

    ("第五章", "判别分析的目的与适用情境", ["判别分析"]),
    ("第五章", "判别分析的假设条件", ["假设"]),
    ("第五章", "判别函数与分类函数", ["判别函数", "分类函数"]),
    ("第五章", "判别系数与结构系数", ["判别系数", "结构系数"]),
    ("第五章", "矩心", ["矩心"]),
    ("第五章", "同时判别与逐步判别", ["逐步"]),

    ("第六章", "聚类分析的目的与应用场景", ["聚类分析"]),
    ("第六章", "样品聚类与指标聚类", ["样品", "指标"]),
    ("第六章", "距离测度（欧氏 / 平方欧氏 / 明科夫斯基 / 切比雪夫 / 马氏）", ["距离", "欧氏", "明科夫斯基"]),
    ("第六章", "层次聚类法（最短 / 最长 / 平均 / 离差平方和）", ["层次聚类", "离差平方和"]),
    ("第六章", "非层次聚类法（K 均值 / 迭代）", ["K均值", "迭代", "快速聚类"]),
    ("第六章", "类数确定与结果解释", ["类数", "解释"]),
    ("第六章", "聚类与因素分析 / 回归的区别", ["区别"]),

    ("第七章", "探索性因素分析的目的", ["探索性因素分析"]),
    ("第七章", "因素分析模型与基本步骤", ["模型", "步骤"]),
    ("第七章", "公共因素 / 特殊因素 / 载荷 / 共同度", ["公共因素", "载荷"]),
    ("第七章", "前提假设与 KMO / Bartlett 检验", ["KMO", "Bartlett", "假设"]),
    ("第七章", "因素抽取方法（主成分 / 主轴 / 极大似然）", ["抽取", "主成分"]),
    ("第七章", "因素数确定（特征根>1 / 碎石图 / 平行分析）", ["特征根", "碎石"]),
    ("第七章", "因素旋转（正交 / 斜交）", ["旋转"]),
    ("第七章", "因素命名与结果解释", ["命名", "解释"]),

    ("第八章", "CFA 与 EFA 的异同", ["探索性因素分析", "异同"]),
    ("第八章", "CFA 的图示与模型", ["模型", "图"]),
    ("第八章", "模型识别（不可识别 / 恰识别 / 超识别）", ["识别"]),
    ("第八章", "参数估计方法", ["估计"]),
    ("第八章", "拟合指数（χ² / RMSEA / CFI / TLI / SRMR）", ["RMSEA", "拟合"]),
    ("第八章", "模型评价与修正指数（MI）", ["修正"]),
    ("第八章", "等价性检验", ["等价"]),

    ("第九章", "路径分析的目的与因果假设", ["路径分析"]),
    ("第九章", "递归模型与非递归模型", ["非递归", "递归"]),
    ("第九章", "路径分析中的模型识别", ["识别"]),
    ("第九章", "效应分解（直接 / 间接 / 总效应）", ["效应分解", "间接效应"]),
    ("第九章", "模型评价与修正", ["评价", "修正"]),

    ("第十章", "结构方程模型（SEM）的定义与定位", ["结构方程模型"]),
    ("第十章", "测量模型与结构模型", ["测量模型", "结构模型"]),
    ("第十章", "潜变量", ["潜变量"]),
    ("第十章", "模型设定与使用步骤", ["步骤"]),
    ("第十章", "模型比较与多组比较", ["比较"]),
    ("第十章", "SEM 的局限性与注意事项", ["局限", "注意"]),

    ("第十一章", "中介变量与中介效应", ["中介变量", "中介效应"]),
    ("第十一章", "效应分解（总效应 / 直接效应 / 间接效应）", ["效应分解", "间接"]),
    ("第十一章", "完全中介与部分中介", ["完全中介", "部分中介"]),
    ("第十一章", "中介效应检验方法（依次检验 / Sobel / Bootstrap）", ["检验", "Bootstrap", "Sobel"]),
    ("第十一章", "潜变量中介模型", ["潜变量中介"]),
    ("第十一章", "中介效应量指标", ["效应量", "中介比例"]),

    ("第十二章", "调节效应与调节变量", ["调节效应", "调节变量"]),
    ("第十二章", "调节效应与交互作用的关系", ["交互作用"]),
    ("第十二章", "调节效应与中介效应的区别", ["中介"]),
    ("第十二章", "显变量的调节效应检验", ["显变量", "乘积", "检验"]),
    ("第十二章", "连续变量中心化与虚拟编码", ["中心化", "虚拟"]),
    ("第十二章", "简单斜率检验与交互作用图", ["简单斜率", "交互"]),
    ("第十二章", "潜变量的调节效应（乘积指标法）", ["乘积指标", "潜变量"]),
    ("第十二章", "有调节的中介", ["有调节的中介"]),
    ("第十二章", "有中介的调节", ["有中介的调节"]),

    ("第十三章", "多层（嵌套）数据结构", ["嵌套", "层次"]),
    ("第十三章", "多层线性模型（HLM）概述", ["多层线性模型"]),
    ("第十三章", "零模型（随机效应一元方差分析模型）", ["零模型"]),
    ("第十三章", "随机截距模型", ["随机截距"]),
    ("第十三章", "随机斜率模型", ["随机斜率"]),
    ("第十三章", "固定效应与随机效应", ["固定效应", "随机效应"]),
    ("第十三章", "参数估计方法（ML / REML）", ["估计"]),
    ("第十三章", "组内相关系数（ICC）与组间方差", ["组内", "组间", "方差"]),

    ("第十四章", "重复测量嵌套于个体的结构", ["重复测量", "嵌套"]),
    ("第十四章", "追踪研究中的多层线性模型", ["追踪"]),
    ("第十四章", "增长曲线模型", ["增长", "发展"]),
    ("第十四章", "时间编码与趋势解释", ["时间"]),
    ("第十四章", "个体内与个体间变异", ["个体", "变异"]),
    ("第十四章", "注意问题与应用案例", ["注意", "案例"]),
]


def pages_of(chap_data, keywords, limit=3):
    """在该章的证据条目（节标题/要点/定义候选）里找含关键词的页号。"""
    hits = []
    for key in ("definitions", "bullets", "sections"):
        for item in chap_data.get(key, []):
            text = item.get("text") or item.get("title") or ""
            if any(k in text for k in keywords):
                p = item["page_pdf"]
                if p not in hits:
                    hits.append(p)
            if len(hits) >= limit:
                return hits, key
    return hits, ("definitions" if hits else "")


def main():
    data = json.load(open(CONCEPTS_JSON, encoding="utf-8"))["chapters"]
    rows = []
    for chap, concept, kws in CONCEPTS:
        cd = data.get(chap, {})
        pages, src = pages_of(cd, kws)
        pr = cd.get("page_print_range") or [None, None]
        rows.append({
            "chapter": "%s %s" % (chap, CHAP_TITLES[chap]),
            "concept": concept,
            "evidence_pdf_pages": ",".join(str(p) for p in pages) or "NONE",
            "evidence_print_pages_est": ",".join(str(max(int(p) - 13, 1)) for p in pages) or "NONE",
            "auto_evidence_source": src or "NONE",
            "chapter_pdf_range": "%s-%s" % tuple(cd.get("page_pdf_range") or ["", ""]),
            "chapter_print_range_est": "%s-%s" % tuple(pr),
            "human_page_correct": "",
            "human_verdict": "",
            "human_correction": "",
            "human_notes": "",
            "reviewer": "",
            "reviewed_at": "",
        })

    fields = list(rows[0].keys())
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    L = ["# 概念清单 · 人工查验表\n\n",
         "生成时间：%s\n\n" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
         "## 怎么用这份表\n\n",
         "1. 打开原始教材 PDF（`高级心理统计.pdf`，**页码＝表中 evidence_pdf_pages**），"
         "逐条对照概念是否真的在该章出现。\n",
         "2. 在 `docs/概念清单_人工查验.csv` 中填写：\n",
         "   - `human_page_correct`：自动给出的页码是否正确（1/0）\n",
         "   - `human_verdict`：`OK` / `MISSING`（教材有但清单漏了）/ "
         "`WRONG`（概念名或归属章有误）/ `EXTRA`（清单多余）\n",
         "   - `human_correction`：应改成什么（如正确概念名/正确章节/正确页码）\n",
         "3. 章节级：见每章「节标题核对」表，确认节标题是否与教材一致（OCR 有噪声）。\n\n",
         "> **重要**：`evidence_*` 列是程序从 OCR 文本里找到的**候选页码**，"
         "存在漏检（OCR 符号丢失，如 `η` 全书出现 0 次）与误检，**不能当作教材真值**。\n\n",
         "---\n\n"]

    by_chap = {}
    for r in rows:
        by_chap.setdefault(r["chapter"], []).append(r)
    for chap in [("%s %s" % (c, CHAP_TITLES[c])) for c in CHAP_TITLES]:
        if chap not in by_chap:
            continue
        cd = data[chap.split()[0]]
        L.append("\n## %s\n\n" % chap)
        L.append("章节范围：PDF %s（印刷约 %s）｜节数 %d｜教材自述要点 %d 条｜定义候选 %d 条\n\n"
                 % ("-".join(str(x) for x in cd["page_pdf_range"]),
                    "-".join(str(x) for x in cd["page_print_range"]),
                    cd["n_sections"], len(cd["bullets"]), len(cd["definitions"])))
        L.append("**① 节标题核对**（对照教材，勾选即可）\n\n")
        L.append("| 节标题 | PDF 页 | 一致？ |\n|---|---|---|\n")
        for s in cd["sections"]:
            L.append("| %s | %d | ☐ |\n" % (s["title"], s["page_pdf"]))
        L.append("\n**② 概念核对**（逐条判定 OK / MISSING / WRONG / EXTRA）\n\n")
        L.append("| # | 概念（候选） | 候选 PDF 页 | 判定 | 更正 |\n|---|---|---|---|---|\n")
        for i, r in enumerate(by_chap[chap], 1):
            L.append("| %d | %s | %s | ☐ | |\n"
                     % (i, r["concept"], r["evidence_pdf_pages"]))
        L.append("\n")
    L.append("\n---\n\n## 已知的潜在缺漏（请重点确认是否漏项）\n\n")
    for x in ["效应量系列（η²、偏 η²、Cohen's d）——教材 OCR 中 η 出现 0 次，可能整类漏检",
              "第一类 / 第二类错误、检验力——教材正文少见（实测「第一类错误」0 次）",
              "非参数检验、多重比较校正（Bonferroni）——教材仅零星提及",
              "相关系数与偏相关（Pearson / Spearman）——属基础统计，教材可能仅作回顾",
              "信度 / 效度、项目分析——可能不在本书范围",
              "第十四章第一节标题被 OCR 识别为「第一节能」，需人工确认原标题"]:
        L.append("- %s\n" % x)
    # 自动一致性自检：候选术语库 vs 本清单
    draft = os.path.join(ROOT, "site", "content", "terms_draft.json")
    if os.path.exists(draft):
        lib = json.load(open(draft, encoding="utf-8"))["terms"]
        blob = " | ".join(r["concept"] for r in rows)
        missing = [t["zh"] for t in lib if t["zh"] not in blob]
        L.append("\n## 自动一致性自检（术语库 %d 条 vs 本清单 %d 条）\n\n"
                 % (len(lib), len(rows)))
        L.append("以下候选术语在 `terms_draft.json` 中存在，但本清单未以同名条目出现。\n")
        L.append("**多数是命名差异**（如「缺失机制」↔「缺失类型」、「Wilks 统计量」↔「多元检验统计量」），\n")
        L.append("但其中可能混有**真实缺口**（如 `偏 η²`、`p 值`、`卡方检验`、`自由度`），请人工判定：\n\n")
        for m in missing:
            L.append("- %s\n" % m)
        L.append("\n## 无自动证据、必须人工定位页码的条目（%d 条）\n\n"
                 % sum(1 for r in rows if r["evidence_pdf_pages"] == "NONE"))
        for r in rows:
            if r["evidence_pdf_pages"] == "NONE":
                L.append("- %s（%s）\n" % (r["concept"], r["chapter"]))
    L.append("\n## 查验完成后\n\n"
             "把 CSV 填完 → 用 `tools/promote_term.py` 逐条撰写并核对正文/公式 → "
             "通过校验的条目才会进入站点（未填写一律被拒）。\n")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.writelines(L)
    print("concepts:", len(rows), "→", OUT_CSV)
    print("review doc →", OUT_MD)
    miss = sum(1 for r in rows if r["evidence_pdf_pages"] == "NONE")
    print("无自动证据（需人工定位）:", miss)


if __name__ == "__main__":
    main()
