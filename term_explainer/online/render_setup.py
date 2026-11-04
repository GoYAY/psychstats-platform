"""Check deploy-time tools and CJK fonts before accepting paid model work."""
import sys
from .config import OnlineError

def check_renderer(config):
    if sys.version_info<(3,11):raise OnlineError('runtime_unavailable','在线生成服务需要Python 3.11或更新版本。',503)
    qa=config.figure_qa_dir;font=config.cjk_font
    if qa is None or any(not (qa/name).is_file() for name in ['audit_panel_alignment.py','audit_pdf_text.py','audit_figure_collisions.py','pdfium_geometry.py']):
        raise OnlineError('renderer_unavailable','图示审计工具尚未配置完整，生成暂未启用。',503)
    if font is None or not font.is_file():raise OnlineError('renderer_unavailable','中文图示字体尚未配置，生成暂未启用。',503)
    try:
        import pdfplumber,pypdf,pypdfium2
        # Exercise the native library before accepting model work; import alone
        # would miss a broken/missing PDFium binary on the deployment host.
        with pypdfium2.PdfDocument.new() as document:
            page=document.new_page(20,20);bitmap=page.render(scale=1)
            bitmap.close();page.close()
        from matplotlib import font_manager
        font_manager.FontProperties(fname=str(font)).get_name()
    except Exception:raise OnlineError('renderer_unavailable','图示依赖或字体不可用，生成暂未启用。',503) from None
    return True
