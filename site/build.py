#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Command-line entry point for preview and public static builds."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from sitegen.build import BuildError, build_site


HERE = Path(__file__).resolve().parent
DIST = HERE / "dist"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preview", "public"), default="preview")
    parser.add_argument(
        "--check",
        action="store_true",
        help="build in a temporary directory without changing site/dist",
    )
    args = parser.parse_args(argv)

    try:
        if args.check:
            with tempfile.TemporaryDirectory(prefix="psych-stats-site-check-") as temporary:
                report = build_site(args.mode, Path(temporary))
        else:
            report = build_site(args.mode, DIST)
    except (BuildError, OSError, ValueError) as exc:
        print(exc)
        return 1

    print(
        f"mode={report.mode} pages={report.page_count} terms={report.term_count} "
        f"questions={report.question_count} datasets={report.dataset_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
