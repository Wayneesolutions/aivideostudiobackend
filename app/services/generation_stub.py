"""
Placeholder AI generation functions.

These are stand-ins for the real providers (OpenAI image gen, Vidu AI,
PixVerse, ElevenLabs, FFmpeg) that will be wired in later. Every function
here returns realistic fake data so the full job pipeline can run end to
end before any paid API keys are connected.

When ready to go live, swap the body of each function for a real API call —
the function signatures and return shapes are designed to stay the same.
"""
import asyncio
import uuid

BUDGET_CAPS = {
    "economy": 1.50,
    "standard": 3.00,
    "premium": 5.00,
}

ROUTING = {
    "economy": {"animate_count": 1, "model": "wan"},
    "standard": {"animate_count": 99, "model": "kling"},
    "premium": {"animate_count": 99, "model": "kling"},
}


async def make_shotlist(brief: str, mode: str) -> list[dict]:
    await asyncio.sleep(0.5)
    routing = ROUTING[mode]
    shots = [
        {"idx": 0, "description": f"Opening shot — {brief[:60]}", "motion": "slow zoom in", "duration_sec": 5},
        {"idx": 1, "description": "Product hero shot — close up", "motion": "pan left", "duration_sec": 4},
        {"idx": 2, "description": "Lifestyle context shot", "motion": "slow zoom out", "duration_sec": 5},
        {"idx": 3, "description": "Brand end-card with CTA", "motion": "fade in", "duration_sec": 3},
    ]
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
    rates = {"economy": 1.35, "standard": 2.80, "premium": 4.75}
    return rates.get(mode, 1.35)


async def generate_frame(description: str) -> str:
    await asyncio.sleep(0.5)
    seed = abs(hash(description)) % 1000
    return f"https://picsum.photos/seed/{seed}/1080/1920"


async def animate_frame(frame_url: str, motion: str, model: str) -> tuple[str, float]:
    await asyncio.sleep(0.5)
    clip_id = str(uuid.uuid4())[:8]
    cost = {"wan": 0.30, "kling": 0.55, "veo": 0.90}.get(model, 0.30)
    return f"https://stub-cdn.wayneesolutions.com/clips/{clip_id}.mp4", cost


async def motion_still(frame_url: str, motion: str) -> tuple[str, float]:
    await asyncio.sleep(0.3)
    clip_id = str(uuid.uuid4())[:8]
    return f"https://stub-cdn.wayneesolutions.com/motion/{clip_id}.mp4", 0.0


async def stitch_and_brand(clip_urls: list[str], brand_kit: dict) -> str:
    await asyncio.sleep(0.5)
    video_id = str(uuid.uuid4())[:8]
    return f"https://stub-cdn.wayneesolutions.com/assembled/{video_id}.mp4"


async def export_ratios(video_url: str) -> dict:
    await asyncio.sleep(0.3)
    vid_id = str(uuid.uuid4())[:8]
    return {
        "9:16": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_916.mp4",
        "1:1": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_11.mp4",
        "16:9": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_169.mp4",
    }
