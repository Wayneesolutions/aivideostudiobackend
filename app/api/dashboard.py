from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.database.session import get_db
from app.models.activity import ActivityLog
from app.models.job import Job, JobState

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/stats")
def get_stats(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    total_projects = db.query(Job).count()
    videos_generated = db.query(Job).filter(Job.state == JobState.DONE).count()

    recent_projects = (
        db.query(Job)
        .order_by(Job.created_at.desc())
        .limit(5)
        .all()
    )

    recent_activity = (
        db.query(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "total_projects": total_projects,
        "videos_generated": videos_generated,
        "ai_services_status": "Online",
        "recent_projects": [
            {
                "id": j.id,
                "name": j.name,
                "status": j.state,
                "date": j.created_at.isoformat(),
            }
            for j in recent_projects
        ],
        "recent_activity": [
            {
                "id": a.id,
                "action": a.action,
                "description": a.description,
                "entity_type": a.entity_type,
                "created_at": a.created_at.isoformat(),
            }
            for a in recent_activity
        ],
    }
