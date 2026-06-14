# ComfyUI Anima Variation Batch

[![CI](https://github.com/grawthings-beep/comfyui-anima-variation-batch/actions/workflows/ci.yml/badge.svg)](https://github.com/grawthings-beep/comfyui-anima-variation-batch/actions/workflows/ci.yml)

`Anima Flexible Variation Batch Sampler` creates several deliberately varied
images from one base prompt in a single queued ComfyUI execution.

It:

- accepts any number of chained variation categories;
- selects one comma-separated option from every category;
- uses every option in a category before reshuffling that category;
- encodes a separate positive prompt for every output;
- assigns an independent sampling seed to every output;
- samples and VAE-decodes sequentially to keep sampling VRAM close to a
  one-image workflow;
- combines the finished images into one IMAGE batch for previewing and saving;
- saves each execution as a PNG folder and one-click downloadable ZIP.

The default is four images per execution. This is sequential generation inside
one ComfyUI node, not a four-image GPU batch. Four outputs take roughly four
times the sampling time of one output.

## Install

From the ComfyUI custom node directory:

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/grawthings-beep/comfyui-anima-variation-batch.git \
  ComfyUI-AnimaVariationBatch
```

Restart ComfyUI, then load:

```text
example_workflows/anima_variation_batch_workflow.json
```

It is also exposed through ComfyUI's workflow templates browser.

## Batch ZIP saving

The example workflow uses `Anima Save Batch ZIP` instead of the standard
`Save Image` node. With `auto_download` enabled, the entire batch downloads
to the PC automatically after generation. The node also keeps a
`Download ZIP` button for manual re-download.

Files are stored in:

```text
output/anima_batches/YYYY-MM-DD/anima_batch_00001/
output/anima_batches/YYYY-MM-DD/anima_batch_00001.zip
```

The ZIP contains every PNG plus `prompt_report.txt` with the selected tags,
expanded prompts, and seeds. PNG workflow metadata is preserved.

For the existing RunPod image, the ComfyUI installation is commonly found at
one of:

```text
/opt/ComfyUI
/workspace/ComfyUI
/workspace/comfyui
```

## Inputs

- `base_prompt`: character, clothes, scene, quality tags, and fixed details.
- `variation_groups`: connect the final `Anima Variation Group` node.
- `count`: outputs per queued execution; defaults to `4`.
- `master_seed`: controls category shuffle order and every derived image seed.
- `steps`, `cfg`, `sampler_name`, `scheduler`, `denoise`: KSampler settings.

Each `Anima Variation Group` contains:

- `category_name`: a report label such as `Angle`, `Expression`, or `Pose`.
- `options`: short prompt tags separated by commas or new lines.
- `previous_groups`: connect the preceding Group node here.

Example:

```text
Angle:
from above, from side, from below, eye level, dutch angle

Expression:
smile, serious, angry, surprised, embarrassed

Pose:
standing, sitting, lying, looking back, arms crossed
```

Connect `Angle -> Expression -> Pose -> Flexible Sampler`. Duplicate the Group
node and connect it to the end to add `Composition`, `Lighting`, `Clothes`, or
any other category. There is no fixed category count.

Keep the connected `Empty Latent Image` batch size at `1`. Use `count` on the
custom node to choose the number of outputs.

Each category acts as an independent shuffle bag. With three angle tags and
eight outputs, all three angles are used once in random order, then reshuffled
and used again. This works even when a category has fewer options than
`count`.

Lines beginning with `#` are ignored. Duplicate options are removed
case-insensitively.

The original two-field `Anima Variation Batch Sampler` remains available for
old workflows.

## Optional character LoRA downloads

`config/anima-loras.json` mirrors the private character LoRAs used by the
RunPod image, including Label and Ark Ranger Black. The repository contains
only download metadata, not model weights.

List available IDs:

```bash
python scripts/download_loras.py --list
```

Download selected LoRAs:

```bash
hf auth login
hf auth whoami
python scripts/download_loras.py \
  --root /workspace/comfyui \
  --id label \
  --id arkrangerblack
```

Omit `--id` to download every listed character LoRA. Files are installed under
`models/loras/anima/`. A successful `hf auth login` is required because the
LoRA repository is private.

## Anima Turbo example

The included workflow is configured as an example for:

- Anima-compatible diffusion model
- Qwen 3 0.6B text encoder
- Qwen Image VAE
- Anima Turbo LoRA
- 8 steps
- 4 outputs

Model filenames are examples. Select the files installed in your own ComfyUI
environment.

## What this does not guarantee

Prompt tags increase diversity but do not provide exact pose or camera
control. Closely related tags can still produce visually similar images.
Control Adapter, ControlNet, pose, edge, or depth conditioning is a separate
tool when specific 2D structure is required.

## License

GPL-3.0-only. See `LICENSE`.

This repository does not distribute Anima or LoRA weights. Check the license of
every model used in your workflow. The official Anima model and derivatives
are restricted to non-commercial use unless a commercial license is obtained.

- [Official Anima model card](https://huggingface.co/circlestone-labs/Anima)
- [ComfyUI](https://github.com/Comfy-Org/ComfyUI)
