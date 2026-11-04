# -*- coding: utf-8 -*-
"""detectors.character —— 字符层形式异常检测（U+FFFD / 控制字符 / 异常 Unicode / 替换模式）。"""
import re
import unicodedata
import collections

from .base import make_result, clip, SEV_WATCH, SEV_REVIEW, CONF_HIGH, CONF_MED

NAME = "character"

# 已知 OCR 疑似替换模式（形式候选，非真值判断）
SUBST_PATTERNS = [
    ("一+数字(= 候选)", re.compile(r"一\s*\d")),
    ("十+数字(+ 候选)", re.compile(r"十\s*\d")),
    ("土/士+数字(± 候选)", re.compile(r"[土士]\s*\d")),
    ("单字力(p 候选)", re.compile(r"(?<![动力压力用力人力])力(?![气力量场学])")),
    ("全角冒号 URL", re.compile(r"https?：")),
    ("斜杠被识别为7", re.compile(r"https?：7")),
]

NON_TEXT_SCRIPTS = (
    "CYRILLIC", "HANGUL", "HIRAGANA", "KATAKANA", "ARABIC", "THAI", "HEBREW",
    "DEVANAGARI", "BOPOMOFO", "DINGBAT", "ENCLOSED", "SMALL FORM",
    "COMPATIBILITY", "BRAILLE", "RUNIC", "GEORGIAN", "ARMENIAN", "LAO",
    "KHMER", "MYANMAR", "TIBETAN", "MONGOLIAN", "ETHIOPIC", "MUSICAL",
)
RARE_CATEGORIES = ("Co", "Cs", "Cn", "Cf")


def is_rare_char(c):
    """只把「非本书语言体系的文字/未命名/专用区」视为罕见；
    数字、标点、数学符号不计入（由其他 detector 负责）。"""
    if c.isspace():
        return False
    if unicodedata.category(c) in RARE_CATEGORIES:
        return True
    if c.isalpha():
        nm = unicodedata.name(c, "")
        return any(b in nm for b in NON_TEXT_SCRIPTS)
    nm = unicodedata.name(c, "")
    if not nm:
        return True
    return any(b in nm for b in NON_TEXT_SCRIPTS)


def run(page_pdf, text, ctx):
    ev = []
    n = len(text)
    fffd = text.count("\ufffd")
    if fffd:
        ev.append("U+FFFD 替换字符 x%d" % fffd)
    ctrl = collections.Counter(c for c in text if ord(c) < 32 and c not in "\n\r\t")
    if ctrl:
        ev.append("控制字符 %s" % dict(list(ctrl.items())[:3]))
    priv = sum(1 for c in text if 0xE000 <= ord(c) <= 0xF8FF)
    if priv:
        ev.append("私有区字符 x%d" % priv)

    rare = collections.Counter()
    for c in text:
        o = ord(c)
        if 0x2190 <= o <= 0x2BFF:
            continue                      # 数学/箭头符号，交给 formula detector
        if is_rare_char(c):
            rare[c] += 1
    rare_n = sum(rare.values())
    rare_ratio = rare_n / max(n, 1)
    if rare_ratio > 0.002:
        ev.append("罕见字符比例 %.4f 例=%s" % (
            rare_ratio, [("%s x%d" % (c, k)) for c, k in rare.most_common(3)]))

    subst_hits = []
    for label, pat in SUBST_PATTERNS:
        m = pat.findall(text)
        if m:
            subst_hits.append("%s x%d" % (label, len(m)))
    if subst_hits:
        ev.append("疑似替换模式: " + "; ".join(subst_hits))

    triggered = bool(ev)
    sev = SEV_REVIEW if (fffd or ctrl or priv or rare_ratio > 0.01) else SEV_WATCH
    conf = CONF_HIGH if (fffd or ctrl or priv) else CONF_MED
    reason = ("NO AUTOMATIC ANOMALY DETECTED（字符层未发现形式异常；"
              "不等价于 OCR 正确）") if not triggered else \
             "字符层形式异常：上述模式仅为候选，需人工对照原书确认"
    return make_result(NAME, page_pdf, triggered, sev, conf, ev, reason)
