# RunPod Template

Use this with RunPod's PyTorch image or a ComfyUI image you already trust. The
startup script installs ComfyUI when needed, installs this repository into
`custom_nodes`, installs the Python requirements, and starts ComfyUI on port
`8188`.

## Console Settings

Recommended Pod template values:

```text
Container image: runpod/pytorch:1.0.7-cu1290-torch280-ubuntu2204
Volume mount path: /workspace
Expose HTTP ports: 8188
Expose TCP ports: 22
Container start command:
bash -lc 'curl -fsSL https://raw.githubusercontent.com/grawthings-beep/-fyui-anima-rmbg-workflow/main/runpod/start.sh -o /tmp/anima-rmbg-start.sh && bash /tmp/anima-rmbg-start.sh'
```

If you are editing only the container start command in RunPod's Raw Editor, use:

```json
{
  "entrypoint": [
    "bash",
    "-lc"
  ],
  "cmd": [
    "curl -fsSL https://raw.githubusercontent.com/grawthings-beep/-fyui-anima-rmbg-workflow/main/runpod/start.sh -o /tmp/anima-rmbg-start.sh && bash /tmp/anima-rmbg-start.sh"
  ]
}
```

This short JSON is also available at:

```text
runpod/start-command.raw.json
```

If the image keeps ComfyUI somewhere other than `/workspace/ComfyUI`, set:

```text
COMFYUI_ROOT=/path/to/ComfyUI
```

If the image already has ComfyUI and you do not want the script to install or
update it, set:

```text
INSTALL_COMFYUI=0
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

`pod-template.example.json` mirrors RunPod's REST template fields for creating
the entire template through the API. It is longer than the Start Command Raw
Editor JSON. It uses `runpod/pytorch:1.0.7-cu1290-torch280-ubuntu2204`; you can
replace `imageName` with a ComfyUI image you already use.

## Environment Variables

`template.env.example` contains the supported variables. The important ones are:

- `COMFYUI_ROOT`: set only when auto-detection cannot find ComfyUI.
- `INSTALL_COMFYUI`: `1` clones ComfyUI into `/workspace/ComfyUI` when missing.
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
