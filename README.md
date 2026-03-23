# ComfyUI Video Image

This repository builds a ComfyUI container focused on the workflows in `basic.json`. The container just starts ComfyUI.

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
- Models live under `/workspace/ComfyUI/models`
- Outputs are written under `/workspace/comfyui-vid-runs`
- `entrypoint.sh` starts ComfyUI directly

## Build

```bash
docker buildx build --platform linux/amd64 -t comfyui-vid:test .
```

## Run

```bash
docker run --rm \
  --gpus all \
  -p 8188:8188 \
  -v /path/to/workspace:/workspace \
  comfyui-vid:test
```

Then open `http://localhost:8188`.

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
