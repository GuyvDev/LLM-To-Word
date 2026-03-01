# AGENTS Guidelines – tools-word / md2docx

This file is read by AI agents (Copilot, Codex, etc.) before working in this
directory.  Follow all rules below.

---

## 1. Python Runtime

The system Python is **Python 3.8** with packages in `/home/dev/.local/lib/python3.8/site-packages`.  
Do **not** use the venv at `/home/dev/.venv` — it has no `pip` and no packages.

| Task | Command |
|------|---------|
| Run conversion | `python3.8 md2docx.py sample_input.txt -o result.docx` |
| Install a package | `pip3 install <pkg>` (installs into `/home/dev/.local/…`) |
| Confirm a package | `pip3 show <pkg>` |

---

## 2. Test & Review Workflow

Run this sequence after **every change** to `md2docx.py`:

```bash
# Step 1 – regenerate result.docx from the canonical sample
cd /home/dev/dev-vm/Projects/tools-word
python3.8 md2docx.py sample_input.txt -o result.docx

# Step 2 – convert to PDF via Windows Word COM (no LibreOffice)
powershell.exe -Command "
  \$docx = '\\\\wsl.localhost\\Ubuntu\\home\\dev\\dev-vm\\Projects\\tools-word\\result.docx'
  \$pdf  = '\\\\wsl.localhost\\Ubuntu\\home\\dev\\dev-vm\\Projects\\tools-word\\result.pdf'
  \$w = New-Object -ComObject Word.Application
  \$w.Visible = \$false
  \$d = \$w.Documents.Open(\$docx)
  \$d.SaveAs([ref]\$pdf, [ref]17)
  \$d.Close(\$false)
  \$w.Quit()
  Write-Host 'Saved:' \$pdf
"

# Step 3 – open the PDF in the Windows default viewer
explorer.exe "$(wslpath -w /home/dev/dev-vm/Projects/tools-word/result.pdf)"
```

`SaveAs` format `17` = `wdFormatPDF`. Microsoft Word must be installed on the
Windows host (it always is on this machine).

> **Why Word and not LibreOffice?**  
> Word gives pixel-perfect rendering of Hebrew BiDi, OMML equations, and font
> fallback — exactly what the user will see when they open the docx.
> LibreOffice renders these features differently and is not a reliable proxy.

---

## 3. Inspecting the Raw XML (for bug hunting)

Unzip the docx and parse `word/document.xml` to verify that BiDi/RTL
properties are actually present in the generated XML — do this before touching
the Python code to confirm the root cause:

```bash
mkdir -p /tmp/docx_inspect
cp /home/dev/dev-vm/Projects/tools-word/result.docx /tmp/docx_inspect/
cd /tmp/docx_inspect
unzip -o result.docx word/document.xml -d . > /dev/null

python3.8 - <<'EOF'
from lxml import etree

tree = etree.parse('word/document.xml')
root = tree.getroot()
ns   = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

for para in root.findall('.//w:p', ns):
    pPr    = para.find('w:pPr', ns)
    if pPr is None: continue
    pStyle = pPr.find('w:pStyle', ns)
    if pStyle is None: continue
    val    = pStyle.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '')
    if 'Heading' not in val: continue
    text   = ''.join(t.text or '' for t in para.findall('.//w:t', ns))
    bidi   = pPr.find('w:bidi', ns)
    jc     = pPr.find('w:jc', ns)
    bidiV  = bidi.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val','present') if bidi is not None else 'MISSING'
    jcV    = jc.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val','none')      if jc   is not None else 'MISSING'
    rtls   = para.findall('.//w:rtl', ns)
    print(f'[{val}] bidi={bidiV} jc={jcV} rtl_runs={len(rtls)} | {text[:70]}')
EOF
```

Expected for a Hebrew Heading 1:
```
[Heading1] bidi=1 jc=start rtl_runs=1 | אילוצים ארכיטקטוניים…
```

---

## 4. Known Issues Checklist

Before any PR / commit, verify these specific cases in the PDF:

| # | Input pattern | Expected result |
|---|--------------|-----------------|
| 1 | `# עברית` (Hebrew H1) | Right-aligned, not centred |
| 2 | `(1) **נעילה** text` | `(1)` and `**...**` brackets NOT mirrored |
| 3 | `## English Heading` | Left-aligned, unchanged |
| 4 | Inline `$math$` in Hebrew line | Equation renders, paragraph stays RTL |
| 5 | `> blockquote` | Italic, left border, left-indented |
| 6 | Pipe table with `$math$` cells | Equation inside cell, bold header row |

---

## 5. Key Architecture Notes

Refer to `FORMATTING_GUIDE.md` for full details.  Quick reminders:

- `doc.add_heading()` creates a plain run with **no** BiDi properties.  
  For RTL headings the heading paragraph must be post-processed with
  `_set_rtl_para()` and every run must have `_set_rtl_run()` applied.
- `<w:jc w:val="right">` is **reversed** by `<w:bidi/>` (OOXML §17.3.1.17).  
  Always use `<w:jc w:val="start">` for RTL paragraphs.
- Leading neutral chars (`(`, `1`, `)`, spaces, `**`) before the first Hebrew
  character in `_split_rtl_ltr()` must flush as **LTR**, not be absorbed into
  the first RTL run.  Otherwise `()` brackets render mirrored in Word.
- Complex-script (Hebrew) glyphs come from the `w:cs` font slot, **not**
  `w:ascii`.  Always set `w:rFonts w:cs=` in RTL runs.

---

## 6. File Map

| File | Purpose |
|------|---------|
| `md2docx.py` | Main converter (Python library + CLI) |
| `sample_input.txt` | Canonical test input — covers all features |
| `result.docx` | Last generated output (not committed) |
| `result.pdf` | Last PDF preview (not committed) |
| `FORMATTING_GUIDE.md` | AI-assistant authoring guide + PDF conversion instructions |
| `README.md` | Project overview, usage, architecture |
| `requirements.txt` | Python dependencies |
