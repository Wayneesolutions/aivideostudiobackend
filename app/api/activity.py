from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.database.session import get_db
from app.models.activity import ActivityLog

router = APIRouter(prefix="/api/v1/activity", tags=["Activity"])


@router.get("/")
def get_activity(
    limit: int = 20,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    logs = (
        db.query(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log.id,
            "action": log.action,
            "description": log.description,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
