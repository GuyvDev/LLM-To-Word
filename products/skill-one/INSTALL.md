# Install Skill One

Skill One is self-contained and needs Python 3 plus its bundled native
`md2docx-core`. It does not need an API, account, hosted service, or Docker at
runtime.

## Build the upload package

```powershell
.\scripts\build_converter_core.ps1
.\scripts\build_linux_core.ps1
python products\skill-one\package_skill.py
```

## Codex

Copy the complete `products/skill-one/skill-one` directory into the Codex
skills directory, then start a new session and invoke `$skill-one`.

## Direct local use

```bash
python products/skill-one/skill-one/scripts/docx_brain.py doctor --json
python products/skill-one/skill-one/scripts/docx_brain.py preflight input.md --source llm --json
python products/skill-one/skill-one/scripts/docx_brain.py build input.md output.docx --source llm --report report.json --review-text extracted.txt
python products/skill-one/skill-one/scripts/docx_brain.py review input.md output.docx --source llm --report verify.json --review-text extracted.txt
python products/skill-one/skill-one/scripts/visual_gate.py --docx output.docx --pdf output.pdf --pages-dir rendered-pages --report visual-report.json
```

Use the same Markdown and `--source` value in another product when comparing
byte-for-byte output. Accept a build only when `valid` and every boolean in
`checks` are true, then read `extracted.txt`. Render the exact DOCX, inspect
every rasterized PDF page, and require the visual gate to pass. Use `review`,
not package-only `validate`, as the machine acceptance command for an existing
DOCX.
