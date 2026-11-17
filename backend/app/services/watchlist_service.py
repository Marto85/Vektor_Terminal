from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy.orm import Session

from app.models.database import (
    Watchlist,
    WatchlistItem,
    AlertNotification,
    CompanyMarketCache,
    CompanyEstimatesCache,
    CompanyProfile,
)
from app.core.yf_client import get_company_profile

MAX_WATCHLISTS = 10
ARG_TZ = timezone(timedelta(hours=-3))

METRIC_LABELS: dict[str, str] = {
    "price": "Precio (US$)",
    "change_pct": "Variación Diaria (%)",
    "market_cap_mm": "Cap. Bursátil (MM)",
    "pe_ltm": "P/E LTM",
    "pe_ntm": "P/E NTM",
    "ev_ebitda_ltm": "EV/EBITDA",
    "pb_ltm": "P/BV",
    "p_fcf_ltm": "P/FCF",
    "fcf_yield_pct": "FCF Yield (%)",
    "ebit_margin_pct": "Margen EBIT (%)",
    "roic_pct": "ROIC (%)",
    "roe_pct": "ROE (%)",
    "net_debt_to_ebitda": "DN/EBITDA",
    "rev_growth_yoy_pct": "Crec. Ventas (%)",
    "upside_ws_pct": "Potencial WS (%)",
}


def _format_arg_timestamp(dt: datetime | None) -> str:
    if not isinstance(dt, datetime):
        return ""
    aware = dt.replace(tzinfo=timezone.utc).astimezone(ARG_TZ)
    return aware.strftime("%d/%m/%Y %H:%M")


def _ensure_default_watchlist(db: Session) -> Watchlist:
    first = db.query(Watchlist).order_by(Watchlist.id.asc()).first()
    if first:
        return first
    default_wl = Watchlist(name="Principal")
    db.add(default_wl)
    db.commit()
    db.refresh(default_wl)
    return default_wl


def _extract_ticker_snapshot(ticker: str, db: Session) -> dict[str, Any]:
    sym = ticker.upper().strip()
    cache_row = db.query(CompanyMarketCache).filter(CompanyMarketCache.ticker == sym).first()
    raw_md = getattr(cache_row, "market_data", None) if cache_row else None
    md: dict[str, Any] = dict(raw_md) if isinstance(raw_md, dict) else {}

    cached_name = str(md.get("name") or "").strip()
    if not cache_row or len(md) == 0 or not cached_name or cached_name.upper() == sym:
        try:
            prof_payload = get_company_profile(sym, db)
            if isinstance(prof_payload, dict) and prof_payload.get("name"):
                cached_name = str(prof_payload["name"]).strip()
            cache_row = db.query(CompanyMarketCache).filter(CompanyMarketCache.ticker == sym).first()
            raw_md_refreshed = getattr(cache_row, "market_data", None) if cache_row else None
            if isinstance(raw_md_refreshed, dict):
                md = dict(raw_md_refreshed)
        except Exception:
            pass

    if not cached_name or cached_name.upper() == sym:
        prof_row = db.query(CompanyProfile).filter(CompanyProfile.ticker == sym).first()
        if prof_row and getattr(prof_row, "name", None):
            cached_name = str(getattr(prof_row, "name")).strip()

    company_name = cached_name if cached_name else sym

    sm = md.get("summary_metrics") or {}
    val = sm.get("valuation") or {}
    eff = sm.get("efficiency") or {}
    cap = sm.get("capital") or {}
    grw = sm.get("growth") or {}

    price = md.get("price")
    target_price = val.get("target_price")
    upside_ws_pct = None
    if isinstance(price, (int, float)) and price > 0 and isinstance(target_price, (int, float)) and target_price > 0:
        upside_ws_pct = round(((target_price - price) / price) * 100.0, 2)
    else:
        est_row = db.query(CompanyEstimatesCache).filter(CompanyEstimatesCache.ticker == sym).first()
        raw_est = getattr(est_row, "estimates_data", None) if est_row else None
        if isinstance(raw_est, dict):
            tp_est = raw_est.get("target_price_mean")
            if isinstance(price, (int, float)) and price > 0 and isinstance(tp_est, (int, float)) and tp_est > 0:
                upside_ws_pct = round(((tp_est - price) / price) * 100.0, 2)

    mcap = cap.get("market_cap")
    fcf_ltm = grw.get("fcf_ltm")
    fcf_yield_pct = None
    if isinstance(mcap, (int, float)) and mcap > 0 and isinstance(fcf_ltm, (int, float)):
        fcf_yield_pct = round((fcf_ltm / mcap) * 100.0, 2)

    return {
        "ticker": sym,
        "name": company_name,
        "sector": md.get("sector") or "",
        "industry": md.get("industry") or "",
        "price": price,
        "change_pct": md.get("change_pct"),
        "market_cap_mm": mcap,
        "pe_ltm": val.get("pe_ltm"),
        "pe_ntm": val.get("pe_ntm"),
        "ev_ebitda_ltm": val.get("ev_ebitda_ltm"),
        "pb_ltm": val.get("pb_ltm"),
        "p_fcf_ltm": val.get("p_fcf_ltm"),
        "fcf_yield_pct": fcf_yield_pct,
        "ebit_margin_pct": eff.get("ebit_margin"),
        "roic_pct": eff.get("roic"),
        "roe_pct": eff.get("roe"),
        "net_debt_to_ebitda": cap.get("net_debt_to_ebitda"),
        "rev_growth_yoy_pct": grw.get("revenue_growth_yoy"),
        "upside_ws_pct": upside_ws_pct,
    }


