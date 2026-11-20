from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import (
    VEKTOR_ADMIN_EMAIL,
    VEKTOR_ADMIN_NAME,
    VEKTOR_ADMIN_PASSWORD,
)
from app.core.security import (
    VALID_ROLES,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.database import SessionLocal, User


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": bool(user.is_active),
        "must_change_password": bool(user.must_change_password),
        "advisor_id": user.advisor_id,
        "advisor_name": user.advisor.full_name if user.advisor else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def ensure_default_superadmin() -> None:
    """Crea el superadmin inicial de forma idempotente si la tabla users está vacía."""
    db = SessionLocal()
    try:
        has_any_user = db.query(User.id).first() is not None
        if has_any_user:
            return

        admin_user = User(
            email=VEKTOR_ADMIN_EMAIL,
            full_name=VEKTOR_ADMIN_NAME,
            hashed_password=hash_password(VEKTOR_ADMIN_PASSWORD),
            role="superadmin",
            is_active=True,
            must_change_password=False,
        )
        db.add(admin_user)
        db.commit()
    finally:
        db.close()


def authenticate_user(db: Session, email: str, password: str) -> dict:
    normalized_email = email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    if not user or not verify_password(password, str(user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
        )

    if not bool(user.is_active):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta está desactivada. Contactá al administrador.",
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


def change_user_password(
    db: Session, user: User, current_password: str, new_password: str
) -> dict:
    if len(new_password.strip()) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe tener al menos 8 caracteres.",
        )
    if not verify_password(current_password, str(user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta.",
        )

    user.hashed_password = hash_password(new_password.strip())
    user.must_change_password = False
    db.commit()
    db.refresh(user)
    return serialize_user(user)


def list_users_for_actor(db: Session, actor: User) -> list[dict]:
    if actor.role == "superadmin":
        users = db.query(User).order_by(User.id.asc()).all()
        return [serialize_user(u) for u in users]

    if actor.role == "advisor":
        clients = (
            db.query(User)
            .filter(User.role == "client", User.advisor_id == actor.id)
            .order_by(User.full_name.asc())
            .all()
        )
        return [serialize_user(c) for c in clients]

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tenés permisos para listar usuarios.",
    )


def create_user_by_admin(
    db: Session,
    email: str,
    full_name: str,
    password: str,
    role: str,
    advisor_id: Optional[int] = None,
    must_change_password: bool = True,
) -> dict:
    normalized_email = email.strip().lower()
    if not normalized_email or "@" not in normalized_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ingresá un correo electrónico válido.",
        )
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rol inválido. Valores permitidos: {', '.join(VALID_ROLES)}.",
        )
    if len(password.strip()) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña inicial debe tener al menos 8 caracteres.",
        )

    existing = db.query(User).filter(User.email == normalized_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario registrado con ese correo.",
        )

    resolved_advisor_id = None
    if role == "client" and advisor_id is not None:
        advisor = (
            db.query(User)
            .filter(User.id == advisor_id, User.role.in_(["advisor", "superadmin"]))
            .first()
        )
        if not advisor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El asesor asignado no existe o no tiene rol de asesor.",
            )
        resolved_advisor_id = advisor.id

    new_user = User(
        email=normalized_email,
        full_name=full_name.strip() or normalized_email.split("@")[0],
        hashed_password=hash_password(password.strip()),
        role=role,
        is_active=True,
        must_change_password=must_change_password,
        advisor_id=resolved_advisor_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return serialize_user(new_user)


def update_user_by_admin(
    db: Session,
    target_user_id: int,
    actor: User,
    full_name: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    advisor_id: Optional[int] = None,
    clear_advisor: bool = False,
    reset_password: Optional[str] = None,
) -> dict:
    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    if user.id == actor.id and is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No podés desactivar tu propia cuenta de superadmin.",
        )

    if full_name is not None and full_name.strip():
        user.full_name = full_name.strip()

    if role is not None:
        if role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rol inválido. Valores permitidos: {', '.join(VALID_ROLES)}.",
            )
        if user.id == actor.id and role != "superadmin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No podés degradar tu propio rol de superadmin.",
            )
        user.role = role
        if role != "client":
            user.advisor_id = None

    if is_active is not None:
        user.is_active = bool(is_active)

    if clear_advisor:
        user.advisor_id = None
    elif advisor_id is not None:
        if user.role != "client":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo los usuarios con rol 'client' pueden tener asesor asignado.",
            )
        advisor = (
            db.query(User)
            .filter(User.id == advisor_id, User.role.in_(["advisor", "superadmin"]))
            .first()
        )
        if not advisor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El asesor asignado no es válido.",
            )
        user.advisor_id = advisor.id

    if reset_password is not None:
        if len(reset_password.strip()) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña reseteada debe tener al menos 8 caracteres.",
            )
        user.hashed_password = hash_password(reset_password.strip())
        user.must_change_password = True

    db.commit()
    db.refresh(user)
    return serialize_user(user)