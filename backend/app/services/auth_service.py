from datetime import datetime, timedelta
import hashlib
import os
import re
import secrets
from typing import Optional
from urllib.parse import urlencode

import jwt
import requests
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import (
    BACKEND_PUBLIC_URL,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    JWT_ALGORITHM,
    VEKTOR_SECRET_KEY,
    VEKTOR_ADMIN_EMAIL,
    VEKTOR_ADMIN_NAME,
    VEKTOR_ADMIN_PASSWORD,
    VEKTOR_ENV,
    VEKTOR_INVITE_CODE,
    get_registration_mode,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.models.database import EmailVerificationToken, PasswordResetToken, SessionLocal, User
from app.services.email_service import (
    is_email_delivery_configured,
    send_recovery_email,
    send_verification_email,
)

VALID_ROLES = ("superadmin", "advisor", "client")
USERNAME_REGEX = re.compile(r"^[a-z0-9._]{3,32}$")


def normalize_username(raw: str) -> str:
    cleaned = raw.strip().lower()
    if not USERNAME_REGEX.match(cleaned):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de usuario debe tener entre 3 y 32 caracteres (letras minúsculas, números, punto o guion bajo).",
        )
    return cleaned


def _generate_unique_username(db: Session, base_seed: str) -> str:
    base = re.sub(r"[^a-z0-9._]", "", base_seed.strip().lower())[:26]
    if len(base) < 3:
        base = f"user{secrets.randbelow(9000) + 1000}"
    candidate = base
    idx = 1
    while db.query(User).filter(func.lower(User.username) == candidate).first():
        idx += 1
        candidate = f"{base[:26]}{idx}"
    return candidate


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "auth_provider": user.auth_provider or "local",
        "is_active": bool(user.is_active),
        "must_change_password": bool(user.must_change_password),
        "advisor_id": user.advisor_id,
        "advisor_name": user.advisor.full_name if user.advisor else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def list_public_advisors(db: Session) -> list[dict]:
    """Devuelve ejecutivos activos (advisor/superadmin) seleccionables durante el registro."""
    if get_registration_mode() == "closed":
        return []
    advisors = (
        db.query(User)
        .filter(
            User.role.in_(("superadmin", "advisor")),
            User.is_active == True,  # noqa: E712
        )
        .order_by(User.full_name.asc())
        .all()
    )
    return [
        {
            "id": int(a.id),
            "full_name": str(a.full_name),
            "role": str(a.role),
        }
        for a in advisors
    ]


def ensure_default_superadmin() -> None:
    db = SessionLocal()
    try:
        existing_admin = db.query(User).filter(User.role == "superadmin").first()
        if existing_admin:
            return
        normalized_email = VEKTOR_ADMIN_EMAIL.strip().lower()
        existing_by_email = db.query(User).filter(func.lower(User.email) == normalized_email).first()
        if existing_by_email:
            existing_by_email.role = "superadmin"
            existing_by_email.is_active = True
            db.commit()
            return

        uname = _generate_unique_username(db, normalized_email.split("@")[0])
        admin_user = User(
            username=uname,
            email=normalized_email,
            full_name=VEKTOR_ADMIN_NAME.strip() or "Administrador Vektor",
            hashed_password=hash_password(VEKTOR_ADMIN_PASSWORD),
            auth_provider="local",
            role="superadmin",
            is_active=True,
            must_change_password=False,
        )
        db.add(admin_user)
        db.commit()
    finally:
        db.close()


def authenticate_user(db: Session, identifier: str, password: str) -> User:
    clean_id = identifier.strip().lower()
    user = (
        db.query(User)
        .filter(
            (func.lower(User.email) == clean_id)
            | (func.lower(User.username) == clean_id)
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario/correo o contraseña incorrectos.",
        )
    if not user.hashed_password:
        if user.auth_provider == "managed":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Esta cuenta corresponde a una cartera administrada sin acceso habilitado.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Esta cuenta se registró con {user.auth_provider.capitalize()}. Ingresá con ese botón o usá 'Recuperar acceso' para crear una contraseña local.",
        )
    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario/correo o contraseña incorrectos.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta está desactivada. Contactá al administrador.",
        )
    if not getattr(user, "email_verified", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Confirmá tu correo electrónico desde el enlace que te enviamos antes de ingresar.",
        )
    return user


