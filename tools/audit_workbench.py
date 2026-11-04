# -*- coding: utf-8 -*-
"""tools/audit_workbench.py —— 本机人工校对工作台（127.0.0.1，供人使用，不做自动判定）。

功能：
  1) OCR 人工 Ground Truth 填写与导出（写回 audit_v2_out/OCR_AUDIT_GROUND_TRUTH.csv，写前自动备份）
  2) 页 → OCR 文本 → chunk → 教材/讲义双源 溯源面板
  3) 术语与公式校对队列（读 terms_draft.json，逐条确认后提升到 site/content/terms.json）

启动（.venv）：.venv\\Scripts\\python.exe tools\\audit_workbench.py  → http://127.0.0.1:5057
安全：仅监听 127.0.0.1；不修改 OCR TXT / index.pkl / 既有审计产物（仅 GT CSV 与 terms.json 由人工操作触发）
"""
import os
import csv
import json
import shutil
import datetime
import collections

from flask import Flask, request, jsonify, Response, redirect

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUDIT_OUT = os.path.join(ROOT, "rag", "audit_v2_out")
GT_CSV = os.path.join(AUDIT_OUT, "OCR_AUDIT_GROUND_TRUTH.csv")
PLAN_CSV = os.path.join(AUDIT_OUT, "sampling_plan.csv")
EVID_CSV = os.path.join(AUDIT_OUT, "detector_page_evidence.csv")
PAGE_CSV = os.path.join(AUDIT_OUT, "page_spans.csv")
CHUNK_CSV = os.path.join(AUDIT_OUT, "chunk_spans.csv")
TXT = os.path.join(ROOT, "data", "高级心理统计.txt")
COURSE_DIR = os.path.join(ROOT, "data", "course")
COURSE_MANIFEST = os.path.join(ROOT, "site", "content", "course_manifest.json")
TERMS_DRAFT = os.path.join(ROOT, "site", "content", "terms_draft.json")
TERMS = os.path.join(ROOT, "site", "content", "terms.json")

ERROR_TYPES = ["NONE", "CHARACTER", "NUMBER", "FORMULA", "TABLE", "HEADER_FOOTER",
               "LINE_BREAK", "MULTI_COLUMN", "MISSING_TEXT", "EXTRA_TEXT",
               "WRONG_ORDER", "OTHER"]
SEVERITIES = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

app = Flask(__name__)


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_txt_cached():
    if not hasattr(read_txt_cached, "_c"):
        with open(TXT, encoding="utf-8") as f:
            read_txt_cached._c = f.read()
    return read_txt_cached._c


def page_text(page_pdf):
    txt = read_txt_cached()
    rows = {int(r["page_pdf"]): r for r in read_csv(PAGE_CSV)}
    r = rows.get(int(page_pdf))
    if not r:
        return ""
    return txt[int(r["content_start"]):int(r["content_end"])]


def chunks_on_page(page_pdf):
    return [r for r in read_csv(CHUNK_CSV) if r["page_pdf"] == str(page_pdf)]


def evidence_for(page_pdf):
    return [r for r in read_csv(EVID_CSV)
            if r["page_pdf"] == str(page_pdf) and r["triggered"] == "True"]


