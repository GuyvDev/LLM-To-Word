# LLM to Word

Local, self-contained tools that turn LLM output into polished Microsoft Word
documents. The project focuses on native RTL and BiDi behavior, editable OMML
equations, logical RTL tables, centered cells, and stable spacing between
Hebrew or Arabic and English, numbers, code, currency, brackets, and
punctuation.

No current product requires a hosted conversion API, account, payment, Docker
runtime, watermark, or telemetry. Docker is used only as a development test for
Skill One.

## Products and release status

Status meanings:

- **Verified**: automated tests and the applicable local benchmark pass.
- **Release candidate**: implementation is complete, but an external store or
  clean-machine acceptance gate remains.
- **Beta**: implemented, but it still requires end-to-end product validation.

| Product | Status | Delivery | Remaining release work |
|---|---|---|---|
| [Chrome extension](products/chrome-extension/README.md) | Release candidate | Manifest V3 with bundled WebAssembly | Chrome acceptance test, Web Store validation, signing, and publication |
| [Clipboard helper](products/clipboard-helper/README.md) | Release candidate | Windows installer plus native compiler | Clean Windows machine installation, global hotkey, and Word clipboard acceptance test |
| [Skill One](products/skill-one/README.md) | Verified | Installable AI skill with bundled Python compiler | Optional provider-specific marketplace publication |
| [Word add-in](products/word-addin/README.md) | Beta, not end-to-end tested | HTTPS Office task pane with bundled WebAssembly | Hosted deployment, credential broker, provider tests, Word tests, and Microsoft manifest validation |

The retired FastAPI service, web client, legacy Python Markdown converter, and
Python CLI are intentionally absent. They are not required by the current
architecture.

## Feature matrix

| Capability | Chrome extension | Clipboard helper | Skill One | Word add-in |
|---|:---:|:---:|:---:|:---:|
| Runs without a conversion service | Yes | Yes | Yes | Yes |
| Download a native DOCX | Yes | Temporary internal DOCX | Yes | Inserts into Word |
| Formatted clipboard output | Yes | Yes, Word-native | No | No |
| Capture visible LLM output | Yes | Clipboard input | Agent-provided content | AI chat and Word selection |
| CommonMark and GFM Markdown | Yes | Yes | Uses DocSpec instead | Yes |
| Native editable OMML equations | Yes | Yes | Yes | Yes |
| RTL paragraphs and mixed BiDi runs | Yes | Yes | Yes | Yes |
| RTL table column behavior | Yes | Yes | Yes | Yes |
| Centered table cells | Yes | Yes | Yes | Yes |
| Deterministic OOXML self-validation | Shared compiler tests | Shared compiler tests | Built into every build | Shared compiler tests |
| User AI credential required | No | No | No | Only for optional AI chat |

## Chrome extension

The extension captures the latest visible answer from ChatGPT, Claude, Gemini,
Microsoft Copilot, Grok, Perplexity, DeepSeek, or a generic LLM page. Users can
also capture selected page content or paste Markdown manually. Auto-detection
selects the provider dialect without injecting a formatting prompt into the
LLM.

Features include:

- Local Manifest V3 service worker with a packaged Rust/WebAssembly compiler.
- Downloaded DOCX and Word-compatible formatted clipboard output.
- Headings H1 through H6, paragraphs, emphasis, links, images as labels/URLs,
  nested lists, blockquotes, fenced code with arbitrary languages, horizontal
  rules, tables, task lists, footnotes, description lists, highlights,
  underline, subscript, and superscript.
- Inline and block LaTeX converted to OMML in DOCX and Presentation MathML in
  formatted clipboard HTML.
- Word-stable mixed-direction spacing and logical RTL table columns.
- Temporary `activeTab` capture instead of broad LLM host permissions.

Install from source:

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked**.
4. Choose `products/chrome-extension`.
5. Pin **md2docx - Markdown to Word**.

See the [Chrome extension guide](products/chrome-extension/README.md) for use
and current acceptance gates.

## Clipboard helper

The Windows helper reads Markdown from the clipboard, runs the same canonical
native Rust compiler, asks Microsoft Word to create native rich clipboard
formats, and leaves the result ready for normal paste.

Features include:

- One-command PowerShell installation under `%LOCALAPPDATA%\Programs\md2docx`.
- Private Python environment with pinned Windows automation dependency.
- Start Menu shortcut and configurable global hotkey, default `Ctrl+Alt+M`.
- Repair/upgrade by rerunning the installer and guarded uninstall support.
- Reuses an existing Word process without closing it; closes only documents and
  processes created by the helper.
- Local temporary files are removed after conversion and shortcut errors are
  shown in a Windows dialog.

Build and install from a source checkout:

```powershell
.\scripts\build_converter_core.ps1
PowerShell -ExecutionPolicy Bypass -File .\products\clipboard-helper\install.ps1
```

The packaged release includes `md2docx-core.exe`, so release users do not need
Rust. Microsoft Word desktop and Python 3.12 or newer are currently required.

## Skill One

Skill One is a provider-neutral AI skill that converts strict DocSpec 1.0 JSON
through its bundled, dependency-free Python compiler. GPT, Claude, Codex, or
another agent receives the same schema and script. Identical DocSpec input
produces byte-identical DOCX output.

Features include:

