# -*- coding: utf-8 -*-
"""audit_v2.run_detectors —— Phase B：Detector Evidence Layer（只读）。

产出：
  audit_v2_out/detector_page_evidence.csv   433 页 × 8 detector = 3464 条
  audit_v2_out/detector_summary.md
  audit_v2_out/detector_run_meta.json

本层不产生 risk score / PASS-FAIL / OCR accuracy；只记录形式特征证据。
"""
import os
import sys
import csv
import json
import hashlib
import datetime
import collections
import platform
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from audit_v2 import loaders, page_spans as ps_mod  # noqa: E402
from audit_v2.schema import SCHEMA_VERSION, AUDIT_VERSION  # noqa: E402
from audit_v2.detectors import (character, number, formula, table,  # noqa: E402
                                linebreak, repetition, header_footer, multicol)

DETECTOR_VERSION = "1.0"
DETECTORS = [character, number, formula, table,
             linebreak, repetition, header_footer, multicol]

PARAMS = {
    "number.DENSE_RATIO": number.DENSE_RATIO,
    "number.DENSE_COUNT": number.DENSE_COUNT,
    "formula.SYM_MIN": formula.SYM_MIN,
    "formula.SYM_DENSITY": formula.SYM_DENSITY,
    "table.MIN_GAP_LINES": table.MIN_GAP_LINES,
    "table.MIN_COL_LINES": table.MIN_COL_LINES,
    "linebreak.SHORT_RATIO": linebreak.SHORT_RATIO,
    "linebreak.MICRO_RATIO": linebreak.MICRO_RATIO,
    "linebreak.NOEND_RATIO": linebreak.NOEND_RATIO,
    "multicol.SHORT_MAX": multicol.SHORT_MAX,
    "multicol.LONG_MIN": multicol.LONG_MIN,
    "repetition.MIN_PARA": repetition.MIN_PARA,
    "base.MAX_EVIDENCE": 6,
}


def find_pdf(root):
    pdfs = [x for x in os.listdir(root) if x.lower().endswith(".pdf")]
    return os.path.join(root, pdfs[0]) if pdfs else None


