from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database.session import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(100), nullable=False)   # e.g. "job_created"
    description = Column(Text, nullable=False)      # e.g. "Wayne Product Launch created"
    entity_type = Column(String(50), nullable=True) # e.g. "job", "client", "image"
    entity_id = Column(String(100), nullable=True)  # the id of the related entity
    created_at = Column(DateTime(timezone=True), server_default=func.now())
