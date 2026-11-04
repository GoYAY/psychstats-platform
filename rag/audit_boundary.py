# -*- coding: utf-8 -*-
"""
audit_boundary.py —— AI 边界与可追溯性审计（只读，不修改索引/数据/代码）

用途：把「AI 能程序化验证的部分」与「只能概率判断 / 必须人工检查的部分」分开。
输出：
  [OCR]      OCR 文本的自动化体检（编码/乱码/页眉页脚/异常字符/噪声页）
  [CHUNK]    切块边界与完整性（长度/重叠/跨小节/截断/噪声块/页面覆盖）
  [TRACE]    可追溯性：chunk -> 页 -> 源 TXT；印刷页码映射；章节标签
  [RETRIEVE] 检索证据级评测（36 题 × Top1/3/5/10，双判据）
  [EMBED]    Embedding 实际执行证据

说明：本脚本只做统计与打印，不做任何修复。
用法：.venv\Scripts\python.exe audit_boundary.py
"""
import os
import re
import sys
import pickle
import hashlib
import collections

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

SRC = os.path.join(ROOT, "data", "高级心理统计.txt")
INDEX = os.path.join(HERE, "rag_data", "index.pkl")

from build_index import parse_pages, clean_lines, build_print_map, extract_printed_page  # noqa: E402
from rag_core import retrieve, load_index, embed_texts, EMBED_MODEL, tokenize  # noqa: E402

CJK = re.compile(r"[\u4e00-\u9fff]")
SEC_MARK = re.compile(r"第[一二三四五六七八九十百]+节")
CHAP_MARK = re.compile(r"第[一二三四五六七八九十百]+章")
SENT_END = "。！？；：.”》）】!?;:"
PAGE_RESID = re.compile(r"(?m)^\s*/?\s*\d{1,3}\s*/?\s*$")


def hr(t):
    print("\n" + "=" * 72)
    print("### " + t)
    print("=" * 72)


