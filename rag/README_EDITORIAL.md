# 术语页生产用RAG候选入口

用于建站时准备术语资料包。当前网站页面不因本入口而改变；原来的`rag_multi.py`和三个索引保留。

## 优化二版逐要点核验

`editorial_semantic.py` 是可选的编辑期入口，用明确问题和所需信息点准备一份教材资料。它从长块与短块两路各取最多 24 条候选，再补读短块所在页。DeepSeek 核验每个要点能否由候选直接回答，程序核对摘录并在 3,000 字符内优先选互补证据。返回的 `assessments` 说明各要点的判断，`priority_ids` 标记优先选入的原文，`contexts` 保留出处。其余位置仍可能有背景段落，编辑可据引文继续查证。

先按[数据准备说明](../docs/DATA_PREPARATION.md)准备本地索引和 BGE 嵌入模型。该入口使用项目现有 `DEEPSEEK_API_KEY` 配置，向 DeepSeek 发送问题、要点名称与候选原文。公式用下方的 `--field formula` 入口取已核验外部证据。

```powershell
python -X utf8 rag/editorial_semantic.py manova `
  --question "经典多元方差分析的推断需要哪些基本假设？" `
  --point "观测之间的关系" --point "各组协方差的要求" --point "因变量联合分布的要求"
```

[旧版与优化二版离线对照](../docs/reports/editorial-rag-evaluation.md)

## 内容分工

| 内容 | 提供者 | 交付方式 |
|---|---|---|
| 术语发现、定义、操作解释、通俗解释的事实依据 | 高级教材、讲义、基础教材RAG | 原混合排序为主，短子块与同页上下文补充，附PDF页码和提取方法 |
| 假设、适用条件、易混点 | RAG优先；外部资料补充缺口或纠正问题表述 | 原始证据与独立科学审查意见分字段 |
| 公式、变量含义、数学适用条件 | `editorial_sources.json`中的已审权威外部资料 | 直接交付公式证据卡及链接；不引用OCR残缺公式 |
| 固定效应、Pearson卡方的核心定义补充 | `editorial_concepts.json` | 明确语境、条件和权威链接 |
| 图示 | 原页或权威资料提供关系，建站模型负责绘制 | 绘制后检查轴、单位、关系和数值 |
| 比喻、教学案例和页面措辞 | 建站模型组织 | 标明示例，不反向冒充教材事实 |

评测按 90 项文字、22 项公式记录责任。80 项文字以教材为主，6 项使用教材加外部概念卡，4 项用已审外部资料补充。汇总与例子见 [教材 RAG 质量复核](../docs/reports/editorial-rag-evaluation.md)。

## 使用

在项目根目录准备 `numpy`、`fastembed` 和 `pymupdf`。基于自己有权使用的 PDF 和 OCR 文本，按[材料准备指南](../docs/DATA_PREPARATION.md)生成三个本地索引。讲义先执行 `tools/ingest_course_pdfs.py` 生成清单和本地提取文本，再执行 `rag/build_index_course.py`。基础教材用 `rag/build_index_basic.py --pdf`，高级教材用 `rag/build_index.py --src`。

本入口读取 `rag/rag_data/index.pkl`、`index_basic.pkl` 和 `index_course.pkl`。高级教材 PDF 默认在 `data/高级心理统计.pdf`，基础教材 PDF 默认在 `data/basic-textbook.pdf`。课程清单默认在 `site/content/course_manifest.json`，清单中的相对 PDF 路径默认从仓库根目录解释。已登记错误规则以开发评测使用的文档 ID、页码和原文为定位条件。更换教材或版本时，需要按新材料重新核查这些定位条件。

