---
name: scanned-pdf-ocr
description: 扫描版PDF批量OCR转文本。使用 rapidocr-onnxruntime 本地识别中文，零 token 消耗、完全离线、隐私安全。当用户提到 OCR、识别扫描件、提取PDF文字、扫描版转文本、批量OCR、本地OCR 时触发。
---

# 扫描版 PDF 批量 OCR（本地 / 零 token）

把扫描版（图片型）PDF 转成可搜索、可复制的纯文本。基于 PyMuPDF 渲染 +
RapidOCR 本地 ONNX 推理，全程离线、不消耗任何积分。

## 触发词
OCR、识别扫描件、提取PDF文字、扫描版转文本、批量OCR、本地OCR

## 前置依赖
- 使用自己的 Python 环境，安装 `pymupdf` 和 `rapidocr-onnxruntime`：
  `python -m pip install pymupdf rapidocr-onnxruntime`
- 脚本位于本 skill 目录：`pdf_ocr.py`（单文件）、`batch_ocr.py`（批量）

## 运行方式（由 WorkBuddy 执行）
1. 确定目标 PDF 或目录（用户随口给路径即可，支持中文路径）。
2. 单文件：
   `python pdf_ocr.py "<pdf路径>" -d 300`
   可选 `-o <输出路径>` 指定 txt 落点。
3. 批量（递归子目录，自动跳过已生成的 txt；`-f` 强制重跑）：
   `python batch_ocr.py "<目录>" -d 300`

## 关键注意
- 首次运行 RapidOCR 会从 HuggingFace 下载一次模型权重（约 10–15MB），
  之后断网也能用。若下载失败，提示用户挂代理或手动下载权重到缓存目录。
- Windows 已通过 `PYTHONUTF8=1` 处理中文路径。
- dpi 默认 200；扫描质量差/倾斜时提到 250~300 更准。
- 表格类 PDF 文本顺序可能乱（OCR 不保表格结构）；纯文本提取够用，
  需表格结构可后续接 pandas 二次规整。
- 空白页识别出空字符串属正常，脚本已容错不会报错。

## 进阶（可选）
- 想输出 Word：把 `pdf_to_text` 写文件部分换成 python-docx 写入 .docx。
- 想走 GPU 加速：换 rapidocr_onnxruntime 的 CUDA 构建或 Paddle 原版推理。
