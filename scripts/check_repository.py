#!/usr/bin/env python3
"""Validate publication structure, documentation, and artifact hygiene."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PRODUCTS = {
    "chrome-extension",
    "clipboard-helper",
    "skill-one",
    "word-addin",
}
EXPECTED_SKILL_FILES = {
    "SKILL.md",
    "agents/openai.yaml",
    "assets/example.md",
    "assets/icon.svg",
    "assets/runtime-manifest.json",
    "bin/md2docx-core.exe",
    "bin/md2docx-core-linux-x64",
    "references/document-design.md",
    "references/provider-adapters.md",
    "scripts/docx_brain.py",
    "scripts/visual_gate.py",
}
EXPECTED_EXAMPLE_IMAGES = {
    f"{index:02d}-{name}-{side}.png"
    for index, name in enumerate(
        ("mixed-bidi", "math-symbols", "rtl-table", "document-styles"),
        start=1,
    )
    for side in ("before", "after")
}
IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    ".venv-win",
    "__pycache__",
    "audit-output",
    "build",
    "dist",
    "target",
}
BANNED_PUBLICATION_TERMS = {
    "api" + "-service": "retired product name",
    "fast" + "api": "retired service implementation",
    "python" + "-cli": "retired product name",
    "web" + "-client": "retired product name",
}
LINK_RE = re.compile(r"(?<!!)\[[^\]]*]\(([^)]+)\)")
MACHINE_PATH_RE = re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+")


def source_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in IGNORED_DIRECTORIES for part in path.parts)
    )


def main() -> int:
    errors: list[str] = []
    products = {
        path.name for path in (ROOT / "products").iterdir() if path.is_dir()
    }
    if products != EXPECTED_PRODUCTS:
        errors.append(
            "products/ must contain exactly "
            f"{sorted(EXPECTED_PRODUCTS)}; found {sorted(products)}"
        )

    skill_root = ROOT / "products" / "skill-one" / "skill-one"
    skill_files = {
        path.relative_to(skill_root).as_posix()
        for path in skill_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    if skill_files != EXPECTED_SKILL_FILES:
        errors.append(
            "Skill One file set mismatch: "
            f"missing={sorted(EXPECTED_SKILL_FILES - skill_files)}, "
            f"unexpected={sorted(skill_files - EXPECTED_SKILL_FILES)}"
        )

    files = source_files()
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix.casefold() in {".docx", ".pdf"}:
            errors.append(f"generated document in publication tree: {relative}")
        if len(path.parts) == len(ROOT.parts) + 1 and path.suffix.casefold() in {
            ".docx",
            ".pdf",
            ".zip",
        }:
            errors.append(f"generated artifact at repository root: {relative}")
        if path.suffix.casefold() not in {
            ".md",
            ".py",
            ".ps1",
            ".js",
            ".json",
            ".yml",
            ".yaml",
            ".xml",
            ".toml",
        }:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            errors.append(f"non-UTF-8 source file {relative}: {error}")
            continue
        if MACHINE_PATH_RE.search(text):
            errors.append(f"machine-specific user path in {relative}")
        lowered = text.casefold()
        for term, reason in BANNED_PUBLICATION_TERMS.items():
            if term in lowered:
                errors.append(f"{reason} {term!r} found in {relative}")

    for path in (file for file in files if file.suffix.casefold() == ".md"):
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for raw_target in LINK_RE.findall(text):
            target = raw_target.split("#", 1)[0].strip()
            if (
                not target
                or "://" in target
                or target.startswith(("mailto:", "#"))
            ):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"broken Markdown link in {relative}: {target}")

    gallery = ROOT / "docs" / "images" / "examples"
    gallery_files = (
        {path.name for path in gallery.iterdir() if path.is_file()}
        if gallery.is_dir()
        else set()
    )
    if gallery_files != EXPECTED_EXAMPLE_IMAGES:
        errors.append(
            "README example gallery mismatch: "
            f"missing={sorted(EXPECTED_EXAMPLE_IMAGES - gallery_files)}, "
            f"unexpected={sorted(gallery_files - EXPECTED_EXAMPLE_IMAGES)}"
        )
    for name in sorted(EXPECTED_EXAMPLE_IMAGES & gallery_files):
        path = gallery / name
        payload = path.read_bytes()
        if (
            len(payload) < 24
            or payload[:8] != b"\x89PNG\r\n\x1a\n"
            or payload[12:16] != b"IHDR"
        ):
            errors.append(f"invalid PNG example image: {path.relative_to(ROOT)}")
            continue
        width = int.from_bytes(payload[16:20], "big")
        height = int.from_bytes(payload[20:24], "big")
        if width < 1000 or height < 250:
            errors.append(
                f"example image is below publication resolution: "
                f"{path.relative_to(ROOT)} ({width}x{height})"
            )

    if errors:
        print("Repository publication audit failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        f"Repository publication audit passed: {len(files)} source files, "
        f"{sum(path.suffix.casefold() == '.md' for path in files)} Markdown files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
