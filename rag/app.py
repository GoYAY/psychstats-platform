#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
app.py  v2 —— 本地 RAG 检索 + 问答 Web 应用

v2 变更（依据审计报告）：
  [CRITICAL] 引用改用【教材印刷页码】（page_print），并同时显示 PDF 页，解决 13 页偏差
  [MEDIUM]  Prompt 强化：禁自身知识 / 空上下文拒答 / 禁编造页码 / 冲突处理 / 超范围说明
  [LOW]     RAG Debug 面板：展示 dense_rank / bm25_rank / RRF / 章节路径 / block_type / 索引新鲜度
  [LOW]     Top-K 默认 4 -> 6

生成环节（LLM）仍为可插拔：安装 Ollama 并 `ollama pull qwen2.5:7b` 后自动启用。
"""
import os
from flask import Flask, request, jsonify, Response

from rag_core import (INDEX_PATH, EMBED_MODEL, retrieve, load_index,
                      index_status, EXPECTED_CHUNK_VER)

# 本机实际可用的模型：Qwen2.5-3B-Instruct(Q4_K_M) 经 GGUF 导入 Ollama
# （registry.ollama.ai 被限速 45KB/s，无法直接 ollama pull，改从 hf-mirror 导入）
LLM_MODEL = os.environ.get("RAG_LLM", "qwen2.5:3b")
TOP_K = int(os.environ.get("RAG_TOP_K", "6"))

app = Flask(__name__)


def llm_status():
    try:
        import ollama
        ollama.Client().list()
        return {"available": True, "mode": "ollama", "model": LLM_MODEL}
    except Exception:
        return {"available": False, "mode": None, "model": None}


# ---------- Prompt（审计后强化） ----------
PROMPT_TMPL = """你是《高级心理统计》教材的问答助手。你的回答【只能】依据下面给出的【教材参考片段】。

严格规则：
1. 只能使用【教材参考片段】中的信息作答。禁止使用你自己的知识、经验或推测来补充教材内容。
2. 如果【教材参考片段】为空，或其中没有任何与问题相关的信息，你必须只回答这一句：
   「教材中未直接提及该内容，我无法依据教材回答。」
   不要尝试用常识回答，也不要部分作答。
3. 引用时只能使用片段前标注的页码（形如「教材第X页」），禁止编造任何页码、章节号、表号或公式编号。
4. 若多个片段的信息相互冲突，请明确指出存在不同说法并分别标注来源，不要自行选择其中一种。
5. 若学生要求教材之外的知识，先说明这超出本书范围，再仅就教材内容作答。
6. 用通俗、有条理的中文回答，必要时分点说明；涉及公式时保留原文写法并标注所在页。

【教材参考片段】
{context}

