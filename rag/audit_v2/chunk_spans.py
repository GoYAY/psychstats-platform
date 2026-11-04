# -*- coding: utf-8 -*-
"""audit_v2.chunk_spans —— 重建 chunk 在 OCR TXT 中的真实字符区间。

禁止使用 chunk['offset'] 作为来源位置（已证明不可信）。
定位顺序：EXACT(原始页文本) -> CLEANED_EXACT(清洗后) -> OVERLAP_PREFIX(去重叠前缀)
         -> AMBIGUOUS(同页多次) -> NOT_FOUND
"""
from .schema import (CHAP_RE, PAGENUM_RE, BOOKTITLE, MATCH_EXACT,
                     MATCH_CLEANED_EXACT, MATCH_OVERLAP_PREFIX,
                     MATCH_AMBIGUOUS, MATCH_NOT_FOUND, STATUS_BY_METHOD)


def clean_lines_with_offsets(txt, start, end):
    """复刻 build_index.clean_lines 的删除规则，但保留每行的原始字符区间。

    返回 [(raw_start, raw_end, stripped_text), ...]
    """
    out, skipping, pos = [], True, start
    while pos < end:
        nl = txt.find("\n", pos)
        line_end = end if (nl == -1 or nl > end) else nl
        line = txt[pos:line_end]
        s = line.strip()
        drop = False
        if not s:
            drop = True
        elif PAGENUM_RE.match(s):
            drop = True
        elif s == BOOKTITLE:
            drop = True
        elif skipping and CHAP_RE.match(s):
            drop = True
        if not drop:
            out.append((pos, line_end, s))
            skipping = False
        else:
            skipping = False
        pos = line_end + 1
    return out


class PageIndex(object):
    """一页的清洗文本 + joined位置 -> 原始偏移 映射。"""

    def __init__(self, txt, span):
        self.raw = txt
        self.span = span
        self.lines = clean_lines_with_offsets(txt, span["content_start"], span["content_end"])
        self.map = []
        p = 0
        for rs, re_, s in self.lines:
            self.map.append((p, p + len(s), rs, re_))
            p += len(s) + 1
        self.joined = "\n".join(s for _, _, s in self.lines)

    def to_raw(self, jpos):
        for js, je, rs, re_ in self.map:
            if js <= jpos <= je:
                return rs + (jpos - js)
        return None

    def span_of(self, jstart, jend):
        a = self.to_raw(jstart)
        b = self.to_raw(jend - 1)
        if a is None or b is None:
            return None, None
        return a, b + 1


def locate_chunk(chunk_text, pidx, page_txt, overlap):
    """返回 dict(method, start, end, occurrences, prefix_len, note)。坐标为绝对字符位置。"""
    cs, ce = pidx.span["content_start"], pidx.span["content_end"]

    # 1) EXACT：原始页文本逐字命中
    occ_raw = page_txt.count(chunk_text)
    if occ_raw == 1:
        p = page_txt.find(chunk_text)
        return {"method": MATCH_EXACT, "start": cs + p, "end": cs + p + len(chunk_text),
                "occurrences": 1, "prefix_len": 0, "note": "raw page text verbatim"}
    if occ_raw > 1:
        return {"method": MATCH_AMBIGUOUS, "start": None, "end": None,
                "occurrences": occ_raw, "prefix_len": 0,
                "note": "multiple occurrences in raw page text"}

    # 2) CLEANED_EXACT
    occ = pidx.joined.count(chunk_text)
    if occ == 1:
        p = pidx.joined.find(chunk_text)
        a, b = pidx.span_of(p, p + len(chunk_text))
        return {"method": MATCH_CLEANED_EXACT, "start": a, "end": b,
                "occurrences": 1, "prefix_len": 0,
                "note": "matched after removing page-number/booktitle/header lines"}
    if occ > 1:
        return {"method": MATCH_AMBIGUOUS, "start": None, "end": None,
                "occurrences": occ, "prefix_len": 0,
                "note": "multiple occurrences in cleaned page text"}

    # 3) OVERLAP_PREFIX：去掉人工拼接的前缀后命中
    cand = None
    ks = [overlap] + [k for k in range(1, min(400, len(chunk_text)))]
    for k in ks:
        core = chunk_text[k:]
        if not core:
            break
        o = pidx.joined.count(core)
        if o == 1:
            p = pidx.joined.find(core)
            if p != 0 and pidx.joined[p - 1] != "\n":
                continue       # 必须落在行边界
            a, b = pidx.span_of(p, p + len(core))
            cand = {"method": MATCH_OVERLAP_PREFIX, "start": a, "end": b,
                    "occurrences": 1, "prefix_len": k,
                    "note": "leading %d chars are overlap copied from previous chunk" % k}
            break
        if o > 1:
            cand = {"method": MATCH_AMBIGUOUS, "start": None, "end": None,
                    "occurrences": o, "prefix_len": k,
                    "note": "core occurs %d times in cleaned page text" % o}
            break
    if cand:
        return cand

    return {"method": MATCH_NOT_FOUND, "start": None, "end": None,
            "occurrences": 0, "prefix_len": 0, "note": "no match in this page"}
