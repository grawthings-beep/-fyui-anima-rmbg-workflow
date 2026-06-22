import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class RunPodTemplateTest(unittest.TestCase):
    def test_template_uses_built_ghcr_image(self):
        template = json.loads(
            (ROOT / "runpod" / "pod-template.example.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertIn("8188/http", template["ports"])
        self.assertNotIn("22/tcp", template["ports"])
        self.assertEqual("/workspace", template["volumeMountPath"])
        self.assertEqual(
            "ghcr.io/grawthings-beep/comfyui-anima-rmbg-workflow:cuda12.8",
            template["imageName"],
        )
        self.assertEqual([], template["dockerEntrypoint"])
        self.assertEqual([], template["dockerStartCmd"])
        self.assertEqual("/workspace/comfyui", template["env"]["MODEL_ROOT"])
        self.assertEqual("/workspace/huggingface", template["env"]["HF_HOME"])
        self.assertEqual("1", template["env"]["DOWNLOAD_MODELS"])

    def test_dockerfile_uses_runpod_comfyui_base(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("ARG BASE_IMAGE=runpod/comfyui:latest", dockerfile)
        self.assertIn("pip install", dockerfile)
        self.assertIn("U2NET_HOME=/root/.u2net", dockerfile)
        self.assertIn("new_session('isnet-general-use')", dockerfile)
        self.assertIn("ANIMA_LLLITE_REPO", dockerfile)
        self.assertIn("ComfyUI-Anima-LLLite", dockerfile)
        self.assertIn('CMD ["/opt/anima-rmbg/custom_node/runpod/start.sh"]', dockerfile)
        self.assertIn("rembg[cpu]", requirements)
        self.assertIn("transformers", requirements)
        self.assertIn("kornia", requirements)

    def test_start_script_is_docker_first(self):
        script = (ROOT / "runpod" / "start.sh").read_text(encoding="utf-8")

        self.assertTrue(script.startswith("#!/usr/bin/env bash\n"))
        self.assertIn("find_comfyui_dir", script)
        self.assertIn("extra_model_paths.yaml", script)
        self.assertIn("ANIMA_LLLITE_SOURCE", script)
        self.assertIn("anima_single_regional_rmbg_transparent_workflow.json", script)
        self.assertIn("download_models.py", script)
        self.assertNotIn("git clone --depth 1 --branch", script)

    def test_raw_start_command_points_to_baked_script(self):
        raw_command = json.loads(
            (ROOT / "runpod" / "start-command.raw.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual([], raw_command["entrypoint"])
        self.assertEqual(
            ["/opt/anima-rmbg/custom_node/runpod/start.sh"],
            raw_command["cmd"],
        )
        self.assertNotIn("imageName", raw_command)

    def test_base_model_manifest_has_only_required_loras(self):
        manifest = json.loads(
            (ROOT / "config" / "anima-rmbg-models.json").read_text(
                encoding="utf-8"
            )
        )
        lora_paths = [
            entry["path"]
            for entry in manifest["models"]
            if entry["path"].startswith("models/loras/")
        ]

        self.assertEqual(
            lora_paths,
            [
                "models/loras/anima-turbo-lora-v0.2.safetensors",
                "models/loras/anima/pixel-AnimaB_V10-V1-CAME.safetensors",
            ],
        )

        controlnet_paths = [
            entry["path"]
            for entry in manifest["models"]
            if entry["path"].startswith("models/controlnet/")
        ]
        self.assertEqual(
            controlnet_paths,
            ["models/controlnet/anima-lllite-regional-exp-v3.safetensors"],
        )


if __name__ == "__main__":
    unittest.main()