【学生问题】
{question}
"""


def generate(question, sources):
    context = "\n\n".join(
        f"({s['rank']}) [教材第{s.get('page_print', s.get('page'))}页] {s['text']}"
        for s in sources
    )
    prompt = PROMPT_TMPL.format(context=context, question=question)
    import ollama
    resp = ollama.Client().generate(model=LLM_MODEL, prompt=prompt, stream=False)
    return resp["response"].strip()


@app.route("/")
def index():
    return Response(PAGE_HTML, mimetype="text/html")


@app.route("/api/ask", methods=["POST"])
def api_ask():
    body = request.get_json(force=True, silent=True) or {}
    q = (body.get("q") or "").strip()
    if not q:
        return jsonify({"error": "请输入问题"}), 400
    try:
        include_noise = bool(body.get("include_noise"))
        sources = retrieve(q, k=TOP_K, mode="hybrid", include_noise=include_noise)
        answer, no_llm = "", False
        if not body.get("retrieve_only"):
            if llm_status()["available"]:
                answer = generate(q, sources)
            else:
                no_llm = True
        return jsonify({
            "question": q, "answer": answer, "no_llm": no_llm,
            "sources": sources,
            "debug": {"top_k": TOP_K, "mode": "hybrid",
                      "include_noise": include_noise,
                      "embed_model": EMBED_MODEL,
                      "returned": len(sources)},
        })
    except Exception as e:
        return jsonify({"error": f"处理失败：{e}"}), 500


@app.route("/api/health")
def api_health():
    try:
        idx = load_index()
        return jsonify({
            "index_blocks": len(idx["chunks"]),
            "embed_model": idx["meta"].get("embed_model"),
            "chunk_ver": idx["meta"].get("version"),
            "expected_chunk_ver": EXPECTED_CHUNK_VER,
            "index_status": idx["status"],
            "llm": llm_status(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status")
def api_status():
    try:
        return jsonify(index_status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- 前端（浅色主题，单文件） ----------
PAGE_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>高级心理统计 · 本地 RAG</title>
<style>
  :root{ --bg:#f6f7f9; --panel:#fff; --border:#e3e6ea; --text:#1f2329; --muted:#6b7280; --brand:#2f6feb; --brand-soft:#eaf1ff; --warn:#b26a00; --warn-soft:#fff4e0; --ok:#0f9d58; }
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text);}
  header{padding:16px 22px;border-bottom:1px solid var(--border);background:var(--panel);display:flex;align-items:center;gap:12px;flex-wrap:wrap;}
  header h1{font-size:18px;margin:0;}
  header .sub{color:var(--muted);font-size:13px;}
  .wrap{max-width:920px;margin:0 auto;padding:20px 16px 60px;}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:16px;}
  textarea{width:100%;min-height:64px;resize:vertical;padding:12px;border:1px solid var(--border);border-radius:10px;font-size:15px;font-family:inherit;background:#fff;}
  button{cursor:pointer;border:none;border-radius:10px;padding:11px 18px;font-size:14px;font-weight:600;background:var(--brand);color:#fff;white-space:nowrap;}
  button:disabled{opacity:.5;cursor:not-allowed;}
  button.ghost{background:var(--brand-soft);color:var(--brand);}
  .opts{display:flex;gap:16px;align-items:center;margin-top:10px;color:var(--muted);font-size:13px;flex-wrap:wrap;}
  .opts label{display:flex;gap:6px;align-items:center;cursor:pointer;}
  .answer{line-height:1.75;font-size:15.5px;white-space:pre-wrap;}
  .banner{background:var(--warn-soft);border:1px solid #f0d9a8;color:var(--warn);padding:10px 12px;border-radius:8px;font-size:13.5px;margin-top:10px;line-height:1.6;}
  .src{border-left:3px solid var(--brand);background:var(--brand-soft);padding:10px 12px;border-radius:6px;margin-top:10px;font-size:13.5px;color:#283042;}
  .src .meta{color:var(--muted);font-size:12px;margin-bottom:4px;font-family:ui-monospace,Menlo,Consolas,monospace;}
  .src .txt{white-space:pre-wrap;max-height:170px;overflow:auto;}
  .tag{display:inline-block;background:#fff;border:1px solid var(--border);border-radius:999px;padding:2px 10px;font-size:12px;color:var(--muted);}
  .hint{color:var(--muted);font-size:13px;line-height:1.7;}
  .spinner{display:inline-block;width:14px;height:14px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:spin .7s linear infinite;vertical-align:-2px;margin-right:6px;}
  @keyframes spin{to{transform:rotate(360deg)}}
  code{background:#eef1f5;padding:1px 5px;border-radius:4px;font-size:13px;}
</style>
</head>
<body>
<header>
  <h1>📚 高级心理统计 · 本地 RAG</h1>
  <span class="sub">混合检索（语义 + BM25）· 引用为教材印刷页码 · 零 token</span>
</header>
<div class="wrap">
  <div class="card">
    <textarea id="q" placeholder="例如：什么是调节效应？聚类分析要注意哪些因素？RMSEA 是什么指标？"></textarea>
    <div style="margin-top:12px;display:flex;gap:10px;">
      <button id="askBtn" onclick="ask()">检索 / 提问</button>
      <button class="ghost" id="exportBtn" onclick="exportMd()" disabled>导出 Markdown（含来源）</button>
    </div>
    <div class="opts">
      <label><input type="checkbox" id="retrieveOnly"/> 仅检索（不调用大模型）</label>
      <label><input type="checkbox" id="incNoise"/> 包含表格/数字片段</label>
      <span id="status" class="tag">就绪</span>
    </div>
  </div>

  <div class="card" id="indexWarn" style="display:none;"></div>

  <div class="card" id="answerCard" style="display:none;">
    <div class="answer" id="answer"></div>
    <div id="banner"></div>
    <div id="sources"></div>
  </div>

  <div class="card">
    <div class="hint">
      <b>说明</b><br/>
      • <b>引用页码</b>为教材印刷页码（如「教材第84页」），括号内为 PDF 页，两者相差约 12–13 页。<br/>
      • 检索为<b>混合检索</b>（语义 + BM25 关键词，RRF 融合），默认过滤纯表格/数字片段；勾选「包含表格/数字片段」可放开。<br/>
      • 每条来源下方为 RAG Debug 信息：dense 排名、bm25 排名、RRF 分值、章节路径。<br/>
      • 公式与符号在 OCR 中损坏较多，涉及具体数值/公式请回到原书核对。
    </div>
  </div>
</div>

<script>
let lastData = null;
async function ask(){
  const q = document.getElementById('q').value.trim();
  if(!q){ alert('请输入问题'); return; }
  const btn = document.getElementById('askBtn');
  const status = document.getElementById('status');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>检索中';
  status.textContent = '检索中…';
  try{
    const resp = await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({q,
        retrieve_only: document.getElementById('retrieveOnly').checked,
        include_noise: document.getElementById('incNoise').checked})});
    const data = await resp.json();
    if(data.error){ status.textContent='出错'; alert(data.error); return; }
    lastData = data; render(data);
    document.getElementById('exportBtn').disabled = false;
    status.textContent = '完成';
  }catch(e){ status.textContent='网络错误'; alert('请求失败：'+e); }
  finally{ btn.disabled=false; btn.textContent='检索 / 提问'; }
}
function render(data){
  document.getElementById('answerCard').style.display='block';
  const ans=document.getElementById('answer'), banner=document.getElementById('banner'), src=document.getElementById('sources');
  banner.innerHTML='';
  if(data.answer){ ans.style.display='block'; ans.textContent=data.answer; } else { ans.style.display='none'; }
  if(data.no_llm){
    banner.innerHTML='<div class="banner">⚠️ 未检测到本地生成模型（Ollama）。已检索到下列教材片段；'+
      '如需自动生成答案，请安装 Ollama 并拉取 <code>qwen2.5:7b</code>，或接入云端 LLM。</div>';
  }
  src.innerHTML='<div style="margin-top:14px;color:var(--muted);font-size:13px;">📎 命中来源（'+data.sources.length+' 段）</div>';
  data.sources.forEach(s=>{
    const d=document.createElement('div'); d.className='src';
    const meta='#'+s.rank+' · 教材第'+s.page_print+'页 (PDF '+s.page_pdf+')'
      +(s.path?(' · '+s.path):'')+' · 相似度 '+s.sim
      +' · dense#'+(s.dense_rank||'-')+' bm25#'+(s.bm25_rank||'-')
      +' · rrf '+s.score+' · '+s.block_type;
    d.innerHTML='<div class="meta">'+meta+'</div><div class="txt">'+escapeHtml(s.text)+'</div>';
    src.appendChild(d);
  });
}
function escapeHtml(t){return t.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function exportMd(){
  if(!lastData) return;
  const md=[];
  md.push('# 高级心理统计 · RAG 检索导出');
  md.push('');
  md.push('## 问题');
  md.push(lastData.question);
  md.push('');
  if(lastData.answer){ md.push('## 回答（本地大模型生成）'); md.push(lastData.answer); md.push(''); }
  md.push('## 命中教材片段');
  lastData.sources.forEach(s=>{
    md.push('### 片段 #'+s.rank+'（教材第'+s.page_print+'页 / PDF '+s.page_pdf+'页'
      +(s.path?(' · '+s.path):'')+'，相似度 '+s.sim+'）');
    md.push('');
    md.push(s.text.split('\\n').map(x=>'> '+x).join('\\n'));
    md.push('');
  });
  md.push('---');
  md.push('*本地 RAG（bge-small-zh-v1.5 + BM25 混合检索）生成，零 token。*');
  const blob=new Blob([md.join('\\n')],{type:'text/markdown;charset=utf-8'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='rag_导出_'+Date.now()+'.md'; a.click();
}
fetch('/api/health').then(r=>r.json()).then(h=>{
  if(h.index_status && !h.index_status.fresh){
    const w=document.getElementById('indexWarn');
    w.style.display='block';
    w.innerHTML='<div class="banner">⚠️ 索引一致性检查未通过：<br/>'+
      (h.index_status.issues||[]).map(x=>'· '+x).join('<br/>')+
      '<br/>请重新运行 <code>python build_index.py</code>。</div>';
  }
});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    port = int(os.environ.get("RAG_PORT", "5000"))
    st = index_status()
    print(f"本地 RAG 启动中：http://127.0.0.1:{port}")
    print(f"  索引: {INDEX_PATH}")
    print(f"  块数={st.get('blocks')} 嵌入={EMBED_MODEL} chunk_ver={st.get('version')}")
    print(f"  索引新鲜度: {'OK' if st.get('fresh') else st.get('issues')}")
    print(f"  生成模型: Ollama({LLM_MODEL}) 当前可用={llm_status()['available']}")
    app.run(host="127.0.0.1", port=port, debug=False)
