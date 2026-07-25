#!/usr/bin/env python3
"""Validate the mandatory visual-release artifacts for Skill One."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> None:
    print(json.dumps({"valid": False, "error": message}, ensure_ascii=False))
    raise SystemExit(1)


def require_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        fail(f"{key} must be a non-negative integer")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docx", required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--pages-dir", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    docx = Path(args.docx)
    pdf = Path(args.pdf)
    pages_dir = Path(args.pages_dir)
    report_path = Path(args.report)

    for label, path in (("DOCX", docx), ("PDF", pdf), ("report", report_path)):
        if not path.is_file():
            fail(f"{label} file does not exist: {path}")
        if path.stat().st_size == 0:
            fail(f"{label} file is empty: {path}")
    if not pages_dir.is_dir():
        fail(f"pages directory does not exist: {pages_dir}")

    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid visual report: {exc}")
    if not isinstance(data, dict):
        fail("visual report must be a JSON object")

    expected = require_int(data, "pages_expected")
    rendered = require_int(data, "pages_rendered")
    reviewed = require_int(data, "pages_reviewed")
    rebuild_count = require_int(data, "rebuild_count")
    if expected < 1:
        fail("pages_expected must be at least 1")

    page_files = sorted(
        p for p in pages_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    if len(page_files) != expected:
        fail(f"found {len(page_files)} rendered page images; expected {expected}")
    if rendered != expected:
        fail("pages_rendered must equal pages_expected")
    if reviewed != expected:
        fail("pages_reviewed must equal pages_expected")

    reviewed_pages = data.get("reviewed_pages")
    required_pages = list(range(1, expected + 1))
    if reviewed_pages != required_pages:
        fail(f"reviewed_pages must equal {required_pages}")

    if data.get("visual_valid") is not True:
        fail("visual_valid must be true")
    issues = data.get("issues")
    if issues != []:
        fail("issues must be an empty array")

    actual_docx_hash = sha256_file(docx)
    actual_pdf_hash = sha256_file(pdf)
    if data.get("docx_sha256") != actual_docx_hash:
        fail("docx_sha256 does not match the delivered DOCX")
    if data.get("pdf_sha256") != actual_pdf_hash:
        fail("pdf_sha256 does not match the rendered PDF")

    result = {
        "valid": True,
        "docx_sha256": actual_docx_hash,
        "pdf_sha256": actual_pdf_hash,
        "pages_expected": expected,
        "pages_rendered": rendered,
        "pages_reviewed": reviewed,
        "rebuild_count": rebuild_count,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
