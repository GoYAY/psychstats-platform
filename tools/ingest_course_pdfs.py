# -*- coding: utf-8 -*-
"""tools/ingest_course_pdfs.py —— 课程讲义 PDF 混合采集（只读原件）。

策略（依据实测）：讲义不是「全图无文本框」，而是混合形态——
  * 文本层充足页（ch1/w8/w9/w10）→ 文本层直接作文本草稿
  * 图片主导页（Week2/4/6、第14章）→ 抽取【内嵌图片原生分辨率】后 OCR
    （页面渲染到 300dpi 只是放大，不增加信息：实测原生即 ~200dpi）
  * 同一 xref 在多页复用（模板底色/页脚）→ 按 xref 去重，只 OCR 一次
  * 统计软件结果截图 → 用 OCR 框做【几何重建】产出表格候选（TABLE_CANDIDATE）
  * 数值一律标记 NUMERIC_HIGH_RISK，进人工核对队列，不作为事实

产出：
  data/course/<slug>.txt            逐页文本（标注来源等级）
  data/course/.cache/<slug>.json    图片 OCR 缓存（可复跑）
  site/content/course_manifest.json 页级清单
  site/assets/img/course/<slug>/pNNN.png  页面预览图（人工核对用）

运行（在已安装 pymupdf 和 rapidocr-onnxruntime 的环境中）：
  python tools/ingest_course_pdfs.py [--only w08-moderation] [--force] [--max-images N]
"""
import os
import re
import sys
import json
import time
import argparse
import datetime
import collections

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_COURSE = os.path.join(ROOT, "data", "course")
CACHE_DIR = os.path.join(DATA_COURSE, ".cache")
MANIFEST = os.path.join(ROOT, "site", "content", "course_manifest.json")
IMG_DIR = os.path.join(ROOT, "site", "assets", "img", "course")

TEXT_LAYER_MIN = 20          # 文本层字符数下限
IMG_MIN_W_PT = 100           # 视为内容图的最小放置宽度(pt)
IMG_MIN_H_PT = 60
IMG_MIN_AREA_RATIO = 0.01    # 视为内容图的最小面积占比
MAX_NATIVE_PX = 2600         # 原生图长边上限（控制 OCR 耗时）
OCR_SCORE_MIN = 0.50
PREVIEW_DPI = 120

SLUG_MAP = {
    "ch1-2025新.pdf": "w01-ch1-intro",
    "高级统计-Week2-2025.pdf": "w02-week2",
    "高级统计-Week4-2025.pdf": "w04-week4",
    "高级统计-Week6探索性因子分析-2025.pdf": "w06-efa",
    "高级统计-多元回归-2025.pdf": "w07-regression",
    "w8-调节效应 new.pdf": "w08-moderation",
    "w9-中介效应++ new.pdf": "w09-mediation",
    "w10-验证性因素分析new.pdf": "w10-cfa",
    "第14章 心理实验常用统计方法.pdf": "ch14-expstats",
}


def slugify(name):
    if name in SLUG_MAP:
        return SLUG_MAP[name]
    base = os.path.splitext(name)[0].lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base or "course"


def list_course_pdfs():
    out = []
    for f in sorted(os.listdir(ROOT)):
        if not f.lower().endswith(".pdf"):
            continue
        if f == "高级心理统计.pdf":
            continue
        out.append(f)
    return out


# ---------------- 几何重建：OCR 框 → 表格候选 ----------------
NUM_TOKEN = re.compile(r"[-+]?\d+(?:\.\d+)?%?|\b(?:p|t|F|df|SE|SD|M|SD)\b")


def rows_from_boxes(boxes):
    """boxes: [(x0,y0,x1,y1,text)] → 逐行分组（按纵向重叠聚类）。"""
    bs = sorted(boxes, key=lambda b: (b[1], b[0]))
    rows = []
    for b in bs:
        placed = False
        for r in rows:
            ry0 = min(x[1] for x in r)
            ry1 = max(x[3] for x in r)
            ov = min(ry1, b[3]) - max(ry0, b[1])
            h = min(ry1 - ry0, b[3] - b[1]) or 1
            if ov / h > 0.5:
                r.append(b)
                placed = True
                break
        if not placed:
            rows.append([b])
    rows.sort(key=lambda r: min(x[1] for x in r))
    return [sorted(r, key=lambda b: b[0]) for r in rows]


def columns_from_rows(rows, tol=14.0):
    """用行内框的 x0 聚类出列边界；返回每行的单元格文本列表。"""
    starts = sorted(b[0] for r in rows for b in r)
    col_starts = []
    for s in starts:
        if not col_starts or s - col_starts[-1] > tol:
            col_starts.append(s)
    table = []
    for r in rows:
        cells = [""] * len(col_starts)
        for b in r:
            idx = 0
            for i, cs in enumerate(col_starts):
                if b[0] >= cs - tol:
                    idx = i
            cells[idx] = (cells[idx] + " " + b[4]).strip()
        table.append(cells)
    return [c for c in table if any(x for x in c)]


