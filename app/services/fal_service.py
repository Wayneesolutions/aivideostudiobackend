"""
Real fal.ai integration — Kling text-to-video for real animated scenes.
"""
import asyncio
import logging
import os
import uuid
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

FAL_KLING_T2V = "fal-ai/kling-video/v1.6/pro/text-to-video"
FAL_KLING_I2V = "fal-ai/kling-video/v1.6/pro/image-to-video"
FAL_WAN_MODEL = "fal-ai/wan/v2.2-5b/image-to-video"

MODEL_COST_PER_SEC = {"wan": 0.10, "kling": 0.10}


def _get_fal_client():
    import fal_client
    os.environ["FAL_KEY"] = settings.FAL_API_KEY
    return fal_client


def _extract_video_url(result) -> str | None:
    if not result:
        return None
    if isinstance(result, dict):
        v = result.get("video") or (result.get("videos") or [None])[0]
        if v:
            return v.get("url") if isinstance(v, dict) else getattr(v, "url", None)
    else:
        v = getattr(result, "video", None) or ((getattr(result, "videos", None) or [None])[0])
        if v:
            return v.get("url") if isinstance(v, dict) else getattr(v, "url", None)
    return None


async def animate_frame(frame_url: str, motion: str, model: str) -> tuple[str, float]:
    """
    Generate real AI video using Kling text-to-video.
    Falls back to image-to-video, then FFmpeg if all fail.
    """
    if not settings.FAL_API_KEY:
        logger.warning("FAL_API_KEY not set — falling back to FFmpeg")
        from app.services.ffmpeg_service import motion_still
        return await motion_still(frame_url, motion)

    duration = 5
    cost = duration * MODEL_COST_PER_SEC.get(model, 0.10)
    fal_client = _get_fal_client()

    text_prompt = (
        f"{motion or 'cinematic professional advertisement scene'}, "
        f"smooth natural movement, real people moving naturally, "
        f"high quality commercial video, professional lighting, premium brand aesthetic"
    )

    # Resolution based on quality mode
    resolution = "1080p" if model == "kling" else "720p"

    logger.info(f"Kling text-to-video ({resolution}): {text_prompt[:80]}")

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: fal_client.subscribe(
                FAL_KLING_T2V,
                arguments={
                    "prompt": text_prompt,
                    "duration": "5",
                    "cfg_scale": 0.5,
                    "aspect_ratio": "9:16",
                    "resolution": resolution,
                },
            )
        )
        video_url = _extract_video_url(result)
        if video_url:
            logger.info(f"Kling T2V complete: {video_url[:60]}")
            return video_url, cost
        raise Exception("No video URL in T2V result")

    except Exception as e:
        logger.error(f"Kling T2V failed: {e} — trying image-to-video")

        try:
            import httpx
            public_url = frame_url
            if "127.0.0.1" in frame_url or "localhost" in frame_url:
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    resp = await client.get(frame_url)
                    resp.raise_for_status()
                    tmp = Path(f"static/images/fal_{uuid.uuid4().hex}.png")
                    tmp.write_bytes(resp.content)
                public_url = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: fal_client.upload_file(str(tmp))
                )
                try:
                    tmp.unlink()
                except Exception:
                    pass

            result2 = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: fal_client.subscribe(
                    FAL_KLING_I2V,
                    arguments={
                        "image_url": public_url,
                        "prompt": text_prompt,
                        "duration": "5",
                        "cfg_scale": 0.5,
                    },
                )
            )
            video_url = _extract_video_url(result2)
            if video_url:
                logger.info(f"Kling I2V complete: {video_url[:60]}")
                return video_url, cost

        except Exception as e2:
            logger.error(f"Kling I2V also failed: {e2}")

    logger.warning("All fal.ai attempts failed — falling back to FFmpeg")
    from app.services.ffmpeg_service import motion_still
    return await motion_still(frame_url, motion)
