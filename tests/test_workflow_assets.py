import json
import unittest
from pathlib import Path


MANIFEST_PATH = (
    Path(__file__).parents[1]
    / "config"
    / "workflow-assets.json"
)
WORKFLOW_PATH = (
    Path(__file__).parents[1]
    / "example_workflows"
    / "anima_single_rmbg_transparent_workflow.json"
)


class WorkflowAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))

    def test_manifest_has_only_workflow_loras(self):
        loras = [
            entry["path"]
            for entry in self.manifest["assets"]
            if entry["kind"] == "lora"
        ]
        self.assertEqual(
            sorted(loras),
            [
                "models/loras/anima-turbo-lora-v0.2.safetensors",
                "models/loras/anima/pixel-AnimaB_V10-V1-CAME.safetensors",
                "models/loras/anima/skintextureV1.safetensors",
            ],
        )

    def test_manifest_covers_workflow_model_widgets(self):
        workflow_text = json.dumps(self.workflow, ensure_ascii=False)
        filenames = {entry["filename"] for entry in self.manifest["assets"]}
        for filename in filenames:
            self.assertIn(filename, workflow_text)


if __name__ == "__main__":
    unittest.main()
