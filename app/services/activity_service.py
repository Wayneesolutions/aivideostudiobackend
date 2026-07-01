from sqlalchemy.orm import Session

from app.models.activity import ActivityLog


def log_activity(
    db: Session,
    action: str,
    description: str,
    entity_type: str = None,
    entity_id: str = None,
):
    entry = ActivityLog(
        action=action,
        description=description,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(entry)
    db.commit()
