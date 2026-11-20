from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user, get_db, require_roles
from app.models.database import User
from app.services.auth_service import (
    authenticate_user,
    change_user_password,
    create_user_by_admin,
    list_users_for_actor,
    serialize_user,
    update_user_by_admin,
)

auth_router = APIRouter(tags=["Autenticación y Usuarios"])


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = "client"
    advisor_id: Optional[int] = None
    must_change_password: bool = True


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    advisor_id: Optional[int] = None
    clear_advisor: bool = False
    reset_password: Optional[str] = None


@auth_router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return authenticate_user(db, payload.email, payload.password)


@auth_router.get("/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)


@auth_router.post("/auth/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = change_user_password(
        db, current_user, payload.current_password, payload.new_password
    )
    return {"status": "ok", "user": updated}


@auth_router.get("/admin/users")
def list_users(
    current_user: User = Depends(require_roles("superadmin", "advisor")),
    db: Session = Depends(get_db),
):
    return {"users": list_users_for_actor(db, current_user)}


@auth_router.post("/admin/users")
def create_user(
    payload: CreateUserRequest,
    current_user: User = Depends(require_roles("superadmin")),
    db: Session = Depends(get_db),
):
    created = create_user_by_admin(
        db=db,
        email=payload.email,
        full_name=payload.full_name,
        password=payload.password,
        role=payload.role,
        advisor_id=payload.advisor_id,
        must_change_password=payload.must_change_password,
    )
    return {"status": "created", "user": created}


@auth_router.patch("/admin/users/{user_id}")
def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    current_user: User = Depends(require_roles("superadmin")),
    db: Session = Depends(get_db),
):
    updated = update_user_by_admin(
        db=db,
        target_user_id=user_id,
        actor=current_user,
        full_name=payload.full_name,
        role=payload.role,
        is_active=payload.is_active,
        advisor_id=payload.advisor_id,
        clear_advisor=payload.clear_advisor,
        reset_password=payload.reset_password,
    )
    return {"status": "updated", "user": updated}