import runpod
import os
import websocket
import base64
import json
import uuid
import logging
import urllib.request
import urllib.parse
import binascii  # Used for Base64 error handling
import subprocess
import shutil
import time
from typing import Any, Dict, List, Optional, Tuple
# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


server_address = os.getenv('SERVER_ADDRESS', '127.0.0.1')
client_id = str(uuid.uuid4())
BASIC_WORKFLOW_PATH = os.path.join(os.path.dirname(__file__), "basic.json")
def to_nearest_multiple_of_16(value):
    """Round a value to the nearest multiple of 16, with a minimum of 16."""
    try:
        numeric_value = float(value)
    except Exception:
        raise Exception(f"width/height must be numeric: {value}")
    adjusted = int(round(numeric_value / 16.0) * 16)
    if adjusted < 16:
        adjusted = 16
    return adjusted
def process_input(input_data, temp_dir, output_filename, input_type):
    """Process input data and return a file path."""
    if input_type == "path":
        logger.info(f"Processing path input: {input_data}")
        return input_data
    elif input_type == "url":
        logger.info(f"Processing URL input: {input_data}")
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        return download_file_from_url(input_data, file_path)
    elif input_type == "base64":
        logger.info("Processing Base64 input")
        return save_base64_to_file(input_data, temp_dir, output_filename)
    else:
        raise Exception(f"Unsupported input type: {input_type}")

        
def download_file_from_url(url, output_path):
    """Download a file from a URL."""
    try:
        # Download the file with wget.
        result = subprocess.run([
            'wget', '-O', output_path, '--no-verbose', url
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Downloaded file successfully: {url} -> {output_path}")
            return output_path
        else:
            logger.error(f"wget download failed: {result.stderr}")
            raise Exception(f"URL download failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("Download timed out")
        raise Exception("Download timed out")
    except Exception as e:
        logger.error(f"Error while downloading file: {e}")
        raise Exception(f"Error while downloading file: {e}")


def save_base64_to_file(base64_data, temp_dir, output_filename):
    """Save Base64 data to a file."""
    try:
        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]

        # Decode the Base64 string.
        decoded_data = base64.b64decode(base64_data)
        
        # Create the directory if it does not exist.
        os.makedirs(temp_dir, exist_ok=True)
        
        # Write the decoded file to disk.
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        
        logger.info(f"Saved Base64 input to file: {file_path}")
        return file_path
    except (binascii.Error, ValueError) as e:
        logger.error(f"Base64 decode failed: {e}")
        raise Exception(f"Base64 decode failed: {e}")
    
def queue_prompt(prompt):
    url = f"http://{server_address}:8188/prompt"
    logger.info(f"Queueing prompt to: {url}")
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    url = f"http://{server_address}:8188/view"
    logger.info(f"Getting image from: {url}")
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"{url}?{url_values}") as response:
        return response.read()

def get_history(prompt_id):
    url = f"http://{server_address}:8188/history/{prompt_id}"
    logger.info(f"Getting history from: {url}")
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())

