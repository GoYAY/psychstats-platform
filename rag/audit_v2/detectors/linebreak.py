# -*- coding: utf-8 -*-
"""detectors.linebreak —— 断行/换行结构形式检测。

只记录 POSSIBLE_OCR_LINE_BREAK_ERROR，不直接判错（教材本身也可能有短行）。
"""
import re

from .base import make_result, clip, SEV_WATCH, SEV_REVIEW, CONF_HIGH, CONF_MED

NAME = "linebreak"

RE_START_PUNCT = re.compile(r"^[，。；：、）】》”!？,.;)\]]")
RE_WORDSPLIT = re.compile(r"[A-Za-z]$")
RE_NEXTWORD = re.compile(r"^[A-Za-z]")
SENT_END = "。！？；.”）】!?;:"

SHORT_RATIO = 0.45
MICRO_RATIO = 0.12
NOEND_RATIO = 0.85


def run(page_pdf, text, ctx):
    ev = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    n = max(len(lines), 1)

    tiny = [l for l in lines if len(l) <= 2]
    short = [l for l in lines if len(l) <= 8]
    if len(short) / n > SHORT_RATIO:
        ev.append("短行比例 %.2f (%d/%d)" % (len(short) / n, len(short), n))
    if len(tiny) / n > MICRO_RATIO:
        ev.append("单/双字行比例 %.2f (%d/%d)" % (len(tiny) / n, len(tiny), n))

    micro_runs, cur = 0, 0
    for l in lines:
        if len(l) <= 3:
            cur += 1
            if cur >= 3:
                micro_runs += 1
        else:
            cur = 0
    if micro_runs:
        ev.append("连续超短行段(>=3 行) %d 段" % micro_runs)

    startp = [l for l in lines if RE_START_PUNCT.match(l)]
    if startp:
        ev.append("行首为标点（疑似断句位置） %d 行" % len(startp))

    noend = [l for l in lines if l[-1] not in SENT_END]
    if len(noend) / n > NOEND_RATIO:
        ev.append("非句末结尾行比例 %.2f (%d/%d)" % (len(noend) / n, len(noend), n))

    splits = []
    for i in range(len(lines) - 1):
        if RE_WORDSPLIT.search(lines[i][-1:]) and RE_NEXTWORD.match(lines[i + 1][:1]):
            splits.append(clip(lines[i][-12:] + "|" + lines[i + 1][:12], 30))
    if splits:
        ev.append("英文单词跨行断裂候选 %d 处 例=%s" % (len(splits), splits[:3]))

    triggered = bool(ev)
    sev = SEV_REVIEW if (splits or micro_runs or startp) else SEV_WATCH
    conf = CONF_MED if triggered else CONF_HIGH
    reason = ("NO AUTOMATIC ANOMALY DETECTED（断行形态未发现异常；"
              "不排除正常排版被误判或异常未被捕获）") if not triggered else \
             "POSSIBLE_OCR_LINE_BREAK_ERROR：仅为形式候选，正常教材排版同样可能产生"
    return make_result(NAME, page_pdf, triggered, sev, conf, ev, reason)
