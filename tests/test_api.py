import unittest
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient
from api.main import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_public_conversion_has_no_account_or_watermark(self):
        response = self.client.post("/convert", json={"markdown": "# hello"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("x-quota-limit", response.headers)
        with ZipFile(BytesIO(response.content)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertNotIn("word/footer1.xml", archive.namelist())

    def test_removed_quota_endpoint_and_hidden_docs(self):
        self.assertEqual(self.client.get("/quota").status_code, 404)
        self.assertEqual(self.client.get("/docs").status_code, 404)
