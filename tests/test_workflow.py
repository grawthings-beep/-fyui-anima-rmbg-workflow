import json
import unittest
from pathlib import Path


WORKFLOW_PATH = (
    Path(__file__).parents[1]
    / "example_workflows"
    / "anima_variation_batch_workflow.json"
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


if __name__ == "__main__":
    unittest.main()
