from datetime import datetime, timedelta
import math
from typing import Any
import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from app.models.database import CompanyOwnershipCache
from app.core.yf_client import get_cached_market_snapshot

OWNERSHIP_CACHE_TTL = timedelta(hours=12)


def _clean_num(val: Any, decimals: int = 2) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, decimals)
    except (TypeError, ValueError):
        return None


def _clean_date_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    return s[:10] if len(s) >= 10 else s


def _normalize_major_holders(df: Any, info: dict[str, Any]) -> dict[str, Any]:
    insiders_pct = _clean_num((info.get("heldPercentInsiders") or 0) * 100.0, 2) if info.get("heldPercentInsiders") is not None else None
    institutions_pct = _clean_num((info.get("heldPercentInstitutions") or 0) * 100.0, 2) if info.get("heldPercentInstitutions") is not None else None
    inst_float_pct: float | None = None
    institutions_count: int | None = None

    if isinstance(df, pd.DataFrame) and not df.empty:
        # yfinance >= 0.2.36 devuelve índice con claves como 'insidersPercentHeld', 'institutionsPercentHeld', etc.
        if "Value" in df.columns:
            for idx, row in df.iterrows():
                key = str(idx).strip().lower()
                raw_v = row["Value"]
                num_v = _clean_num(raw_v, 4)
                if num_v is None:
                    continue
                if "insiderspercent" in key and insiders_pct is None:
                    insiders_pct = round(num_v * 100.0, 2) if num_v <= 1.0 else round(num_v, 2)
                elif "institutionspercent" in key and institutions_pct is None:
                    institutions_pct = round(num_v * 100.0, 2) if num_v <= 1.0 else round(num_v, 2)
                elif "institutionsfloat" in key:
                    inst_float_pct = round(num_v * 100.0, 2) if num_v <= 1.0 else round(num_v, 2)
                elif "institutionscount" in key:
                    institutions_count = int(num_v)
        elif df.shape[1] >= 2:
            for _, row in df.iterrows():
                raw_str = str(row.iloc[0]).replace("%", "").strip()
                desc = str(row.iloc[1]).lower()
                num_v = _clean_num(raw_str, 2)
                if num_v is None:
                    continue
                if "insider" in desc and insiders_pct is None:
                    insiders_pct = num_v
                elif "float" in desc and inst_float_pct is None:
                    inst_float_pct = num_v
                elif "institution" in desc and ("held" in desc or "shares" in desc) and institutions_pct is None:
                    institutions_pct = num_v
                elif "number of institutions" in desc or "institutions holding" in desc:
                    institutions_count = int(num_v)

    public_other_pct: float | None = None
    if insiders_pct is not None and institutions_pct is not None:
        rem = round(max(0.0, 100.0 - insiders_pct - institutions_pct), 2)
        public_other_pct = rem

    return {
        "insiders_pct": insiders_pct,
        "institutions_pct": institutions_pct,
        "institutions_float_pct": inst_float_pct,
        "institutions_count": institutions_count,
        "public_other_pct": public_other_pct,
    }


def _normalize_holders_table(df: Any, shares_out_raw: float, price: float, limit: int = 15) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []

    rows_out: list[dict[str, Any]] = []
    for _, row in df.head(limit).iterrows():
        holder = str(row.get("Holder") or row.get("holder") or "").strip()
        if not holder:
            continue

        shares = _clean_num(row.get("Shares") or row.get("shares"), 0)
        date_rep = _clean_date_str(row.get("Date Reported") or row.get("dateReported"))

        pct_out_raw = _clean_num(row.get("pctHeld") or row.get("% Out"), 4)
        pct_out: float | None = None
        if pct_out_raw is not None:
            pct_out = round(pct_out_raw * 100.0, 2) if abs(pct_out_raw) <= 1.0 else round(pct_out_raw, 2)
        elif shares is not None and shares_out_raw > 0:
            pct_out = round((shares / shares_out_raw) * 100.0, 2)

        val_raw = _clean_num(row.get("Value") or row.get("value"), 2)
        value_mm: float | None = None
        if val_raw is not None and val_raw > 0:
            value_mm = round(val_raw / 1_000_000.0, 2)
        elif shares is not None and price > 0:
            value_mm = round((shares * price) / 1_000_000.0, 2)

        pct_chg_raw = _clean_num(row.get("pctChange") or row.get("% Change"), 4)
        pct_change: float | None = None
        if pct_chg_raw is not None:
            pct_change = round(pct_chg_raw * 100.0, 2) if abs(pct_chg_raw) <= 5.0 else round(pct_chg_raw, 2)

        rows_out.append({
            "holder": holder,
            "date_reported": date_rep,
            "shares": int(shares) if shares is not None else None,
            "pct_out": pct_out,
            "value_mm": value_mm,
            "pct_change": pct_change,
        })

    return rows_out


def _classify_insider_tx(tx_text: str) -> str:
    low = tx_text.lower()
    if any(k in low for k in ["purchase", "buy", "open market acquisition", "acquis"]):
        return "buy"
    if any(k in low for k in ["sale", "sell", "disposition"]):
        return "sell"
    return "other"