def table_candidate(boxes):
    """返回 (is_candidate, markdown_lines)。仅在 >=2 行且 >=2 列时成立。"""
    if len(boxes) < 4:
        return False, []
    rows = rows_from_boxes(boxes)
    cells = columns_from_rows(rows)
    if len(cells) < 2:
        return False, []
    ncol = max(len(c) for c in cells)
    if ncol < 2:
        return False, []
    filled = sum(1 for c in cells for x in c if x)
    if filled < len(cells) * 1.5:
        return False, []
    lines = ["| " + " | ".join((c + [""] * ncol)[:ncol]) + " |" for c in cells]
    sep = "|" + "---|" * ncol
    return True, [lines[0], sep] + lines[1:]


def numeric_risk(lines):
    """数值高风险行：含小数/百分号/等号统计量的行。"""
    risky = []
    for l in lines:
        if re.search(r"\d+\.\d+|\d+%|=\s*[-+]?\d|<\s*\.\d+|>\s*\.\d+", l):
            risky.append(l)
    return risky


# ---------------- OCR 引擎 ----------------
_OCR = None


def get_ocr():
    global _OCR
    if _OCR is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR = RapidOCR()
    return _OCR


def pixmap_for(doc, xref):
    pm = pymupdf.Pixmap(doc, xref)
    if pm.n > 3:
        pm = pymupdf.Pixmap(pymupdf.csRGB, pm)
    return pm


def ocr_xref(doc, xref, cache, stats):
    """按 xref 缓存 OCR 结果；返回 (lines, boxes, table_md, is_table)。"""
    key = str(xref)
    if key in cache:
        c = cache[key]
        return c["lines"], c["boxes"], c.get("table_md", []), c.get("is_table", False)
    t0 = time.time()
    pm = pixmap_for(doc, xref)
    scale = 1.0
    long_side = max(pm.width, pm.height)
    if long_side > MAX_NATIVE_PX:
        scale = MAX_NATIVE_PX / float(long_side)
        pm = pymupdf.Pixmap(pm, 0)
        pm = pymupdf.Pixmap(pm, pymupdf.Matrix(scale, scale))
    png = pm.tobytes("png")
    result, _ = get_ocr()(png)
    lines, boxes = [], []
    for item in (result or []):
        box, text, score = item[0], item[1], float(item[2])
        if score < OCR_SCORE_MIN or not str(text).strip():
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        lines.append(str(text).strip())
        boxes.append((min(xs), min(ys), max(xs), max(ys), str(text).strip()))
    is_tab, md = table_candidate(boxes)
    cache[key] = {"lines": lines, "boxes": boxes, "table_md": md,
                  "is_table": is_tab, "px": [pm.width, pm.height],
                  "scale": round(scale, 3), "secs": round(time.time() - t0, 2)}
    stats["ocr_images"] += 1
    stats["ocr_secs"] += cache[key]["secs"]
    return lines, boxes, md, is_tab


def content_images(page, doc):
    """页面中值得 OCR 的内嵌图片：返回 [(xref, bbox)]（同 xref 去重）。"""
    pa = page.rect.width * page.rect.height
    seen, out = set(), []
    for r in page.get_image_info(xrefs=True):
        x = r.get("xref")
        if not x or x in seen:
            continue
        x0, y0, x1, y1 = r["bbox"]
        w, h = x1 - x0, y1 - y0
        if w < IMG_MIN_W_PT or h < IMG_MIN_H_PT:
            continue
        if (w * h) / max(pa, 1) < IMG_MIN_AREA_RATIO:
            continue
        seen.add(x)
        out.append((x, (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))))
    return out


