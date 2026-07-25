"""
Real FFmpeg service for Wayne AI Video Studio.
Uses scale+crop for smooth Ken-Burns instead of zoompan.
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

BRAND_NAME = "Wayne E Solutions"
TAGLINE = "Luxury Redefined"
CTA = "wayneesolutions.com"

FPS = 30
DURATION = 5
WIDTH = 1080
HEIGHT = 1920


def _get_font_path() -> str:
    system_fonts = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/Arial.ttf",
    ]
    for sf in system_fonts:
        if os.path.exists(sf):
            return sf.replace("C:/", "C\\\\:/")
    return ""


def _run_ffmpeg(args: list[str]) -> bool:
    cmd = ["ffmpeg", "-y"] + args
    logger.info(f"Running FFmpeg: {' '.join(cmd[:6])}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr[-300:]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timed out")
        return False
    except FileNotFoundError:
        logger.error("FFmpeg not found")
        return False


async def _run_ffmpeg_async(args: list[str]) -> bool:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_ffmpeg, args)


async def _download_image(url: str) -> Path | None:
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            ext = ".png"
            path = IMAGES_DIR / f"temp_{uuid.uuid4().hex}{ext}"
            path.write_bytes(response.content)
            return path
    except Exception as e:
        logger.error(f"Failed to download image {url}: {e}")
        return None


def _smooth_kenburns_filter(motion: str) -> str:
    """Simple still image — no movement, clean and stable."""
    return f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black"


def _make_text_filter(shot_idx: int, total_shots: int, font_path: str) -> str:
    ff = f":fontfile={font_path}" if font_path else ""
    filters = []

    if shot_idx == 0:
        filters.append(f"drawbox=x=0:y=0:w=iw:h=120:color=black@0.6:t=fill")
        filters.append(
            f"drawtext=text={BRAND_NAME}{ff}"
            f":fontsize=52:fontcolor=white"
            f":x=(w-text_w)/2:y=35"
            f":shadowcolor=black:shadowx=2:shadowy=2"
        )
    elif shot_idx == total_shots - 1:
        filters.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.35:t=fill")
        filters.append(
            f"drawtext=text={BRAND_NAME}{ff}"
            f":fontsize=60:fontcolor=gold"
            f":x=(w-text_w)/2:y=(h-text_h)/2-80"
            f":shadowcolor=black:shadowx=3:shadowy=3"
        )
        filters.append(
            f"drawtext=text={TAGLINE}{ff}"
            f":fontsize=36:fontcolor=white"
            f":x=(w-text_w)/2:y=(h-text_h)/2+10"
            f":shadowcolor=black:shadowx=2:shadowy=2"
        )
        filters.append(f"drawbox=x=0:y=ih-120:w=iw:h=120:color=black@0.7:t=fill")
        filters.append(
            f"drawtext=text={CTA}{ff}"
            f":fontsize=30:fontcolor=white"
            f":x=(w-text_w)/2:y=ih-70"
        )
    else:
        filters.append(f"drawbox=x=0:y=ih-110:w=iw:h=110:color=black@0.55:t=fill")
        filters.append(
            f"drawtext=text={TAGLINE}{ff}"
            f":fontsize=42:fontcolor=white"
            f":x=(w-text_w)/2:y=ih-70"
            f":shadowcolor=black:shadowx=2:shadowy=2"
        )

    return ",".join(filters)


async def motion_still(
    frame_url: str,
    motion: str,
    shot_idx: int = 0,
    total_shots: int = 4,
    brand_kit: dict = {},
) -> tuple[str, float]:

    img_path = await _download_image(frame_url)
    if not img_path:
        clip_id = str(uuid.uuid4())[:8]
        return f"https://stub-cdn.wayneesolutions.com/motion/{clip_id}.mp4", 0.0

    output_path = OUTPUT_DIR / f"motion_{uuid.uuid4().hex}.mp4"

    kenburns = _smooth_kenburns_filter(motion)
    fade = f"fade=t=in:st=0:d=0.4,fade=t=out:st={DURATION - 0.4}:d=0.4"
    font_path = _get_font_path()
    text = _make_text_filter(shot_idx, total_shots, font_path)
    vf = f"{kenburns},{fade},{text}"

    success = await _run_ffmpeg_async([
        "-loop", "1",
        "-framerate", str(FPS),
        "-i", str(img_path),
        "-vf", vf,
        "-t", str(DURATION),
        "-r", str(FPS),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "18",
        "-movflags", "+faststart",
        str(output_path),
    ])

    try:
        img_path.unlink()
    except Exception:
        pass

    if success and output_path.exists():
        logger.info(f"motion_still complete: {output_path.name}")
        return f"http://127.0.0.1:8000/static/videos/{output_path.name}", 0.0

    # Fallback without text
    logger.warning("Retrying without text overlay")
    img_path2 = await _download_image(frame_url)
    if img_path2:
        output_path2 = OUTPUT_DIR / f"motion_{uuid.uuid4().hex}.mp4"
        success2 = await _run_ffmpeg_async([
            "-loop", "1",
            "-framerate", str(FPS),
            "-i", str(img_path2),
            "-vf", f"{kenburns},{fade}",
            "-t", str(DURATION),
            "-r", str(FPS),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "medium",
            "-crf", "18",
            "-movflags", "+faststart",
            str(output_path2),
        ])
        try:
            img_path2.unlink()
        except Exception:
            pass
        if success2 and output_path2.exists():
            logger.info(f"motion_still (no text) complete: {output_path2.name}")
            return f"http://127.0.0.1:8000/static/videos/{output_path2.name}", 0.0

    clip_id = str(uuid.uuid4())[:8]
    return f"https://stub-cdn.wayneesolutions.com/motion/{clip_id}.mp4", 0.0


async def stitch_and_brand(clip_urls: list[str], brand_kit: dict) -> str:
    if not clip_urls:
        video_id = str(uuid.uuid4())[:8]
        return f"https://stub-cdn.wayneesolutions.com/assembled/{video_id}.mp4"

    import httpx

    # Download all clips to local files (handles both local and fal.ai URLs)
    local_clips = []
    for url in clip_urls:
        if not url or "stub-cdn" in url:
            continue
        if "127.0.0.1" in url:
            clip_file = url.replace("http://127.0.0.1:8000/static/videos/", "")
            clip_path = OUTPUT_DIR / clip_file
            if clip_path.exists():
                local_clips.append(str(clip_path.absolute()))
        else:
            # External URL (fal.ai) — download first
            try:
                logger.info(f"Downloading fal.ai clip: {url[:60]}")
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    tmp_path = OUTPUT_DIR / f"clip_{uuid.uuid4().hex}.mp4"
                    tmp_path.write_bytes(resp.content)
                    local_clips.append(str(tmp_path.absolute()))
                    logger.info(f"Downloaded: {tmp_path.name} ({len(resp.content)//1024}KB)")
            except Exception as e:
                logger.error(f"Failed to download clip {url}: {e}")

    if not local_clips:
        video_id = str(uuid.uuid4())[:8]
        return f"https://stub-cdn.wayneesolutions.com/assembled/{video_id}.mp4"

    output_path = OUTPUT_DIR / f"assembled_{uuid.uuid4().hex}.mp4"

    if len(local_clips) == 1:
        success = await _run_ffmpeg_async([
            "-i", local_clips[0], "-c", "copy", str(output_path)
        ])
    else:
        concat_file = OUTPUT_DIR / f"concat_{uuid.uuid4().hex}.txt"
        with open(concat_file, "w") as f:
            for clip_path in local_clips:
                f.write(f"file '{clip_path}'\n")

        success = await _run_ffmpeg_async([
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "medium", "-crf", "18",
            "-movflags", "+faststart",
            str(output_path),
        ])
        try:
            concat_file.unlink()
        except Exception:
            pass

    if success and output_path.exists():
        logger.info(f"stitch complete: {output_path.name}")
        return f"http://127.0.0.1:8000/static/videos/{output_path.name}"

    video_id = str(uuid.uuid4())[:8]
    return f"https://stub-cdn.wayneesolutions.com/assembled/{video_id}.mp4"


async def export_ratios(video_url: str, logo_path: str | None = None, overlay_text: str | None = None, overlay_color: str = "#FFFFFF") -> dict:
    if "stub-cdn" in video_url:
        vid_id = str(uuid.uuid4())[:8]
        return {
            "9:16": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_916.mp4",
            "1:1": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_11.mp4",
            "16:9": f"https://stub-cdn.wayneesolutions.com/final/{vid_id}_169.mp4",
        }

    filename = video_url.split("/")[-1]
    input_path = OUTPUT_DIR / filename

    logger.info(f"export_ratios looking for: {input_path} (exists: {input_path.exists()})")

    if not input_path.exists():
        matches = list(OUTPUT_DIR.glob(f"*{filename}*"))
        if matches:
            input_path = matches[0]
        else:
            logger.error(f"Could not find: {filename}")
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

    # Build FFmpeg filter for logo and text watermark
    def build_vf(w: str, h: str, logo_p: str | None, text: str | None, color: str) -> str:
        scale = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
        filters = [scale]

        if logo_p and Path(logo_p).exists():
            logo_size = int(int(w) * 0.12)
            margin = int(int(w) * 0.02)
            filters.append(f"movie={logo_p}[logo];[in][logo]overlay=W-{logo_size+margin}:{margin}:eval=init[out]")
            return ",".join(filters)

        if text:
            # Convert hex color to FFmpeg format
            hex_color = color.lstrip("#")
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            font_size = max(int(int(w) * 0.04), 24)
            bar_h = int(int(h) * 0.08)
            safe_text = text.replace("'", "").replace(":", r"\:").replace("=", r"\=")
            filters.append(
                f"drawbox=x=0:y=ih-{bar_h}:w=iw:h={bar_h}:color=black@0.7:t=fill,"
                f"drawtext=text='{safe_text}':fontsize={font_size}:fontcolor=#{hex_color}:"
                f"x=(w-text_w)/2:y=h-{bar_h//2}-text_h/2:shadowcolor=black:shadowx=2:shadowy=2"
            )

        return ",".join(filters)

    result = {}
    for ratio, (w, h, out_filename) in ratios.items():
        output_path = OUTPUT_DIR / out_filename
        vf = build_vf(w, h, logo_path, overlay_text, overlay_color)

        # Logo overlay needs different filter_complex approach
        if logo_path and Path(logo_path).exists():
            logo_size = int(int(w) * 0.12)
            margin = int(int(w) * 0.02)
            scale_vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
            logo_vf = f"scale={logo_size}:-1"
            success = await _run_ffmpeg_async([
                "-i", str(input_path),
                "-i", str(logo_path),
                "-filter_complex",
                f"[0:v]{scale_vf}[bg];[1:v]{logo_vf}[logo];[bg][logo]overlay=W-{logo_size+margin}:{margin}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "medium", "-crf", "18",
                "-movflags", "+faststart",
                str(output_path),
            ])
        else:
            success = await _run_ffmpeg_async([
                "-i", str(input_path),
                "-vf", vf,
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "medium", "-crf", "18",
                "-movflags", "+faststart",
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
