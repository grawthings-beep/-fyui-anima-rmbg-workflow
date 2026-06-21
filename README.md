# ComfyUI Anima RMBG Workflow

ComfyUI custom nodes and workflows for generating Anima pixel-style sprites,
removing the background, and saving transparent PNG batches.

This repo is based on `comfyui-anima-variation-batch`, with two added nodes:

- `Anima Remove Background`
- `Anima Save Transparent Batch ZIP`

The packaged workflow is:

```text
example_workflows/anima_single_rmbg_transparent_workflow.json
```

It is configured from the supplied workflow and adds:

```text
VAEDecode
-> Anima Remove Background
-> PreviewImage
-> Anima Save Transparent Batch ZIP
```

The preview image is composited over a checkerboard. The saved PNG files use a
real alpha channel.

## Install

From the ComfyUI custom node directory:

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/grawthings-beep/-fyui-anima-rmbg-workflow.git \
  ComfyUI-AnimaRmbgWorkflow
```

Install optional background-removal dependencies:

```bash
cd ComfyUI-AnimaRmbgWorkflow
pip install -r requirements.txt
```

Restart ComfyUI, then load:

```text
example_workflows/anima_single_rmbg_transparent_workflow.json
```

## Background Removal

`Anima Remove Background` has two methods:

- `rembg`: AI background removal. Requires `rembg` from `requirements.txt`.
- `edge_connected_chroma`: removes only corner-color background connected to the image edges.

For pixel sprites, start with:

```text
method: rembg
rembg_model: isnet-general-use
alpha_matting: false
erode_size: 0
preview_background: checker
```

If the mask is too soft or eats pixel details, try:

```text
method: edge_connected_chroma
edge_tolerance: 20-40
```

That method is only reliable when the generated image has a simple solid-ish
background.

## Output

`Anima Save Transparent Batch ZIP` writes:

```text
output/anima_transparent/YYYY-MM-DD/anima_transparent_00001/image_01.png
output/anima_transparent/YYYY-MM-DD/anima_transparent_00001.zip
```

The PNGs contain RGBA transparency. The ZIP is suitable for moving generated
sprites into a downstream animation pipeline.

## Workflow Assets

This repo includes a workflow-specific asset manifest:

```text
config/workflow-assets.json
```

It lists only the files used by the packaged workflow:

- `waiANIMA_v10Base10.safetensors`
- `qwen_3_06b_base.safetensors`
- `qwen_image_vae.safetensors`
- `anima-turbo-lora-v0.2.safetensors`
- `anima/pixel-AnimaB_V10-V1-CAME.safetensors`
- `anima/skintextureV1.safetensors`

List them:

```bash
python scripts/download_workflow_assets.py --list
```

Install into a ComfyUI root:

```bash
hf auth login
python scripts/download_workflow_assets.py --root /workspace/comfyui
```

If the files already exist in another ComfyUI install, copy only these workflow
assets from it:

```bash
python scripts/download_workflow_assets.py \
  --root /workspace/comfyui \
  --source-root /path/to/existing/ComfyUI
```

Known limitation: most model URLs in `config/workflow-assets.json` are left as
`null` because the supplied workflow references local filenames and the original
repo only contained a public URL for `pixel-came`. Fill in the remaining URLs
when their source repositories are known, or use `--source-root` to copy them
from an existing ComfyUI install.

## Regenerate The Workflow

To inject the background-removal nodes into another ComfyUI UI workflow:

```bash
python scripts/inject_background_nodes.py input_workflow.json output_workflow.json
```

By default it connects the last `VAEDecode` to the last `PreviewImage`.

## License

GPL-3.0-only. See `LICENSE`.

This repository does not distribute Anima, Qwen, RMBG, or LoRA weights. Check
the license of every model used in your workflow. The official Anima model and
derivatives may be restricted to non-commercial use unless a commercial license
is obtained.
