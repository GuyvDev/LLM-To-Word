# md2docx

Convert Markdown files containing **Hebrew (RTL) text**, **LaTeX math**, and
standard formatting into natively-formatted Microsoft Word `.docx` files —
with no image rendering, no COM automation, and no LibreOffice dependency.

> **Pure Python.** Math is embedded as native OMML equations. Hebrew text is
> properly right-aligned with BiDi runs. Tables, lists, blockquotes, and all
> common Markdown elements are supported.

---

## Features

| Feature | Details |
|---|---|
| **Math** | LaTeX → MathML → OMML (native Word equations, not images) |
| **Hebrew / Arabic RTL** | Auto-detected; `<w:bidi>`, `<w:rtl>`, `w:cs` font injected |
| **Mixed BiDi** | Hebrew + Latin on one line — each script gets its own `<w:r>` run |
| **Headings** | H1–H6 (`#` … `######`) with academic black heading styles |
| **Inline formatting** | `**bold**` · `*italic*` · `` `code` `` · `~~strikethrough~~` |
| **Block equations** | `$$…$$` on its own line — display centred equation |
| **Inline equations** | `$…$` anywhere in a paragraph |
| **Tables** | Pipe syntax — centred, bold header row, inline markup in cells |
| **Lists** | Unordered (`-` / `*` / `+`) and ordered (`1.`) |
| **Blockquotes** | `>` — italic, indented, grey left border |
| **Horizontal rule** | `---` / `***` / `___` |
| **Academic style** | Times New Roman 12 pt, 1.5× spacing, standard margins |

---

## Installation

```bash
pip install -r requirements.txt
```

**Dependencies** (see `requirements.txt`):

| Package | Purpose |
|---|---|
| `python-docx` | Word document container and high-level API |
| `lxml` | Low-level XML for injecting OMML math and BiDi properties |
| `latex2mathml` | LaTeX string → W3C MathML XML |

Requires **Python 3.12+** for the supported container runtime.

---

## Word Add-in (Office) — optional beta

The optional Word task-pane add-in provides an AI chat over the current Word selection. It sends a Word-formatting contract with every provider request, converts returned Markdown locally in JavaScript, and inserts native Word content directly. No md2docx conversion API is used. See `office-addin/README.md` for BYOK and credential-broker guidance.

See `office-addin/README.md` for deployment and validation steps.

## Clipboard Service Plan

`CLIPBOARD_SERVICE_PLAN.md` documents the production Windows installer, local clipboard helper, and `Ctrl+Alt+M` shortcut.

---

## Usage

```bash
# Convert a file
python md2docx.py input.txt -o output.docx

# Run the built-in feature demo
python md2docx.py

# Custom fonts
python md2docx.py input.txt -o output.docx --font "David" --base-font "David"
```

### CLI options

| Flag | Default | Description |
|---|---|---|
| `INPUT` | _(none)_ | Input text file path. Omit to run the built-in demo. |
| `-o / --output` | `result.docx` | Output `.docx` path |
| `--font` | `Arial` | Complex-script font for Hebrew / Arabic glyphs (`w:cs` slot) |
| `--base-font` | `Times New Roman` | Body and heading font |

---

## Quick Example

**Input (`input.txt`):**

```
# Mathematical Foundations

The quadratic formula solves $ax^2 + bx + c = 0$:

$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$

## Hebrew Section

שלום עולם! זוהי פסקה בעברית הכתובה מימין לשמאל.

## Mixed BiDi

התוכנה מתחילה עם main()
הפונקציה קוראת ל־initialize()

## Formatting

This paragraph has **bold text**, *italic text*, `inline code`, and ~~strikethrough~~.

## Table

| Formula | Description |
|---|---|
| $E = mc^2$ | Energy-mass equivalence |
| $a^2 + b^2 = c^2$ | Pythagorean theorem |

## Lists

- First bullet item
- Second item with $x^2 + y^2$ inline math

1. First numbered item
2. Second numbered item

## Blockquote

> Mathematics is the language of the universe.
```

**Command:**

```bash
python md2docx.py input.txt -o output.docx
```

**Result — what Word renders:**

