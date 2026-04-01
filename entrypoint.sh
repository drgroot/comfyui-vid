#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

if [ -n "${MY_SSH_PUB}" ]; then
    mkdir -p /root/.ssh
    chmod 700 /root/.ssh
    echo "${MY_SSH_PUB}" >> /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
fi

if [ -n "${SECRET_RCLONE_CONFIG}" ]; then
    mkdir -p /root/.config/rclone
    chmod 700 /root/.config/rclone
    printf '%s' "${SECRET_RCLONE_CONFIG}" > /root/.config/rclone/rclone.conf
    chmod 600 /root/.config/rclone/rclone.conf
fi

if [ -f /root/.config/rclone/rclone.conf ] && [ -n "${DOWNLOAD_MODELS}" ]; then
    echo "Downloading models from remote storage..." >&2
    IFS=',' read -ra _model_files <<< "${DOWNLOAD_MODELS}"
    for _model_file in "${_model_files[@]}"; do
        _model_file=$(echo "$_model_file" | xargs)
        [ -z "$_model_file" ] && continue
        _dest_dir="/ComfyUI/models/$(dirname "$_model_file")"
        mkdir -p "$_dest_dir"
        echo "Downloading in background: $_model_file" >&2
        (
            rclone copy \
                --multi-thread-streams=8 \
                --buffer-size=256M \
                --s3-chunk-size=128M \
                --transfers=1 \
                --fast-list \
                "b2:/comfyui/models/$_model_file" "$_dest_dir" || \
            echo "Warning: Failed to download $_model_file" >&2
        ) &
    done
fi

COMFYUI_DIR="${COMFYUI_DIR:-/ComfyUI}"
WORKSPACE_COMFYUI_DIR="${WORKSPACE_COMFYUI_DIR:-/workspace/ComfyUI}"
COMFYUI_MODELS_DIR="${COMFYUI_DIR}/models"
WORKSPACE_MODELS_DIR="${WORKSPACE_COMFYUI_DIR}/models"
COMFYUI_SYNC_SERVER_HOST="${COMFYUI_SYNC_SERVER_HOST:-0.0.0.0}"
COMFYUI_SYNC_SERVER_PORT="${COMFYUI_SYNC_SERVER_PORT:-8189}"
COMFYUI_SYNC_SERVER_ENABLED="${COMFYUI_SYNC_SERVER_ENABLED:-1}"

mkdir -p "$WORKSPACE_MODELS_DIR"/{checkpoints,loras,text_encoders,vae}

# if [ -L "$COMFYUI_MODELS_DIR" ]; then
#     rm -f "$COMFYUI_MODELS_DIR"
# elif [ -d "$COMFYUI_MODELS_DIR" ]; then
#     if find "$COMFYUI_MODELS_DIR" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
#         cp -a "$COMFYUI_MODELS_DIR"/. "$WORKSPACE_MODELS_DIR"/
#     fi
#     rm -rf "$COMFYUI_MODELS_DIR"
# fi

# ln -s "$WORKSPACE_MODELS_DIR" "$COMFYUI_MODELS_DIR"

COMFYUI_RUNS_DIR="${COMFYUI_DIR}/output/comfyui-vid-runs"
WORKSPACE_RUNS_DIR="/workspace/comfyui-vid-runs"

mkdir -p "$WORKSPACE_RUNS_DIR"

if [ -L "$COMFYUI_RUNS_DIR" ]; then
    rm -f "$COMFYUI_RUNS_DIR"
elif [ -d "$COMFYUI_RUNS_DIR" ]; then
    if find "$COMFYUI_RUNS_DIR" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
        cp -a "$COMFYUI_RUNS_DIR"/. "$WORKSPACE_RUNS_DIR"/
    fi
    rm -rf "$COMFYUI_RUNS_DIR"
fi

mkdir -p "${COMFYUI_DIR}/output"
ln -s "$WORKSPACE_RUNS_DIR" "$COMFYUI_RUNS_DIR"

comfyui_args=(--listen)
if [ "${COMFYUI_USE_SAGE_ATTENTION:-auto}" = "auto" ]; then
    if python3 -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('sageattention') else 1)"; then
        comfyui_args+=(--use-sage-attention)
    fi
elif [ "${COMFYUI_USE_SAGE_ATTENTION}" = "1" ] || [ "${COMFYUI_USE_SAGE_ATTENTION}" = "true" ]; then
    comfyui_args+=(--use-sage-attention)
fi

if [ "${COMFYUI_FORCE_CPU:-auto}" = "auto" ]; then
    if ! python3 -c "import torch; raise SystemExit(0 if torch.cuda.is_available() else 1)"; then
        comfyui_args+=(--cpu)
    fi
elif [ "${COMFYUI_FORCE_CPU}" = "1" ] || [ "${COMFYUI_FORCE_CPU}" = "true" ]; then
    comfyui_args+=(--cpu)
fi

if [ "${COMFYUI_SYNC_SERVER_ENABLED}" = "1" ] || [ "${COMFYUI_SYNC_SERVER_ENABLED}" = "true" ]; then
    python3 /workspace_sync_server.py &
    echo "Started workspace sync server on ${COMFYUI_SYNC_SERVER_HOST}:${COMFYUI_SYNC_SERVER_PORT}" >&2
fi

exec python3 "$COMFYUI_DIR/main.py" "${comfyui_args[@]}"
