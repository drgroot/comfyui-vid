#!/usr/bin/env python3
"""
Generate Video API client with base64 encoding
Client for generating videos from images using RunPod's generate_video endpoint
"""

import os
import requests
import json
import time
import base64
from typing import Optional, Dict, Any, List, Tuple, Union
import logging

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PromptEntry = Union[Tuple[str, str], Tuple[str, str, int]]

class GenerateVideoClient:
    def __init__(
        self,
        runpod_endpoint_id: str,
        runpod_api_key: str
    ):
        """
        Initialize Generate Video client
        
        Args:
            runpod_endpoint_id: RunPod endpoint ID
            runpod_api_key: RunPod API key
        """
        self.runpod_endpoint_id = runpod_endpoint_id
        self.runpod_api_key = runpod_api_key
        self.runpod_api_endpoint = f"https://api.runpod.ai/v2/{runpod_endpoint_id}/run"
        self.status_url = f"https://api.runpod.ai/v2/{runpod_endpoint_id}/status"
        
        # Initialize HTTP session
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {runpod_api_key}',
            'Content-Type': 'application/json'
        })
        
        logger.info(f"GenerateVideoClient initialized - Endpoint: {runpod_endpoint_id}")
    
    def encode_file_to_base64(self, file_path: str) -> Optional[str]:
        """
        Encode file to base64
        
        Args:
            file_path: File path to encode
        
        Returns:
            Base64 encoded string or None (on failure)
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"File does not exist: {file_path}")
                return None
            
            with open(file_path, 'rb') as f:
                file_data = f.read()
                base64_data = base64.b64encode(file_data).decode('utf-8')
            
            logger.info(f"File base64 encoding completed: {file_path}")
            return base64_data
            
        except Exception as e:
            logger.error(f"File base64 encoding failed: {e}")
            return None
    
    def submit_job(self, input_data: Dict[str, Any]) -> Optional[str]:
        """
        Submit job to RunPod
        
        Args:
            input_data: API input data
        
        Returns:
            Job ID or None (on failure)
        """
        payload = {"input": input_data}
        
        try:
            logger.info(f"Submitting job to RunPod: {self.runpod_api_endpoint}")
            logger.info(f"Input data: {json.dumps(input_data, indent=2, ensure_ascii=False)}")
            
            response = self.session.post(self.runpod_api_endpoint, json=payload, timeout=30)
            response.raise_for_status()
            
            response_data = response.json()
            job_id = response_data.get('id')
            
            if job_id:
                logger.info(f"Job submission successful. Job ID: {job_id}")
                return job_id
            else:
                logger.error(f"Failed to receive Job ID: {response_data}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Job submission failed: {e}")
            return None
    
    def wait_for_completion(self, job_id: str, check_interval: int = 10, max_wait_time: int = 1800) -> Dict[str, Any]:
        """
        Wait for job completion
        
        Args:
            job_id: Job ID
            check_interval: Status check interval (seconds)
            max_wait_time: Maximum wait time (seconds)
        
        Returns:
            Job result dictionary
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                logger.info(f"Checking job status... (Job ID: {job_id})")
                
                response = self.session.get(f"{self.status_url}/{job_id}", timeout=30)
                response.raise_for_status()
                
                status_data = response.json()
                status = status_data.get('status')
                
                if status == 'COMPLETED':
                    logger.info("Job completed.")
                    return {
                        'status': 'COMPLETED',
                        'output': status_data.get('output'),
                        'job_id': job_id
                    }
                elif status == 'FAILED':
                    logger.error("Job failed.")
                    return {
                        'status': 'FAILED',
                        'error': status_data.get('error', 'Unknown error'),
                        'job_id': job_id
                    }
                elif status in ['IN_QUEUE', 'IN_PROGRESS']:
                    logger.info(f"Job in progress... (Status: {status})")
                    time.sleep(check_interval)
                else:
                    logger.warning(f"Unknown status: {status}")
                    return {
                        'status': 'UNKNOWN',
                        'data': status_data,
                        'job_id': job_id
                    }
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Status check error: {e}")
                time.sleep(check_interval)
        
        logger.error(f"Job wait timeout ({max_wait_time} seconds)")
        return {
            'status': 'TIMEOUT',
            'job_id': job_id
        }
    
    def save_video_result(self, result: Dict[str, Any], output_path: str) -> bool:
        """
        Save video file from job result
        
        Args:
            result: Job result dictionary
            output_path: File path to save
        
        Returns:
            Save success status
        """
        try:
            if result.get('status') != 'COMPLETED':
                logger.error(f"Job not completed: {result.get('status')}")
                return False
            
            output = result.get('output', {})
            video_b64 = output.get('video')
            
            if not video_b64:
                logger.error("Video data not found")
                return False
            
            # Create directory
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Decode base64 and save video
            decoded_video = base64.b64decode(video_b64)
            
            with open(output_path, 'wb') as f:
                f.write(decoded_video)
            
            file_size = os.path.getsize(output_path)
            logger.info(f"Video saved successfully: {output_path} ({file_size / (1024*1024):.1f}MB)")
            return True
            
        except Exception as e:
            logger.error(f"Video save failed: {e}")
            return False

    def normalize_prompts(
        self,
        prompts: List[PromptEntry],
        default_length: Optional[int] = None,
    ) -> List[List[Union[str, int]]]:
        """
        Normalize prompt tuples to the payload format expected by the worker.
        """
        normalized: List[List[Union[str, int]]] = []
        for index, prompt_entry in enumerate(prompts):
            if not isinstance(prompt_entry, (list, tuple)) or len(prompt_entry) not in (2, 3):
                raise ValueError(f"prompts[{index}] must be a 2-item or 3-item tuple/list.")

            positive = prompt_entry[0]
            negative = prompt_entry[1]
            if not isinstance(positive, str) or not isinstance(negative, str):
                raise ValueError(f"prompts[{index}] must contain string prompt values.")

            if len(prompt_entry) == 3:
                if not isinstance(prompt_entry[2], int):
                    raise ValueError(f"prompts[{index}][2] must be an integer when provided.")
                normalized.append([positive, negative, prompt_entry[2]])
            elif default_length is not None:
                normalized.append([positive, negative, default_length])
            else:
                normalized.append([positive, negative])
        return normalized

    def submit_batch_video_job(
        self,
        tasks: List[Dict[str, Any]],
        seed: int = 2025,
        frame_rate: int = 24,
        sampler: str = "euler",
        steps: int = 4,
        models: Optional[Dict[str, Any]] = None,
        extra_options: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Submit a batch video job using the new tasks-based payload.
        """
        input_data: Dict[str, Any] = {
            "tasks": tasks,
            "seed": seed,
            "frame_rate": frame_rate,
            "sampler": sampler,
            "steps": steps,
        }
        if models is not None:
            input_data["models"] = models
        if extra_options:
            input_data.update(extra_options)
        return self.submit_job(input_data)
    
    def create_video_from_image(
        self,
        image_path: str,
        prompts: List[PromptEntry],
        width: int = 480,
        height: int = 480,
        length: int = 81,
        steps: int = 4,
        seed: int = 2025,
        cfg: float = 1.0,
        frame_rate: int = 24,
        sampler: str = "euler",
        models: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate video from image
        
        Args:
            image_path: Image file path
            prompts: List of (positive_prompt, negative_prompt) pairs
            width: Output width
            height: Output height
            length: Number of frames per sampling stage
            steps: Number of steps
            seed: Seed value
            cfg: CFG scale
        
        Returns:
            Job result dictionary
        """
        # Check file existence
        if not os.path.exists(image_path):
            return {"error": f"Image file does not exist: {image_path}"}
        
        # Encode image to base64
        image_base64 = self.encode_file_to_base64(image_path)
        if not image_base64:
            return {"error": "Image base64 encoding failed"}
        
        task = {
            "image_base64": image_base64,
            "prompts": self.normalize_prompts(prompts, default_length=length),
        }

        extra_options = {
            "width": width,
            "height": height,
            "cfg": cfg,
        }

        job_id = self.submit_batch_video_job(
            tasks=[task],
            seed=seed,
            frame_rate=frame_rate,
            sampler=sampler,
            steps=steps,
            models=models,
            extra_options=extra_options,
        )
        if not job_id:
            return {"error": "Job submission failed"}
        
        result = self.wait_for_completion(job_id)
        if result.get("status") == "COMPLETED":
            output = result.get("output") or {}
            task_outputs = output.get("tasks")
            if isinstance(task_outputs, list) and task_outputs:
                result["output"] = task_outputs[0]
        return result
    
    def batch_process_images(
        self,
        image_folder_path: str,
        output_folder_path: str,
        valid_extensions: tuple = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff'),
        prompts: Optional[List[PromptEntry]] = None,
        width: int = 480,
        height: int = 480,
        length: int = 81,
        steps: int = 4,
        seed: int = 2025,
        cfg: float = 1.0,
        frame_rate: int = 24,
        sampler: str = "euler",
        models: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Batch process all image files in folder
        
        Args:
            image_folder_path: Folder path containing image files
            output_folder_path: Folder path to save results
            valid_extensions: Image file extensions to process
            prompts: List of (positive_prompt, negative_prompt) pairs
            width: Output width
            height: Output height
            length: Number of frames per sampling stage
            steps: Number of steps
            seed: Seed value
            cfg: CFG scale
        
        Returns:
            Batch processing result dictionary
        """
        # Check path
        if not os.path.isdir(image_folder_path):
            return {"error": f"Image folder does not exist: {image_folder_path}"}
        
        # Create output folder
        os.makedirs(output_folder_path, exist_ok=True)
        
        # Get image file list
        image_files = [
            f for f in os.listdir(image_folder_path)
            if f.lower().endswith(valid_extensions)
        ]
        
        if not image_files:
            return {"error": f"No image files to process: {image_folder_path}"}

        if prompts is None:
            prompts = [("running man, grab the gun", "blurry, low quality, distorted")]

        logger.info(f"Starting batch processing: {len(image_files)} files")
        
        results = {
            "total_files": len(image_files),
            "successful": 0,
            "failed": 0,
            "results": []
        }
        
        tasks: List[Dict[str, Any]] = []
        ordered_files: List[str] = []
        for filename in image_files:
            image_path = os.path.join(image_folder_path, filename)
            image_base64 = self.encode_file_to_base64(image_path)
            if not image_base64:
                logger.error(f"[{filename}] Image base64 encoding failed")
                results["failed"] += 1
                results["results"].append({
                    "filename": filename,
                    "status": "failed",
                    "error": "Image base64 encoding failed",
                })
                continue

            tasks.append({
                "image_base64": image_base64,
                "prompts": self.normalize_prompts(prompts, default_length=length),
            })
            ordered_files.append(filename)

        if not tasks:
            return results

        extra_options = {
            "width": width,
            "height": height,
            "cfg": cfg,
        }
        job_id = self.submit_batch_video_job(
            tasks=tasks,
            seed=seed,
            frame_rate=frame_rate,
            sampler=sampler,
            steps=steps,
            models=models,
            extra_options=extra_options,
        )
        if not job_id:
            for filename in ordered_files:
                results["failed"] += 1
                results["results"].append({
                    "filename": filename,
                    "status": "failed",
                    "error": "Job submission failed",
                })
            return results

        result = self.wait_for_completion(job_id)
        if result.get("status") != "COMPLETED":
            batch_error = result.get("error", "Unknown error")
            for filename in ordered_files:
                logger.error(f"[{filename}] Job failed: {batch_error}")
                results["failed"] += 1
                results["results"].append({
                    "filename": filename,
                    "status": "failed",
                    "error": batch_error,
                    "job_id": result.get("job_id"),
                })
            return results

        task_outputs = (result.get("output") or {}).get("tasks")
        if not isinstance(task_outputs, list):
            batch_error = "Batch output does not contain a tasks list"
            for filename in ordered_files:
                results["failed"] += 1
                results["results"].append({
                    "filename": filename,
                    "status": "failed",
                    "error": batch_error,
                    "job_id": result.get("job_id"),
                })
            return results

        for filename, task_output in zip(ordered_files, task_outputs):
            if not isinstance(task_output, dict):
                results["failed"] += 1
                results["results"].append({
                    "filename": filename,
                    "status": "failed",
                    "error": "Invalid task output",
                    "job_id": result.get("job_id"),
                })
                continue

            if task_output.get("error"):
                results["failed"] += 1
                results["results"].append({
                    "filename": filename,
                    "status": "failed",
                    "error": task_output["error"],
                    "job_id": result.get("job_id"),
                })
                continue

            base_filename = os.path.splitext(filename)[0]
            output_filename = os.path.join(output_folder_path, f"result_{base_filename}.mp4")
            single_result = {
                "status": "COMPLETED",
                "output": task_output,
                "job_id": result.get("job_id"),
            }
            if self.save_video_result(single_result, output_filename):
                results["successful"] += 1
                results["results"].append({
                    "filename": filename,
                    "status": "success",
                    "output_file": output_filename,
                    "job_id": result.get("job_id"),
                })
            else:
                results["failed"] += 1
                results["results"].append({
                    "filename": filename,
                    "status": "failed",
                    "error": "Result save failed",
                    "job_id": result.get("job_id"),
                })

        if len(task_outputs) < len(ordered_files):
            for filename in ordered_files[len(task_outputs):]:
                results["failed"] += 1
                results["results"].append({
                    "filename": filename,
                    "status": "failed",
                    "error": "Batch output missing task result",
                    "job_id": result.get("job_id"),
                })

        logger.info(f"\nBatch processing completed: {results['successful']}/{results['total_files']} successful")
        return results


def main():
    """Usage example"""
    
    # Configuration (change to actual values)
    ENDPOINT_ID = "your-endpoint-id"
    RUNPOD_API_KEY = "your-runpod-api-key"
    
    # Initialize client
    client = GenerateVideoClient(
        runpod_endpoint_id=ENDPOINT_ID,
        runpod_api_key=RUNPOD_API_KEY
    )
    
    print("=== Generate Video Client Usage Example ===\n")
    
    # Example 1: Single image processing
    print("1. Single image processing")
    result1 = client.create_video_from_image(
        image_path="./example_image.png",
        prompts=[
            (
                "The woman drives the luxury convertible car through a tropical mountainous valley during sunset. The camera follows close behind the car as it speeds down the road.",
                "blurry, low quality, distorted",
            ),
            (
                "The woman turns the car right down another road and quickly accelerates away. The camera follows close behind the car.",
                "blurry, low quality, distorted",
            ),
        ],
        width=480,
        height=480,
        length=81,
        steps=4,
        seed=42,
        cfg=1.0
    )
    
    if result1.get('status') == 'COMPLETED':
        client.save_video_result(result1, "./output_single.mp4")
    else:
        print(f"Error: {result1.get('error')}")
    
    print("\n" + "-"*50 + "\n")
    
    # Example 2: Single-stage generation
    print("2. Single-stage generation")
    result2 = client.create_video_from_image(
        image_path="./example_image.png",
        prompts=[
            (
                "A cinematic close-up of a runner sprinting through a neon-lit alley at night.",
                "blurry, low quality, distorted",
            )
        ],
        width=480,
        height=480,
        length=81,
        steps=4,
        seed=42,
        cfg=1.0,
    )
    
    if result2.get('status') == 'COMPLETED':
        client.save_video_result(result2, "./output_lora.mp4")
    else:
        print(f"Error: {result2.get('error')}")
    
    print("\n" + "-"*50 + "\n")
    
    # Example 3: Batch processing (uncomment to use)
    # print("3. Batch processing")
    # batch_result = client.batch_process_images(
    #     image_folder_path="./input_images",
    #     output_folder_path="./output_videos",
    #     prompts=[("running man, grab the gun", "blurry, low quality, distorted")],
    #     width=480,
    #     height=480,
    #     length=81,
    #     steps=4,
    #     seed=42,
    #     cfg=1.0
    # )
    
    # print(f"Batch processing result: {batch_result}")
    
    print("\n=== All examples completed ===")


if __name__ == "__main__":
    main()
