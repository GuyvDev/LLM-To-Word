# Contributor Guide

## Runtime

Use Python 3.12 for Skill One tests and a current stable Rust toolchain with the
`wasm32-unknown-unknown` target for the canonical compiler. Skill One has no
third-party Python runtime dependencies. Install the optional repository
validation dependency with `python -m pip install -r requirements-dev.txt`.

## Verification

Run these checks before opening a pull request:

```bash
.\scripts\test_all.ps1 -IncludeDocker
.\scripts\package_release.ps1
python scripts/check_credentials.py
python scripts/check_repository.py
```

For automated visual review, convert the generated DOCX to PDF and rasterize
only the PDF pages. Never capture the desktop or an application window. A human
release tester must also open the DOCX in Microsoft Word and verify Hebrew
headings, mixed BiDi text, inline/block math, blockquotes, lists, and tables.

## Safety

Do not commit credentials, private documents, generated DOCX/PDF files, debug
images, screen captures, or machine-specific paths. Keep the project usable
without an account, payment, hosted service, or optional user-provided AI
credential.
