"""Render formulas once per build with the pinned, local KaTeX distribution."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from .reading_aids import formula_aid


RENDERER = Path(__file__).resolve().parents[2] / "tools" / "render_math.mjs"


def render_formulas(formulas: dict[str, str]) -> dict[str, str]:
    if not formulas:
        return {}
    result = subprocess.run(
        ["node", str(RENDERER)], input=json.dumps({slug:formula_aid(latex,slug)[0] for slug,latex in formulas.items()}, ensure_ascii=False),
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    if result.returncode:
        raise ValueError("formula rendering failed: " + result.stderr.strip())
    rendered = json.loads(result.stdout)
    if set(rendered) != set(formulas) or any(not isinstance(v, str) for v in rendered.values()):
        raise ValueError("formula renderer returned an incomplete result")
    return rendered
