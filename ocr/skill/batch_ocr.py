import os
import sys
import glob
import argparse

# 确保能 import 同目录的 pdf_ocr
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdf_ocr import pdf_to_text


def batch_ocr(folder: str, dpi: int = 200, recursive: bool = True, force: bool = False):
    pattern = os.path.join(folder, "**", "*.pdf") if recursive else os.path.join(folder, "*.pdf")
    pdfs = sorted(glob.glob(pattern, recursive=recursive))
    print(f"找到 {len(pdfs)} 个 PDF")
    done = 0
    for pdf in pdfs:
        out = pdf[:-4] + ".txt"
        if os.path.exists(out) and not force:
            print(f"[跳过] 已存在 {out}")
            continue
        try:
            pdf_to_text(pdf, out, dpi=dpi)
            done += 1
        except Exception as e:
            print(f"[失败] {pdf}: {e}")
    print(f"完成 {done} 个，共 {len(pdfs)} 个（跳过 {len(pdfs) - done} 个）")


def main():
    parser = argparse.ArgumentParser(description="扫描版 PDF 批量本地 OCR（零 token）")
    parser.add_argument("folder", help="包含 PDF 的目录")
    parser.add_argument("-d", "--dpi", type=int, default=200, help="渲染清晰度，默认 200")
    parser.add_argument("--no-recursive", action="store_true", help="不递归子目录")
    parser.add_argument("-f", "--force", action="store_true", help="强制重跑（忽略已存在的 txt）")
    args = parser.parse_args()
    batch_ocr(args.folder, dpi=args.dpi, recursive=not args.no_recursive, force=args.force)


if __name__ == "__main__":
    main()
