# RunPod Template

This template follows the same Docker-first layout as
`grawthings-beep/anima-image-runpod`.

The image is based on `runpod/comfyui:latest`. It bakes the Anima RMBG custom
node, background-removal dependency, workflow, and startup/download scripts into
the container. Large model files are downloaded into the persistent RunPod
volume at Pod startup, so later boots reuse `/workspace/comfyui/models`.

## GHCR Image

GitHub Actions builds:

```text
ghcr.io/grawthings-beep/comfyui-anima-rmbg-workflow:cuda12.8
```

The package name intentionally avoids the repository's leading hyphen so it is a
valid Docker image reference.

## Console Settings

Recommended Pod template values:

```text
Container image: ghcr.io/grawthings-beep/comfyui-anima-rmbg-workflow:cuda12.8
Container disk: 40 GB
Volume disk: 100 GB+
Volume mount path: /workspace
Expose HTTP ports: 8188
Container start command: leave empty
```

Environment variables:

```text
PORT=8188
LISTEN=0.0.0.0
WORKSPACE_DIR=/workspace/comfyui
MODEL_ROOT=/workspace/comfyui
HF_HOME=/workspace/huggingface
DOWNLOAD_MODELS=1
RUN_DEP_CHECK=0
HF_TOKEN={{ RUNPOD_SECRET_HF_TOKEN }}
ARIA2_CONNECTIONS=16
ARIA2_SPLITS=16
COMFYUI_ARGS=--reserve-vram 3
```

Keep tokens in RunPod Secrets. Do not paste raw tokens into a public template.
The packaged workflow defaults to `briaai/RMBG-2.0`; make sure the Hugging Face
account behind `HF_TOKEN` has accepted the model terms.

## Model Layout

Startup downloads only the model files used by the packaged transparent RMBG
workflow:

```text
/workspace/comfyui/models/diffusion_models/waiANIMA_v10Base10.safetensors
/workspace/comfyui/models/text_encoders/qwen_3_06b_base.safetensors
/workspace/comfyui/models/vae/qwen_image_vae.safetensors
/workspace/comfyui/models/loras/anima-turbo-lora-v0.2.safetensors
/workspace/comfyui/models/loras/anima/pixel-AnimaB_V10-V1-CAME.safetensors
```

The only LoRAs in the base manifest are:

```text
anima-turbo-lora-v0.2.safetensors
anima/pixel-AnimaB_V10-V1-CAME.safetensors
```

## ComfyUI

Open RunPod Connect for port `8188`.

The startup script installs this custom node into ComfyUI and places the
workflow in ComfyUI's normal Workflows list:

```text
anima_single_rmbg_transparent_workflow.json
```
