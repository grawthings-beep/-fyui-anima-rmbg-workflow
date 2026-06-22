import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW_PATH = (
    ROOT / "example_workflows" / "anima_variation_batch_workflow.json"
)
TRANSPARENT_WORKFLOW_PATH = (
    ROOT / "example_workflows" / "anima_single_rmbg_transparent_workflow.json"
)
REGIONAL_WORKFLOW_PATH = (
    ROOT / "example_workflows" / "anima_single_regional_rmbg_transparent_workflow.json"
)


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))

    def test_custom_node_is_present(self):
        node_types = {node["type"] for node in self.workflow["nodes"]}
        self.assertIn("AnimaFlexibleVariationBatchSampler", node_types)
        self.assertIn("AnimaVariationGroup", node_types)
        self.assertIn("AnimaSaveBatchZip", node_types)

    def test_node_orders_are_unique(self):
        orders = [node["order"] for node in self.workflow["nodes"]]
        self.assertEqual(len(orders), len(set(orders)))

    def test_example_has_angle_expression_pose_and_composition_groups(self):
        groups = [
            node
            for node in self.workflow["nodes"]
            if node["type"] == "AnimaVariationGroup"
        ]
        self.assertGreaterEqual(len(groups), 4)
        category_names = [node["widgets_values"][0] for node in groups]
        self.assertEqual(
            category_names[:4],
            ["Angle", "Expression", "Pose", "Composition"],
        )

    def test_links_reference_existing_nodes_and_sockets(self):
        nodes = {node["id"]: node for node in self.workflow["nodes"]}
        link_ids = set()

        for link_id, source_id, source_slot, target_id, target_slot, _type in (
            self.workflow["links"]
        ):
            self.assertNotIn(link_id, link_ids)
            link_ids.add(link_id)
            self.assertIn(source_id, nodes)
            self.assertIn(target_id, nodes)
            self.assertLess(source_slot, len(nodes[source_id]["outputs"]))
            self.assertLess(target_slot, len(nodes[target_id]["inputs"]))

    def test_example_uses_only_turbo_lora(self):
        lora_nodes = [
            node
            for node in self.workflow["nodes"]
            if node["type"] == "LoraLoaderModelOnly"
        ]
        self.assertEqual(len(lora_nodes), 1)
        self.assertIn("turbo", lora_nodes[0]["widgets_values"][0].lower())

    def test_prompt_report_is_connected_to_zip_saver(self):
        sampler = next(
            node
            for node in self.workflow["nodes"]
            if node["type"] == "AnimaFlexibleVariationBatchSampler"
        )
        saver = next(
            node
            for node in self.workflow["nodes"]
            if node["type"] == "AnimaSaveBatchZip"
        )
        report_links = sampler["outputs"][1]["links"]
        self.assertEqual(len(report_links), 1)
        link = next(
            item
            for item in self.workflow["links"]
            if item[0] == report_links[0]
        )
        self.assertEqual(link[3:5], [saver["id"], 1])
        self.assertIs(saver["widgets_values"][1], True)


class TransparentWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = json.loads(
            TRANSPARENT_WORKFLOW_PATH.read_text(encoding="utf-8")
        )

    def test_background_nodes_are_present(self):
        node_types = {node["type"] for node in self.workflow["nodes"]}
        self.assertIn("AnimaRemoveBackground", node_types)
        self.assertIn("AnimaSaveTransparentBatchZip", node_types)

    def test_transparent_workflow_uses_only_turbo_and_pixel_loras(self):
        lora_names = [
            node["widgets_values"][0]
            for node in self.workflow["nodes"]
            if node["type"] == "LoraLoaderModelOnly"
        ]
        self.assertEqual(
            lora_names,
            [
                "anima-turbo-lora-v0.2.safetensors",
                "anima/pixel-AnimaB_V10-V1-CAME.safetensors",
            ],
        )

    def test_birefnet_is_default_background_method(self):
        remover = next(
            node
            for node in self.workflow["nodes"]
            if node["type"] == "AnimaRemoveBackground"
        )
        self.assertEqual(
            remover["widgets_values"][:6],
            [
                "birefnet",
                "isnet-general-use",
                "briaai/RMBG-2.0",
                "ZhengPeng7/BiRefNet_HR",
                "PramaLLC/BEN2",
                0,
            ],
        )

    def test_background_model_sessions_are_cached(self):
        source = (ROOT / "nodes.py").read_text(encoding="utf-8")
        self.assertIn("_REMBG_SESSIONS", source)
        self.assertIn("_RMBG2_MODELS", source)
        self.assertIn("_get_rembg_session", source)
        self.assertIn("_get_rmbg2_model", source)

    def test_links_reference_existing_nodes_and_sockets(self):
        nodes = {node["id"]: node for node in self.workflow["nodes"]}
        link_ids = set()

        for link_id, source_id, source_slot, target_id, target_slot, _type in (
            self.workflow["links"]
        ):
            self.assertNotIn(link_id, link_ids)
            link_ids.add(link_id)
            self.assertIn(source_id, nodes)
            self.assertIn(target_id, nodes)
            self.assertLess(source_slot, len(nodes[source_id]["outputs"]))
            self.assertLess(target_slot, len(nodes[target_id]["inputs"]))

    def test_vae_decode_feeds_background_removal(self):
        vae_decode = next(
            node for node in self.workflow["nodes"] if node["type"] == "VAEDecode"
        )
        remover = next(
            node
            for node in self.workflow["nodes"]
            if node["type"] == "AnimaRemoveBackground"
        )
        output_links = vae_decode["outputs"][0]["links"]
        self.assertEqual(len(output_links), 1)
        link = next(
            item
            for item in self.workflow["links"]
            if item[0] == output_links[0]
        )
        self.assertEqual(link[3:5], [remover["id"], 0])

    def test_transparent_saver_receives_image_and_mask(self):
        remover = next(
            node
            for node in self.workflow["nodes"]
            if node["type"] == "AnimaRemoveBackground"
        )
        saver = next(
            node
            for node in self.workflow["nodes"]
            if node["type"] == "AnimaSaveTransparentBatchZip"
        )
        saver_links = [item for item in self.workflow["links"] if item[3] == saver["id"]]
        self.assertEqual(
            sorted((link[1], link[2], link[4], link[5]) for link in saver_links),
            [
                (remover["id"], 0, 0, "IMAGE"),
                (remover["id"], 1, 1, "MASK"),
            ],
        )


class RegionalWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = json.loads(REGIONAL_WORKFLOW_PATH.read_text(encoding="utf-8"))

    def test_regional_control_nodes_are_present(self):
        node_types = {node["type"] for node in self.workflow["nodes"]}
        self.assertIn("AnimaRegionalControlMask", node_types)
        self.assertIn("AnimaLLLiteApply", node_types)
        self.assertIn("AnimaRemoveBackground", node_types)
        self.assertIn("AnimaSaveTransparentBatchZip", node_types)

    def test_links_reference_existing_nodes_and_sockets(self):
        nodes = {node["id"]: node for node in self.workflow["nodes"]}
        link_ids = set()

        for link_id, source_id, source_slot, target_id, target_slot, _type in (
            self.workflow["links"]
        ):
            self.assertNotIn(link_id, link_ids)
            link_ids.add(link_id)
            self.assertIn(source_id, nodes)
            self.assertIn(target_id, nodes)
            self.assertLess(source_slot, len(nodes[source_id]["outputs"]))
            self.assertLess(target_slot, len(nodes[target_id]["inputs"]))

    def test_lllite_uses_regional_controlnet_weight(self):
        lllite = next(
            node for node in self.workflow["nodes"] if node["type"] == "AnimaLLLiteApply"
        )

        self.assertEqual(
            lllite["widgets_values"],
            [
                "anima-lllite-regional-exp-v3.safetensors",
                1,
                0,
                0.55,
                True,
            ],
        )

    def test_regional_mask_feeds_lllite_before_sampler(self):
        mask = next(
            node
            for node in self.workflow["nodes"]
            if node["type"] == "AnimaRegionalControlMask"
        )
        lllite = next(
            node for node in self.workflow["nodes"] if node["type"] == "AnimaLLLiteApply"
        )
        turbo_lora = next(
            node
            for node in self.workflow["nodes"]
            if node["type"] == "LoraLoaderModelOnly"
            and node["widgets_values"][0] == "anima-turbo-lora-v0.2.safetensors"
        )
        sampler = next(
            node for node in self.workflow["nodes"] if node["type"] == "KSampler"
        )

        incoming_to_lllite = [
            link for link in self.workflow["links"] if link[3] == lllite["id"]
        ]
        self.assertEqual(
            sorted((link[1], link[2], link[4], link[5]) for link in incoming_to_lllite),
            [
                (turbo_lora["id"], 0, 0, "MODEL"),
                (mask["id"], 0, 1, "IMAGE"),
            ],
        )

        sampler_model_link = next(
            link for link in self.workflow["links"] if link[0] == sampler["inputs"][0]["link"]
        )
        self.assertEqual(sampler_model_link[1:5], [lllite["id"], 0, sampler["id"], 0])


if __name__ == "__main__":
    unittest.main()