# ============================================================ 1. OCR
def audit_ocr():
    hr("1. OCR 自动化体检（只能查形式，不能查忠实性）")
    raw = open(SRC, "rb").read()
    txt = raw.decode("utf-8")            # 若非 UTF-8 会在此抛错
    print(f"源文件: {SRC}")
    print(f"sha256 : {hashlib.sha256(raw).hexdigest()}")
    print(f"字节数 : {len(raw)}  字符数: {len(txt)}  行数: {len(txt.splitlines())}")
    print(f"U+FFFD 替换字符: {txt.count(chr(0xFFFD))}")
    ctrl = sum(1 for c in txt if ord(c) < 32 and c not in "\n\r\t")
    print(f"控制字符(非\\n\\r\\t): {ctrl}")
    print(f"私有区/不可见字符(U+E000-U+F8FF): "
          f"{sum(1 for c in txt if 0xE000 <= ord(c) <= 0xF8FF)}")

    pages = parse_pages(SRC)
    print(f"\n页标记解析: {len(pages)} 页, PDF 页号 {pages[0][0]}–{pages[-1][0]}")
    nums = [n for n, _ in pages]
    print(f"页号连续: {nums == list(range(1, len(nums) + 1))}")

    # 空页 / 短页
    empty = [n for n, b in pages if not b.strip()]
    short = [(n, len(b.strip())) for n, b in pages if 0 < len(b.strip()) < 50]
    print(f"空页: {len(empty)} {empty[:10]}")
    print(f"正文<50字的页: {len(short)} 例: {short[:8]}")

    # 页眉页脚重复
    first = collections.Counter()
    last = collections.Counter()
    for n, b in pages:
        ls = [l.strip() for l in b.splitlines() if l.strip()]
        if ls:
            first[ls[0]] += 1
            last[ls[-1]] += 1
    print("\n-- 高频首页行(疑似页眉, >=8次) --")
    for l, c in first.most_common(20):
        if c >= 8:
            print(f"  {c:>4}  {l[:56]}")
    print("-- 高频末页行(疑似页脚, >=8次) --")
    for l, c in last.most_common(20):
        if c >= 8:
            print(f"  {c:>4}  {l[:56]}")

    # 页码残留
    resid = sum(1 for l in txt.splitlines() if PAGE_RESID.match(l))
    print(f"\n页码残留行(纯数字或 N/ ): {resid}")

    # 每页 CJK 占比分布（噪声页检测）
    ratios = []
    low_pages = []
    for n, b in pages:
        s = b.strip()
        if not s:
            continue
        r = len(CJK.findall(s)) / len(s)
        ratios.append(r)
        if r < 0.30:
            low_pages.append((n, round(r, 3)))
    ratios = np.asarray(ratios)
    print(f"\n每页 CJK 占比: min={ratios.min():.3f} 中位数={np.median(ratios):.3f} "
          f"均值={ratios.mean():.3f} max={ratios.max():.3f}")
    print(f"CJK<30% 的页(疑似图表/公式/参考文献): {len(low_pages)}/{len(ratios)} "
          f"({len(low_pages)/len(ratios):.1%})")
    print(f"  例: {low_pages[:15]}")

    # 可疑符号损坏（AI 只能给候选，不能定性）
    cand = {
        "'一'紧邻数字(疑似 = 误识)": len(re.findall(r"一\s*\d", txt)),
        "'十'紧邻数字(疑似 + 误识)": len(re.findall(r"十\s*\d", txt)),
        "'力'作单字出现(疑似 p 误识)": len(re.findall(r"(?<![力能动压])力(?![力气量场])", txt)),
        "全角括号 ）": txt.count("）"), "半角括号 )": txt.count(")"),
        "希腊/数学符号 Σ√≤≥±": sum(txt.count(c) for c in "Σ√≤≥±×÷"),
        "英文字母 p 出现次数": len(re.findall(r"(?<![A-Za-z])p(?![A-Za-z])", txt)),
    }
    print("\n-- 可疑符号统计（候选，需人工判定） --")
    for k, v in cand.items():
        print(f"  {k}: {v}")

    # 重复行（跨页重复，可能是页眉页脚未剥离）
    all_lines = [l.strip() for l in txt.splitlines() if l.strip()]
    dup = collections.Counter(all_lines)
    dup_lines = [(l, c) for l, c in dup.most_common(12) if c >= 10 and len(l) > 4]
    print("\n-- 高频重复行(>=10次) --")
    for l, c in dup_lines:
        print(f"  {c:>4}  {l[:56]}")

    # 目录结构（用于独立校验章节起始页）
    toc = [l.strip() for l in pages[3][1].splitlines() if CHAP_MARK.search(l)][:40]
    print("\n-- 目录页(PDF p4)含章名行 --")
    for l in toc[:20]:
        print("  ", l[:60])
    return pages


