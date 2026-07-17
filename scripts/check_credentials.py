#!/usr/bin/env python3
"""Fail when repository source files contain common credential literals."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "OpenAI API key": re.compile(r"sk" + r"-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    "Anthropic API key": re.compile(r"sk" + r"-ant-[A-Za-z0-9_-]{20,}"),
    "Gemini API key": re.compile(r"AI" + r"za[0-9A-Za-z_-]{30,}"),
    "Stripe-style secret": re.compile(r"sk" + r"_(?:live|test)_[A-Za-z0-9_-]+"),
    "Webhook secret": re.compile(r"wh" + r"sec_[A-Za-z0-9_-]+"),
    "GitHub token": re.compile(r"gh" + r"[pousr]_[A-Za-z0-9_-]{20,}"),
    "Private key": re.compile(r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----"),
}


def repository_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / name.decode("utf-8") for name in result.stdout.split(b"\0") if name]


def main() -> int:
    findings: list[str] = []
    for path in repository_files():
        if not path.is_file():
            continue
        payload = path.read_bytes()
        if b"\0" in payload:
            continue
        text = payload.decode("utf-8", errors="replace")
        relative = path.relative_to(ROOT).as_posix()
        for line_number, line in enumerate(text.splitlines(), 1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{relative}:{line_number}: {label}")
    if findings:
        print("Credential-like literals found:")
        print("\n".join(findings))
        return 1
    print("Credential scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