def get_videos(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_videos = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break
        else:
            continue

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        videos_output = []
        if 'gifs' in node_output:
            for video in node_output['gifs']:
                videos_output.append(video)
        output_videos[node_id] = videos_output

    return output_videos

def load_workflow(workflow_path):
    with open(workflow_path, 'r') as file:
        return json.load(file)

def normalize_prompt_pairs(raw_pairs: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_pairs, list) or not raw_pairs:
        raise ValueError("The 'prompts' field must be a non-empty list of [positive, negative] or [positive, negative, length] entries.")

    normalized: List[Dict[str, Any]] = []
    for index, pair in enumerate(raw_pairs, start=1):
        if not isinstance(pair, (list, tuple)) or len(pair) not in (2, 3):
            raise ValueError(f"'prompts[{index - 1}]' must be a 2-item or 3-item list or tuple.")
        positive, negative = pair[0], pair[1]
        if not isinstance(positive, str) or not isinstance(negative, str):
            raise ValueError(f"'prompts[{index - 1}]' values must both be strings.")
        if not positive.strip():
            raise ValueError(f"'prompts[{index - 1}]' positive prompt cannot be empty.")
        stage_length = 81
        if len(pair) == 3:
            stage_length = pair[2]
            if not isinstance(stage_length, int):
                raise ValueError(f"'prompts[{index - 1}][2]' must be an integer when provided.")
            if stage_length <= 0:
                raise ValueError(f"'prompts[{index - 1}][2]' must be greater than 0.")
        normalized.append(
            {
                "positive": positive,
                "negative": negative,
                "length": stage_length,
            }
        )
    return normalized


def normalize_model_reference(model_path: str, model_group: str) -> str:
    if not isinstance(model_path, str) or not model_path.strip():
        raise ValueError(f"Model path for '{model_group}' must be a non-empty string.")

    normalized_path = model_path.strip()
    marker = f"/models/{model_group}/"
    if marker in normalized_path:
        return normalized_path.split(marker, 1)[1]
    if os.path.isabs(normalized_path):
        return os.path.basename(normalized_path)
    return normalized_path


def resolve_lora_pairs(models_input: Dict[str, Any], basic_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    if "loras" not in models_input:
        return [
            {
                "high": basic_config["high_base_lora_name"],
                "low": basic_config["low_base_lora_name"],
                "high_weight": basic_config["high_base_lora_strength"],
                "low_weight": basic_config["low_base_lora_strength"],
            },
            {
                "high": basic_config["high_svi_lora_name"],
                "low": basic_config["low_svi_lora_name"],
                "high_weight": basic_config["high_svi_lora_strength"],
                "low_weight": basic_config["low_svi_lora_strength"],
            },
        ]

    raw_loras = models_input.get("loras")
    if not isinstance(raw_loras, list):
        raise ValueError("'models.loras' must be a list when provided.")

    normalized_loras: List[Dict[str, Any]] = []
    for index, lora in enumerate(raw_loras):
        if not isinstance(lora, dict):
            raise ValueError(f"'models.loras[{index}]' must be an object.")
        high_path = lora.get("high")
        low_path = lora.get("low")
        if not isinstance(high_path, str) or not high_path.strip():
            raise ValueError(f"'models.loras[{index}].high' must be a non-empty string.")
        if not isinstance(low_path, str) or not low_path.strip():
            raise ValueError(f"'models.loras[{index}].low' must be a non-empty string.")
        high_weight = lora.get("high_weight", 1.0)
        low_weight = lora.get("low_weight", 1.0)
        if not isinstance(high_weight, (int, float)):
            raise ValueError(f"'models.loras[{index}].high_weight' must be numeric.")
        if not isinstance(low_weight, (int, float)):
            raise ValueError(f"'models.loras[{index}].low_weight' must be numeric.")

        normalized_loras.append(
            {
                "high": normalize_model_reference(high_path, "loras"),
                "low": normalize_model_reference(low_path, "loras"),
                "high_weight": float(high_weight),
                "low_weight": float(low_weight),
            }
        )
    return normalized_loras


def resolve_runtime_config(job_input: Dict[str, Any], basic_config: Dict[str, Any]) -> Dict[str, Any]:
    config = dict(basic_config)
    config["video"] = dict(basic_config["video"])
    config["video"]["format"] = "video/h264-mp4"

    models_input = job_input.get("models")
    if models_input is None:
        models_input = {}
    elif not isinstance(models_input, dict):
        raise ValueError("'models' must be an object when provided.")

    if "vae" in models_input:
        config["vae_name"] = normalize_model_reference(models_input["vae"], "vae")
    if "clip" in models_input:
        config["clip_name"] = normalize_model_reference(models_input["clip"], "text_encoders")

    wan_models = models_input.get("wan")
    if wan_models is None:
        wan_models = {}
    elif not isinstance(wan_models, dict):
        raise ValueError("'models.wan' must be an object when provided.")
    if "high" in wan_models:
        config["high_unet_name"] = normalize_model_reference(wan_models["high"], "checkpoints")
    if "low" in wan_models:
        config["low_unet_name"] = normalize_model_reference(wan_models["low"], "checkpoints")

    config["lora_pairs"] = resolve_lora_pairs(models_input, basic_config)

    if "sampler" in job_input:
        if not isinstance(job_input["sampler"], str) or not job_input["sampler"].strip():
            raise ValueError("'sampler' must be a non-empty string when provided.")
        config["sampler_name"] = job_input["sampler"].strip()

    if "frame_rate" in job_input:
        frame_rate = job_input["frame_rate"]
        if not isinstance(frame_rate, int) or frame_rate <= 0:
            raise ValueError("'frame_rate' must be a positive integer when provided.")
        config["video"]["frame_rate"] = frame_rate

    return config


def resolve_output_video_path(job_input: Dict[str, Any]) -> Optional[str]:
    requested_path = job_input.get("ouput_video")
    if requested_path is None:
        requested_path = job_input.get("output_video")

    if requested_path is None:
        return None
    if not isinstance(requested_path, str) or not requested_path.strip():
        raise ValueError("'ouput_video' must be a non-empty string when provided.")

    normalized_path = requested_path.strip()
    root, ext = os.path.splitext(normalized_path)
    if ext.lower() != ".mp4":
        normalized_path = f"{root}.mp4" if ext else f"{normalized_path}.mp4"

    return os.path.abspath(normalized_path)


def save_generated_video(source_path: str, output_path: str) -> str:
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    shutil.copy2(source_path, output_path)
    return output_path


def merge_job_input(shared_input: Dict[str, Any], task_input: Dict[str, Any]) -> Dict[str, Any]:
    merged = {key: value for key, value in shared_input.items() if key != "tasks"}

    shared_models = merged.get("models")
    task_models = task_input.get("models")
    if isinstance(shared_models, dict) and isinstance(task_models, dict):
        merged_models = dict(shared_models)
        for key, value in task_models.items():
            if key == "wan" and isinstance(merged_models.get("wan"), dict) and isinstance(value, dict):
                merged_wan = dict(merged_models["wan"])
                merged_wan.update(value)
                merged_models["wan"] = merged_wan
            else:
                merged_models[key] = value
        merged["models"] = merged_models

    for key, value in task_input.items():
        if key == "models" and isinstance(shared_models, dict) and isinstance(task_models, dict):
            continue
        merged[key] = value

    return merged


def normalize_job_tasks(job_input: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], bool]:
    raw_tasks = job_input.get("tasks")
    if raw_tasks is None:
        return [job_input], False

    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("'tasks' must be a non-empty list when provided.")

    normalized_tasks: List[Dict[str, Any]] = []
    for index, task in enumerate(raw_tasks):
        if not isinstance(task, dict):
            raise ValueError(f"'tasks[{index}]' must be an object.")
        normalized_tasks.append(merge_job_input(job_input, task))
    return normalized_tasks, True


def connect_to_comfyui() -> websocket.WebSocket:
    ws_url = f"ws://{server_address}:8188/ws?clientId={client_id}"
    logger.info(f"Connecting to WebSocket: {ws_url}")

    http_url = f"http://{server_address}:8188/"
    logger.info(f"Checking HTTP connection to: {http_url}")

    max_http_attempts = 180
    for http_attempt in range(max_http_attempts):
        try:
            response = urllib.request.urlopen(http_url, timeout=5)
            logger.info(f"HTTP connection succeeded (attempt {http_attempt + 1})")
            response.close()
            break
        except Exception as e:
            logger.warning(f"HTTP connection failed (attempt {http_attempt + 1}/{max_http_attempts}): {e}")
            if http_attempt == max_http_attempts - 1:
                raise Exception("Could not connect to the ComfyUI server. Confirm that it is running.")
            time.sleep(1)

    ws = websocket.WebSocket()
    max_attempts = int(180 / 5)
    for attempt in range(max_attempts):
        try:
            ws.connect(ws_url)
            logger.info(f"WebSocket connection succeeded (attempt {attempt + 1})")
            return ws
        except Exception as e:
            logger.warning(f"WebSocket connection failed (attempt {attempt + 1}/{max_attempts}): {e}")
            if attempt == max_attempts - 1:
                raise Exception("WebSocket connection timed out (3 minutes)")
            time.sleep(5)

    raise Exception("WebSocket connection timed out (3 minutes)")


def extract_generated_video(videos: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    for node_id in videos:
        if videos[node_id]:
            return videos[node_id][0]
    raise ValueError("Could not find a generated video.")

def load_basic_workflow_config() -> Dict[str, Any]:
    workflow = load_workflow(BASIC_WORKFLOW_PATH)
    nodes = {node["id"]: node for node in workflow["nodes"]}
    subgraphs = {subgraph["id"]: subgraph for subgraph in workflow["definitions"]["subgraphs"]}
    stage_one_nodes = {node["id"]: node for node in subgraphs["8bfbb9ea-806f-408a-b795-0b0203ad0179"]["nodes"]}
    stage_extension_nodes = {node["id"]: node for node in subgraphs["fea43421-19fd-4371-8ea3-8a6cca4ab475"]["nodes"]}

    video_defaults = dict(nodes[319]["widgets_values"])
    video_defaults.pop("videopreview", None)

    return {
        "clip_name": nodes[84]["widgets_values"][0],
        "clip_type": nodes[84]["widgets_values"][1],
        "clip_device": nodes[84]["widgets_values"][2],
        "vae_name": nodes[90]["widgets_values"][0],
        "high_unet_name": nodes[557]["widgets_values"][0],
        "low_unet_name": nodes[558]["widgets_values"][0],
        "high_base_lora_name": nodes[301]["widgets_values"][0],
        "high_base_lora_strength": nodes[301]["widgets_values"][1],
        "high_svi_lora_name": nodes[300]["widgets_values"][0],
        "high_svi_lora_strength": nodes[300]["widgets_values"][1],
        "low_base_lora_name": nodes[306]["widgets_values"][0],
        "low_base_lora_strength": nodes[306]["widgets_values"][1],
        "low_svi_lora_name": nodes[304]["widgets_values"][0],
        "low_svi_lora_strength": nodes[304]["widgets_values"][1],
        "sampler_name": nodes[299]["widgets_values"][0],
        "scheduler_name": nodes[298]["widgets_values"][0],
        "scheduler_steps": nodes[298]["widgets_values"][1],
        "scheduler_denoise": nodes[298]["widgets_values"][2],
        "split_step": nodes[128]["widgets_values"][0],
        "model_shift": nodes[297]["widgets_values"][0],
        "stage_length": stage_one_nodes[134]["widgets_values"][0],
        "motion_latent_count": stage_one_nodes[134]["widgets_values"][1],
        "guider_cfg": stage_one_nodes[121]["widgets_values"][0],
        "guider_start_percent": stage_one_nodes[121]["widgets_values"][1],
        "guider_end_percent": stage_one_nodes[121]["widgets_values"][2],
        "extension_overlap": stage_extension_nodes[329]["widgets_values"][0],
        "extension_overlap_side": stage_extension_nodes[329]["widgets_values"][1],
        "extension_overlap_mode": stage_extension_nodes[329]["widgets_values"][2],
        "video": video_defaults,
    }

def add_prompt_node(
    prompt: Dict[str, Any],
    next_id: List[int],
    class_type: str,
    inputs: Dict[str, Any],
    title: str,
) -> str:
    node_id = str(next_id[0])
    next_id[0] += 1
    prompt[node_id] = {
        "inputs": inputs,
        "class_type": class_type,
        "_meta": {"title": title},
    }
    return node_id

def build_basic_prompt(
    image_path: str,
    prompt_pairs: List[Dict[str, Any]],
    steps: int,
    cfg: float,
    seed: int,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    prompt: Dict[str, Any] = {}
    next_id = [1]

    split_ratio = config["split_step"] / max(config["scheduler_steps"], 1)
    split_step = min(max(1, int(round(steps * split_ratio))), max(1, steps - 1))

    clip_loader = add_prompt_node(
        prompt, next_id, "CLIPLoader",
        {
            "clip_name": config["clip_name"],
            "type": config["clip_type"],
            "device": config["clip_device"],
        },
        "CLIP Loader",
    )
    vae_loader = add_prompt_node(
        prompt, next_id, "VAELoader",
        {"vae_name": config["vae_name"]},
        "Load VAE",
    )
    image_loader = add_prompt_node(
        prompt, next_id, "LoadImage",
        {"image": image_path},
        "Input Image",
    )
    anchor_samples = add_prompt_node(
        prompt, next_id, "VAEEncode",
        {"pixels": [image_loader, 0], "vae": [vae_loader, 0]},
        "Anchor Samples",
    )

    high_unet = add_prompt_node(
        prompt, next_id, "UnetLoaderGGUF",
        {"unet_name": config["high_unet_name"]},
        "High UNet",
    )
    def add_lora_chain(base_model_id: str, branch: str) -> str:
        current_model_id = base_model_id
        for index, lora_pair in enumerate(config["lora_pairs"], start=1):
            current_model_id = add_prompt_node(
                prompt, next_id, "LoraLoaderModelOnly",
                {
                    "model": [current_model_id, 0],
                    "lora_name": lora_pair[branch],
                    "strength_model": lora_pair[f"{branch}_weight"],
                },
                f"{branch.title()} LoRA {index}",
            )
        return current_model_id

    high_lora_model = add_lora_chain(high_unet, "high")
    high_model_sampling = add_prompt_node(
        prompt, next_id, "ModelSamplingSD3",
        {"model": [high_lora_model, 0], "shift": config["model_shift"]},
        "Model Sampling SD3",
    )
    sigma_scheduler = add_prompt_node(
        prompt, next_id, "BasicScheduler",
        {
            "model": [high_model_sampling, 0],
            "scheduler": config["scheduler_name"],
            "steps": steps,
            "denoise": config["scheduler_denoise"],
        },
        "Basic Scheduler",
    )
    split_sigmas = add_prompt_node(
        prompt, next_id, "SplitSigmas",
        {"sigmas": [sigma_scheduler, 0], "step": split_step},
        "Split Sigmas",
    )

    low_unet = add_prompt_node(
        prompt, next_id, "UnetLoaderGGUF",
        {"unet_name": config["low_unet_name"]},
        "Low UNet",
    )
    low_lora_model = add_lora_chain(low_unet, "low")
    sampler = add_prompt_node(
        prompt, next_id, "KSamplerSelect",
        {"sampler_name": config["sampler_name"]},
        "Sampler Select",
    )

    def build_stage(
        pair: Dict[str, Any],
        stage_index: int,
        prev_samples: Optional[Tuple[str, int]] = None,
        source_images: Optional[Tuple[str, int]] = None,
    ) -> Tuple[Tuple[str, int], Tuple[str, int], Tuple[str, int]]:
        positive_prompt = pair["positive"]
        negative_prompt = pair["negative"]
        length = pair["length"]
        positive = add_prompt_node(
            prompt, next_id, "CLIPTextEncode",
            {"text": positive_prompt, "clip": [clip_loader, 0]},
            f"Positive Prompt {stage_index}",
        )
        negative = add_prompt_node(
            prompt, next_id, "CLIPTextEncode",
            {"text": negative_prompt, "clip": [clip_loader, 0]},
            f"Negative Prompt {stage_index}",
        )

        svi_inputs: Dict[str, Any] = {
            "positive": [positive, 0],
            "negative": [negative, 0],
            "length": length,
            "anchor_samples": [anchor_samples, 0],
            "motion_latent_count": config["motion_latent_count"],
        }
        if prev_samples is not None:
            svi_inputs["prev_samples"] = [prev_samples[0], prev_samples[1]]

        svi = add_prompt_node(
            prompt, next_id, "WanImageToVideoSVIPro", svi_inputs, f"SVI Stage {stage_index}"
        )
        guider_high = add_prompt_node(
            prompt, next_id, "ScheduledCFGGuidance",
            {
                "model": [high_lora_model, 0],
                "positive": [svi, 0],
                "negative": [svi, 1],
                "cfg": cfg,
                "start_percent": config["guider_start_percent"],
                "end_percent": config["guider_end_percent"],
            },
            f"High CFG {stage_index}",
        )
        guider_low = add_prompt_node(
            prompt, next_id, "ScheduledCFGGuidance",
            {
                "model": [low_lora_model, 0],
                "positive": [svi, 0],
                "negative": [svi, 1],
                "cfg": cfg,
                "start_percent": config["guider_start_percent"],
                "end_percent": config["guider_end_percent"],
            },
            f"Low CFG {stage_index}",
        )
        random_noise = add_prompt_node(
            prompt, next_id, "RandomNoise",
            {"noise_seed": seed + ((stage_index - 1) * 300)},
            f"Random Noise {stage_index}",
        )
        disabled_noise = add_prompt_node(
            prompt, next_id, "DisableNoise", {}, f"Disable Noise {stage_index}"
        )
        high_sample = add_prompt_node(
            prompt, next_id, "SamplerCustomAdvanced",
            {
                "noise": [random_noise, 0],
                "guider": [guider_high, 0],
                "sampler": [sampler, 0],
                "sigmas": [split_sigmas, 0],
                "latent_image": [svi, 2],
            },
            f"High Sample {stage_index}",
        )
        low_sample = add_prompt_node(
            prompt, next_id, "SamplerCustomAdvanced",
            {
                "noise": [disabled_noise, 0],
                "guider": [guider_low, 0],
                "sampler": [sampler, 0],
                "sigmas": [split_sigmas, 1],
                "latent_image": [high_sample, 0],
            },
            f"Low Sample {stage_index}",
        )
        decoded_images = add_prompt_node(
            prompt, next_id, "VAEDecode",
            {"samples": [low_sample, 0], "vae": [vae_loader, 0]},
            f"Decode Stage {stage_index}",
        )

        if source_images is None:
            return (low_sample, 0), (decoded_images, 0), (decoded_images, 0)

        extended_images = add_prompt_node(
            prompt, next_id, "ImageBatchExtendWithOverlap",
            {
                "source_images": [source_images[0], source_images[1]],
                "new_images": [decoded_images, 0],
                "overlap": config["extension_overlap"],
                "overlap_side": config["extension_overlap_side"],
                "overlap_mode": config["extension_overlap_mode"],
            },
            f"Extend Stage {stage_index}",
        )
        return (low_sample, 0), (decoded_images, 0), (extended_images, 2)

    previous_latent, _previous_preview_images, final_images = build_stage(prompt_pairs[0], 1)
    for stage_index, pair in enumerate(prompt_pairs[1:], start=2):
        previous_latent, _previous_preview_images, final_images = build_stage(
            pair,
            stage_index,
            prev_samples=previous_latent,
            source_images=final_images,
        )

    video_inputs = dict(config["video"])
    video_inputs["images"] = [final_images[0], final_images[1]]
    add_prompt_node(prompt, next_id, "VHS_VideoCombine", video_inputs, "Video Combine")
    return prompt


def run_generation_task(job_input: Dict[str, Any], basic_config: Dict[str, Any]) -> Dict[str, Any]:
    task_id = f"task_{uuid.uuid4()}"

    prompt_pairs = normalize_prompt_pairs(job_input.get("prompts"))
    output_video_path = resolve_output_video_path(job_input)

    image_path = None
    if "image_path" in job_input:
        image_path = process_input(job_input["image_path"], task_id, "input_image.jpg", "path")
    elif "image_url" in job_input:
        image_path = process_input(job_input["image_url"], task_id, "input_image.jpg", "url")
    elif "image_base64" in job_input:
        image_path = process_input(job_input["image_base64"], task_id, "input_image.jpg", "base64")
    else:
        image_path = "/example_image.png"
        logger.info("Using default image file: /example_image.png")

    runtime_config = resolve_runtime_config(job_input, basic_config)
    seed = job_input.get("seed", 2025)
    if not isinstance(seed, int):
        raise ValueError("'seed' must be an integer when provided.")

    cfg = job_input.get("cfg", basic_config["guider_cfg"])
    steps = job_input.get("steps", basic_config["scheduler_steps"])
    if not isinstance(steps, int) or steps <= 0:
        raise ValueError("'steps' must be a positive integer when provided.")

    original_width = job_input.get("width", 480)
    original_height = job_input.get("height", 480)
    adjusted_width = to_nearest_multiple_of_16(original_width)
    adjusted_height = to_nearest_multiple_of_16(original_height)
    if adjusted_width != original_width:
        logger.info(f"Width adjusted to nearest multiple of 16: {original_width} -> {adjusted_width}")
    if adjusted_height != original_height:
        logger.info(f"Height adjusted to nearest multiple of 16: {original_height} -> {adjusted_height}")

    prompt = build_basic_prompt(
        image_path=image_path,
        prompt_pairs=prompt_pairs,
        steps=steps,
        cfg=cfg,
        seed=seed,
        config=runtime_config,
    )

    ws = connect_to_comfyui()
    try:
        videos = get_videos(ws, prompt)
    finally:
        ws.close()

    generated_video = extract_generated_video(videos)
    source_video_path = generated_video.get("fullpath")
    if not source_video_path:
        raise ValueError("Generated video metadata does not include 'fullpath'.")

    if output_video_path:
        saved_path = save_generated_video(source_video_path, output_video_path)
        return {"ouput_video": saved_path, "output_video": saved_path}

    with open(source_video_path, 'rb') as f:
        video_data = base64.b64encode(f.read()).decode('utf-8')
    return {"video": video_data}

def handler(event):
    if "input" not in event:
        raise ValueError("Runpod event payload must include an 'input' object.")

    job_input = event["input"] or {}
    logger.info(f"Received event input: {job_input}")
    basic_config = load_basic_workflow_config()
    tasks, is_batch_request = normalize_job_tasks(job_input)

    if not is_batch_request:
        return run_generation_task(tasks[0], basic_config)

    results: List[Dict[str, Any]] = []
    for index, task_input in enumerate(tasks):
        logger.info(f"Starting batch task {index + 1}/{len(tasks)}")
        try:
            task_result = run_generation_task(task_input, basic_config)
        except Exception as e:
            logger.exception(f"Batch task {index + 1} failed: {e}")
            task_result = {"error": str(e)}
        results.append(task_result)

    return {"tasks": results}

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