def is_email_verification_required() -> bool:
    flag = os.getenv("VEKTOR_REQUIRE_EMAIL_VERIFICATION", "").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    if flag in ("0", "false", "no"):
        return False
    return VEKTOR_ENV == "production" and is_email_delivery_configured()


def register_public_user(
    db: Session,
    username: str,
    email: str,
    full_name: str,
    password: str,
    advisor_id: Optional[int] = None,
    invite_code: Optional[str] = None,
) -> User:
    reg_mode = get_registration_mode()
    if reg_mode == "closed":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El registro público está deshabilitado. Solicitá tu cuenta al administrador.",
        )
    if reg_mode == "invite":
        provided_code = (invite_code or "").strip()
        if not provided_code or not secrets.compare_digest(provided_code, VEKTOR_INVITE_CODE):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Código de invitación inválido o faltante.",
            )

    clean_username = normalize_username(username)
    clean_email = email.strip().lower()

    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe tener al menos 8 caracteres.",
        )

    if db.query(User).filter(func.lower(User.username) == clean_username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese nombre de usuario ya está en uso. Elegí otro.",
        )

    if db.query(User).filter(func.lower(User.email) == clean_email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cuenta registrada con ese correo electrónico.",
        )

    resolved_advisor_id: Optional[int] = None
    if advisor_id is not None:
        advisor = (
            db.query(User)
            .filter(
                User.id == advisor_id,
                User.role.in_(("advisor", "superadmin")),
                User.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not advisor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El ejecutivo seleccionado no existe o no está disponible.",
            )
        resolved_advisor_id = int(advisor.id)

    require_verify = is_email_verification_required()
    user = User(
        username=clean_username,
        email=clean_email,
        full_name=full_name.strip(),
        hashed_password=hash_password(password),
        auth_provider="local",
        role="client",
        is_active=True,
        email_verified=not require_verify,
        must_change_password=False,
        advisor_id=resolved_advisor_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if require_verify:
        raw_token = secrets.token_urlsafe(24)
        token_row = EmailVerificationToken(
            user_id=user.id,
            token_hash=_hash_reset_token(raw_token),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            used=False,
        )
        db.add(token_row)
        db.commit()
        send_verification_email(
            to_email=user.email,
            full_name=user.full_name,
            username=user.username,
            raw_token=raw_token,
        )

    return user


def verify_registered_email(db: Session, token: str) -> User:
    t_hash = _hash_reset_token((token or "").strip())
    row = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token_hash == t_hash,
            EmailVerificationToken.used == False,  # noqa: E712
        )
        .first()
    )
    if not row or row.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de confirmación es inválido o ya expiró.",
        )
    user = db.query(User).filter(User.id == row.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cuenta asociada no está disponible.",
        )
    user.email_verified = True
    row.used = True
    db.commit()
    db.refresh(user)
    return user


