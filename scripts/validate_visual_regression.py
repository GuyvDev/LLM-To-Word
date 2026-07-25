#!/usr/bin/env python3
"""Render canonical DOCX examples and enforce exact approved PNG hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from generate_readme_examples import (
    BRAIN,
    EXAMPLES,
    crop_to_content,
    locate_soffice,
    rasterize,
    render_docx_to_pdf,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPECTED = ROOT / "tests" / "visual" / "expected-sha256.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_cases(output: Path) -> dict[str, dict[str, object]]:
    output.mkdir(parents=True, exist_ok=True)
    soffice = locate_soffice()
    results: dict[str, dict[str, object]] = {}

    with tempfile.TemporaryDirectory(prefix="md2docx-visual-ci-") as directory:
        work = Path(directory)
        for index, (name, markdown_text) in enumerate(EXAMPLES.items(), start=1):
            case = work / name
            case.mkdir()
            markdown = case / f"{name}.md"
            docx = case / f"{name}.docx"
            report = case / "report.json"
            markdown.write_text(markdown_text, encoding="utf-8", newline="\n")
            subprocess.run(
                [
                    sys.executable,
                    str(BRAIN),
                    "build",
                    str(markdown),
                    str(docx),
                    "--source",
                    "llm",
                    "--report",
                    str(report),
                ],
                check=True,
            )
            machine_report = json.loads(report.read_text(encoding="utf-8"))
            if machine_report.get("valid") is not True:
                raise RuntimeError(f"canonical compiler rejected {name}")

            pdf, renderer = render_docx_to_pdf(
                "libreoffice",
                soffice,
                docx,
                case,
                case / "lo-profile",
            )
            if renderer != "libreoffice":
                raise RuntimeError(f"unexpected renderer for {name}: {renderer}")

            image_name = f"{index:02d}-{name}-after.png"
            image = output / image_name
            rasterize(pdf, image)
            crop_to_content(image)
            results[image_name] = {
                "sha256": sha256_file(image),
                "bytes": image.stat().st_size,
            }

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=Path, default=DEFAULT_EXPECTED)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--write-expected",
        action="store_true",
        help="replace the expected manifest with the current pinned-renderer hashes",
    )
    args = parser.parse_args()

    actual = render_cases(args.output.resolve())
    manifest = {
        "schema": 1,
        "renderer": "tests/visual/Dockerfile",
        "images": actual,
    }
    expected_path = args.expected.resolve()
    if args.write_expected:
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        expected_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote visual baseline: {expected_path}")
        return 0

    if not expected_path.is_file():
        print(f"Visual baseline is missing: {expected_path}", file=sys.stderr)
        return 1
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    expected_images = expected.get("images")
    if expected_images != actual:
        names = sorted(set(expected_images or {}) | set(actual))
        print("Visual regression detected:", file=sys.stderr)
        for name in names:
            wanted = (expected_images or {}).get(name)
            found = actual.get(name)
            if wanted != found:
                print(
                    f"- {name}: expected={wanted!r}, actual={found!r}",
                    file=sys.stderr,
                )
        print(f"Rendered PNG evidence: {args.output.resolve()}", file=sys.stderr)
        return 1

    print(f"Visual regression gate passed: {len(actual)} exact PNG hashes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
