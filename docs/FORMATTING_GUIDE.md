# Markdown formatting guide

This guide describes the canonical Rust converter used by the Chrome
extension, clipboard helper, and Word add-in. Skill One uses the stricter
[DocSpec contract](../products/skill-one/skill-one/references/docspec.md).

## Default Word theme

- Arial 11.5 pt body text.
- 1.15 line spacing and 4 pt after body paragraphs.
- A4 page with compact 0.79 inch margins.
- Six native Word heading styles with keep-with-next behavior.
- Restrained blue/gray heading hierarchy and an H1 bottom border.
- Centered display equations.
- Centered table cells with subtle borders, header fill, and alternate rows.
- Direction-aware quotation border and fill.

| Heading | Size | Space before | Space after |
|---|---:|---:|---:|
| H1 | 21 pt | 0 pt | 5 pt |
| H2 | 16 pt | 9 pt | 3 pt |
| H3 | 13.5 pt | 7 pt | 2 pt |
| H4 | 12 pt | 6 pt | 2 pt |
| H5 | 11 pt | 5 pt | 1.5 pt |
| H6 | 10.5 pt | 4 pt | 1.5 pt |

Blank Markdown lines separate blocks but do not generate decorative empty Word
paragraphs. Use ordinary CommonMark spacing; do not add repeated blank lines to
force page layout.

## Supported Markdown

### Headings

ATX headings H1 through H6 and Setext H1/H2 become native Word heading styles.

```markdown
# Document title
## Section
### Subsection
```

### Inline formatting

```markdown
**bold**
*italic*
~~strikethrough~~
`inline code`
[link label](https://example.com)
==highlight==
++underline++
H~2~O
x^2^
```

Nested emphasis supported by CommonMark is preserved. Links remain visible and
clickable in rich output. Images preserve their label and URL; the converter
does not fetch remote image bytes.

### Lists and task lists

Ordered, unordered, nested, and task lists are supported. Word owns the visible
list numbering.

```markdown
- First item
  - Nested item
1. Ordered item
2. Next item
- [x] Complete
- [ ] Pending
```

### Blockquotes

```markdown
> Important text with **formatting** and $x^2$.
```

Blockquotes use a subtle fill and a border on the correct visual side for the
paragraph direction.

### Code

Indented code and fenced code are supported. Arbitrary fence info strings such
as `bash`, `python`, `json`, or another language identifier are preserved.

````markdown
```bash
printf '%s\n' "hello"
```
````

Code remains LTR even when surrounded by an RTL paragraph.

### Tables

```markdown
| Model | Accuracy | Time |
|---|---:|---:|
| Baseline | 88.2% | 8 min |
| Transformer | **94.7%** | 12 min |
```

- GFM tables and escaped pipe characters are supported.
- Every cell is horizontally and vertically centered.
- Header and alternating-row fills use the shared visual theme.
- Alignment hints are accepted, but the product intentionally centers all
  cells.
- Hebrew and Arabic tables keep semantic source column order and receive Word's
  visual RTL table property. Do not reverse source columns manually.

### Other block structures

- Horizontal rules from `---`, `***`, or `___`.
- Footnotes and description lists.
- Autolinks.
- Nested blockquotes and lists.
- Sanitized inline HTML. Unsafe HTML is never executed.

## Mathematics

Inline math uses single dollar delimiters and display math uses double dollar
delimiters.

```markdown
The update is $\theta_{t+1}=\theta_t-\alpha\nabla J(\theta_t)$.

$$\frac{1}{m}\sum_{i=1}^{m}(h_\theta(x_i)-y_i)^2$$
```

Supported constructs include:

- Fractions and square or indexed roots.
- Subscript and superscript combinations.
- Greek symbols, operators, relations, arrows, and set symbols.
- Functions such as sine, cosine, logarithm, limit, minimum, and maximum.
- Bracketed expressions and matrices.

DOCX output uses native editable OMML, not images or raw LaTeX. Formatted
clipboard output uses Presentation MathML for Word import. Malformed or unknown
math degrades safely and never executes input.

## Hebrew, Arabic, and mixed BiDi text

RTL content is detected automatically.

- RTL paragraphs receive native Word BiDi paragraph properties.
- RTL runs receive complex-script font, language, and RTL properties.
- LTR English, code, paths, numbers, and equations remain readable islands.
- Mixed-direction boundary spaces become nonbreaking Word-stable spaces where
  Word would otherwise reorder or suppress them.
- Brackets, punctuation, currency, percentages, and API paths are covered by
  the conformance suite.

Preserve natural source text and spaces. Do not reverse Hebrew/Arabic
characters or table columns before conversion.

## Source profiles

The canonical compiler supports CommonMark, GFM, and provider-oriented LLM
profiles. The Chrome extension normally auto-detects the profile from the
current page and provider. Users can override the source when capture markup
changes or paste Markdown directly.

The shared compatibility matrix and edge cases are documented in
[MARKDOWN_CONFORMANCE.md](../tests/MARKDOWN_CONFORMANCE.md).

## PDF and visual review

DOCX is the primary output. For automated visual review:

1. Convert the DOCX to PDF with Microsoft Word export or LibreOffice headless.
2. Rasterize only the resulting PDF pages.
3. Inspect the page images for layout, RTL, BiDi, math, tables, lists, code, and
   clipping.

Never capture the desktop or an application window. A human release tester
must separately open the DOCX in Microsoft Word because LibreOffice and Word
can differ in OMML and BiDi layout.
