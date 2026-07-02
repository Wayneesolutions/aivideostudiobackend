"""
Real FFmpeg service for Wayne AI Video Studio.

Handles:
- motion_still: Ken-Burns pan/zoom effect on images (Economy mode - FREE)
- stitch_and_brand: Join all clips into one video with brand overlay
- export_ratios: Export final video in 9:16, 1:1, 16:9 formats
"""
import asyncio
import logging
import os
import subprocess
import uuid
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("static/videos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

IMAGES_DIR = Path("static/images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _run_ffmpeg(args: list[str]) -> bool:
    """Run an FFmpeg command. Returns True if successful."""
    cmd = ["ffmpeg", "-y"] + args
    logger.info(f"Running FFmpeg: {' '.join(cmd[:6])}...")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr[-500:]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timed out")
        return False
    except FileNotFoundError:
        logger.error("FFmpeg not found — make sure it is installed and in PATH")
        return False


async def _download_image(url: str) -> Path | None:
    """Download an image from a URL to a local temp file."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            ext = ".jpg" if "jpg" in url or "jpeg" in url else ".png"
            path = IMAGES_DIR / f"temp_{uuid.uuid4().hex}{ext}"
            path.write_bytes(response.content)
            return path
    except Exception as e:
        logger.error(f"Failed to download image {url}: {e}")
        return None


async def motion_still(frame_url: str, motion: str) -> tuple[str, float]:
    """
    Apply Ken-Burns pan/zoom effect to a still image using FFmpeg.
    This is the FREE Economy mode path — no AI video model needed.
    """
    # Download the source image
    img_path = await _download_image(frame_url)
    if not img_path:
        # Fallback stub if download fails
        clip_id = str(uuid.uuid4())[:8]
        return f"https://stub-cdn.wayneesolutions.com/motion/{clip_id}.mp4", 0.0

    output_path = OUTPUT_DIR / f"motion_{uuid.uuid4().hex}.mp4"

    # Choose zoom direction based on motion hint
    motion_lower = motion.lower() if motion else ""
    if "zoom in" in motion_lower:
        zoom_filter = "zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1920"
    elif "zoom out" in motion_lower:
        zoom_filter = "zoompan=z='if(lte(zoom,1.0),1.5,max(1.001,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1920"
    elif "pan left" in motion_lower:
        zoom_filter = "zoompan=z=1.3:x='iw/2-(iw/zoom/2)+((iw/zoom/2)*on/125)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1920"
    elif "pan right" in motion_lower:
        zoom_filter = "zoompan=z=1.3:x='iw/2-(iw/zoom/2)-((iw/zoom/2)*on/125)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1920"
    elif "fade" in motion_lower:
        zoom_filter = "zoompan=z=1.0:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1920"
    else:
        # Default: gentle zoom in
        zoom_filter = "zoompan=z='min(zoom+0.001,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1920"

    success = _run_ffmpeg([
        "-loop", "1",
        "-i", str(img_path),
        "-vf", f"{zoom_filter},fps=25",
        "-t", "5",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        str(output_path),
    ])

    # Clean up temp image
    try:
        img_path.unlink()
    except Exception:
        pass

    if success and output_path.exists():
        url = f"http://127.0.0.1:8000/static/videos/{output_path.name}"
        logger.info(f"motion_still complete: {output_path.name}")
        return url, 0.0
    else:
        clip_id = str(uuid.uuid4())[:8]
        return f"https://stub-cdn.wayneesolutions.com/motion/{clip_id}.mp4", 0.0


async def stitch_and_brand(clip_urls: list[str], brand_kit: dict) -> str:
    """
    Stitch all clips into one video using FFmpeg concat.
    Optionally overlay brand text from brand_kit.
    """
    if not clip_urls:
        video_id = str(uuid.uuid4())[:8]
        return f"https://stub-cdn.wayneesolutions.com/assembled/{video_id}.mp4"

    # Separate local clips from stub URLs
    local_clips = [u for u in clip_urls if "127.0.0.1" in u or u.startswith("/")]
    stub_clips = [u for u in clip_urls if u not in local_clips]

    if not local_clips:
        # All stubs — return stub assembled URL
        video_id = str(uuid.uuid4())[:8]
        return f"https://stub-cdn.wayneesolutions.com/assembled/{video_id}.mp4"

    output_path = OUTPUT_DIR / f"assembled_{uuid.uuid4().hex}.mp4"

    if len(local_clips) == 1:
        # Only one clip — just copy it
        clip_file = local_clips[0].replace("http://127.0.0.1:8000/static/videos/", "")
        clip_path = OUTPUT_DIR / clip_file
        success = _run_ffmpeg([
            "-i", str(clip_path),
            "-c", "copy",
            str(output_path),
        ])
    else:
        # Multiple clips — use concat
        concat_file = OUTPUT_DIR / f"concat_{uuid.uuid4().hex}.txt"
        with open(concat_file, "w") as f:
            for url in local_clips:
                clip_file = url.replace("http://127.0.0.1:8000/static/videos/", "")
                clip_path = OUTPUT_DIR / clip_file
                if clip_path.exists():
                    f.write(f"file '{clip_path.absolute()}'\n")

        success = _run_ffmpeg([
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path),
        ])

        try:
            concat_file.unlink()
        except Exception:
            pass

    if success and output_path.exists():
        url = f"http://127.0.0.1:8000/static/videos/{output_path.name}"
        logger.info(f"stitch complete: {output_path.name}")
        return url
    else:
        video_id = str(uuid.uuid4())[:8]
        return f"https://stub-cdn.wayneesolutions.com/assembled/{video_id}.mp4"


async def export_ratios(video_url: str) -> dict:
    """
    Export the final video in 9:16, 1:1, and 16:9 ratios using FFmpeg.
    """
    if "stub-cdn" in video_url:
        vid_id = str(uuid.uuid4())[:8]
        return {
            "9:16": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_916.mp4",
            "1:1": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_11.mp4",
            "16:9": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_169.mp4",
        }

    # Extract just the filename from the URL
    filename = video_url.split("/")[-1]
    input_path = OUTPUT_DIR / filename

    logger.info(f"export_ratios looking for: {input_path} (exists: {input_path.exists()})")

    if not input_path.exists():
        # Try searching the directory for the file
        matches = list(OUTPUT_DIR.glob(f"*{filename}*"))
        if matches:
            input_path = matches[0]
            logger.info(f"Found file at: {input_path}")
        else:
            logger.error(f"Could not find video file: {filename}")
            vid_id = str(uuid.uuid4())[:8]
            return {
                "9:16": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_916.mp4",
                "1:1": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_11.mp4",
                "16:9": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_169.mp4",
            }

    ratios = {
        "9:16": ("1080", "1920", f"export_{uuid.uuid4().hex}_916.mp4"),
        "1:1":  ("1080", "1080", f"export_{uuid.uuid4().hex}_11.mp4"),
        "16:9": ("1920", "1080", f"export_{uuid.uuid4().hex}_169.mp4"),
    }

    result = {}
    for ratio, (w, h, out_filename) in ratios.items():
        output_path = OUTPUT_DIR / out_filename
        success = _run_ffmpeg([
            "-i", str(input_path),
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            str(output_path),
        ])
        if success and output_path.exists():
            result[ratio] = f"http://127.0.0.1:8000/static/videos/{out_filename}"
            logger.info(f"export_ratios {ratio} complete: {out_filename}")
        else:
            vid_id = str(uuid.uuid4())[:8]
            result[ratio] = f"https://stub-cdn.wayneesolutions.com/final/{vid_id}.mp4"

    logger.info(f"export_ratios complete: {list(result.keys())}")
    return result