def create_user_by_admin(
    db: Session,
    email: str,
    full_name: str,
    password: str,
    role: str = "client",
    advisor_id: Optional[int] = None,
    must_change_password: bool = True,
    username: Optional[str] = None,
) -> User:
    normalized_role = role.strip().lower()
    if normalized_role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rol inválido. Valores permitidos: {', '.join(VALID_ROLES)}.",
        )
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe tener al menos 8 caracteres.",
        )

    normalized_email = email.strip().lower()
    if db.query(User).filter(func.lower(User.email) == normalized_email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario registrado con ese correo electrónico.",
        )

    if username and username.strip():
        clean_username = normalize_username(username)
        if db.query(User).filter(func.lower(User.username) == clean_username).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ese nombre de usuario ya está en uso.",
            )
    else:
        clean_username = _generate_unique_username(db, normalized_email.split("@")[0])

    resolved_advisor_id = None
    if normalized_role == "client" and advisor_id is not None:
        advisor = db.query(User).filter(User.id == advisor_id).first()
        if not advisor or advisor.role not in ("advisor", "superadmin"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El asesor asignado no existe o no tiene rol de asesor.",
            )
        resolved_advisor_id = advisor.id

    user = User(
        username=clean_username,
        email=normalized_email,
        full_name=full_name.strip(),
        hashed_password=hash_password(password),
        auth_provider="local",
        role=normalized_role,
        is_active=True,
        must_change_password=must_change_password,
        advisor_id=resolved_advisor_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_by_admin(
    db: Session,
    target_user_id: int,
    actor_user: User,
    full_name: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    advisor_id: Optional[int] = None,
    clear_advisor: bool = False,
    reset_password: Optional[str] = None,
) -> User:
    target = db.query(User).filter(User.id == target_user_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    if target.id == actor_user.id:
        if is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No podés desactivar tu propia cuenta de superadmin.",
            )
        if role is not None and role.strip().lower() != "superadmin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No podés quitarte el rol superadmin a vos mismo.",
            )

    if full_name is not None and full_name.strip():
        target.full_name = full_name.strip()

    if role is not None:
        normalized_role = role.strip().lower()
        if normalized_role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rol inválido. Valores permitidos: {', '.join(VALID_ROLES)}.",
            )
        target.role = normalized_role
        if normalized_role != "client":
            target.advisor_id = None

    if is_active is not None:
        target.is_active = bool(is_active)

    if clear_advisor:
        target.advisor_id = None
    elif advisor_id is not None and target.role == "client":
        advisor = db.query(User).filter(User.id == advisor_id).first()
        if not advisor or advisor.role not in ("advisor", "superadmin"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El asesor asignado no existe o no tiene rol de asesor.",
            )
        target.advisor_id = advisor.id

    if reset_password is not None and reset_password != "":
        if len(reset_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La nueva contraseña debe tener al menos 8 caracteres.",
            )
        target.hashed_password = hash_password(reset_password)
        target.must_change_password = True

    db.commit()
    db.refresh(target)
    return target


def change_own_password(
    db: Session,
    user: User,
    current_password: Optional[str],
    new_password: str,
) -> User:
    if user.hashed_password:
        if not current_password or not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña actual es incorrecta.",
            )
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe tener al menos 8 caracteres.",
        )
    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    db.commit()
    db.refresh(user)
    return user


# --- RECUPERACIÓN DE USUARIO Y CONTRASEÑA POR EMAIL ---

def _hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def request_password_recovery(db: Session, email: str) -> dict:
    clean_email = email.strip().lower()
    user = db.query(User).filter(func.lower(User.email) == clean_email).first()

    # Por seguridad, respondemos siempre mensaje neutro si no existe el mail
    if not user or not user.is_active:
        return {
            "status": "ok",
            "message": "Si el correo está registrado, enviamos tu nombre de usuario y el enlace de recuperación.",
        }

    # Invalidar tokens previos no usados del usuario
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used == False,  # noqa: E712
    ).update({"used": True})

    raw_token = secrets.token_urlsafe(24)
    token_row = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_reset_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(minutes=15),
        used=False,
    )
    db.add(token_row)
    db.commit()

    delivery_info = send_recovery_email(
        to_email=user.email,
        full_name=user.full_name,
        username=user.username,
        raw_token=raw_token,
    )

    resp = {
        "status": "ok",
        "message": "Si el correo está registrado, enviamos tu nombre de usuario y el enlace de recuperación.",
    }
    # En modo consola local devolvemos hint para facilitar pruebas sin servidor SMTP
    if delivery_info.get("delivery") == "console" and VEKTOR_ENV != "production":
        resp["dev_hint"] = f"Modo local sin SMTP: revisá la terminal del backend (usuario: {user.username})."
    return resp


def confirm_password_reset(db: Session, token: str, new_password: str) -> User:
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe tener al menos 8 caracteres.",
        )

    t_hash = _hash_reset_token(token.strip())
    row = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == t_hash,
            PasswordResetToken.used == False,  # noqa: E712
        )
        .first()
    )
    if not row or row.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El código o enlace de recuperación es inválido o ya expiró.",
        )

    user = db.query(User).filter(User.id == row.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cuenta asociada no está disponible.",
        )

    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    row.used = True
    db.commit()
    db.refresh(user)
    return user


