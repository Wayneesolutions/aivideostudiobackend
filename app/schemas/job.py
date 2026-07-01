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


class ChatMessageRequest(BaseModel):
    message: str
