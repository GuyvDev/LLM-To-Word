#!/usr/bin/env python3
"""Build a deterministic, uploadable Skill One ZIP package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent
SKILL = ROOT / "skill-one"
REQUIRED = {
    "SKILL.md",
    "agents/openai.yaml",
    "scripts/docx_brain.py",
    "scripts/visual_gate.py",
    "references/document-design.md",
    "references/provider-adapters.md",
    "assets/example.md",
    "assets/icon.svg",
    "assets/runtime-manifest.json",
    "bin/md2docx-core.exe",
    "bin/md2docx-core-linux-x64",
}


def verify_runtime_manifest() -> None:
    manifest_path = SKILL / "assets" / "runtime-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Runtime manifest is unreadable: {error}") from error
    if (
        manifest.get("schema_version") != 1
        or manifest.get("engine") != "md2docx-core"
        or not isinstance(manifest.get("binaries"), dict)
    ):
        raise SystemExit("Runtime manifest has an invalid schema")
    expected_paths = {
        "bin/md2docx-core.exe",
        "bin/md2docx-core-linux-x64",
    }
    if set(manifest["binaries"]) != expected_paths:
        raise SystemExit("Runtime manifest must list exactly the bundled runtimes")
    for relative, expected_hash in manifest["binaries"].items():
        binary = SKILL / relative
        actual_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise SystemExit(
                f"Runtime hash mismatch for {relative}: "
                f"expected={expected_hash}, actual={actual_hash}"
            )


def package(output: Path) -> dict[str, object]:
    present = {
        path.relative_to(SKILL).as_posix()
        for path in SKILL.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    missing = sorted(REQUIRED - present)
    if missing:
        raise SystemExit(f"Skill package is incomplete: {', '.join(missing)}")
    unexpected = sorted(present - REQUIRED)
    if unexpected:
        raise SystemExit(
            f"Skill package contains unexpected files: {', '.join(unexpected)}"
        )
    verify_runtime_manifest()

    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        sources = {relative: SKILL / relative for relative in REQUIRED}
        for relative, source in sorted(sources.items()):
            info = ZipInfo(f"skill-one/{relative}", (2000, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            mode = 0o100755 if relative.startswith("bin/") else 0o100644
            info.external_attr = mode << 16
            archive.writestr(info, source.read_bytes())

    result = {"output": str(output), "files": len(sources), "valid": True}
    print(json.dumps(result, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / "skill-one.zip",
        help="destination ZIP path",
    )
    args = parser.parse_args()
    package(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
