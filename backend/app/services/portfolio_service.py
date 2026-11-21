from datetime import datetime
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
import yfinance as yf

from app.models.database import ClientProfile, PortfolioTransaction, User

VALID_TX_TYPES = ("BUY", "SELL", "DIVIDEND", "DEPOSIT", "WITHDRAWAL")
VALID_RISK_PROFILES = ("conservador", "moderado", "agresivo")
VALID_HORIZONS = ("corto_plazo", "mediano_plazo", "largo_plazo")


def _assert_can_access_client(actor: User, target_client: User) -> None:
    if target_client.role != "client":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario seleccionado no tiene rol de cliente.",
        )
    if actor.role == "superadmin":
        return
    if actor.role == "advisor" and target_client.advisor_id == actor.id:
        return
    if actor.role == "client" and target_client.id == actor.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tenés permisos para acceder a la cartera de este cliente.",
    )


def _assert_can_edit_client(actor: User, target_client: User) -> None:
    if actor.role == "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Los clientes tienen acceso de solo lectura sobre su cartera.",
        )
    _assert_can_access_client(actor, target_client)


def get_or_create_client_profile(db: Session, client_id: int) -> ClientProfile:
    profile = (
        db.query(ClientProfile).filter(ClientProfile.user_id == client_id).first()
    )
    if not profile:
        profile = ClientProfile(
            user_id=client_id,
            risk_profile="moderado",
            investment_horizon="largo_plazo",
            target_currency="USD",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def serialize_client_profile(user: User, profile: ClientProfile) -> dict:
    return {
        "client_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "is_active": bool(user.is_active),
        "advisor_id": user.advisor_id,
        "advisor_name": user.advisor.full_name if user.advisor else None,
        "risk_profile": profile.risk_profile,
        "investment_horizon": profile.investment_horizon,
        "target_currency": profile.target_currency,
        "phone": profile.phone or "",
        "notes": profile.notes or "",
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


def serialize_transaction(tx: PortfolioTransaction) -> dict:
    gross_amount = round(float(tx.quantity) * float(tx.unit_price), 4)
    return {
        "id": tx.id,
        "client_id": tx.client_id,
        "tx_type": tx.tx_type,
        "ticker": tx.ticker,
        "tx_date": tx.tx_date,
        "quantity": float(tx.quantity),
        "unit_price": float(tx.unit_price),
        "commission": float(tx.commission),
        "gross_amount": gross_amount,
        "currency": tx.currency,
        "notes": tx.notes or "",
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
    }


def fetch_live_quotes(tickers: list[str]) -> dict[str, dict]:
    """Obtiene precio actual y nombre corto para una lista de tickers."""
    quotes: dict[str, dict] = {}
    unique = sorted({t.strip().upper() for t in tickers if t and t.strip()})
    for sym in unique:
        try:
            tk = yf.Ticker(sym)
            fast = getattr(tk, "fast_info", None)
            price = None
            prev_close = None
            if fast:
                price = getattr(fast, "last_price", None)
                prev_close = getattr(fast, "previous_close", None)
            if price is None:
                hist = tk.history(period="2d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                    if len(hist) > 1:
                        prev_close = float(hist["Close"].iloc[-2])

            day_change_pct = None
            if price and prev_close and prev_close > 0:
                day_change_pct = round(((price - prev_close) / prev_close) * 100, 2)

            quotes[sym] = {
                "price": round(float(price), 4) if price is not None else None,
                "day_change_pct": day_change_pct,
            }
        except Exception:
            quotes[sym] = {"price": None, "day_change_pct": None}
    return quotes


def compute_portfolio_positions(
    transactions: list[PortfolioTransaction],
    quotes_map: Optional[dict[str, dict]] = None,
) -> dict:
    """
    Motor contable de Precio Promedio Ponderado (PPP).
    Ordena cronológicamente por (tx_date, id) y calcula tenencias, PPP,
    P&L realizado, P&L no realizado, dividendos y caja neta.
    """
    ordered = sorted(transactions, key=lambda t: (t.tx_date or "", t.id or 0))
    ledger: dict[str, dict] = {}
    cash_balance = 0.0
    total_dividends = 0.0
    total_realized_pnl = 0.0

    for tx in ordered:
        ttype = (tx.tx_type or "").upper()
        sym = (tx.ticker or "").strip().upper()
        qty = float(tx.quantity or 0.0)
        price = float(tx.unit_price or 0.0)
        comm = float(tx.commission or 0.0)

        if ttype == "DEPOSIT":
            cash_balance += qty * price - comm
            continue

        if ttype == "WITHDRAWAL":
            cash_balance -= qty * price + comm
            continue

        if not sym:
            continue

        if sym not in ledger:
            ledger[sym] = {
                "ticker": sym,
                "quantity": 0.0,
                "total_cost": 0.0,
                "ppp": 0.0,
                "realized_pnl": 0.0,
                "dividends": 0.0,
                "commissions": 0.0,
            }

        pos = ledger[sym]

        if ttype == "BUY":
            op_cost = qty * price + comm
            pos["quantity"] += qty
            pos["total_cost"] += op_cost
            pos["commissions"] += comm
            pos["ppp"] = (
                pos["total_cost"] / pos["quantity"] if pos["quantity"] > 1e-9 else 0.0
            )
            cash_balance -= op_cost

        elif ttype == "SELL":
            if qty > pos["quantity"] + 1e-6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Operación inválida en {sym}: intentás vender {qty} nominales pero la tenencia disponible es {round(pos['quantity'], 4)}.",
                )
            avg_cost = pos["ppp"]
            proceeds = qty * price - comm
            cost_removed = qty * avg_cost
            realized = proceeds - cost_removed

            pos["quantity"] = max(0.0, pos["quantity"] - qty)
            pos["total_cost"] = max(0.0, pos["total_cost"] - cost_removed)
            pos["realized_pnl"] += realized
            pos["commissions"] += comm
            if pos["quantity"] <= 1e-9:
                pos["quantity"] = 0.0
                pos["total_cost"] = 0.0
                pos["ppp"] = 0.0

            total_realized_pnl += realized
            cash_balance += proceeds

        elif ttype == "DIVIDEND":
            net_div = qty * price - comm
            pos["dividends"] += net_div
            pos["commissions"] += comm
            total_dividends += net_div
            cash_balance += net_div

    open_symbols = [s for s, p in ledger.items() if p["quantity"] > 1e-6]
    resolved_quotes = (
        quotes_map if quotes_map is not None else fetch_live_quotes(open_symbols)
    )

    holdings = []
    total_invested_cost = 0.0
    total_market_value = 0.0

    for sym in sorted(ledger.keys()):
        pos = ledger[sym]
        if pos["quantity"] <= 1e-6:
            continue

        q_info = resolved_quotes.get(sym, {})
        current_price = q_info.get("price")
        effective_price = current_price if current_price is not None else pos["ppp"]
        market_value = pos["quantity"] * effective_price
        unrealized_pnl = market_value - pos["total_cost"]
        unrealized_pnl_pct = (
            (unrealized_pnl / pos["total_cost"]) * 100
            if pos["total_cost"] > 1e-9
            else 0.0
        )

        total_invested_cost += pos["total_cost"]
        total_market_value += market_value

        holdings.append(
            {
                "ticker": sym,
                "quantity": round(pos["quantity"], 4),
                "ppp": round(pos["ppp"], 4),
                "total_cost": round(pos["total_cost"], 2),
                "current_price": round(effective_price, 4),
                "has_live_quote": current_price is not None,
                "day_change_pct": q_info.get("day_change_pct"),
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
                "realized_pnl": round(pos["realized_pnl"], 2),
                "dividends": round(pos["dividends"], 2),
                "weight_pct": 0.0,
            }
        )

    for h in holdings:
        h["weight_pct"] = (
            round((h["market_value"] / total_market_value) * 100, 2)
            if total_market_value > 1e-9
            else 0.0
        )

    holdings.sort(key=lambda item: item["market_value"], reverse=True)

    total_unrealized_pnl = total_market_value - total_invested_cost
    total_unrealized_pct = (
        (total_unrealized_pnl / total_invested_cost) * 100
        if total_invested_cost > 1e-9
        else 0.0
    )

    return {
        "summary": {
            "positions_count": len(holdings),
            "total_invested_cost": round(total_invested_cost, 2),
            "total_market_value": round(total_market_value, 2),
            "total_unrealized_pnl": round(total_unrealized_pnl, 2),
            "total_unrealized_pct": round(total_unrealized_pct, 2),
            "total_realized_pnl": round(total_realized_pnl, 2),
            "total_dividends": round(total_dividends, 2),
            "cash_balance": round(cash_balance, 2),
            "total_equity": round(total_market_value + max(0.0, cash_balance), 2),
        },
        "holdings": holdings,
    }


def list_accessible_clients(db: Session, actor: User) -> list[dict]:
    if actor.role == "superadmin":
        clients = (
            db.query(User)
            .filter(User.role == "client")
            .order_by(User.full_name.asc())
            .all()
        )
    elif actor.role == "advisor":
        clients = (
            db.query(User)
            .filter(User.role == "client", User.advisor_id == actor.id)
            .order_by(User.full_name.asc())
            .all()
        )
    else:
        clients = [actor]

    result = []
    for c in clients:
        prof = get_or_create_client_profile(db, int(c.id))
        result.append(serialize_client_profile(c, prof))
    return result


def get_client_portfolio_detail(
    db: Session,
    actor: User,
    client_id: int,
    quotes_map: Optional[dict[str, dict]] = None,
) -> dict:
    target = db.query(User).filter(User.id == client_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado.",
        )
    _assert_can_access_client(actor, target)

    prof = get_or_create_client_profile(db, int(target.id))
    txs = (
        db.query(PortfolioTransaction)
        .filter(PortfolioTransaction.client_id == target.id)
        .order_by(PortfolioTransaction.tx_date.desc(), PortfolioTransaction.id.desc())
        .all()
    )
    computed = compute_portfolio_positions(txs, quotes_map=quotes_map)

    return {
        "client": serialize_client_profile(target, prof),
        "can_edit": actor.role in ("superadmin", "advisor"),
        "summary": computed["summary"],
        "holdings": computed["holdings"],
        "transactions": [serialize_transaction(t) for t in txs],
    }


def update_client_profile_data(
    db: Session,
    actor: User,
    client_id: int,
    risk_profile: Optional[str] = None,
    investment_horizon: Optional[str] = None,
    target_currency: Optional[str] = None,
    phone: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    target = db.query(User).filter(User.id == client_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado.",
        )
    _assert_can_edit_client(actor, target)

    prof = get_or_create_client_profile(db, int(target.id))

    if risk_profile is not None:
        if risk_profile not in VALID_RISK_PROFILES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Perfil de riesgo inválido. Opciones: {', '.join(VALID_RISK_PROFILES)}.",
            )
        prof.risk_profile = risk_profile

    if investment_horizon is not None:
        if investment_horizon not in VALID_HORIZONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Horizonte inválido. Opciones: {', '.join(VALID_HORIZONS)}.",
            )
        prof.investment_horizon = investment_horizon

    if target_currency is not None and target_currency.strip():
        prof.target_currency = target_currency.strip().upper()[:10]

    if phone is not None:
        prof.phone = phone.strip()

    if notes is not None:
        prof.notes = notes.strip()

    db.commit()
    db.refresh(prof)
    return serialize_client_profile(target, prof)


def add_portfolio_transaction(
    db: Session,
    actor: User,
    client_id: int,
    tx_type: str,
    tx_date: str,
    quantity: float,
    unit_price: float,
    ticker: Optional[str] = None,
    commission: float = 0.0,
    currency: str = "USD",
    notes: Optional[str] = None,
) -> PortfolioTransaction:
    target = db.query(User).filter(User.id == client_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado.",
        )
    _assert_can_edit_client(actor, target)

    normalized_type = tx_type.strip().upper()
    if normalized_type not in VALID_TX_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de operación inválido. Opciones: {', '.join(VALID_TX_TYPES)}.",
        )

    normalized_ticker = (ticker or "").strip().upper() or None
    if normalized_type in ("BUY", "SELL", "DIVIDEND") and not normalized_ticker:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El ticker es obligatorio para operaciones de compra, venta o dividendo.",
        )

    if quantity <= 0 or unit_price < 0 or commission < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cantidad debe ser mayor a 0 y precio/comisión no pueden ser negativos.",
        )

    try:
        datetime.strptime(tx_date.strip(), "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de operación debe tener formato YYYY-MM-DD.",
        )

    new_tx = PortfolioTransaction(
        client_id=int(target.id),
        created_by_id=int(actor.id),
        tx_type=normalized_type,
        ticker=normalized_ticker,
        tx_date=tx_date.strip(),
        quantity=float(quantity),
        unit_price=float(unit_price),
        commission=float(commission),
        currency=(currency or "USD").strip().upper()[:10],
        notes=(notes or "").strip() or None,
    )

    # Validación preventiva de integridad de tenencias (evitar venta en descubierto)
    existing_txs = (
        db.query(PortfolioTransaction)
        .filter(PortfolioTransaction.client_id == target.id)
        .all()
    )
    compute_portfolio_positions([*existing_txs, new_tx], quotes_map={})

    db.add(new_tx)
    db.commit()
    db.refresh(new_tx)
    return new_tx


def delete_portfolio_transaction(
    db: Session,
    actor: User,
    client_id: int,
    tx_id: int,
) -> None:
    target = db.query(User).filter(User.id == client_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado.",
        )
    _assert_can_edit_client(actor, target)

    tx = (
        db.query(PortfolioTransaction)
        .filter(
            PortfolioTransaction.id == tx_id,
            PortfolioTransaction.client_id == target.id,
        )
        .first()
    )
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operación no encontrada.",
        )

    remaining_txs = (
        db.query(PortfolioTransaction)
        .filter(
            PortfolioTransaction.client_id == target.id,
            PortfolioTransaction.id != tx_id,
        )
        .all()
    )
    # Verificar que eliminar esta compra no deje ventas posteriores sin respaldo
    compute_portfolio_positions(remaining_txs, quotes_map={})

    db.delete(tx)
    db.commit()