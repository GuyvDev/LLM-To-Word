#!/usr/bin/env python3
"""Self-validating launcher for the canonical md2docx compiler."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import BadZipFile, ZipFile


ENGINE = "md2docx-core"
ENGINE_CREATOR = "md2docx canonical compiler"
ENGINE_APPLICATION = "md2docx"
REPORT_SCHEMA = 3
VALIDATOR_VERSION = "0.3.2"
RUNTIME_MANIFEST = Path(__file__).resolve().parent.parent / "assets" / "runtime-manifest.json"
REQUIRED_PARTS = {
    "[Content_Types].xml",
    "_rels/.rels",
    "word/document.xml",
    "word/styles.xml",
    "word/numbering.xml",
    "word/_rels/document.xml.rels",
    "docProps/core.xml",
    "docProps/app.xml",
}
BIDI_CONTROLS = {
    chr(value)
    for value in [0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)]
}
LRI = "\u2066"
PDI = "\u2069"
COMPILER_OUTPUT_BIDI_CONTROLS = {LRI, PDI}
UNSAFE_OUTPUT_BIDI_CONTROLS = BIDI_CONTROLS - COMPILER_OUTPUT_BIDI_CONTROLS
RTL_RE = re.compile(r"[\u0590-\u08ff]")
LTR_RE = re.compile(r"[A-Za-z]")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+\S", re.MULTILINE)
LIST_ITEM_RE = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+\S", re.MULTILINE)
TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$",
    re.MULTILINE,
)
LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\([^) \n]+(?:\s+\"[^\"]*\")?\)")
INLINE_MATH_RE = re.compile(
    r"(?<![\\$])\$(?![\s$\d])(.+?)(?<![\s\\])\$(?!\$)"
)
SAME_LINE_BLOCK_MATH_RE = re.compile(r"(?<!\\)\$\$(?!\s*$).+?(?<!\\)\$\$")
SELF_TEST_MARKDOWN = """# בדיקת Skill One - Runtime Self-Test

עברית + English + 2026 + 18% + [brackets] → symbols.

- **Bold** and *italic* with `inline_code()`.

| פריט | Value |
|---|---:|
| Alpha | 94.7% |

$$
\\theta_{t+1}=\\theta_t-\\alpha\\nabla_\\theta L(\\theta_t)
$$

