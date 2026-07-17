import importlib.util
import contextlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRAIN_PATH = ROOT / "products" / "skill-one" / "skill-one" / "scripts" / "docx_brain.py"
SPEC = importlib.util.spec_from_file_location("skill_one_brain", BRAIN_PATH)
BRAIN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BRAIN
SPEC.loader.exec_module(BRAIN)

PACKAGER_PATH = ROOT / "products" / "skill-one" / "package_skill.py"
PACKAGER_SPEC = importlib.util.spec_from_file_location("skill_one_packager", PACKAGER_PATH)
PACKAGER = importlib.util.module_from_spec(PACKAGER_SPEC)
sys.modules[PACKAGER_SPEC.name] = PACKAGER
PACKAGER_SPEC.loader.exec_module(PACKAGER)


class SkillOneTests(unittest.TestCase):
    def comprehensive_spec(self):
        return {
            "version": "1.0",
            "metadata": {"title": "בדיקת Skill One", "author": "Tests"},
            "blocks": [
                {"type": "heading", "level": 1, "content": "דוח Q4 — 2026"},
                {"type": "heading", "level": 6, "content": "כל רמות הכותרת"},
                {
                    "type": "paragraph",
                    "content": [
                        {"text": "המודל Transformer הגיע ל־"},
                        {"text": "94.7%", "bold": True},
                        {"text": " (Accuracy), ועלותו "},
                        {"text": "$42", "italic": True},
                        {"text": " בסוף."},
                        {"type": "break"},
                        {"text": "code()", "code": True},
                        {"text": " highlighted", "highlight": True},
                        {"text": " x", "superscript": True},
                        {"type": "equation", "latex": "x^2"},
                        {"type": "link", "text": " OpenAI", "url": "https://openai.com"},
                    ],
                },
                {"type": "equation", "latex": "\\frac{1}{n}\\sum_{i=1}^{m}(y_i-\\theta)^2"},
                {"type": "quote", "content": "מסקנה: value < 0.01."},
                {"type": "code", "language": "bash", "text": "printf '%s\\n' \"ok\""},
                {"type": "list", "ordered": False, "items": ["פריט (A)", "Item — 2"]},
                {"type": "list", "ordered": True, "items": ["ראשון", "Second"]},
                {"type": "paragraph", "content": "Between lists"},
                {"type": "list", "ordered": True, "items": ["Restarted first", "Restarted second"]},
                {
                    "type": "table",
                    "direction": "rtl",
                    "headers": ["מודל", "Accuracy", "זמן אימון"],
                    "rows": [["Transformer", "94.7%", "12 דקות"], ["CNN-LSTM", "91.3%", "15 דקות"]],
                },
                {"type": "horizontal_rule"},
                {"type": "page_break"},
            ],
        }

    def test_build_is_deterministic_and_structurally_valid(self):
        spec = self.comprehensive_spec()
        first = BRAIN.package(spec)
        second = BRAIN.package(spec)
        self.assertEqual(first, second)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.docx"
            path.write_bytes(first)
            report = BRAIN.validate_docx(path, spec)
            self.assertTrue(report["valid"], report["errors"])
            self.assertGreaterEqual(report["checks"]["rtl_text_runs"], 1)
            self.assertGreaterEqual(report["checks"]["word_stable_spaces"], 2)
            self.assertEqual(report["checks"]["tables"], 1)
            self.assertEqual(report["checks"]["list_instances"], 3)
            self.assertEqual(report["checks"]["em_dash_parts"], 0)

            with zipfile.ZipFile(path) as archive:
                document = archive.read("word/document.xml").decode("utf-8")
                numbering = archive.read("word/numbering.xml").decode("utf-8")
                settings = archive.read("word/settings.xml").decode("utf-8")
            self.assertIn("<w:rtl/>", document)
            self.assertIn("<w:bidiVisual/>", document)
            self.assertIn('<w:vAlign w:val="center"/>', document)
            self.assertIn('<w:jc w:val="center"/>', document)
            self.assertIn("<m:oMath", document)
            self.assertIn("\u00a0", document)
            self.assertIn('<w:rtl w:val="0"/>', document)
            self.assertNotIn("—", document)
            self.assertIn("Q4 - 2026", document)
            self.assertIn("Item - 2", document)
            self.assertIn('w:name="compatibilityMode"', settings)
            self.assertIn('w:val="15"', settings)
            self.assertEqual(numbering.count('<w:startOverride w:val="1"/>'), 3)
            self.assertIn('<w:num w:numId="2"><w:abstractNumId w:val="1"/>', numbering)
            self.assertIn('<w:num w:numId="3"><w:abstractNumId w:val="1"/>', numbering)

    def test_each_ordered_list_gets_an_independent_restart(self):
        spec = {
            "version": "1.0",
            "blocks": [
                {"type": "list", "ordered": True, "items": ["A", "B", "C"]},
                {"type": "paragraph", "content": "separator"},
                {"type": "list", "ordered": True, "items": ["D", "E", "F", "G"]},
            ],
        }
        payload = BRAIN.package(spec)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lists.docx"
            path.write_bytes(payload)
            report = BRAIN.validate_docx(path, spec)
            self.assertTrue(report["valid"], report["errors"])
            self.assertEqual(report["checks"]["list_instances"], 2)
            with zipfile.ZipFile(path) as archive:
                numbering = archive.read("word/numbering.xml").decode("utf-8")
            self.assertEqual(numbering.count('<w:startOverride w:val="1"/>'), 2)

    def test_em_dash_is_normalized_before_directional_splitting(self):
        segments = BRAIN.split_directional("דוגמה 4 — מקרה בעברית")
        self.assertEqual(segments, [("דוגמה 4 - מקרה בעברית", True)])
        mixed = BRAIN.split_directional("דוגמה 4 — LLM בעברית")
        self.assertEqual(mixed[0], ("דוגמה\u00a04\u00a0-\u00a0", True))
        self.assertEqual(mixed[1], ("LLM\u00a0", False))

    def test_clean_replaces_every_em_dash_with_regular_hyphen(self):
        self.assertEqual(BRAIN.clean("before — middle —— after"), "before - middle -- after")

    def test_build_cli_writes_validation_report(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "input.json"
            output = base / "output.docx"
            report_path = base / "report.json"
            source.write_text(json.dumps(self.comprehensive_spec(), ensure_ascii=False), encoding="utf-8")
            report = BRAIN.build(source, output, report_path)
            self.assertTrue(report["valid"])
            self.assertTrue(report["deterministic"])
            self.assertEqual(report, json.loads(report_path.read_text(encoding="utf-8")))

    def test_validator_rejects_corrupt_package(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrupt.docx"
            path.write_bytes(b"not a zip")
            report = BRAIN.validate_docx(path)
            self.assertFalse(report["valid"])
            self.assertTrue(report["errors"])

    def test_validator_rejects_broken_ooxml_relationships(self):
        source = BRAIN.package(self.comprehensive_spec())
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.docx"
            broken = Path(directory) / "broken.docx"
            original.write_bytes(source)
            with zipfile.ZipFile(original) as archive:
                entries = {name: archive.read(name) for name in archive.namelist()}
            relationships = entries["word/_rels/document.xml.rels"].decode("utf-8")
            relationships = relationships.replace(' Target="styles.xml"', ' Target="missing-styles.xml"')
            entries["word/_rels/document.xml.rels"] = relationships.encode("utf-8")
            with zipfile.ZipFile(broken, "w") as archive:
                for name, payload in entries.items():
                    archive.writestr(name, payload)
            report = BRAIN.validate_docx(broken)
            self.assertFalse(report["valid"])
            self.assertTrue(any("styles.xml" in error for error in report["errors"]))

    def test_validator_rejects_an_em_dash_in_any_package_xml(self):
        source = BRAIN.package(self.comprehensive_spec())
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.docx"
            broken = Path(directory) / "broken.docx"
            original.write_bytes(source)
            with zipfile.ZipFile(original) as archive:
                entries = {name: archive.read(name) for name in archive.namelist()}
            document = entries["word/document.xml"].decode("utf-8")
            entries["word/document.xml"] = document.replace("Item - 2", "Item — 2").encode("utf-8")
            with zipfile.ZipFile(broken, "w") as archive:
                for name, payload in entries.items():
                    archive.writestr(name, payload)
            report = BRAIN.validate_docx(broken)
            self.assertFalse(report["valid"])
            self.assertEqual(report["checks"]["em_dash_parts"], 1)
            self.assertTrue(any("em dash" in error for error in report["errors"]))

    def test_invalid_docspec_is_rejected(self):
        invalid_specs = [
            {},
            {"version": "2.0", "blocks": []},
            {"version": "1.0", "blocks": [{"type": "heading", "level": 7, "content": "x"}]},
            {"version": "1.0", "blocks": [{"type": "table", "headers": ["a"], "rows": [["a", "b"]]}]},
            {"version": "1.0", "blocks": [{"type": "unknown"}]},
        ]
        for spec in invalid_specs:
            with self.subTest(spec=spec), self.assertRaises(BRAIN.SpecError):
                BRAIN.validate_spec(spec)

    def test_unknown_or_malformed_latex_is_rejected(self):
        for latex in [r"\\unknown{x}", r"\\frac{1}{2"]:
            with self.subTest(latex=latex), self.assertRaises(BRAIN.SpecError):
                BRAIN.latex_to_omml(latex)

    def test_upload_package_is_deterministic_and_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.zip"
            second = Path(directory) / "second.zip"
            with contextlib.redirect_stdout(io.StringIO()):
                PACKAGER.package(first)
                PACKAGER.package(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertIsNone(archive.testzip())
                self.assertTrue({f"skill-one/{name}" for name in PACKAGER.REQUIRED} <= set(archive.namelist()))


if __name__ == "__main__":
    unittest.main()
