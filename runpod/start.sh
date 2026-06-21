#!/usr/bin/env bash
set -Eeuo pipefail

find_python_bin() {
  command -v python || command -v python3 || true
}

find_comfyui_dir() {
  if [[ -n "${COMFYUI_DIR:-}" && -f "${COMFYUI_DIR}/main.py" ]]; then
    printf '%s\n' "${COMFYUI_DIR}"
    return 0
  fi

  for candidate in \
    /opt/ComfyUI \
    /workspace/ComfyUI \
    /workspace/comfyui \
    /comfyui \
    /ComfyUI \
    /app/ComfyUI; do
    if [[ -f "${candidate}/main.py" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  local found_main
  found_main="$(find /opt /workspace /app /comfyui /ComfyUI -maxdepth 4 -type f -name main.py 2>/dev/null | head -n 1 || true)"
  if [[ -n "${found_main}" ]]; then
    dirname "${found_main}"
    return 0
  fi

  return 1
}

COMFYUI_DIR="$(find_comfyui_dir)" || {
  echo "ERROR: could not find ComfyUI main.py. Set COMFYUI_DIR explicitly." >&2
  exit 2
}

PYTHON_BIN="$(find_python_bin)" || {
  echo "ERROR: neither python nor python3 was found in PATH." >&2
  exit 2
}

CUSTOM_NODE_SOURCE="${CUSTOM_NODE_SOURCE:-/opt/anima-rmbg/custom_node}"
CUSTOM_NODE_DIR_NAME="${CUSTOM_NODE_DIR_NAME:-ComfyUI-AnimaRmbgWorkflow}"
CUSTOM_NODE_TARGET="${COMFYUI_DIR}/custom_nodes/${CUSTOM_NODE_DIR_NAME}"
COMFYUI_WORKFLOW_DIR="${COMFYUI_WORKFLOW_DIR:-${COMFYUI_DIR}/user/default/workflows}"

if [[ "${INSTALL_CUSTOM_NODE:-1}" == "1" ]]; then
  if [[ ! -f "${CUSTOM_NODE_SOURCE}/__init__.py" ]]; then
    echo "ERROR: custom node source was not found: ${CUSTOM_NODE_SOURCE}" >&2
    exit 2
  fi
  echo "Installing Anima RMBG custom node into ${CUSTOM_NODE_TARGET}..."
  rm -rf "${CUSTOM_NODE_TARGET}"
  mkdir -p "${CUSTOM_NODE_TARGET}"
  cp -a "${CUSTOM_NODE_SOURCE}/." "${CUSTOM_NODE_TARGET}/"

  WORKFLOW_SOURCE="${CUSTOM_NODE_TARGET}/example_workflows/anima_single_rmbg_transparent_workflow.json"
  if [[ -f "${WORKFLOW_SOURCE}" ]]; then
    mkdir -p "${COMFYUI_WORKFLOW_DIR}"
    cp "${WORKFLOW_SOURCE}" \
       "${COMFYUI_WORKFLOW_DIR}/anima_single_rmbg_transparent_workflow.json"
    echo "Installed transparent RMBG workflow in ${COMFYUI_WORKFLOW_DIR}."
  else
    echo "WARN: transparent RMBG workflow was not found at ${WORKFLOW_SOURCE}."
  fi
fi

WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace/comfyui}"
MODEL_ROOT="${MODEL_ROOT:-${WORKSPACE_DIR}}"
CONFIG_DIR="${CONFIG_DIR:-/workspace/config}"
MODEL_MANIFEST="${MODEL_MANIFEST:-${CONFIG_DIR}/anima-rmbg-models.json}"
EXTRA_MODEL_MANIFEST="${EXTRA_MODEL_MANIFEST:-${CONFIG_DIR}/extra-anima-rmbg-models.json}"
HF_HOME="${HF_HOME:-/workspace/huggingface}"
PORT="${PORT:-8188}"
LISTEN="${LISTEN:-0.0.0.0}"
export HF_HOME

mkdir -p "${WORKSPACE_DIR}/input" \
         "${WORKSPACE_DIR}/output" \
         "${MODEL_ROOT}/models/checkpoints" \
         "${MODEL_ROOT}/models/clip" \
         "${MODEL_ROOT}/models/clip_vision" \
         "${MODEL_ROOT}/models/configs" \
         "${MODEL_ROOT}/models/controlnet" \
         "${MODEL_ROOT}/models/diffusion_models" \
         "${MODEL_ROOT}/models/embeddings" \
         "${MODEL_ROOT}/models/loras/anima" \
         "${MODEL_ROOT}/models/text_encoders" \
         "${MODEL_ROOT}/models/unet" \
         "${MODEL_ROOT}/models/upscale_models" \
         "${MODEL_ROOT}/models/vae" \
         "${MODEL_ROOT}/models/vae_approx" \
         "${CONFIG_DIR}" \
         "${HF_HOME}"

write_extra_model_paths() {
  local target="$1"
  cat > "${target}" <<YAML
workspace:
  base_path: ${MODEL_ROOT}
  checkpoints: models/checkpoints/
  clip: models/clip/
  clip_vision: models/clip_vision/
  configs: models/configs/
  controlnet: models/controlnet/
  diffusion_models: models/diffusion_models/
  embeddings: models/embeddings/
  loras: models/loras/
  text_encoders: models/text_encoders/
  unet: models/unet/
  upscale_models: models/upscale_models/
  vae: models/vae/
  vae_approx: models/vae_approx/
YAML
}

write_extra_model_paths "${COMFYUI_DIR}/extra_model_paths.yaml"
write_extra_model_paths "${COMFYUI_DIR}/extra_model_paths.yml"

if [[ -n "${MODEL_MANIFEST_JSON:-}" ]]; then
  printf '%s' "${MODEL_MANIFEST_JSON}" > "${MODEL_MANIFEST}"
elif [[ -n "${MODEL_MANIFEST_URL:-}" ]]; then
  "${PYTHON_BIN}" - "${MODEL_MANIFEST_URL}" "${MODEL_MANIFEST}" <<'PY'
import pathlib
import sys
import urllib.request

url, output = sys.argv[1], pathlib.Path(sys.argv[2])
output.parent.mkdir(parents=True, exist_ok=True)
request = urllib.request.Request(url, headers={"User-Agent": "runpod-anima-rmbg-template"})
with urllib.request.urlopen(request, timeout=60) as response:
    output.write_bytes(response.read())
PY
elif [[ ! -f "${MODEL_MANIFEST}" && -f "${CUSTOM_NODE_TARGET}/config/anima-rmbg-models.json" ]]; then
  cp "${CUSTOM_NODE_TARGET}/config/anima-rmbg-models.json" "${MODEL_MANIFEST}"
fi

if [[ -n "${EXTRA_MODEL_MANIFEST_JSON:-}" ]]; then
  printf '%s' "${EXTRA_MODEL_MANIFEST_JSON}" > "${EXTRA_MODEL_MANIFEST}"
elif [[ -n "${EXTRA_MODEL_MANIFEST_URL:-}" ]]; then
  "${PYTHON_BIN}" - "${EXTRA_MODEL_MANIFEST_URL}" "${EXTRA_MODEL_MANIFEST}" <<'PY'
import pathlib
import sys
import urllib.request

url, output = sys.argv[1], pathlib.Path(sys.argv[2])
output.parent.mkdir(parents=True, exist_ok=True)
request = urllib.request.Request(url, headers={"User-Agent": "runpod-anima-rmbg-template"})
with urllib.request.urlopen(request, timeout=60) as response:
    output.write_bytes(response.read())
PY
fi

if [[ "${DOWNLOAD_MODELS:-1}" == "1" ]]; then
  if [[ -f "${MODEL_MANIFEST}" ]]; then
    "${PYTHON_BIN}" "${CUSTOM_NODE_TARGET}/scripts/download_models.py" \
      --manifest "${MODEL_MANIFEST}" \
      --root "${MODEL_ROOT}"
  else
    echo "No base model manifest found at ${MODEL_MANIFEST}."
  fi
  if [[ -f "${EXTRA_MODEL_MANIFEST}" ]]; then
    "${PYTHON_BIN}" "${CUSTOM_NODE_TARGET}/scripts/download_models.py" \
      --manifest "${EXTRA_MODEL_MANIFEST}" \
      --root "${MODEL_ROOT}"
  fi
else
  echo "Skipping model downloads."
fi

if [[ "${RUN_DEP_CHECK:-0}" == "1" ]]; then
  "${PYTHON_BIN}" "${CUSTOM_NODE_TARGET}/scripts/check_env.py" \
    --comfyui-dir "${COMFYUI_DIR}" \
    --model-root "${MODEL_ROOT}"
fi

cd "${COMFYUI_DIR}"
exec "${PYTHON_BIN}" main.py \
  --listen "${LISTEN}" \
  --port "${PORT}" \
  --enable-cors-header "${COMFYUI_CORS_ORIGIN:-*}" \
  --input-directory "${WORKSPACE_DIR}/input" \
  --output-directory "${WORKSPACE_DIR}/output" \
  ${COMFYUI_ARGS:-}
