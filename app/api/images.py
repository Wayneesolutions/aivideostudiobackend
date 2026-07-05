from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.database.session import get_db
from app.services.openai_service import generate_frame
from app.services.activity_service import log_activity

router = APIRouter(prefix="/api/v1/images", tags=["Images"])


class GenerateImageRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    style: str = "Realistic"
    ratio: str = "1:1"
    resolution: str = "1024x1024"
    reference_image_url: Optional[str] = None


class GenerateImageResponse(BaseModel):
    image_url: str
    prompt: str
    style: str
    resolution: str


@router.post("/generate", response_model=GenerateImageResponse)
async def generate_image(
    req: GenerateImageRequest,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    full_prompt = f"{req.prompt} | Style: {req.style} | Ratio: {req.ratio}"
    if req.reference_image_url:
        full_prompt += f" | Reference image provided"

    image_url = await generate_frame(full_prompt)

    log_activity(
        db,
        action="image_generated",
        description=f"Generated image: {req.prompt[:60]}",
        entity_type="image",
        entity_id=None,
    )

    return GenerateImageResponse(
        image_url=image_url,
        prompt=req.prompt,
        style=req.style,
        resolution=req.resolution,
    )
