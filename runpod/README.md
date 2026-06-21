# RunPod Template

Use this with a RunPod image or template that already contains ComfyUI. The
startup script installs this repository into `custom_nodes`, installs the Python
requirements, and starts ComfyUI on port `8188`.

## Console Settings

Recommended Pod template values:

```text
Container image: a ComfyUI-capable image you already use
Volume mount path: /workspace
Expose HTTP ports: 8188
Expose TCP ports: 22
Container start command:
bash -lc 'curl -fsSL https://raw.githubusercontent.com/grawthings-beep/-fyui-anima-rmbg-workflow/main/runpod/start.sh -o /tmp/anima-rmbg-start.sh && bash /tmp/anima-rmbg-start.sh'
```

If the image keeps ComfyUI somewhere other than `/workspace/ComfyUI`, set:

```text
COMFYUI_ROOT=/path/to/ComfyUI
```

After the Pod starts, open:

```text
https://[POD_ID]-8188.proxy.runpod.net
```

Then load:

```text
custom_nodes/ComfyUI-AnimaRmbgWorkflow/example_workflows/anima_single_rmbg_transparent_workflow.json
```

## Template JSON

`pod-template.example.json` mirrors RunPod's REST template fields. Replace
`YOUR_COMFYUI_IMAGE:TAG` with the actual ComfyUI image you want to run before
creating the template.

## Environment Variables

`template.env.example` contains the supported variables. The important ones are:

- `COMFYUI_ROOT`: set only when auto-detection cannot find ComfyUI.
- `START_COMFYUI`: `1` starts `main.py --listen 0.0.0.0 --port 8188`.
- `RUN_BASE_START`: starts `/start.sh` from the base image in the background.
- `INSTALL_WORKFLOW_ASSETS`: installs only the models and LoRAs referenced by
  the packaged workflow.
- `WORKFLOW_ASSET_SOURCE_ROOT`: copies those assets from another ComfyUI root.
- `HF_TOKEN`: use a RunPod secret when downloading from Hugging Face.

Keep `INSTALL_WORKFLOW_ASSETS=0` until the missing URLs in
`config/workflow-assets.json` are filled or the assets are already available in
the Pod volume. The original workflow references local model filenames, and only
the `pixel-came` LoRA currently has a known public URL in this repo.
