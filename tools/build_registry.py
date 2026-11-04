"""Build the v2 draft registry from reviewed scope decisions and legacy candidates."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "site" / "content" / "terms_draft.json"
OUTPUT = ROOT / "site" / "content" / "registry.json"

TOPIC_BY_CATEGORY = {
    "心理统计基础": "foundations",
    "数据准备": "data-preparation",
    "效应量与假设检验": "hypothesis-testing",
    "实验统计方法": "group-comparisons",
    "方差分析": "group-comparisons",
    "回归": "regression",
    "分类与聚类": "classification-clustering",
    "因素分析": "factor-analysis",
    "结构方程": "structural-equation-modeling",
    "中介调节": "mediation-moderation",
    "多层模型": "multilevel-longitudinal",
}

BRIDGE_TERMS = [
    ("variable", "变量", "Variable", "心理统计基础"),
    ("standard-score", "标准分数", "Standard Score", "心理统计基础"),
    ("null-hypothesis", "零假设", "Null Hypothesis", "效应量与假设检验"),
    ("data-cleaning", "数据清理", "Data Cleaning", "数据准备"),
    ("exploratory-data-analysis", "探索性数据分析", "Exploratory Data Analysis", "数据准备"),
    ("descriptive-statistics", "描述统计", "Descriptive Statistics", "心理统计基础"),
    ("measurement-scales", "变量与测量尺度", "Variables and Measurement Scales", "心理统计基础"),
    ("population-and-sample", "总体与样本", "Population and Sample", "心理统计基础"),
    ("parameter-and-statistic", "参数与统计量", "Parameter and Statistic", "心理统计基础"),
    ("central-tendency-and-dispersion", "集中趋势与离散程度", "Central Tendency and Dispersion", "心理统计基础"),
    ("normal-distribution", "正态分布", "Normal Distribution", "心理统计基础"),
    ("sampling-distribution", "抽样分布", "Sampling Distribution", "心理统计基础"),
    ("null-and-alternative-hypotheses", "零假设与备择假设", "Null and Alternative Hypotheses", "效应量与假设检验"),
    ("type-i-and-type-ii-errors", "第一类错误与第二类错误", "Type I and Type II Errors", "效应量与假设检验"),
    ("statistical-assumptions", "统计假设", "Statistical Assumptions", "心理统计基础"),
    ("normality", "正态性", "Normality", "心理统计基础"),
    ("linearity", "线性", "Linearity", "心理统计基础"),
    ("independence", "独立性", "Independence", "心理统计基础"),
    ("covariance", "协方差", "Covariance", "心理统计基础"),
    ("correlation-coefficient", "相关系数", "Correlation Coefficient", "心理统计基础"),
    ("simple-linear-regression", "简单线性回归", "Simple Linear Regression", "回归"),
    ("influential-point", "影响点", "Influential Point", "回归"),
    ("sum-of-squares", "平方和", "Sum of Squares", "方差分析"),
    ("mean-square", "均方", "Mean Square", "方差分析"),
    ("f-statistic", "F 统计量", "F Statistic", "方差分析"),
    ("repeated-measures", "重复测量", "Repeated Measures", "方差分析"),
    ("measurement-error", "测量误差", "Measurement Error", "因素分析"),
    ("communality", "共同度", "Communality", "因素分析"),
    ("kmo", "KMO 检验", "KMO", "因素分析"),
    ("bartlett-test", "Bartlett 球形检验", "Bartlett's Test of Sphericity", "因素分析"),
    ("pca", "主成分分析", "Principal Component Analysis", "因素分析"),
    ("factor-extraction", "因素提取", "Factor Extraction", "因素分析"),
    ("direct-effect", "直接效应", "Direct Effect", "中介调节"),
    ("total-effect", "总效应", "Total Effect", "中介调节"),
    ("conditional-effect", "条件效应", "Conditional Effect", "中介调节"),
    ("nested-data", "嵌套数据", "Nested Data", "多层模型"),
    ("level-one", "水平一", "Level 1", "多层模型"),
    ("level-two", "水平二", "Level 2", "多层模型"),
    ("reml", "限制性极大似然估计", "Restricted Maximum Likelihood", "多层模型"),
    ("time-coding", "时间编码", "Time Coding", "多层模型"),
]

WORKFLOWS = {"data-cleaning", "exploratory-data-analysis"}
METHODS = {
    "multiple-imputation", "manova", "anova", "simple-slope-test",
    "multiple-regression", "stepwise-regression", "logistic-regression",
    "discriminant-analysis", "cluster-analysis", "hierarchical-clustering",
    "k-means-clustering", "efa", "cfa", "factor-rotation", "path-analysis",
    "sem", "bootstrap", "sobel-test", "hlm", "null-model",
    "random-intercept-model", "random-slope-model", "growth-model", "t-test",
    "chi-square-test", "post-hoc-comparison", "nonparametric-test",
    "simple-linear-regression", "bartlett-test", "pca", "factor-extraction",
}
INDICATORS = {
    "mahalanobis-distance", "box-plot", "wilks-lambda", "standard-error",
    "r-squared", "odds-ratio", "eigenvalue", "scree-plot", "fit-indices",
    "rmsea", "modification-index", "icc", "effect-size",
    "partial-eta-squared", "statistical-power", "p-value",
    "confidence-interval", "correlation-coefficient", "sum-of-squares",
    "mean-square", "f-statistic", "communality", "kmo",
}
ADVANCED_TOPICS = {
    "factor-analysis", "structural-equation-modeling",
    "mediation-moderation", "multilevel-longitudinal",
}
BASIC_IDS = {
    "variable", "standard-score", "null-hypothesis",
    "outlier", "box-plot", "missing-data", "standardization", "centering",
    "main-effect", "interaction", "regression-coefficient", "standard-error",
    "residual", "effect-size", "statistical-power", "significance-level",
    "p-value", "confidence-interval", "t-test", "chi-square-test",
    "degrees-of-freedom", "data-cleaning", "exploratory-data-analysis",
    "descriptive-statistics", "measurement-scales", "population-and-sample",
    "parameter-and-statistic", "central-tendency-and-dispersion",
    "normal-distribution", "sampling-distribution",
    "null-and-alternative-hypotheses", "type-i-and-type-ii-errors",
    "statistical-assumptions", "normality", "linearity", "independence",
    "covariance", "correlation-coefficient", "simple-linear-regression",
    "sum-of-squares", "mean-square", "f-statistic", "repeated-measures",
}


def term_type(term_id: str) -> str:
    if term_id in WORKFLOWS:
        return "workflow"
    if term_id in METHODS:
        return "method"
    if term_id in INDICATORS:
        return "indicator"
    return "concept"


def build() -> dict:
    legacy = json.loads(LEGACY.read_text(encoding="utf-8"))["terms"]
    raw_terms = [
        {
            "id": item["slug"],
            "zh": item["zh"],
            "en": item["en"],
            "aliases": item.get("aliases", []),
            "category": item["category"],
            "candidate_origin": "legacy-candidate",
        }
        for item in legacy
    ]
    raw_terms.extend(
        {
            "id": term_id,
            "zh": zh,
            "en": en,
            "aliases": [],
            "category": category,
            "candidate_origin": "design-spec",
        }
        for term_id, zh, en, category in BRIDGE_TERMS
    )

    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in raw_terms:
        item["topic"] = TOPIC_BY_CATEGORY[item.pop("category")]
        grouped[item["topic"]].append(item)

    terms = []
    for item in raw_terms:
        topic_terms = grouped[item["topic"]]
        index = topic_terms.index(item)
        next_ids = [topic_terms[index + 1]["id"]] if index + 1 < len(topic_terms) else []
        level = "basic" if item["id"] in BASIC_IDS else (
            "advanced" if item["topic"] in ADVANCED_TOPICS else "intermediate"
        )
        terms.append(
            {
                "id": item["id"],
                "zh": item["zh"],
                "en": item["en"],
                "aliases": item["aliases"],
                "type": term_type(item["id"]),
                "level": level,
                "topic": item["topic"],
                "status": "draft",
                "summary": f"用于理解和应用“{item['zh']}”的心理统计候选条目。",
                "relations": {
                    "prerequisites": [],
                    "components": [],
                    "contrasts": [],
                    "used_in": [],
                    "next": next_ids,
                },
                "candidate_origin": item["candidate_origin"],
            }
        )
    return {"schema_version": "2.0", "terms": terms}


def main() -> int:
    payload = build()
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"registry terms: {len(payload['terms'])} -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
