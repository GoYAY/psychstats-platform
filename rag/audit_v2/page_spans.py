# -*- coding: utf-8 -*-
"""audit_v2.page_spans —— 用页标记重建每一页在 OCR TXT 中的真实字符区间。

输出字段：page_pdf / marker_start / marker_end / content_start / content_end
校验：页数、连续性、无重复、无缺失、区间不重叠。
"""
from .schema import PAGE_MARKER_RE


def build_page_spans(txt):
    marks = [(m.start(), m.end(), int(m.group(1)))
             for m in PAGE_MARKER_RE.finditer(txt)]
    spans = []
    for i, (s, e, n) in enumerate(marks):
        content_start = e
        content_end = marks[i + 1][0] if i + 1 < len(marks) else len(txt)
        spans.append({
            "page_pdf": n,
            "marker_start": s,
            "marker_end": e,
            "content_start": content_start,
            "content_end": content_end,
            "n_chars": content_end - content_start,
            "n_lines": txt.count("\n", content_start, content_end),
        })
    return spans


def validate_page_spans(spans, expected_pages=None):
    """返回 (issues, stats)。issues 为空表示结构校验通过。"""
    issues = []
    nums = [s["page_pdf"] for s in spans]
    if len(set(nums)) != len(nums):
        dup = sorted(n for n in set(nums) if nums.count(n) > 1)
        issues.append("重复页号: %s" % dup[:20])
    if nums:
        missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
        if missing:
            issues.append("缺失页号: %s" % missing[:20])
        if nums != list(range(1, max(nums) + 1)):
            issues.append("页号顺序非 1..N 连续递增")
    if expected_pages is not None and len(spans) != expected_pages:
        issues.append("页数与 PDF 页数不一致: OCR=%d PDF=%d" % (len(spans), expected_pages))
    for i in range(len(spans) - 1):
        if spans[i]["content_end"] > spans[i + 1]["marker_start"]:
            issues.append("页区间重叠/错位: page %d" % spans[i]["page_pdf"])
    if any(s["n_chars"] <= 0 for s in spans):
        issues.append("存在空页(内容长度为 0): %s" %
                      [s["page_pdf"] for s in spans if s["n_chars"] <= 0][:20])
    stats = {
        "n_pages": len(spans),
        "min_page": min(nums) if nums else None,
        "max_page": max(nums) if nums else None,
        "unique_pages": len(set(nums)),
        "empty_pages": sum(1 for s in spans if s["n_chars"] <= 0),
        "total_content_chars": sum(s["n_chars"] for s in spans),
    }
    return issues, stats
