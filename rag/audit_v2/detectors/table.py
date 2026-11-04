# -*- coding: utf-8 -*-
"""detectors.table —— 表格形式检测（列间隙 / 数字列 / 重复列结构 / 表头候选）。

输出 TABLE_PRESENT（有表题 + 结构证据）或 TABLE_SUSPECTED（仅结构证据）。
不判断表格内容是否被正确识别。
"""
import re

from .base import make_result, clip, SEV_WATCH, SEV_REVIEW, CONF_HIGH, CONF_MED

NAME = "table"

RE_GAP = re.compile(r"\S\s{2,}\S")
RE_CAPTION = re.compile(r"表\s*\d{1,2}\s*[-—–]\s*\d{1,2}|表\s*\d{1,2}")
RE_NUMLINE = re.compile(r"(?m)^[^\n]*\d[^\n]*$")
RE_SHORT = re.compile(r"(?m)^\s*.{1,8}$")

MIN_GAP_LINES = 3
MIN_COL_LINES = 4


def _tokens(line):
    return [t for t in re.split(r"\s{2,}", line.strip()) if t]


def run(page_pdf, text, ctx):
    ev = []
    lines = [l for l in text.split("\n")]
    nonblank = [l for l in lines if l.strip()]
    if not nonblank:
        return make_result(NAME, page_pdf, False, SEV_WATCH, CONF_HIGH, [],
                           "空页：无表格形式特征")

    gap_lines = [l for l in nonblank if RE_GAP.search(l)]
    if len(gap_lines) >= MIN_GAP_LINES:
        ev.append("多列空白对齐行 %d 行 例=%s" % (
            len(gap_lines), [clip(x, 40) for x in gap_lines[:3]]))

    tok_counts = []
    for l in nonblank:
        t = _tokens(l)
        if len(t) >= 2:
            tok_counts.append(len(t))
    runs = 0
    cur = 1
    for i in range(1, len(tok_counts)):
        if tok_counts[i] == tok_counts[i - 1]:
            cur += 1
        else:
            if cur >= MIN_COL_LINES:
                runs += 1
            cur = 1
    if cur >= MIN_COL_LINES:
        runs += 1
    if runs:
        ev.append("重复列结构段 %d 段（>=%d 行同列数）" % (runs, MIN_COL_LINES))

    num_cols = [l for l in nonblank if len(re.findall(r"\d+", l)) >= 3]
    if len(num_cols) >= MIN_COL_LINES:
        ev.append("数字列候选 %d 行 例=%s" % (
            len(num_cols), [clip(x, 40) for x in num_cols[:3]]))

    short_runs = [l for l in nonblank if len(l.strip()) <= 8]
    if len(short_runs) >= 8:
        ev.append("短文本横向排列候选: 超短行 %d 行" % len(short_runs))

    caps = RE_CAPTION.findall(text)
    present = bool(caps) and bool(ev)
    if caps:
        ev.append("表题候选 %d 处 例=%s" % (len(caps), caps[:3]))

    lens = [len(l.strip()) for l in nonblank]
    if len(lens) >= 6:
        same = sum(1 for i in range(1, len(lens)) if abs(lens[i] - lens[i - 1]) <= 2)
        if same >= 5:
            ev.append("行长度周期性: %d 对相邻行长度差<=2" % same)

    triggered = bool(ev)
    sev = SEV_REVIEW if present else SEV_WATCH
    conf = CONF_HIGH if present else CONF_MED
    if not triggered:
        reason = "NO AUTOMATIC ANOMALY DETECTED（未发现表格形式特征）"
    elif present:
        reason = "TABLE_PRESENT：存在表题与列结构形式特征；表格行列归属需人工核对"
    else:
        reason = "TABLE_SUSPECTED：仅有结构形式特征，未发现表题；需人工确认是否为表格"
    return make_result(NAME, page_pdf, triggered, sev, conf, ev, reason)
