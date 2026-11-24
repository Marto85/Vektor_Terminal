from concurrent.futures import ThreadPoolExecutor
from typing import Any
from sqlalchemy.orm import Session

from app.models.database import CompanyMarketCache, SessionLocal
from app.core.yf_client import (
    get_cached_market_snapshot,
    _build_summary_metrics,
    CF_LTM_SCHEMA_VERSION,
)

# Universo institucional curado (~150 emisores líderes globales y ADRs LatAm)
SCREENER_UNIVERSE: list[str] = [
    # Mega Cap Tech, IA Frontier, Software & Ciberseguridad (28)
    "MSFT", "AAPL", "GOOGL", "META", "AMZN", "NVDA", "AVGO", "ORCL", "CRM", "ADBE",
    "NOW", "INTU", "ANT", "PLTR", "PANW", "CRWD", "ZS", "FTNT", "DDOG", "NET",
    "SNOW", "MDB", "WDAY", "TEAM", "HUBS", "APP", "SHOP", "GLOB",
    # Semiconductores, Equipos & Infraestructura IA (17)
    "AMD", "QCOM", "TXN", "INTC", "TSM", "ASML", "MU", "AMAT", "LRCX", "KLAC",
    "ARM", "SNPS", "CDNS", "MRVL", "ANET", "VRT", "SMCI",
    # Consumo, Retail, Lujo & Plataformas (24)
    "TSLA", "WMT", "COST", "HD", "LOW", "TGT", "MCD", "SBUX", "CMG", "NKE",
    "LULU", "RACE", "KO", "PEP", "PG", "PM", "UBER", "DASH", "ABNB", "BKNG",
    "MAR", "HLT", "SPOT", "RBLX",
    # Salud, Farma & Dispositivos Médicos (12)
    "LLY", "JNJ", "UNH", "ABBV", "MRK", "PFE", "TMO", "ISRG", "VRTX", "REGN",
    "AMGN", "SYK",
    # Financieras, Mercados, Pagos & Fintech (16)
    "BRK-B", "JPM", "BAC", "WFC", "GS", "MS", "SCHW", "BLK", "SPGI", "ICE",
    "V", "MA", "AXP", "PYPL", "COIN", "NU",
    # Energía, Nuclear, Utilities, Industriales & Materiales (22)
    "XOM", "CVX", "COP", "OXY", "SLB", "CEG", "VST", "GEV", "OKLO", "SMR",
    "CCJ", "CAT", "DE", "GE", "UNP", "LMT", "RTX", "BA", "LIN", "FCX",
    "SCCO", "MP",
    # Espacio, Satélites & Computación Cuántica (5)
    "RKLB", "ASTS", "IRDM", "IONQ", "RGTI",
    # Telecom & Media (4)
    "NFLX", "DIS", "VZ", "T",
    # Argentina ADRs (NYSE / NASDAQ) (15)
    "MELI", "YPF", "VIST", "GGAL", "BMA", "BBAR", "SUPV", "PAM", "TGS", "CEPU",
    "EDN", "IRS", "CRESY", "LOMA", "TEO",
    # LatAm & Emergentes (7)
    "STNE", "PAGS", "XP", "ITUB", "PBR", "VALE", "BABA",
]


def _fetch_snapshot_isolated(ticker_sym: str) -> tuple[str, dict[str, Any] | None]:
    """Ejecuta `get_cached_market_snapshot` con sesión SQLAlchemy aislada por hilo."""
    local_db = SessionLocal()
    try:
        snap = get_cached_market_snapshot(ticker_sym, local_db)
        if snap and float(snap.get("price") or 0) > 0:
            return ticker_sym, snap
        return ticker_sym, None
    except Exception:
        local_db.rollback()
        return ticker_sym, None
    finally:
        local_db.close()


def _infer_sector_from_sic_desc(sic_desc: str) -> str:
    low = (sic_desc or "").lower()
    if not low:
        return "Otros"
    if any(k in low for k in ("software", "computer", "semiconductor", "electronic", "data processing", "communications")):
        return "Technology"
    if any(k in low for k in ("bank", "depository", "credit", "finance", "insurance", "investment", "security brokers")):
        return "Financial Services"
    if any(k in low for k in ("pharmaceutical", "biological", "medical", "surgical", "hospital", "health")):
        return "Healthcare"
    if any(k in low for k in ("retail", "catalog", "apparel", "restaurant", "eating", "hotel", "motor vehicles")):
        return "Consumer Cyclical"
    if any(k in low for k in ("beverage", "food", "soap", "tobacco", "grocery")):
        return "Consumer Defensive"
    if any(k in low for k in ("petroleum", "oil", "gas", "coal", "energy")):
        return "Energy"
    if any(k in low for k in ("electric", "water", "natural gas distribution", "utility")):
        return "Utilities"
    if any(k in low for k in ("aircraft", "machinery", "railroad", "construction", "industrial", "aerospace")):
        return "Industrials"
    if any(k in low for k in ("chemical", "metal", "mining", "steel", "paper")):
        return "Basic Materials"
    if any(k in low for k in ("real estate", "reit")):
        return "Real Estate"
    return "Otros"


