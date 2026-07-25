# Product roadmap

## Current products

| Product | Status |
|---|---|
| Chrome extension | Verified in use; Web Store validation, signing, and publication remain |
| Clipboard helper | Verified in use; signing and publication remain |
| Skill One | Verified in web use; machine checks and mandatory all-page visual gate are packaged |
| Word add-in | Implemented but not end-to-end tested; hosted provider, Word, accessibility, and Microsoft validation remain |

## Release gates

- [x] One canonical Rust Markdown compiler for native and WASM products.
- [x] Shared Markdown dialect, punctuation, BiDi, math, clipboard, and DOCX tests.
- [x] No hosted conversion dependency, account, payment, watermark, or telemetry.
- [x] Deterministic Skill One package with structural OOXML validation.
- [x] Skill One extracted-text review and mandatory all-page visual gate.
- [x] One-command release packaging with SHA-256 checksums.
- [x] Version-tagged GitHub Releases after Linux and Windows CI pass.
- [x] Privacy-safe PDF page-image visual audit workflow.
- [ ] Complete human Microsoft Word visual regression checks on Windows.
- [ ] Complete Chrome Web Store and Microsoft add-in validation.
- [ ] Create signed release artifacts and publish store installation pages.
