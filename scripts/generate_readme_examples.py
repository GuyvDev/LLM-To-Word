#!/usr/bin/env python3
"""Generate README DOCX before/after examples through PDF page rasterization."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRAIN = (
    ROOT
    / "products"
    / "skill-one"
    / "skill-one"
    / "scripts"
    / "docx_brain.py"
)
VISUAL_GATE = BRAIN.with_name("visual_gate.py")
DEFAULT_OUTPUT = ROOT / "docs" / "images" / "examples"

EXAMPLES = {
    "mixed-bidi": """# דוח ביצועים רבעוני

ברבעון הראשון של 2026 החברה הגדילה את ההכנסות ב-18% לעומת Q4 2025.

המדד Customer Acquisition Cost (CAC) ירד מ-$42 ל-$31.

המעבר המרכזי: הרשמה → אימות → Dashboard; סטטוס: [פעיל] (Beta).

המסקנה: השילוב בין עברית, English, מספרים 12.5%, וסוגריים {A[0]} נשאר קריא.
""",
    "math-symbols": """# ניתוח אלגוריתם - Gradient Descent

המטרה היא למצוא את הפרמטרים האופטימליים של המודל.

פונקציית העלות מוגדרת כך:

$$
J(\\theta)=\\frac{1}{m}\\sum_{i=1}^{m}(h_\\theta(x_i)-y_i)^2
$$

בכל שלב מתבצע עדכון:

$$
\\theta := \\theta-\\alpha\\nabla J(\\theta)
$$

- אם $L < 0.01$ התהליך נעצר.
- עבור $\\alpha = 0.001$ האימון יציב יותר.
""",
    "rtl-table": """# השוואת פתרונות AI

הטבלה משלבת שמות באנגלית, נתונים מספריים ותיאור בעברית.

| פתרון | Accuracy | זמן אימון | סטטוס |
|---|---:|---:|---|
| Baseline | 88.2% | 8 דקות | תקין |
| Transformer | **94.7%** | 12 דקות | מומלץ |
| CNN-LSTM | 91.3% | 15 דקות | בבדיקה |

> כל התאים מיושרים למרכז וסדר העמודות נשמר נכון במסמך RTL.
""",
    "document-styles": """# סיכום פרויקט - Launch Plan

## מטרות מרכזיות

> החלטה: להשיק גרסת Beta לאחר השלמת בדיקות האיכות.

- **איכות:** להשלים בדיקות RTL, טבלאות ומשוואות.
- **ביצועים:** לשמור זמן המרה מתחת ל-2 שניות.
- **אחריות:** צוות Platform מטפל ב-`release_check()`.

## פקודת אימות

```bash
python scripts/check_repository.py
```

