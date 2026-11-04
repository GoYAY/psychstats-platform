# -*- coding: utf-8 -*-
"""audit_v2.groundtruth —— 人工 Ground Truth 模板与校验（程序只生成待填模板）。

铁律：
  * GT 只能由人工对照原 PDF 页填写，程序不得自动生成 error_present / error_type / severity
  * 三种情形必须区分：OCR ERROR / NORMAL_LAYOUT / SOURCE_ISSUE
  * CRITICAL 仅用于「含义被改变」的错误，不允许因排版观感判定
"""
import csv

ERROR_TYPES = ["NONE", "CHARACTER", "NUMBER", "FORMULA", "TABLE",
               "HEADER_FOOTER", "LINE_BREAK", "MULTI_COLUMN",
               "MISSING_TEXT", "EXTRA_TEXT", "WRONG_ORDER", "OTHER"]

SEVERITIES = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

GT_FIELDS = ["page_pdf", "human_verified", "error_present", "error_type",
             "severity", "description", "pdf_location", "ocr_location",
             "correct_text", "reviewer", "reviewed_at", "notes"]

NOTE_FLAGS = ["NORMAL_LAYOUT", "SOURCE_ISSUE"]


def empty_row(page_pdf):
    return {"page_pdf": page_pdf, "human_verified": 0, "error_present": "",
            "error_type": "", "severity": "", "description": "",
            "pdf_location": "", "ocr_location": "", "correct_text": "",
            "reviewer": "", "reviewed_at": "", "notes": ""}


def write_template(path, page_list):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=GT_FIELDS)
        w.writeheader()
        for p in page_list:
            w.writerow(empty_row(p))


def validate_rows(rows):
    """校验已填写的 GT（人工填完后自检用；不修改数据）。"""
    issues = []
    for r in rows:
        p = r.get("page_pdf")
        if str(r.get("human_verified")) not in ("0", "1"):
            issues.append("page %s: human_verified 必须为 0/1" % p)
            continue
        if str(r.get("human_verified")) == "0":
            continue
        ep = str(r.get("error_present", "")).strip()
        if ep not in ("0", "1"):
            issues.append("page %s: error_present 必须为 0/1" % p)
            continue
        et = (r.get("error_type") or "").strip()
        sv = (r.get("severity") or "").strip()
        if et not in ERROR_TYPES:
            issues.append("page %s: error_type 非法 %r" % (p, et))
        if sv not in SEVERITIES:
            issues.append("page %s: severity 非法 %r" % (p, sv))
        if ep == "0" and et != "NONE":
            issues.append("page %s: error_present=0 时 error_type 应为 NONE" % p)
        if ep == "1" and et == "NONE":
            issues.append("page %s: error_present=1 时 error_type 不能为 NONE" % p)
        if sv == "CRITICAL" and ep != "1":
            issues.append("page %s: CRITICAL 只能用于 error_present=1" % p)
        if ep == "0" and not any(f in (r.get("notes") or "") for f in NOTE_FLAGS):
            issues.append("page %s: error_present=0 时 notes 建议标注 "
                          "NORMAL_LAYOUT 或 SOURCE_ISSUE" % p)
    return issues


def build_calibration_frame(gt_rows, evidence_rows, detectors):
    """把人工 GT 与 detector 证据关联，供【后续】计算 TP/FP/FN/TN。
    本函数在本阶段【不调用】：不执行 calibration，不输出任何指标。
    """
    ev = {(int(r["page_pdf"]), r["detector_name"]): r["triggered"] == "True"
          for r in evidence_rows}
    out = []
    for g in gt_rows:
        if str(g.get("human_verified")) != "1":
            continue
        p = int(g["page_pdf"])
        err = str(g.get("error_present")) == "1"
        for d in detectors:
            out.append({"page_pdf": p, "detector_name": d,
                        "detector_triggered": ev.get((p, d)),
                        "error_present": err,
                        "error_type": (g.get("error_type") or "").strip(),
                        "severity": g.get("severity", "")})
    return out
