from typing import Optional

from pydantic import BaseModel

from app.models.client import QualityMode
from app.models.job import JobType


class CreateJobRequest(BaseModel):
    client_id: int
    name: str
    brief_text: str
    mode: QualityMode = QualityMode.economy
    job_type: JobType = JobType.studio
    thread_id: Optional[str] = None
    num_shots: int = 4
    logo_url: Optional[str] = None
    overlay_text: Optional[str] = None
    overlay_color: Optional[str] = None  # Controls video duration: 1=5s, 2=10s, 3=15s, 4=20s, 6=30s


class ChatMessageRequest(BaseModel):
    message: str
