# -*- coding: utf-8 -*-
"""detectors.repetition —— 重复文本检测（行/段/页片段/跨页重复）。

注意：重复可能是正常页眉、章节标题或教材结构，因此只输出 evidence，不判 OCR error。
"""
import collections

from .base import make_result, clip, SEV_WATCH, SEV_REVIEW, CONF_HIGH, CONF_MED

NAME = "repetition"

MIN_PARA = 20


def run(page_pdf, text, ctx):
    ev = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return make_result(NAME, page_pdf, False, SEV_WATCH, CONF_HIGH, [],
                           "空页：无重复形式特征")

    dup_lines = [(l, c) for l, c in collections.Counter(lines).items() if c >= 2 and len(l) >= 4]
    if dup_lines:
        ev.append("页内重复行 %d 类 例=%s" % (
            len(dup_lines), ["%s x%d" % (clip(l, 24), c) for l, c in dup_lines[:3]]))

    paras = [l for l in lines if len(l) >= MIN_PARA]
    dup_para = [(l, c) for l, c in collections.Counter(paras).items() if c >= 2]
    if dup_para:
        ev.append("页内重复长句(>=%d字) %d 类 例=%s" % (
            MIN_PARA, len(dup_para), ["%s x%d" % (clip(l, 28), c) for l, c in dup_para[:2]]))

    global_freq = ctx.get("line_freq", {})
    hot = [(l, global_freq.get(l, 0)) for l in set(lines)
           if global_freq.get(l, 0) >= 20 and len(l) >= 4]
    if hot:
        ev.append("全书高频行(>=20 次) %d 条 例=%s" % (
            len(hot), ["%s x%d" % (clip(l, 24), c) for l, c in hot[:3]]))

    prev = ctx.get("prev_page_lines")
    if prev:
        common = [l for l in set(lines) & set(prev) if len(l) >= 12]
        if len(common) >= 3:
            ev.append("与上一页重复长行 %d 条 例=%s" % (
                len(common), [clip(x, 24) for x in common[:3]]))

    blob = "".join(lines)
    dup_blocks = []
    for size in (120, 60):
        seen = set()
        for i in range(0, max(len(blob) - size, 0), 20):
            seg = blob[i:i + size]
            if seg in seen:
                dup_blocks.append(clip(seg, 40))
                break
            seen.add(seg)
        if dup_blocks:
            break
    if dup_blocks:
        ev.append("大段重复片段候选 例=%s" % dup_blocks[:2])

    triggered = bool(ev)
    sev = SEV_REVIEW if (dup_para or dup_blocks) else SEV_WATCH
    conf = CONF_HIGH if (dup_lines or hot) else CONF_MED
    reason = ("NO AUTOMATIC ANOMALY DETECTED（未发现重复形式特征）") if not triggered else \
             "重复形式特征：可能来自页眉/章节标题等正常结构，需人工区分，不直接判为 OCR 错误"
    return make_result(NAME, page_pdf, triggered, sev, conf, ev, reason)