# --- OAUTH 2.0 (GOOGLE Y GITHUB) ---

def _create_oauth_state(provider: str) -> str:
    payload = {
        "provider": provider,
        "nonce": secrets.token_hex(8),
        "exp": datetime.utcnow() + timedelta(minutes=10),
    }
    return jwt.encode(payload, VEKTOR_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _verify_oauth_state(state_token: str, expected_provider: str) -> None:
    try:
        data = jwt.decode(state_token, VEKTOR_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if data.get("provider") != expected_provider:
            raise ValueError("Provider mismatch")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado OAuth inválido o expirado. Volvé a intentarlo.",
        )


def build_oauth_authorize_url(provider: str) -> str:
    prov = provider.strip().lower()
    callback_url = f"{BACKEND_PUBLIC_URL}/api/v1/auth/oauth/{prov}/callback"
    state = _create_oauth_state(prov)

    if prov == "google":
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Inicio de sesión con Google no configurado aún (faltan GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET en .env).",
            )
        params = urlencode(
            {
                "client_id": GOOGLE_CLIENT_ID,
                "redirect_uri": callback_url,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "prompt": "select_account",
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    if prov == "github":
        if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Inicio de sesión con GitHub no configurado aún (faltan GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET en .env).",
            )
        params = urlencode(
            {
                "client_id": GITHUB_CLIENT_ID,
                "redirect_uri": callback_url,
                "scope": "read:user user:email",
                "state": state,
            }
        )
        return f"https://github.com/login/oauth/authorize?{params}"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Proveedor OAuth no soportado.",
    )


def handle_oauth_callback(db: Session, provider: str, code: str, state: str) -> str:
    prov = provider.strip().lower()
    _verify_oauth_state(state, prov)
    callback_url = f"{BACKEND_PUBLIC_URL}/api/v1/auth/oauth/{prov}/callback"

    if prov == "google":
        token_resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": callback_url,
                "grant_type": "authorization_code",
            },
            timeout=12,
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No se pudo obtener token de Google.")

        info_resp = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=12,
        )
        info = info_resp.json()
        email = (info.get("email") or "").strip().lower()
        sub = str(info.get("sub") or "")
        full_name = (info.get("name") or email.split("@")[0]).strip()
        preferred_user = email.split("@")[0]

    elif prov == "github":
        token_resp = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": callback_url,
            },
            timeout=12,
        )
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No se pudo obtener token de GitHub.")

        gh_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        }
        profile = requests.get("https://api.github.com/user", headers=gh_headers, timeout=12).json()
        sub = str(profile.get("id") or "")
        preferred_user = (profile.get("login") or "githubuser").lower()
        full_name = (profile.get("name") or preferred_user).strip()
        email = (profile.get("email") or "").strip().lower()

        if not email:
            emails_resp = requests.get(
                "https://api.github.com/user/emails", headers=gh_headers, timeout=12
            ).json()
            if isinstance(emails_resp, list):
                primary = next(
                    (e["email"] for e in emails_resp if e.get("primary") and e.get("verified")),
                    None,
                )
                fallback = next((e["email"] for e in emails_resp if e.get("verified")), None)
                email = (primary or fallback or "").strip().lower()
    else:
        raise HTTPException(status_code=400, detail="Proveedor no soportado.")

    if not email:
        raise HTTPException(
            status_code=400,
            detail=f"Tu cuenta de {prov.capitalize()} no expuso un correo electrónico verificado.",
        )

    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user:
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Tu cuenta está desactivada.")
        if not user.oauth_sub:
            user.oauth_sub = sub
            if user.auth_provider == "local":
                user.auth_provider = prov
            db.commit()
    else:
        if get_registration_mode() != "open":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu cuenta no está habilitada para auto-registro. Solicitá acceso al administrador.",
            )
        uname = _generate_unique_username(db, preferred_user)
        user = User(
            username=uname,
            email=email,
            full_name=full_name,
            hashed_password=None,
            auth_provider=prov,
            oauth_sub=sub,
            role="client",
            is_active=True,
            must_change_password=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return create_access_token(
        user_id=int(user.id),
        email=str(user.email),
        role=str(user.role),
    )