- The `# Mathematical Foundations` title appears centred, 22 pt, bold, underlined.
- `$$…$$` becomes a native Word equation (editable in Word's equation editor).
- Hebrew paragraphs are automatically right-aligned with proper BiDi shaping.
- `main()` stays at the visual left edge of its Hebrew RTL paragraph.
- The table is centred on the page with a bold header row and centred cell content.

---

## Supported Markdown Syntax

### Headings

```
# Heading 1      →  22 pt, bold, underline, centred
## Heading 2     →  14 pt, bold, left-aligned
### Heading 3    →  12 pt, bold italic, left-aligned
#### Heading 4   →  11 pt, bold, left-aligned
##### Heading 5  →  10 pt, bold, left-aligned
###### Heading 6 →  10 pt, bold italic, left-aligned
```

> **Tip:** Do not add a blank line after a heading. Heading styles already
> include spacing-before. An empty line creates a double gap.

### Math

```
Inline:  $a^2 + b^2 = c^2$
Block:   $$\frac{d}{dx}\sin(x) = \cos(x)$$
```

Block equations must be on their own line, starting and ending with `$$`.
Supported LaTeX: fractions, roots, super/subscripts, operators (`\pm`, `\cdot`,
`\neq`), functions (`\sin`, `\cos`, `\frac`), and more via `latex2mathml`.

### Inline Formatting

```
**bold**          →  bold run
*italic*          →  italic run
`code`            →  Courier New 10 pt monospace run
~~strikethrough~~ →  strikethrough run
**$E = mc^2$**    →  bold text wrapping a math equation
```

### Lists

```
- Unordered item       (also works with * or +)
1. Ordered item
2. Second ordered item
```

### Tables

```
| Header A  | Header B  |
|-----------|-----------|
| cell      | $x^2$     |
| **bold**  | `code`    |
```

- Header row rendered **bold**.
- LTR tables use centred cell content.
- Hebrew/Arabic tables switch to RTL cell direction and visual column flow
  (first Markdown column appears on the right).
- Table centred on the page.
- Cell content supports all inline markup.

### Blockquote and Horizontal Rule

```
> Quoted text — italic, indented, grey left border.

---
```

### Hebrew / RTL

No special syntax. Hebrew and Arabic characters are auto-detected.

```
שלום עולם!                         →  RTL paragraph, right-aligned
התוכנה מתחילה עם main()            →  Mixed BiDi: Hebrew + LTR island
הנוסחה: $x = \frac{-b}{2a}$       →  Hebrew + inline math
```

---

## Converting the Output to PDF

The tool produces a `.docx`. For PDF output, use the **Windows host** — Word
COM automation gives pixel-perfect rendering of Hebrew BiDi and OMML equations.

**From WSL / the dev VM terminal (PowerShell Word COM):**

```bash
powershell.exe -Command "
  \$w = New-Object -ComObject Word.Application; \$w.Visible = \$false;
  \$d = \$w.Documents.Open('C:\\full\\path\\output.docx');
  \$d.SaveAs([ref]'C:\\full\\path\\output.pdf', [ref]17);
  \$d.Close(); \$w.Quit()
"
```

**On the Windows host (Python `docx2pdf`):**

```powershell
pip install docx2pdf
docx2pdf output.docx output.pdf
```

See `FORMATTING_GUIDE.md` → *Converting to PDF* for all options including
LibreOffice headless as a fallback.

---

## How It Works

### Why not use python-docx's normal API?

python-docx exposes no API for two critical features:

1. **BiDi / RTL** — requires injecting `<w:bidi/>` into `<w:pPr>` and `<w:rtl/>` into `<w:rPr>` with `w:cs` font slots. python-docx has no method for this.
2. **OMML equations** — Word uses its own Office Math Markup Language, not MathML. `<m:oMath>` must be appended directly as a sibling of `<w:r>` inside `<w:p>`.

Both are handled by direct lxml element-tree manipulation.

### Math pipeline

```
LaTeX string
    │
    ▼ latex2mathml.converter.convert()
W3C MathML XML string
    │
    ▼ lxml.etree.fromstring()
MathML element tree
    │
    ▼ _convert_node()  (recursive MathML → OMML translator)
OMML <m:oMath> element
    │
    ▼ para._element.append()
Word paragraph with native equation
```

### RTL / BiDi pipeline

```
Hebrew text detected (_is_rtl)
    │
    ├─▶ _set_rtl_para()
    │     <w:bidi w:val="1"/>          paragraph base direction = RTL
    │     <w:jc w:val="start"/>        physical-right alignment (not "right"!
    │                                  OOXML §17.3.1.17 reverses left/right
    │                                  under bidi — "start" is direction-aware)
    │
    └─▶ _split_rtl_ltr()              split mixed line by script direction
          Hebrew segment → _set_rtl_run()
            <w:rFonts w:cs="Arial"/>   Hebrew glyphs come from cs= font slot
            <w:rtl w:val="1"/>
            <w:lang w:bidi="he-IL"/>
          Latin segment  → plain run  (no <w:rtl/>, BiDi algo positions it)
```

---

## Project Structure

```
md2docx.py          Main script and library
api/                Stateless FastAPI service
web/                Browser client
extension/          Chrome extension
office-addin/       Optional Word add-in
tests/              Automated regression tests
requirements.txt    Python dependencies
sample_input.txt    Example input file demonstrating all features
```

---

## License

MIT

---

## Contributing

Bug reports and pull requests welcome. When reporting a rendering issue, please
include the minimal `.txt` input that reproduces the problem and a description
of the expected vs. actual Word output.


## Open-source and self-hosting

md2docx is MIT licensed. The core converter and conversion API have no login, payment, conversion API-key, quota-database, watermark, or telemetry requirement. The optional Office AI feature uses a provider credential supplied by the user. Run it locally as a CLI/library, or deploy the included stateless API:

```bash
docker build -t md2docx .
docker run --rm -p 8000:8000 md2docx

# Convert through the API
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{"markdown":"# Hello"}' \
  --output result.docx
```

The optional API exposes `POST /convert`, `POST /convert/base64`, and `GET /health` for web/self-hosted integrations. The Chrome extension does not use it: conversion is bundled and runs locally. See [extension/README.md](extension/README.md), [DEPLOYMENT.md](DEPLOYMENT.md), [PRIVACY.md](PRIVACY.md), and [ROADMAP.md](ROADMAP.md).
