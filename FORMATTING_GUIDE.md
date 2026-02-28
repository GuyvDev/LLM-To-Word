# md2docx Formatting Guide

A reference for AI assistants and writers preparing Markdown source files for
the md2docx converter. Covers every supported element, default rendering
behaviour, and spacing conventions that differ from standard Markdown.

---

## How to Run

```
python md2docx.py input.txt -o output.docx
python md2docx.py input.txt -o output.docx --font "Arial" --base-font "Times New Roman"
```

---

## Critical Spacing Rules

These are the most common mistakes when writing for md2docx.

**Do NOT add a blank line after a heading.**
The heading styles already include space-before (18 pt for H1, 14 pt for H2,
12 pt for H3) and space-after (4 pt). An empty line produces an extra empty
paragraph, creating a visible gap. Write:

```
## My Section
First sentence of the section.
```

Not:

```
## My Section

First sentence of the section.   ← unwanted gap
```

**One blank line = one empty paragraph (1.5-line gap).**
Use blank lines only to create deliberate visual separation between blocks.
Avoid consecutive blank lines.

**No blank line needed around block equations, lists, or tables.**
They render cleanly when placed directly after the preceding text.

---

## Headings

```
# Heading 1
## Heading 2
### Heading 3
```

| Level | Font size | Style                      | Alignment | Space before |
|-------|-----------|----------------------------|-----------|--------------|
| H1    | 22 pt     | Bold, underline            | Centred   | 18 pt        |
| H2    | 14 pt     | Bold                       | Left      | 14 pt        |
| H3    | 12 pt     | Bold italic                | Left      | 12 pt        |

All headings use the document base font (default: Times New Roman) in black.
Only three levels are supported. There is no H4 or deeper.

---

## Paragraphs

Plain text lines become body paragraphs:
- Font: Times New Roman 12 pt (configurable via `--base-font`)
- Line spacing: 1.5×
- Space before/after: 0 pt (spacing comes entirely from line height)

---

## Inline Formatting

| Syntax           | Result                              |
|------------------|-------------------------------------|
| `**bold**`       | Bold                                |
| `*italic*`       | Italic                              |
| `` `code` ``     | Monospace, Courier New 10 pt        |
| `~~strike~~`     | Strikethrough                       |
| `$formula$`      | Inline OMML math equation           |
| `$$formula$$`    | Display math (also works inline)    |

Inline markup may be combined with math: `**$E = mc^2$**` renders as bold
surrounding text with a native math equation inside.

Simple nesting is supported: `**bold *italic* bold**` does NOT work (the
`[^*]+` pattern excludes the inner star). Keep formatting non-nested.

---

## Mathematics

### Block equation (display, centred on its own line)

```
$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$
```

The entire line must start with `$$` and end with `$$`. The LaTeX content
between them is converted to native OMML (Office Math Markup Language) — no
images, no MathType.

### Inline equation

```
The formula $a^2 + b^2 = c^2$ holds for all right triangles.
```

### Supported LaTeX constructs

| LaTeX            | Meaning                       |
|------------------|-------------------------------|
| `\frac{a}{b}`    | Fraction                      |
| `\sqrt{x}`       | Square root                   |
| `\sqrt[n]{x}`    | nth root                      |
| `x^{2}`          | Superscript                   |
| `x_{i}`          | Subscript                     |
| `x_{i}^{2}`      | Sub + superscript             |
| `\pm`, `\cdot`   | Operators                     |
| `\sin`, `\cos`   | Functions                     |
| `\frac{d}{dx}`   | Derivative notation           |
| `\neq`, `\leq`   | Relations                     |

---

## Lists

### Unordered list

```
- First item
- Second item with $x^2$ inline math
- Third item with **bold** text
```

Markers `- `, `* `, and `+ ` are all equivalent.

### Ordered list

```
1. First item
2. Second item
3. Third item
```

The number prefix is ignored by the converter — Word auto-numbers the items.
Do not add blank lines between list items.

---

## Blockquotes

```
> Quoted text rendered italic with a grey left border.
```

Each `> ` line is a separate blockquote paragraph. Multi-line blockquotes
require the `> ` prefix on every line. Inline markup and math work inside
blockquotes.

---

## Horizontal Rule

Any of these produces a thin horizontal line:

```
---
***
___
```

(Three or more characters, nothing else on the line.)

---

## Tables

```
| Header A     | Header B     | Header C     |
|--------------|--------------|--------------|
| cell content | cell content | cell content |
| $E = mc^2$   | **bold**     | `code`       |
```

- The separator row (`|---|`) identifies the header row (rendered **bold**).
- All cell content is horizontally centred by default.
- The table itself is centred on the page.
- Cell content supports all inline markup: `$math$`, `**bold**`, `*italic*`,
  `` `code` ``, `~~strike~~`.
- Column alignment hints (`:---:`, `---:`) in the separator row are parsed
  but currently ignored — all cells centre regardless.
- No blank line is needed before or after a table.

---

## Hebrew and Arabic (RTL) Text

RTL characters are auto-detected. No special syntax is required.

```
שלום עולם! זוהי פסקה בעברית הכתובה מימין לשמאל.
```

- The paragraph receives `<w:bidi/>` and `<w:jc w:val="start"/>` (physical
  right alignment).
- Runs use `w:cs="Arial"` for the complex-script font slot.

### Mixed BiDi (Hebrew + Latin on one line)

```
התוכנה מתחילה עם main()
הפונקציה קוראת ל־initialize()
```

Each contiguous script block becomes its own `<w:r>` run. Hebrew runs get
`<w:rtl/>`, Latin runs do not. The Unicode BiDi algorithm then places the
Latin island at the visual left edge of the RTL paragraph:

```
  main()          התוכנה מתחילה עם
```

Inline math on a Hebrew line also works: `הנוסחה היא: $x = \frac{-b}{2a}$`

---

## Complete Minimal Example

```
# Document Title
## Introduction
This document demonstrates all supported features.

## Mathematics
The quadratic formula:
$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$
Inline: the hypotenuse is $\sqrt{a^2 + b^2}$.
## Formatting
Regular text with **bold**, *italic*, `code`, and ~~strikethrough~~.
## Hebrew
שלום עולם! זוהי פסקה בעברית.
המחלקה נקראת MyClass
## Lists
- First item
- Second item
1. Numbered one
2. Numbered two
## Quote
> An important note here.
---
## Table
| Name  | Value               |
|-------|---------------------|
| Pi    | $\pi \approx 3.14$  |
| Euler | $e \approx 2.718$   |
```

---

## Things to Avoid

| Anti-pattern                          | Why                                              |
|---------------------------------------|--------------------------------------------------|
| Blank line after a heading            | Creates double gap (heading already has spacing) |
| Consecutive blank lines               | Each empty line = one empty paragraph row        |
| Four-space indented code blocks       | Not supported; use `` `inline code` ``           |
| Fenced code blocks (` ``` `)          | Not supported; content renders as plain text     |
| Inline HTML tags                      | Not parsed; rendered as literal text             |
| Images `![alt](url)`                  | Not supported                                    |
| Links `[text](url)`                   | Not supported; rendered as literal text          |
| `####` H4 or deeper headings          | Not supported; renders as a plain paragraph      |
| Nested block elements                 | Lists inside blockquotes, etc. are not supported |
