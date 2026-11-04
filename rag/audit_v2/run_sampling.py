# -*- coding: utf-8 -*-
"""audit_v2.run_sampling —— Phase C：抽样 + Ground Truth 基础设施（只读 + 新建产物）。

产出：
  audit_v2_out/sampling_plan.csv
  audit_v2_out/sampling_summary.md
  audit_v2_out/sampling_run_meta.json
  audit_v2_out/OCR_AUDIT_GROUND_TRUTH.csv   （空模板，待人工填写）
  audit_v2_out/HUMAN_REVIEW_GUIDE.md        （人工对照说明）

本轮不执行 calibration，不输出任何 Precision/Recall/FNR/OCR accuracy。
"""
import os
import sys
import csv
import json
import hashlib
import datetime
import platform
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from audit_v2 import loaders, page_spans as ps_mod  # noqa: E402
from audit_v2 import sampling as sp, groundtruth as gt  # noqa: E402
from audit_v2.schema import SCHEMA_VERSION, AUDIT_VERSION, RANDOM_SEED  # noqa: E402

SAMPLING_VERSION = "1.0"
EVIDENCE_CSV = "detector_page_evidence.csv"
ROOT = os.path.dirname(os.path.dirname(HERE))


def find_pdf():
    for x in sorted(os.listdir(ROOT)):
        if x.lower().endswith(".pdf"):
            return os.path.join(ROOT, x)
    return None


