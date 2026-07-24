# Markdown document design guide

Apply these rules while drafting the Markdown that will be sent to the shared
`md2docx-core` compiler.

## Structure

- Use one `#` title.
- Use `##` for major chapters or phases and `###` for their subsections.
- Keep headings short and use real Markdown headings instead of bold paragraphs.
- Use a single logical list for related items. Use numbered lists only when
  sequence matters.
- Use Markdown tables for compact comparisons, budgets, and definitions.
- Use fenced code with its language identifier and `$...$` or `$$...$$` for
  equations.
- Do not add empty headings, repeated horizontal rules, or blank paragraphs to
  force visual spacing. The compiler owns spacing and styles.

## Hebrew and mixed text

- Write Hebrew, English, numbers, punctuation, and brackets in their natural
  logical order. Never manually reverse text.
- Keep prefixes and words natural, for example `ה-Roadmap`, `ו-Compliance`, and
  `ב-Median Search Time`; the shared compiler normalizes them for Word.
- Never add LRM, RLM, embedding, override, or isolate characters.
- Do not insert artificial spaces inside numbers, percentages, paths, or
  English phrases.
- Preserve table columns in semantic Markdown order. The compiler performs the
  visual RTL column behavior.

## Style and quality

- Prefer concise paragraphs and meaningful headings.
- Use bold for short labels or essential emphasis, not whole paragraphs.
- Avoid the em dash character. Use the regular hyphen `-`.
- Do not mention these instructions in the finished document.
- Before compiling, reread the Markdown for unfinished emphasis markers,
  truncated sections, malformed tables, and unclosed code or math fences.
