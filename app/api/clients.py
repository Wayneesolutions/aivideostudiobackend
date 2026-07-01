from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.database.session import get_db
from app.models.client import Client, QualityMode
from app.schemas.client import ClientOut, CreateClientRequest
from app.services.activity_service import log_activity

router = APIRouter(prefix="/api/v1/clients", tags=["Clients"])


class UpdateClientRequest(BaseModel):
    company_name: str
    email: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    default_mode: QualityMode = QualityMode.economy


@router.post("/", response_model=ClientOut)
def create_client(
    req: CreateClientRequest,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    client = Client(
        company_name=req.company_name,
        email=req.email,
        contact_person=req.contact_person,
        phone=req.phone,
        default_mode=req.default_mode,
        brand_kit=req.brand_kit,
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    log_activity(
        db,
        action="client_created",
        description=f"Client '{client.company_name}' created",
        entity_type="client",
        entity_id=str(client.id),
    )

    return client


@router.get("/", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    return db.query(Client).order_by(Client.created_at.desc()).all()


@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.put("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    req: UpdateClientRequest,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client.company_name = req.company_name
    client.email = req.email
    client.contact_person = req.contact_person
    client.phone = req.phone
    client.default_mode = req.default_mode
    db.commit()
    db.refresh(client)

    log_activity(
        db,
        action="client_updated",
        description=f"Client '{client.company_name}' updated",
        entity_type="client",
        entity_id=str(client.id),
    )

    return client


@router.delete("/{client_id}")
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    name = client.company_name
    db.delete(client)
    db.commit()

    log_activity(
        db,
        action="client_deleted",
        description=f"Client '{name}' deleted",
        entity_type="client",
        entity_id=str(client_id),
    )

    return {"message": f"Client '{name}' deleted successfully"}
