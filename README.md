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
- `ComfyUI_smZNodes` (for `CLIP Text Encode++`)
- `ComfyUI-LTXVideo` (official Lightricks LTX 2.3/2.5 workflow and utility nodes)

These cover the workflows currently referenced in this repo, including Wan and LTX image-to-video, T2I, I2I, and SAM-related flows. Current ComfyUI core supplies the model nodes for FLUX.2 (including klein 9B), Krea 2, and LTX 2.x; no separate custom-node packages are required for those base model loaders.

## Image Behavior

- The default command launches ComfyUI on `0.0.0.0:8188`
- A sidecar sync server listens on `0.0.0.0:8189` by default
- Models live under `/ComfyUI/models`
- Outputs are written under `/ComfyUI/output`
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

To fetch files from the `b2` rclone remote into ComfyUI's model directory, call:

```bash
curl -G 'http://localhost:8189/' \
  --data-urlencode 'files=checkpoints/foo.safetensors' \
  --data-urlencode 'files=vae/bar.safetensors'
```

The sync server:

- Copies from `b2:<path>` into `/ComfyUI/models/<path>`
- Skips files that already exist locally
- Runs up to 3 copies in parallel by default
- Accepts repeated `files` query parameters, form payloads, or JSON with `{"files": ["..."]}`

Useful environment variables:

- `COMFYUI_SYNC_SERVER_ENABLED=0` disables the sidecar server
- `COMFYUI_SYNC_SERVER_HOST` and `COMFYUI_SYNC_SERVER_PORT` change the bind address
- `COMFYUI_SYNC_MAX_JOBS` changes the parallel copy limit
- `COMFYUI_SYNC_RCLONE_REMOTE` changes the rclone remote name from the default `b2`

### Startup model downloads

Set `SECRET_RCLONE_CONFIG` to the contents of an rclone configuration and set `DOWNLOAD_MODELS` to a comma- or newline-separated list of model paths relative to `/ComfyUI/models`. `COMFYUI_SYNC_RCLONE_REMOTE` selects the rclone remote and defaults to `b2`.

For example:

```bash
docker run --rm --gpus all \
  -e SECRET_RCLONE_CONFIG="$(<rclone.conf)" \
  -e COMFYUI_SYNC_RCLONE_REMOTE=b2 \
  -e DOWNLOAD_MODELS=$'checkpoints/model.safetensors\nvae/model-vae.safetensors\nloras/style.safetensors' \
  comfyui-vid:test
```

At startup, each entry is copied from `${COMFYUI_SYNC_RCLONE_REMOTE:-b2}:<path>` to `/ComfyUI/models/<path>`—`b2:<path>` when the default remote is used. Downloads begin in the background, so ComfyUI starts immediately; wait for a model's transfer to finish before running a workflow that needs it.

## Notes

- This image requires an NVIDIA GPU at runtime.
- If `sageattention` is installed, the entrypoint can enable `--use-sage-attention`.
- The local build I verified for this repo targets `linux/amd64`.
