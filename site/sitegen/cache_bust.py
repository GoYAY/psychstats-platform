from __future__ import annotations

import hashlib
import re
from pathlib import Path

# 会给这些扩展名的"会更新资源"引用注入内容哈希参数 ?v=...。
# 字体(.woff/.woff2/.ttf)、图片(.png/.ico) 等不常变更，交由 Caddy 的短时缓存。
_HASH_EXTS = {".css", ".js", ".svg", ".json"}

# 匹配可选 ../ 前缀 + assets/... + 指定扩展名，且后面不是已带查询参数。
# 用 [.] 代替 \.、用显式空白类代替 \s，并用 \x22/\x27 表示引号，避免字符串歧义。
_REF_RE = re.compile(
    r'((?:[.][.]/)?assets/(?:[^\x22\x27)(> \t\r\n]+?[.](?:css|js|svg|json)))(?=[ \t\r\n\x22\x27()>]|$)'
)


def add_cache_busting(out: Path) -> None:
    """给 HTML/JS/CSS 中对会更新资源的引用追加内容哈希查询参数。

    文件内容不变，仅 URL 追加 ?v=<hash>；内容一变哈希即变，URL 随之变化，
    浏览器便会拉取新文件。Caddy 对带 ?v= 的资源可设长效缓存。
    """
    hashes: dict[str, str] = {}
    for f in out.rglob("*"):
        if f.is_file() and f.suffix in _HASH_EXTS:
            rel = f.relative_to(out).as_posix()
            hashes[rel] = hashlib.sha256(f.read_bytes()).hexdigest()[:10]

    common = [key for key in sorted(hashes) if key.startswith('assets/') and
              (key.endswith('.js') or key in ('assets/site.css', 'assets/analysis-reader.css'))]
    runtime_version = hashlib.sha256('|'.join(key+':'+hashes[key] for key in common).encode()).hexdigest()[:16]

    def rewrite(m):
        ref = m.group(1)
        norm = ref
        while norm.startswith("../"):
            norm = norm[3:]
        key = norm.lstrip("./")
        h = hashes.get(key)
        if h is None:
            return ref
        return ref + "?v=" + h

    for t in out.rglob("*"):
        if t.is_file() and t.suffix in (".html", ".js", ".css"):
            text = t.read_text(encoding="utf-8")
            new = _REF_RE.sub(rewrite, text)
            if t.suffix == '.html':
                new = new.replace('</head>', f'  <meta name="psych-runtime" content="{runtime_version}">\n</head>')
            if new != text:
                t.write_text(new, encoding="utf-8")
