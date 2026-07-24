# Skill One

Provider-neutral AI skill that preserves or authors Markdown, compiles it with
the repository's canonical `md2docx-core`, validates the result, and requires
an all-page visual release gate.

## Status

Verified in web use on Windows x64 and Linux x64. The Python components launch
and validate the shared compiler; they contain no separate formatting or OOXML
renderer.

## Features

- Same CommonMark/GFM/LLM parser and DOCX renderer as Chrome and clipboard.
- Native RTL/BiDi, RTL tables, centered cells, OMML equations, code, links,
  lists, headings, and Markdown extensions from the shared core.
- Shared removal of Unicode BiDi controls and replacement of em dashes.
- Local execution without an account or credential.
- Mandatory DOCX-to-PDF rendering, all-page raster review, and visual receipt.
- Default lossless conversion mode with input SHA-256 reporting.
- Verified compiler provenance instead of trusting generic DOCX validity.
- Hash-approved bundled runtimes; environment variables and PATH cannot replace
  the canonical executable.
- Runtime compiler doctor, Markdown preflight, feature-coverage validation,
  semantic OOXML review, extracted-text fidelity, and deterministic replay.
- Byte-identical Windows/Linux DOCX output, enforced by a Docker parity gate.
- Hash and page-count validation for the exact DOCX, PDF, and reviewed images.

## Product files

- [Implementation plan](PLAN.md)
- [Installation and packaging](INSTALL.md)
- `skill-one/scripts/docx_brain.py` - native-core launcher and validator
- `skill-one/bin/` - native builds of the shared Rust core
- `skill-one/assets/runtime-manifest.json` - approved runtime hashes
- `skill-one/assets/icon.svg` - published skill icon
- `skill-one/references/document-design.md` - model-facing Markdown guide
- `skill-one/scripts/visual_gate.py` - mandatory visual receipt validator
- `package_skill.py` - deterministic upload ZIP builder
