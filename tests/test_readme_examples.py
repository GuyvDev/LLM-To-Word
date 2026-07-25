import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from scripts.generate_readme_examples import crop_to_content


class ReadmeExampleTests(unittest.TestCase):
    def test_publication_crop_is_readable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.png"
            source = Image.new("RGB", (400, 300), "white")
            ImageDraw.Draw(source).rectangle((100, 80, 300, 180), fill="black")
            source.save(path, "PNG")

            crop_to_content(path)
            first_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            with Image.open(path) as published:
                self.assertEqual(published.width, 1200)
                self.assertGreaterEqual(published.height, 250)
                background = Image.new("RGB", published.size, "white")
                bounds = ImageChops.difference(
                    published.convert("RGB"), background
                ).getbbox()
                self.assertEqual(bounds[0], 30)
                self.assertEqual(bounds[1], 30)
                self.assertEqual(bounds[2], 1170)
                self.assertEqual(bounds[3], published.height - 30)

            crop_to_content(path)
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                first_hash,
            )

    def test_publication_crop_rejects_blank_images(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blank.png"
            Image.new("RGB", (400, 300), "white").save(path, "PNG")
            with self.assertRaisesRegex(RuntimeError, "cannot find rendered content"):
                crop_to_content(path)


if __name__ == "__main__":
    unittest.main()
