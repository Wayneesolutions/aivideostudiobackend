from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.database.session import get_db
from app.models.brand_kit import BrandKit

router = APIRouter(prefix="/api/v1/brand-kit", tags=["Brand Kit"])


class BrandKitPayload(BaseModel):
    client_id: int
    company_name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = "#6D28D9"
    secondary_color: Optional[str] = "#FFFFFF"
    brand_voice: Optional[str] = None
    tagline: Optional[str] = None
    website: Optional[str] = None


@router.get("/{client_id}")
def get_brand_kit(
    client_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    kit = db.query(BrandKit).filter(BrandKit.client_id == client_id).first()
    if not kit:
        return {
            "client_id": client_id,
            "company_name": None,
            "logo_url": None,
            "primary_color": "#6D28D9",
            "secondary_color": "#FFFFFF",
            "brand_voice": None,
            "tagline": None,
            "website": None,
        }
    return {
        "client_id": kit.client_id,
        "company_name": kit.company_name,
        "logo_url": kit.logo_url,
        "primary_color": kit.primary_color,
        "secondary_color": kit.secondary_color,
        "brand_voice": kit.brand_voice,
        "tagline": kit.tagline,
        "website": kit.website,
    }


@router.post("/")
def save_brand_kit(
    payload: BrandKitPayload,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    kit = db.query(BrandKit).filter(BrandKit.client_id == payload.client_id).first()
    if kit:
        kit.company_name = payload.company_name
        kit.logo_url = payload.logo_url
        kit.primary_color = payload.primary_color
        kit.secondary_color = payload.secondary_color
        kit.brand_voice = payload.brand_voice
        kit.tagline = payload.tagline
        kit.website = payload.website
    else:
        kit = BrandKit(
            client_id=payload.client_id,
            company_name=payload.company_name,
            logo_url=payload.logo_url,
            primary_color=payload.primary_color,
            secondary_color=payload.secondary_color,
            brand_voice=payload.brand_voice,
            tagline=payload.tagline,
            website=payload.website,
        )
        db.add(kit)
    db.commit()
    return {"message": "Brand kit saved successfully"}