# ============================================================ 2. Chunking
def audit_chunk(pages):
    hr("2. Chunking 边界与完整性")
    d = pickle.load(open(INDEX, "rb"))
    chunks = d["chunks"]
    print(f"chunk 总数: {len(chunks)}   索引版本: {d['version']}   参数: {d['params']}")
    lens = np.asarray([len(c["text"]) for c in chunks])
    print(f"长度 min/中位/均值/max: {lens.min()} / {int(np.median(lens))} / "
          f"{lens.mean():.0f} / {lens.max()}")
    print(f"<300字: {(lens<300).sum()}   >900字: {(lens>900).sum()}")

    # 实际重叠（同页内相邻块）
    ov = []
    for i in range(len(chunks) - 1):
        a, b = chunks[i]["text"], chunks[i + 1]["text"]
        if chunks[i]["page_pdf"] != chunks[i + 1]["page_pdf"]:
            continue
        m = 0
        for L in range(min(len(a), len(b), 300), 0, -1):
            if a[-L:] == b[:L]:
                m = L
                break
        ov.append(m)
    if ov:
        print(f"同页相邻块实际重叠: 均值 {np.mean(ov):.0f} 中位 {int(np.median(ov))} "
              f"min {min(ov)} max {max(ov)}  n={len(ov)}")
    cross = sum(1 for i in range(len(chunks) - 1)
                if chunks[i]["page_pdf"] != chunks[i + 1]["page_pdf"])
    print(f"跨页相邻块对: {cross} 对（页内切分 → 跨页处【无重叠】，页边界知识点可能被切断）")

    # 分布
    bt = collections.Counter(c["block_type"] for c in chunks)
    print(f"\nblock_type 分布: {dict(bt)}")
    no_chap = sum(1 for c in chunks if not c["chapter_no"])
    no_sec = sum(1 for c in chunks if not c["section_no"])
    print(f"chapter_no 为空: {no_chap} ({no_chap/len(chunks):.1%})   "
          f"section_no 为空: {no_sec} ({no_sec/len(chunks):.1%})")

    # 跨小节 / 截断 / 噪声
    multi_sec = [c["chunk_id"] for c in chunks if len(SEC_MARK.findall(c["text"])) >= 2]
    truncated = [c["chunk_id"] for c in chunks
                 if c["text"].rstrip()[-1:] not in SENT_END and c["block_type"] == "prose"]
    print(f"\n含 >=2 个『第X节』（跨小节）的 chunk: {len(multi_sec)} 例 {multi_sec[:12]}")
    print(f"结尾非句末标点（疑似截断）的 prose chunk: {len(truncated)} "
          f"({len(truncated)/max(bt.get('prose',1),1):.1%} of prose) 例 {truncated[:10]}")

    # 页面覆盖：整页都被判 noise → 默认检索不可见
    by_page = collections.defaultdict(list)
    for c in chunks:
        by_page[c["page_pdf"]].append(c)
    invisible = [p for p, cs in by_page.items() if all(c["block_type"] == "noise" for c in cs)]
    print(f"\n全部 chunk 均为 noise（默认检索不可见）的页: {len(invisible)} 例 {sorted(invisible)[:20]}")
    no_chunk_pages = [n for n, b in pages if n not in by_page]
    print(f"未产生任何 chunk 的页: {len(no_chunk_pages)} 例 {no_chunk_pages[:10]}")

    # 抽样展示：原文 vs chunk
    print("\n-- 抽样：chunk 与所在页原文对照（前 3 个 prose chunk）--")
    shown = 0
    for c in chunks:
        if c["block_type"] != "prose" or not c["chapter_no"]:
            continue
        body = dict(pages)[c["page_pdf"]]
        print(f"\n[chunk_id={c['chunk_id']}] page_pdf={c['page_pdf']} "
              f"page_print={c['page_print']} path='{c['path']}' len={len(c['text'])}")
        print("--- 所在页原文（前 420 字）---")
        print(body.strip()[:420].replace("\n", " / "))
        print("--- chunk 内容（前 420 字）---")
        print(c["text"][:420].replace("\n", " / "))
        shown += 1
        if shown >= 3:
            break
    return d


