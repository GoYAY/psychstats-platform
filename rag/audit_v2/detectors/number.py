# -*- coding: utf-8 -*-
"""detectors.number —— 数字层形式异常检测（数字密集 / 小数 / 百分号 / 符号粘连 / 统计量候选）。

只输出形式证据，不判断原书数值真值。
"""
import re
import collections

from .base import make_result, SEV_WATCH, SEV_REVIEW, CONF_HIGH, CONF_MED

NAME = "number"

RE_DECIMAL = re.compile(r"\d+\.\d+")
RE_PCT = re.compile(r"\d+%|%\s*\d")
RE_LONGDIGIT = re.compile(r"\d{6,}")
RE_YEAR = re.compile(r"(19|20)\d{2}")
RE_PAGE = re.compile(r"(?m)^\s*/?\s*\d{1,3}\s*/?\s*$")
RE_SIGN_GLUE = re.compile(r"[土士一十]\s*\d")
RE_CJK_DIGIT = re.compile(r"[\u4e00-\u9fff]\d|\d[\u4e00-\u9fff]")
RE_SPACE_AROUND = re.compile(r"\d\s{2,}\d|\d\s+\.")
RE_STAT = re.compile(r"\b(p|t|F|df|r|R|z|Z|β|α)\s*[=<>≤≥]\s*[\d\.\-]|χ2|χ²|R2|R²|SD|SE\b")

DENSE_RATIO = 0.12
DENSE_COUNT = 150


def run(page_pdf, text, ctx):
    ev = []
    n = max(len(text), 1)
    digits = sum(c.isdigit() for c in text)
    ratio = digits / n
    if ratio > DENSE_RATIO or digits > DENSE_COUNT:
        ev.append("数字密集: %d 个数字, 占比 %.3f" % (digits, ratio))

    dec = RE_DECIMAL.findall(text)
    if len(dec) >= 10:
        ev.append("小数 %d 处 例=%s" % (len(dec), dec[:4]))
    pct = RE_PCT.findall(text)
    if pct:
        ev.append("百分号 %d 处 例=%s" % (len(pct), pct[:3]))
    longd = RE_LONGDIGIT.findall(text)
    if longd:
        ev.append("连续数字>=6位 %d 处 例=%s" % (len(longd), longd[:3]))
    years = RE_YEAR.findall(text)
    if len(years) >= 3:
        ev.append("年份样式数字 %d 处" % len(years))
    pageno = RE_PAGE.findall(text)
    if pageno:
        ev.append("疑似页码残留行 %d 行 例=%s" % (len(pageno), pageno[:3]))

    sign = RE_SIGN_GLUE.findall(text)
    if sign:
        ev.append("符号粘连候选(土/士/一/十+数字) %d 处" % len(sign))
    cjkd = RE_CJK_DIGIT.findall(text)
    if len(cjkd) > 30:
        ev.append("汉字-数字直接粘连 %d 处（中文排版常见，低置信）" % len(cjkd))
    sp = RE_SPACE_AROUND.findall(text)
    if sp:
        ev.append("数字周围异常空格 %d 处 例=%s" % (len(sp), [clip2(x) for x in sp[:3]]))
    stat = RE_STAT.findall(text)
    if stat:
        ev.append("统计量样式候选 %d 处 例=%s" % (len(stat), stat[:4]))

    triggered = bool(ev)
    sev = SEV_REVIEW if (sign or sp or longd) else SEV_WATCH
    conf = CONF_HIGH if (ratio > DENSE_RATIO or dec or pct) else CONF_MED
    reason = ("NO AUTOMATIC ANOMALY DETECTED（数字层未发现可疑形式；"
              "数字是否被正确识别仍需人工核对）") if not triggered else \
             "数字层形式候选：数值真值未经核对，HUMAN VERIFICATION REQUIRED"
    return make_result(NAME, page_pdf, triggered, sev, conf, ev, reason)


def clip2(s):
    return repr(s)[:24]
