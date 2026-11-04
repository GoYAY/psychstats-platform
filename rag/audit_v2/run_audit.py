# -*- coding: utf-8 -*-
"""audit_v2.run_audit —— P0：Traceability Infrastructure（只读）。

产出：
  audit_v2_out/page_spans.csv
  audit_v2_out/chunk_spans.csv
  audit_v2_out/traceability_report.md
  audit_v2_out/run_meta.json

本轮不做：OCR 正确性判断 / Risk Score / Sampling / Ground Truth / Dashboard。
"""
import os
import sys
import csv
import json
import random
import datetime
import collections
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audit_v2 import loaders, page_spans as ps_mod, chunk_spans as cs_mod  # noqa: E402
from audit_v2.schema import (SCHEMA_VERSION, AUDIT_VERSION, RANDOM_SEED,
                             STATUS_BY_METHOD, LEGACY_OFFSET_FIELD)  # noqa: E402

SAMPLE_N = 40
QUOTA = {"front": 5, "back": 5, "noise": 8, "prose": 22}


def build_chunk_rows(txt, index_chunks, spans, overlap):
    by_page = {s["page_pdf"]: s for s in spans}
    cache = {}
    rows = []
    for c in index_chunks:
        span = by_page.get(c["page_pdf"])
        if span is None:
            rows.append({"chunk_id": c["chunk_id"], "page_pdf": c["page_pdf"],
                         "method": "NOT_FOUND", "status": "NOT_FOUND",
                         "start": "", "end": "", "occurrences": 0, "prefix_len": 0,
                         "note": "page not found in OCR TXT"})
            continue
        if c["page_pdf"] not in cache:
            cache[c["page_pdf"]] = cs_mod.PageIndex(txt, span)
        pidx = cache[c["page_pdf"]]
        page_txt = txt[span["content_start"]:span["content_end"]]
        r = cs_mod.locate_chunk(c["text"], pidx, page_txt, overlap)
        rows.append({
            "chunk_id": c["chunk_id"],
            "page_pdf": c["page_pdf"],
            "page_print": c.get("page_print", ""),
            "chapter_no": c.get("chapter_no", ""),
            "block_type": c.get("block_type", ""),
            "chunk_len": len(c["text"]),
            "method": r["method"],
            "status": STATUS_BY_METHOD[r["method"]],
            "source_char_start": r["start"] if r["start"] is not None else "",
            "source_char_end": r["end"] if r["end"] is not None else "",
            "span_len": (r["end"] - r["start"]) if r["start"] is not None else "",
            "occurrences": r["occurrences"],
            "prefix_len": r["prefix_len"],
            "legacy_offset": c.get(LEGACY_OFFSET_FIELD, ""),
            "legacy_offset_valid": "",
            "note": r["note"],
        })
    # 负面测试：旧 offset 是否可作为真实来源位置
    for r, c in zip(rows, index_chunks):
        off = c.get(LEGACY_OFFSET_FIELD)
        ok = 0
        if isinstance(off, int) and 0 <= off < len(txt):
            ok = int(txt[off:off + len(c["text"])] == c["text"])
        r["legacy_offset_valid"] = ok
    return rows


def pick_sample(rows, chunks, seed=RANDOM_SEED):
    """分层抽样：front/back/noise/prose，尽量覆盖不同页与不同章。"""
    rng = random.Random(seed)
    pool = collections.defaultdict(list)
    for r in rows:
        if r["source_char_start"] != "":
            pool[r["block_type"]].append(r)
    picked, used_pages, used_chaps = [], set(), set()
    for bt, n in QUOTA.items():
        cand = [r for r in pool.get(bt, []) if r["page_pdf"] not in used_pages]
        rng.shuffle(cand)
        cand.sort(key=lambda r: (r["page_pdf"] in used_pages,
                                 r["chapter_no"] in used_chaps))
        for r in cand[:n]:
            picked.append(r)
            used_pages.add(r["page_pdf"])
            if r["chapter_no"]:
                used_chaps.add(r["chapter_no"])
    extra = [r for r in rows if r["source_char_start"] != ""
             and r["chunk_id"] not in {p["chunk_id"] for p in picked}]
    rng.shuffle(extra)
    for r in extra:
        if len(picked) >= SAMPLE_N:
            break
        if r["page_pdf"] in used_pages:
            continue
        picked.append(r)
        used_pages.add(r["page_pdf"])
    seen = set()
    uniq = []
    for r in picked:                      # 保证页互不重复
        if r["page_pdf"] in seen:
            continue
        seen.add(r["page_pdf"])
        uniq.append(r)
    for r in extra:                       # 用不重复页补齐到 SAMPLE_N
        if len(uniq) >= SAMPLE_N:
            break
        if r["page_pdf"] in seen or r["chunk_id"] in {p["chunk_id"] for p in uniq}:
            continue
        seen.add(r["page_pdf"])
        uniq.append(r)
    return sorted(uniq, key=lambda r: r["chunk_id"])