# ============================================================ 3. Traceability
def audit_trace(pages, d):
    hr("3. 可追溯性：chunk -> 页 -> 源 TXT / 印刷页码 / 章节标签")
    chunks = d["chunks"]

    # 3.1 chunk 文本能否在源 TXT 对应页中原文命中
    page_body = dict(pages)
    cleaned = {n: "\n".join(clean_lines(b)) for n, b in pages}
    hit, hit_strip, miss = 0, 0, []
    for c in chunks:
        t = c["text"]
        base = cleaned.get(c["page_pdf"], "")
        if t in base:
            hit += 1
        elif t[100:] in base:      # 去掉人工拼接的 overlap 前缀后命中
            hit_strip += 1
        else:
            miss.append(c["chunk_id"])
    print(f"chunk 文本原文命中源页: 直接命中 {hit} + 去重叠前缀命中 {hit_strip} "
          f"= {hit+hit_strip}/{len(chunks)} ({(hit+hit_strip)/len(chunks):.1%})")
    print(f"未命中(清洗造成差异): {len(miss)} 例 {miss[:10]}")

    # 3.2 印刷页码映射
    print_map, n_ext = build_print_map(pages)
    diffs = collections.Counter()
    anchors = []
    for n, b in pages:
        p = extract_printed_page(b)
        if p is not None and 0 < n - p < 40:
            diffs[n - p] += 1
            if len(anchors) < 8:
                anchors.append((n, p, n - p))
    print(f"\n印刷页码锚点：直接提取 {n_ext} 页 / 共 {len(pages)} 页 "
          f"（其余为插值/DEFAULT 推测）")
    print(f"锚点样例 (PDF页, 印刷页, 差): {anchors}")
    print(f"(PDF页-印刷页) 差值分布 top6: {diffs.most_common(6)}")
    vals = [print_map[n] for n in sorted(print_map)]
    mono = all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1))
    jumps = [(n, print_map[n], print_map[sorted(print_map)[i + 1]])
             for i, n in enumerate(sorted(print_map)[:-1])
             if print_map[sorted(print_map)[i + 1]] - print_map[n] not in (0, 1)]
    print(f"映射单调不减: {mono}   非 +1 跳变处: {len(jumps)} 例 {jumps[:10]}")
    print("注意：差值并非恒为 13；前 15 页与末段靠 DEFAULT(max(n-13,1)) 兜底 → "
          "【印刷页码为推断值，非人工核对真值】")

    # 3.3 章节标签 vs 页眉真值（同源方法 → 只能查自洽，不能查正确性）
    truth, cur = {}, None
    for n, b in pages:
        for l in b.splitlines():
            if l.strip():
                m = CHAP_MARK.match(l.strip())
                if m:
                    cur = m.group(0)
                break
        truth[n] = cur
    bad = [(c["chunk_id"], c["page_pdf"], c["chapter_no"], truth.get(c["page_pdf"]))
           for c in chunks
           if truth.get(c["page_pdf"]) and c["chapter_no"]
           and c["chapter_no"] != truth[c["page_pdf"]]]
    print(f"\nchunk.chapter_no 与【页眉推真值】不一致: {len(bad)} 例 {bad[:6]}")
    print("（页眉本身来自 OCR，故此比对只能证明自洽，不能证明章节归属正确）")

    # 3.4 章节起始页：目录 vs 页眉（独立信号交叉校验）
    toc_page = dict(pages).get(4, "") + dict(pages).get(5, "")
    toc_lines = [l.strip() for l in toc_page.splitlines() if CHAP_MARK.search(l)]
    print("\n-- 目录行（含章名，若带页码则可独立校验）--")
    for l in toc_lines[:16]:
        print("  ", l[:70])
    return chunks


# ============================================================ 4. Embedding
def audit_embed():
    hr("4. Embedding 实际执行证据")
    q = ["什么是调节效应？", "聚类分析", "今天天气怎么样"]
    v = embed_texts(q)
    n = np.linalg.norm(v, axis=1)
    print(f"模型: {EMBED_MODEL}  实际输出 shape={v.shape}  L2 范数={np.round(n,4).tolist()}")
    cos = v @ v.T
    print(f"自相似矩阵对角={np.round(np.diag(cos),3).tolist()}")
    print(f"cos(调节效应?, 聚类分析)={cos[0,1]:.4f}  cos(调节效应?, 天气)={cos[0,2]:.4f}")
    print("→ 证明：Embedding 真实执行且向量可用（但【是否适配本教材】需人工/实验验证）")
    print(f"BM25 分词示例 tokenize('RMSEA 指标') = {tokenize('RMSEA 指标')}")


