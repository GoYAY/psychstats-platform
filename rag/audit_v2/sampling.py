# -*- coding: utf-8 -*-
"""audit_v2.sampling —— 分层抽样（只服务于人工 Ground Truth 与后续 detector 校准）。

禁止用途：抽样结果不得被解释为「全书 OCR 正确」的任何证据。
本模块只读：detector_page_evidence.csv + OCR TXT（用于内容分层）。
"""
import csv
import json
import random
import collections
import re

from .schema import RANDOM_SEED

DETECTORS = ["character", "number", "formula", "table",
             "linebreak", "repetition", "header_footer", "multicol"]

N_PER_DETECTOR_POS = 10
N_DETECTOR_NEGATIVE = 25        # 严格负样本（8/8 未触发）目标
N_PER_DETECTOR_NEG = 5          # 每个 detector 的未触发页补充（用于测 FN）
N_LOW_SIGNAL = 25               # 触发数 <= LOW_SIGNAL_MAX 的页
LOW_SIGNAL_MAX = 2
N_RANDOM = 25
N_PER_CONTENT = 8

RE_FIG = re.compile(r"图\s*\d{1,2}\s*[-—–]\s*\d{1,2}|图\s*\d{1,2}")
RE_TABCAP = re.compile(r"表\s*\d{1,2}\s*[-—–]\s*\d{1,2}")
RE_HEAD = re.compile(r"(?m)^\s*第[一二三四五六七八九十百]+[章节]|(?:^|\s)[一二三四五六七八九十]+、")
CJK = re.compile(r"[\u4e00-\u9fff]")
MATH_SYMBOLS = "Σ√±×÷≠≤≥≈→∈⊆∞∑∏"
GREEK = "αβγδεζηθικλμνξπρστυφχψω"


def load_evidence(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def page_index(rows):
    """{page_pdf: {detector: {"triggered":bool,"severity":str,"confidence":str}}}"""
    idx = collections.defaultdict(dict)
    for r in rows:
        idx[int(r["page_pdf"])][r["detector_name"]] = {
            "triggered": r["triggered"] == "True",
            "severity": r["severity_hint"],
            "confidence": r["confidence"],
        }
    return idx


def content_tags(text):
    """内容分层标签（只用于抽样，不能作为 OCR 正确性判断）。"""
    tags = []
    n = max(len(text), 1)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    digit_ratio = sum(c.isdigit() for c in text) / n
    cjk_ratio = len(CJK.findall(text)) / n
    sym = sum(1 for c in text if c in MATH_SYMBOLS)
    greek = sum(1 for c in text if c in GREEK)

    if RE_FIG.search(text):
        tags.append("content_figure_caption")
    gap_lines = sum(1 for l in lines if re.search(r"\S\s{2,}\S", l))
    num_cols = sum(1 for l in lines if len(re.findall(r"\d+", l)) >= 3)
    if RE_TABCAP.search(text) or (gap_lines >= 3 and num_cols >= 3):
        tags.append("content_table_like")
    if sym >= 3 or greek >= 2:
        tags.append("content_formula_heavy")
    if digit_ratio > 0.12:
        tags.append("content_numeric_heavy")
    if len(RE_HEAD.findall(text)) >= 2 and len(lines) <= 25:
        tags.append("content_heading_heavy")
    if cjk_ratio > 0.45 and len(lines) >= 8 and not tags:
        tags.append("content_prose")
    return tags or ["content_other"]


def _pick(pool, n, rng):
    pool = sorted(set(pool))
    if len(pool) <= n:
        return pool
    return sorted(rng.sample(pool, n))


def build_plan(idx, page_texts, seed=RANDOM_SEED):
    """返回 {page_pdf: {"reasons":[...], "strata":[...], "triggers":{...}}}"""
    rng = random.Random(seed)
    pages = sorted(idx.keys())
    reasons = collections.defaultdict(list)
    strata = collections.defaultdict(list)

    def add(page, stratum, reason):
        if stratum not in strata[page]:
            strata[page].append(stratum)
        if reason not in reasons[page]:
            reasons[page].append(reason)

    # A. detector-positive
    for det in DETECTORS:
        pool = [p for p in pages if idx[p].get(det, {}).get("triggered")]
        picked = _pick(pool, N_PER_DETECTOR_POS, rng)
        for p in picked:
            add(p, "detector_positive", "%s_positive" % det)

    # B. detector-negative（严格：8/8 未触发）
    strict_neg = [p for p in pages
                  if not any(idx[p].get(d, {}).get("triggered") for d in DETECTORS)]
    for p in _pick(strict_neg, N_DETECTOR_NEGATIVE, rng):
        add(p, "detector_negative_strict", "all_detectors_negative")

    # B2. per-detector negative（补充，用于估计该 detector 的 FN）
    for det in DETECTORS:
        pool = [p for p in pages if not idx[p].get(det, {}).get("triggered")]
        for p in _pick(pool, N_PER_DETECTOR_NEG, rng):
            add(p, "detector_negative_per_detector", "%s_negative" % det)

    # B3. low-signal pages
    low = [p for p in pages
           if sum(1 for d in DETECTORS if idx[p].get(d, {}).get("triggered")) <= LOW_SIGNAL_MAX]
    for p in _pick(low, N_LOW_SIGNAL, rng):
        add(p, "detector_low_signal", "triggered_count<=%d" % LOW_SIGNAL_MAX)

    # C. content-stratified
    by_tag = collections.defaultdict(list)
    for p in pages:
        for t in content_tags(page_texts.get(p, "")):
            by_tag[t].append(p)
    for tag in sorted(by_tag):
        for p in _pick(by_tag[tag], N_PER_CONTENT, rng):
            add(p, "content_stratified", tag)

    # D. random baseline
    for p in _pick(pages, N_RANDOM, rng):
        add(p, "random_baseline", "random")

    plan = {}
    for p in sorted(reasons):
        trig = {d: bool(idx[p].get(d, {}).get("triggered")) for d in DETECTORS}
        n_trig = sum(trig.values())
        sev_review = any(idx[p].get(d, {}).get("severity") == "REVIEW" for d in DETECTORS)
        if any(r.endswith("_positive") for r in reasons[p]):
            pri = "P1"
        elif "all_detectors_negative" in reasons[p]:
            pri = "P2"
        elif any(r.endswith("_negative") for r in reasons[p]) or \
                "triggered_count<=%d" % LOW_SIGNAL_MAX in reasons[p]:
            pri = "P2"
        else:
            pri = "P3"
        plan[p] = {
            "page_pdf": p,
            "sampling_strata": ";".join(sorted(strata[p])),
            "sampling_reasons": json.dumps(reasons[p], ensure_ascii=False),
            "detector_triggers": json.dumps(trig, ensure_ascii=False),
            "triggered_count": n_trig,
            "has_review_severity": sev_review,
            "priority": pri,
            "random_seed": seed,
        }
    return plan, {
        "strict_negative_pool": len(strict_neg),
        "low_signal_pool": len(low),
        "content_pools": {k: len(v) for k, v in sorted(by_tag.items())},
    }