def _evaluate_and_persist_alerts(
    db: Session,
    watchlist_id: int,
    watchlist_name: str,
    item: WatchlistItem,
    snap: dict[str, Any],
) -> list[dict[str, Any]]:
    triggered: list[dict[str, Any]] = []
    price = snap.get("price")
    sym = str(getattr(item, "ticker"))
    comp_name = str(snap.get("name") or sym)

    buy_tp = getattr(item, "buy_target_price", None)
    if isinstance(buy_tp, (int, float)) and buy_tp > 0 and isinstance(price, (int, float)) and price > 0:
        if price <= buy_tp:
            diff_pct = round(((price - buy_tp) / buy_tp) * 100.0, 2)
            fp = f"{watchlist_id}:{sym}:buy:{buy_tp:.4f}"
            triggered.append({
                "fingerprint": fp,
                "watchlist_id": watchlist_id,
                "watchlist_name": watchlist_name,
                "ticker": sym,
                "name": comp_name,
                "type": "buy_target",
                "label": "Objetivo de Compra alcanzado",
                "detail": f"US$ {price:.2f} ≤ Obj. US$ {buy_tp:.2f} ({diff_pct:+.1f}%)",
            })

    sell_tp = getattr(item, "sell_target_price", None)
    if isinstance(sell_tp, (int, float)) and sell_tp > 0 and isinstance(price, (int, float)) and price > 0:
        if price >= sell_tp:
            diff_pct = round(((price - sell_tp) / sell_tp) * 100.0, 2)
            fp = f"{watchlist_id}:{sym}:sell:{sell_tp:.4f}"
            triggered.append({
                "fingerprint": fp,
                "watchlist_id": watchlist_id,
                "watchlist_name": watchlist_name,
                "ticker": sym,
                "name": comp_name,
                "type": "sell_target",
                "label": "Objetivo de Venta alcanzado",
                "detail": f"US$ {price:.2f} ≥ Obj. US$ {sell_tp:.2f} ({diff_pct:+.1f}%)",
            })

    raw_alerts = getattr(item, "alerts", None)
    rules = raw_alerts if isinstance(raw_alerts, list) else []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        metric_key = str(rule.get("metric") or "").strip()
        op = str(rule.get("op") or "<=").strip()
        threshold = rule.get("value")
        if metric_key not in METRIC_LABELS or not isinstance(threshold, (int, float)):
            continue

        current_val = snap.get(metric_key)
        if not isinstance(current_val, (int, float)):
            continue

        matched = (current_val <= threshold) if op == "<=" else (current_val >= threshold)
        if matched:
            m_label = METRIC_LABELS[metric_key]
            fp = f"{watchlist_id}:{sym}:{metric_key}:{op}:{threshold:.4f}"
            triggered.append({
                "fingerprint": fp,
                "watchlist_id": watchlist_id,
                "watchlist_name": watchlist_name,
                "ticker": sym,
                "name": comp_name,
                "type": "custom_metric",
                "label": f"Alerta en {m_label}",
                "detail": f"{m_label}: {current_val:.2f} {op} {threshold:.2f}",
            })

    # Deduplicar contra cualquier notificación ya emitida (leída o no) para esta misma regla/umbral
    for al in triggered:
        already_emitted = (
            db.query(AlertNotification)
            .filter(AlertNotification.rule_fingerprint == al["fingerprint"])
            .first()
        )
        if not already_emitted:
            db.add(
                AlertNotification(
                    rule_fingerprint=al["fingerprint"],
                    watchlist_id=al["watchlist_id"],
                    watchlist_name=al["watchlist_name"],
                    ticker=al["ticker"],
                    company_name=al["name"],
                    alert_type=al["type"],
                    title=al["label"],
                    detail=al["detail"],
                    is_read=False,
                )
            )

    return triggered