# ============================================================ 5. Retrieval
# 36 题：(问题, 类别, 期望章节号 or None(教材外), [词法关键词])
CH = {1: "第一章", 2: "第二章", 3: "第三章", 4: "第四章", 5: "第五章", 6: "第六章",
      7: "第七章", 8: "第八章", 9: "第九章", 10: "第十章", 11: "第十一章",
      12: "第十二章", 13: "第十三章", 14: "第十四章"}

CASES = [
    ("教材里聚类分析介绍了哪几种距离？", "事实", 6, ["距离", "欧氏", "明科夫斯基"]),
    ("多元回归分析的前提假设有哪些？", "事实", 3, ["假设"]),
    ("第十二章主要讲什么内容？", "事实", 12, ["调节效应"]),
    ("验证性因素分析中模型识别分为哪几种情况？", "事实", 8, ["识别"]),
    ("Logistic 回归适用于什么类型的因变量？", "事实", 4, ["Logistic", "logistic", "因变量"]),
    ("什么是调节效应？", "定义", 12, ["调节效应"]),
    ("什么是中介效应？", "定义", 11, ["中介效应"]),
    ("什么是验证性因素分析？", "定义", 8, ["验证性因素分析", "验证性因子"]),
    ("什么是探索性因素分析？", "定义", 7, ["探索性因素分析", "探索性因子"]),
    ("什么叫零模型？", "定义", 13, ["零模型"]),
    ("结构方程模型适合解决什么问题？", "解释", 10, ["结构方程模型"]),
    ("聚类分析主要回答什么问题？", "解释", 6, ["聚类分析"]),
    ("多层线性模型适合分析什么样的数据？", "解释", 13, ["多层线性模型", "嵌套"]),
    ("路径分析的作用是什么？", "解释", 9, ["路径分析"]),
    ("判别分析有什么用途？", "解释", 5, ["判别分析"]),
    ("探索性因素分析和验证性因素分析有什么区别？", "比较", None, ["探索性因素分析", "验证性因素分析"]),
    ("中介效应和调节效应有什么区别？", "比较", None, ["中介效应", "调节效应"]),
    ("一元方差分析和多元方差分析的区别是什么？", "比较", 2, ["多元方差分析"]),
    ("判别分析和聚类分析有什么不同？", "比较", None, ["判别分析", "聚类分析"]),
    ("为什么要检验调节效应？", "因果", 12, ["调节效应"]),
    ("为什么异常值会影响回归分析的结果？", "因果", 3, ["异常值"]),
    ("为什么聚类分析的结果需要研究者主观判断？", "因果", 6, ["聚类分析", "主观"]),
    ("为什么要用 Bootstrap 检验中介效应？", "因果", 11, ["Bootstrap"]),
    ("使用结构方程模型的步骤有哪些？", "跨段落", 10, ["结构方程模型"]),
    ("应用聚类分析时要注意哪些会影响结果的因素？", "跨段落", 6, ["聚类分析"]),
    ("数据里有缺失值和极端值，分析前应该先做什么？", "跨段落", 1, ["缺失值"]),
    ("调节效应和多层线性模型分别适用于什么研究问题？", "跨章节", None, ["调节效应", "多层线性模型"]),
    ("中介分析和路径分析有什么联系？", "跨章节", None, ["中介", "路径分析"]),
    ("RMSEA 是什么指标？", "术语", 10, ["RMSEA"]),
    ("简单斜率检验是什么？", "术语", 12, ["简单斜率"]),
    ("乘积指标法是如何操作的？", "术语", 12, ["乘积指标"]),
    ("我想考察压力对抑郁的影响，并想知道社会支持是否会减弱这种影响，该用什么统计方法、具体步骤是什么？", "长问题", 12, ["调节效应"]),
    ("如果一个变量通过另一个变量影响结果，这个过程叫什么，用什么方法检验？", "改写表达", 11, ["中介"]),
    ("调节效应", "短问题", 12, ["调节效应"]),
    ("聚类分析", "短问题", 6, ["聚类分析"]),
    ("这本教材里讲怎么用 Python 做深度学习吗？", "教材外", None, []),
]


