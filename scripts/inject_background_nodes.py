#!/usr/bin/env python3
import argparse
import copy
import json
from pathlib import Path


REMOVE_TYPE = "AnimaRemoveBackground"
SAVE_TYPE = "AnimaSaveTransparentBatchZip"


def load_workflow(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def next_id(values):
    return max(values or [0]) + 1


def find_node(nodes, node_type):
    matches = [node for node in nodes if node.get("type") == node_type]
    if not matches:
        raise ValueError(f"workflow has no {node_type} node")
    return matches[-1]


def remove_link(workflow, link_id):
    workflow["links"] = [link for link in workflow["links"] if link[0] != link_id]
    for node in workflow["nodes"]:
        for output in node.get("outputs", []):
            links = output.get("links")
            if links:
                output["links"] = [value for value in links if value != link_id]
        for node_input in node.get("inputs", []):
            if node_input.get("link") == link_id:
                node_input["link"] = None


def node_by_id(workflow, node_id):
    for node in workflow["nodes"]:
        if node["id"] == node_id:
            return node
    raise ValueError(f"unknown node id: {node_id}")


def add_link(workflow, link_id, source_id, source_slot, target_id, target_slot, link_type):
    workflow["links"].append([link_id, source_id, source_slot, target_id, target_slot, link_type])
    source = node_by_id(workflow, source_id)
    target = node_by_id(workflow, target_id)
    source_links = source["outputs"][source_slot].setdefault("links", [])
    if source_links is None:
        source["outputs"][source_slot]["links"] = []
        source_links = source["outputs"][source_slot]["links"]
    source_links.append(link_id)
    target["inputs"][target_slot]["link"] = link_id


def build_remove_node(node_id, order, pos):
    return {
        "id": node_id,
        "type": REMOVE_TYPE,
        "pos": pos,
        "size": [360, 250],
        "flags": {},
        "order": order,
        "mode": 0,
        "inputs": [
            {
                "name": "images",
                "type": "IMAGE",
                "link": None,
            }
        ],
        "outputs": [
            {
                "name": "preview_images",
                "type": "IMAGE",
                "links": [],
            },
            {
                "name": "alpha_masks",
                "type": "MASK",
                "links": [],
            },
        ],
        "properties": {
            "cnr_id": "grawthings-beep-comfyui-anima-rmbg-workflow",
            "ver": "0.1.0",
            "Node name for S&R": REMOVE_TYPE,
        },
        "widgets_values": [
            "rembg",
            "isnet-general-use",
            False,
            240,
            10,
            0,
            34,
            "checker",
        ],
    }


def build_save_node(node_id, order, pos):
    return {
        "id": node_id,
        "type": SAVE_TYPE,
        "pos": pos,
        "size": [360, 130],
        "flags": {},
        "order": order,
        "mode": 0,
        "inputs": [
            {
                "name": "images",
                "type": "IMAGE",
                "link": None,
            },
            {
                "name": "alpha_masks",
                "type": "MASK",
                "link": None,
            },
        ],
        "outputs": [],
        "properties": {
            "cnr_id": "grawthings-beep-comfyui-anima-rmbg-workflow",
            "ver": "0.1.0",
            "Node name for S&R": SAVE_TYPE,
        },
        "widgets_values": [
            "anima_transparent/%year%-%month%-%day%/anima_transparent",
            True,
        ],
    }


def inject(workflow, image_node_id=None, preview_node_id=None):
    workflow = copy.deepcopy(workflow)
    nodes = workflow["nodes"]
    image_node = node_by_id(workflow, image_node_id) if image_node_id else find_node(nodes, "VAEDecode")
    preview_node = (
        node_by_id(workflow, preview_node_id)
        if preview_node_id
        else find_node(nodes, "PreviewImage")
    )

    image_output_slot = 0
    preview_input_slot = 0
    old_preview_link = preview_node["inputs"][preview_input_slot].get("link")
    if old_preview_link is not None:
        remove_link(workflow, old_preview_link)

    ids = [node["id"] for node in workflow["nodes"]]
    link_ids = [link[0] for link in workflow["links"]]
    remove_id = next_id(ids)
    save_id = remove_id + 1
    link_image_to_remove = next_id(link_ids)
    link_preview = link_image_to_remove + 1
    link_save_image = link_image_to_remove + 2
    link_save_mask = link_image_to_remove + 3

    max_order = max(node.get("order", 0) for node in workflow["nodes"])
    x = image_node.get("pos", [0, 0])[0] + 300
    y = image_node.get("pos", [0, 0])[1]
    remove_node = build_remove_node(remove_id, max_order + 1, [x, y])
    save_node = build_save_node(save_id, max_order + 2, [x + 420, y + 170])
    workflow["nodes"].extend([remove_node, save_node])

    add_link(
        workflow,
        link_image_to_remove,
        image_node["id"],
        image_output_slot,
        remove_id,
        0,
        "IMAGE",
    )
    add_link(workflow, link_preview, remove_id, 0, preview_node["id"], preview_input_slot, "IMAGE")
    add_link(workflow, link_save_image, remove_id, 0, save_id, 0, "IMAGE")
    add_link(workflow, link_save_mask, remove_id, 1, save_id, 1, "MASK")

    workflow["last_node_id"] = max(node["id"] for node in workflow["nodes"])
    workflow["last_link_id"] = max(link[0] for link in workflow["links"])
    return workflow


def main():
    parser = argparse.ArgumentParser(
        description="Inject Anima background removal and transparent PNG saving nodes into a ComfyUI workflow."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--image-node-id", type=int)
    parser.add_argument("--preview-node-id", type=int)
    args = parser.parse_args()

    workflow = inject(
        load_workflow(args.input),
        image_node_id=args.image_node_id,
        preview_node_id=args.preview_node_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(workflow, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
