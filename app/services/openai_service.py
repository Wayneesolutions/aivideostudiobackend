"""
Real OpenAI integration for Wayne AI Video Studio.

Replaces the stub functions for:
- make_shotlist: GPT-4o mini reads the brief and plans shots intelligently
- generate_frame: gpt-image-1 generates real keyframe images

animate_frame, motion_still, stitch_and_brand, export_ratios
are still stubbed until fal.ai and FFmpeg are connected.
"""
import asyncio
import json
import logging
import uuid
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

BUDGET_CAPS = {
    "economy": 1.50,
    "standard": 3.00,
    "premium": 5.00,
}

ROUTING = {
    "economy":  {"animate_count": 1,  "model": "wan"},    # 1 Wan shot, rest FFmpeg free
    "standard": {"animate_count": 99, "model": "wan"},    # All shots Wan 2.2 T2V 720p
    "premium":  {"animate_count": 99, "model": "kling"},  # All shots Kling 2.5 Turbo 720p
}

SYSTEM_PROMPT = """You are a professional video production planner for Wayne E Solutions, 
a social media video agency. Your job is to read a client brief and produce a precise shot list.

Rules you MUST follow:
- Always produce exactly 3 to 5 shots.
- Each shot gets a 'render_type': either 'animate' (real AI video, costs money) or 'motion_still' (free FFmpeg Ken-Burns).
- Economy mode: ONLY 1 shot can be 'animate' (the hero shot). All others must be 'motion_still'.
- Standard mode: All shots can be 'animate'. Use 'wan' for most, 'kling' for the hero shot.
- Premium mode: All shots 'animate' with 'kling' model throughout.
- Shot descriptions must be specific, visual, and match the brief's mood, colors, and product.
- Always end with a branded CTA/end-card shot.
- Return ONLY valid JSON — no explanation, no markdown, no extra text.

Return this exact JSON structure:
[
  {
    "idx": 0,
    "description": "specific visual description for the keyframe image",
    "motion": "camera motion e.g. slow zoom in, pan left, fade in",
    "duration_sec": 5,
    "render_type": "animate or motion_still",
    "model": "wan, kling, or ffmpeg"
  }
]"""


def _get_client() -> AsyncOpenAI:
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in .env")
    return AsyncOpenAI(api_key=api_key)


async def analyze_reference_image(image_data_url: str) -> str:
    """
    Use GPT-4o mini vision to analyze a reference image and describe it
    for use in shot planning.
    """
    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_url}
                        },
                        {
                            "type": "text",
                            "text": (
                                "You are a professional advertising photographer analyzing a product/brand image. "
                                "Describe this image in detail for a video production team. Include: "
                                "1) What the product/subject is, "
                                "2) Key visual elements (colors, textures, shapes), "
                                "3) Brand style (luxury, casual, etc.), "
                                "4) Suggested camera angles and shots that would showcase it best. "
                                "Keep it concise — 3-4 sentences max."
                            )
                        }
                    ]
                }
            ],
            max_tokens=200,
        )
        description = response.choices[0].message.content.strip()
        logger.info(f"GPT vision analyzed reference image: {description[:80]}")
        return description
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        return ""


