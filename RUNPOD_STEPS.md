# RunPod Steps

## 1. Push Repo

Push this repository to GitHub.

## 2. Wait For GHCR Build

Open GitHub Actions and wait for `Build GHCR image`.

Container image:

```text
ghcr.io/grawthings-beep/comfyui-anima-rmbg-workflow:cuda12.8
```

If RunPod cannot pull it, make the GHCR package public.

The GHCR package name intentionally avoids this repository's leading hyphen so
the Docker image reference is valid.

## 3. RunPod Template

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

## 4. Open ComfyUI

Use RunPod Connect port `8188`.

The first boot downloads the model files. Later boots reuse
`/workspace/comfyui/models`.

The workflow defaults to `briaai/RMBG-2.0` for background removal. Make sure the
Hugging Face account behind `HF_TOKEN` has accepted the model terms; the model
cache is reused from `/workspace/huggingface`.

The workflow is installed into ComfyUI's normal Workflows list:

```text
anima_single_rmbg_transparent_workflow.json
```
