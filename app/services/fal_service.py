"""
Real fal.ai integration for Wayne AI Video Studio.

Handles animate_frame() — converts a keyframe image into a real video clip
using Wan (Economy/Standard) or Kling 3.0 (Standard hero / Premium).

Routing per spec:
- Economy:  Wan for all animate shots
- Standard: Kling for hero shot (idx=0), Wan for rest
- Premium:  Kling for all shots
"""
import asyncio
import logging
import uuid
from pathlib import Path

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("static/videos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# fal.ai model endpoints — updated July 2026
FAL_WAN_MODEL = "fal-ai/wan/v2.2/image-to-video"
FAL_KLING_MODEL = "fal-ai/kling-video/v1.6/pro/image-to-video"

# Cost per second of video
MODEL_COST_PER_SEC = {
    "wan": 0.10,   # Wan 2.2 A14B — $0.10/sec at 720p
    "kling": 0.10, # Kling 3.0 Pro — $0.10/sec
}


def _get_fal_headers() -> dict:
    api_key = settings.FAL_API_KEY
    if not api_key:
        raise ValueError("FAL_API_KEY is not set in .env")
    return {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }


async def _submit_fal_job(model: str, payload: dict) -> str | None:
    """Submit a job to fal.ai and return the request_id."""
    url = f"https://queue.fal.run/{model}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=_get_fal_headers())
            response.raise_for_status()
            data = response.json()
            request_id = data.get("request_id")
            logger.info(f"fal.ai job submitted: {request_id} on {model}")
            return request_id
    except Exception as e:
        logger.error(f"fal.ai submit failed: {e}")
        return None


async def _poll_fal_job(model: str, request_id: str, timeout: int = 300) -> dict | None:
    """Poll fal.ai until the job completes or times out."""
    status_url = f"https://queue.fal.run/{model}/requests/{request_id}/status"
    result_url = f"https://queue.fal.run/{model}/requests/{request_id}"
    start = asyncio.get_event_loop().time()

    async with httpx.AsyncClient(timeout=30) as client:
        while asyncio.get_event_loop().time() - start < timeout:
            try:
                resp = await client.get(status_url, headers=_get_fal_headers())
                resp.raise_for_status()
                status_data = resp.json()
                status = status_data.get("status", "")

                if status == "COMPLETED":
                    result_resp = await client.get(result_url, headers=_get_fal_headers())
                    result_resp.raise_for_status()
                    logger.info(f"fal.ai job {request_id} completed")
                    return result_resp.json()
                elif status == "FAILED":
                    logger.error(f"fal.ai job {request_id} failed: {status_data}")
                    return None
                else:
                    logger.info(f"fal.ai job {request_id} status: {status}")
                    await asyncio.sleep(3)

            except Exception as e:
                logger.error(f"fal.ai poll error: {e}")
                await asyncio.sleep(3)

    logger.error(f"fal.ai job {request_id} timed out after {timeout}s")
    return None


async def animate_frame(frame_url: str, motion: str, model: str) -> tuple[str, float]:
    """
    Convert a keyframe image to a video clip using fal.ai.
    Returns (video_url, cost).
    """
    fal_model = FAL_KLING_MODEL if model == "kling" else FAL_WAN_MODEL
    duration = 5  # seconds
    cost_per_sec = MODEL_COST_PER_SEC.get(model, 0.05)
    estimated_cost = duration * cost_per_sec

    # Build payload based on model
    if model == "kling":
        payload = {
            "image_url": frame_url,
            "prompt": motion or "cinematic camera movement, professional marketing video",
            "duration": "5",
            "cfg_scale": 0.5,
        }
    else:
        # Wan 2.2 payload
        payload = {
            "image_url": frame_url,
            "prompt": motion or "smooth cinematic motion, professional quality",
            "num_frames": 81,
            "resolution": "720p",
            "num_inference_steps": 30,
        }

    try:
        request_id = await _submit_fal_job(fal_model, payload)
        if not request_id:
            raise Exception("Failed to submit fal.ai job")

        result = await _poll_fal_job(fal_model, request_id)
        if not result:
            raise Exception("fal.ai job failed or timed out")

        # Extract video URL from result
        video_url = None
        if "video" in result:
            video_url = result["video"].get("url")
        elif "videos" in result and result["videos"]:
            video_url = result["videos"][0].get("url")
        elif "output" in result:
            video_url = result["output"] if isinstance(result["output"], str) else result["output"][0]

        if not video_url:
            raise Exception(f"No video URL in fal.ai response: {result}")

        logger.info(f"animate_frame complete via {model}: {video_url[:60]}")
        return video_url, estimated_cost

    except Exception as e:
        logger.error(f"animate_frame failed ({model}): {e} — falling back to motion_still")
        # Fallback to FFmpeg motion_still if fal.ai fails
        from app.services.ffmpeg_service import motion_still
        return await motion_still(frame_url, motion)
