# -*- coding: utf-8 -*-
"""detectors.formula —— 公式/数学符号形式检测。

重要：公式页 ≠ OCR 错误。本 detector 只提高人工审核优先级，
输出 FORMULA_REQUIRES_HUMAN_VERIFICATION，不断言公式正确或错误。
"""
import re
import collections

from .base import make_result, clip, SEV_WATCH, SEV_REVIEW, CONF_HIGH, CONF_MED

NAME = "formula"

MATH_SYMBOLS = "Σ√±×÷≠≤≥≈→∈⊆∞∂∇∫∝∑∏"
GREEK = "αβγδεζηθικλμνξπρστυφχψωΑΒΓΔΘΛΞΠΣΦΨΩ"
RE_GREEK = re.compile("[" + GREEK + "]")
RE_SUP = re.compile(r"[A-Za-z\u4e00-\u9fff][²³¹⁰₀₁₂₃₄₅₆₇₈₉]|\^[A-Za-z0-9]")
RE_FRAC = re.compile(r"[A-Za-z0-9\)]\s*/\s*[A-Za-z0-9\(]")
RE_LABEL = re.compile(r"[（(]\s*\d{1,2}\s*[-—–]\s*\d{1,2}\s*[)）]")
RE_EQSTRUCT = re.compile(r"[A-Za-z\u4e00-\u9fff]\s*[=＝]\s*[A-Za-z0-9\u4e00-\u9fff]")
RE_VARSEQ = re.compile(r"\b[a-z]\d\b|\bX\d\b|\bY\d\b")
RE_MATRIX = re.compile(r"[\[\(]\s*[\d\.\s，,]{6,}[\]\)]")

SYM_DENSITY = 0.004
SYM_MIN = 3


def run(page_pdf, text, ctx):
    ev = []
    n = max(len(text), 1)
    sym = collections.Counter(c for c in text if c in MATH_SYMBOLS)
    sym_n = sum(sym.values())
    dens = sym_n / n
    if sym_n >= SYM_MIN or dens > SYM_DENSITY:
        ev.append("数学符号 %d 个, 密度 %.4f 例=%s" % (sym_n, dens, dict(list(sym.items())[:4])))

    greek = RE_GREEK.findall(text)
    if len(greek) >= 2:
        ev.append("希腊字母 %d 个 例=%s" % (len(greek), sorted(set(greek))[:6]))
    sup = RE_SUP.findall(text)
    if sup:
        ev.append("上下标候选 %d 处 例=%s" % (len(sup), sup[:4]))
    frac = RE_FRAC.findall(text)
    if frac:
        ev.append("分数/除式结构候选 %d 处 例=%s" % (len(frac), frac[:3]))
    label = RE_LABEL.findall(text)
    if label:
        ev.append("公式编号候选 %d 处 例=%s" % (len(label), label[:3]))
    eq = RE_EQSTRUCT.findall(text)
    if eq:
        ev.append("等式结构候选 %d 处 例=%s" % (len(eq), eq[:3]))
    varseq = RE_VARSEQ.findall(text)
    if len(varseq) >= 5:
        ev.append("连续变量模式(x1/x2/Y1) %d 处 例=%s" % (len(varseq), varseq[:4]))
    mat = RE_MATRIX.findall(text)
    if mat:
        ev.append("矩阵/向量结构候选 %d 处 例=%s" % (len(mat), [clip(x, 30) for x in mat[:2]]))

    triggered = bool(ev)
    sev = SEV_REVIEW if (sym_n >= SYM_MIN or mat or len(greek) >= 5) else SEV_WATCH
    conf = CONF_HIGH if (sym_n >= SYM_MIN or label) else CONF_MED
    reason = ("NO AUTOMATIC ANOMALY DETECTED（未发现公式形式特征；"
              "不代表该页无公式或公式正确）") if not triggered else \
             "FORMULA_REQUIRES_HUMAN_VERIFICATION：仅表明存在公式形式特征，" \
             "程序不判断公式是否被正确识别"
    return make_result(NAME, page_pdf, triggered, sev, conf, ev, reason)
