# LLM to Word

[![AI Skill: ChatGPT, Claude, Codex](https://img.shields.io/badge/AI%20Skill-ChatGPT%20%7C%20Claude%20%7C%20Codex-6f42c1?style=flat-square)](#skill-one-the-ai-skill-for-word)
[![Chrome extension](https://img.shields.io/badge/Chrome-Extension-4285F4?logo=googlechrome&logoColor=white&style=flat-square)](#chrome-extension)
[![Windows clipboard helper](https://img.shields.io/badge/Windows-Clipboard%20Helper-0078D4?logo=windows&logoColor=white&style=flat-square)](#clipboard-helper)
[![CI](https://img.shields.io/github/actions/workflow/status/GuyvDev/LLM-To-Word/ci.yml?branch=main&label=tests&style=flat-square)](https://github.com/GuyvDev/LLM-To-Word/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/GuyvDev/LLM-To-Word?display_name=tag&sort=semver&style=flat-square)](https://github.com/GuyvDev/LLM-To-Word/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

Turn Markdown and AI output into polished Microsoft Word documents. The tools
fix RTL and mixed Hebrew/English text, punctuation, equations, tables, code,
lists, headings, and spacing locally, without a conversion API.

**Start here:** [Download Skill One](https://github.com/GuyvDev/LLM-To-Word/releases/latest/download/skill-one.zip)
· [View all downloads](https://github.com/GuyvDev/LLM-To-Word/releases/latest)

## Skill One: the AI skill for Word

Skill One is the primary product. Upload one ZIP to ChatGPT or Claude, or ask
Codex to install it. The skill includes the formatting guidance, native
compiler, structural checks, and visual-review workflow needed to create the
DOCX correctly.

### Install in ChatGPT

1. [Download `skill-one.zip`](https://github.com/GuyvDev/LLM-To-Word/releases/latest/download/skill-one.zip).
2. In ChatGPT, open **Plugins → Skills → Create → Upload from computer**.
3. Upload the ZIP, install it, and ask: `Use Skill One to create a Word document from this content.`

ChatGPT Skills availability depends on your plan and workspace settings. See
the official [ChatGPT Skills guide](https://help.openai.com/en/articles/20001066).

### Install in Claude

1. [Download `skill-one.zip`](https://github.com/GuyvDev/LLM-To-Word/releases/latest/download/skill-one.zip).
2. Enable **Code execution and file creation**, then open
   **Customize → Skills → + → Create skill → Upload a skill**.
3. Upload the ZIP, enable Skill One, and ask:
   `Use Skill One to create a Word document from this content.`

See the official [Claude Skills guide](https://support.claude.com/en/articles/12512180-use-skills-in-claude).

### Install in Codex with one prompt

Paste this into Codex:

```text
Install Skill One from the latest GitHub Release of
https://github.com/GuyvDev/LLM-To-Word. Download skill-one.zip and
SHA256SUMS.txt, verify the checksum, install it as a Codex skill, run its
doctor check, and tell me when I should start a new session.
```

After installation, ask:

```text
Use $skill-one to turn this Markdown into a polished Word document.
```

### What Skill One handles

- Correct Word RTL and mixed-direction run properties.
- Stable Hebrew/English spacing, punctuation, brackets, numbers, and symbols.
- Native editable OMML equations.
- Logical RTL table columns with centered, styled cells.
- Headings, lists, blockquotes, links, code, and extended Markdown.
- Deterministic DOCX packaging and OOXML self-validation.
- DOCX → PDF → page-image visual review before delivery.
- The same canonical compiler on Windows and Linux.

## Before and after

These are PDF-rendered pages from real DOCX files. Each pair uses the same
source content: basic AI-generated Word output on the left and the shared
compiler output on the right.

## Example 1: Mixed Hebrew and English

Numbers, punctuation, brackets, and arrows remain in their logical positions.

| **BEFORE - Basic AI DOCX** | **AFTER - Skill One** |
|:---:|:---:|
| <img src="docs/images/examples/01-mixed-bidi-before.png" width="500" alt="Poor mixed Hebrew and English alignment with displaced punctuation, brackets, numbers, and symbols"> | <img src="docs/images/examples/01-mixed-bidi-after.png" width="500" alt="Correct mixed Hebrew and English document showing natural Hebrew brackets, nested LTR syntax, stable punctuation, numbers, and mirrored RTL arrows"> |

## Example 2: Native Word equations

LaTeX becomes centered, editable OMML instead of raw equation text.

| **BEFORE - Basic AI DOCX** | **AFTER - Skill One** |
|:---:|:---:|
| <img src="docs/images/examples/02-math-symbols-before.png" width="500" alt="Raw LaTeX mixed into Hebrew prose with broken alignment"> | <img src="docs/images/examples/02-math-symbols-after.png" width="500" alt="Native editable Word equations centered inside correctly aligned Hebrew prose"> |

## Example 3: RTL tables

Columns keep their logical order and every cell is styled and centered.

| **BEFORE - Basic AI DOCX** | **AFTER - Skill One** |
|:---:|:---:|
| <img src="docs/images/examples/03-rtl-table-before.png" width="500" alt="Unformatted Markdown table with confused Hebrew and English column order"> | <img src="docs/images/examples/03-rtl-table-after.png" width="500" alt="Styled RTL Word table with logical columns, centered cells, banding, and stable mixed text"> |

## Example 4: Professional document styles

Headings, lists, quotes, code, and spacing form a consistent hierarchy.

| **BEFORE - Basic AI DOCX** | **AFTER - Skill One** |
|:---:|:---:|
| <img src="docs/images/examples/04-document-styles-before.png" width="500" alt="Raw Markdown headings, bullets, emphasis, quote, and code with weak spacing"> | <img src="docs/images/examples/04-document-styles-after.png" width="500" alt="Polished Word heading hierarchy, blockquote, RTL list, code block, and compact spacing"> |

## Chrome extension

[![Download Chrome extension](https://img.shields.io/badge/Download-chrome--extension.zip-4285F4?logo=googlechrome&logoColor=white)](https://github.com/GuyvDev/LLM-To-Word/releases/latest/download/chrome-extension.zip)

Capture an answer from ChatGPT, Claude, Gemini, Copilot, Grok, Perplexity,
DeepSeek, or another page. Download a DOCX or replace the clipboard with
Word-compatible formatted content. Conversion stays inside the extension.

Install:

1. Download and extract
   [`chrome-extension.zip`](https://github.com/GuyvDev/LLM-To-Word/releases/latest/download/chrome-extension.zip).
2. Open `chrome://extensions` and enable **Developer mode**.
3. Select **Load unpacked**, choose the extracted folder, and pin the extension.

[Chrome extension details](products/chrome-extension/README.md)

## Clipboard helper

[![Download clipboard helper](https://img.shields.io/badge/Download-clipboard--helper--windows--x64.zip-0078D4?logo=windows&logoColor=white)](https://github.com/GuyvDev/LLM-To-Word/releases/latest/download/clipboard-helper-windows-x64.zip)

Press `Ctrl+Alt+M` to turn Markdown on the Windows clipboard into Word-native
formatted clipboard content. Microsoft Word desktop and Python 3.12+ are
required.

Paste this installation prompt into Codex on the Windows computer:

```text
Install the clipboard helper from the latest GitHub Release of
https://github.com/GuyvDev/LLM-To-Word. Download
clipboard-helper-windows-x64.zip and SHA256SUMS.txt, verify the checksum,
extract it to a temporary folder, run install.ps1, verify the Ctrl+Alt+M
shortcut, and remove the temporary download when installation succeeds.
```

Codex will show the commands and request approval before downloading or running
the installer. [Clipboard helper details](products/clipboard-helper/README.md)

## Word add-in

The task-pane add-in connects AI chat with the current Word document and uses
the same local compiler for insertion. It is implemented, but has not yet
completed end-to-end Word desktop, Word Online, provider, accessibility, or
Microsoft manifest validation.

[Word add-in status](products/word-addin/README.md)

## One compiler, consistent output

```text
Markdown or AI output
          │
          ▼
 shared md2docx-core
          │
          ├── Skill One
          ├── Chrome extension
          ├── Clipboard helper
          └── Word add-in
```

The Rust compiler in [`shared/rust/md2docx-core`](shared/rust/md2docx-core)
owns Markdown parsing, RTL/BiDi behavior, equations, tables, styles, and OOXML
packaging. Products do not maintain separate formatting implementations.

## Product status

| Product | Status | Next external step |
|---|---|---|
| **Skill One** | **Verified** on Windows and Linux | Provider marketplace publication |
| **Chrome extension** | **Verified** | Chrome Web Store validation and signing |
| **Clipboard helper** | **Verified** | Windows signing |
| **Word add-in** | Implemented, not end-to-end tested | Hosting and Microsoft validation |

## GitHub Releases

Every version tag matching `v*` runs the complete Linux and Windows validation
jobs. If they pass, GitHub publishes these files on the version’s
[Release page](https://github.com/GuyvDev/LLM-To-Word/releases):

- `skill-one.zip`
- `chrome-extension.zip`
- `clipboard-helper-windows-x64.zip`
- `word-addin-host.zip`
- `SHA256SUMS.txt`

The native Windows files are currently unsigned. Verify downloads with
`SHA256SUMS.txt`.

Maintainers can build the same deterministic packages locally:

```powershell
.\scripts\test_all.ps1 -IncludeDocker
.\scripts\package_release.ps1
```

## Repository layout

```text
products/
  skill-one/          Primary AI skill and validation workflow
  chrome-extension/   Browser capture, DOCX download, formatted clipboard
  clipboard-helper/   Windows installer and Word-native clipboard helper
  word-addin/          AI task pane; implemented, pending end-to-end tests
shared/
  rust/md2docx-core/  Canonical Markdown-to-DOCX compiler
tests/                Cross-product conformance and regression tests
scripts/              Build, validation, gallery, and release automation
docs/                 Formatting guide and roadmap
```

Development requirements and release gates are documented in
[Contributing](CONTRIBUTING.md) and the [roadmap](docs/ROADMAP.md).

## License

MIT licensed. See [third-party notices](THIRD_PARTY_NOTICES.md),
[privacy](PRIVACY.md), and [security](SECURITY.md).
