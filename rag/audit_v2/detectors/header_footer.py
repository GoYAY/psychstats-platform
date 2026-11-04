# -*- coding: utf-8 -*-
"""detectors.header_footer —— 页眉/页脚候选检测（高频首末行、页码模式、章名重复）。

输出 HEADER_FOOTER_CANDIDATE；本 detector 不删除、不修改任何文本。
"""
import re
import collections

from .base import make_result, clip, SEV_WATCH, SEV_REVIEW, CONF_HIGH, CONF_MED

NAME = "header_footer"

RE_PAGENUM = re.compile(r"^\s*/?\s*\d{1,3}\s*/?\s*$")
RE_PRINTED = re.compile(r"^\s*\d{1,3}\s*/\s*$|^\s*/\s*\d{1,3}\s*$")
RE_CHAP = re.compile(r"^第[一二三四五六七八九十百]+章")
RE_SEC = re.compile(r"^第[一二三四五六七八九十百]+节")
BOOKTITLE = "高级心理统计"


def run(page_pdf, text, ctx):
    ev = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return make_result(NAME, page_pdf, False, SEV_WATCH, CONF_HIGH, [], "空页")

    first, last = lines[0], lines[-1]
    first_freq = ctx.get("first_line_freq", {}).get(first, 0)
    last_freq = ctx.get("last_line_freq", {}).get(last, 0)
    line_freq = ctx.get("line_freq", {}).get(first, 0)

    if first_freq >= 5 or line_freq >= 20:
        ev.append("首行为高频行: '%s' (首行出现 %d 次 / 全书 %d 次)" % (
            clip(first, 30), first_freq, line_freq))
    if RE_CHAP.match(first) or RE_SEC.match(first):
        ev.append("首行为章/节标题: '%s'" % clip(first, 30))
    if first == BOOKTITLE:
        ev.append("首行为书名: '%s'" % BOOKTITLE)

    if RE_PAGENUM.match(last) or RE_PRINTED.match(last):
        ev.append("末行为页码模式: '%s'" % clip(last, 20))
    if last == BOOKTITLE:
        ev.append("末行为书名（疑似页脚）: '%s'" % BOOKTITLE)
    if last_freq >= 5:
        ev.append("末行为高频行: '%s' (%d 次)" % (clip(last, 30), last_freq))

    pn = [l for l in lines if RE_PAGENUM.match(l) or RE_PRINTED.match(l)]
    if pn:
        ev.append("页内页码样式行 %d 行 例=%s" % (len(pn), pn[:3]))
    bt = [l for l in lines if l == BOOKTITLE]
    if bt:
        ev.append("页内书名行 %d 行" % len(bt))

    triggered = bool(ev)
    sev = SEV_REVIEW if (len(pn) >= 2 or bt) else SEV_WATCH
    conf = CONF_HIGH if (first_freq >= 5 or pn or bt) else CONF_MED
    reason = ("NO AUTOMATIC ANOMALY DETECTED（未发现页眉页脚形式特征）") if not triggered else \
             "HEADER_FOOTER_CANDIDATE：仅提示可能混入正文；是否造成 chunk 污染需人工判断"
    return make_result(NAME, page_pdf, triggered, sev, conf, ev, reason)
