import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BRAIN_PATH = ROOT / "products" / "skill-one" / "skill-one" / "scripts" / "docx_brain.py"
SPEC = importlib.util.spec_from_file_location("skill_one_launcher", BRAIN_PATH)
BRAIN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BRAIN
SPEC.loader.exec_module(BRAIN)

VISUAL_GATE_PATH = (
    ROOT
    / "products"
    / "skill-one"
    / "skill-one"
    / "scripts"
    / "visual_gate.py"
)

PACKAGER_PATH = ROOT / "products" / "skill-one" / "package_skill.py"
PACKAGER_SPEC = importlib.util.spec_from_file_location("skill_one_packager", PACKAGER_PATH)
PACKAGER = importlib.util.module_from_spec(PACKAGER_SPEC)
sys.modules[PACKAGER_SPEC.name] = PACKAGER
PACKAGER_SPEC.loader.exec_module(PACKAGER)

MARKDOWN = """# Spotwize - מפת דרכים

**גרסה:** 1.0

## 2. Phase 0 - תשתית ותכנון Validation

- מזכר Legal Feasibility ו-Compliance.
- הפחתה של 20% ב-Median Search Time.

| פריט | טווח |
|---|---:|
| Baseline | 88.2% |

$$
\\theta_{t+1}=\\theta_t-\\alpha\\nabla_\\theta L(\\theta_t)
$$
"""


