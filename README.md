# ComfyUI Video Image

This repository builds a ComfyUI container focused on the workflows in `basic.json`. The container starts ComfyUI and a small sidecar sync server.

## What It Includes

- ComfyUI
- `ComfyUI-GGUF`
- `ComfyUI-KJNodes`
- `ComfyUI-VideoHelperSuite`
- `ComfyUI-Impact-Pack`
- `ComfyUI-Impact-Subpack`
- `comfyui_segment_anything`
- `ComfyUI_essentials`

These cover the workflows currently referenced in this repo, including Wan image-to-video, T2I, I2I, and SAM-related flows.

## Image Behavior

- The default command launches ComfyUI on `0.0.0.0:8188`
- A sidecar sync server listens on `0.0.0.0:8189` by default
- Models live under `/workspace/ComfyUI/models`
- Outputs are written under `/workspace/comfyui-vid-runs`
- `entrypoint.sh` starts the sync server in the background and then `exec`s ComfyUI

## Build

```bash
docker buildx build --platform linux/amd64 -t comfyui-vid:test .
```

## Run

```bash
docker run --rm \
  --gpus all \
  -p 8188:8188 \
  -p 8189:8189 \
  -v /path/to/workspace:/workspace \
  comfyui-vid:test
```

Then open `http://localhost:8188`.

To fetch files from the `b2` rclone remote into the workspace, call:

```bash
curl -G 'http://localhost:8189/' \
  --data-urlencode 'files=models/checkpoints/foo.safetensors' \
  --data-urlencode 'files=models/vae/bar.safetensors'
```

The sync server:

- Copies from `b2:<path>` into `$WORKSPACE_COMFYUI_DIR/<path>`
- Skips files that already exist locally
- Runs up to 3 copies in parallel by default
- Accepts repeated `files` query parameters, form payloads, or JSON with `{"files": ["..."]}`

Useful environment variables:

- `COMFYUI_SYNC_SERVER_ENABLED=0` disables the sidecar server
- `COMFYUI_SYNC_SERVER_HOST` and `COMFYUI_SYNC_SERVER_PORT` change the bind address
- `COMFYUI_SYNC_MAX_JOBS` changes the parallel copy limit
- `COMFYUI_SYNC_RCLONE_REMOTE` changes the rclone remote name from the default `b2`

## Model Layout

The container expects the usual ComfyUI model directories under `/workspace/ComfyUI/models`, including:

- `checkpoints`
- `clip`
- `diffusion_models`
- `embeddings`
- `loras`
- `text_encoders`
- `upscale_models`
- `vae`

## Files

- `Dockerfile`: image build
- `entrypoint.sh`: container startup
- `basic.json`: reference workflow
- `extra_model_paths.yaml`: ComfyUI model path config

## Notes

- This image requires an NVIDIA GPU at runtime.
- If `sageattention` is installed, the entrypoint can enable `--use-sage-attention`.
- The local build I verified for this repo targets `linux/amd64`.
