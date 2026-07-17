# Product roadmap

## Current products

| Product | Status |
|---|---|
| Chrome extension | Release candidate; automated conversion/capture tests pass, Web Store validation remains |
| Clipboard helper | Release candidate; installer/native core implemented, clean-machine Word acceptance remains |
| Skill One | Verified; deterministic compiler, packaging, OOXML validation, Docker, and PDF image benchmark pass |
| Word add-in | Beta and not end-to-end tested; hosted provider and Microsoft validation remain |

The retired FastAPI service, web client, Python Markdown converter, and Python
CLI are intentionally not part of the current architecture.

## Release gates

- [x] One canonical Rust Markdown compiler for native and WASM products.
- [x] Shared Markdown dialect, punctuation, BiDi, math, clipboard, and DOCX tests.
- [x] No hosted conversion dependency, account, payment, watermark, or telemetry.
- [x] Deterministic Skill One package with structural OOXML validation.
- [x] One-command release packaging with SHA-256 checksums.
- [x] Privacy-safe PDF page-image visual audit workflow.
- [ ] Complete human Microsoft Word visual regression checks on Windows.
- [ ] Complete Chrome Web Store and Microsoft add-in validation.
- [ ] Complete clipboard clean-machine install/hotkey/Word acceptance testing.
- [ ] Create signed release artifacts and publish store installation pages.