```powershell
# 构建独立候选索引；原索引不会覆盖
python -X utf8 rag/build_editorial_index.py --advanced-pdf data/高级心理统计.pdf --basic-pdf data/basic-textbook.pdf

# 给建站模型的完整资料包：RAG文字证据与外部公式分开
python -X utf8 rag/editorial_rag.py p-value --package

# 单独取得经过外部核查的公式与条件
python -X utf8 rag/editorial_rag.py partial-eta-squared --field formula

# 只取文字证据，设置上下文字符预算
python -X utf8 rag/editorial_rag.py "多变量异常值" --budget 9000

# 诊断检索排序：额外输出经过过滤的子块和锚点
python -X utf8 rag/editorial_rag.py manova --diagnostics

# 本轮新增回归测试与原RAG测试
python -X utf8 -m unittest tests.test_editorial_rag tests.test_editorial_rerank -v
```

`--course-manifest` 和 `--course-pdf-dir` 可指定本地讲义清单与 PDF 根目录。对应环境变量为 `PSY_STATS_COURSE_MANIFEST` 和 `PSY_STATS_COURSE_PDF_DIR`。本地构建输出 `rag/rag_data/editorial_candidate.pkl`，审计文件默认写入 `outputs/editorial-rag-local/`。索引、输入材料和审计原文由使用者保存在本地。

在 Python 中可按用途取出文字与公式。

```python
from editorial_rag import EditorialRetriever, model_payload, external_evidence

retriever = EditorialRetriever()
diagnostic_result = retriever.retrieve("p-value", context_budget=9000)
text_evidence = model_payload(diagnostic_result)
formula_evidence = external_evidence("p-value")
```

建站模型接收 `model_payload` 生成的实际上下文。9000 字符预算约束 RAG 正文，外部公式、审查意见及引用元数据使用独立字段。

## 提取、切块与检索

- 直接读取PDF文字层，使用内容流顺序，避免按全页纵坐标排序将邻栏文字交错。文字层不足时回退已有OCR，保留来源方法。
- 《高级心理统计》433页没有文字层，继续使用可追溯的现有OCR；扫描公式与图结构由外部证据负责。
- 默认按句/行切块，目标420字符、上限700字符，短句尾部重叠上限80字符；不跨页、不跨文档。
- 使用同一BGE模型重新编码子块，与BM25做RRF融合；通用查询覆盖术语、定义和前提，不写入测试答案或指定证据位置。
- 主列表保留经过知识过滤的原三源混合排序，移除问题片段后由短子块补足数量。纯短子块主排序的保留集首测结果单独留档。
- 过滤目录、代码和缺少解释内容的片段，英文定义保留。独立知识审查登记的问题按页内区间隔离，覆盖跨子块边界。
- 保留经过知识过滤的原Top-8证据作为锚点，再补充新片段的同页上下文。已知问题在子块、锚点和父页扩展三个入口执行相同检查。
- 给正文设预算时，截取后的文字再次通过过滤，避免输出只剩几个字的片段。有适用条件需要说明的内容使用 `editorial_quality_notes.json` 随证据交付。

## 复测记录

公开 [评测报告](../docs/reports/editorial-rag-evaluation.md) 和 [汇总数据](../docs/reports/editorial-rag-metrics.json) 记录 30 个开发术语与后续新词评审的结果。

每条相关性标注绑定术语和返回片段，供计算P@1/3/5/8、Hit@k与MRR。已核验证据组的机械覆盖另行计算，作为充分证据覆盖下界。正文、公式和来源配置的任务范围分列。

## 重排与术语关系实验

`editorial_rerank.py` 提供独立的本地入口。同一排序同时考虑长块和短块，`--relations` 会从已有术语草稿取一条与字段相关的边，并把补查结果放到同一个候选池。常规建站入口仍是 `editorial_rag.py`。

```powershell
python -X utf8 rag/editorial_rerank.py "优势比" --diagnostics
python -X utf8 rag/editorial_rerank.py "测量模型" --relations --diagnostics
python -X utf8 rag/editorial_rerank.py "p 值" --package
```

指标、执行结果和策略取舍见 [教材 RAG 质量复核](../docs/reports/editorial-rag-evaluation.md)。
