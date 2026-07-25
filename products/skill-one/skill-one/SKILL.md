---
name: skill-one
description: Create polished Microsoft Word DOCX files from Markdown through the canonical md2docx compiler. Use for professional Word output with RTL/BiDi, tables, equations, code, lists, links, structural validation, complete PDF rendering, and a mandatory all-page visual release gate. Use the full DOCX authoring workflow or require a template when the user requests highly designed, branded, executive, editorial, investor-ready, stylish, or elegant output.
---

# Skill One

Compile content with the bundled canonical engine. Never write OOXML, DocSpec,
or replacement conversion code.

## Choose the mode

**Conversion mode is the default whenever the user supplies Markdown, text, or
a file.** Preserve the complete input exactly: do not paraphrase, summarize,
translate, reorder, omit, rename headings, change list/table structure, replace
arrows, or add content. Save uploaded Markdown by copying its bytes. For pasted
content, preserve every character and line in logical order.

Use **authoring mode** only when the user explicitly asks you to create, edit,
rewrite, translate, summarize, reorganize, or restyle content. State that
content will change before doing so.

If the user asks for highly designed, branded, executive, editorial,
investor-ready, stylish, or elegant output, do not assume plain Markdown
conversion is sufficient. Use the full authoring workflow and the strongest
supported design treatment. If the available compiler cannot meet the requested
visual standard, require an approved DOCX template or state the limitation
before building. Never promise elegance that the renderer cannot produce.

## Workflow

1. Read `references/document-design.md`. In conversion mode it is descriptive,
   not permission to rewrite the input.
2. In conversion mode, save the exact supplied content as UTF-8 Markdown. In
   authoring mode, draft the complete content and apply the design guide.
3. Preserve natural Hebrew, Arabic, English, numbers, punctuation, Markdown
   tables, lists, fenced code, and LaTeX. Do not add Unicode BiDi controls. Use
   `-` instead of the em dash character.
4. Save the final Markdown as `input.md`.
5. Locate `scripts/docx_brain.py`. For supplied files, calculate the SHA-256
   before any model processing and keep it as `SOURCE_SHA256`. Check the
   bundled runtime and the authored Markdown:

   ```bash
   python scripts/docx_brain.py doctor --json
   python scripts/docx_brain.py preflight input.md --json
   ```

   Fix authored Markdown syntax errors before continuing. In conversion mode,
   never change supplied content to silence a check; report the input problem.
6. Run the single self-validating build and review command:

   ```bash
   python scripts/docx_brain.py build input.md output.docx --source llm --report report.json --review-text extracted.txt
   ```

   When `SOURCE_SHA256` exists, also pass
   `--expected-input-sha256 SOURCE_SHA256`. The command verifies the approved
   runtime hash, runs its self-test, preflights Markdown, compiles, validates
   the package and OOXML semantics, extracts visible text, checks source-text
   fidelity and feature coverage, and performs a trusted deterministic replay.
   Do not replace, patch, imitate, or skip this command.
7. Read `extracted.txt`. Confirm its headings, sections, values, table cells,
   code, and natural reading order match the intended final `input.md`. This
   human-readable review is mandatory even though the machine fidelity gate
   also runs.
8. Treat the successful DOCX build as a **draft**, not a deliverable. Machine
   validation is necessary but never sufficient.
9. Require `report.json` to have `valid: true`, `checks.engine` equal to
   `md2docx-core`, and every value below equal to `true`:

   - `checks.engine_verified`
   - `checks.runtime_manifest_verified`
   - `checks.markdown_preflight`
   - `checks.core_self_test`
   - `checks.feature_coverage`
   - `checks.ooxml_semantics`
   - `checks.text_fidelity`
   - `checks.deterministic_replay`
   - `checks.input_sha256_verified`

   In conversion mode, confirm `input_sha256` belongs to the exact supplied
   input. Never patch the DOCX or report.

## Mandatory visual release gate

Visual inspection is mandatory for every generated DOCX. It is never optional
and is not conditional on document value, task duration, or machine validation.

After each successful build:

1. Convert the exact final DOCX to PDF using an actual DOCX renderer.
2. Rasterize **every** PDF page to a separate PNG at readable resolution.
3. Inspect **every** page image visually. Sampling, thumbnails, first-page-only
   review, or selected-page review is forbidden.
4. Check for clipping, overflow, unreadably small or crowded text, weak visual
   hierarchy, excessive blank space, orphan headings, malformed tables,
   incorrect list indentation or bullets, broken RTL, and malformed mixed
   Hebrew-English text.
5. Create `visual-report.json` with this exact minimum structure:

   ```json
   {
     "visual_valid": true,
     "docx_sha256": "<sha256>",
     "pdf_sha256": "<sha256>",
     "pages_expected": 1,
     "pages_rendered": 1,
     "pages_reviewed": 1,
     "reviewed_pages": [1],
     "issues": [],
     "rebuild_count": 0
   }
   ```

6. If any issue is found, set `visual_valid` to `false`, list every issue with
   page numbers, revise `input.md` using supported authoring changes, rebuild,
   re-render, and inspect every page again. Repeat until the report passes or
   the requested visual standard cannot be achieved.
7. Run the deterministic gate validator:

   ```bash
   python scripts/visual_gate.py \
     --docx output.docx \
     --pdf output.pdf \
     --pages-dir rendered-pages \
     --report visual-report.json
   ```

Do not return or link the DOCX unless the validator exits successfully and all
of these conditions are true:

- the PDF exists;
- at least one rasterized page image exists;
- `pages_rendered == pages_expected`;
- `pages_reviewed == pages_expected`;
- `reviewed_pages` is exactly `[1, 2, ..., pages_expected]`;
- `visual_valid` is `true`;
- `issues` is an empty array;
- `docx_sha256` matches the exact DOCX being delivered;
- `pdf_sha256` matches the rendered PDF.

If the renderer, PDF conversion tool, page rasterizer, or visual inspection is
unavailable or fails, do not deliver the DOCX as completed. Do not call it
finished, approved, polished, elegant, or visually validated. State that the
mandatory visual gate could not be completed.

Never claim visual validation based on `report.json`, `extracted.txt`, package
validity, text fidelity, OOXML semantics, deterministic replay, or the mere
existence of a PDF. These do not substitute for inspection of every page image.

## Release response

Only after both the machine gate and mandatory visual gate pass, return:

- the final DOCX;
- the rendered PDF;
- `report.json`;
- `extracted.txt`;
- `visual-report.json`.

State the exact number of pages inspected and the number of rebuilds. Never
claim a visual check without these artifacts and a passing validator result.

## Existing DOCX validation

```bash
python scripts/docx_brain.py validate document.docx --json
```

Treat a nonzero exit status as failure.

To review an existing DOCX and prove it came from a specific `input.md`, run:

```bash
python scripts/docx_brain.py review input.md document.docx --source llm --report verify.json --review-text extracted.txt
```

`validate` checks package structure and provenance only. It is not an
acceptance test. `review` is the acceptance command for an existing DOCX. An
existing DOCX still requires the mandatory visual release gate before delivery.

## Provider setup

Read `references/provider-adapters.md` only when installing or configuring the
skill for ChatGPT, Claude, or another hosted Agent Skills provider.