def build_context(txt, spans):
    """全书层面的确定性统计（供 repetition / header_footer 使用）。"""
    line_freq = collections.Counter()
    first_freq = collections.Counter()
    last_freq = collections.Counter()
    page_lines = {}
    for s in spans:
        body = txt[s["content_start"]:s["content_end"]]
        lines = [l.strip() for l in body.split("\n") if l.strip()]
        page_lines[s["page_pdf"]] = lines
        for l in lines:
            line_freq[l] += 1
        if lines:
            first_freq[lines[0]] += 1
            last_freq[lines[-1]] += 1
    return {"line_freq": line_freq, "first_line_freq": first_freq,
            "last_line_freq": last_freq, "page_lines": page_lines}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=None)
    args = ap.parse_args()

    txt, d, meta = loaders.load_all()
    spans = ps_mod.build_page_spans(txt)
    ctx = build_context(txt, spans)

    root = os.path.dirname(os.path.dirname(HERE))
    pdf = args.pdf or find_pdf(root)
    pdf_sha = None
    if pdf and os.path.exists(pdf):
        h = hashlib.sha256()
        with open(pdf, "rb") as f:
            while True:
                b = f.read(1 << 20)
                if not b:
                    break
                h.update(b)
        pdf_sha = h.hexdigest()

    rows = []
    per_detector = collections.defaultdict(lambda: {"triggered": 0, "examples": []})
    for s in spans:
        body = txt[s["content_start"]:s["content_end"]]
        p = s["page_pdf"]
        ctx["prev_page_lines"] = ctx["page_lines"].get(p - 1)
        for det in DETECTORS:
            r = det.run(p, body, ctx)
            rows.append({
                "page_pdf": r["page_pdf"],
                "detector_name": r["detector_name"],
                "triggered": r["triggered"],
                "severity_hint": r["severity_hint"],
                "confidence": r["confidence"],
                "evidence_json": json.dumps(r["evidence"], ensure_ascii=False),
                "reason": r["reason"],
            })
            if r["triggered"]:
                per_detector[r["detector_name"]]["triggered"] += 1
                ex = per_detector[r["detector_name"]]["examples"]
                if len(ex) < 3:
                    ex.append((p, r["evidence"][:2], r["severity_hint"]))

    outdir = loaders.OUT_DIR
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "detector_page_evidence.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    run_meta = {
        "schema_version": SCHEMA_VERSION,
        "audit_version": AUDIT_VERSION,
        "detector_version": DETECTOR_VERSION,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "python_version": platform.python_version(),
        "src_sha256": meta["src_sha256"],
        "index_sha256": meta["index_sha256"],
        "pdf_path": pdf,
        "pdf_sha256": pdf_sha,
        "n_pages": len(spans),
        "n_detectors": len(DETECTORS),
        "n_records": len(rows),
        "detector_parameters": PARAMS,
        "trigger_counts": {k: v["triggered"] for k, v in per_detector.items()},
        "independence_note": "detectors 仅使用 OCR TXT 形式特征；"
                            "未使用 embedding/retrieval/chunk metadata/LLM",
    }
    loaders.write_json(os.path.join(outdir, "detector_run_meta.json"), run_meta)

    L = []
    L.append("# Detector Summary (audit_v2 Phase B)\n\n")
    L.append("只记录**形式特征证据**；不产生 risk score，不判断 OCR 正确性。\n\n")
    L.append("| detector | 触发页数 | 占 433 页 |\n|---|---|---|\n")
    for det in DETECTORS:
        t = per_detector[det.NAME]["triggered"]
        L.append("| %s | %d | %.1f%% |\n" % (det.NAME, t, 100.0 * t / len(spans)))
    L.append("\n记录总数：%d（%d 页 × %d detector）\n\n"
             % (len(rows), len(spans), len(DETECTORS)))
    for det in DETECTORS:
        L.append("\n## %s\n" % det.NAME)
        for p, ev, sev in per_detector[det.NAME]["examples"]:
            L.append("- page %d [%s] %s\n" % (p, sev, ev))
    per_page = collections.Counter()
    review_pages = collections.Counter()
    for r in rows:
        if r["triggered"]:
            per_page[r["page_pdf"]] += 1
        if r["severity_hint"] == "REVIEW":
            review_pages[r["page_pdf"]] += 1

    L.append("\n---\n\n# Detector 结论与边界（人工阅读部分）\n\n")
    L.append("## 1. 是否全部页完成扫描\n")
    L.append("- 页标记解析 %d 页，逐页执行 %d 个 detector，记录 %d 条 = %d×%d → **全部完成**\n"
             % (len(spans), len(DETECTORS), len(rows), len(spans), len(DETECTORS)))
    L.append("- 未触发的 detector 同样写入记录（`triggered=false`），未做省略\n\n")

    L.append("## 2. 每个 detector 触发页数\n见上表。触发数高只说明「形式特征普遍」，"
             "**不说明错误普遍**。\n\n")

    L.append("## 3. 证据示例\n见上「## <detector>」各节（每 detector 最多 3 页示例）。\n\n")

    L.append("## 4. 可能产生大量 false positive 的 detector\n")
    L.append("| detector | FP 风险 | 原因 |\n|---|---|---|\n")
    L.append("| table | **高** | 「行长度周期性」「短行横向排列」在普通正文页同样成立 |\n")
    L.append("| header_footer | **高** | 教材每页都有章名页眉，属正常结构而非错误 |\n")
    L.append("| number | 中高 | 数字密集/小数在统计教材中普遍存在 |\n")
    L.append("| character | 中 | 「一+数字」「单字力」等模式可能是正常汉字用法 |\n")
    L.append("| multicol | 中高 | 短长行交替在无多栏的页面也常见 |\n")
    L.append("| linebreak | 中 | 教材换行本就破碎，短行/非句末结尾属常态 |\n")
    L.append("| repetition | 中 | 页眉、章节标题、习题模板都会重复 |\n")
    L.append("| formula | 低-中 | 符号本身明确，但「是否识别正确」不可判定 |\n\n")

    L.append("## 5. 只能作为人工审核优先级的 detector\n")
    L.append("- **formula**：只能输出 `FORMULA_REQUIRES_HUMAN_VERIFICATION`，"
             "程序不能判断公式是否被正确识别\n")
    L.append("- **table**：只能输出 `TABLE_PRESENT / TABLE_SUSPECTED`，"
             "不能判断行列归属与数值\n")
    L.append("- **multicol**：只能输出 `POSSIBLE_MULTICOLUMN`，"
             "阅读顺序是否错误只能人工对照原书\n")
    L.append("- **linebreak**：只能输出 `POSSIBLE_OCR_LINE_BREAK_ERROR`\n")
    L.append("- **repetition / header_footer**：重复与页眉常为正常结构，"
             "只能输出候选\n\n")

    L.append("## 6. detector 是否依赖 OCR-derived metadata\n")
    L.append("- **否**。8 个 detector 的输入仅为「页标记切出的原始 OCR 页文本」。\n")
    L.append("- 使用的全书统计（`line_freq`/首末行频次）同样由 OCR TXT 自身计算，**未使用**"
             "index.pkl 的 chapter/section/page_print、未使用 embedding、未使用 retrieval 结果、"
             "未使用 LLM。\n")
    L.append("- 唯一外部输入是「页边界」，来自 `=== 第 N 页 ===` 标记（属 OCR 产物结构），"
             "因此**页边界本身若错，detector 结果随之错**——这是一条已知依赖。\n\n")

    L.append("## 7. 仍然完全无法验证的项目（HUMAN VERIFICATION REQUIRED）\n")
    for item in ["0/O 混淆", "1/l/I 混淆", "5/S", "公式语义与结构正确性",
                 "表格列归属与数值正确性", "多栏阅读顺序", "专业术语是否正确",
                 "图注/脚注是否缺失", "是否漏字/多字", "原书印刷页码真值"]:
        L.append("- %s → **UNVERIFIED（需人工目视对照原 PDF 页）**\n" % item)
    L.append("\n> 特别禁止的推论：不得因「retrieval 能命中」或「文本看起来正常」"
             "推出 OCR 正确。\n\n")

    L.append("## 8. 建议人工视觉检查的页（按触发数排序，非错误判定）\n")
    L.append("| page_pdf | 触发 detector 数 | 其中 REVIEW 级 |\n|---|---|---|\n")
    for p, c in per_page.most_common(15):
        L.append("| %s | %d | %d |\n" % (p, c, review_pages.get(p, 0)))
    L.append("\n至少 1 个 REVIEW 级信号的页数：%d / %d\n"
             % (len(review_pages), len(spans)))
    L.append("\n## 9. 结论\n\n**DETECTOR_LAYER_COMPLETE**\n\n")
    L.append("含义：8 个 detector 已在 433 页上完成扫描并输出证据；"
             "**不代表任何 OCR 正确性结论**。\n")
    L.append("本层不含 risk score、不含 PASS/FAIL、不含 OCR accuracy。\n")

    with open(os.path.join(outdir, "detector_summary.md"), "w", encoding="utf-8") as f:
        f.writelines(L)

    print("records:", len(rows))
    print("trigger counts:", {k: v["triggered"] for k, v in per_detector.items()})
    print("pdf_sha256:", (pdf_sha or "")[:16])
    print("out:", outdir)


if __name__ == "__main__":
    main()
