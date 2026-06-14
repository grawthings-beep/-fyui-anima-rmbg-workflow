import tempfile
import unittest
import zipfile
from pathlib import Path

from batch_archive import create_batch_zip


class BatchArchiveTests(unittest.TestCase):
    def test_zip_contains_images_and_prompt_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = []
            for index in range(1, 4):
                image = root / f"image_{index:02}.png"
                image.write_bytes(b"fake png")
                images.append(image)

            archive_path = create_batch_zip(
                root / "batch.zip",
                images,
                "01 | seed=123 | from above",
            )

            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(
                    archive.namelist(),
                    [
                        "image_01.png",
                        "image_02.png",
                        "image_03.png",
                        "prompt_report.txt",
                    ],
                )
                self.assertEqual(
                    archive.read("prompt_report.txt").decode("utf-8"),
                    "01 | seed=123 | from above\n",
                )

    def test_empty_report_is_not_added(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "image_01.png"
            image.write_bytes(b"fake png")

            archive_path = create_batch_zip(root / "batch.zip", [image])

            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(archive.namelist(), ["image_01.png"])


if __name__ == "__main__":
    unittest.main()