async def make_shotlist(brief: str, mode: str, num_shots: int = 4) -> list[dict]:
    """Use GPT-4o mini to intelligently plan shots from the brief."""
    client = _get_client()
    routing = ROUTING.get(mode, ROUTING["economy"])
    # Clamp num_shots between 1 and 8
    num_shots = max(1, min(8, num_shots))

    user_message = f"""
Client Brief: {brief}

Quality Mode: {mode.upper()}
Budget Cap: ${BUDGET_CAPS.get(mode, 1.50)}
Number of shots required: EXACTLY {num_shots} shots (no more, no less)
Animate quota: {"1 shot only (hero shot)" if mode == "economy" else "all shots"}
Default video model: {routing["model"]}

Plan exactly {num_shots} shots now.
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=800,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if GPT wraps in them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        shots = json.loads(raw)

        # Enforce routing policy — GPT sometimes ignores the rules
        animate_count = routing["animate_count"]
        animated = 0
        for shot in shots:
            if shot.get("render_type") == "animate":
                if animated < animate_count:
                    shot["model"] = routing["model"]
                    animated += 1
                else:
                    # Over quota — convert to motion_still
                    shot["render_type"] = "motion_still"
                    shot["model"] = "ffmpeg"
            else:
                shot["render_type"] = "motion_still"
                shot["model"] = "ffmpeg"

        logger.info(f"GPT planned {len(shots)} shots for mode={mode}")
        return shots

    except json.JSONDecodeError as e:
        logger.error(f"GPT returned invalid JSON: {e}. Raw: {raw[:200]}")
        return _fallback_shotlist(brief, mode, num_shots)
    except Exception as e:
        logger.error(f"make_shotlist failed: {e}")
        return _fallback_shotlist(brief, mode, num_shots)


def _fallback_shotlist(brief: str, mode: str, num_shots: int = 4) -> list[dict]:
    """Fallback hardcoded shotlist if GPT fails."""
    routing = ROUTING.get(mode, ROUTING["economy"])
    all_shots = [
        {"idx": 0, "description": f"Opening shot — {brief[:80]}", "motion": "slow zoom in", "duration_sec": 5},
        {"idx": 1, "description": "Product hero shot — close up detail", "motion": "pan left", "duration_sec": 5},
        {"idx": 2, "description": "Lifestyle context shot", "motion": "slow zoom out", "duration_sec": 5},
        {"idx": 3, "description": "Brand end-card with call to action", "motion": "fade in", "duration_sec": 5},
        {"idx": 4, "description": "Final product reveal", "motion": "slow zoom in", "duration_sec": 5},
    ]
    shots = all_shots[:num_shots]
    animate_count = routing["animate_count"]
    for i, shot in enumerate(shots):
        if i < animate_count:
            shot["render_type"] = "animate"
            shot["model"] = routing["model"]
        else:
            shot["render_type"] = "motion_still"
            shot["model"] = "ffmpeg"
    return shots


async def estimate_cost(mode: str) -> float:
    """Estimate job cost based on mode."""
    rates = {"economy": 1.35, "standard": 2.80, "premium": 4.75}
    return rates.get(mode, 1.35)


async def generate_frame(description: str) -> str:
    """
    Generate a keyframe image.
    Uses fal.ai Flux first (~$0.003/image - cheapest)
    Falls back to DALL-E 2 (~$0.02/image) if Flux fails
    Falls back to picsum if both fail
    """
    # Try Flux first (cheapest)
    try:
        from app.services.fal_service import generate_image_flux
        flux_url = await generate_image_flux(description)
        if flux_url:
            logger.info(f"Flux image generated for: {description[:60]}")
            return flux_url
    except Exception as e:
        logger.warning(f"Flux failed, trying DALL-E 2: {e}")

    # Fallback to DALL-E 2
    client = _get_client()
    try:
        response = await client.images.generate(
            model="dall-e-2",
            prompt=description[:1000],
            n=1,
            size="1024x1024",
        )
        image_url = response.data[0].url
        logger.info(f"DALL-E 2 image generated for: {description[:60]}")
        return image_url

    except Exception as e:
        logger.error(f"generate_frame failed: {e}")
        seed = abs(hash(description)) % 1000
        return f"https://picsum.photos/seed/{seed}/1024/1024"


# ── Still stubbed — fal.ai and FFmpeg not connected yet ───────────────────────

async def animate_frame(frame_url: str, motion: str, model: str) -> tuple[str, float]:
    """STUB — will be replaced with fal.ai when key is available."""
    await asyncio.sleep(0.5)
    clip_id = str(uuid.uuid4())[:8]
    cost = {"wan": 0.30, "kling": 0.55, "veo": 0.90}.get(model, 0.30)
    return f"https://stub-cdn.wayneesolutions.com/clips/{clip_id}.mp4", cost


async def motion_still(frame_url: str, motion: str) -> tuple[str, float]:
    """STUB — will be replaced with FFmpeg Ken-Burns when installed."""
    await asyncio.sleep(0.3)
    clip_id = str(uuid.uuid4())[:8]
    return f"https://stub-cdn.wayneesolutions.com/motion/{clip_id}.mp4", 0.0


async def stitch_and_brand(clip_urls: list[str], brand_kit: dict) -> str:
    """STUB — will be replaced with FFmpeg stitching."""
    await asyncio.sleep(0.5)
    video_id = str(uuid.uuid4())[:8]
    return f"https://stub-cdn.wayneesolutions.com/assembled/{video_id}.mp4"


async def export_ratios(video_url: str) -> dict:
    """STUB — will be replaced with FFmpeg ratio export."""
    await asyncio.sleep(0.3)
    vid_id = str(uuid.uuid4())[:8]
    return {
        "9:16": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_916.mp4",
        "1:1":  f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_11.mp4",
        "16:9": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_169.mp4",
    }