def sha256_file(p):
    if not p or not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    txt, _d, meta = loaders.load_all()
    spans = ps_mod.build_page_spans(txt)
    page_texts = {s["page_pdf"]: txt[s["content_start"]:s["content_end"]] for s in spans}

    ev_rows = sp.load_evidence(os.path.join(loaders.OUT_DIR, EVIDENCE_CSV))
    idx = sp.page_index(ev_rows)
    plan, pools = sp.build_plan(idx, page_texts, RANDOM_SEED)

    outdir = loaders.OUT_DIR
    os.makedirs(outdir, exist_ok=True)

    plan_rows = [plan[p] for p in sorted(plan)]
    with open(os.path.join(outdir, "sampling_plan.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(plan_rows[0].keys()))
        w.writeheader()
        w.writerows(plan_rows)

    gt.write_template(os.path.join(outdir, "OCR_AUDIT_GROUND_TRUTH.csv"), sorted(plan))

    pdf_path = find_pdf()
    run_meta = {
        "schema_version": SCHEMA_VERSION,
        "audit_version": AUDIT_VERSION,
        "sampling_version": SAMPLING_VERSION,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "python_version": platform.python_version(),
        "random_seed": RANDOM_SEED,
        "src_sha256": meta["src_sha256"],
        "index_sha256": meta["index_sha256"],
        "pdf_path": pdf_path,
        "pdf_sha256": sha256_file(pdf_path),
        "evidence_source": EVIDENCE_CSV,
        "n_pages_total": len(spans),
        "n_pages_sampled": len(plan),
        "pools": pools,
        "params": {
            "N_PER_DETECTOR_POS": sp.N_PER_DETECTOR_POS,
            "N_DETECTOR_NEGATIVE": sp.N_DETECTOR_NEGATIVE,
            "N_PER_DETECTOR_NEG": sp.N_PER_DETECTOR_NEG,
            "N_LOW_SIGNAL": sp.N_LOW_SIGNAL,
            "LOW_SIGNAL_MAX": sp.LOW_SIGNAL_MAX,
            "N_RANDOM": sp.N_RANDOM,
            "N_PER_CONTENT": sp.N_PER_CONTENT,
        },
        "gt_note": "GT 为空模板，必须由人工对照原 PDF 页填写；程序不得自动生成。",
    }
    loaders.write_json(os.path.join(outdir, "sampling_run_meta.json"), run_meta)

    by_stratum = collections.Counter()
    by_reason = collections.Counter()
    for r in plan_rows:
        for s in r["sampling_strata"].split(";"):
            by_stratum[s] += 1
        for x in json.loads(r["sampling_reasons"]):
            by_reason[x] += 1
    pri = collections.Counter(r["priority"] for r in plan_rows)
    pos_pages = sum(1 for r in plan_rows if any(
        x.endswith("_positive") for x in json.loads(r["sampling_reasons"])))
    strict_neg = by_reason.get("all_detectors_negative", 0)

    L = []
    L.append("# Sampling Summary (audit_v2 Phase C)\n\n")
    L.append("抽样只服务于：建立人工 GT、测量 detector FP/FN、为后续 calibration 提供数据。"
             "**抽样不能证明全书 OCR 正确**。\n\n")
    L.append("## 1. 总页数\n- %d 页\n\n" % len(spans))
    L.append("## 2. 各 stratum 页数（未去重）\n| stratum | 页数 |\n|---|---|\n")
    for k, v in sorted(by_stratum.items()):
        L.append("| %s | %d |\n" % (k, v))
    L.append("\n各 reason 计数：%s\n\n" % json.dumps(dict(by_reason), ensure_ascii=False))
    L.append("## 3. 去重后最终人工审核页数\n- **%d 页**（page_pdf 唯一）\n" % len(plan))
    L.append("- 优先级分布：%s\n\n" % dict(pri))
    L.append("## 4. detector-positive / detector-negative\n")
    L.append("- 含 detector_positive 的页：%d\n" % pos_pages)
    L.append("- 严格负样本（8/8 未触发）池 **%d 页**，抽中 %d 页；"
             "不足 25 页，已补充 per-detector negative 与 low-signal\n\n"
             % (pools["strict_negative_pool"], strict_neg))
    L.append("## 5. Sampling bias\n")
    L.append("- 有偏部分：detector_positive（刻意偏向命中页，用于测 FP），"
             "不可外推全书错误率。\n")
    L.append("- 无偏部分：random_baseline(%d 页, seed=%d)、detector_negative_strict(%d 页)。\n"
             % (sp.N_RANDOM, RANDOM_SEED, pools["strict_negative_pool"]))
    L.append("- 内容层池大小：%s\n" % json.dumps(pools["content_pools"], ensure_ascii=False))
    L.append("- 结论：**样本不能外推为全书 OCR 质量**。\n\n")
    L.append("## 6. 尚未获得 GT 的 detector\n- **8 个 detector 全部尚无人工 GT**"
             "（GT 文件为空模板）。\n")
    for d in sp.DETECTORS:
        L.append("  - %s: 计划 positive %d / negative %d 页\n"
                 % (d, by_reason.get("%s_positive" % d, 0),
                    by_reason.get("%s_negative" % d, 0)))
    L.append("\n## 7. 为什么现在不能计算 OCR accuracy\n")
    L.append("- accuracy 需要「全书真实字符级真值」，而人工只检查 %d 个抽样页，"
             "且只记录是否存在错误、不重录全文 → 分母不存在。\n" % len(plan))
    L.append("- 即使 %d 页全部无错，也只能说「该样本未发现错误」，"
             "不能推出全书无错。\n\n" % len(plan))
    L.append("## 8. 为什么现在不能计算 detector Precision/Recall/FNR\n")
    L.append("- Precision/Recall 的真值是 `error_present`，目前 0 条人工填写。\n")
    L.append("- 且 detector 是「形式特征」而非「错误判定」，"
             "TP/FP 的定义需先确定：detector 命中 **且** 人工确认该页存在"
             "对应类型错误 才算 TP；否则为 FP。\n")
    L.append("- 关联字段已备齐（page_pdf + detector_name + detector_triggered + "
             "error_present + error_type + severity），见 "
             "`groundtruth.build_calibration_frame()`，本轮**未调用**。\n\n")
    L.append("## 9. 结论\n\n**SAMPLING_READY_FOR_HUMAN_GT**\n\n")
    L.append("待人工填写 `OCR_AUDIT_GROUND_TRUTH.csv`（%d 行），"
             "对照原 PDF 页面逐页目视核对。\n" % len(plan))
    with open(os.path.join(outdir, "sampling_summary.md"), "w", encoding="utf-8") as f:
        f.writelines(L)

    print("pages:", len(spans), "sampled:", len(plan), "priority:", dict(pri))
    print("strict_negative_pool:", pools["strict_negative_pool"])
    print("out:", outdir)


if __name__ == "__main__":
    main()
