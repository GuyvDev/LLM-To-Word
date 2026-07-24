# Provider adapters

Claude and ChatGPT follow the same workflow: generate final UTF-8 Markdown,
save it as `input.md`, and run the bundled `scripts/docx_brain.py`. The launcher
must find and execute the bundled `md2docx-core`; it must never reimplement DOCX
generation with Python or `python-docx`.

When the user supplies content, conversion mode is mandatory unless they
explicitly request editing. Copy an uploaded Markdown file byte-for-byte. Do
not summarize, improve, restructure, rename headings, replace punctuation, or
drop sections before compilation. A provider-generated rewrite is a different
document even if it uses the same compiler.

For a ChatGPT custom GPT, enable Code Interpreter, upload the complete Skill One
ZIP, extract it under `/mnt/data`, and execute the bundled launcher. For Claude,
install or upload the same complete skill directory and enable file execution.

Always request `--review-text extracted.txt`, then read the extracted text and
compare its headings, sections, values, table cells, and reading order with the
intended final Markdown. Return a DOCX only after the report contains
`valid: true`, `checks.engine: md2docx-core`, and all nine boolean checks
documented in `SKILL.md`. Return `report.json` and `extracted.txt` with the DOCX
so the user can inspect the receipt. Never claim success from prose reasoning,
DOCX existence, or the weaker `validate` command alone. Identical Markdown
bytes and the same `--source` profile produce the same DOCX bytes across the
Windows and Linux runtimes and the other products using that profile.

For a ChatGPT custom GPT, put the mandatory build command and nine acceptance
checks directly in the GPT Instructions. Keep the complete ZIP available to
Code Interpreter. The model may author `input.md`, but it must not implement,
patch, or replace the build and verification logic.