PAGE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>校对工作台 · 心理统计术语站</title>
<style>
 body{font-family:"Noto Sans SC",system-ui,sans-serif;margin:0;background:#F7F6F3;color:#1B1F2A}
 header{background:#1F2A6B;color:#fff;padding:12px 20px;display:flex;gap:18px;align-items:center}
 header a{color:#C9D4FF;text-decoration:none;font-size:14px}
 .wrap{max-width:1180px;margin:0 auto;padding:18px 20px 60px}
 .card{background:#fff;border:1px solid #E3E6EA;border-radius:12px;padding:16px;margin-bottom:14px}
 table{border-collapse:collapse;width:100%;font-size:13px}
 th,td{border-bottom:1px solid #EEF1F8;padding:6px 8px;text-align:left;vertical-align:top}
 .mono{font-family:ui-monospace,Consolas,monospace;font-size:12px;color:#7A8194}
 pre{white-space:pre-wrap;background:#F7F8FC;border:1px solid #E7EAF3;border-radius:8px;padding:12px;max-height:420px;overflow:auto;font-size:13px}
 .tag{font-size:11.5px;background:#EEF1F8;border-radius:999px;padding:2px 8px;color:#4A5160}
 .warn{color:#B45309;background:rgba(180,83,9,.12)}
 input,select,textarea{font-family:inherit;font-size:13.5px;padding:6px 8px;border:1px solid #D8DCE6;border-radius:8px}
 button{background:#2B3A8F;color:#fff;border:none;border-radius:8px;padding:8px 14px;font-size:13.5px;cursor:pointer}
 button.g{background:#EEF1F8;color:#2B3A8F}
 .bar{height:10px;background:#EEF1F8;border-radius:999px;overflow:hidden}
 .bar>i{display:block;height:100%;background:#0E8F7E}
</style></head><body>
<header><b>校对工作台</b>
 <a href="/">总览</a><a href="/ocr">OCR 人工 GT</a><a href="/terms">术语校对</a>
 <span class="mono" style="margin-left:auto">仅本机 · 只写 GT/术语库，不动原始数据</span></header>
<div class="wrap">__BODY__</div></body></html>"""


@app.route("/")
def home():
    gt = read_csv(GT_CSV)
    done = sum(1 for r in gt if str(r.get("human_verified", "0")) == "1")
    errs = sum(1 for r in gt if str(r.get("error_present", "")) == "1")
    acc = read_csv(AUDIT_OUT) if False else []
    body = ["<div class='card'><h3>OCR 人工 Ground Truth</h3>",
            "<p>已填写 <b>%d</b> / %d 页；其中判定存在 OCR 错误 <b>%d</b> 页。</p>"
            % (done, len(gt), errs),
            "<div class='bar'><i style='width:%.1f%%'></i></div>"
            % (100.0 * done / max(len(gt), 1)),
            "<p class='mono'>GT 文件：%s</p></div>" % GT_CSV]
    draft = json.load(open(TERMS_DRAFT, encoding="utf-8")) if os.path.exists(TERMS_DRAFT) else {"terms": []}
    terms = json.load(open(TERMS, encoding="utf-8")) if os.path.exists(TERMS) else {"terms": []}
    body.append("<div class='card'><h3>术语校对队列</h3>"
                "<p>候选 %d 条；已进入冻结库 %d 条（其中已核对 %d 条）。</p>"
                "<p class='mono'>候选：%s · 冻结：%s</p></div>"
                % (len(draft["terms"]), len(terms["terms"]),
                   sum(1 for t in terms["terms"] if t.get("verified")),
                   TERMS_DRAFT, TERMS))
    body.append("<div class='card'><h3>边界提醒</h3><ul>"
                "<li>detector 触发 ≠ OCR 错误；detector 未触发 ≠ OCR 正确。</li>"
                "<li>GT 的三种判定必须区分：OCR ERROR / NORMAL_LAYOUT / SOURCE_ISSUE。</li>"
                "<li>CRITICAL 仅用于「含义被改变」的错误。</li>"
                "<li>讲义数值（SPSS/Mplus 输出）一律视为高风险，需逐项核对。</li></ul></div>")
    return Response(PAGE.replace("__BODY__", "".join(body)), mimetype="text/html")


@app.route("/ocr")
def ocr_list():
    gt = read_csv(GT_CSV)
    plan = {r["page_pdf"]: r for r in read_csv(PLAN_CSV)}
    rows = []
    for r in gt:
        p = r["page_pdf"]
        pl = plan.get(p, {})
        flag = r.get("human_verified", "0") == "1"
        rows.append("<tr><td><a href='/trace?page=%s'>%s</a></td>"
                    "<td>%s</td><td class='mono'>%s</td>"
                    "<td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (p, p, pl.get("priority", ""), pl.get("sampling_reasons", "")[:60],
                       "✔" if flag else "—", r.get("error_type", ""), r.get("severity", "")))
    body = ["<div class='card'><h3>人工审核页清单（%d 页）</h3>"
            "<p class='mono'>点击页码进入溯源面板 → 对照原 PDF → 填写右侧表单</p>"
            "<table><tr><th>页</th><th>优先级</th><th>抽样原因</th><th>已填</th>"
            "<th>error_type</th><th>severity</th></tr>%s</table></div>" % (len(rows), "".join(rows))]
    return Response(PAGE.replace("__BODY__", "".join(body)), mimetype="text/html")


@app.route("/trace")
def trace():
    p = request.args.get("page", "")
    txt = page_text(p)
    chs = chunks_on_page(p)
    evs = evidence_for(p)
    html = ["<div class='card'><h3>第 %s 页 · 溯源</h3>" % p]
    html.append("<div class='mono'>教材 OCR 文本（codepoint 区间见 page_spans.csv）</div>")
    html.append("<pre>%s</pre></div>" % (txt[:6000].replace("&", "&amp;").replace("<", "&lt;")))
    html.append("<div class='card'><h3>该页 chunk（%d）</h3><table>"
                "<tr><th>chunk_id</th><th>定位方式</th><th>状态</th><th>字符区间</th></tr>%s</table>"
                "<p class='mono'>来源：chunk_spans.csv（1 条 AMBIGUOUS = chunk 83，见 ambiguous_forensic_report.md）</p></div>"
                % (len(chs), "".join(
                    "<tr><td>%s</td><td>%s</td><td>%s</td><td class='mono'>%s–%s</td></tr>"
                    % (c["chunk_id"], c["method"], c["status"],
                       c["source_char_start"], c["source_char_end"]) for c in chs)))
    html.append("<div class='card'><h3>detector 形式证据（%d）</h3><table>"
                "<tr><th>detector</th><th>severity</th><th>reason</th></tr>%s</table>"
                "<p class='mono'>证据 JSON 明细见 detector_page_evidence.csv</p></div>"
                % (len(evs), "".join(
                    "<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (e["detector_name"], e["severity_hint"], e["reason"]) for e in evs)))
    html.append(GT_FORM % {"page": p,
                           "types": "".join("<option>%s</option>" % x for x in ERROR_TYPES),
                           "sevs": "".join("<option>%s</option>" % x for x in SEVERITIES)})
    return Response(PAGE.replace("__BODY__", "".join(html)), mimetype="text/html")


GT_FORM = """<div class='card'><h3>人工判读表单（第 %(page)s 页）</h3>
 <p class='mono'>填写前必须先目视对照原始 PDF 页面。detector 触发≠错误。</p>
 <form method="post" action="/api/gt">
  <input type="hidden" name="page_pdf" value="%(page)s"/>
  <p>已核对：<select name="human_verified"><option value="1">1 已核对</option><option value="0">0 未核对</option></select>
     存在 OCR 错误：<select name="error_present"><option value="0">0 否</option><option value="1">1 是</option></select>
     类型：<select name="error_type">%(types)s</select>
     严重度：<select name="severity">%(sevs)s</select></p>
  <p>说明：<input name="description" size="70"/> 原书位置：<input name="pdf_location" size="24"/></p>
  <p>OCR 位置：<input name="ocr_location" size="40"/> 正确文本：<input name="correct_text" size="40"/></p>
  <p>检查人：<input name="reviewer" size="14"/> 备注：<input name="notes" size="46" placeholder="NORMAL_LAYOUT / SOURCE_ISSUE"/></p>
  <button type="submit">保存到 GT CSV（自动备份）</button>
 </form></div>"""


@app.route("/api/gt", methods=["POST"])
def save_gt():
    row = dict(request.form)
    rows = read_csv(GT_CSV)
    fields = list(rows[0].keys()) if rows else list(row.keys())
    if not os.path.exists(GT_CSV + ".bak"):
        shutil.copy2(GT_CSV, GT_CSV + ".bak")
    hit = False
    for r in rows:
        if r["page_pdf"] == row["page_pdf"]:
            for k in fields:
                if k in row:
                    r[k] = row[k]
            r["reviewed_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            hit = True
    if not hit:
        return jsonify({"ok": False, "error": "page not in GT template"}), 400
    with open(GT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return redirect("/ocr")


@app.route("/terms")
def terms_list():
    draft = json.load(open(TERMS_DRAFT, encoding="utf-8"))
    rows = []
    for t in draft["terms"]:
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                    "<td class='mono'>%s</td><td>%s</td></tr>"
                    % (t["zh"], t["en"], t["category"], t["coverage"],
                       ",".join(t["flags"]) or "—",
                       "、".join("<a href='#%s'>%s</a>" % (s["chunk_id"], s["page_print"])
                                 for s in t["evidence"]["textbook"][:3])))
    body = ["<div class='card'><h3>候选术语（%d 条）</h3>"
            "<p>对齐要求：先人工核对教材原页 → 再改写正文与公式 → 置 verified/formula_verified → "
            "写入 <span class='mono'>site/content/terms.json</span>（本工作台不自动提升）。</p>"
            "<table><tr><th>术语</th><th>英文</th><th>分类</th><th>覆盖</th>"
            "<th>告警</th><th>教材候选页</th></tr>%s</table></div>"
            % (len(rows), "".join(rows))]
    return Response(PAGE.replace("__BODY__", "".join(body)), mimetype="text/html")


def main():
    port = int(os.environ.get("WORKBENCH_PORT", "5057"))
    print("校对工作台：http://127.0.0.1:%d" % port)
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
