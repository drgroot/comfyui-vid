# Wan2.2 RunPod Serverless Worker

[![Runpod](https://api.runpod.io/badge/drgroot/comfyui-vid)](https://console.runpod.io/hub/drgroot/comfyui-vid)

This repository packages a ComfyUI-based Wan2.2 image-to-video workflow as a RunPod serverless worker.

## Payload

The worker now accepts this `input` shape:

```json
{
  "input": {
    "tasks": [
      {
        "prompts": [
          ["running man, grab the gun", "blurry, low quality, distorted"],
          ["the man keeps running toward the camera", "blurry, low quality, distorted", 97]
        ],
        "image_path": "/workspace/input/example_image.png",
        "ouput_video": "/workspace/output/final/video.mp4",
      },
    ],
    "seed": 2025,
    "frame_rate": 24,
    "sampler": "euler",
    "steps": 4,
    "models": {
      "vae": "/workspace/ComfyUI/models/vae/wan_2.1_vae.safetensors",
      "clip": "/workspace/ComfyUI/models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
      "wan": {
        "high": "/workspace/ComfyUI/models/checkpoints/wan22EnhancedNSFWSVICamera_nolightningSVICfQ8H.gguf",
        "low": "/workspace/ComfyUI/models/checkpoints/wan22EnhancedNSFWSVICamera_nolightningSVICfQ8L.gguf"
      },
      "loras": [
        {
          "high": "/workspace/ComfyUI/models/loras/SVI_v2_PRO_Wan2.2-I2V-A14B_HIGH_lora_rank_128_fp16.safetensors",
          "low": "/workspace/ComfyUI/models/loras/SVI_v2_PRO_Wan2.2-I2V-A14B_LOW_lora_rank_128_fp16.safetensors",
          "high_weight": 1.0,
          "low_weight": 1.0
        },
        {
          "high": "/workspace/ComfyUI/models/loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors",
          "low": "/workspace/ComfyUI/models/loras/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors",
          "high_weight": 1.0,
          "low_weight": 1.0
        }
      ]
    }
  }
}
```

## Field Notes

- `prompts` is required and must be a non-empty list.
- Each `prompts` item can be `[positive, negative]` or `[positive, negative, length]`.
- The optional third value sets `length` on `WanImageToVideoSVIPro` for that stage.
- If the third value is omitted, the stage length defaults to `81`.
- `image_path` is the canonical image input for this payload.
- `ouput_video` is the requested save path for the generated video. Parent folders are created automatically.
- Generated videos are always written as `.mp4`. If you pass a different extension, the worker rewrites it to `.mp4`.
- `output_video` is also accepted as a compatibility alias, but `ouput_video` matches the current payload contract.
- `seed` defaults to `2025`.
- `frame_rate` updates the `VHS_VideoCombine` node.
- `sampler` updates the `KSamplerSelect` node.
- `steps` updates the `BasicScheduler` node.
- Model paths are normalized to the names ComfyUI expects under `models/`.

## Models

### `models.vae`

- String path to the VAE file.

### `models.clip`

- String path to the text encoder file.

### `models.wan`

- `high`: high UNet / checkpoint path.
- `low`: low UNet / checkpoint path.

### `models.loras`

- List of LoRA pairs applied in order.
- Each item must include `high` and `low`.
- `high_weight` and `low_weight` default to `1.0` when omitted.
- An empty list is allowed if you want to run without any LoRAs.

## Response

### Saved video response

When `ouput_video` is provided, the worker copies the generated video to that exact path and returns:

```json
{
  "ouput_video": "/workspace/output/final/video.mp4",
  "output_video": "/workspace/output/final/video.mp4"
}
```

### Legacy response

If no output path is provided, the worker keeps the previous behavior and returns Base64 video data:

```json
{
  "video": "...base64..."
}
```

## Example Request

```bash
curl -X POST "$RUNPOD_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -d '{
    "input": {
      "prompts": [
        ["running man, grab the gun", "blurry, low quality, distorted"],
        ["the man turns and runs away from camera", "blurry, low quality, distorted", 97]
      ],
      "image_path": "/workspace/example_image.png",
      "ouput_video": "/workspace/results/run_01/output.mp4",
      "seed": 2025,
      "frame_rate": 24,
      "sampler": "euler",
      "steps": 4,
      "models": {
        "vae": "/workspace/ComfyUI/models/vae/wan_2.1_vae.safetensors",
        "clip": "/workspace/ComfyUI/models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "wan": {
          "high": "/workspace/ComfyUI/models/checkpoints/wan22EnhancedNSFWSVICamera_nolightningSVICfQ8H.gguf",
          "low": "/workspace/ComfyUI/models/checkpoints/wan22EnhancedNSFWSVICamera_nolightningSVICfQ8L.gguf"
        },
        "loras": [
          {
            "high": "/workspace/ComfyUI/models/loras/SVI_v2_PRO_Wan2.2-I2V-A14B_HIGH_lora_rank_128_fp16.safetensors",
            "low": "/workspace/ComfyUI/models/loras/SVI_v2_PRO_Wan2.2-I2V-A14B_LOW_lora_rank_128_fp16.safetensors",
            "high_weight": 1.0,
            "low_weight": 1.0
          },
          {
            "high": "/workspace/ComfyUI/models/loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors",
            "low": "/workspace/ComfyUI/models/loras/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors",
            "high_weight": 1.0,
            "low_weight": 1.0
          }
        ]
      }
    }
  }'
```

## Compatibility

- `image_url` and `image_base64` are still supported by `handler.py` for older callers.
- If `models` is omitted, the worker falls back to the defaults stored in `basic.json`.
- If `models.loras` is omitted, the worker falls back to the default LoRA pair chain from `basic.json`.

## Key Files

- `handler.py`: request validation, workflow assembly, video save handling.
- `basic.json`: source ComfyUI workflow used to extract defaults.
- `entrypoint.sh`: worker bootstrap.
- `Dockerfile`: container build.

## Credits

- `Wan2.2`: `https://github.com/Wan-Video/Wan2.2`
- `ComfyUI`: `https://github.com/comfyanonymous/ComfyUI`
- `ComfyUI-WanVideoWrapper`: `https://github.com/kijai/ComfyUI-WanVideoWrapper`
