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
        self.assertEqual(
            "runpod/pytorch:1.0.7-cu1290-torch280-ubuntu2204",
            template["imageName"],
        )
        self.assertEqual("1", template["env"]["INSTALL_COMFYUI"])
        self.assertIn("runpod/start.sh", " ".join(template["dockerStartCmd"]))

    def test_start_script_is_bash_script(self):
        script = (ROOT / "runpod" / "start.sh").read_text(encoding="utf-8")

        self.assertTrue(script.startswith("#!/usr/bin/env bash\n"))
        self.assertIn("ComfyUI was not found; installing it", script)
        self.assertIn("download_workflow_assets.py", script)

    def test_raw_start_command_is_short_ui_json(self):
        raw_command = json.loads(
            (ROOT / "runpod" / "start-command.raw.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(["bash", "-lc"], raw_command["entrypoint"])
        self.assertEqual(1, len(raw_command["cmd"]))
        self.assertIn("runpod/start.sh", raw_command["cmd"][0])
        self.assertNotIn("imageName", raw_command)


if __name__ == "__main__":
    unittest.main()
