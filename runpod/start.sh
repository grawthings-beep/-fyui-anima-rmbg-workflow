#!/usr/bin/env bash
set -Eeuo pipefail

log() {
  printf '[anima-rmbg] %s\n' "$*"
}

die() {
  log "ERROR: $*"
  exit 1
}

is_truthy() {
  case "${1:-}" in
    1 | true | TRUE | yes | YES | on | ON) return 0 ;;
    *) return 1 ;;
  esac
}

find_comfyui_root() {
  if [ -n "${COMFYUI_ROOT:-}" ]; then
    [ -f "$COMFYUI_ROOT/main.py" ] && printf '%s\n' "$COMFYUI_ROOT" && return 0
    return 1
  fi

  for candidate in \
    /workspace/ComfyUI \
    /workspace/comfyui \
    /workspace/ComfyUI_windows_portable/ComfyUI \
    /opt/ComfyUI \
    /app/ComfyUI \
    /comfyui
  do
    [ -f "$candidate/main.py" ] && printf '%s\n' "$candidate" && return 0
  done

  return 1
}

find_python() {
  for candidate in \
    "$COMFYUI_ROOT/venv/bin/python" \
    "$COMFYUI_ROOT/.venv/bin/python" \
    /opt/conda/bin/python
  do
    [ -x "$candidate" ] && printf '%s\n' "$candidate" && return 0
  done

  command -v python3 && return 0
  command -v python && return 0
  return 1
}

REPO_URL="${REPO_URL:-https://github.com/grawthings-beep/-fyui-anima-rmbg-workflow.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
CUSTOM_NODE_DIR_NAME="${CUSTOM_NODE_DIR_NAME:-ComfyUI-AnimaRmbgWorkflow}"
COMFYUI_PORT="${COMFYUI_PORT:-8188}"

if ! COMFYUI_ROOT_RESOLVED="$(find_comfyui_root)"; then
  die "ComfyUI root was not found. Set COMFYUI_ROOT to the directory that contains main.py."
fi
export COMFYUI_ROOT="$COMFYUI_ROOT_RESOLVED"

if ! PYTHON="$(find_python)"; then
  die "Python was not found in the ComfyUI environment."
fi
export PATH="$(dirname "$PYTHON"):$PATH"

CUSTOM_NODES_DIR="$COMFYUI_ROOT/custom_nodes"
TARGET_DIR="$CUSTOM_NODES_DIR/$CUSTOM_NODE_DIR_NAME"

log "ComfyUI root: $COMFYUI_ROOT"
log "Python: $PYTHON"
mkdir -p "$CUSTOM_NODES_DIR"

if [ -d "$TARGET_DIR/.git" ]; then
  log "Custom node already exists: $TARGET_DIR"
  if is_truthy "${UPDATE_REPO:-1}"; then
    if git -C "$TARGET_DIR" fetch --depth 1 origin "$REPO_BRANCH" \
      && { git -C "$TARGET_DIR" checkout "$REPO_BRANCH" 2>/dev/null || git -C "$TARGET_DIR" checkout -B "$REPO_BRANCH" "origin/$REPO_BRANCH"; } \
      && git -C "$TARGET_DIR" merge --ff-only "origin/$REPO_BRANCH"
    then
      log "Updated custom node repo to origin/$REPO_BRANCH"
    else
      log "Could not fast-forward existing repo; continuing with the current checkout"
    fi
  fi
elif [ -e "$TARGET_DIR" ]; then
  log "Target directory exists but is not a git checkout: $TARGET_DIR"
else
  log "Cloning custom node repo"
  git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$TARGET_DIR"
fi

if is_truthy "${INSTALL_NODE_REQUIREMENTS:-1}"; then
  log "Installing custom node Python requirements"
  "$PYTHON" -m pip install --upgrade pip
  "$PYTHON" -m pip install -r "$TARGET_DIR/requirements.txt"
  "$PYTHON" -m pip install "huggingface_hub>=0.23"
fi

if [ -n "${HF_TOKEN:-}" ] && command -v hf >/dev/null 2>&1; then
  log "Configuring Hugging Face token from HF_TOKEN"
  hf auth login --token "$HF_TOKEN" --add-to-git-credential >/dev/null 2>&1 || true
fi

if is_truthy "${INSTALL_WORKFLOW_ASSETS:-0}"; then
  log "Installing workflow assets"
  asset_args=(--root "$COMFYUI_ROOT")
  if [ -n "${WORKFLOW_ASSET_SOURCE_ROOT:-}" ]; then
    asset_args+=(--source-root "$WORKFLOW_ASSET_SOURCE_ROOT")
  fi

  if "$PYTHON" "$TARGET_DIR/scripts/download_workflow_assets.py" "${asset_args[@]}"; then
    log "Workflow assets installed"
  elif is_truthy "${ALLOW_MISSING_WORKFLOW_ASSETS:-0}"; then
    log "Workflow asset install failed, but ALLOW_MISSING_WORKFLOW_ASSETS=1 is set"
  else
    die "Workflow asset install failed. Use WORKFLOW_ASSET_SOURCE_ROOT or fill missing URLs in config/workflow-assets.json."
  fi
else
  log "Workflow asset auto-install is disabled. Required files:"
  "$PYTHON" "$TARGET_DIR/scripts/download_workflow_assets.py" --list || true
fi

if is_truthy "${RUN_BASE_START:-0}" && [ -x /start.sh ]; then
  log "Starting base image /start.sh in the background"
  /start.sh &
  sleep "${BASE_START_DELAY:-2}"
fi

if is_truthy "${START_COMFYUI:-1}"; then
  log "Starting ComfyUI on 0.0.0.0:$COMFYUI_PORT"
  cd "$COMFYUI_ROOT"
  exec "$PYTHON" main.py --listen 0.0.0.0 --port "$COMFYUI_PORT"
fi

log "Setup complete. START_COMFYUI=0, keeping the pod alive."
tail -f /dev/null
