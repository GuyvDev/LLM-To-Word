#!/usr/bin/env python3
"""Skill One: dependency-free DocSpec 1.0 to validated DOCX compiler."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZIP_STORED, ZipFile, ZipInfo

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC = "http://purl.org/dc/elements/1.1/"
DCTERMS = "http://purl.org/dc/terms/"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
REQUIRED_PARTS = {
    "[Content_Types].xml",
    "_rels/.rels",
    "word/document.xml",
    "word/styles.xml",
    "word/numbering.xml",
    "word/settings.xml",
    "word/_rels/document.xml.rels",
    "docProps/core.xml",
    "docProps/app.xml",
}
OPENING = set("([{<\"'“‘«‹（［｛【「『〈《$€£¥₪₹₩")
RTL_RANGE = re.compile(r"[\u0590-\u08ff]")
ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

SYMBOLS = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "theta": "θ",
    "lambda": "λ", "mu": "μ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "phi": "φ",
    "chi": "χ", "psi": "ψ", "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ",
    "Lambda": "Λ", "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
    "pm": "±", "mp": "∓", "times": "×", "cdot": "·", "div": "÷", "le": "≤", "leq": "≤",
    "ge": "≥", "geq": "≥", "neq": "≠", "approx": "≈", "infty": "∞", "partial": "∂",
    "nabla": "∇", "sum": "∑", "prod": "∏", "int": "∫", "oint": "∮", "to": "→",
    "rightarrow": "→", "leftarrow": "←", "leftrightarrow": "↔", "in": "∈", "notin": "∉",
    "subset": "⊂", "supset": "⊃", "subseteq": "⊆", "supseteq": "⊇", "cup": "∪", "cap": "∩",
    "forall": "∀", "exists": "∃", "neg": "¬", "land": "∧", "lor": "∨", "ldots": "…",
    "cdots": "⋯", "degree": "°", "quad": "  ", "qquad": "    ",
}
FUNCTIONS = {"sin", "cos", "tan", "log", "ln", "lim", "max", "min", "det"}
STRUCTURAL_COMMANDS = {
    "frac", "dfrac", "tfrac", "sqrt", "text", "mathrm", "operatorname",
    "left", "right", "displaystyle", "begin", "end",
}


class SpecError(ValueError):
    pass


def clean(value: Any) -> str:
    text = str(value if value is not None else "").replace("\u2014", "-")
    return ILLEGAL_XML.sub("", text)


def xe(value: Any) -> str:
    return escape(clean(value), {'"': "&quot;", "'": "&apos;"})


def contains_rtl(value: str) -> bool:
    return bool(RTL_RANGE.search(value))


def strong_direction(character: str) -> bool | None:
    if contains_rtl(character):
        return True
    bidi = unicodedata.bidirectional(character)
    if bidi == "L":
        return False
    # Keep numbers neutral so Word's native BiDi engine places them within the
    # surrounding paragraph direction. Treating EN/AN as independent LTR runs
    # reverses adjacent punctuation in headings such as "דוגמה 4 - ...".
    return None


def split_directional(value: str) -> list[tuple[str, bool]]:
    result: list[tuple[str, bool]] = []
    buffer = ""
    neutrals = ""
    direction: bool | None = None
    for character in clean(value):
        next_direction = strong_direction(character)
        if next_direction is None:
            neutrals += character
            continue
        if direction is None:
            buffer += neutrals
            neutrals = ""
            direction = next_direction
        elif direction == next_direction:
            buffer += neutrals
            neutrals = ""
        else:
            pivot = next((index for index, item in enumerate(neutrals) if item in OPENING), len(neutrals))
            buffer += neutrals[:pivot].replace(" ", "\u00a0")
            if buffer:
                result.append((buffer, direction))
            buffer = neutrals[pivot:]
            neutrals = ""
            direction = next_direction
        buffer += character
    buffer += neutrals
    if buffer:
        result.append((buffer, bool(direction)))
    return result


def edge_directions(value: str) -> tuple[bool | None, bool | None]:
    directions = [direction for character in clean(value) if (direction := strong_direction(character)) is not None]
    return (directions[0], directions[-1]) if directions else (None, None)


def stabilize_inline_boundaries(content: Any) -> Any:
    """Use NBSP where separately styled RTL/LTR runs meet in Word."""
    if not isinstance(content, list):
        return content
    result: list[Any] = []
    for item in content:
        copied = dict(item) if isinstance(item, dict) else item
        result.append(copied)

    def value_of(item: Any) -> str | None:
        if isinstance(item, str):
            return item
        if isinstance(item, dict) and "text" in item:
            return str(item["text"])
        if isinstance(item, dict) and item.get("type") == "link":
            return str(item.get("text", item.get("url", "")))
        return None

    for current_index in range(1, len(result)):
        previous_index = current_index - 1
        previous = result[previous_index]
        current = result[current_index]
        previous_value = value_of(previous)
        current_value = value_of(current)
        if previous_value is None or current_value is None:
            continue
        _, previous_last = edge_directions(previous_value)
        current_first, _ = edge_directions(current_value)
        if previous_last is None or current_first is None or previous_last == current_first:
            continue
        if previous_value.endswith(" "):
            previous_value = re.sub(r" +$", lambda match: "\u00a0" * len(match.group(0)), previous_value)
        elif current_value.startswith(" "):
            current_value = re.sub(r"^ +", lambda match: "\u00a0" * len(match.group(0)), current_value)
        if isinstance(previous, str):
            result[previous_index] = previous_value
        else:
            previous["text"] = previous_value
        if isinstance(current, str):
            result[current_index] = current_value
        else:
            current["text"] = current_value
    return result


@dataclass(frozen=True)
class Token:
    kind: str
    value: str = ""


def tokenize_latex(source: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    while index < len(source):
        character = source[index]
        if character.isspace():
            index += 1
            continue
        if character == "\\":
            if source[index:index + 2] == "\\\\":
                tokens.append(Token("row")); index += 2; continue
            match = re.match(r"[A-Za-z]+", source[index + 1:])
            if match:
                tokens.append(Token("command", match.group(0))); index += len(match.group(0)) + 1; continue
            if index + 1 < len(source):
                tokens.append(Token("char", source[index + 1])); index += 2; continue
        kind = {"{": "open", "}": "close", "^": "sup", "_": "sub", "&": "cell"}.get(character, "char")
        tokens.append(Token(kind, character))
        index += 1
    return tokens


class MathParser:
    def __init__(self, source: str):
        self.tokens = tokenize_latex(source)
        self.position = 0

    def group(self) -> str:
        if self.peek("open"):
            self.position += 1
            value = self.sequence("close")
            if self.peek("close"):
                self.position += 1
            return value
        return self.scripted_atom()

    def peek(self, kind: str) -> bool:
        return self.position < len(self.tokens) and self.tokens[self.position].kind == kind

    def atom(self) -> str:
        if self.position >= len(self.tokens):
            return ""
        token = self.tokens[self.position]
        self.position += 1
        if token.kind == "open":
            value = self.sequence("close")
            if self.peek("close"):
                self.position += 1
            return value
        if token.kind == "command":
            if token.value in {"frac", "dfrac", "tfrac"}:
                return f"<m:f><m:num>{self.group()}</m:num><m:den>{self.group()}</m:den></m:f>"
            if token.value == "sqrt":
                return f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>{self.group()}</m:e></m:rad>'
            if token.value in {"text", "mathrm", "operatorname"}:
                return self.group()
            if token.value in {"left", "right", "displaystyle"}:
                return ""
            value = SYMBOLS.get(token.value, token.value if token.value in FUNCTIONS else f"\\{token.value}")
            return math_run(value)
        if token.kind == "char":
            return math_run(token.value)
        return ""

    def scripted_atom(self) -> str:
        base = self.atom()
        subscript = ""
        superscript = ""
        while self.position < len(self.tokens) and self.tokens[self.position].kind in {"sub", "sup"}:
            kind = self.tokens[self.position].kind
            self.position += 1
            if kind == "sub":
                subscript = self.group()
            else:
                superscript = self.group()
        if subscript and superscript:
            return f"<m:sSubSup><m:e>{base}</m:e><m:sub>{subscript}</m:sub><m:sup>{superscript}</m:sup></m:sSubSup>"
        if subscript:
            return f"<m:sSub><m:e>{base}</m:e><m:sub>{subscript}</m:sub></m:sSub>"
        if superscript:
            return f"<m:sSup><m:e>{base}</m:e><m:sup>{superscript}</m:sup></m:sSup>"
        return base

    def sequence(self, until: str | None = None) -> str:
        result = ""
        while self.position < len(self.tokens):
            kind = self.tokens[self.position].kind
            if kind == until or kind in {"close", "cell", "row"}:
                break
            result += self.scripted_atom()
        return result


def math_run(value: str) -> str:
    return f"<m:r><m:t>{xe(value)}</m:t></m:r>"


def latex_to_omml(source: str, display: bool = False) -> str:
    source = source.strip()
    if not source:
        raise SpecError("equation latex must not be empty")
    if source.count("{") != source.count("}"):
        raise SpecError("equation latex has unbalanced braces")
    commands = set(re.findall(r"\\([A-Za-z]+)", source))
    unknown = sorted(commands - set(SYMBOLS) - FUNCTIONS - STRUCTURAL_COMMANDS)
    if unknown:
        raise SpecError("unsupported LaTeX command(s): " + ", ".join(f"\\{command}" for command in unknown))
    matrix_match = re.fullmatch(r"\\begin\{(bmatrix|pmatrix|matrix)\}(.*?)\\end\{\1\}", source, re.S)
    if matrix_match:
        environment, body = matrix_match.groups()
        rows = ""
        for row in re.split(r"\\\\", body):
            cells = "".join(f"<m:e>{MathParser(cell.strip()).sequence()}</m:e>" for cell in row.split("&"))
            rows += f"<m:mr>{cells}</m:mr>"
        matrix = f"<m:m>{rows}</m:m>"
        delimiters = {"bmatrix": ("[", "]"), "pmatrix": ("(", ")")}
        if environment in delimiters:
            begin, end = delimiters[environment]
            inner = f'<m:d><m:dPr><m:begChr m:val="{begin}"/><m:endChr m:val="{end}"/></m:dPr><m:e>{matrix}</m:e></m:d>'
        else:
            inner = matrix
    else:
        inner = MathParser(source).sequence()
    if display:
        return f'<m:oMathPara><m:oMathParaPr><m:jc m:val="centerGroup"/></m:oMathParaPr><m:oMath>{inner}</m:oMath></m:oMathPara>'
    return f"<m:oMath>{inner}</m:oMath>"


def plain_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise SpecError("content must be a string or array")
    result = ""
    for item in content:
        if isinstance(item, str):
            result += item
        elif isinstance(item, dict):
            if "text" in item:
                result += str(item["text"])
            elif item.get("type") == "link":
                result += str(item.get("text", ""))
            elif item.get("type") == "break":
                result += "\n"
    return result


def validate_spec(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise SpecError("DocSpec root must be an object")
    if spec.get("version") != "1.0":
        raise SpecError("DocSpec version must be '1.0'")
    blocks = spec.get("blocks")
    if not isinstance(blocks, list):
        raise SpecError("DocSpec blocks must be an array")
    allowed = {"heading", "paragraph", "quote", "equation", "code", "list", "table", "horizontal_rule", "page_break"}
    counts: dict[str, int] = {}
    for index, block in enumerate(blocks):
        if not isinstance(block, dict) or block.get("type") not in allowed:
            raise SpecError(f"block {index} has unsupported type")
        kind = block["type"]
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "heading" and not 1 <= int(block.get("level", 0)) <= 6:
            raise SpecError(f"block {index} heading level must be 1..6")
        if kind == "equation" and not str(block.get("latex", "")).strip():
            raise SpecError(f"block {index} equation requires latex")
        if kind == "table":
            headers = block.get("headers", [])
            rows = block.get("rows", [])
            if not isinstance(headers, list) or not isinstance(rows, list):
                raise SpecError(f"block {index} table headers/rows must be arrays")
            columns = len(headers) or (len(rows[0]) if rows else 0)
            if columns == 0 or any(not isinstance(row, list) or len(row) != columns for row in rows):
                raise SpecError(f"block {index} table rows must have {columns} columns")
    return {"blocks": len(blocks), "counts": counts}


class Compiler:
    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.body: list[str] = []
        self.hyperlinks: list[tuple[str, str]] = []
        self.number_instances: list[tuple[int, bool]] = []

    def text_runs(self, text: str, style: dict[str, Any] | None = None) -> str:
        style = style or {}
        result = ""
        for part, rtl in split_directional(text):
            properties = ""
            for key, xml_value in [
                ("bold", "<w:b/>"), ("italic", "<w:i/>"), ("strike", "<w:strike/>"),
                ("underline", '<w:u w:val="single"/>'), ("superscript", '<w:vertAlign w:val="superscript"/>'),
                ("subscript", '<w:vertAlign w:val="subscript"/>'), ("highlight", '<w:highlight w:val="yellow"/>'),
            ]:
                if style.get(key):
                    properties += xml_value
            if style.get("code"):
                properties += '<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/><w:sz w:val="20"/>'
            if style.get("color"):
                properties += f'<w:color w:val="{xe(style["color"]).lstrip("#")}"/>'
            if rtl:
                properties += '<w:rFonts w:cs="Arial"/><w:rtl/><w:lang w:bidi="he-IL"/>'
            else:
                properties += '<w:rtl w:val="0"/><w:lang w:val="en-US"/>'
            result += f'<w:r>{f"<w:rPr>{properties}</w:rPr>" if properties else ""}<w:t xml:space="preserve">{xe(part)}</w:t></w:r>'
        return result

    def inlines(self, content: Any, inherited: dict[str, Any] | None = None) -> str:
        inherited = inherited or {}
        if isinstance(content, str):
            return self.text_runs(content, inherited)
        if not isinstance(content, list):
            raise SpecError("inline content must be string or array")
        content = stabilize_inline_boundaries(content)
        result = ""
        for item in content:
            if isinstance(item, str):
                result += self.text_runs(item, inherited)
                continue
            if not isinstance(item, dict):
                raise SpecError("inline item must be string or object")
            if "text" in item:
                style = {**inherited, **item}
                result += self.text_runs(str(item["text"]), style)
            elif item.get("type") == "equation":
                result += latex_to_omml(str(item.get("latex", "")))
            elif item.get("type") == "break":
                result += "<w:r><w:br/></w:r>"
            elif item.get("type") == "link":
                url = str(item.get("url", ""))
                if not re.match(r"https?://", url):
                    raise SpecError("links must use http or https")
                relationship = f"rId{10 + len(self.hyperlinks)}"
                self.hyperlinks.append((relationship, url))
                style = {**inherited, "underline": True, "color": "0563C1"}
                result += f'<w:hyperlink r:id="{relationship}">{self.text_runs(str(item.get("text", url)), style)}</w:hyperlink>'
            else:
                raise SpecError(f"unsupported inline type {item.get('type')!r}")
        return result

    def paragraph(self, content: Any, *, style: str | None = None, direction: str = "auto", center: bool = False,
                  quote: bool = False, list_id: int | None = None) -> str:
        plain = plain_content(content)
        rtl = contains_rtl(plain) if direction == "auto" else direction == "rtl"
        properties = f'<w:pStyle w:val="{style}"/>' if style else ""
        if rtl:
            properties += "<w:bidi/><w:jc w:val=\"start\"/>"
        if center:
            properties += '<w:jc w:val="center"/>'
        if quote:
            side = "right" if rtl else "left"
            properties += f'<w:ind w:{side}="360"/><w:shd w:val="clear" w:fill="F8FAFC"/><w:pBdr><w:{side} w:val="single" w:sz="14" w:space="5" w:color="5B7FA3"/></w:pBdr>'
        if list_id:
            properties += f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{list_id}"/></w:numPr>'
        return f'<w:p>{f"<w:pPr>{properties}</w:pPr>" if properties else ""}{self.inlines(content)}</w:p>'

    def table(self, block: dict[str, Any]) -> str:
        headers = block.get("headers", [])
        rows = block.get("rows", [])
        all_cells = headers + [cell for row in rows for cell in row]
        direction = block.get("direction", "auto")
        rtl = any(contains_rtl(plain_content(cell)) for cell in all_cells) if direction == "auto" else direction == "rtl"
        columns = len(headers) or len(rows[0])
        rendered_rows = ""
        source_rows = ([headers] if headers else []) + rows
        for row_index, row in enumerate(source_rows):
            cells = ""
            is_header = bool(headers) and row_index == 0
            for cell in row:
                shade = '<w:shd w:val="clear" w:fill="D9EAF7"/>' if is_header else ('<w:shd w:val="clear" w:fill="F8FAFC"/>' if row_index % 2 == 0 else "")
                content = self.inlines(cell, {"bold": True} if is_header else {})
                plain = plain_content(cell)
                paragraph = self.paragraph_xml(content, plain, contains_rtl(plain), center=True, compact=True)
                cells += f'<w:tc><w:tcPr><w:tcW w:w="2400" w:type="dxa"/><w:vAlign w:val="center"/>{shade}</w:tcPr>{paragraph}</w:tc>'
            rendered_rows += f"<w:tr>{cells}</w:tr>"
        grid = "".join('<w:gridCol w:w="2400"/>' for _ in range(columns))
        bidi = "<w:bidiVisual/>" if rtl else ""
        borders = ''.join(f'<w:{side} w:val="single" w:sz="{6 if side in {"top", "left", "bottom", "right"} else 4}" w:color="{ "B7C9DB" if side in {"top", "left", "bottom", "right"} else "D9E2EC"}"/>' for side in ["top", "left", "bottom", "right", "insideH", "insideV"])
        return f'<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/><w:jc w:val="center"/>{bidi}<w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="100" w:type="dxa"/><w:bottom w:w="80" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar><w:tblBorders>{borders}</w:tblBorders></w:tblPr><w:tblGrid>{grid}</w:tblGrid>{rendered_rows}</w:tbl>'

    @staticmethod
    def paragraph_xml(content_xml: str, plain: str, rtl: bool, *, center: bool = False, compact: bool = False) -> str:
        properties = "<w:bidi/>" if rtl else ""
        if center:
            properties += '<w:jc w:val="center"/>'
        if compact:
            properties += '<w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
        return f'<w:p><w:pPr>{properties}</w:pPr>{content_xml}</w:p>'

    def render(self) -> None:
        for block in self.spec["blocks"]:
            kind = block["type"]
            direction = block.get("direction", "auto")
            if kind == "heading":
                self.body.append(self.paragraph(block.get("content", ""), style=f'Heading{int(block["level"])}', direction=direction))
            elif kind == "paragraph":
                self.body.append(self.paragraph(block.get("content", ""), direction=direction))
            elif kind == "quote":
                self.body.append(self.paragraph(block.get("content", ""), direction=direction, quote=True))
            elif kind == "equation":
                self.body.append(f'<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="60" w:after="60"/></w:pPr>{latex_to_omml(str(block["latex"]), True)}</w:p>')
            elif kind == "code":
                language = str(block.get("language", ""))
                text = str(block.get("text", ""))
                content = self.text_runs(language, {"bold": True, "code": True}) if language else ""
                if language and text:
                    content += "<w:r><w:br/></w:r>"
                for index, line in enumerate(text.splitlines() or [""]):
                    if index:
                        content += "<w:r><w:br/></w:r>"
                    content += self.text_runs(line, {"code": True})
                self.body.append(f'<w:p><w:pPr><w:ind w:left="360"/><w:shd w:val="clear" w:fill="F3F4F6"/><w:pBdr><w:left w:val="single" w:sz="8" w:color="94A3B8"/></w:pBdr></w:pPr>{content}</w:p>')
            elif kind == "list":
                list_id = len(self.number_instances) + 1
                self.number_instances.append((list_id, bool(block.get("ordered"))))
                for item in block.get("items", []):
                    self.body.append(self.paragraph(item, direction=direction, list_id=list_id))
            elif kind == "table":
                self.body.append(self.table(block))
            elif kind == "horizontal_rule":
                self.body.append('<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="D9E2F3"/></w:pBdr></w:pPr></w:p>')
            elif kind == "page_break":
                self.body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def document_xml(self) -> str:
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}" xmlns:m="{M}" xmlns:r="{R}"><w:body>{"".join(self.body)}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>'

    def relationships_xml(self) -> str:
        links = "".join(f'<Relationship Id="{relationship}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target={quoteattr(url)} TargetMode="External"/>' for relationship, url in self.hyperlinks)
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{PR}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>{links}</Relationships>'


def styles_xml() -> str:
    heading_data = [(1, 42, "17365D", 0, 100), (2, 32, "1F4E79", 180, 60), (3, 27, "334155", 140, 40), (4, 24, "334155", 120, 40), (5, 22, "475569", 100, 30), (6, 21, "475569", 80, 30)]
    headings = ""
    for level, size, color, before, after in heading_data:
        border = '<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="4" w:color="D9E2F3"/></w:pBdr>' if level == 1 else ""
        headings += f'<w:style w:type="paragraph" w:styleId="Heading{level}"><w:name w:val="heading {level}"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="{before}" w:after="{after}"/>{border}</w:pPr><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:b/><w:color w:val="{color}"/><w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr></w:style>'
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="23"/><w:szCs w:val="23"/><w:color w:val="1F2937"/><w:lang w:val="en-US" w:bidi="he-IL"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="276" w:lineRule="auto"/><w:widowControl/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>{headings}<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/></w:style></w:styles>'


def numbering_xml(instances: list[tuple[int, bool]] | None = None) -> str:
    instances = instances or []
    nums = "".join(
        f'<w:num w:numId="{number_id}"><w:abstractNumId w:val="{1 if ordered else 0}"/>'
        f'<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'
        for number_id, ordered in instances
    )
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering xmlns:w="{W}"><w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="multilevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="start"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum><w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="multilevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="start"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>{nums}</w:numbering>'


def settings_xml() -> str:
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings xmlns:w="{W}"><w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat><w:defaultTabStop w:val="720"/><w:characterSpacingControl w:val="doNotCompress"/></w:settings>'


def fixed_zip(files: dict[str, str]) -> bytes:
    from io import BytesIO
    output = BytesIO()
    with ZipFile(output, "w", ZIP_STORED) as archive:
        for name, content in files.items():
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_STORED
            info.external_attr = 0o600 << 16
            archive.writestr(info, content.encode("utf-8"))
    return output.getvalue()


def package(spec: dict[str, Any]) -> bytes:
    compiler = Compiler(spec)
    compiler.render()
    metadata = spec.get("metadata") or {}
    title = xe(metadata.get("title", "Skill One document"))
    author = xe(metadata.get("author", "Skill One"))
    files = {
        "[Content_Types].xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/><Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>',
        "_rels/.rels": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{PR}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>',
        "word/document.xml": compiler.document_xml(),
        "word/styles.xml": styles_xml(),
        "word/numbering.xml": numbering_xml(compiler.number_instances),
        "word/settings.xml": settings_xml(),
        "word/_rels/document.xml.rels": compiler.relationships_xml(),
        "docProps/core.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="{CP}" xmlns:dc="{DC}" xmlns:dcterms="{DCTERMS}" xmlns:xsi="{XSI}"><dc:title>{title}</dc:title><dc:creator>{author}</dc:creator><cp:lastModifiedBy>Skill One</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">2000-01-01T00:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2000-01-01T00:00:00Z</dcterms:modified></cp:coreProperties>',
        "docProps/app.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Skill One</Application><AppVersion>1.0</AppVersion></Properties>',
    }
    return fixed_zip(files)


def validate_docx(path: Path, spec: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    checks: dict[str, Any] = {}
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            missing = sorted(REQUIRED_PARTS - names)
            if missing:
                errors.append(f"missing package parts: {', '.join(missing)}")
            corrupt = archive.testzip()
            if corrupt:
                errors.append(f"corrupt ZIP entry: {corrupt}")
            parsed: dict[str, ET.Element] = {}
            em_dash_parts: list[str] = []
            for name in sorted(names):
                if name.endswith((".xml", ".rels")):
                    payload = archive.read(name)
                    if "\u2014".encode("utf-8") in payload:
                        em_dash_parts.append(name)
                    try:
                        parsed[name] = ET.fromstring(payload)
                    except ET.ParseError as error:
                        errors.append(f"invalid XML {name}: {error}")
            if em_dash_parts:
                errors.append("em dash found in package parts: " + ", ".join(em_dash_parts))
            checks["em_dash_parts"] = len(em_dash_parts)
            document = parsed.get("word/document.xml")
            numbering = parsed.get("word/numbering.xml")
            settings = parsed.get("word/settings.xml")
            content_types = parsed.get("[Content_Types].xml")
            root_relationships = parsed.get("_rels/.rels")
            document_relationships = parsed.get("word/_rels/document.xml.rels")
            if content_types is not None:
                overrides = {
                    node.attrib.get("PartName"): node.attrib.get("ContentType")
                    for node in content_types.findall(f"{{{CT}}}Override")
                }
                expected_overrides = {
                    "/word/document.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
                    "/word/styles.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml",
                    "/word/numbering.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml",
                    "/word/settings.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml",
                }
                for part, content_type in expected_overrides.items():
                    if overrides.get(part) != content_type:
                        errors.append(f"missing or invalid content type for {part}")
            if root_relationships is not None:
                root_targets = {node.attrib.get("Target") for node in root_relationships.findall(f"{{{PR}}}Relationship")}
                if "word/document.xml" not in root_targets:
                    errors.append("package relationship to word/document.xml is missing")
            relationship_map: dict[str, ET.Element] = {}
            if document_relationships is not None:
                relationship_map = {
                    node.attrib.get("Id", ""): node
                    for node in document_relationships.findall(f"{{{PR}}}Relationship")
                }
                targets = {node.attrib.get("Target") for node in relationship_map.values()}
                for target in {"styles.xml", "numbering.xml", "settings.xml"}:
                    if target not in targets:
                        errors.append(f"document relationship to {target} is missing")
            if settings is not None:
                compatibility = settings.find("w:compat/w:compatSetting[@w:name='compatibilityMode']", {"w": W})
                if compatibility is None or compatibility.attrib.get(f"{{{W}}}val") != "15":
                    errors.append("Word compatibility mode is not set to 15")
            if document is not None:
                ns = {"w": W, "m": M, "r": R}
                if document.tag != f"{{{W}}}document" or document.find("w:body", ns) is None:
                    errors.append("word/document.xml has an invalid root or no body")
                for hyperlink in document.findall(".//w:hyperlink", ns):
                    relationship_id = hyperlink.attrib.get(f"{{{R}}}id", "")
                    relationship = relationship_map.get(relationship_id)
                    if relationship is None or relationship.attrib.get("TargetMode") != "External":
                        errors.append(f"hyperlink relationship {relationship_id!r} is missing or not external")
                tables = document.findall(".//w:tbl", ns)
                equations = document.findall(".//m:oMath", ns)
                text_nodes = document.findall(".//w:t", ns)
                list_num_ids = [
                    node.attrib.get(f"{{{W}}}val", "")
                    for paragraph in document.findall(".//w:p", ns)
                    if (node := paragraph.find("w:pPr/w:numPr/w:numId", ns)) is not None
                ]
                unique_list_num_ids = set(list_num_ids)
                defined_num_ids: set[str] = set()
                if numbering is not None:
                    defined_num_ids = {
                        node.attrib.get(f"{{{W}}}numId", "")
                        for node in numbering.findall("w:num", ns)
                    }
                    for number in numbering.findall("w:num", ns):
                        number_id = number.attrib.get(f"{{{W}}}numId", "")
                        restart = number.find("w:lvlOverride/w:startOverride", ns)
                        if number_id in unique_list_num_ids and (
                            restart is None or restart.attrib.get(f"{{{W}}}val") != "1"
                        ):
                            errors.append(f"list numbering instance {number_id!r} does not restart at 1")
                undefined_num_ids = sorted(unique_list_num_ids - defined_num_ids)
                if undefined_num_ids:
                    errors.append("undefined list numbering instances: " + ", ".join(undefined_num_ids))
                rtl_text_runs = 0
                stable_spaces = 0
                for run in document.findall(".//w:r", ns):
                    text = "".join(node.text or "" for node in run.findall("w:t", ns))
                    if contains_rtl(text):
                        rtl_text_runs += 1
                        if run.find("w:rPr/w:rtl", ns) is None:
                            errors.append(f"RTL text run lacks w:rtl: {text[:40]!r}")
                    stable_spaces += text.count("\u00a0")
                for table in tables:
                    table_text = "".join(node.text or "" for node in table.findall(".//w:t", ns))
                    if contains_rtl(table_text) and table.find("w:tblPr/w:bidiVisual", ns) is None:
                        errors.append("RTL table lacks w:bidiVisual")
                    for cell in table.findall(".//w:tc", ns):
                        if cell.find("w:tcPr/w:vAlign[@w:val='center']", ns) is None:
                            errors.append("table cell lacks vertical centering")
                        if cell.find("w:p/w:pPr/w:jc[@w:val='center']", ns) is None:
                            errors.append("table cell lacks horizontal centering")
                visible_text = "".join(node.text or "" for node in text_nodes)
                if re.search(r"\$\$|\\(?:frac|sqrt|theta|alpha|nabla|sum|begin)", visible_text):
                    errors.append("raw supported LaTeX leaked into Word text")
                checks.update({"tables": len(tables), "equations": len(equations), "list_instances": len(unique_list_num_ids), "rtl_text_runs": rtl_text_runs, "word_stable_spaces": stable_spaces})
                if spec:
                    expected_equations = sum(1 for block in spec["blocks"] if block["type"] == "equation")
                    expected_equations += sum(
                        1 for block in spec["blocks"] for item in (block.get("content") if isinstance(block.get("content"), list) else [])
                        if isinstance(item, dict) and item.get("type") == "equation"
                    )
                    if len(equations) != expected_equations:
                        errors.append(f"equation count {len(equations)} != expected {expected_equations}")
                    expected_lists = sum(1 for block in spec["blocks"] if block["type"] == "list")
                    if len(unique_list_num_ids) != expected_lists:
                        errors.append(f"list numbering instances {len(unique_list_num_ids)} != expected {expected_lists}")
            checks["xml_parts"] = len(parsed)
            checks["required_parts"] = not missing
    except Exception as error:
        errors.append(f"cannot read DOCX: {error}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return {"valid": not errors, "errors": errors, "checks": checks, "sha256": digest, "path": str(path)}


def build(spec_path: Path, output_path: Path, report_path: Path | None) -> dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec_summary = validate_spec(spec)
    first = package(spec)
    second = package(spec)
    if first != second:
        raise RuntimeError("compiler output is not deterministic")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(first)
    report = validate_docx(output_path, spec)
    report["spec"] = spec_summary
    report["deterministic"] = True
    if report_path:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not report["valid"]:
        output_path.unlink(missing_ok=True)
        raise RuntimeError("generated DOCX failed validation: " + "; ".join(report["errors"]))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="compile DocSpec JSON into validated DOCX")
    build_parser.add_argument("spec", type=Path)
    build_parser.add_argument("output", type=Path)
    build_parser.add_argument("--report", type=Path)
    validate_parser = subparsers.add_parser("validate", help="validate an existing DOCX")
    validate_parser.add_argument("document", type=Path)
    validate_parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "build":
            report = build(args.spec, args.output, args.report)
        else:
            report = validate_docx(args.document)
        if args.command == "validate" and not args.json:
            print("valid" if report["valid"] else "invalid")
            for error in report["errors"]:
                print(f"- {error}")
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["valid"] else 1
    except (OSError, json.JSONDecodeError, SpecError, RuntimeError) as error:
        print(json.dumps({"valid": False, "errors": [str(error)]}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