הבדיקה הסתיימה בהצלחה וכל שלבי הפרסום מוכנים.
""",
}


def locate_soffice() -> Path:
    discovered = shutil.which("soffice") or shutil.which("libreoffice")
    candidates = [
        Path(discovered) if discovered else None,
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise SystemExit("LibreOffice soffice was not found")


def locate_pdftoppm() -> Path:
    discovered = shutil.which("pdftoppm")
    candidates = [
        Path(discovered) if discovered else None,
        Path.home()
        / "AppData"
        / "Local"
        / "Programs"
        / "MiKTeX"
        / "miktex"
        / "bin"
        / "x64"
        / "pdftoppm.exe",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise RuntimeError(
        "pdftoppm is required for faithful PDF rasterization; "
        "LibreOffice PDF import must not be used for BiDi review images"
    )


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def convert_document(
    soffice: Path,
    source: Path,
    output_dir: Path,
    profile: Path,
    output_format: str,
) -> Path:
    profile_uri = profile.resolve().as_uri()
    run(
        [
            str(soffice),
            "--headless",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            output_format,
            "--outdir",
            str(output_dir),
            str(source),
        ]
    )
    extension = output_format.split(":", maxsplit=1)[0]
    converted = output_dir / f"{source.stem}.{extension}"
    if not converted.is_file():
        raise RuntimeError(f"LibreOffice did not create {converted}")
    return converted


def convert_to_pdf(soffice: Path, source: Path, output_dir: Path, profile: Path) -> Path:
    return convert_document(soffice, source, output_dir, profile, "pdf")


def convert_docx_to_pdf_with_word(source: Path, output_dir: Path) -> Path:
    powershell = shutil.which("powershell") or shutil.which("powershell.exe")
    if os.name != "nt" or not powershell:
        raise RuntimeError("Microsoft Word PDF export requires Windows PowerShell")
    pdf = output_dir / f"{source.stem}.pdf"
    source_literal = str(source.resolve()).replace("'", "''")
    pdf_literal = str(pdf.resolve()).replace("'", "''")
    script = (
        "$ErrorActionPreference='Stop';"
        "$word=New-Object -ComObject Word.Application;"
        "$word.Visible=$false;$word.DisplayAlerts=0;$doc=$null;"
        "try {"
        f"$doc=$word.Documents.Open('{source_literal}',$false,$true);"
        f"$doc.ExportAsFixedFormat('{pdf_literal}',17);"
        "} finally {"
        "if ($null -ne $doc) {$doc.Close(0)};"
        "$word.Quit()"
        "}"
    )
    run([powershell, "-NoProfile", "-NonInteractive", "-Command", script])
    if not pdf.is_file():
        raise RuntimeError(f"Microsoft Word did not create {pdf}")
    return pdf


def render_docx_to_pdf(
    renderer: str,
    soffice: Path,
    source: Path,
    output_dir: Path,
    profile: Path,
) -> tuple[Path, str]:
    if renderer in {"auto", "word"}:
        try:
            return convert_docx_to_pdf_with_word(source, output_dir), "microsoft-word"
        except (OSError, RuntimeError, subprocess.CalledProcessError):
            if renderer == "word":
                raise
    return convert_to_pdf(soffice, source, output_dir, profile), "libreoffice"


def split_pdf_pages(pdf: Path, output_dir: Path, expected_pages: int) -> list[Path]:
    discovered = shutil.which("pdfseparate")
    candidates = [
        Path(discovered) if discovered else None,
        Path.home()
        / "AppData"
        / "Local"
        / "Programs"
        / "MiKTeX"
        / "miktex"
        / "bin"
        / "x64"
        / "pdfseparate.exe",
    ]
    executable = next(
        (candidate for candidate in candidates if candidate and candidate.is_file()),
        None,
    )
    if executable is None:
        raise RuntimeError(
            "pdfseparate is required with --baseline-docx; install Poppler or MiKTeX"
        )
    pattern = output_dir / "baseline-page-%d.pdf"
    run([str(executable), str(pdf), str(pattern)])
    pages = [output_dir / f"baseline-page-{page}.pdf" for page in range(1, expected_pages + 1)]
    if not all(page.is_file() for page in pages):
        raise RuntimeError(
            f"baseline DOCX must render to exactly {expected_pages} readable PDF pages"
        )
    extra = output_dir / f"baseline-page-{expected_pages + 1}.pdf"
    if extra.exists():
        raise RuntimeError(
            f"baseline DOCX has more than the expected {expected_pages} pages"
        )
    return pages


def rasterize(pdf: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    rasterizer = locate_pdftoppm()
    prefix = destination.with_suffix("")
    run(
        [
            str(rasterizer),
            "-f",
            "1",
            "-singlefile",
            "-png",
            "-r",
            "96",
            str(pdf),
            str(prefix),
        ]
    )
    produced = prefix.with_suffix(".png")
    if produced != destination and produced.is_file():
        produced.replace(destination)
    if not destination.is_file():
        raise RuntimeError(f"PDF rasterization did not create {destination}")


def crop_to_content(
    path: Path, padding: int = 30, publication_width: int = 1200
) -> None:
    try:
        from PIL import Image, ImageChops
    except ImportError as error:
        raise RuntimeError(
            "Pillow is required to crop README images; "
            "install requirements-dev.txt"
        ) from error

    with Image.open(path) as source:
        image = source.convert("RGB")
        background = Image.new("RGB", image.size, image.getpixel((0, 0)))
        difference = ImageChops.difference(image, background).convert("L")
        foreground = difference.point(lambda value: 255 if value > 8 else 0)
        bounds = foreground.getbbox()
        if bounds is None:
            raise RuntimeError(f"cannot find rendered content in {path}")
        content = image.crop(bounds)
        content_width = publication_width - (padding * 2)
        content_height = round(content.height * content_width / content.width)
        if content.size != (content_width, content_height):
            content = content.resize(
                (content_width, content_height),
                Image.Resampling.LANCZOS,
            )
        published = Image.new(
            "RGB",
            (publication_width, content_height + (padding * 2)),
            image.getpixel((0, 0)),
        )
        published.paste(content, (padding, padding))
        published.save(path, "PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case", choices=tuple(EXAMPLES))
    parser.add_argument(
        "--baseline-docx",
        type=Path,
        help="actual GPT-generated DOCX whose four pages become the before images",
    )
    parser.add_argument(
        "--renderer",
        choices=("auto", "word", "libreoffice"),
        default="auto",
        help="DOCX-to-PDF renderer; auto prefers invisible Microsoft Word export",
    )
    parser.add_argument(
        "--approve-visual",
        action="store_true",
        help="write and validate visual receipts after every output page was inspected",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    soffice = locate_soffice()

    with tempfile.TemporaryDirectory(prefix="md2docx-readme-") as directory:
        work = Path(directory)
        reports: dict[str, dict[str, object]] = {}
        baseline_pages: list[Path] | None = None
        baseline_renderer = "preserved-existing-image"
        if args.baseline_docx:
            baseline_docx = args.baseline_docx.resolve()
            if not baseline_docx.is_file():
                raise RuntimeError(f"baseline DOCX was not found: {baseline_docx}")
            baseline_pdf, baseline_renderer = render_docx_to_pdf(
                args.renderer,
                soffice,
                baseline_docx,
                work,
                work / "lo-baseline-profile",
            )
            baseline_pages = split_pdf_pages(
                baseline_pdf, work, expected_pages=len(EXAMPLES)
            )
        for index, (name, markdown_text) in enumerate(EXAMPLES.items(), start=1):
            if args.case and name != args.case:
                continue
            case = work / name
            case.mkdir()
            markdown = case / f"{name}.md"
            docx = case / f"{name}-after.docx"
            report = case / "report.json"
            extracted = case / "extracted.txt"
            markdown.write_text(markdown_text, encoding="utf-8", newline="\n")
            run(
                [
                    "python",
                    str(BRAIN),
                    "build",
                    str(markdown),
                    str(docx),
                    "--source",
                    "llm",
                    "--report",
                    str(report),
                    "--review-text",
                    str(extracted),
                ]
            )
            machine_report = json.loads(report.read_text(encoding="utf-8"))
            if not machine_report.get("valid"):
                raise RuntimeError(f"Skill One rejected {name}: {machine_report}")

            after_pdf, after_renderer = render_docx_to_pdf(
                args.renderer,
                soffice,
                docx,
                case,
                case / "lo-after-profile",
            )
            before_image = output / f"{index:02d}-{name}-before.png"
            if baseline_pages is not None:
                before_full = case / "before-full.png"
                rasterize(
                    baseline_pages[index - 1],
                    before_full,
                )
                shutil.copy2(before_full, before_image)
            elif not before_image.is_file():
                raise RuntimeError(
                    f"{before_image} is missing; pass --baseline-docx with the "
                    "actual four-page GPT output"
                )
            crop_to_content(before_image)
            after_image = output / f"{index:02d}-{name}-after.png"
            after_full = case / "after-full.png"
            rasterize(
                after_pdf,
                after_full,
            )
            shutil.copy2(after_full, after_image)
            crop_to_content(after_image)
            visual_gate_valid = False
            if args.approve_visual:
                visual_pages = case / "rendered-pages"
                visual_pages.mkdir()
                shutil.copy2(after_full, visual_pages / "page-1.png")
                visual_report = case / "visual-report.json"
                visual_report.write_text(
                    json.dumps(
                        {
                            "visual_valid": True,
                            "docx_sha256": sha256_file(docx),
                            "pdf_sha256": sha256_file(after_pdf),
                            "pages_expected": 1,
                            "pages_rendered": 1,
                            "pages_reviewed": 1,
                            "reviewed_pages": [1],
                            "issues": [],
                            "rebuild_count": 0,
                        }
                    ),
                    encoding="utf-8",
                )
                run(
                    [
                        "python",
                        str(VISUAL_GATE),
                        "--docx",
                        str(docx),
                        "--pdf",
                        str(after_pdf),
                        "--pages-dir",
                        str(visual_pages),
                        "--report",
                        str(visual_report),
                    ]
                )
                visual_gate_valid = True
            reports[name] = {
                "machine_valid": True,
                "visual_gate_valid": visual_gate_valid,
                "before_pdf_renderer": baseline_renderer,
                "after_pdf_renderer": after_renderer,
                "input_sha256": machine_report["input_sha256"],
                "output_sha256": machine_report["output_sha256"],
            }

    print(json.dumps({"valid": True, "output": str(output), "cases": reports}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
