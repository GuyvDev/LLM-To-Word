# DocSpec 1.0

DocSpec is the provider-neutral input to Skill One. Emit UTF-8 JSON and pass it
to `scripts/docx_brain.py build`. Do not write OOXML directly.

## Root

```json
{
  "version": "1.0",
  "metadata": {"title": "Document title", "author": "Skill One"},
  "blocks": []
}
```

`version` must be `1.0`. `blocks` is required. Metadata is optional.

## Blocks

- `{"type":"heading","level":1,"content":"Title"}` — levels 1–6.
- `{"type":"paragraph","content":[...]}` — normal paragraph.
- `{"type":"quote","content":[...]}` — shaded directional quotation.
- `{"type":"equation","latex":"..."}` — centered native OMML.
- `{"type":"code","language":"bash","text":"echo ok"}` — LTR code block.
- `{"type":"list","ordered":false,"items":["One", [...]]}` — one paragraph per item.
- `{"type":"table","headers":[...],"rows":[[...]],"direction":"auto"}`.
- `{"type":"horizontal_rule"}`.
- `{"type":"page_break"}`.

Use `page_break` deliberately in long reports to keep major sections visually
balanced. Do not place a break between a heading and its first content block.

Paragraph-like blocks accept `direction` as `auto`, `rtl`, or `ltr`. Use
`auto` unless the requested direction must override the content.

## Inline content

Content may be a string or an array containing:

```json
[
  {"text":"Bold", "bold":true},
  {"text":" italic", "italic":true},
  {"text":" code", "code":true},
  {"text":" highlighted", "highlight":true},
  {"type":"equation", "latex":"x^2"},
  {"type":"link", "text":"OpenAI", "url":"https://openai.com"},
  {"type":"break"}
]
```

Text runs also support `underline`, `strike`, `superscript`, and `subscript`.
Keep natural spaces in text. The compiler converts only mixed-direction run
boundaries to nonbreaking Word-stable spaces.

Do not use the em dash character (`—`) in DocSpec text. Use the regular hyphen
(`-`) instead. The compiler also replaces any em dash that reaches it, including
inside headings, paragraphs, lists, tables, links, metadata, and code blocks.

## Tables

`headers` is an array of cells. `rows` is an array of equally-sized row arrays.
A cell may be a string or inline-content array. Never reverse Hebrew table
columns: preserve semantic source order and set `direction` to `rtl` or `auto`.

## Equations

Use LaTeX without `$` delimiters. Supported structures include fractions,
roots, subscript/superscript, matrices, Greek letters, functions, relations,
operators, arrows, set symbols, and common delimiters. Unknown commands remain
visible for audit and cause validation to fail if they leak into Word text.
