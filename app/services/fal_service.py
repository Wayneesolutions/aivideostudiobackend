"""
Real fal.ai integration using the official fal_client SDK.

Handles animate_frame() — converts a keyframe image into a real video clip
using Wan 2.2 (Economy/Standard) or Kling 3.0 (Standard hero / Premium).
"""
import asyncio
import logging
import os

from app.core.config import settings

logger = logging.getLogger(__name__)

# fal.ai model endpoints
FAL_WAN_MODEL = "fal-ai/wan/v2.2/image-to-video"
FAL_KLING_MODEL = "fal-ai/kling-video/v1.6/pro/image-to-video"

# Cost per second of video
MODEL_COST_PER_SEC = {
    "wan": 0.10,
    "kling": 0.10,
}


def _get_fal_client():
    """Get fal_client with API key configured."""
    import fal_client
    os.environ["FAL_KEY"] = settings.FAL_API_KEY
    return fal_client


async def animate_frame(frame_url: str, motion: str, model: str) -> tuple[str, float]:
    """
    Convert a keyframe image to a video clip using fal.ai official SDK.
    Returns (video_url, cost).
    """
    if not settings.FAL_API_KEY:
        logger.warning("FAL_API_KEY not set — falling back to FFmpeg motion_still")
        from app.services.ffmpeg_service import motion_still
        return await motion_still(frame_url, motion)

    fal_model = FAL_KLING_MODEL if model == "kling" else FAL_WAN_MODEL
    duration = 5
    cost = duration * MODEL_COST_PER_SEC.get(model, 0.10)

    # Build payload based on model
    if model == "kling":
        payload = {
            "image_url": frame_url,
            "prompt": motion or "cinematic camera movement, professional marketing video",
            "duration": "5",
            "cfg_scale": 0.5,
        }
    else:
        payload = {
            "image_url": frame_url,
            "prompt": motion or "smooth cinematic motion, professional quality",
            "num_frames": 81,
            "resolution": "720p",
            "num_inference_steps": 30,
        }

    try:
        fal_client = _get_fal_client()
        logger.info(f"Submitting fal.ai job: {fal_model}")

        # Use the official SDK which handles queue/polling automatically
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: fal_client.subscribe(
                fal_model,
                arguments=payload,
            )
        )

        # Extract video URL from result
        video_url = None
        if isinstance(result, dict):
            if "video" in result:
                video_url = result["video"].get("url")
            elif "videos" in result and result["videos"]:
                video_url = result["videos"][0].get("url")
            elif "output" in result:
                output = result["output"]
                video_url = output if isinstance(output, str) else (output[0] if output else None)

        if not video_url:
            raise Exception(f"No video URL in result: {list(result.keys()) if result else 'empty'}")

        logger.info(f"animate_frame complete via {model}: {video_url[:60]}")
        return video_url, cost

    except Exception as e:
        logger.error(f"animate_frame failed ({model}): {e} — falling back to FFmpeg")
        from app.services.ffmpeg_service import motion_still
        return await motion_still(frame_url, motion)
