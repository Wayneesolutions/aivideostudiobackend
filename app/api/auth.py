from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.jwt import create_access_token
from app.core.security import hash_password, verify_password
from app.database.session import get_db
from app.models.admin import Admin
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth_service import authenticate_admin
from app.api.deps import get_current_admin

router = APIRouter(prefix="/auth", tags=["Authentication"])


class UpdateProfileRequest(BaseModel):
    full_name: str
    email: str
    current_password: str = ""
    new_password: str = ""


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    admin = authenticate_admin(db=db, email=request.email, password=request.password)
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"sub": admin.email})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def get_me(admin: Admin = Depends(get_current_admin)):
    return {
        "id": admin.id,
        "full_name": admin.full_name,
        "email": admin.email,
    }


@router.put("/profile")
def update_profile(
    req: UpdateProfileRequest,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    # If changing password, verify current password first
    if req.new_password:
        if not req.current_password:
            raise HTTPException(status_code=400, detail="Current password required to set a new password")
        if not verify_password(req.current_password, admin.password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        admin.password = hash_password(req.new_password)

    # Check email not taken by another admin
    if req.email != admin.email:
        existing = db.query(Admin).filter(Admin.email == req.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")

    admin.full_name = req.full_name
    admin.email = req.email
    db.commit()

    # Return new token since email (sub) may have changed
    token = create_access_token({"sub": admin.email})
    return {
        "message": "Profile updated successfully",
        "access_token": token,
        "full_name": admin.full_name,
        "email": admin.email,
    }
