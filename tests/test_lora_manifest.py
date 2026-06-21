import json
import unittest
from pathlib import Path

from scripts.download_loras import parse_hf_resolve_url, select_loras


MANIFEST_PATH = (
    Path(__file__).parents[1]
    / "config"
    / "anima-loras.json"
)


class LoraManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8")
        )["loras"]

    def test_ids_urls_and_paths_are_unique(self):
        for key in ("id", "url", "path"):
            values = [entry[key] for entry in self.entries]
            self.assertEqual(len(values), len(set(values)), key)

    def test_all_files_install_under_anima_lora_directory(self):
        self.assertTrue(
            all(
                entry["path"].startswith("models/loras/anima/")
                and entry["path"].endswith(".safetensors")
                for entry in self.entries
            )
        )

    def test_workflow_loras_with_known_urls_are_present(self):
        by_id = {entry["id"]: entry for entry in self.entries}
        self.assertEqual(set(by_id), {"pixel-came"})
        self.assertEqual(by_id["pixel-came"]["trigger"], "CAME")
        self.assertEqual(
            by_id["pixel-came"]["url"],
            "https://huggingface.co/uwgm/nikke-loras/resolve/main/"
            "pixel-AnimaB_V10-V1-CAME.safetensors",
        )

    def test_selection_accepts_multiple_ids(self):
        selected = select_loras(self.entries, ["pixel-came"])
        self.assertEqual(
            [entry["id"] for entry in selected],
            ["pixel-came"],
        )

    def test_hugging_face_urls_can_be_passed_to_hf_download(self):
        entry = next(item for item in self.entries if item["id"] == "pixel-came")
        self.assertEqual(
            parse_hf_resolve_url(entry["url"]),
            (
                "uwgm/nikke-loras",
                "pixel-AnimaB_V10-V1-CAME.safetensors",
            ),
        )


if __name__ == "__main__":
    unittest.main()
