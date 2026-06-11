# ComfyUI Anima Variation Batch

[![CI](https://github.com/grawthings-beep/comfyui-anima-variation-batch/actions/workflows/ci.yml/badge.svg)](https://github.com/grawthings-beep/comfyui-anima-variation-batch/actions/workflows/ci.yml)

`Anima Variation Batch Sampler` creates several deliberately varied images
from one base prompt in a single queued ComfyUI execution.

It:

- selects unique `shot recipe x expression` combinations;
- encodes a separate positive prompt for every output;
- assigns an independent sampling seed to every output;
- samples and VAE-decodes sequentially to keep sampling VRAM close to a
  one-image workflow;
- combines the finished images into one IMAGE batch for previewing and saving.

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
workflows/anima_variation_batch_workflow.json
```

For the existing RunPod image, the ComfyUI installation is commonly found at
one of:

```text
/opt/ComfyUI
/workspace/ComfyUI
/workspace/comfyui
```

## Inputs

- `base_prompt`: character, clothes, scene, quality tags, and fixed details.
- `shot_recipes`: one camera/composition/pose recipe per line.
- `expressions`: one expression per line.
- `count`: outputs per queued execution; defaults to `4`.
- `master_seed`: controls combination selection and every derived image seed.
- `steps`, `cfg`, `sampler_name`, `scheduler`, `denoise`: KSampler settings.

Keep the connected `Empty Latent Image` batch size at `1`. Use `count` on the
custom node to choose the number of outputs.

There must be at least `count` unique combinations. Eight shot recipes and
eight expressions provide 64 possible combinations.

Lines beginning with `#` are ignored, so recipe lists can contain notes.

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

Prompt recipes increase diversity but do not provide exact pose or camera
control. Closely related recipes can still produce visually similar images.
Control Adapter, ControlNet, pose, edge, or depth conditioning is a separate
tool when specific 2D structure is required.

## License

GPL-3.0-only. See `LICENSE`.

This repository does not distribute Anima or LoRA weights. Check the license of
every model used in your workflow. The official Anima model and derivatives
are restricted to non-commercial use unless a commercial license is obtained.

- [Official Anima model card](https://huggingface.co/circlestone-labs/Anima)
- [ComfyUI](https://github.com/Comfy-Org/ComfyUI)