- Native RTL run properties and Word-stable mixed Hebrew/English spacing.
- Native OMML inline and block equations with supported LaTeX validation.
- Semantic RTL tables, centered cells, headings, paragraphs, quotes, code,
  links, page breaks, and independent list numbering.
- Modern Word compatibility settings and deterministic ZIP/XML packaging.
- Automatic replacement of em dashes with regular hyphens.
- Self-validation of parts, relationships, XML, table properties, equations,
  list restarts, RTL runs, and prohibited output.
- Privacy-safe visual-review instructions that use PDF page images only and
  prohibit desktop or application-window screenshots.

Package or run it directly:

```powershell
python products\skill-one\package_skill.py
python products\skill-one\skill-one\scripts\docx_brain.py build input.json output.docx --report report.json
python products\skill-one\skill-one\scripts\docx_brain.py validate output.docx --json
```

See [installation](products/skill-one/INSTALL.md), the
[implementation plan](products/skill-one/PLAN.md), and the
[DocSpec contract](products/skill-one/skill-one/references/docspec.md).

## Word add-in

The Office task pane provides an AI chat that can read the current Word
selection on request and return insert, replace-selection, or conversational
reply actions. Its formatting contract asks the provider for structured
Markdown, while the bundled local renderer owns Word formatting.

Implemented features include:

- OpenAI, Anthropic, and Gemini direct-provider adapters for personal testing.
- Session-only API key handling; keys are not written to local storage.
- Selection preview, conversation history, generated Markdown review, insert,
  and replace-selection actions.
- Local WebAssembly conversion with the packaged JavaScript compatibility
  renderer as fallback.
- Native Word insertion through `insertFileFromBase64`.

The add-in is not yet production-validated. It still needs an HTTPS deployment,
an organization-controlled credential broker, real provider tests, Word desktop
and Word Online tests, and Microsoft manifest validation. Do not deploy its
direct browser-key mode as an organization-wide credential architecture.

## Canonical compiler

`shared/rust/md2docx-core/` owns Markdown parsing, source-profile selection,
DOCX generation, clipboard HTML, OMML math, RTL tables, mixed-direction
spacing, styling, and OOXML packaging for the Chrome extension, clipboard
helper, and Word add-in.

Build native Windows and browser outputs:

```powershell
.\scripts\build_converter_core.ps1
```

The WebAssembly files are written to `products/chrome-extension/core/`. The
native executable is written to the ignored `dist/windows/` directory.

## Build release packages

Create all four product bundles and a SHA-256 checksum manifest:

```powershell
.\scripts\package_release.ps1
```

Output is written to the ignored `dist/releases/` directory:

- `chrome-extension.zip`
- `clipboard-helper-windows-x64.zip`
- `skill-one.zip`
- `word-addin-host.zip`
- `SHA256SUMS.txt`

The Word add-in archive is a hosting bundle, not a Microsoft-validated store
package. Replace the example HTTPS origin in `manifest.xml` before deployment.

## Verification

Development requirements are Python 3.12, Node.js 22, a stable Rust toolchain,
the `wasm32-unknown-unknown` target, and Docker for the optional clean Skill One
gate.

```powershell
python -m pip install -r requirements-dev.txt
.\scripts\test_all.ps1
.\scripts\test_all.ps1 -IncludeDocker
```

The suite runs Rust unit and conformance tests, rebuilds native and WebAssembly
outputs, runs browser/worker/capture tests, validates JavaScript syntax, runs
Skill One determinism/corruption tests, and optionally verifies Skill One in a
clean Python container.

For visual review, convert a generated DOCX to PDF and rasterize only the PDF
pages into images. Never capture the desktop or an application window. A human
release tester must separately open release candidates in Microsoft Word and
check Hebrew headings, mixed BiDi text, equations, blockquotes, lists, tables,
and clipboard paste behavior.

## Repository layout

```text
products/
  chrome-extension/  Manifest V3 extension and packaged WebAssembly
  clipboard-helper/  Windows installer and Word-native clipboard helper
  skill-one/          Installable provider-neutral AI skill
  word-addin/         Microsoft Word AI task-pane add-in
shared/
  rust/md2docx-core/  Canonical Markdown compiler shared by three products
tests/                Cross-product conformance and regression suites
scripts/              Build, verification, and release packaging
docs/                 Formatting contract and product roadmap
```

## Production checklist

- [x] Local-only canonical conversion architecture.
- [x] Organized product and shared-core repository structure.
- [x] Locked Rust and development Python dependencies.
- [x] Automated Rust, WebAssembly, browser, Skill One, and Docker gates.
- [x] Credential-literal scanning in CI.
- [x] Deterministic release packaging with SHA-256 checksums.
- [x] Privacy, security, contribution, licensing, and third-party notices.
- [ ] Chrome Web Store validation and signed publication.
- [ ] Clipboard helper clean-machine and Microsoft Word acceptance test.
- [ ] Word add-in hosted, provider, Microsoft Word, and manifest validation.
- [ ] Signed native Windows release artifacts.

See the live [product roadmap](docs/ROADMAP.md) for the remaining external
release gates.

## License and policies

MIT licensed. See [third-party notices](THIRD_PARTY_NOTICES.md),
[privacy](PRIVACY.md), [security](SECURITY.md), and
[contributing](CONTRIBUTING.md).
