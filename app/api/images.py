from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.database.session import get_db
from app.models.image_generation import ImageGeneration
from app.models.brand_kit import BrandKit
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
    client_id: Optional[int] = None


class GenerateImageResponse(BaseModel):
    id: str
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
    # Build prompt — enhance with brand kit if client_id provided
    full_prompt = req.prompt
    if req.client_id:
        kit = db.query(BrandKit).filter(BrandKit.client_id == req.client_id).first()
        if kit and kit.brand_voice:
            full_prompt += f", {kit.brand_voice} brand aesthetic"
        if kit and kit.tagline:
            full_prompt += f", brand tagline: {kit.tagline}"

    full_prompt += f" | Style: {req.style} | Ratio: {req.ratio}"

    image_url = await generate_frame(full_prompt)

    # Save to database
    gen = ImageGeneration(
        client_id=req.client_id,
        prompt=req.prompt,
        negative_prompt=req.negative_prompt,
        style=req.style,
        ratio=req.ratio,
        resolution=req.resolution,
        image_url=image_url,
        reference_image_url=req.reference_image_url,
    )
    db.add(gen)
    db.commit()
    db.refresh(gen)

    log_activity(
        db,
        action="image_generated",
        description=f"Generated image: {req.prompt[:60]}",
        entity_type="image",
        entity_id=gen.id,
    )

    return GenerateImageResponse(
        id=gen.id,
        image_url=image_url,
        prompt=req.prompt,
        style=req.style,
        resolution=req.resolution,
    )


@router.get("/history")
def get_image_history(
    limit: int = 20,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    query = db.query(ImageGeneration)
    if client_id:
        query = query.filter(ImageGeneration.client_id == client_id)
    images = query.order_by(ImageGeneration.created_at.desc()).limit(limit).all()
    return [
        {
            "id": img.id,
            "prompt": img.prompt,
            "style": img.style,
            "ratio": img.ratio,
            "image_url": img.image_url,
            "created_at": img.created_at.isoformat(),
        }
        for img in images
    ]
