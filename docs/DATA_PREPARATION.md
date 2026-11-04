# 材料准备与 OCR 知识库

教材知识库由原材料、OCR文本、页码/章节映射、切块和检索索引组成。本仓库保存处理代码，教材和索引由使用者在本地建立。

## 单份 PDF 转文本

在独立 Python 环境安装 `pymupdf`、`rapidocr-onnxruntime` 后：

```powershell
python ocr/skill/pdf_ocr.py "自己的材料.pdf" -o "自己的材料.txt"
```

扫描质量会影响识别，公式和表格需人工抽查。OCR Skill 中历史环境路径应替换为自己的解释器；无需创建原作者机器上的目录。

## 建立检索索引

`rag/build_index.py` 使用带 `=== 第 N 页 ===` 标记的文本；先检查文本格式，再执行：

```powershell
python rag/build_index.py --help
python rag/build_index.py --src "自己的带页码文本.txt"
```

依赖涉及 `numpy`、`fastembed`。嵌入模型由 `rag/rag_core.py` 指定，首次使用可能需要下载；本地索引默认写入 `rag/rag_data/index.pkl`，不提交到仓库。

`rag/app.py` 还包含历史问答入口，服务依赖应按其实际导入配置；首次启动前核对是否启用模型调用。

## 课程材料分支

原开发目录中的课程 PDF、课程页图片、`site/content/course_manifest.json` 与 `site/materials/` 未复制。需要该分支时，使用自己的材料查看 `tools/ingest_course_pdfs.py --help`，再按工具要求生成清单和资源。

自行创建的文本、向量索引和课程页资源保持在本地；拥有明确分享许可后再决定分发范围。

材料与索引路径可通过环境变量配置，见[可移植路径说明](PORTABILITY.md)。
