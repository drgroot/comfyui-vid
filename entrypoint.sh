#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

COMFYUI_DIR="${COMFYUI_DIR:-/ComfyUI}"
WORKSPACE_COMFYUI_DIR="${WORKSPACE_COMFYUI_DIR:-/workspace/ComfyUI}"
COMFYUI_MODELS_DIR="${COMFYUI_DIR}/models"
WORKSPACE_MODELS_DIR="${WORKSPACE_COMFYUI_DIR}/models"

mkdir -p "$WORKSPACE_MODELS_DIR"/{checkpoints,loras,text_encoders,vae}

if [ -L "$COMFYUI_MODELS_DIR" ]; then
    rm -f "$COMFYUI_MODELS_DIR"
elif [ -d "$COMFYUI_MODELS_DIR" ]; then
    if find "$COMFYUI_MODELS_DIR" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
        cp -a "$COMFYUI_MODELS_DIR"/. "$WORKSPACE_MODELS_DIR"/
    fi
    rm -rf "$COMFYUI_MODELS_DIR"
fi

ln -s "$WORKSPACE_MODELS_DIR" "$COMFYUI_MODELS_DIR"

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

# Start ComfyUI in the background
echo "Starting ComfyUI in the background..."
python3 "$COMFYUI_DIR/main.py" "${comfyui_args[@]}" &

# Wait for ComfyUI to be ready
echo "Waiting for ComfyUI to be ready..."
max_wait=120  # Wait up to 2 minutes
wait_count=0
while [ $wait_count -lt $max_wait ]; do
    if curl -s http://127.0.0.1:8188/ > /dev/null 2>&1; then
        echo "ComfyUI is ready!"
        break
    fi
    echo "Waiting for ComfyUI... ($wait_count/$max_wait)"
    sleep 2
    wait_count=$((wait_count + 2))
done

if [ $wait_count -ge $max_wait ]; then
    echo "Error: ComfyUI failed to start within $max_wait seconds"
    exit 1
fi

# Start the handler in the foreground.
# This script becomes the container's main process.
echo "Starting the handler..."
exec python3 handler.py