```bash
echo self-test
```
"""


def is_balanced_ascii_syntax_atom(value: str) -> bool:
    if (
        not value.isascii()
        or any(character.isspace() for character in value)
        or not any(character.isalnum() for character in value)
        or "[" not in value
    ):
        return False
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    nested = False
    for character in value:
        if character in "([{":
            stack.append(character)
            nested = nested or len(stack) > 1
        elif character in pairs:
            if not stack or stack.pop() != pairs[character]:
                return False
    return nested and not stack


def compiler_ltr_syntax_atom(node: ET.Element) -> str | None:
    word = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    tag = lambda name: f"{{{word}}}{name}"
    if node.tag != tag("bdo") or node.attrib.get(tag("val")) != "ltr":
        return None
    if any(descendant is not node for descendant in node.iter(tag("bdo"))):
        return None

    characters: list[str] = []
    children = list(node)
    if not children or any(child.tag != tag("r") for child in children):
        return None
    for run in children:
        run_children = list(run)
        if [child.tag for child in run_children] != [tag("rPr"), tag("t")]:
            return None
        properties, text_node = run_children
        rtl = properties.find(tag("rtl"))
        language = properties.find(tag("lang"))
        if (
            rtl is None
            or rtl.attrib.get(tag("val")) != "0"
            or language is None
            or language.attrib.get(tag("val")) != "en-US"
        ):
            return None
        value = text_node.text or ""
        if len(value) != 1 or not value.isascii():
            return None
        characters.append(value)

    value = "".join(characters)
    return value if is_balanced_ascii_syntax_atom(value) else None


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def core_candidates() -> list[Path]:
    script = Path(__file__).resolve()
    names = (
        ["md2docx-core.exe", "md2docx-core"]
        if os.name == "nt"
        else ["md2docx-core", "md2docx-core-linux-x64"]
    )
    return [script.parent.parent / "bin" / name for name in names]


def runtime_manifest() -> dict[str, object]:
    try:
        manifest = json.loads(RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read bundled runtime manifest: {error}") from error
    if (
        manifest.get("schema_version") != 1
        or manifest.get("engine") != ENGINE
        or not isinstance(manifest.get("binaries"), dict)
    ):
        raise RuntimeError("bundled runtime manifest is invalid")
    return manifest


def find_core() -> Path:
    manifest = runtime_manifest()
    binaries = manifest["binaries"]
    for candidate in core_candidates():
        if candidate.is_file():
            relative = candidate.relative_to(RUNTIME_MANIFEST.parent.parent).as_posix()
            expected = binaries.get(relative)
            actual = sha256_bytes(candidate.read_bytes())
            if not expected:
                raise RuntimeError(f"bundled core is not listed in runtime manifest: {relative}")
            if actual != expected:
                raise RuntimeError(
                    f"bundled core hash mismatch: {relative}; "
                    f"expected={expected}, actual={actual}"
                )
            if os.name != "nt" and not os.access(candidate, os.X_OK):
                candidate.chmod(candidate.stat().st_mode | 0o111)
            return candidate
    raise FileNotFoundError("bundled md2docx canonical compiler is missing")


def run_core(core: Path, markdown: Path, output: Path, source: str) -> None:
    subprocess.run(
        [str(core), str(markdown), str(output), source],
        check=True,
        capture_output=True,
        text=True,
    )


def markdown_features(markdown: str, source: str = "llm") -> dict[str, object]:
    lines = markdown.splitlines()
    extended = source.strip().lower() != "commonmark"
    fence_open: tuple[str, int] | None = None
    fenced_blocks = 0
    fence_errors: list[str] = []
    display_delimiters = 0
    structural_lines: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        match = re.match(r"(`{3,}|~{3,})", stripped)
        if match:
            marker = match.group(1)
            kind = marker[0]
            if fence_open is None:
                fence_open = (kind, len(marker))
                fenced_blocks += 1
            elif kind == fence_open[0] and len(marker) >= fence_open[1]:
                fence_open = None
            structural_lines.append("")
            continue
        if fence_open is not None:
            structural_lines.append("")
            continue
        structural_lines.append(line)
        if line.strip() == "$$":
            display_delimiters += 1
    if fence_open is not None:
        fence_errors.append("unclosed fenced code block")
    if extended and display_delimiters % 2:
        fence_errors.append("unclosed display-math block")

    logical_lines = [
        re.sub(r"^\s*(?:>\s*)+", "", line) if re.match(r"^\s*>", line) else line
        for line in structural_lines
    ]
    structural = "\n".join(logical_lines)
    inline_code = len(re.findall(r"(?<!`)`(?!`)[^`\n]+`", structural))
    semantic = re.sub(r"(?<!`)`(?!`)[^`\n]*`", "", structural)
    heading_levels = [len(match.group(1)) for match in HEADING_RE.finditer(structural)]
    setext_lines: set[int] = set()
    for index in range(1, len(logical_lines)):
        if not logical_lines[index - 1].strip():
            continue
        underline = logical_lines[index].strip()
        if re.fullmatch(r"=+", underline):
            heading_levels.append(1)
            setext_lines.add(index)
        elif re.fullmatch(r"-{3,}", underline):
            heading_levels.append(2)
            setext_lines.add(index)
    inline_math = len(INLINE_MATH_RE.findall(semantic))
    same_line_math = len(SAME_LINE_BLOCK_MATH_RE.findall(semantic))
    block_math = display_delimiters // 2
    return {
        "bytes": len(markdown.encode("utf-8")),
        "lines": len(lines),
        "headings": len(heading_levels),
        "heading_levels": heading_levels,
        "tables": len(TABLE_SEPARATOR_RE.findall(structural)) if extended else 0,
        "list_items": len(LIST_ITEM_RE.findall(structural)),
        "fenced_code_blocks": fenced_blocks,
        "math_expressions": (
            block_math + same_line_math + inline_math if extended else 0
        ),
        "block_math": block_math + same_line_math if extended else 0,
        "links": len(LINK_RE.findall(semantic)),
        "blockquotes": sum(
            1 for line in structural_lines if re.match(r"^\s*>", line)
        ),
        "thematic_breaks": sum(
            1
            for index, line in enumerate(logical_lines)
            if index not in setext_lines
            if re.match(r"^\s{0,3}(?:\*\s*){3,}$|^\s{0,3}(?:-\s*){3,}$|^\s{0,3}(?:_\s*){3,}$", line)
        ),
        "bold": (
            semantic.count("**") // 2
            + (0 if extended else semantic.count("__") // 2)
        ),
        "strikethrough": semantic.count("~~") // 2 if extended else 0,
        "inline_code": inline_code,
        "contains_rtl": bool(RTL_RE.search(markdown)),
        "contains_ltr": bool(LTR_RE.search(markdown)),
        "contains_em_dash": "—" in markdown,
        "bidi_controls": sum(markdown.count(control) for control in BIDI_CONTROLS),
        "syntax_errors": fence_errors,
    }


def preflight_markdown(path: Path, source: str = "llm") -> dict[str, object]:
    errors: list[str] = []
    try:
        payload = path.read_bytes()
        markdown = payload.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return {
            "valid": False,
            "errors": [f"cannot read UTF-8 Markdown: {error}"],
            "path": str(path),
        }
    if not markdown.lstrip("\ufeff").strip():
        errors.append("Markdown input is empty")
    if "\x00" in markdown:
        errors.append("Markdown input contains a NUL character")
    features = markdown_features(markdown, source)
    errors.extend(features["syntax_errors"])
    return {
        "valid": not errors,
        "errors": errors,
        "path": str(path),
        "sha256": sha256_bytes(payload),
        "features": features,
    }


def validate_docx(path: Path) -> dict[str, object]:
    errors: list[str] = []
    checks: dict[str, object] = {"engine": None, "engine_verified": False}
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            missing = sorted(REQUIRED_PARTS - names)
            if missing:
                errors.append("missing package parts: " + ", ".join(missing))
            corrupt = archive.testzip()
            if corrupt:
                errors.append(f"corrupt ZIP entry: {corrupt}")
            xml_parts = 0
            em_dash_parts: list[str] = []
            bidi_control_parts: list[str] = []
            bidi_isolate_parts: list[str] = []
            unsafe_bidi_control_parts: list[str] = []
            bidi_isolate_pairs = 0
            ltr_syntax_overrides = 0
            parsed: dict[str, ET.Element] = {}
            for name in sorted(names):
                if not name.endswith((".xml", ".rels")):
                    continue
                payload = archive.read(name)
                decoded = payload.decode("utf-8", errors="replace")
                try:
                    parsed[name] = ET.fromstring(payload)
                    xml_parts += 1
                except ET.ParseError as error:
                    errors.append(f"invalid XML {name}: {error}")
                if "—" in decoded:
                    em_dash_parts.append(name)
                if any(control in decoded for control in BIDI_CONTROLS):
                    bidi_control_parts.append(name)
                if any(control in decoded for control in UNSAFE_OUTPUT_BIDI_CONTROLS):
                    unsafe_bidi_control_parts.append(name)
                if LRI in decoded or PDI in decoded:
                    bidi_isolate_parts.append(name)
                    if name != "word/document.xml":
                        errors.append(
                            f"compiler-owned BiDi isolates found outside "
                            f"word/document.xml: {name}"
                        )
            if em_dash_parts:
                errors.append("em dash found in package parts: " + ", ".join(em_dash_parts))
            if unsafe_bidi_control_parts:
                errors.append(
                    "unsafe Unicode BiDi controls found in package parts: "
                    + ", ".join(unsafe_bidi_control_parts)
                )
            document_root = parsed.get("word/document.xml")
            if document_root is not None:
                word_text = _tag(
                    "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
                    "t",
                )
                for node in document_root.iter(word_text):
                    value = node.text or ""
                    isolate_depth = 0
                    isolate_pairs = 0
                    for character in value:
                        if character == LRI:
                            if isolate_depth:
                                errors.append(
                                    "nested compiler-owned LTR isolate in a Word text node"
                                )
                            isolate_depth += 1
                        elif character == PDI:
                            if isolate_depth == 0:
                                errors.append(
                                    "unmatched compiler-owned PDI in a Word text node"
                                )
                            else:
                                isolate_depth -= 1
                                isolate_pairs += 1
                    if isolate_depth:
                        errors.append(
                            "unclosed compiler-owned LTR isolate in a Word text node"
                        )
                    bidi_isolate_pairs += isolate_pairs

                document_payload = archive.read("word/document.xml").decode(
                    "utf-8", errors="replace"
                )
                if (
                    document_payload.count(LRI) != bidi_isolate_pairs
                    or document_payload.count(PDI) != bidi_isolate_pairs
                ):
                    errors.append(
                        "compiler-owned BiDi isolates must be balanced inside "
                        "individual Word text nodes"
                    )
                word_bdo = _tag(
                    "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
                    "bdo",
                )
                for override in document_root.iter(word_bdo):
                    if compiler_ltr_syntax_atom(override) is None:
                        errors.append(
                            "invalid compiler-owned native LTR syntax override"
                        )
                    else:
                        ltr_syntax_overrides += 1
            creator = None
            application = None
            core_root = parsed.get("docProps/core.xml")
            if core_root is not None:
                creator_node = core_root.find(
                    "{http://purl.org/dc/elements/1.1/}creator"
                )
                creator = creator_node.text if creator_node is not None else None
            app_root = parsed.get("docProps/app.xml")
            if app_root is not None:
                application_node = app_root.find(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}Application"
                )
                application = (
                    application_node.text if application_node is not None else None
                )
            engine_verified = (
                creator == ENGINE_CREATOR and application == ENGINE_APPLICATION
            )
            if not engine_verified:
                errors.append(
                    "DOCX engine provenance is not md2docx-core "
                    f"(creator={creator!r}, application={application!r})"
                )
            checks.update(
                {
                    "engine": ENGINE if engine_verified else None,
                    "engine_verified": engine_verified,
                    "engine_creator": creator,
                    "engine_application": application,
                    "required_parts": not missing,
                    "xml_parts": xml_parts,
                    "em_dash_parts": len(em_dash_parts),
                    "bidi_control_parts": len(bidi_control_parts),
                    "bidi_isolate_parts": len(bidi_isolate_parts),
                    "bidi_isolate_pairs": bidi_isolate_pairs,
                    "ltr_syntax_overrides": ltr_syntax_overrides,
                    "unsafe_bidi_control_parts": len(unsafe_bidi_control_parts),
                }
            )
    except (BadZipFile, OSError) as error:
        errors.append(f"cannot read DOCX: {error}")
    digest = sha256_bytes(path.read_bytes()) if path.is_file() else None
    return {
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "sha256": digest,
        "path": str(path),
    }


def document_xml(path: Path) -> str:
    with ZipFile(path) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _tag(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def extract_docx_text_and_semantics(path: Path) -> dict[str, object]:
    word = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    math = "http://schemas.openxmlformats.org/officeDocument/2006/math"
    errors: list[str] = []
    paragraphs: list[str] = []
    headings = 0
    empty_headings = 0
    rtl_paragraphs = 0
    mixed_paragraphs = 0
    tables = 0
    centered_table_cells = 0
    table_cells = 0
    equations = 0
    with ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        styles = ET.fromstring(archive.read("word/styles.xml"))

    for override in document.iter(_tag(word, "bdo")):
        if compiler_ltr_syntax_atom(override) is None:
            errors.append("DOCX contains an invalid native LTR syntax override")

    def without_bidi_controls(value: str) -> str:
        return "".join(
            character for character in value if character not in BIDI_CONTROLS
        )

    for paragraph in document.iter(_tag(word, "p")):
        pieces: list[str] = []
        for element in paragraph.iter():
            if element.tag in {_tag(word, "t"), _tag(math, "t")} and element.text:
                pieces.append(element.text)
            elif element.tag == _tag(word, "tab"):
                pieces.append("\t")
            elif element.tag == _tag(word, "br"):
                pieces.append("\n")
        text = without_bidi_controls("".join(pieces))
        paragraphs.append(text)
        properties = paragraph.find(_tag(word, "pPr"))
        style = (
            properties.find(_tag(word, "pStyle"))
            if properties is not None
            else None
        )
        if style is not None and style.attrib.get(_tag(word, "val"), "").startswith(
            "Heading"
        ):
            headings += 1
            if not text.strip():
                empty_headings += 1
                errors.append("DOCX contains an empty heading")
        bidi = (
            properties.find(_tag(word, "bidi"))
            if properties is not None
            else None
        )
        if bidi is not None:
            rtl_paragraphs += 1
        if RTL_RE.search(text) and LTR_RE.search(text):
            mixed_paragraphs += 1
        for run in paragraph.findall(f".//{_tag(word, 'r')}"):
            run_text = without_bidi_controls(
                "".join(
                    node.text or ""
                    for node in run.findall(f".//{_tag(word, 't')}")
                )
            )
            if not run_text:
                continue
            run_properties = run.find(_tag(word, "rPr"))
            rtl = (
                run_properties.find(_tag(word, "rtl"))
                if run_properties is not None
                else None
            )
            rtl_value = rtl.attrib.get(_tag(word, "val")) if rtl is not None else None
            if (
                RTL_RE.search(run_text)
                and (rtl is None or rtl_value in {"0", "false"})
            ):
                errors.append(f"Hebrew/Arabic run lacks RTL properties: {run_text!r}")
            if LTR_RE.search(run_text) and (
                rtl is None or rtl_value not in {"0", "false"}
            ):
                errors.append(f"Latin run lacks explicit LTR properties: {run_text!r}")

    for table in document.iter(_tag(word, "tbl")):
        tables += 1
        table_text = "".join(
            element.text or ""
            for element in table.iter()
            if element.tag == _tag(word, "t")
        )
        properties = table.find(_tag(word, "tblPr"))
        bidi_visual = (
            properties.find(_tag(word, "bidiVisual"))
            if properties is not None
            else None
        )
        if RTL_RE.search(table_text) and bidi_visual is None:
            errors.append("RTL table lacks w:bidiVisual")
        for cell in table.iter(_tag(word, "tc")):
            table_cells += 1
            cell_centered = True
            for paragraph in cell.findall(_tag(word, "p")):
                paragraph_properties = paragraph.find(_tag(word, "pPr"))
                justification = (
                    paragraph_properties.find(_tag(word, "jc"))
                    if paragraph_properties is not None
                    else None
                )
                if (
                    justification is None
                    or justification.attrib.get(_tag(word, "val")) != "center"
                ):
                    cell_centered = False
            if cell_centered:
                centered_table_cells += 1
            else:
                errors.append("table cell content is not centered")

    equations = sum(1 for _ in document.iter(_tag(math, "oMath")))
    for level in range(1, 7):
        matching_styles = [
            style
            for style in styles.iter(_tag(word, "style"))
            if style.attrib.get(_tag(word, "styleId")) == f"Heading{level}"
        ]
        if not matching_styles:
            errors.append(f"Heading{level} style is missing")
            continue
        if matching_styles[0].find(f".//{_tag(word, 'keepNext')}") is None:
            errors.append(f"Heading{level} style lacks keepNext")

    extracted = "\n".join(paragraphs)
    return {
        "valid": not errors,
        "errors": errors,
        "text": extracted,
        "text_sha256": sha256_bytes(extracted.encode("utf-8")),
        "text_preview": extracted[:2000],
        "stats": {
            "paragraphs": len(paragraphs),
            "headings": headings,
            "empty_headings": empty_headings,
            "rtl_paragraphs": rtl_paragraphs,
            "mixed_paragraphs": mixed_paragraphs,
            "tables": tables,
            "table_cells": table_cells,
            "centered_table_cells": centered_table_cells,
            "equations": equations,
            "characters": len(extracted),
        },
    }


def source_review_text(markdown: str) -> str:
    output: list[str] = []
    fence: tuple[str, int] | None = None
    display_math = False
    for line in markdown.splitlines():
        stripped = line.lstrip()
        marker_match = re.match(r"(`{3,}|~{3,})", stripped)
        if marker_match:
            marker = marker_match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            continue
        if fence is not None:
            output.append(line)
            continue
        if line.strip() == "$$":
            display_math = not display_math
            continue
        if display_math:
            continue
        output.append(line)
    text = "\n".join(output)
    text = SAME_LINE_BLOCK_MATH_RE.sub(" ", text)
    text = INLINE_MATH_RE.sub(" ", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*(?:>\s*)+", "", text, flags=re.MULTILINE)
    text = re.sub(
        r"^\s*(?:[-+*]|\d+[.)])\s+(?:\[[ xX]\]\s+)?",
        "",
        text,
        flags=re.MULTILINE,
    )
    text = TABLE_SEPARATOR_RE.sub(" ", text)
    text = re.sub(r"^\s{0,3}(?:\*\s*){3,}$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}(?:-\s*){3,}$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}(?:_\s*){3,}$", " ", text, flags=re.MULTILINE)
    # Inline Markdown markers are not visible text. Remove them without adding a
    # boundary so split runs such as H~2~O and 2^10^ compare as H2O and 210.
    text = re.sub(
        r"==|\+\+|\|\||~~|\*\*|__|(?<!~)~(?!~)|\^|(?<!\*)\*(?!\*)",
        "",
        text,
    )
    return html.unescape(text)


def review_tokens(text: str) -> Counter[str]:
    tokens = re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)
    return Counter(token for token in tokens if token)


def validate_text_fidelity(markdown_path: Path, semantic: dict[str, object]) -> dict[str, object]:
    markdown = markdown_path.read_text(encoding="utf-8")
    expected = review_tokens(source_review_text(markdown))
    actual = review_tokens(semantic["text"])
    missing = {
        token: count - actual[token]
        for token, count in expected.items()
        if actual[token] < count
    }
    expected_count = sum(expected.values())
    missing_count = sum(missing.values())
    coverage = 1.0 if expected_count == 0 else (expected_count - missing_count) / expected_count
    errors = []
    if missing:
        sample = ", ".join(
            f"{token}×{count}" for token, count in sorted(missing.items())[:20]
        )
        errors.append(
            f"extracted DOCX text is missing {missing_count} source tokens: {sample}"
        )
    return {
        "valid": not errors,
        "errors": errors,
        "expected_tokens": expected_count,
        "missing_tokens": missing_count,
        "token_coverage": coverage,
        "missing_sample": dict(list(sorted(missing.items()))[:100]),
        "extracted_text_sha256": semantic["text_sha256"],
        "extracted_text_preview": semantic["text_preview"],
        "stats": semantic["stats"],
    }


def validate_feature_coverage(
    markdown_report: dict[str, object], path: Path
) -> dict[str, object]:
    expected = markdown_report["features"]
    xml = document_xml(path)
    actual = {
        "headings": len(re.findall(r'<w:pStyle w:val="Heading[1-6]"/>', xml)),
        "tables": xml.count("<w:tbl>"),
        "list_items": xml.count("<w:numPr>"),
        "math_expressions": len(re.findall(r"<m:oMath(?:\s|>)", xml)),
        "rtl_paragraphs": xml.count("<w:bidi/>"),
        "rtl_runs": xml.count("<w:rtl/>"),
        "ltr_runs": xml.count('<w:rtl w:val="0"/>'),
        "rtl_tables": xml.count("<w:bidiVisual/>"),
        "code_fonts": xml.count("Courier New"),
        "links": xml.count("http://") + xml.count("https://"),
        "bold_runs": xml.count("<w:b/>"),
        "strike_runs": xml.count("<w:strike/>"),
    }
    errors: list[str] = []

    def require_equal(feature: str) -> None:
        if actual[feature] != expected[feature]:
            errors.append(
                f"{feature} coverage mismatch: input={expected[feature]}, "
                f"docx={actual[feature]}"
            )

    def require_at_least(feature: str) -> None:
        if actual[feature] < expected[feature]:
            errors.append(
                f"{feature} coverage incomplete: input={expected[feature]}, "
                f"docx={actual[feature]}"
            )

    require_equal("headings")
    require_equal("tables")
    require_at_least("list_items")
    require_at_least("math_expressions")
    if expected["fenced_code_blocks"] + expected["inline_code"] > 0 and not actual["code_fonts"]:
        errors.append("code formatting is missing from DOCX")
    if expected["links"] > 0 and actual["links"] < expected["links"]:
        errors.append("link targets are missing from DOCX")
    if expected["bold"] > 0 and not actual["bold_runs"]:
        errors.append("bold formatting is missing from DOCX")
    if expected["strikethrough"] > 0 and not actual["strike_runs"]:
        errors.append("strikethrough formatting is missing from DOCX")
    if expected["contains_rtl"]:
        if not actual["rtl_paragraphs"] or not actual["rtl_runs"]:
            errors.append("required RTL paragraph/run properties are missing")
        if expected["tables"] > 0 and not actual["rtl_tables"]:
            errors.append("required RTL table behavior is missing")
    if expected["contains_rtl"] and expected["contains_ltr"] and not actual["ltr_runs"]:
        errors.append("required explicit LTR run properties are missing")
    return {
        "valid": not errors,
        "errors": errors,
        "expected": expected,
        "actual": actual,
    }


def core_self_test(core: Path) -> dict[str, object]:
    core_hash = sha256_bytes(core.read_bytes())
    manifest_hash = sha256_bytes(RUNTIME_MANIFEST.read_bytes())
    errors: list[str] = []
    first_hash = None
    second_hash = None
    coverage: dict[str, object] | None = None
    semantic_review: dict[str, object] | None = None
    text_fidelity: dict[str, object] | None = None
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        markdown = base / "self-test.md"
        first = base / "first.docx"
        second = base / "second.docx"
        markdown.write_text(
            SELF_TEST_MARKDOWN.replace("\r\n", "\n"),
            encoding="utf-8",
            newline="\n",
        )
        try:
            run_core(core, markdown, first, "llm")
            run_core(core, markdown, second, "llm")
            first_hash = sha256_bytes(first.read_bytes())
            second_hash = sha256_bytes(second.read_bytes())
            package = validate_docx(first)
            if not package["valid"]:
                errors.extend(package["errors"])
            coverage = validate_feature_coverage(
                preflight_markdown(markdown, "llm"), first
            )
            if not coverage["valid"]:
                errors.extend(coverage["errors"])
            semantic_review = extract_docx_text_and_semantics(first)
            if not semantic_review["valid"]:
                errors.extend(semantic_review["errors"])
            text_fidelity = validate_text_fidelity(markdown, semantic_review)
            if not text_fidelity["valid"]:
                errors.extend(text_fidelity["errors"])
            if first.read_bytes() != second.read_bytes():
                errors.append("canonical compiler self-test is not deterministic")
        except (OSError, subprocess.SubprocessError, BadZipFile, KeyError) as error:
            errors.append(f"canonical compiler self-test failed: {error}")
    return {
        "valid": not errors,
        "errors": errors,
        "engine": ENGINE,
        "core_path": str(core),
        "core_sha256": core_hash,
        "runtime_manifest_sha256": manifest_hash,
        "runtime_manifest_verified": True,
        "deterministic": first_hash is not None and first_hash == second_hash,
        "first_sha256": first_hash,
        "second_sha256": second_hash,
        "feature_coverage": coverage,
        "ooxml_semantics": (
            None
            if semantic_review is None
            else {key: value for key, value in semantic_review.items() if key != "text"}
        ),
        "text_fidelity": text_fidelity,
    }


def deterministic_replay(
    core: Path, markdown_path: Path, output_path: Path, source: str
) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as directory:
        replay = Path(directory) / "replay.docx"
        run_core(core, markdown_path, replay, source)
        expected = replay.read_bytes()
    actual = output_path.read_bytes()
    return {
        "valid": actual == expected,
        "expected_sha256": sha256_bytes(expected),
        "actual_sha256": sha256_bytes(actual),
        "byte_identical": actual == expected,
    }


def base_report(command: str) -> dict[str, object]:
    return {
        "schema_version": REPORT_SCHEMA,
        "validator_version": VALIDATOR_VERSION,
        "command": command,
        "valid": False,
        "errors": [],
    }


def write_report(report: dict[str, object], report_path: Path | None) -> None:
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def verify_run(
    markdown_path: Path,
    output_path: Path,
    source: str,
    report_path: Path | None,
    expected_input_sha256: str | None = None,
    review_text_path: Path | None = None,
) -> dict[str, object]:
    report = base_report("verify-run")
    core = find_core()
    preflight = preflight_markdown(markdown_path, source)
    self_test = core_self_test(core)
    package = validate_docx(output_path)
    errors: list[str] = []
    errors.extend(preflight["errors"])
    errors.extend(self_test["errors"])
    errors.extend(package["errors"])
    if expected_input_sha256 and preflight.get("sha256") != expected_input_sha256.lower():
        errors.append(
            "input SHA-256 mismatch: "
            f"expected={expected_input_sha256.lower()}, actual={preflight.get('sha256')}"
        )
    coverage: dict[str, object] | None = None
    replay: dict[str, object] | None = None
    semantic_review: dict[str, object] | None = None
    text_fidelity: dict[str, object] | None = None
    if preflight["valid"] and package["valid"]:
        coverage = validate_feature_coverage(preflight, output_path)
        errors.extend(coverage["errors"])
        semantic_review = extract_docx_text_and_semantics(output_path)
        errors.extend(semantic_review["errors"])
        text_fidelity = validate_text_fidelity(markdown_path, semantic_review)
        errors.extend(text_fidelity["errors"])
        if review_text_path:
            review_text_path.parent.mkdir(parents=True, exist_ok=True)
            review_text_path.write_text(semantic_review["text"], encoding="utf-8")
        replay = deterministic_replay(core, markdown_path, output_path, source)
        if not replay["valid"]:
            errors.append("DOCX is not byte-identical to trusted deterministic replay")
    input_hash_verified = (
        expected_input_sha256 is None
        or preflight.get("sha256") == expected_input_sha256.lower()
    )
    checks = {
        "engine": package["checks"].get("engine"),
        "engine_verified": package["checks"].get("engine_verified", False),
        "runtime_manifest_verified": self_test["runtime_manifest_verified"],
        "markdown_preflight": preflight["valid"],
        "core_self_test": self_test["valid"],
        "feature_coverage": bool(coverage and coverage["valid"]),
        "ooxml_semantics": bool(semantic_review and semantic_review["valid"]),
        "text_fidelity": bool(text_fidelity and text_fidelity["valid"]),
        "deterministic_replay": bool(replay and replay["valid"]),
        "input_sha256_verified": input_hash_verified,
    }
    report.update(
        {
            "valid": not errors,
            "errors": errors,
            "source": source,
            "input_sha256": preflight.get("sha256"),
            "input_bytes": preflight.get("features", {}).get("bytes"),
            "output_sha256": package.get("sha256"),
            "checks": checks,
            "input": preflight,
            "output": package,
            "core_self_test": self_test,
            "feature_coverage": coverage,
            "ooxml_semantics": (
                None
                if semantic_review is None
                else {
                    key: value
                    for key, value in semantic_review.items()
                    if key != "text"
                }
            ),
            "text_fidelity": text_fidelity,
            "review_text_path": str(review_text_path) if review_text_path else None,
            "deterministic_replay": replay,
        }
    )
    write_report(report, report_path)
    return report


def build(
    markdown_path: Path,
    output_path: Path,
    source: str,
    report_path: Path | None,
    expected_input_sha256: str | None = None,
    review_text_path: Path | None = None,
) -> dict[str, object]:
    core = find_core()
    preflight = preflight_markdown(markdown_path, source)
    self_test = core_self_test(core)
    errors = [*preflight["errors"], *self_test["errors"]]
    if expected_input_sha256 and preflight.get("sha256") != expected_input_sha256.lower():
        errors.append(
            "input SHA-256 mismatch: "
            f"expected={expected_input_sha256.lower()}, actual={preflight.get('sha256')}"
        )
    if errors:
        report = base_report("build")
        report.update(
            {
                "errors": errors,
                "source": source,
                "input_sha256": preflight.get("sha256"),
                "input_bytes": preflight.get("features", {}).get("bytes"),
                "output_sha256": None,
                "checks": {
                    "engine": None,
                    "engine_verified": False,
                    "runtime_manifest_verified": self_test[
                        "runtime_manifest_verified"
                    ],
                    "markdown_preflight": preflight["valid"],
                    "core_self_test": self_test["valid"],
                    "feature_coverage": False,
                    "ooxml_semantics": False,
                    "text_fidelity": False,
                    "deterministic_replay": False,
                    "input_sha256_verified": (
                        expected_input_sha256 is None
                        or preflight.get("sha256") == expected_input_sha256.lower()
                    ),
                },
                "input": preflight,
                "core_self_test": self_test,
            }
        )
        output_path.unlink(missing_ok=True)
        write_report(report, report_path)
        return report

    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_core(core, markdown_path, output_path, source)
    report = verify_run(
        markdown_path,
        output_path,
        source,
        report_path=None,
        expected_input_sha256=expected_input_sha256,
        review_text_path=review_text_path,
    )
    report["command"] = "build"
    if not report["valid"]:
        output_path.unlink(missing_ok=True)
    write_report(report, report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser(
        "doctor", help="run deterministic compiler and feature self-tests"
    )
    doctor_parser.add_argument("--json", action="store_true")

    preflight_parser = subparsers.add_parser(
        "preflight", help="validate and inventory authored Markdown"
    )
    preflight_parser.add_argument("input", type=Path)
    preflight_parser.add_argument("--source", default="llm")
    preflight_parser.add_argument("--json", action="store_true")

    build_parser = subparsers.add_parser(
        "build", help="self-test, compile, validate, and deterministically replay"
    )
    build_parser.add_argument("input", type=Path)
    build_parser.add_argument("output", type=Path)
    build_parser.add_argument("--source", default="llm")
    build_parser.add_argument("--report", type=Path)
    build_parser.add_argument("--expected-input-sha256")
    build_parser.add_argument("--review-text", type=Path)

    verify_parser = subparsers.add_parser(
        "verify-run", help="independently replay and verify a DOCX against Markdown"
    )
    verify_parser.add_argument("input", type=Path)
    verify_parser.add_argument("document", type=Path)
    verify_parser.add_argument("--source", default="llm")
    verify_parser.add_argument("--report", type=Path)
    verify_parser.add_argument("--expected-input-sha256")
    verify_parser.add_argument("--review-text", type=Path)

    review_parser = subparsers.add_parser(
        "review",
        help="run verification, OOXML semantic review, and extracted-text fidelity",
    )
    review_parser.add_argument("input", type=Path)
    review_parser.add_argument("document", type=Path)
    review_parser.add_argument("--source", default="llm")
    review_parser.add_argument("--report", type=Path)
    review_parser.add_argument("--expected-input-sha256")
    review_parser.add_argument("--review-text", type=Path)

    validate_parser = subparsers.add_parser(
        "validate", help="validate a generated DOCX package"
    )
    validate_parser.add_argument("document", type=Path)
    validate_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "doctor":
            report = core_self_test(find_core())
        elif args.command == "preflight":
            report = preflight_markdown(args.input, args.source)
        elif args.command == "build":
            report = build(
                args.input,
                args.output,
                args.source,
                args.report,
                args.expected_input_sha256,
                args.review_text,
            )
        elif args.command in {"verify-run", "review"}:
            report = verify_run(
                args.input,
                args.document,
                args.source,
                args.report,
                args.expected_input_sha256,
                args.review_text,
            )
            if args.command == "review":
                report["command"] = "review"
                write_report(report, args.report)
        else:
            report = validate_docx(args.document)
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0 if report["valid"] else 1
    except Exception as error:
        print(
            json.dumps(
                {"valid": False, "errors": [str(error)]}, ensure_ascii=True
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