# ---------------- 处理单份讲义 ----------------
def load_cache(slug):
    p = os.path.join(CACHE_DIR, slug + ".json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(slug, cache):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, slug + ".json"), "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def process_file(name, force=False, max_images=None, stats=None):
    slug = slugify(name)
    pdf_path = os.path.join(ROOT, name)
    out_txt = os.path.join(DATA_COURSE, slug + ".txt")
    prev_pages = {}
    if os.path.exists(out_txt) and not force:
        with open(out_txt, encoding="utf-8") as f:
            prev_pages = {int(m.group(1)): True
                          for m in re.finditer(r"=== 讲义页 (\d+) ===", f.read())}
    doc = pymupdf.open(pdf_path)
    cache = load_cache(slug)
    imgdir = os.path.join(IMG_DIR, slug)
    os.makedirs(imgdir, exist_ok=True)
    os.makedirs(DATA_COURSE, exist_ok=True)

    page_records, blocks = [], []
    for i in range(doc.page_count):
        pageno = i + 1
        page = doc[i]
        layer = page.get_text("text").strip()
        has_layer = len(layer) >= TEXT_LAYER_MIN
        imgs = content_images(page, doc)
        used_ocr, table_md, ocr_lines_all, risky = [], [], [], []
        section = []
        if layer:
            section.append(("TEXT_LAYER", layer.split("\n")))
        for xref, bbox in imgs:
            if max_images is not None and stats["ocr_images"] >= max_images:
                break
            try:
                lines, boxes, md, is_tab = ocr_xref(doc, xref, cache, stats)
            except Exception as e:                      # OCR 失败不应中断整份讲义
                lines, md, is_tab = [], [], False
                section.append(("IMAGE_OCR_ERROR[xref=%s]" % xref, [str(e)[:120]]))
            if not lines:
                continue
            used_ocr.append(xref)
            ocr_lines_all.extend(lines)
            if is_tab:
                table_md.append((xref, md))
            tag = "IMAGE_OCR[xref=%s%s]" % (xref, " TABLE_CANDIDATE" if is_tab else "")
            body = list(lines)
            if is_tab:
                body = ["```` 表格候选（几何重建，需人工核对）", ""] + md + ["````"] + body
            section.append((tag, body))

        risky = numeric_risk([l for _, ls in section for l in ls])
        rec = {
            "page_course": pageno,
            "has_text_layer": has_layer,
            "text_layer_chars": len(layer),
            "content_images": [x for x, _ in imgs],
            "ocr_used_xrefs": used_ocr,
            "table_candidates": [x for x, _ in table_md],
            "numeric_risk_lines": len(risky),
            "preview_png": os.path.join("assets", "img", "course", slug,
                                        "p%03d.png" % pageno).replace("\\", "/"),
            "provenance": sorted({t.split("[")[0] for t, _ in section} or {"EMPTY"}),
        }
        page_records.append(rec)
        blocks.append((pageno, rec, section))

        # 预览图（人工核对用，低 dpi；已存在则跳过）
        png = os.path.join(imgdir, "p%03d.png" % pageno)
        if force or not os.path.exists(png):
            pix = page.get_pixmap(dpi=PREVIEW_DPI)
            pix.save(png)
        print("  [%s] p%d/%d layer=%s imgs=%d ocr=%d%s"
              % (slug, pageno, doc.page_count, "Y" if has_layer else "N",
                 len(imgs), len(used_ocr), " TABLE" if table_md else ""), flush=True)

    doc.close()
    save_cache(slug, cache)
    write_txt(out_txt, name, slug, blocks)
    return {"slug": slug, "source_file": name, "pages": len(page_records),
            "pages_detail": page_records,
            "cache_images": len(cache)}


def write_txt(path, name, slug, blocks):
    """每页：=== 讲义页 N === + provenance 行 + 各来源分级段落。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write("# 课程讲义原文（自动采集，未经人工核对）\n")
        f.write("# 来源文件：%s\n" % name)
        f.write("# slug：%s\n" % slug)
        f.write("# 说明：TEXT_LAYER=PDF 文本层（公式可能被打散）；"
                "IMAGE_OCR=图片 OCR（数值高风险）；TABLE_CANDIDATE=几何重建表格候选\n\n")
        for pageno, rec, section in blocks:
            f.write("=== 讲义页 %d ===\n" % pageno)
            f.write("provenance: text_layer=%s image_ocr=%s tables=%s numeric_lines=%d\n"
                    % ("Y" if rec["has_text_layer"] else "N",
                       rec["ocr_used_xrefs"], rec["table_candidates"],
                       rec["numeric_risk_lines"]))
            for tag, lines in section:
                f.write("--- %s ---\n" % tag)
                f.write("\n".join(lines).strip() + "\n")
            f.write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="只处理某个 slug")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--max-images", type=int, default=None, help="本次最多新增 OCR 图片数")
    args = ap.parse_args()

    files = list_course_pdfs()
    stats = {"ocr_images": 0, "ocr_secs": 0.0}
    entries = []
    t0 = time.time()
    for name in files:
        slug = slugify(name)
        if args.only and slug != args.only:
            continue
        print("== 处理 %s -> %s" % (name, slug), flush=True)
        entries.append(process_file(name, force=args.force,
                                    max_images=args.max_images, stats=stats))

    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "ocr_engine": "RapidOCR(onnxruntime) 本地零 token",
        "params": {"TEXT_LAYER_MIN": TEXT_LAYER_MIN, "IMG_MIN_W_PT": IMG_MIN_W_PT,
                   "IMG_MIN_H_PT": IMG_MIN_H_PT, "IMG_MIN_AREA_RATIO": IMG_MIN_AREA_RATIO,
                   "MAX_NATIVE_PX": MAX_NATIVE_PX, "OCR_SCORE_MIN": OCR_SCORE_MIN,
                   "PREVIEW_DPI": PREVIEW_DPI},
        "totals": {
            "files": len(entries),
            "pages": sum(e["pages"] for e in entries),
            "ocr_images_this_run": stats["ocr_images"],
            "ocr_seconds_this_run": round(stats["ocr_secs"], 1),
            "elapsed_seconds": round(time.time() - t0, 1),
        },
        "note": "讲义文本同样未经人工核对；数值与公式不得直接引用。",
        "files": [{"slug": e["slug"], "source_file": e["source_file"],
                   "pages": e["pages"], "cache_images": e["cache_images"],
                   "pages_detail": e["pages_detail"]} for e in entries],
    }
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print("\nmanifest ->", MANIFEST)
    print("totals:", manifest["totals"])
    print("records:", collections.Counter(e["source_file"] for e in entries))


if __name__ == "__main__":
    main()
