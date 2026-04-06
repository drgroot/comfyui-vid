#!/bin/bash

# Upload .safetensors files from /ComfyUI/models/loras to the equivalent
# location in the configured rclone remote (e.g. Cloudflare R2 or Backblaze B2).
#
# Usage: ./upload_loras.sh
#
# Required: rclone must be configured (via SECRET_RCLONE_CONFIG env var or
#           an existing /root/.config/rclone/rclone.conf file).
#
# Optional environment variables:
#   RCLONE_REMOTE              - rclone remote name (default: b2)
#   COMFYUI_DIR                - path to ComfyUI installation (default: /ComfyUI)
#   RCLONE_MULTI_THREAD_STREAMS - number of multi-thread streams (default: 8)
#   RCLONE_BUFFER_SIZE         - rclone buffer size (default: 256M)
#   RCLONE_S3_CHUNK_SIZE       - S3 upload chunk size (default: 128M)
#   RCLONE_TRANSFERS           - number of parallel file transfers (default: 4)

set -e

RCLONE_REMOTE="${RCLONE_REMOTE:-b2}"
COMFYUI_DIR="${COMFYUI_DIR:-/ComfyUI}"
LORAS_DIR="${COMFYUI_DIR}/models/loras"
REMOTE_LORAS_PATH="${RCLONE_REMOTE}:comfyui/models/loras"

RCLONE_MULTI_THREAD_STREAMS="${RCLONE_MULTI_THREAD_STREAMS:-8}"
RCLONE_BUFFER_SIZE="${RCLONE_BUFFER_SIZE:-256M}"
RCLONE_S3_CHUNK_SIZE="${RCLONE_S3_CHUNK_SIZE:-128M}"
RCLONE_TRANSFERS="${RCLONE_TRANSFERS:-4}"

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
    --multi-thread-streams="${RCLONE_MULTI_THREAD_STREAMS}" \
    --buffer-size="${RCLONE_BUFFER_SIZE}" \
    --s3-chunk-size="${RCLONE_S3_CHUNK_SIZE}" \
    --transfers="${RCLONE_TRANSFERS}" \
    --fast-list \
    --progress \
    "${LORAS_DIR}" "${REMOTE_LORAS_PATH}"

echo "Upload complete." >&2
