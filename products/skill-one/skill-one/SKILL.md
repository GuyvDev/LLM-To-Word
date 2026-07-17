---
name: skill-one
description: Create deterministic, professionally formatted Microsoft Word DOCX files with native RTL/BiDi, OMML equations, RTL tables, code, lists, links, and structural validation. Use when an agent must generate or deliver a polished .docx document from user content without an external conversion API.
---

# Skill One

Create the document through the bundled deterministic compiler. Never construct
OOXML manually and never return an unvalidated DOCX.

## Workflow

1. Read `references/docspec.md` before creating a document.
2. Translate the user's requested content and structure into DocSpec 1.0 JSON.
3. Preserve natural Hebrew, Arabic, English, numbers, symbols, and spaces in the
   JSON. Preserve table columns in semantic order. Never use the em dash
   character (`—`); use the regular hyphen (`-`) instead. The compiler enforces
   this rule as a final safeguard.
4. For a long multi-section document, estimate section sizes and insert
   `page_break` blocks where they prevent a crowded first page or a sparse
   trailing page. Keep a heading with the content that follows it.
5. Save the specification as UTF-8 JSON in the working directory.
6. Run:

   ```bash
   python scripts/docx_brain.py build input.json output.docx --report report.json
   ```

7. Read the command result or report. Return the DOCX only when `valid` is
   `true`. If validation fails, correct the DocSpec and rebuild; do not patch the
   DOCX package.
8. Provide the output file and a short description of the document. Do not
   expose intermediate JSON unless requested.
9. For visual review, never capture the desktop, an application window, or any
   other screen content. Convert the DOCX to PDF, rasterize only the PDF pages
   into images, and inspect those page images.

## Existing DOCX validation

Validate a package without rebuilding it:

```bash
python scripts/docx_brain.py validate document.docx --json
```

Treat any nonzero exit status as a failed document.

## Provider setup

Read `references/provider-adapters.md` only when installing or configuring this
skill for Claude or a ChatGPT custom GPT.
