from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user, get_db
from app.models.database import User
from app.services.portfolio_service import (
    add_portfolio_transaction,
    create_managed_client,
    delete_portfolio_transaction,
    get_client_portfolio_detail,
    list_accessible_clients,
    update_client_profile_data,
)

portfolio_router = APIRouter(prefix="/portfolios", tags=["CRM y Carteras"])


class CreateManagedClientRequest(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    risk_profile: str = "moderado"
    investment_horizon: str = "largo_plazo"
    target_currency: str = "USD"
    notes: Optional[str] = None


class UpdateClientProfileRequest(BaseModel):
    risk_profile: Optional[str] = None
    investment_horizon: Optional[str] = None
    target_currency: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class CreateTransactionRequest(BaseModel):
    tx_type: str
    ticker: Optional[str] = None
    tx_date: str
    quantity: float
    unit_price: float
    commission: float = 0.0
    currency: str = "USD"
    notes: Optional[str] = None


@portfolio_router.get("/clients")
def get_clients(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"clients": list_accessible_clients(db, current_user)}


@portfolio_router.post("/clients")
def post_managed_client(
    payload: CreateManagedClientRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    created = create_managed_client(
        db=db,
        actor=current_user,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        risk_profile=payload.risk_profile,
        investment_horizon=payload.investment_horizon,
        target_currency=payload.target_currency,
        notes=payload.notes,
    )
    return {"status": "created", "client": created}


@portfolio_router.get("/me")
def get_my_portfolio(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_client_portfolio_detail(db, current_user, int(current_user.id))


@portfolio_router.get("/{client_id}")
def get_client_portfolio(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_client_portfolio_detail(db, current_user, client_id)


@portfolio_router.patch("/{client_id}/profile")
def patch_client_profile(
    client_id: int,
    payload: UpdateClientProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = update_client_profile_data(
        db=db,
        actor=current_user,
        client_id=client_id,
        risk_profile=payload.risk_profile,
        investment_horizon=payload.investment_horizon,
        target_currency=payload.target_currency,
        phone=payload.phone,
        notes=payload.notes,
    )
    return {"status": "updated", "client": updated}


@portfolio_router.post("/{client_id}/transactions")
def create_transaction(
    client_id: int,
    payload: CreateTransactionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    add_portfolio_transaction(
        db=db,
        actor=current_user,
        client_id=client_id,
        tx_type=payload.tx_type,
        ticker=payload.ticker,
        tx_date=payload.tx_date,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        commission=payload.commission,
        currency=payload.currency,
        notes=payload.notes,
    )
    return get_client_portfolio_detail(db, current_user, client_id)


@portfolio_router.delete("/{client_id}/transactions/{tx_id}")
def remove_transaction(
    client_id: int,
    tx_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delete_portfolio_transaction(db, current_user, client_id, tx_id)
    return get_client_portfolio_detail(db, current_user, client_id)