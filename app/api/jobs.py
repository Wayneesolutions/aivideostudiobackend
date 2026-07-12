import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.database.session import get_db
from app.models.client import Client
from app.models.job import Job, JobState
from app.schemas.job import ChatMessageRequest, CreateJobRequest
from app.services import coordinator
from app.services.activity_service import log_activity
from app.services.openai_service import BUDGET_CAPS
from app.services.intent_parser import parse_intent

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.post("/")
def create_job(
    req: CreateJobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    client = db.query(Client).filter(Client.id == req.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    job = Job(
        client_id=req.client_id,
        job_type=req.job_type,
        name=req.name,
        brief_text=req.brief_text,
        mode=req.mode,
        budget_cap=BUDGET_CAPS[req.mode.value],
        thread_id=req.thread_id or str(uuid.uuid4()),
        state=JobState.CREATED,
        num_shots=req.num_shots,
        logo_url=req.logo_url,
        overlay_text=req.overlay_text,
        overlay_color=req.overlay_color,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    log_activity(
        db,
        action="job_created",
        description=f"Project '{job.name}' created",
        entity_type="job",
        entity_id=job.id,
    )

    background_tasks.add_task(coordinator.run_async, coordinator.run_planning(job.id))

    return {
        "job_id": job.id,
        "state": job.state,
        "thread_id": job.thread_id,
        "message": "Job created — planning started",
    }


@router.get("/")
def list_jobs(
    search: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    query = db.query(Job)

    if search:
        query = query.filter(Job.name.ilike(f"%{search}%"))
    if state:
        query = query.filter(Job.state == state.upper())
    if job_type:
        query = query.filter(Job.job_type == job_type.lower())

    total = query.count()
    jobs = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_job_summary(j) for j in jobs],
    }


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_detail(job)


@router.patch("/{job_id}/shots")
def update_shot_frames(
    job_id: str,
    frame_updates: list[dict],
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Update shot frame_urls with branded/overlaid images."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for update in frame_updates:
        shot_idx = update.get("idx")
        new_url = update.get("frame_url")
        if shot_idx is not None and new_url:
            for shot in job.shots:
                if shot.idx == shot_idx:
                    shot.frame_url = new_url
                    break
    db.commit()
    return {"message": "Shot frames updated"}



def update_job_mode(
    job_id: str,
    mode: str,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    from app.models.client import QualityMode
    from app.services.openai_service import BUDGET_CAPS
    try:
        job.mode = QualityMode(mode)
        job.budget_cap = BUDGET_CAPS.get(mode, 1.50)
        db.commit()
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
    return {"message": f"Mode updated to {mode}", "mode": mode}


@router.delete("/{job_id}")
def delete_job(
    job_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    name = job.name
    db.delete(job)
    db.commit()

    log_activity(
        db,
        action="job_deleted",
        description=f"Project '{name}' deleted",
        entity_type="job",
        entity_id=job_id,
    )

    return {"message": f"Job '{name}' deleted successfully"}




@router.patch("/{job_id}/shots/{shot_idx}/frame")
def update_shot_frame(
    job_id: str,
    shot_idx: int,
    frame_url: str,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Update a shot's frame URL with a branded/overlaid version."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    shot = next((s for s in job.shots if s.idx == shot_idx), None)
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    shot.frame_url = frame_url
    db.commit()
    return {"message": "Frame URL updated", "shot_idx": shot_idx}



@router.post("/{job_id}/message")
def post_message(
    job_id: str,
    req: ChatMessageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    action = parse_intent(req.message, job.state.value)

    if action.type == "approve":
        if job.state == JobState.SHOTLIST_READY:
            background_tasks.add_task(coordinator.run_async, coordinator.run_generating_frames(job.id))
            return {"action": "approve", "message": "Generating frames now..."}
        if job.state == JobState.FRAMES_READY:
            background_tasks.add_task(coordinator.run_async, coordinator.run_rendering_motion(job.id))
            est = float(job.est_cost or 0)
            return {"action": "approve", "message": f"Rendering video — est cost ${est:.2f}"}
        if job.state == JobState.CLIPS_READY:
            background_tasks.add_task(coordinator.run_async, coordinator.run_assembling(job.id))
            return {"action": "approve", "message": "Assembling with branding..."}

    if action.type in ("regenerate_shot", "edit_shot"):
        if action.shot_idx is None:
            return {"action": "clarify", "message": "Which shot? e.g. 'shot 2 brighter'"}
        background_tasks.add_task(
            coordinator.run_async,
            coordinator.regenerate_shot(job.id, action.shot_idx, action.modifier or ""),
        )
        return {
            "action": action.type,
            "shot_idx": action.shot_idx,
            "message": f"Re-doing shot {action.shot_idx + 1}...",
        }

    if action.type == "cancel":
        job.state = JobState.FAILED
        db.commit()
        log_activity(db, "job_cancelled", f"Project '{job.name}' cancelled", "job", job.id)
        return {"action": "cancel", "message": "Job cancelled."}

    return {"action": "clarify", "message": "Try: 'yes go ahead', 'shot 2 brighter', or 'cancel'"}


def _job_summary(job: Job) -> dict:
    return {
        "job_id": job.id,
        "name": job.name,
        "job_type": job.job_type,
        "state": job.state,
        "mode": job.mode,
        "est_cost": float(job.est_cost or 0),
        "cost_total": float(job.cost_total or 0),
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def _job_detail(job: Job) -> dict:
    return {
        **_job_summary(job),
        "brief_text": job.brief_text,
        "budget_cap": float(job.budget_cap),
        "thread_id": job.thread_id,
        "final_urls": job.final_urls,
        "shots": [
            {
                "idx": s.idx,
                "description": s.description,
                "render_type": s.render_type,
                "model": s.model,
                "version": s.version,
                "frame_url": s.frame_url,
                "frame_status": s.frame_status,
                "clip_url": s.clip_url,
                "clip_status": s.clip_status,
                "cost": float(s.cost or 0),
            }
            for s in job.shots
        ],
    }
