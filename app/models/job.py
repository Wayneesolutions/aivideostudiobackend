import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Enum as SAEnum, ForeignKey, Integer,
    JSON, Numeric, String, Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.session import Base
from app.models.client import QualityMode


def gen_uuid() -> str:
    return str(uuid.uuid4())


class JobState(str, enum.Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    SHOTLIST_READY = "SHOTLIST_READY"
    GENERATING_FRAMES = "GENERATING_FRAMES"
    FRAMES_READY = "FRAMES_READY"
    RENDERING_MOTION = "RENDERING_MOTION"
    CLIPS_READY = "CLIPS_READY"
    ASSEMBLING = "ASSEMBLING"
    EXPORTING = "EXPORTING"
    DONE = "DONE"
    FAILED = "FAILED"


class JobType(str, enum.Enum):
    studio = "studio"
    smart_video = "smart_video"
    image = "image"


class FrameStatus(str, enum.Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class ClipStatus(str, enum.Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class RenderType(str, enum.Enum):
    animate = "animate"
    motion_still = "motion_still"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    job_type = Column(SAEnum(JobType), default=JobType.studio, nullable=False)
    name = Column(String(255), nullable=False)
    brief_text = Column(Text, nullable=False)
    mode = Column(SAEnum(QualityMode), nullable=False)
    budget_cap = Column(Numeric(8, 2), nullable=False, default=0)
    state = Column(SAEnum(JobState), default=JobState.CREATED, nullable=False)
    est_cost = Column(Numeric(8, 2), nullable=True)
    cost_total = Column(Numeric(8, 2), default=0.00)
    final_urls = Column(JSON, nullable=True)
    thread_id = Column(String(100), nullable=True)
    num_shots = Column(Integer, default=4, nullable=False)
    logo_url = Column(Text, nullable=True)
    overlay_text = Column(Text, nullable=True)
    overlay_color = Column(String(20), nullable=True)
    num_shots = Column(Integer, default=4, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=datetime.utcnow
    )

    client = relationship("Client", back_populates="jobs")
    shots = relationship("Shot", back_populates="job", order_by="Shot.idx")


class Shot(Base):
    __tablename__ = "shots"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    idx = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    motion = Column(String(200), nullable=True)
    duration_sec = Column(Integer, default=5)
    render_type = Column(SAEnum(RenderType), nullable=False)
    model = Column(String(50), default="ffmpeg")
    version = Column(Integer, default=1)
    frame_url = Column(Text, nullable=True)
    frame_status = Column(SAEnum(FrameStatus), default=FrameStatus.pending)
    clip_url = Column(Text, nullable=True)
    clip_status = Column(SAEnum(ClipStatus), default=ClipStatus.pending)
    cost = Column(Numeric(8, 4), default=0.0000)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=datetime.utcnow
    )

    job = relationship("Job", back_populates="shots")
