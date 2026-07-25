# Skill One implementation plan

## Product promise

Create the same Word document as the Chrome extension and clipboard helper from
the same Markdown input, then require both machine validation and inspection of
every rendered page. The runtime is local and self-contained.

## Architecture

1. The model preserves supplied Markdown or applies the formatting guide while
   authoring new Markdown.
2. The Python launcher passes that Markdown unchanged to bundled
   `md2docx-core`.
3. Chrome uses the WASM build, while clipboard and Skill One use native builds
   of that same Rust source.
4. The launcher self-tests the compiler, preflights Markdown, validates feature
   coverage and OOXML, and recompiles deterministically before returning a DOCX.
5. The agent renders the exact DOCX to PDF, rasterizes every page, inspects all
   page images, and records hashes, counts, issues, and rebuilds.
6. `visual_gate.py` rejects an incomplete or mismatched visual receipt.

There is no Skill-One-specific DOCX compiler or intermediate translation
format.

## Acceptance gates

- Identical Markdown and source profile produce identical native-core DOCX
  bytes.
- Windows and Linux x64 native cores are bundled for local/provider execution.
- RTL/BiDi, tables, Markdown, equations, and styles are owned by the shared
  compiler and covered by its conformance suite.
- The launcher rejects corrupt XML, em dashes, and Unicode BiDi controls.
- The launcher rejects malformed input, wrong expected input hashes, skipped
  features, tampered packages, and output that differs from trusted replay.
- A deliverable requires matching DOCX/PDF hashes, one image per expected page,
  review of every page number, no unresolved issues, and `visual_valid: true`.
