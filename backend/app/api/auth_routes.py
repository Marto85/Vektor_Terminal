from collections import defaultdict
import threading
import time
from typing import Annotated, Optional
from urllib.parse import quote
from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import AfterValidator, BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import (
    FRONTEND_APP_URL,
    GITHUB_CLIENT_ID,
    GOOGLE_CLIENT_ID,
    get_registration_mode,
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
    verify_registered_email,
)

auth_router = APIRouter(tags=["Autenticación y Usuarios"])

_AUTH_RATE_LOCK = threading.Lock()
_AUTH_RATE_BUCKETS: dict[str, list[float]] = defaultdict(list)


def _extract_trusted_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        # Usar el último salto agregado por el proxy confiable (Render/Edge), no el primer valor manipulable por el cliente
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "unknown"


def _enforce_auth_rate_limit(
    request: Request,
    bucket: str,
    max_calls: int,
    window_seconds: int = 60,
    subject_key: str | None = None,
) -> None:
    client_ip = _extract_trusted_client_ip(request)
    keys = [f"{bucket}:ip:{client_ip}"]
    if subject_key:
        clean_subj = subject_key.strip().lower()[:120]
        if clean_subj:
            keys.append(f"{bucket}:subj:{clean_subj}")

    now = time.monotonic()
    cutoff = now - window_seconds
    with _AUTH_RATE_LOCK:
        if len(_AUTH_RATE_BUCKETS) > 512:
            stale_keys = [
                k for k, ts_list in _AUTH_RATE_BUCKETS.items() if not ts_list or ts_list[-1] <= cutoff
            ]
            for sk in stale_keys:
                _AUTH_RATE_BUCKETS.pop(sk, None)

        for key in keys:
            hits = [t for t in _AUTH_RATE_BUCKETS[key] if t > cutoff]
            if len(hits) >= max_calls:
                _AUTH_RATE_BUCKETS[key] = hits
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Demasiados intentos en poco tiempo. Esperá un minuto antes de reintentar.",
                    headers={"Retry-After": str(window_seconds)},
                )
            hits.append(now)
            _AUTH_RATE_BUCKETS[key] = hits


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
    identifier: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)  # Compatibilidad retroactiva
    password: str = Field(..., max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., max_length=32)
    email: VektorEmail
    full_name: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., max_length=128)
    advisor_id: Optional[int] = None
    invite_code: Optional[str] = Field(None, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: VektorEmail


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., max_length=256)
    new_password: str = Field(..., max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: Optional[str] = Field(None, max_length=128)
    new_password: str = Field(..., max_length=128)


class CreateUserRequest(BaseModel):
    username: Optional[str] = Field(None, max_length=32)
    email: VektorEmail
    full_name: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., max_length=128)
    role: str = Field("client", max_length=20)
    advisor_id: Optional[int] = None
    must_change_password: bool = True


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = Field(None, max_length=120)
    role: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None
    advisor_id: Optional[int] = None
    clear_advisor: bool = False
    reset_password: Optional[str] = Field(None, max_length=128)


@auth_router.get("/auth/providers")
def get_enabled_auth_providers():
    return {
        "google": bool(GOOGLE_CLIENT_ID),
        "github": bool(GITHUB_CLIENT_ID),
        "registration_mode": get_registration_mode(),
    }


@auth_router.get("/auth/advisors")
def get_public_advisors(db: Session = Depends(get_db)):
    return {"advisors": list_public_advisors(db)}


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=200)


@auth_router.post("/auth/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ident = (payload.identifier or payload.email or "").strip()
    _enforce_auth_rate_limit(request, "login", max_calls=20, window_seconds=60, subject_key=ident)
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
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    _enforce_auth_rate_limit(request, "register", max_calls=10, window_seconds=60)
    user = register_public_user(
        db=db,
        username=payload.username,
        email=str(payload.email),
        full_name=payload.full_name,
        password=payload.password,
        advisor_id=payload.advisor_id,
        invite_code=payload.invite_code,
    )
    if not getattr(user, "email_verified", True):
        return {
            "requires_email_verification": True,
            "message": "Cuenta creada. Te enviamos un correo para confirmar tu dirección y activar el acceso.",
            "user": serialize_user(user),
        }
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


@auth_router.post("/auth/verify-email")
def verify_email(payload: VerifyEmailRequest, request: Request, db: Session = Depends(get_db)):
    _enforce_auth_rate_limit(request, "verify_email", max_calls=10, window_seconds=60)
    user = verify_registered_email(db, payload.token)
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
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    _enforce_auth_rate_limit(request, "forgot_password", max_calls=8, window_seconds=60)
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
        return RedirectResponse(url=f"{FRONTEND_APP_URL}/#oauth_token={quote(jwt_token, safe='')}")
    except Exception as exc:
        detail = str(getattr(exc, "detail", "Error al autenticar con el proveedor externo."))
        return RedirectResponse(url=f"{FRONTEND_APP_URL}/?oauth_error={quote(detail, safe='')}")


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