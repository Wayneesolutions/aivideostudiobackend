from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.admin import Admin


def authenticate_admin(db: Session, email: str, password: str) -> Admin | None:
    admin = db.query(Admin).filter(Admin.email == email).first()
    if not admin:
        return None
    if not admin.is_active:
        return None
    if not verify_password(password, admin.password):
        return None
    return admin
