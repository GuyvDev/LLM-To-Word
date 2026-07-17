#!/usr/bin/env python3
"""Build a deterministic, uploadable Skill One ZIP package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent
SKILL = ROOT / "skill-one"
REQUIRED = {
    "SKILL.md",
    "agents/openai.yaml",
    "scripts/docx_brain.py",
    "references/docspec.md",
    "references/provider-adapters.md",
    "assets/example-docspec.json",
}


def package(output: Path) -> dict[str, object]:
    present = {
        path.relative_to(SKILL).as_posix()
        for path in SKILL.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    missing = sorted(REQUIRED - present)
    if missing:
        raise SystemExit(f"Skill package is incomplete: {', '.join(missing)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in sorted(present):
            info = ZipInfo(f"skill-one/{relative}", (2000, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (SKILL / relative).read_bytes())

    result = {"output": str(output), "files": len(present), "valid": True}
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