class SkillOneTests(unittest.TestCase):
    def test_ltr_syntax_atom_detection_is_narrow(self):
        self.assertTrue(BRAIN.is_balanced_ascii_syntax_atom("{A[0]}"))
        for value in ("[פעיל]", "{A]0[}", "{A[0]} extra", "{plain}", "[0]"):
            self.assertFalse(BRAIN.is_balanced_ascii_syntax_atom(value), value)

    def test_wrapper_matches_shared_core_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            markdown = base / "input.md"
            wrapped = base / "wrapped.docx"
            direct = base / "direct.docx"
            markdown.write_text(MARKDOWN, encoding="utf-8")
            report = BRAIN.build(markdown, wrapped, "llm", None)
            core = BRAIN.find_core()
            subprocess.run([str(core), str(markdown), str(direct), "llm"], check=True)
            self.assertTrue(report["valid"], report["errors"])
            self.assertEqual(wrapped.read_bytes(), direct.read_bytes())

    def test_build_report_and_shared_rtl_output(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            markdown = base / "input.md"
            output = base / "output.docx"
            report_path = base / "report.json"
            markdown.write_text(MARKDOWN, encoding="utf-8")
            report = BRAIN.build(markdown, output, "llm", report_path)
            self.assertEqual(report, json.loads(report_path.read_text(encoding="utf-8")))
            self.assertEqual(report["schema_version"], 3)
            self.assertEqual(report["output"]["checks"]["engine"], "md2docx-core")
            self.assertTrue(report["output"]["checks"]["engine_verified"])
            self.assertTrue(report["core_self_test"]["valid"])
            self.assertTrue(report["core_self_test"]["deterministic"])
            self.assertTrue(report["feature_coverage"]["valid"])
            self.assertTrue(report["deterministic_replay"]["byte_identical"])
            self.assertEqual(report["checks"]["engine"], "md2docx-core")
            for check in (
                "engine_verified",
                "runtime_manifest_verified",
                "markdown_preflight",
                "core_self_test",
                "feature_coverage",
                "ooxml_semantics",
                "text_fidelity",
                "deterministic_replay",
                "input_sha256_verified",
            ):
                self.assertTrue(report["checks"][check], check)
            self.assertEqual(
                report["input"]["sha256"],
                hashlib.sha256(markdown.read_bytes()).hexdigest(),
            )
            self.assertEqual(report["input_sha256"], report["input"]["sha256"])
            self.assertEqual(report["output_sha256"], report["output"]["sha256"])
            self.assertEqual(
                report["input"]["features"]["bytes"], len(markdown.read_bytes())
            )
            self.assertEqual(report["output"]["checks"]["em_dash_parts"], 0)
            self.assertEqual(report["output"]["checks"]["bidi_control_parts"], 1)
            self.assertEqual(report["output"]["checks"]["bidi_isolate_parts"], 1)
            self.assertGreater(report["output"]["checks"]["bidi_isolate_pairs"], 0)
            self.assertEqual(
                report["output"]["checks"]["unsafe_bidi_control_parts"], 0
            )
            with zipfile.ZipFile(output) as archive:
                document = archive.read("word/document.xml").decode("utf-8")
            for component in (
                "2. Phase 0",
                "תשתית ותכנון",
                "Validation",
                "ו־",
                "Compliance",
                "ב־",
                "Median Search Time",
            ):
                self.assertIn(component, document)
            self.assertIn("<w:rtl/>", document)
            self.assertIn('<w:rtl w:val="0"/>', document)
            self.assertNotIn("\u00a0", document)
            self.assertIn('xml:space="preserve"> 1.0</w:t>', document)
            self.assertIn('xml:space="preserve"> תשתית ותכנון </w:t>', document)
            self.assertIn("<w:bidiVisual/>", document)
            self.assertIn("<m:oMath", document)
            self.assertNotIn("—", document)
            self.assertNotRegex(
                document, r"[\u200e\u200f\u202a-\u202e\u2067\u2068]"
            )
            self.assertEqual(document.count(BRAIN.LRI), document.count(BRAIN.PDI))
            self.assertGreater(document.count(BRAIN.LRI), 0)

    def test_cli_builds_markdown_and_writes_report(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            markdown = base / "input.md"
            output = base / "output.docx"
            report = base / "report.json"
            markdown.write_text(MARKDOWN, encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(BRAIN_PATH), "build", str(markdown), str(output), "--source", "llm", "--report", str(report)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(output.is_file())
            stdout_report = json.loads(completed.stdout)
            saved_report = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(stdout_report["valid"])
            self.assertTrue(saved_report["valid"])
            self.assertTrue(saved_report["deterministic_replay"]["byte_identical"])

    def test_review_writes_extracted_text_and_runs_every_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            markdown = base / "input.md"
            output = base / "output.docx"
            review_text = base / "extracted.txt"
            report_path = base / "review.json"
            markdown.write_text(MARKDOWN, encoding="utf-8")
            self.assertTrue(BRAIN.build(markdown, output, "llm", None)["valid"])
            completed = subprocess.run(
                [
                    sys.executable,
                    str(BRAIN_PATH),
                    "review",
                    str(markdown),
                    str(output),
                    "--source",
                    "llm",
                    "--report",
                    str(report_path),
                    "--review-text",
                    str(review_text),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(completed.stdout)
            self.assertEqual(report["command"], "review")
            self.assertTrue(report["valid"], report["errors"])
            self.assertEqual(report["text_fidelity"]["token_coverage"], 1.0)
            self.assertTrue(review_text.is_file())
            self.assertIn("Baseline", review_text.read_text(encoding="utf-8"))
            for check in (
                "engine_verified",
                "runtime_manifest_verified",
                "markdown_preflight",
                "core_self_test",
                "feature_coverage",
                "ooxml_semantics",
                "text_fidelity",
                "deterministic_replay",
                "input_sha256_verified",
            ):
                self.assertTrue(report["checks"][check], check)

    def test_doctor_and_markdown_preflight_cover_runtime_features(self):
        doctor = BRAIN.core_self_test(BRAIN.find_core())
        self.assertTrue(doctor["valid"], doctor["errors"])
        self.assertTrue(doctor["deterministic"])
        self.assertTrue(doctor["feature_coverage"]["valid"])
        actual = doctor["feature_coverage"]["actual"]
        for feature in (
            "headings",
            "tables",
            "list_items",
            "math_expressions",
            "rtl_paragraphs",
            "rtl_runs",
            "ltr_runs",
            "rtl_tables",
            "code_fonts",
        ):
            self.assertGreater(actual[feature], 0, feature)

        with tempfile.TemporaryDirectory() as directory:
            malformed = Path(directory) / "malformed.md"
            malformed.write_text("# Title\n\n```bash\necho broken\n", encoding="utf-8")
            report = BRAIN.preflight_markdown(malformed)
            self.assertFalse(report["valid"])
            self.assertIn("unclosed fenced code block", report["errors"])

    def test_preflight_ignores_markdown_symbols_inside_code_and_currency(self):
        with tempfile.TemporaryDirectory() as directory:
            markdown = Path(directory) / "code.md"
            markdown.write_text(
                """# Real heading

The price moved from $42 to $31 and `$not_math$` remains code.

```markdown
# Fake heading
| Fake | Table |
|---|---|
$$fake_math$$
- fake list
```
""",
                encoding="utf-8",
            )
            report = BRAIN.preflight_markdown(markdown)
            self.assertTrue(report["valid"], report["errors"])
            features = report["features"]
            self.assertEqual(features["headings"], 1)
            self.assertEqual(features["tables"], 0)
            self.assertEqual(features["list_items"], 0)
            self.assertEqual(features["math_expressions"], 0)
            self.assertEqual(features["fenced_code_blocks"], 1)
            self.assertEqual(features["inline_code"], 1)

    def test_preflight_rejects_invalid_utf8_and_nul_input(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            invalid_utf8 = base / "invalid.md"
            invalid_utf8.write_bytes(b"# title\n\xff")
            self.assertFalse(BRAIN.preflight_markdown(invalid_utf8)["valid"])

            nul = base / "nul.md"
            nul.write_bytes(b"# title\n\x00body")
            self.assertFalse(BRAIN.preflight_markdown(nul)["valid"])

    def test_build_rejects_wrong_expected_input_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            markdown = base / "input.md"
            output = base / "output.docx"
            report_path = base / "report.json"
            markdown.write_text(MARKDOWN, encoding="utf-8")
            report = BRAIN.build(
                markdown,
                output,
                "llm",
                report_path,
                expected_input_sha256="0" * 64,
            )
            self.assertFalse(report["valid"])
            self.assertFalse(output.exists())
            self.assertTrue(
                any("input SHA-256 mismatch" in error for error in report["errors"])
            )
            self.assertEqual(
                report, json.loads(report_path.read_text(encoding="utf-8"))
            )

    def test_verify_run_rejects_tampering_and_skipped_features(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            markdown = base / "input.md"
            original = base / "original.docx"
            tampered = base / "tampered.docx"
            markdown.write_text(MARKDOWN, encoding="utf-8")
            self.assertTrue(BRAIN.build(markdown, original, "llm", None)["valid"])
            with zipfile.ZipFile(original) as archive:
                entries = {name: archive.read(name) for name in archive.namelist()}
            document = entries["word/document.xml"].decode("utf-8")
            table_start = document.index("<w:tbl>")
            table_end = document.index("</w:tbl>", table_start) + len("</w:tbl>")
            entries["word/document.xml"] = (
                document[:table_start] + document[table_end:]
            ).encode("utf-8")
            with zipfile.ZipFile(tampered, "w") as archive:
                for name, payload in entries.items():
                    archive.writestr(name, payload)
            package = BRAIN.validate_docx(tampered)
            self.assertTrue(package["valid"], package["errors"])
            report = BRAIN.verify_run(markdown, tampered, "llm", None)
            self.assertFalse(report["valid"])
            self.assertFalse(report["feature_coverage"]["valid"])
            self.assertFalse(report["deterministic_replay"]["valid"])
            self.assertTrue(
                any("tables coverage mismatch" in error for error in report["errors"])
            )
            self.assertTrue(
                any("deterministic replay" in error for error in report["errors"])
            )

    def test_verify_run_rejects_docx_built_from_different_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            intended = base / "intended.md"
            substituted = base / "substituted.md"
            output = base / "output.docx"
            intended.write_text("# Original\n\nKeep every section.", encoding="utf-8")
            substituted.write_text("# Rewritten\n\nA shorter replacement.", encoding="utf-8")
            self.assertTrue(BRAIN.build(substituted, output, "llm", None)["valid"])
            report = BRAIN.verify_run(intended, output, "llm", None)
            self.assertFalse(report["valid"])
            self.assertFalse(report["deterministic_replay"]["byte_identical"])

    def test_strict_build_accepts_supported_conformance_dialects(self):
        cases = json.loads(
            (ROOT / "tests" / "fixtures" / "markdown_conformance.json").read_text(
                encoding="utf-8"
            )
        )
        intentionally_rejected = {"malformed-markup-recovers", "empty-and-whitespace"}
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for case in cases:
                markdown = base / f"{case['id']}.md"
                output = base / f"{case['id']}.docx"
                markdown.write_text(case["markdown"], encoding="utf-8")
                report = BRAIN.build(
                    markdown, output, case["source"], None
                )
                if case["id"] in intentionally_rejected:
                    self.assertFalse(report["valid"], case["id"])
                    self.assertFalse(output.exists(), case["id"])
                else:
                    self.assertTrue(
                        report["valid"], f"{case['id']}: {report['errors']}"
                    )
                    self.assertTrue(
                        report["checks"]["feature_coverage"], case["id"]
                    )
                    self.assertTrue(report["checks"]["ooxml_semantics"], case["id"])
                    self.assertTrue(report["checks"]["text_fidelity"], case["id"])

    def test_reviewer_accepts_full_hebrew_and_mixed_bidi_benchmarks(self):
        fixtures = (
            "canonical_markdown.md",
            "hebrew_experiment_benchmark.md",
            "spotwize_bidi_regression.md",
        )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for name in fixtures:
                source = ROOT / "tests" / "fixtures" / name
                output = base / f"{source.stem}.docx"
                review_text = base / f"{source.stem}.txt"
                report = BRAIN.build(
                    source,
                    output,
                    "llm",
                    None,
                    review_text_path=review_text,
                )
                self.assertTrue(report["valid"], f"{name}: {report['errors']}")
                self.assertTrue(report["checks"]["ooxml_semantics"], name)
                self.assertTrue(report["checks"]["text_fidelity"], name)
                self.assertEqual(
                    report["text_fidelity"]["token_coverage"], 1.0, name
                )
                self.assertTrue(review_text.read_text(encoding="utf-8").strip())

    def test_exact_word_visual_brackets_keep_natural_review_text(self):
        markdown_text = """# בדיקת כיווניות

סטטוס: [פעיל] (Beta).

{A[0]} נשאר קריא.

השילוב בין עברית, English, מספרים.

אחריות: צוות Platform מטפל ב-`release_check()`.
"""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            markdown = base / "input.md"
            output = base / "output.docx"
            review_text = base / "review.txt"
            markdown.write_text(markdown_text, encoding="utf-8")
            report = BRAIN.build(
                markdown,
                output,
                "llm",
                None,
                review_text_path=review_text,
            )
            self.assertTrue(report["valid"], report["errors"])
            with zipfile.ZipFile(output) as archive:
                document_bytes = archive.read("word/document.xml")
                document = document_bytes.decode("utf-8")
            self.assertIn("[פעיל]", document)
            self.assertNotIn("]פעיל[", document)
            self.assertIn('<w:bdo w:val="ltr">', document)
            root = ET.fromstring(document_bytes)
            word = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            overrides = [
                BRAIN.compiler_ltr_syntax_atom(node)
                for node in root.iter(f"{{{word}}}bdo")
            ]
            self.assertEqual(overrides, ["{A[0]}"])
            self.assertIn(f"{BRAIN.LRI}(Beta){BRAIN.PDI}", document)
            self.assertIn(">.</w:t>", document)
            self.assertNotIn(f"{BRAIN.LRI}{{A[0]}}{BRAIN.PDI}", document)
            self.assertNotIn("<w:dir", document)
            self.assertIn(f"{BRAIN.LRI}English{BRAIN.PDI}", document)
            self.assertIn(">,</w:t>", document)
            self.assertIn(
                f"{BRAIN.LRI}release_check(){BRAIN.PDI}", document
            )
            self.assertNotIn(
                f"{BRAIN.LRI}release_check().{BRAIN.PDI}", document
            )
            reviewed = review_text.read_text(encoding="utf-8")
            self.assertIn("סטטוס: [פעיל] (Beta).", reviewed)
            self.assertIn("{A[0]} נשאר קריא.", reviewed)
            self.assertIn("release_check().", reviewed)
            self.assertNotIn("]פעיל[", reviewed)
            self.assertEqual(report["text_fidelity"]["token_coverage"], 1.0)

    def test_reviewer_rejects_bidi_text_and_table_alignment_damage(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            markdown = base / "input.md"
            original = base / "original.docx"
            markdown.write_text(MARKDOWN, encoding="utf-8")
            self.assertTrue(BRAIN.build(markdown, original, "llm", None)["valid"])
            with zipfile.ZipFile(original) as archive:
                base_entries = {
                    name: archive.read(name) for name in archive.namelist()
                }

            cases = {
                "rtl": ("<w:rtl/>", "", "RTL properties"),
                "center": (
                    '<w:jc w:val="center"/>',
                    '<w:jc w:val="left"/>',
                    "not centered",
                ),
            }
            for name, (old, new, expected_error) in cases.items():
                entries = dict(base_entries)
                document = entries["word/document.xml"].decode("utf-8")
                self.assertIn(old, document)
                start = document.index("<w:tc>") if name == "center" else 0
                prefix = document[:start]
                suffix = document[start:].replace(old, new, 1)
                entries["word/document.xml"] = (prefix + suffix).encode("utf-8")
                damaged = base / f"{name}.docx"
                with zipfile.ZipFile(damaged, "w") as archive:
                    for relative, payload in entries.items():
                        archive.writestr(relative, payload)
                report = BRAIN.verify_run(markdown, damaged, "llm", None)
                self.assertFalse(report["valid"], name)
                self.assertFalse(report["checks"]["ooxml_semantics"], name)
                self.assertTrue(
                    any(expected_error in error for error in report["errors"]),
                    report["errors"],
                )

    def test_reviewer_rejects_text_omission_even_when_structure_survives(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            markdown = base / "input.md"
            original = base / "original.docx"
            damaged = base / "damaged.docx"
            markdown.write_text(MARKDOWN, encoding="utf-8")
            self.assertTrue(BRAIN.build(markdown, original, "llm", None)["valid"])
            with zipfile.ZipFile(original) as archive:
                entries = {name: archive.read(name) for name in archive.namelist()}
            document = entries["word/document.xml"].decode("utf-8")
            self.assertIn("Baseline", document)
            entries["word/document.xml"] = document.replace(
                "Baseline", "Removed", 1
            ).encode("utf-8")
            with zipfile.ZipFile(damaged, "w") as archive:
                for name, payload in entries.items():
                    archive.writestr(name, payload)
            report = BRAIN.verify_run(markdown, damaged, "llm", None)
            self.assertFalse(report["valid"])
            self.assertFalse(report["checks"]["text_fidelity"])
            self.assertIn("baseline", report["text_fidelity"]["missing_sample"])

    def test_validator_rejects_corrupt_and_forbidden_content(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            corrupt = base / "corrupt.docx"
            corrupt.write_bytes(b"not a zip")
            self.assertFalse(BRAIN.validate_docx(corrupt)["valid"])

            markdown = base / "input.md"
            original = base / "original.docx"
            broken = base / "broken.docx"
            markdown.write_text(MARKDOWN, encoding="utf-8")
            BRAIN.build(markdown, original, "llm", None)
            with zipfile.ZipFile(original) as archive:
                entries = {name: archive.read(name) for name in archive.namelist()}
            document = entries["word/document.xml"].decode("utf-8")
            entries["word/document.xml"] = document.replace(
                "Baseline", "—\u202eBaseline", 1
            ).encode("utf-8")
            with zipfile.ZipFile(broken, "w") as archive:
                for name, payload in entries.items():
                    archive.writestr(name, payload)
            report = BRAIN.validate_docx(broken)
            self.assertFalse(report["valid"])
            self.assertEqual(report["checks"]["em_dash_parts"], 1)
            self.assertEqual(report["checks"]["bidi_control_parts"], 1)
            self.assertEqual(report["checks"]["unsafe_bidi_control_parts"], 1)

    def test_validator_rejects_unbalanced_compiler_isolates(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            markdown = base / "input.md"
            original = base / "original.docx"
            broken = base / "broken.docx"
            markdown.write_text(MARKDOWN, encoding="utf-8")
            self.assertTrue(BRAIN.build(markdown, original, "llm", None)["valid"])
            with zipfile.ZipFile(original) as archive:
                entries = {name: archive.read(name) for name in archive.namelist()}
            document = entries["word/document.xml"].decode("utf-8")
            self.assertIn(BRAIN.PDI, document)
            entries["word/document.xml"] = document.replace(BRAIN.PDI, "", 1).encode(
                "utf-8"
            )
            with zipfile.ZipFile(broken, "w") as archive:
                for name, payload in entries.items():
                    archive.writestr(name, payload)
            report = BRAIN.validate_docx(broken)
            self.assertFalse(report["valid"])
            self.assertTrue(
                any("unclosed compiler-owned LTR isolate" in error for error in report["errors"]),
                report["errors"],
            )

    def test_replay_rejects_extra_or_duplicate_package_parts(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            markdown = base / "input.md"
            original = base / "original.docx"
            markdown.write_text(MARKDOWN, encoding="utf-8")
            self.assertTrue(BRAIN.build(markdown, original, "llm", None)["valid"])
            with zipfile.ZipFile(original) as archive:
                entries = [(name, archive.read(name)) for name in archive.namelist()]

            damaged = base / "unsafe.docx"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(damaged, "w") as archive:
                    for name, payload in entries:
                        archive.writestr(name, payload)
                    archive.writestr("word/document.xml", b"<duplicate/>")
                    archive.writestr("../escape.xml", b"<unsafe/>")
                    archive.writestr("word/vbaProject.bin", b"macro")
            report = BRAIN.validate_docx(damaged)
            self.assertTrue(report["valid"])
            replay = BRAIN.verify_run(markdown, damaged, "llm", None)
            self.assertFalse(replay["valid"])
            self.assertFalse(replay["checks"]["deterministic_replay"])

    def test_validator_rejects_unverified_engine_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            markdown = base / "input.md"
            original = base / "original.docx"
            foreign = base / "foreign.docx"
            markdown.write_text(MARKDOWN, encoding="utf-8")
            BRAIN.build(markdown, original, "llm", None)
            with zipfile.ZipFile(original) as archive:
                entries = {name: archive.read(name) for name in archive.namelist()}
            entries["docProps/core.xml"] = entries["docProps/core.xml"].replace(
                b"md2docx canonical compiler", b"another DOCX generator"
            )
            with zipfile.ZipFile(foreign, "w") as archive:
                for name, payload in entries.items():
                    archive.writestr(name, payload)
            report = BRAIN.validate_docx(foreign)
            self.assertFalse(report["valid"])
            self.assertIsNone(report["checks"]["engine"])
            self.assertFalse(report["checks"]["engine_verified"])
            self.assertTrue(
                any("engine provenance" in error for error in report["errors"])
            )

    def test_upload_package_is_deterministic_and_contains_shared_cores(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.zip"
            second = Path(directory) / "second.zip"
            with contextlib.redirect_stdout(io.StringIO()):
                PACKAGER.package(first)
                PACKAGER.package(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                names = set(archive.namelist())
                self.assertIn("skill-one/bin/md2docx-core.exe", names)
                self.assertIn("skill-one/bin/md2docx-core-linux-x64", names)
                self.assertIn("skill-one/assets/example.md", names)
                self.assertIn("skill-one/assets/icon.svg", names)
                self.assertIn("skill-one/assets/runtime-manifest.json", names)
                self.assertIn("skill-one/scripts/visual_gate.py", names)

    def test_visual_gate_requires_exact_hashes_and_complete_page_review(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            docx = base / "output.docx"
            pdf = base / "output.pdf"
            pages = base / "pages"
            report_path = base / "visual-report.json"
            docx.write_bytes(b"docx")
            pdf.write_bytes(b"%PDF-test")
            pages.mkdir()
            (pages / "page-1.png").write_bytes(b"png")
            report = {
                "visual_valid": True,
                "docx_sha256": hashlib.sha256(docx.read_bytes()).hexdigest(),
                "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                "pages_expected": 1,
                "pages_rendered": 1,
                "pages_reviewed": 1,
                "reviewed_pages": [1],
                "issues": [],
                "rebuild_count": 0,
            }
            report_path.write_text(json.dumps(report), encoding="utf-8")
            command = [
                sys.executable,
                str(VISUAL_GATE_PATH),
                "--docx",
                str(docx),
                "--pdf",
                str(pdf),
                "--pages-dir",
                str(pages),
                "--report",
                str(report_path),
            ]
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(json.loads(completed.stdout)["valid"])

            report["reviewed_pages"] = []
            report_path.write_text(json.dumps(report), encoding="utf-8")
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("reviewed_pages", completed.stdout)

    def test_bundled_runtime_hash_cannot_be_bypassed_by_environment_or_tampering(self):
        core = BRAIN.find_core()
        with mock.patch.dict(
            "os.environ", {"MD2DOCX_CORE": str(ROOT / "untrusted.exe")}
        ):
            self.assertEqual(BRAIN.find_core(), core)

        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "skill.zip"
            extracted = Path(directory) / "extracted"
            with contextlib.redirect_stdout(io.StringIO()):
                PACKAGER.package(package)
            with zipfile.ZipFile(package) as archive:
                archive.extractall(extracted)
            binary = extracted / "skill-one" / "bin" / core.name
            binary.write_bytes(binary.read_bytes() + b"tampered")
            brain = (
                extracted
                / "skill-one"
                / "scripts"
                / "docx_brain.py"
            )
            completed = subprocess.run(
                [sys.executable, str(brain), "doctor", "--json"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("hash mismatch", completed.stderr)


if __name__ == "__main__":
    unittest.main()
