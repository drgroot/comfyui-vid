#!/bin/bash

# Symlink files from /workspace/loras into /ComfyUI/models/loras.
#
# Usage: ./link_workspace_loras.sh
#
# Optional environment variables:
#   WORKSPACE_LORAS_DIR - source directory (default: /workspace/loras)
#   COMFYUI_DIR         - path to ComfyUI installation (default: /ComfyUI)

set -euo pipefail

WORKSPACE_LORAS_DIR="${WORKSPACE_LORAS_DIR:-/workspace/loras}"
COMFYUI_DIR="${COMFYUI_DIR:-/ComfyUI}"
TARGET_LORAS_DIR="${COMFYUI_DIR}/models/loras"

if [ ! -d "${WORKSPACE_LORAS_DIR}" ]; then
    echo "Error: source directory not found: ${WORKSPACE_LORAS_DIR}" >&2
    exit 1
fi

mkdir -p "${TARGET_LORAS_DIR}"

shopt -s nullglob

linked_count=0
skipped_count=0

for source_path in "${WORKSPACE_LORAS_DIR}"/*; do
    if [ ! -f "${source_path}" ] && [ ! -L "${source_path}" ]; then
        echo "Skipping non-file entry: ${source_path}" >&2
        skipped_count=$((skipped_count + 1))
        continue
    fi

    target_path="${TARGET_LORAS_DIR}/$(basename "${source_path}")"

    if [ -L "${target_path}" ]; then
        existing_target="$(readlink "${target_path}")"
        if [ "${existing_target}" = "${source_path}" ]; then
            echo "Already linked: ${target_path}" >&2
            continue
        fi
        rm -f "${target_path}"
    elif [ -e "${target_path}" ]; then
        echo "Skipping existing non-symlink target: ${target_path}" >&2
        skipped_count=$((skipped_count + 1))
        continue
    fi

    ln -s "${source_path}" "${target_path}"
    echo "Linked ${target_path} -> ${source_path}" >&2
    linked_count=$((linked_count + 1))
done

echo "Done. linked=${linked_count} skipped=${skipped_count}" >&2
