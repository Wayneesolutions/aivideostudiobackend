from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.database.session import get_db
from app.models.setting import Setting

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])

DEFAULTS = {
    "profile_name": "Wayne Admin",
    "profile_email": "admin@wayneesolutions.com",
    "notifications_enabled": "true",
    "dark_mode": "true",
    "openai_api_key": "",
    "vidu_api_key": "",
    "elevenlabs_api_key": "",
}


class SettingsPayload(BaseModel):
    profile_name: str = ""
    profile_email: str = ""
    notifications_enabled: bool = True
    dark_mode: bool = True
    openai_api_key: str = ""
    vidu_api_key: str = ""
    elevenlabs_api_key: str = ""


def _get_all(db: Session) -> dict:
    rows = db.query(Setting).all()
    data = dict(DEFAULTS)
    for row in rows:
        data[row.key] = row.value
    return data


@router.get("/")
def get_settings(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    data = _get_all(db)
    return {
        "profile_name": data["profile_name"],
        "profile_email": data["profile_email"],
        "notifications_enabled": data["notifications_enabled"] == "true",
        "dark_mode": data["dark_mode"] == "true",
        "openai_api_key": data["openai_api_key"],
        "vidu_api_key": data["vidu_api_key"],
        "elevenlabs_api_key": data["elevenlabs_api_key"],
    }


@router.post("/")
def save_settings(
    payload: SettingsPayload,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    updates = {
        "profile_name": payload.profile_name,
        "profile_email": payload.profile_email,
        "notifications_enabled": str(payload.notifications_enabled).lower(),
        "dark_mode": str(payload.dark_mode).lower(),
        "openai_api_key": payload.openai_api_key,
        "vidu_api_key": payload.vidu_api_key,
        "elevenlabs_api_key": payload.elevenlabs_api_key,
    }

    for key, value in updates.items():
        existing = db.query(Setting).filter(Setting.key == key).first()
        if existing:
            existing.value = value
        else:
            db.add(Setting(key=key, value=value))

    db.commit()
    return {"message": "Settings saved successfully"}