def _normalize_insider_transactions(df: Any, limit: int = 30) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return [], {
            "total_transactions": 0,
            "buy_count": 0,
            "sell_count": 0,
            "other_count": 0,
            "buy_value_mm": 0.0,
            "sell_value_mm": 0.0,
            "net_value_mm": 0.0,
            "sentiment": "neutral",
        }

    txs: list[dict[str, Any]] = []
    buy_count = 0
    sell_count = 0
    other_count = 0
    buy_val_total = 0.0
    sell_val_total = 0.0

    for _, row in df.head(limit).iterrows():
        insider = str(row.get("Insider") or row.get("insider") or "").strip()
        if not insider:
            continue

        position = str(row.get("Position") or row.get("position") or "").strip()
        tx_desc = str(row.get("Transaction") or row.get("Text") or row.get("transaction") or "").strip()
        ownership_type = str(row.get("Ownership") or row.get("ownership") or "D").strip()
        start_date = _clean_date_str(row.get("Start Date") or row.get("startDate"))

        shares_val = _clean_num(row.get("Shares") or row.get("shares"), 0)
        value_raw = _clean_num(row.get("Value") or row.get("value"), 2)

        tx_kind = _classify_insider_tx(tx_desc)
        if tx_kind == "buy":
            buy_count += 1
            if value_raw and value_raw > 0:
                buy_val_total += value_raw
        elif tx_kind == "sell":
            sell_count += 1
            if value_raw and value_raw > 0:
                sell_val_total += value_raw
        else:
            other_count += 1

        txs.append({
            "date": start_date,
            "insider": insider,
            "position": position or "Directivo / Ejecutivo",
            "transaction": tx_desc or "Operación Form 4",
            "kind": tx_kind,  # buy | sell | other
            "ownership": ownership_type,
            "shares": int(abs(shares_val)) if shares_val is not None else None,
            "value_usd": round(abs(value_raw), 2) if value_raw is not None else None,
        })

    buy_mm = round(buy_val_total / 1_000_000.0, 2)
    sell_mm = round(sell_val_total / 1_000_000.0, 2)
    net_mm = round(buy_mm - sell_mm, 2)

    if buy_count > sell_count and net_mm > 0:
        sentiment = "bullish"
    elif sell_count > buy_count * 2 and sell_mm > 5.0:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    summary = {
        "total_transactions": len(txs),
        "buy_count": buy_count,
        "sell_count": sell_count,
        "other_count": other_count,
        "buy_value_mm": buy_mm,
        "sell_value_mm": sell_mm,
        "net_value_mm": net_mm,
        "sentiment": sentiment,
    }
    return txs, summary


def build_ownership_and_insiders_report(ticker_symbol: str, db: Session) -> dict[str, Any]:
    """
    Construye y cachea (TTL 12h) el reporte de Propiedad Institucional (13F),
    Fondos Mutuos y Operaciones de Insiders (Form 4) para el ticker indicado.
    """
    sym = ticker_symbol.upper().strip()
    now = datetime.utcnow()

    cached_row = (
        db.query(CompanyOwnershipCache)
        .filter(CompanyOwnershipCache.ticker == sym)
        .first()
    )
    if cached_row is not None:
        updated_at: Any = cached_row.last_updated
        payload_cached: Any = cached_row.ownership_data
        if isinstance(updated_at, datetime) and isinstance(payload_cached, dict):
            if (now - updated_at) < OWNERSHIP_CACHE_TTL:
                return payload_cached

    snapshot = get_cached_market_snapshot(sym, db)
    info: dict[str, Any] = snapshot.get("info", {})
    price = float(snapshot.get("price") or 0.0)
    shares_out_raw = float(info.get("sharesOutstanding") or 0.0)

    tk = yf.Ticker(sym)
    try:
        major_df = tk.major_holders
    except Exception:
        major_df = None

    try:
        inst_df = tk.institutional_holders
    except Exception:
        inst_df = None

    try:
        mf_df = tk.mutualfund_holders
    except Exception:
        mf_df = None

    try:
        insider_df = tk.insider_transactions
    except Exception:
        insider_df = None

    major_summary = _normalize_major_holders(major_df, info)
    institutional_holders = _normalize_holders_table(inst_df, shares_out_raw, price, limit=15)
    mutualfund_holders = _normalize_holders_table(mf_df, shares_out_raw, price, limit=10)
    insider_txs, insider_summary = _normalize_insider_transactions(insider_df, limit=30)

    report: dict[str, Any] = {
        "ticker": sym,
        "company_name": str(info.get("longName") or info.get("shortName") or sym),
        "current_price": round(price, 2),
        "shares_out_mm": round(shares_out_raw / 1_000_000.0, 2) if shares_out_raw > 0 else None,
        "as_of": now.strftime("%Y-%m-%d %H:%M UTC"),
        "major_holders": major_summary,
        "institutional_holders": institutional_holders,
        "mutualfund_holders": mutualfund_holders,
        "insider_transactions": insider_txs,
        "insider_summary": insider_summary,
    }

    if cached_row is not None:
        db.query(CompanyOwnershipCache).filter(
            CompanyOwnershipCache.ticker == sym
        ).update({
            "ownership_data": report,
            "last_updated": now,
        })
    else:
        db.add(
            CompanyOwnershipCache(
                ticker=sym,
                ownership_data=report,
                last_updated=now,
            )
        )

    db.commit()
    return report
