from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_admin
from app.services.openai_service import generate_frame

router = APIRouter(prefix="/api/v1/images", tags=["Images"])


class GenerateImageRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    style: str = "Realistic"
    ratio: str = "1:1"
    resolution: str = "1024x1024"


class GenerateImageResponse(BaseModel):
    image_url: str
    prompt: str
    style: str
    resolution: str


@router.post("/generate", response_model=GenerateImageResponse)
async def generate_image(
    req: GenerateImageRequest,
    _admin=Depends(get_current_admin),
):
    full_prompt = f"{req.prompt} | Style: {req.style} | Ratio: {req.ratio}"
    image_url = await generate_frame(full_prompt)

    return GenerateImageResponse(
        image_url=image_url,
        prompt=req.prompt,
        style=req.style,
        resolution=req.resolution,
    )
