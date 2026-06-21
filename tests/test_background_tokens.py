import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class BackgroundTokenTests(unittest.TestCase):
    def test_hf_token_rejects_unresolved_runpod_secret_placeholders(self):
        source = (ROOT / "nodes.py").read_text(encoding="utf-8")

        self.assertIn("def _is_unresolved_template", source)
        self.assertIn("RUNPOD_SECRET", source)
        self.assertIn("return None", source)

    def test_start_script_warns_about_unresolved_hf_token(self):
        source = (ROOT / "runpod" / "start.sh").read_text(encoding="utf-8")

        self.assertIn("HF_TOKEN looks like an unresolved RunPod secret", source)
        self.assertIn("BRIA RMBG-2.0 will not load", source)


if __name__ == "__main__":
    unittest.main()