def get_all_watchlists_payload(db: Session) -> dict[str, Any]:
    _ensure_default_watchlist(db)
    watchlists = db.query(Watchlist).order_by(Watchlist.id.asc()).all()

    snapshots_cache: dict[str, dict[str, Any]] = {}
    all_triggered_alerts: list[dict[str, Any]] = []
    watchlists_out: list[dict[str, Any]] = []

    for wl in watchlists:
        wl_id = int(getattr(wl, "id"))
        wl_name = str(getattr(wl, "name"))
        items = (
            db.query(WatchlistItem)
            .filter(WatchlistItem.watchlist_id == wl_id)
            .order_by(WatchlistItem.position.asc(), WatchlistItem.id.asc())
            .all()
        )
        items_out: list[dict[str, Any]] = []

        for it in items:
            sym = str(getattr(it, "ticker")).upper()
            if sym not in snapshots_cache:
                snapshots_cache[sym] = _extract_ticker_snapshot(sym, db)
            snap = snapshots_cache[sym]

            item_alerts = _evaluate_and_persist_alerts(db, wl_id, wl_name, it, snap)
            all_triggered_alerts.extend(item_alerts)

            price = snap.get("price")
            buy_tp = getattr(it, "buy_target_price", None)
            sell_tp = getattr(it, "sell_target_price", None)
            thesis_val = getattr(it, "thesis_note", None)
            alerts_val = getattr(it, "alerts", None)

            dist_buy_pct = None
            if isinstance(price, (int, float)) and price > 0 and isinstance(buy_tp, (int, float)) and buy_tp > 0:
                dist_buy_pct = round(((price - buy_tp) / buy_tp) * 100.0, 2)

            dist_sell_pct = None
            if isinstance(price, (int, float)) and price > 0 and isinstance(sell_tp, (int, float)) and sell_tp > 0:
                dist_sell_pct = round(((sell_tp - price) / price) * 100.0, 2)

            items_out.append({
                "id": int(getattr(it, "id")),
                "watchlist_id": wl_id,
                "position": int(getattr(it, "position", 0) or 0),
                "buy_target_price": buy_tp,
                "sell_target_price": sell_tp,
                "dist_buy_pct": dist_buy_pct,
                "dist_sell_pct": dist_sell_pct,
                "thesis_note": thesis_val or "",
                "alerts": alerts_val if isinstance(alerts_val, list) else [],
                "triggered_alerts": item_alerts,
                **snap,
            })

        watchlists_out.append({
            "id": wl_id,
            "name": wl_name,
            "item_count": len(items_out),
            "items": items_out,
        })

    db.commit()

    notif_rows = (
        db.query(AlertNotification)
        .order_by(AlertNotification.triggered_at.desc(), AlertNotification.id.desc())
        .limit(60)
        .all()
    )
    notifications_out = [
        {
            "id": int(getattr(n, "id")),
            "watchlist_id": int(getattr(n, "watchlist_id")),
            "watchlist_name": str(getattr(n, "watchlist_name")),
            "ticker": str(getattr(n, "ticker")),
            "company_name": str(getattr(n, "company_name")),
            "alert_type": str(getattr(n, "alert_type")),
            "title": str(getattr(n, "title")),
            "detail": str(getattr(n, "detail")),
            "is_read": bool(getattr(n, "is_read")),
            "triggered_at": _format_arg_timestamp(getattr(n, "triggered_at", None)),
        }
        for n in notif_rows
    ]
    unread_count = sum(1 for n in notifications_out if not n["is_read"])

    return {
        "max_watchlists": MAX_WATCHLISTS,
        "count": len(watchlists_out),
        "remaining_slots": max(0, MAX_WATCHLISTS - len(watchlists_out)),
        "watchlists": watchlists_out,
        "triggered_alerts": all_triggered_alerts,
        "notifications": notifications_out,
        "unread_notifications_count": unread_count,
    }


def create_watchlist(db: Session, name: str) -> dict[str, Any]:
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("El nombre de la watchlist no puede estar vacío.")
    if len(clean_name) > 60:
        raise ValueError("El nombre de la watchlist no puede superar los 60 caracteres.")

    total = db.query(Watchlist).count()
    if total >= MAX_WATCHLISTS:
        raise ValueError(f"Alcanzaste el límite máximo de {MAX_WATCHLISTS} watchlists distintas.")

    exists = db.query(Watchlist).filter(Watchlist.name.ilike(clean_name)).first()
    if exists:
        raise ValueError(f"Ya existe una watchlist llamada '{exists.name}'.")

    wl = Watchlist(name=clean_name)
    db.add(wl)
    db.commit()
    return get_all_watchlists_payload(db)


