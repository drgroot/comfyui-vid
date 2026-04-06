#!/bin/bash

# Upload .safetensors files from /ComfyUI/models/loras to the equivalent
# location in Cloudflare S3 using rclone.
#
# Usage: ./upload_loras.sh
#
# Required: rclone must be configured (via SECRET_RCLONE_CONFIG env var or
#           an existing /root/.config/rclone/rclone.conf file).
#
# Optional environment variables:
#   RCLONE_REMOTE      - rclone remote name (default: b2)
#   COMFYUI_DIR        - path to ComfyUI installation (default: /ComfyUI)

set -e

RCLONE_REMOTE="${RCLONE_REMOTE:-b2}"
COMFYUI_DIR="${COMFYUI_DIR:-/ComfyUI}"
LORAS_DIR="${COMFYUI_DIR}/models/loras"
REMOTE_LORAS_PATH="${RCLONE_REMOTE}:comfyui/models/loras"

if [ -n "${SECRET_RCLONE_CONFIG}" ]; then
    mkdir -p /root/.config/rclone
    chmod 700 /root/.config/rclone
    printf '%s' "${SECRET_RCLONE_CONFIG}" > /root/.config/rclone/rclone.conf
    chmod 600 /root/.config/rclone/rclone.conf
fi

if [ ! -f /root/.config/rclone/rclone.conf ]; then
    echo "Error: rclone is not configured. Set SECRET_RCLONE_CONFIG or provide /root/.config/rclone/rclone.conf." >&2
    exit 1
fi

if [ ! -d "${LORAS_DIR}" ]; then
    echo "Error: loras directory not found: ${LORAS_DIR}" >&2
    exit 1
fi

echo "Uploading .safetensors files from ${LORAS_DIR} to ${REMOTE_LORAS_PATH} ..." >&2

rclone copy \
    --include="*.safetensors" \
    --multi-thread-streams=8 \
    --buffer-size=256M \
    --s3-chunk-size=128M \
    --transfers=4 \
    --fast-list \
    --progress \
    "${LORAS_DIR}" "${REMOTE_LORAS_PATH}"

echo "Upload complete." >&2
