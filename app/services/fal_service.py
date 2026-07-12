"""
Real fal.ai integration.
Medium = Wan 2.2 text-to-video 720p (~$0.04/sec)
Premium = Kling 2.5 Turbo text-to-video 720p (~$0.07/sec)
Images = Flux (~$0.003/image)
"""
import asyncio
import logging
import os
import uuid
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# Video models
FAL_WAN_T2V = "fal-ai/wan/v2.2-5b/text-to-video"           # Medium - cheapest
FAL_KLING_T2V = "fal-ai/kling-video/v2.5/turbo/text-to-video"  # Premium - better quality
FAL_WAN_I2V = "fal-ai/wan/v2.2-5b/image-to-video"
FAL_KLING_I2V = "fal-ai/kling-video/v2.5/turbo/image-to-video"

# Image model - Flux (cheapest, ~$0.003/image)
FAL_FLUX_MODEL = "fal-ai/flux/schnell"

MODEL_COST_PER_SEC = {
    "wan": 0.04,    # Wan 2.2 ~$0.04/sec
    "kling": 0.07,  # Kling 2.5 Turbo ~$0.07/sec
}


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


def _extract_image_url(result) -> str | None:
    if not result:
        return None
    if isinstance(result, dict):
        images = result.get("images") or []
        if images:
            img = images[0]
            return img.get("url") if isinstance(img, dict) else getattr(img, "url", None)
    else:
        images = getattr(result, "images", None) or []
        if images:
            img = images[0]
            return img.get("url") if isinstance(img, dict) else getattr(img, "url", None)
    return None


async def generate_image_flux(prompt: str) -> str | None:
    """
    Generate image using fal.ai Flux Schnell.
    Cost: ~$0.003 per image (90% cheaper than DALL-E 3)
    """
    if not settings.FAL_API_KEY:
        return None

    try:
        fal_client = _get_fal_client()
        logger.info(f"Generating Flux image: {prompt[:60]}")

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: fal_client.subscribe(
                FAL_FLUX_MODEL,
                arguments={
                    "prompt": prompt,
                    "image_size": "square_hd",
                    "num_images": 1,
                    "num_inference_steps": 4,
                    "enable_safety_checker": True,
                },
            )
        )

        image_url = _extract_image_url(result)
        if image_url:
            logger.info(f"Flux image generated: {image_url[:60]}")
            return image_url

    except Exception as e:
        logger.error(f"Flux image generation failed: {e}")

    return None


async def animate_frame(frame_url: str, motion: str, model: str) -> tuple[str, float]:
    """
    Generate real AI video.
    model='wan' → Wan 2.2 T2V 720p (~$0.04/sec) — Medium
    model='kling' → Kling 2.5 Turbo T2V 720p (~$0.07/sec) — Premium
    """
    if not settings.FAL_API_KEY:
        logger.warning("FAL_API_KEY not set — falling back to FFmpeg")
        from app.services.ffmpeg_service import motion_still
        return await motion_still(frame_url, motion)

    duration = 5
    cost = duration * MODEL_COST_PER_SEC.get(model, 0.04)
    fal_client = _get_fal_client()

    text_prompt = (
        f"{motion or 'cinematic professional advertisement scene'}, "
        f"smooth natural movement, high quality commercial video, "
        f"professional lighting, premium brand aesthetic"
    )

    if model == "kling":
        t2v_model = FAL_KLING_T2V
        i2v_model = FAL_KLING_I2V
        t2v_args = {
            "prompt": text_prompt,
            "duration": "5",
            "aspect_ratio": "9:16",
        }
        i2v_args = {
            "prompt": text_prompt,
            "duration": "5",
        }
    else:
        # Wan 2.2
        t2v_model = FAL_WAN_T2V
        i2v_model = FAL_WAN_I2V
        t2v_args = {
            "prompt": text_prompt,
            "duration": "5",
            "resolution": "720p",
            "aspect_ratio": "9:16",
        }
        i2v_args = {
            "prompt": text_prompt,
            "duration": "5",
            "resolution": "720p",
        }

    logger.info(f"Submitting {model.upper()} T2V: {text_prompt[:60]}")

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: fal_client.subscribe(t2v_model, arguments=t2v_args)
        )
        video_url = _extract_video_url(result)
        if video_url:
            logger.info(f"{model.upper()} T2V complete: {video_url[:60]}")
            return video_url, cost
        raise Exception("No video URL in T2V result")

    except Exception as e:
        logger.error(f"{model.upper()} T2V failed: {e} — trying I2V fallback")

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

            i2v_args["image_url"] = public_url
            result2 = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: fal_client.subscribe(i2v_model, arguments=i2v_args)
            )
            video_url = _extract_video_url(result2)
            if video_url:
                logger.info(f"{model.upper()} I2V complete: {video_url[:60]}")
                return video_url, cost

        except Exception as e2:
            logger.error(f"{model.upper()} I2V also failed: {e2}")

    logger.warning("All fal.ai attempts failed — falling back to FFmpeg")
    from app.services.ffmpeg_service import motion_still
    return await motion_still(frame_url, motion)