def rename_watchlist(db: Session, watchlist_id: int, new_name: str) -> dict[str, Any]:
    clean_name = (new_name or "").strip()
    if not clean_name:
        raise ValueError("El nombre no puede estar vacío.")
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not wl:
        raise ValueError("Watchlist no encontrada.")

    dup = (
        db.query(Watchlist)
        .filter(Watchlist.id != watchlist_id, Watchlist.name.ilike(clean_name))
        .first()
    )
    if dup:
        raise ValueError(f"Ya existe otra watchlist llamada '{dup.name}'.")

    setattr(wl, "name", clean_name[:60])
    db.commit()
    return get_all_watchlists_payload(db)


def delete_watchlist(db: Session, watchlist_id: int) -> dict[str, Any]:
    total = db.query(Watchlist).count()
    if total <= 1:
        raise ValueError("Debe existir al menos 1 watchlist activa en tu tablero.")

    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not wl:
        raise ValueError("Watchlist no encontrada.")

    db.query(WatchlistItem).filter(WatchlistItem.watchlist_id == watchlist_id).delete()
    db.delete(wl)
    db.commit()
    return get_all_watchlists_payload(db)


def reorder_watchlist_items(db: Session, watchlist_id: int, ordered_tickers: list[str]) -> dict[str, Any]:
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not wl:
        raise ValueError("Watchlist no encontrada.")

    items = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.watchlist_id == watchlist_id)
        .all()
    )
    by_ticker = {str(getattr(it, "ticker")).upper(): it for it in items}

    pos = 0
    seen: set[str] = set()
    for raw_sym in ordered_tickers:
        sym = (raw_sym or "").upper().strip()
        if sym in by_ticker and sym not in seen:
            setattr(by_ticker[sym], "position", pos)
            seen.add(sym)
            pos += 1

    for sym, it in by_ticker.items():
        if sym not in seen:
            setattr(it, "position", pos)
            pos += 1

    db.commit()
    return get_all_watchlists_payload(db)


def upsert_watchlist_item(
    db: Session,
    watchlist_id: int,
    ticker: str,
    buy_target_price: float | None = None,
    sell_target_price: float | None = None,
    thesis_note: str | None = None,
    alerts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not wl:
        raise ValueError("La watchlist seleccionada no existe.")

    sym = (ticker or "").upper().strip()
    if not sym:
        raise ValueError("Debés indicar un ticker válido.")

    sanitized_alerts: list[dict[str, Any]] = []
    if isinstance(alerts, list):
        for r in alerts:
            if not isinstance(r, dict):
                continue
            metric = str(r.get("metric") or "").strip()
            op = str(r.get("op") or "<=").strip()
            val = r.get("value")
            if metric in METRIC_LABELS and op in ("<=", ">=") and isinstance(val, (int, float)):
                sanitized_alerts.append({
                    "metric": metric,
                    "op": op,
                    "value": float(val),
                })

    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.watchlist_id == watchlist_id, WatchlistItem.ticker == sym)
        .first()
    )

    buy_val = float(buy_target_price) if buy_target_price not in (None, "") else None
    sell_val = float(sell_target_price) if sell_target_price not in (None, "") else None
    note_val = (thesis_note or "").strip()

    # Si se editan objetivos o reglas de este ticker, limpiamos sus huellas previas para permitir re-disparo si aplica
    db.query(AlertNotification).filter(
        AlertNotification.watchlist_id == watchlist_id,
        AlertNotification.ticker == sym,
    ).delete()

    if existing:
        setattr(existing, "buy_target_price", buy_val)
        setattr(existing, "sell_target_price", sell_val)
        setattr(existing, "thesis_note", note_val)
        setattr(existing, "alerts", sanitized_alerts)
    else:
        max_pos = db.query(WatchlistItem).filter(WatchlistItem.watchlist_id == watchlist_id).count()
        item = WatchlistItem(
            watchlist_id=watchlist_id,
            ticker=sym,
            position=max_pos,
            buy_target_price=buy_val,
            sell_target_price=sell_val,
            thesis_note=note_val,
            alerts=sanitized_alerts,
        )
        db.add(item)

    db.commit()
    return get_all_watchlists_payload(db)


def remove_watchlist_item(db: Session, watchlist_id: int, ticker: str) -> dict[str, Any]:
    sym = (ticker or "").upper().strip()
    row = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.watchlist_id == watchlist_id, WatchlistItem.ticker == sym)
        .first()
    )
    if row:
        db.delete(row)
        db.commit()
    return get_all_watchlists_payload(db)


def mark_notifications_read(db: Session, notification_id: int | None = None) -> dict[str, Any]:
    q = db.query(AlertNotification).filter(AlertNotification.is_read.is_(False))
    if notification_id is not None:
        q = q.filter(AlertNotification.id == notification_id)
    for row in q.all():
        setattr(row, "is_read", True)
    db.commit()
    return get_all_watchlists_payload(db)


def clear_all_notifications(db: Session) -> dict[str, Any]:
    db.query(AlertNotification).delete()
    db.commit()
    return get_all_watchlists_payload(db)