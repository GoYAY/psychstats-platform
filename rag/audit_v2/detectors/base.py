# -*- coding: utf-8 -*-
"""detectors.base —— 结果结构与常量。"""

SEV_NONE = "NONE"        # 未触发：NO AUTOMATIC ANOMALY DETECTED
SEV_WATCH = "WATCH"      # 形式特征值得留意
SEV_REVIEW = "REVIEW"    # 建议优先人工查看（仍是提示，不是错误判定）

CONF_HIGH = "HIGH_FORM_CONFIDENCE"
CONF_MED = "MEDIUM_FORM_CONFIDENCE"
CONF_LOW = "LOW_FORM_CONFIDENCE"

MAX_EVIDENCE = 6


def make_result(detector_name, page_pdf, triggered, severity_hint,
                confidence, evidence, reason):
    """evidence: list of str（已截断）；返回统一记录。"""
    ev = list(evidence)[:MAX_EVIDENCE]
    return {
        "page_pdf": page_pdf,
        "detector_name": detector_name,
        "triggered": bool(triggered),
        "severity_hint": severity_hint if triggered else SEV_NONE,
        "confidence": confidence if triggered else CONF_HIGH,
        "evidence": ev,
        "reason": reason,
    }


def clip(s, n=60):
    s = s.replace("\n", "\\n")
    return s if len(s) <= n else s[:n] + "…"
