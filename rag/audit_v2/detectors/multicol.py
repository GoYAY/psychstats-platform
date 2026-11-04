# -*- coding: utf-8 -*-
"""detectors.multicol —— 多栏排版形式检测（短长行交错、列间隙、周期模式）。

输出 POSSIBLE_MULTICOLUMN —— 不是 MULTICOLUMN_ERROR；
阅读顺序是否正确只能由人工对照原书页判断。
"""
import re

from .base import make_result, clip, SEV_WATCH, SEV_REVIEW, CONF_HIGH, CONF_LOW

NAME = "multicol"

RE_GAP = re.compile(r"\S\s{3,}\S")
RE_DIGITONLY = re.compile(r"^[\d\s\.\-%,，]+$")
RE_TEXTY = re.compile(r"[\u4e00-\u9fff]{4,}")

SHORT_MAX = 12
LONG_MIN = 30


def run(page_pdf, text, ctx):
    ev = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    n = max(len(lines), 1)
    if n < 5:
        return make_result(NAME, page_pdf, False, SEV_WATCH, CONF_HIGH, [],
                           "行数过少，无法判断多栏形式")

    flags = [(len(l) <= SHORT_MAX, len(l) >= LONG_MIN) for l in lines]
    alt = 0
    for i in range(1, len(flags)):
        a, b = flags[i - 1], flags[i]
        if (a[0] and b[1]) or (a[1] and b[0]):
            alt += 1
    if alt / n > 0.25:
        ev.append("短行/长行交替比例 %.2f (%d/%d)" % (alt / n, alt, n))

    gaps = [l for l in lines if RE_GAP.search(l)]
    if len(gaps) >= 5:
        ev.append("含大间隙行(疑似左右列) %d 行 例=%s" % (
            len(gaps), [clip(x, 40) for x in gaps[:2]]))

    digit_lines = [l for l in lines if RE_DIGITONLY.match(l)]
    texty = [l for l in lines if RE_TEXTY.search(l)]
    if len(digit_lines) >= 5 and len(texty) >= 5:
        ev.append("纯数字行 %d 行与中文行 %d 行并存（疑似数字列+正文列）" % (
            len(digit_lines), len(texty)))

    lens = [len(l) for l in lines]
    period2 = sum(1 for i in range(2, len(lens))
                  if abs(lens[i] - lens[i - 2]) <= 3) / max(len(lens) - 2, 1)
    if period2 > 0.5:
        ev.append("行长度周期-2 相似度 %.2f（疑似双栏等宽）" % period2)

    triggered = bool(ev)
    sev = SEV_REVIEW if (len(gaps) >= 5 or period2 > 0.5) else SEV_WATCH
    conf = CONF_LOW if triggered else CONF_HIGH
    reason = ("NO AUTOMATIC ANOMALY DETECTED（未发现多栏形式特征）") if not triggered else \
             "POSSIBLE_MULTICOLUMN：仅为排版形式候选；" \
             "多栏阅读顺序是否正确 HUMAN VERIFICATION REQUIRED"
    return make_result(NAME, page_pdf, triggered, sev, conf, ev, reason)
