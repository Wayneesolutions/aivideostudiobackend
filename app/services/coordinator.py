import asyncio
import logging

from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.job import ClipStatus, FrameStatus, Job, JobState, RenderType, Shot
from app.services.openai_service import (
    estimate_cost, generate_frame,
    make_shotlist,
)
from app.services.ffmpeg_service import (
    motion_still, stitch_and_brand, export_ratios,
)
from app.services.fal_service import animate_frame

logger = logging.getLogger(__name__)


def _set_state(db: Session, job: Job, state: JobState):
    job.state = state
    db.commit()
    logger.info(f"Job {job.id} -> {state}")


async def run_planning(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        _set_state(db, job, JobState.PLANNING)

        # Check if brief mentions reference image — analyze it if so
        enhanced_brief = job.brief_text
        if "Reference image provided by client" in job.brief_text:
            logger.info(f"Job {job.id} has reference image — vision analysis would enhance planning")
            # Note: actual image data not stored in DB for security
            # Brief already enhanced on frontend before job creation

        shots_data = await make_shotlist(enhanced_brief, job.mode.value, job.num_shots)
        for s in shots_data:
            db.add(Shot(
                job_id=job.id,
                idx=s["idx"],
                description=s["description"],
                motion=s.get("motion", ""),
                duration_sec=s.get("duration_sec", 5),
                render_type=s["render_type"],
                model=s.get("model", "ffmpeg"),
            ))
        job.est_cost = await estimate_cost(job.mode.value)
        db.commit()
        _set_state(db, job, JobState.SHOTLIST_READY)
    finally:
        db.close()


async def run_generating_frames(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        _set_state(db, job, JobState.GENERATING_FRAMES)

        async def gen(shot: Shot):
            try:
                shot.frame_url = await generate_frame(shot.description)
                shot.frame_status = FrameStatus.ready
            except Exception as e:
                logger.error(f"Frame failed for shot {shot.id}: {e}")
                shot.frame_status = FrameStatus.failed

        await asyncio.gather(*[gen(s) for s in job.shots])
        db.commit()
        _set_state(db, job, JobState.FRAMES_READY)
    finally:
        db.close()


async def run_rendering_motion(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        _set_state(db, job, JobState.RENDERING_MOTION)

        async def render(shot: Shot):
            try:
                # Smart Video Studio always uses FFmpeg (free, fast, predictable)
                # Create Video uses fal.ai Kling/Wan for real AI animation
                from app.models.job import JobType
                use_ffmpeg = (job.job_type == JobType.smart_video)

                if not use_ffmpeg and shot.render_type == RenderType.animate:
                    url, cost = await animate_frame(shot.frame_url, shot.motion, shot.model)
                else:
                    total = len(job.shots)
                    url, cost = await motion_still(shot.frame_url, shot.motion, shot.idx, total)
                shot.clip_url = url
                shot.clip_status = ClipStatus.ready
                shot.cost = cost
            except Exception as e:
                logger.error(f"Render failed for shot {shot.id}: {e}")
                shot.clip_status = ClipStatus.failed

        await asyncio.gather(*[render(s) for s in job.shots])
        db.commit()
        _set_state(db, job, JobState.CLIPS_READY)
    finally:
        db.close()


async def run_assembling(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        _set_state(db, job, JobState.ASSEMBLING)

        clip_urls = [s.clip_url for s in job.shots if s.clip_url]
        brand_kit = job.client.brand_kit or {}
        assembled_url = await stitch_and_brand(clip_urls, brand_kit)

        _set_state(db, job, JobState.EXPORTING)

        # Download logo if provided for FFmpeg watermark
        logo_path = None
        if job.logo_url:
            try:
                import httpx
                from pathlib import Path
                logo_dir = Path("static/logos")
                logo_dir.mkdir(parents=True, exist_ok=True)
                logo_file = logo_dir / f"logo_{job.id[:8]}.png"
                if not logo_file.exists():
                    if job.logo_url.startswith("data:"):
                        import base64
                        header, data = job.logo_url.split(",", 1)
                        logo_file.write_bytes(base64.b64decode(data))
                    else:
                        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                            resp = await client.get(job.logo_url)
                            resp.raise_for_status()
                            logo_file.write_bytes(resp.content)
                logo_path = str(logo_file)
                logger.info(f"Logo ready for watermark: {logo_path}")
            except Exception as e:
                logger.error(f"Failed to download logo: {e}")

        final_urls = await export_ratios(
            assembled_url,
            logo_path=logo_path,
            overlay_text=job.overlay_text,
            overlay_color=job.overlay_color or "#FFFFFF",
        )
        job.cost_total = sum(float(s.cost or 0) for s in job.shots)
        job.final_urls = final_urls
        _set_state(db, job, JobState.DONE)
    finally:
        db.close()


async def regenerate_shot(job_id: str, shot_idx: int, modifier: str = ""):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        shot = next((s for s in job.shots if s.idx == shot_idx), None)
        if not shot:
            return
        shot.version += 1
        if modifier:
            shot.description = f"{shot.description} [{modifier}]"
        shot.frame_url = await generate_frame(shot.description)
        shot.frame_status = FrameStatus.ready
        db.commit()
    finally:
        db.close()


def run_async(coro):
    """Helper for FastAPI BackgroundTasks, which expects sync callables."""
    asyncio.run(coro)
