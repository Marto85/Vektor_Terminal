from typing import Any
from sqlalchemy.orm import Session

from app.models.database import CompanyMarketCache
from app.core.yf_client import get_cached_market_snapshot, CF_LTM_SCHEMA_VERSION

# Universo institucional curado (~68 emisores líderes globales y ADRs LatAm)
SCREENER_UNIVERSE: list[str] = [
    # Mega Cap Tech & Software
    "MSFT", "AAPL", "GOOGL", "META", "AMZN", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "NOW", "INTU",
    # Semiconductores & Hardware
    "AMD", "QCOM", "TXN", "INTC", "TSM", "ASML",
    # Consumo & Retail
    "WMT", "COST", "HD", "MCD", "NKE", "KO", "PEP", "PG", "PM",
    # Salud & Farma
    "LLY", "JNJ", "UNH", "ABBV", "MRK", "PFE", "TMO",
    # Financieras, Pagos & Fintech
    "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "AXP", "PYPL", "BLK",
    # Energía, Industriales & Materiales
    "XOM", "CVX", "COP", "CAT", "GE", "UNP", "LMT", "LIN",
    # Telecom & Media
    "NFLX", "DIS", "VZ", "T",
    # LatAm & Emergentes (ADRs / NYSE / NASDAQ)
    "MELI", "NU", "STNE", "PAGS", "XP", "ITUB", "PBR", "VALE", "YPF", "GGAL", "VIST", "BABA",
]


def _extract_screener_row(ticker_upper: str, snap: dict[str, Any]) -> dict[str, Any] | None:
    info: dict[str, Any] = snap.get("info") or {}
    if not info:
        return None

    sector = str(info.get("sector") or "Otros")
    industry = str(info.get("industry") or "")
    is_financial = "financial" in sector.lower() or any(
        k in industry.lower() for k in ("bank", "insurance", "capital markets", "credit", "asset management")
    )

    price = float(snap.get("price") or 0.0)
    shares_mm = float(snap.get("shares_mm") or 0.0)
    net_debt_mm = float(snap.get("net_debt_mm") or 0.0)
    fx_rate = float(snap.get("fx_rate") or 1.0)
    cf_ltm: dict[str, Any] = snap.get("cf_ltm") or {}

    mcap_mm = round(price * shares_mm, 2) if (price > 0 and shares_mm > 0) else None
    ev_mm = round(mcap_mm + net_debt_mm, 2) if mcap_mm is not None else None

    rev_mm = ((info.get("totalRevenue") or 0) * fx_rate) / 1_000_000.0 if info.get("totalRevenue") is not None else None
    ebitda_mm = ((info.get("ebitda") or 0) * fx_rate) / 1_000_000.0 if info.get("ebitda") is not None else None
    net_inc_mm = ((info.get("netIncomeToCommon") or 0) * fx_rate) / 1_000_000.0 if info.get("netIncomeToCommon") is not None else None

    fcf_mm: float | None = cf_ltm.get("fcf_ltm_mm")
    if fcf_mm is None and info.get("freeCashflow") is not None:
        fcf_mm = round((float(info["freeCashflow"]) * fx_rate) / 1_000_000.0, 2)

    pe_ltm: float | None = None
    raw_pe = info.get("trailingPE")
    if raw_pe is not None and float(raw_pe) > 0:
        pe_ltm = round(float(raw_pe), 2)
    elif mcap_mm and net_inc_mm and net_inc_mm > 0:
        pe_ltm = round(mcap_mm / net_inc_mm, 2)

    pe_ntm: float | None = None
    raw_fpe = info.get("forwardPE")
    if raw_fpe is not None and float(raw_fpe) > 0:
        pe_ntm = round(float(raw_fpe), 2)
    elif price > 0 and info.get("forwardEps") is not None and float(info["forwardEps"]) > 0:
        pe_ntm = round(price / float(info["forwardEps"]), 2)

    ev_ebitda_ltm: float | None = None
    if not is_financial and ev_mm and ev_mm > 0 and ebitda_mm and ebitda_mm > 0:
        ev_ebitda_ltm = round(ev_mm / ebitda_mm, 2)

    ev_sales_ltm: float | None = None
    if ev_mm and ev_mm > 0 and rev_mm and rev_mm > 0:
        ev_sales_ltm = round(ev_mm / rev_mm, 2)

    pb_ltm: float | None = None
    if info.get("priceToBook") is not None and float(info["priceToBook"]) > 0:
        pb_ltm = round(float(info["priceToBook"]), 2)

    p_fcf_ltm: float | None = None
    if not is_financial and mcap_mm and mcap_mm > 0 and fcf_mm and fcf_mm > 0:
        p_fcf_ltm = round(mcap_mm / fcf_mm, 2)

    fcf_yield_pct: float | None = None
    if not is_financial and fcf_mm is not None and mcap_mm and mcap_mm > 0:
        fcf_yield_pct = round((fcf_mm / mcap_mm) * 100.0, 2)

    ebit_margin_pct = round(float(info["operatingMargins"]) * 100.0, 1) if info.get("operatingMargins") is not None else None
    net_margin_pct = round(float(info["profitMargins"]) * 100.0, 1) if info.get("profitMargins") is not None else None
    roe_pct = round(float(info["returnOnEquity"]) * 100.0, 1) if info.get("returnOnEquity") is not None else None

    roic_pct: float | None = None
    if not is_financial and rev_mm and rev_mm > 0 and ebit_margin_pct is not None and mcap_mm and pb_ltm and pb_ltm > 0:
        inv_cap = (mcap_mm / pb_ltm) + net_debt_mm
        if inv_cap > 0:
            roic_pct = round(((rev_mm * (ebit_margin_pct / 100.0)) / inv_cap) * 100.0, 1)

    net_debt_to_ebitda: float | None = None
    if not is_financial and ebitda_mm and ebitda_mm > 0:
        net_debt_to_ebitda = round(net_debt_mm / ebitda_mm, 2)

    rev_growth_yoy_pct = round(float(info["revenueGrowth"]) * 100.0, 1) if info.get("revenueGrowth") is not None else None

    raw_dy = info.get("dividendYield")
    div_yield_pct: float | None = None
    if raw_dy is not None:
        val_dy = float(raw_dy)
        div_yield_pct = round(val_dy if val_dy > 1 else val_dy * 100.0, 2)

    target_price = info.get("targetMeanPrice")
    upside_ws_pct = round(((float(target_price) - price) / price) * 100.0, 1) if (target_price and price > 0) else None

    return {
        "ticker": ticker_upper,
        "name": info.get("shortName") or info.get("longName") or ticker_upper,
        "sector": sector,
        "industry": industry,
        "country": info.get("country") or "",
        "price": round(price, 2),
        "market_cap_mm": mcap_mm,
        "enterprise_value_mm": ev_mm,
        "fcf_ltm_mm": fcf_mm,
        "pe_ltm": pe_ltm,
        "pe_ntm": pe_ntm,
        "ev_ebitda_ltm": ev_ebitda_ltm,
        "ev_sales_ltm": ev_sales_ltm,
        "pb_ltm": pb_ltm,
        "p_fcf_ltm": p_fcf_ltm,
        "fcf_yield_pct": fcf_yield_pct,
        "ebit_margin_pct": ebit_margin_pct,
        "net_margin_pct": net_margin_pct,
        "roe_pct": roe_pct,
        "roic_pct": roic_pct,
        "net_debt_to_ebitda": net_debt_to_ebitda,
        "rev_growth_yoy_pct": rev_growth_yoy_pct,
        "dividend_yield_pct": div_yield_pct,
        "upside_ws_pct": upside_ws_pct,
    }


