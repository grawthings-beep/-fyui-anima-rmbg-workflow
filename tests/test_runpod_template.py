import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class RunPodTemplateTest(unittest.TestCase):
    def test_template_points_to_start_script(self):
        template = json.loads(
            (ROOT / "runpod" / "pod-template.example.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertIn("8188/http", template["ports"])
        self.assertEqual("/workspace", template["volumeMountPath"])
        self.assertEqual(
            "https://github.com/grawthings-beep/-fyui-anima-rmbg-workflow.git",
            template["env"]["REPO_URL"],
        )
        self.assertIn("runpod/start.sh", " ".join(template["dockerStartCmd"]))

    def test_start_script_is_bash_script(self):
        script = (ROOT / "runpod" / "start.sh").read_text(encoding="utf-8")

        self.assertTrue(script.startswith("#!/usr/bin/env bash\n"))
        self.assertIn("ComfyUI root was not found", script)
        self.assertIn("download_workflow_assets.py", script)


if __name__ == "__main__":
    unittest.main()
