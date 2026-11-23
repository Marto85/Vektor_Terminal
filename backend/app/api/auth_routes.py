from typing import Annotated, Optional
from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from pydantic import AfterValidator, BaseModel
from sqlalchemy.orm import Session

from app.core.config import (
    FRONTEND_APP_URL,
    GITHUB_CLIENT_ID,
    GOOGLE_CLIENT_ID,
)
from app.core.security import (
    create_access_token,
    get_current_user,
    get_db,
    require_roles,
)
from app.models.database import User
from app.services.auth_service import (
    authenticate_user,
    build_oauth_authorize_url,
    change_own_password,
    confirm_password_reset,
    create_user_by_admin,
    handle_oauth_callback,
    list_public_advisors,
    register_public_user,
    request_password_recovery,
    serialize_user,
    update_user_by_admin,
)

auth_router = APIRouter(tags=["Autenticación y Usuarios"])


def _validate_vektor_email(v: str) -> str:
    raw = v.strip().lower()
    if raw.endswith(".local") and "@" in raw:
        local_part, domain_part = raw.rsplit("@", 1)
        if local_part and "." in domain_part and not domain_part.startswith("."):
            return f"{local_part}@{domain_part}"
    try:
        info = validate_email(raw, check_deliverability=False, test_environment=True)
        return info.normalized
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc


VektorEmail = Annotated[str, AfterValidator(_validate_vektor_email)]


class LoginRequest(BaseModel):
    identifier: Optional[str] = None
    email: Optional[str] = None  # Compatibilidad retroactiva
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: VektorEmail
    full_name: str
    password: str
    advisor_id: Optional[int] = None


class ForgotPasswordRequest(BaseModel):
    email: VektorEmail


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str


class CreateUserRequest(BaseModel):
    username: Optional[str] = None
    email: VektorEmail
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


@auth_router.get("/auth/providers")
def get_enabled_auth_providers():
    return {
        "google": bool(GOOGLE_CLIENT_ID),
        "github": bool(GITHUB_CLIENT_ID),
    }


@auth_router.get("/auth/advisors")
def get_public_advisors(db: Session = Depends(get_db)):
    return {"advisors": list_public_advisors(db)}


@auth_router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    ident = (payload.identifier or payload.email or "").strip()
    user = authenticate_user(db, ident, payload.password)
    token = create_access_token(
        user_id=int(user.id),
        email=str(user.email),
        role=str(user.role),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user(user),
    }


@auth_router.post("/auth/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = register_public_user(
        db=db,
        username=payload.username,
        email=str(payload.email),
        full_name=payload.full_name,
        password=payload.password,
        advisor_id=payload.advisor_id,
    )
    token = create_access_token(
        user_id=int(user.id),
        email=str(user.email),
        role=str(user.role),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user(user),
    }


@auth_router.post("/auth/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return request_password_recovery(db, str(payload.email))


@auth_router.post("/auth/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = confirm_password_reset(db, payload.token, payload.new_password)
    token = create_access_token(
        user_id=int(user.id),
        email=str(user.email),
        role=str(user.role),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user(user),
    }


@auth_router.get("/auth/oauth/{provider}/login")
def oauth_login(provider: str):
    url = build_oauth_authorize_url(provider)
    return {"authorize_url": url}


@auth_router.get("/auth/oauth/{provider}/callback")
def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        jwt_token = handle_oauth_callback(db, provider, code, state)
        return RedirectResponse(url=f"{FRONTEND_APP_URL}/?oauth_token={jwt_token}")
    except Exception as exc:
        detail = getattr(exc, "detail", "Error al autenticar con el proveedor externo.")
        return RedirectResponse(url=f"{FRONTEND_APP_URL}/?oauth_error={detail}")


@auth_router.get("/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)


@auth_router.post("/auth/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = change_own_password(
        db=db,
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return {"status": "ok", "user": serialize_user(updated)}


@auth_router.get("/admin/users")
def list_users(
    current_user: User = Depends(require_roles("superadmin", "advisor")),
    db: Session = Depends(get_db),
):
    if current_user.role == "superadmin":
        users = db.query(User).order_by(User.id.asc()).all()
    else:
        users = (
            db.query(User)
            .filter(User.advisor_id == current_user.id)
            .order_by(User.id.asc())
            .all()
        )
    return {"users": [serialize_user(u) for u in users]}


@auth_router.post("/admin/users")
def admin_create_user(
    payload: CreateUserRequest,
    _admin: User = Depends(require_roles("superadmin")),
    db: Session = Depends(get_db),
):
    created = create_user_by_admin(
        db=db,
        username=payload.username,
        email=str(payload.email),
        full_name=payload.full_name,
        password=payload.password,
        role=payload.role,
        advisor_id=payload.advisor_id,
        must_change_password=payload.must_change_password,
    )
    return {"status": "created", "user": serialize_user(created)}


@auth_router.patch("/admin/users/{user_id}")
def admin_update_user(
    user_id: int,
    payload: UpdateUserRequest,
    admin: User = Depends(require_roles("superadmin")),
    db: Session = Depends(get_db),
):
    updated = update_user_by_admin(
        db=db,
        target_user_id=user_id,
        actor_user=admin,
        full_name=payload.full_name,
        role=payload.role,
        is_active=payload.is_active,
        advisor_id=payload.advisor_id,
        clear_advisor=payload.clear_advisor,
        reset_password=payload.reset_password,
    )
    return {"status": "updated", "user": serialize_user(updated)}