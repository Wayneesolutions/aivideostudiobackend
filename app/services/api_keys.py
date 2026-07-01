"""
API key reader service.

When real AI providers are connected, call get_api_keys() to get the
keys that were saved by the admin in the Settings page.

This means:
  - Admin saves their OpenAI key in the UI → stored in settings table
  - Backend reads it from here when making real AI calls
  - No need to restart the server to update keys
"""
from sqlalchemy.orm import Session

from app.models.setting import Setting


def get_api_keys(db: Session) -> dict:
    """Return all saved API keys from the settings table."""
    keys = ["openai_api_key", "vidu_api_key", "elevenlabs_api_key"]
    result = {}
    for key in keys:
        row = db.query(Setting).filter(Setting.key == key).first()
        result[key] = row.value if row and row.value else ""
    return result


def get_openai_key(db: Session) -> str:
    row = db.query(Setting).filter(Setting.key == "openai_api_key").first()
    return row.value if row and row.value else ""


def get_vidu_key(db: Session) -> str:
    row = db.query(Setting).filter(Setting.key == "vidu_api_key").first()
    return row.value if row and row.value else ""


def get_elevenlabs_key(db: Session) -> str:
    row = db.query(Setting).filter(Setting.key == "elevenlabs_api_key").first()
    return row.value if row and row.value else ""
