from typing import Optional

from pydantic import BaseModel

from app.models.client import QualityMode


class CreateClientRequest(BaseModel):
    company_name: str
    email: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    default_mode: QualityMode = QualityMode.economy
    brand_kit: dict = {}


class ClientOut(BaseModel):
    id: int
    company_name: str
    email: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    default_mode: QualityMode

    class Config:
        from_attributes = True