def audit_retrieve():
    hr("5. 检索证据级评测（36 题 × Top10，双判据）")
    print("判据 A（结构判据）：top-K 中存在 chapter_no == 期望章 的 chunk → 命中")
    print("判据 B（词法代理）：top-K 中存在含关键词的 chunk → 命中（弱，参考用）")
    print("期望章由【审计者依据教材目录结构人工指定】—— 未经教材原书逐条核对 → "
          "GROUND TRUTH UNVERIFIED\n")
    rows = []
    ra = collections.Counter()
    rb = collections.Counter()
    mrr_a = 0.0
    for q, cat, exp_ch, terms in CASES:
        res = retrieve(q, k=10)
        want = CH.get(exp_ch) if exp_ch else None
        rank_a = next((r["rank"] for r in res
                       if want and r["chapter_no"].startswith(want)), None)
        rank_b = next((r["rank"] for r in res
                       if terms and any(t in r["text"] for t in terms)), None)
        for kk in (1, 3, 5, 10):
            if rank_a and rank_a <= kk:
                ra[kk] += 1
            if rank_b and rank_b <= kk:
                rb[kk] += 1
        if rank_a:
            mrr_a += 1.0 / rank_a
        t1 = res[0]
        rows.append((cat, q, want or "-", rank_a, rank_b,
                     t1["page_print"], t1["sim"], t1["dense_rank"], t1["bm25_rank"],
                     t1["chapter_no"] or "-", t1["text"][:34].replace("\n", " ")))

    print(f"{'类别':<6}{'期望章':<7}{'A秩':<5}{'B秩':<5}{'P1页':<6}{'sim':<7}"
          f"{'dense':<7}{'bm25':<6}  top1章节/内容")
    for cat, q, want, ra_, rb_, pg, sim, dr, br, ch1, prev in rows:
        print(f"{cat:<6}{want:<7}{str(ra_ or '-'):<5}{str(rb_ or '-'):<5}"
              f"{str(pg):<6}{sim:<7.4f}{str(dr):<7}{str(br):<6} {ch1} {prev}")
        print(f"       Q: {q[:60]}")

    n = len(CASES)
    print(f"\n判据 A（结构/章节级）: R@1={ra[1]}/{n}={ra[1]/n:.3f}  R@3={ra[3]/n:.3f}  "
          f"R@5={ra[5]/n:.3f}  R@10={ra[10]/n:.3f}  MRR={mrr_a/n:.3f}")
    print(f"判据 B（词法代理）  : R@1={rb[1]}/{n}={rb[1]/n:.3f}  R@3={rb[3]/n:.3f}  "
          f"R@5={rb[5]/n:.3f}  R@10={rb[10]/n:.3f}")

    # 教材外问题：检索是否会给出高相似度无关片段（幻觉风险信号）
    print("\n-- 教材外问题：检索层是否仍给高分（若接了 LLM，易触发幻觉） --")
    for q in ["这本教材里讲怎么用 Python 做深度学习吗？",
              "量子纠缠在心理学中如何应用？",
              "本书对 ChatGPT 有哪些论述？",
              "2024 年心理学最新研究方法有哪些？"]:
        res = retrieve(q, k=3)
        print(f"  Q: {q}")
        for r in res[:3]:
            print(f"     #{r['rank']} sim={r['sim']:.4f} p{r['page_print']} "
                  f"{r['chapter_no'] or '-'} | {r['text'][:40].replace(chr(10),' ')}")
    return rows


def main():
    pages = audit_ocr()
    d = audit_chunk(pages)
    audit_trace(pages, d)
    audit_embed()
    audit_retrieve()
    hr("审计脚本结束（只读，未修改任何数据/索引/代码）")


if __name__ == "__main__":
    main()