def get_screener_universe(db: Session, bootstrap_limit: int = 12) -> dict[str, Any]:
    """
    Devuelve todas las empresas cacheadas en SQLite listas para filtrar en el Screener.
    Actualiza automáticamente snapshots que usen versiones previas de `cf_ltm`.
    """
    cached_rows = db.query(CompanyMarketCache).all()
    cached_map: dict[str, dict[str, Any]] = {}
    for row in cached_rows:
        tk = str(row.ticker).upper()
        payload: Any = row.market_data
        if isinstance(payload, dict) and payload.get("info"):
            cf_block = payload.get("cf_ltm")
            if isinstance(cf_block, dict) and cf_block.get("schema_version") == CF_LTM_SCHEMA_VERSION:
                cached_map[tk] = payload
            else:
                try:
                    refreshed = get_cached_market_snapshot(tk, db)
                    if refreshed and refreshed.get("info"):
                        cached_map[tk] = refreshed
                except Exception:
                    cached_map[tk] = payload

    missing_from_universe = [t for t in SCREENER_UNIVERSE if t not in cached_map]

    if len(cached_map) < 10 and missing_from_universe:
        for sym in missing_from_universe[:bootstrap_limit]:
            try:
                snap = get_cached_market_snapshot(sym, db)
                if snap and snap.get("info"):
                    cached_map[sym] = snap
            except Exception:
                continue

    items: list[dict[str, Any]] = []
    sectors_set: set[str] = set()

    for tk, snap in sorted(cached_map.items()):
        extracted = _extract_screener_row(tk, snap)
        if extracted is not None:
            items.append(extracted)
            if extracted["sector"]:
                sectors_set.add(extracted["sector"])

    pending_count = len([t for t in SCREENER_UNIVERSE if t not in cached_map])

    return {
        "items": items,
        "total_cached": len(items),
        "universe_size": len(SCREENER_UNIVERSE),
        "pending_sync": pending_count,
        "sectors": sorted(sectors_set),
    }


def sync_screener_batch(db: Session, batch_size: int = 15) -> dict[str, Any]:
    """
    Sincroniza en SQLite el siguiente lote de `batch_size` empresas del universo curado
    que aún no están cacheadas.
    """
    cached_tickers = {
        str(r.ticker).upper()
        for r in db.query(CompanyMarketCache.ticker).all()
    }
    pending = [t for t in SCREENER_UNIVERSE if t not in cached_tickers]

    synced: list[str] = []
    for sym in pending[:batch_size]:
        try:
            snap = get_cached_market_snapshot(sym, db)
            if snap and snap.get("info"):
                synced.append(sym)
        except Exception:
            continue

    result = get_screener_universe(db, bootstrap_limit=0)
    result["synced_now"] = synced
    return result