from datetime import datetime
import re
import secrets
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
import yfinance as yf

from app.core.yf_client import _lookup_fx_multiplier
from app.models.database import ClientProfile, PortfolioTransaction, User

VALID_TX_TYPES = ("BUY", "SELL", "DIVIDEND", "DEPOSIT", "WITHDRAWAL")
VALID_RISK_PROFILES = ("conservador", "moderado", "agresivo")
VALID_HORIZONS = ("corto_plazo", "mediano_plazo", "largo_plazo")


def _assert_can_access_client(actor: User, target_client: User) -> None:
    """
    Aislamiento estricto de carteras:
    - Cada usuario puede acceder a su propia cartera.
    - Un ejecutivo (advisor o superadmin) SOLO puede acceder a carteras
      donde figura expresamente como `advisor_id`.
    """
    if actor.id == target_client.id:
        return
    if target_client.role != "client":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario seleccionado no tiene rol de cliente.",
        )
    if actor.role in ("advisor", "superadmin") and target_client.advisor_id == actor.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tenés permisos para acceder a la cartera de este cliente.",
    )


def _assert_can_edit_client(actor: User, target_client: User) -> None:
    """Tanto el titular de la cartera como su ejecutivo asignado pueden operar sobre ella."""
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
    is_managed_only = (user.auth_provider or "") == "managed"
    display_email = "" if (is_managed_only and user.email.endswith("@cartera.local")) else user.email
    return {
        "client_id": user.id,
        "full_name": user.full_name,
        "email": display_email,
        "is_active": bool(user.is_active),
        "is_managed_only": is_managed_only,
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


def fetch_live_quotes(tickers: list[str], target_currency: str = "USD") -> dict[str, dict]:
    """Obtiene precio actual y variación diaria para una lista de tickers, normalizados a `target_currency`."""
    quotes: dict[str, dict] = {}
    dest_curr = (target_currency or "USD").strip().upper()
    fx_cache: dict[str, float] = {dest_curr: 1.0}
    unique = sorted({t.strip().upper() for t in tickers if t and t.strip()})
    for sym in unique:
        try:
            tk = yf.Ticker(sym)
            fast = getattr(tk, "fast_info", None)
            price = None
            prev_close = None
            quote_curr = ""
            if fast:
                price = getattr(fast, "last_price", None)
                prev_close = getattr(fast, "previous_close", None)
                quote_curr = str(getattr(fast, "currency", None) or "").strip().upper()
            if price is None:
                hist = tk.history(period="2d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                    if len(hist) > 1:
                        prev_close = float(hist["Close"].iloc[-2])

            if not quote_curr:
                try:
                    quote_curr = str((tk.info or {}).get("currency") or "").strip().upper()
                except Exception:
                    quote_curr = ""

            fx_mult = 1.0
            if price is not None and quote_curr and quote_curr != dest_curr:
                if quote_curr not in fx_cache:
                    fx_cache[quote_curr] = _lookup_fx_multiplier(quote_curr, dest_curr)
                fx_mult = fx_cache[quote_curr]
                price = float(price) * fx_mult
                if prev_close is not None:
                    prev_close = float(prev_close) * fx_mult

            day_change_pct = None
            if price and prev_close and prev_close > 0:
                day_change_pct = round(((price - prev_close) / prev_close) * 100, 2)

            quotes[sym] = {
                "price": round(float(price), 4) if price is not None else None,
                "day_change_pct": day_change_pct,
                "currency": quote_curr or dest_curr,
            }
        except Exception:
            quotes[sym] = {"price": None, "day_change_pct": None, "currency": dest_curr}
    return quotes


def _compute_twr_metrics(
    ordered_txs: list[PortfolioTransaction],
    ending_holdings_value: float,
    net_external_deposits: float,
) -> dict:
    """
    Calcula el Time-Weighted Return (TWR) encadenando sub-períodos delimitados
    por flujos externos de caja (DEPOSIT / WITHDRAWAL), reconociendo como aporte
    implícito toda compra (BUY) realizada sin saldo de caja previo para evitar
    falsos -100% al operar sin depósitos explícitos o al liquidar el 100% de una tenencia.
    """
    if not ordered_txs:
        return {
            "twr_pct": 0.0,
            "twr_annualized_pct": None,
            "net_contributed_capital": 0.0,
            "subperiods_count": 0,
            "days_invested": 0,
        }

    by_date: dict[str, list[PortfolioTransaction]] = {}
    for tx in ordered_txs:
        d = (tx.tx_date or "").strip()
        by_date.setdefault(d, []).append(tx)

    sorted_dates = sorted(by_date.keys())
    qty_by_sym: dict[str, float] = {}
    last_known_price: dict[str, float] = {}
    cash = 0.0
    implicit_deposits_total = 0.0

    subperiod_returns: list[float] = []
    v_start: float | None = None

    for d in sorted_dates:
        day_txs = by_date[d]
        external_flow_today = 0.0
        sim_cash = cash

        # 1. Pre-evaluar flujos externos explícitos e implícitos del día antes de las operaciones
        for tx in day_txs:
            ttype = (tx.tx_type or "").upper()
            sym = (tx.ticker or "").strip().upper()
            qty = float(tx.quantity or 0.0)
            price = float(tx.unit_price or 0.0)
            comm = float(tx.commission or 0.0)

            if ttype == "DEPOSIT":
                net_dep = qty * price - comm
                external_flow_today += net_dep
                sim_cash += net_dep
            elif ttype == "WITHDRAWAL":
                net_wdr = qty * price + comm
                external_flow_today -= net_wdr
                sim_cash -= net_wdr
            elif ttype == "BUY" and sym:
                op_cost = qty * price + comm
                if sim_cash < op_cost - 1e-6:
                    shortfall = op_cost - max(0.0, sim_cash)
                    external_flow_today += shortfall
                    implicit_deposits_total += shortfall
                    sim_cash += shortfall
                sim_cash -= op_cost
                if price > 0.0:
                    last_known_price[sym] = price
            elif ttype == "SELL" and sym:
                proceeds = qty * price - comm
                sim_cash += proceeds
                if price > 0.0:
                    last_known_price[sym] = price
            elif ttype == "DIVIDEND":
                sim_cash += qty * price - comm

        holdings_val_before = sum(
            qty_by_sym.get(s, 0.0) * last_known_price.get(s, 0.0)
            for s in qty_by_sym
        )
        equity_before_flow = holdings_val_before + max(0.0, cash)

        if abs(external_flow_today) > 1e-6:
            if v_start is not None and v_start > 1e-6:
                r_sub = (equity_before_flow - v_start) / v_start
                subperiod_returns.append(r_sub)
            new_base = equity_before_flow + external_flow_today
            v_start = new_base if new_base > 1e-6 else None

        # 2. Aplicar efectivamente las operaciones del día
        for tx in day_txs:
            ttype = (tx.tx_type or "").upper()
            sym = (tx.ticker or "").strip().upper()
            qty = float(tx.quantity or 0.0)
            price = float(tx.unit_price or 0.0)
            comm = float(tx.commission or 0.0)

            if ttype == "DEPOSIT":
                cash += qty * price - comm
            elif ttype == "WITHDRAWAL":
                cash -= qty * price + comm
            elif ttype == "BUY" and sym:
                op_cost = qty * price + comm
                if cash < op_cost - 1e-6:
                    cash += op_cost - max(0.0, cash)
                qty_by_sym[sym] = qty_by_sym.get(sym, 0.0) + qty
                if price > 0.0:
                    last_known_price[sym] = price
                cash -= op_cost
            elif ttype == "SELL" and sym:
                qty_by_sym[sym] = max(0.0, qty_by_sym.get(sym, 0.0) - qty)
                if price > 0.0:
                    last_known_price[sym] = price
                cash += qty * price - comm
            elif ttype == "DIVIDEND":
                cash += qty * price - comm

        if v_start is None:
            holdings_val_after = sum(
                qty_by_sym.get(s, 0.0) * last_known_price.get(s, 0.0)
                for s in qty_by_sym
            )
            initial_eq = holdings_val_after + max(0.0, cash)
            if initial_eq > 1e-6:
                v_start = initial_eq

    ending_total_equity = ending_holdings_value + max(0.0, cash)
    if v_start is not None and v_start > 1e-6:
        r_final = (ending_total_equity - v_start) / v_start
        subperiod_returns.append(r_final)

    compound = 1.0
    for r in subperiod_returns:
        compound *= max(0.0, 1.0 + r)

    twr_pct = (compound - 1.0) * 100.0 if subperiod_returns else 0.0

    days_invested = 0
    twr_annualized_pct: float | None = None
    try:
        d_first = datetime.strptime(sorted_dates[0], "%Y-%m-%d")
        d_now = datetime.now()
        days_invested = max((d_now - d_first).days, 1)
        if days_invested >= 365 and compound > 0.0:
            years = days_invested / 365.25
            twr_annualized_pct = round(((compound ** (1.0 / years)) - 1.0) * 100.0, 2)
    except Exception:
        days_invested = 0

    effective_contributed = (
        net_external_deposits
        if abs(net_external_deposits) > 1e-6
        else implicit_deposits_total
    )

    return {
        "twr_pct": round(twr_pct, 2),
        "twr_annualized_pct": twr_annualized_pct,
        "net_contributed_capital": round(effective_contributed, 2),
        "subperiods_count": len(subperiod_returns),
        "days_invested": days_invested,
    }


def compute_portfolio_positions(
    transactions: list[PortfolioTransaction],
    quotes_map: Optional[dict[str, dict]] = None,
    target_currency: str = "USD",
) -> dict:
    """
    Motor contable de Precio Promedio Ponderado (PPP) + Time-Weighted Return (TWR).
    Ordena cronológicamente por (tx_date, id), ubicando operaciones nuevas aún sin ID
    al final de su fecha para validar correctamente compras y ventas en el mismo día.
    """
    ordered = sorted(
        transactions,
        key=lambda t: (t.tx_date or "", t.id if t.id is not None else float("inf")),
    )
    ledger: dict[str, dict] = {}
    cash_balance = 0.0
    total_dividends = 0.0
    total_realized_pnl = 0.0
    net_external_deposits = 0.0

    for tx in ordered:
        ttype = (tx.tx_type or "").upper()
        sym = (tx.ticker or "").strip().upper()
        qty = float(tx.quantity or 0.0)
        price = float(tx.unit_price or 0.0)
        comm = float(tx.commission or 0.0)

        if ttype == "DEPOSIT":
            net_dep = qty * price - comm
            cash_balance += net_dep
            net_external_deposits += net_dep
            continue

        if ttype == "WITHDRAWAL":
            net_wdr = qty * price + comm
            cash_balance -= net_wdr
            net_external_deposits -= net_wdr
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
        quotes_map
        if quotes_map is not None
        else fetch_live_quotes(open_symbols, target_currency=target_currency)
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
    total_equity = total_market_value + max(0.0, cash_balance)

    twr_metrics = _compute_twr_metrics(
        ordered_txs=ordered,
        ending_holdings_value=total_market_value,
        net_external_deposits=net_external_deposits,
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
            "total_equity": round(total_equity, 2),
            **twr_metrics,
        },
        "holdings": holdings,
    }


def list_accessible_clients(db: Session, actor: User) -> list[dict]:
    """
    Devuelve únicamente los clientes bajo la gestión directa del ejecutivo (`advisor_id == actor.id`),
    o el propio usuario si es `client`. Nunca expone clientes independientes sin ejecutivo asignado.
    """
    if actor.role in ("superadmin", "advisor"):
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


def create_managed_client(
    db: Session,
    actor: User,
    full_name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    risk_profile: str = "moderado",
    investment_horizon: str = "largo_plazo",
    target_currency: str = "USD",
    notes: Optional[str] = None,
) -> dict:
    """
    Permite a un ejecutivo (advisor/superadmin) crear una cartera de seguimiento
    para un cliente propio aunque no esté registrado en la plataforma.
    """
    if actor.role not in ("superadmin", "advisor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo asesores o administradores pueden dar de alta carteras de clientes.",
        )

    clean_name = (full_name or "").strip()
    if len(clean_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ingresá el nombre completo del cliente.",
        )

    if risk_profile not in VALID_RISK_PROFILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Perfil de riesgo inválido. Opciones: {', '.join(VALID_RISK_PROFILES)}.",
        )
    if investment_horizon not in VALID_HORIZONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Horizonte inválido. Opciones: {', '.join(VALID_HORIZONS)}.",
        )

    slug = re.sub(r"[^a-z0-9]", "", clean_name.lower())[:16] or "cliente"
    rand_hex = secrets.token_hex(3)

    clean_email = (email or "").strip().lower()
    if clean_email:
        if db.query(User).filter(func.lower(User.email) == clean_email).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una cuenta registrada con ese correo electrónico.",
            )
    else:
        clean_email = f"cli.{slug}.{rand_hex}@cartera.local"

    candidate_username = f"cli_{slug}_{rand_hex}"[:32]
    while db.query(User).filter(func.lower(User.username) == candidate_username).first():
        candidate_username = f"cli_{slug}_{secrets.token_hex(3)}"[:32]

    managed_user = User(
        username=candidate_username,
        email=clean_email,
        full_name=clean_name,
        hashed_password=None,
        auth_provider="managed",
        role="client",
        is_active=True,
        must_change_password=False,
        advisor_id=int(actor.id),
    )
    db.add(managed_user)
    db.flush()

    prof = ClientProfile(
        user_id=int(managed_user.id),
        risk_profile=risk_profile,
        investment_horizon=investment_horizon,
        target_currency=(target_currency or "USD").strip().upper()[:10],
        phone=(phone or "").strip() or None,
        notes=(notes or "").strip() or None,
    )
    db.add(prof)
    db.commit()
    db.refresh(managed_user)
    db.refresh(prof)
    return serialize_client_profile(managed_user, prof)


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
    computed = compute_portfolio_positions(
        txs,
        quotes_map=quotes_map,
        target_currency=(prof.target_currency or "USD").upper(),
    )

    return {
        "client": serialize_client_profile(target, prof),
        "can_edit": True,
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
        next_curr = target_currency.strip().upper()[:10]
        curr_base = (prof.target_currency or "USD").strip().upper()
        if next_curr != curr_base:
            has_txs = (
                db.query(PortfolioTransaction.id)
                .filter(PortfolioTransaction.client_id == target.id)
                .first()
            )
            if has_txs is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No podés cambiar la moneda base ({curr_base} → {next_curr}) mientras existan operaciones cargadas en la cartera.",
                )
        prof.target_currency = next_curr

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

    prof = get_or_create_client_profile(db, int(target.id))
    target_curr = (prof.target_currency or "USD").strip().upper()
    tx_curr = (currency or target_curr).strip().upper()[:10]
    if tx_curr != target_curr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La operación debe registrarse en la moneda base de la cartera ({target_curr}) para evitar mezclas en PPP y TWR.",
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
        currency=tx_curr,
        notes=(notes or "").strip() or None,
    )

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
    compute_portfolio_positions(remaining_txs, quotes_map={})

    db.delete(tx)
    db.commit()