import unittest
from io import BytesIO
from zipfile import ZipFile

from md2docx import convert_markdown


class ConverterTests(unittest.TestCase):
    def test_generates_valid_docx_with_rtl_and_math(self):
        output = convert_markdown("# שלום\n\nFormula: $x^2$")
        with ZipFile(BytesIO(output)) as archive:
            self.assertIsNone(archive.testzip())
            xml = archive.read("word/document.xml")
        self.assertIn("שלום".encode("utf-8"), xml)

    def test_conversion_has_no_service_watermark(self):
        output = convert_markdown("hello")
        with ZipFile(BytesIO(output)) as archive:
            names = archive.namelist()
        self.assertNotIn("word/footer1.xml", names)
