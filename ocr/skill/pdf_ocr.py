import os
import re
import sys
import time
import argparse
import tempfile
import shutil
import fitz  # PyMuPDF
from rapidocr_onnxruntime import RapidOCR

# Windows 中文路径保护
os.environ.setdefault("PYTHONUTF8", "1")

PAGE_RE = re.compile(r"=== 第 (\d+) 页 ===")


def _done_pages(output_path: str) -> int:
    """统计输出文件里已写到的最后一页页码，用于断点续跑。"""
    if not os.path.exists(output_path):
        return 0
    n = 0
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            m = PAGE_RE.search(line)
            if m:
                n = max(n, int(m.group(1)))
    return n


def pdf_to_text(pdf_path: str, output_path: str, dpi: int = 200, start_page: int = 0, ocr=None):
    """把扫描版 PDF 识别成纯文本文件（逐页流式写入，支持断点续跑）。

    - 用 PyMuPDF 把每一页渲染成图片
    - 用 RapidOCR（本地 ONNX 推理）识别文字
    - 全程离线、零 token 消耗
    - start_page>0 时以追加模式续写，跳过已完成的页
    """
    doc = fitz.open(pdf_path)
    tmp_dir = tempfile.mkdtemp(prefix="ocr_")
    try:
        if ocr is None:
            ocr = RapidOCR()  # 首次会下载/加载本地模型权重
        mode = "a" if start_page > 0 else "w"
        with open(output_path, mode, encoding="utf-8") as f:
            for page_num in range(start_page, len(doc)):
                t0 = time.time()
                page = doc[page_num]
                pix = page.get_pixmap(dpi=dpi)
                tmp_img = os.path.join(tmp_dir, f"p{page_num}.png")
                pix.save(tmp_img)
                result, _ = ocr(tmp_img)  # result: [(box, text, score), ...]
                text = "\n".join(line[1] for line in result) if result else ""
                f.write(f"=== 第 {page_num + 1} 页 ===\n{text}\n\n")
                f.flush()
                os.remove(tmp_img)
                print(f"[第 {page_num + 1}/{len(doc)} 页] 用时 {time.time() - t0:.1f}s", flush=True)
    finally:
        doc.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"[完成] {pdf_path} -> {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="扫描版 PDF 本地 OCR 提取（零 token）")
    parser.add_argument("pdf", help="输入 PDF 路径")
    parser.add_argument("-o", "--output", default=None, help="输出 txt 路径（默认同名）")
    parser.add_argument("-d", "--dpi", type=int, default=200, help="渲染清晰度，默认 200")
    parser.add_argument("-f", "--force", action="store_true", help="强制重跑（忽略已有进度，从头写）")
    args = parser.parse_args()
    out = args.output or (args.pdf[:-4] + ".txt")

    start = 0 if args.force else _done_pages(out)
    if start > 0:
        print(f"[续跑] 检测到已完成 {start} 页，从第 {start + 1} 页继续", flush=True)
    pdf_to_text(args.pdf, out, dpi=args.dpi, start_page=start)


if __name__ == "__main__":
    main()