def verify_sample(txt, chunks, spans, sample, overlap):
    by_id = {c["chunk_id"]: c for c in chunks}
    by_page = {s["page_pdf"]: s for s in spans}
    out = []
    for r in sample:
        c = by_id[r["chunk_id"]]
        span = by_page[c["page_pdf"]]
        pidx = cs_mod.PageIndex(txt, span)
        ok = False
        a, b = r["source_char_start"], r["source_char_end"]
        if r["method"] == "EXACT" and a != "":
            ok = txt[a:b] == c["text"]
        elif a != "":
            core = c["text"][r["prefix_len"]:] if r["prefix_len"] else c["text"]
            p = pidx.joined.find(core)
            ok = p >= 0 and pidx.joined.count(core) == 1
        out.append({"chunk_id": r["chunk_id"], "page_pdf": r["page_pdf"],
                    "block_type": r["block_type"], "chapter_no": r["chapter_no"],
                    "source_start": a, "source_end": b,
                    "match_method": r["method"], "status": r["status"],
                    "verified": ok})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-pages", type=int, default=None,
                    help="PDF 页数（由外部用 PyMuPDF 测得；本环境 .venv 无 fitz）")
    ap.add_argument("--pdf-pages-source", default="operator_supplied")
    args = ap.parse_args()

    txt, d, meta = loaders.load_all()
    chunks = d["chunks"]
    overlap = int(d.get("params", {}).get("overlap", 100))

    spans = ps_mod.build_page_spans(txt)
    issues, pstats = ps_mod.validate_page_spans(spans, args.pdf_pages)

    rows = build_chunk_rows(txt, chunks, spans, overlap)
    sample = pick_sample(rows, chunks)
    verified = verify_sample(txt, chunks, spans, sample, overlap)

    outdir = loaders.OUT_DIR
    os.makedirs(outdir, exist_ok=True)

    with open(os.path.join(outdir, "page_spans.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(spans[0].keys()))
        w.writeheader()
        w.writerows(spans)

    with open(os.path.join(outdir, "chunk_spans.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    cnt = collections.Counter(r["method"] for r in rows)
    legacy_ok = sum(r["legacy_offset_valid"] for r in rows)
    resolved = sum(1 for r in rows if r["source_char_start"] != "")

    run_meta = {
        "schema_version": SCHEMA_VERSION,
        "audit_version": AUDIT_VERSION,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "random_seed": RANDOM_SEED,
        "src_sha256": meta["src_sha256"],
        "index_sha256": meta["index_sha256"],
        "pdf_sha256": meta["pdf_sha256"],
        "pdf_path": meta["pdf_path"],
        "pdf_available_at_run": bool(meta["pdf_path"]),
        "pdf_page_count": args.pdf_pages,
        "pdf_page_count_source": args.pdf_pages_source,
        "ocr_page_count": pstats["n_pages"],
        "ocr_page_issues": issues,
        "n_chunks": len(chunks),
        "match_counts": dict(cnt),
        "chunks_with_source_span": resolved,
        "legacy_offset_valid_count": legacy_ok,
        "overlap_param": overlap,
        "outputs": ["page_spans.csv", "chunk_spans.csv",
                    "traceability_report.md", "run_meta.json"],
    }
    loaders.write_json(os.path.join(outdir, "run_meta.json"), run_meta)

    lines = []
    lines.append("# Traceability Report (audit_v2 P0)\n")
    lines.append("只读重建：PDF page → OCR page → OCR source span → chunk。\n")
    lines.append("## 1. 页映射\n")
    lines.append("- OCR 页标记数：**%d**，页号 %s–%s，唯一值 %d\n"
                 % (pstats["n_pages"], pstats["min_page"], pstats["max_page"],
                    pstats["unique_pages"]))
    lines.append("- PDF 页数（%s）：**%s**；运行时刻 PDF 是否可访问：%s\n"
                 % (args.pdf_pages_source, args.pdf_pages,
                    bool(meta["pdf_path"])))
    if not meta["pdf_path"]:
        lines.append("- ⚠️ 运行时刻在 `%s` 未找到 PDF → pdf_sha256 无法计算，"
                     "页数 433 为外部输入值，本次**未重新校验**\n" % loaders.DEFAULT_PDF)
    lines.append("- 结构校验问题：%s\n" % (issues if issues else "NONE"))
    lines.append("\n## 2. Chunk → source span\n")
    lines.append("- chunk 总数：%d，成功定位：**%d**\n" % (len(rows), resolved))
    for m in ["EXACT", "CLEANED_EXACT", "OVERLAP_PREFIX", "AMBIGUOUS", "NOT_FOUND"]:
        lines.append("- %s：%d\n" % (m, cnt.get(m, 0)))
    lines.append("\n## 3. 负面测试：旧 offset 不可信\n")
    lines.append("- `txt[offset:offset+len]` 与 chunk 文本一致：**%d / %d**\n"
                 % (legacy_ok, len(rows)))
    lines.append("\n## 4. 分层抽样验证（40 chunks）\n")
    lines.append("| chunk_id | page_pdf | block_type | chapter | start | end | method | status | verified |\n")
    lines.append("|---|---|---|---|---|---|---|---|---|\n")
    for v in verified:
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |\n" % (
            v["chunk_id"], v["page_pdf"], v["block_type"], v["chapter_no"],
            v["source_start"], v["source_end"], v["match_method"],
            v["status"], v["verified"]))
    nv = sum(1 for v in verified if v["verified"])
    lines.append("\n抽样内二次校验通过：%d / %d\n" % (nv, len(verified)))
    lines.append("\n## 5. 仍需人工验证\n")
    lines.append("- AMBIGUOUS / NOT_FOUND 页：见 chunk_spans.csv\n")
    lines.append("- 本轮仅证明「来源位置可定位」，**未证明 OCR 内容正确**\n")
    with open(os.path.join(outdir, "traceability_report.md"), "w", encoding="utf-8") as f:
        f.writelines(lines)

    print("pages:", pstats["n_pages"], "issues:", issues)
    print("chunks:", len(rows), "resolved:", resolved, "methods:", dict(cnt))
    print("legacy offset valid:", legacy_ok)
    print("sample verified:", sum(1 for v in verified if v["verified"]), "/", len(verified))
    print("out dir:", outdir)


if __name__ == "__main__":
    main()
