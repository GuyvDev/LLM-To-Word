# Markdown conformance coverage

`fixtures/markdown_conformance.json` is the shared corpus for the native Rust compiler and packaged WebAssembly build. Every case declares its dialect/source plus required and forbidden HTML/DOCX fragments.

| Area | Covered cases |
|---|---|
| Dialects | Strict CommonMark, GFM, GitHub, HackMD, generic LLM |
| Blocks | ATX/Setext headings, paragraphs, quotes, alerts, ordered/unordered/task lists, thematic breaks, tables, descriptions, fenced/indented code, footnotes |
| Inline styles | Emphasis, strong, strike, code, links, images, underline, insertion, highlight, subscript, superscript, spoiler text |
| Math | Inline/display math, Greek commands, operators, nested groups, fractions, roots, matrices, subscripts/superscripts, brackets and punctuation |
| Text safety | XML characters, quotes, apostrophes, slashes, all bracket types, arrows/operators, emoji, combining marks, Hebrew, Arabic, mixed BiDi, and Word-stable spaces across language/number/currency/punctuation boundaries |
| Recovery | Unclosed emphasis, links, brackets, math and fences; empty/BOM/whitespace input |
| Stress/property checks | Determinism, long paragraphs, nesting, all ASCII punctuation, control-character filtering and deterministic generated combinations |

The Hebrew benchmark is tested twice as separate product contracts. The DOCX
path must contain native OMML equations and Word RTL table structures. The
formatted-clipboard path must contain self-contained inline styles, compact
headings and paragraphs, RTL tables with centered cells, preserved soft line
breaks, and importable Presentation MathML with no leaked supported LaTeX
commands. Shared theme constants keep the body, heading, table, and quote
decisions aligned across the two renderers.

The suite promises graceful, deterministic conversion for the documented syntax families. It does not claim semantic support for arbitrary vendor plug-ins, executable/unsafe HTML, JavaScript, or downloading remote image bytes. Unknown constructs must remain safe text and must never corrupt the DOCX package.

Run every local gate on Windows with:

```powershell
.\scripts\test_all.ps1
```

Add `-IncludeDocker` for the clean-environment Skill One container gate.
`-SkipPython` is available for isolated canonical-compiler work, but CI always
runs Skill One's dependency-free Python tests, Rust, regenerated-WASM drift
checks, and every JavaScript conformance test.
