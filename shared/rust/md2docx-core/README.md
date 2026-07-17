# md2docx canonical compiler

This crate is the single conversion brain for Chrome, the Word add-in, and the Windows clipboard product.

- Native build: Windows clipboard executable/library.
- `wasm32-unknown-unknown`: Chrome extension and Office webview.
- Inputs include a source/provider hint used to select a Markdown dialect profile automatically.
- Outputs are DOCX bytes and sanitized rich HTML generated from the same Comrak document tree.

The current JavaScript and Python engines remain compatibility fallbacks until golden fixtures and Microsoft Word acceptance checks pass for this core.

## Dependency licenses

- Comrak: BSD-2-Clause.
- wasm-bindgen: MIT OR Apache-2.0.
- zip: MIT.
- serde/serde_json: MIT OR Apache-2.0.

Pandoc is not linked or distributed because its main implementation is GPL-2.0-or-later. It may be used separately by developers for interoperability comparisons.