def _extract_screener_row(ticker_upper: str, snap: dict[str, Any]) -> dict[str, Any] | None:
    raw_info = snap.get("info")
    info: dict[str, Any] = raw_info if isinstance(raw_info, dict) else {}
    raw_sec_fb = snap.get("sec_fundamentals")
    sec_fb: dict[str, Any] = raw_sec_fb if isinstance(raw_sec_fb, dict) else {}

    price = float(snap.get("price") or 0.0)
    if price <= 0.0 and not info and not sec_fb:
        return None

    fx_rate = float(snap.get("fx_rate") or 1.0)
    summary = _build_summary_metrics(
        info=info,
        price=price,
        fx_rate=fx_rate,
        cf_ltm=snap.get("cf_ltm"),
        sec_fundamentals=sec_fb,
        market_1y_fallback=snap.get("market_1y_fallback"),
    )

    cap = summary.get("capital_structure", {})
    eff = summary.get("efficiency", {})
    gcf = summary.get("growth_cashflow", {})
    val = summary.get("valuation", {})

    sic_desc = str(sec_fb.get("sic_description") or "").strip()
    sector = str(info.get("sector") or _infer_sector_from_sic_desc(sic_desc) or "Otros")
    industry = str(info.get("industry") or sic_desc or "")
    is_financial = "financial" in sector.lower() or any(
        k in industry.lower() for k in ("bank", "depository", "insurance", "capital markets", "credit", "asset management")
    )

    mcap_mm = cap.get("market_cap_mm")
    ev_mm = cap.get("enterprise_value_mm")
    fcf_mm = gcf.get("fcf_ltm_mm")

    fcf_yield_pct: float | None = None
    if not is_financial and fcf_mm is not None and mcap_mm and mcap_mm > 0:
        fcf_yield_pct = round((float(fcf_mm) / float(mcap_mm)) * 100.0, 2)

    target_price = val.get("target_price")
    upside_ws_pct = round(((float(target_price) - price) / price) * 100.0, 1) if (target_price and price > 0) else None

    return {
        "ticker": ticker_upper,
        "name": info.get("shortName") or info.get("longName") or sec_fb.get("entity_name") or ticker_upper,
        "sector": sector,
        "industry": industry,
        "country": info.get("country") or "",
        "price": round(price, 2),
        "market_cap_mm": mcap_mm,
        "enterprise_value_mm": ev_mm,
        "fcf_ltm_mm": fcf_mm,
        "pe_ltm": val.get("pe_ltm"),
        "pe_ntm": val.get("pe_ntm"),
        "ev_ebitda_ltm": None if is_financial else val.get("ev_to_ebitda_ltm"),
        "ev_sales_ltm": val.get("ev_to_sales_ltm"),
        "pb_ltm": val.get("pb_ltm"),
        "p_fcf_ltm": None if is_financial else val.get("p_to_fcf_ltm"),
        "fcf_yield_pct": fcf_yield_pct,
        "ebit_margin_pct": eff.get("ebit_margin_pct"),
        "net_margin_pct": eff.get("net_margin_pct"),
        "roe_pct": eff.get("roe_pct"),
        "roic_pct": None if is_financial else eff.get("roic_pct"),
        "net_debt_to_ebitda": None if is_financial else cap.get("net_debt_to_ebitda"),
        "rev_growth_yoy_pct": gcf.get("revenue_growth_yoy_pct"),
        "dividend_yield_pct": val.get("dividend_yield_pct"),
        "upside_ws_pct": upside_ws_pct,
    }


def get_screener_universe(db: Session, bootstrap_limit: int = 4) -> dict[str, Any]:
    """
    Devuelve de inmediato todas las empresas cacheadas en Neon/SQLite sin bloquear
    en refrescos masivos de red. El refresco de esquemas/nuevos emisores se realiza
    vía `POST /screener/sync`.
    """
    cached_rows = db.query(CompanyMarketCache).all()
    cached_map: dict[str, dict[str, Any]] = {}

    for row in cached_rows:
        tk = str(row.ticker).upper()
        payload: Any = row.market_data
        if isinstance(payload, dict) and float(payload.get("price") or 0) > 0:
            cached_map[tk] = payload

    missing_from_universe = [t for t in SCREENER_UNIVERSE if t not in cached_map]

    # Solo hacer bootstrap si la base está completamente vacía
    if len(cached_map) == 0 and missing_from_universe and bootstrap_limit > 0:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for sym, snap in pool.map(_fetch_snapshot_isolated, missing_from_universe[:bootstrap_limit]):
                if snap is not None:
                    cached_map[sym] = snap

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


def sync_screener_batch(db: Session, batch_size: int = 10) -> dict[str, Any]:
    """
    Sincroniza en paralelo el siguiente lote de empresas faltantes o con esquema anterior.
    """
    cached_rows = db.query(CompanyMarketCache).all()
    up_to_date_tickers: set[str] = set()
    stale_tickers: list[str] = []

    for r in cached_rows:
        tk = str(r.ticker).upper()
        payload: Any = r.market_data
        if isinstance(payload, dict) and float(payload.get("price") or 0) > 0:
            cf_block = payload.get("cf_ltm")
            if isinstance(cf_block, dict) and cf_block.get("schema_version") == CF_LTM_SCHEMA_VERSION:
                up_to_date_tickers.add(tk)
            else:
                stale_tickers.append(tk)

    pending_new = [t for t in SCREENER_UNIVERSE if t not in up_to_date_tickers and t not in stale_tickers]
    targets = (pending_new + stale_tickers)[:batch_size]

    synced: list[str] = []
    if targets:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for sym, snap in pool.map(_fetch_snapshot_isolated, targets):
                if snap is not None:
                    synced.append(sym)

    result = get_screener_universe(db, bootstrap_limit=0)
    result["synced_now"] = synced
    return result