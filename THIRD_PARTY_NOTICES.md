# Third-party notices

The canonical local converter is intentionally built from permissively licensed components that may be distributed inside the Chrome extension and native release:

| Component | Use | License |
|---|---|---|
| [Comrak](https://github.com/kivikakk/comrak) | CommonMark/GFM parser and HTML renderer | BSD-2-Clause |
| [wasm-bindgen](https://github.com/wasm-bindgen/wasm-bindgen) | Rust/WebAssembly browser bindings | MIT OR Apache-2.0 |
| [zip](https://github.com/zip-rs/zip2) | DOCX/ZIP package writer | MIT |
| [Serde](https://github.com/serde-rs/serde) and `serde_json` | Compiler option and capability serialization | MIT OR Apache-2.0 |

The exact resolved versions are recorded in `Cargo.lock`. Their copyright notices and license texts remain available in the linked upstream projects and Cargo package metadata.

Pandoc is not linked, copied, or distributed by this project because its executable is GPL-2.0-or-later. Developers may run an independently installed Pandoc executable only as an optional interoperability reference.
