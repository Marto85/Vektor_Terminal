from statistics import mean, median
from typing import Any
from urllib.parse import quote
import requests
from sqlalchemy.orm import Session

from app.core.yf_client import (
    get_cached_market_snapshot,
    get_cached_estimates_and_guidance,
)

# Mapa curado de pares directos por industria / ticker para asegurar comparables institucionales
CURATED_PEERS_BY_TICKER: dict[str, list[str]] = {
    "MSFT": ["AAPL", "GOOGL", "AMZN", "ORCL", "CRM"],
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META", "QCOM"],
    "GOOGL": ["META", "MSFT", "AMZN", "NFLX", "SNAP"],
    "META": ["GOOGL", "SNAP", "PINS", "NFLX", "SPOT"],
    "AMZN": ["MSFT", "WMT", "MELI", "SHOP", "BABA"],
    "NVDA": ["AMD", "AVGO", "QCOM", "INTC", "TSM"],
    "AMD": ["NVDA", "INTC", "AVGO", "QCOM", "MRVL"],
    "JNJ": ["PFE", "MRK", "ABBV", "LLY", "BMY"],
    "PFE": ["JNJ", "MRK", "ABBV", "LLY", "BMY"],
    "KO": ["PEP", "MNST", "KDP", "MDLZ", "GIS"],
    "PEP": ["KO", "MNST", "KDP", "MDLZ", "KHC"],
    "JPM": ["BAC", "WFC", "C", "GS", "MS"],
    "BAC": ["JPM", "WFC", "C", "USB", "PNC"],
    "NU": ["STNE", "PAGS", "XP", "SOFI", "ITUB"],
    "STNE": ["PAGS", "NU", "MELI", "SQ", "PYPL"],
    "MELI": ["AMZN", "SE", "SHOP", "NU", "STNE"],
    "V": ["MA", "AXP", "PYPL", "SQ", "FIS"],
    "MA": ["V", "AXP", "PYPL", "SQ", "GPN"],
    "XOM": ["CVX", "COP", "SHEL", "BP", "SLB"],
    "CVX": ["XOM", "COP", "SHEL", "BP", "EOG"],
}

CURATED_PEERS_BY_INDUSTRY: dict[str, list[str]] = {
    "software - infrastructure": ["MSFT", "ORCL", "CRM", "ADBE", "NOW", "PANW"],
    "software - application": ["CRM", "ADBE", "NOW", "INTU", "WDAY", "SNOW"],
    "internet content & information": ["GOOGL", "META", "NFLX", "SNAP", "PINS", "SPOT"],
    "internet retail": ["AMZN", "MELI", "SHOP", "BABA", "JD", "SE"],
    "consumer electronics": ["AAPL", "SONY", "HPQ", "DELL", "LOGI"],
    "semiconductors": ["NVDA", "AMD", "AVGO", "QCOM", "INTC", "TXN"],
    "drug manufacturers - general": ["JNJ", "LLY", "MRK", "ABBV", "PFE", "BMY"],
    "beverages - non-alcoholic": ["KO", "PEP", "MNST", "KDP", "CELH"],
    "banks - diversified": ["JPM", "BAC", "WFC", "C", "GS", "MS"],
    "banks - regional": ["NU", "USB", "PNC", "TFC", "FITB", "SOFI"],
    "credit services": ["V", "MA", "AXP", "PYPL", "COF", "SOFI"],
    "oil & gas integrated": ["XOM", "CVX", "SHEL", "BP", "TTE", "PBR"],
}

MULTIPLE_KEYS = {
    "ev_sales_ltm",
    "ev_sales_ntm",
    "ev_ebitda_ltm",
    "pe_ltm",
    "pe_ntm",
    "pb_ltm",
    "p_fcf_ltm",
}

OUTLIER_MULTIPLE_CAP = 250.0


def _discover_peer_tickers(ticker_upper: str, sector: str, industry: str) -> list[str]:
    if ticker_upper in CURATED_PEERS_BY_TICKER:
        return [t for t in CURATED_PEERS_BY_TICKER[ticker_upper] if t != ticker_upper][:5]

    ind_key = industry.strip().lower()
    if ind_key in CURATED_PEERS_BY_INDUSTRY:
        return [t for t in CURATED_PEERS_BY_INDUSTRY[ind_key] if t != ticker_upper][:5]

    query = industry or sector
    if not query:
        return []

    url = (
        f"https://query2.finance.yahoo.com/v1/finance/search?q={quote(query)}&"
        + "quotesCount=12&newsCount=0"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    candidates: list[str] = []
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        quotes = resp.json().get("quotes", [])
        for item in quotes:
            sym = str(item.get("symbol") or "").upper()
            qtype = str(item.get("quoteType") or "").upper()
            if sym and qtype == "EQUITY" and "." not in sym and sym != ticker_upper:
                if sym not in candidates:
                    candidates.append(sym)
            if len(candidates) >= 5:
                break
    except Exception:
        pass

    return candidates[:5]


def _valuation_multiple(num: float | None, den: float | None) -> float | str | None:
    """
    Convención institucional para múltiplos de valoración:
    - Si falta numerador o denominador -> None ('-')
    - Si el denominador es <= 0 (pérdidas o FCF negativo) -> 'N/M' (Not Meaningful)
    - Si ambos son > 0 -> redondeo a 2 decimales
    """
    if num is None or den is None:
        return None
    if den <= 0:
        return "N/M"
    if num <= 0:
        return None
    return round(num / den, 2)


def _extract_comparable_row(ticker_upper: str, db: Session, is_base: bool = False) -> dict[str, Any] | None:
    try:
        snap = get_cached_market_snapshot(ticker_upper, db)
        est = get_cached_estimates_and_guidance(ticker_upper, db)
    except Exception:
        return None

    info: dict[str, Any] = snap.get("info", {})
    if not info:
        return None

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

    raw_trailing_pe = info.get("trailingPE")
    if raw_trailing_pe is not None:
        pe_ltm: float | str | None = round(float(raw_trailing_pe), 2) if float(raw_trailing_pe) > 0 else "N/M"
    else:
        pe_ltm = _valuation_multiple(mcap_mm, net_inc_mm)

    raw_fwd_pe = info.get("forwardPE")
    pe_ntm: float | str | None = None
    if raw_fwd_pe is not None:
        pe_ntm = round(float(raw_fwd_pe), 2) if float(raw_fwd_pe) > 0 else "N/M"
    elif price > 0 and info.get("forwardEps") is not None:
        f_eps = float(info["forwardEps"])
        pe_ntm = round(price / f_eps, 2) if f_eps > 0 else "N/M"

    raw_pb = info.get("priceToBook")
    pb_ltm: float | str | None = None
    if raw_pb is not None:
        pb_ltm = round(float(raw_pb), 2) if float(raw_pb) > 0 else "N/M"

    ev_sales = _valuation_multiple(ev_mm, rev_mm)
    ev_ebitda = _valuation_multiple(ev_mm, ebitda_mm)
    p_fcf = _valuation_multiple(mcap_mm, fcf_mm)

    fcf_yield_pct: float | None = None
    if fcf_mm is not None and mcap_mm and mcap_mm > 0:
        fcf_yield_pct = round((fcf_mm / mcap_mm) * 100.0, 2)

    rev_g = info.get("revenueGrowth")
    rev_ntm = rev_mm * (1.0 + float(rev_g)) if (rev_mm and rev_mm > 0 and rev_g is not None) else None
    ev_sales_ntm = _valuation_multiple(ev_mm, rev_ntm)

    ebit_margin = round(float(info["operatingMargins"]) * 100.0, 1) if info.get("operatingMargins") is not None else None
    net_margin = round(float(info["profitMargins"]) * 100.0, 1) if info.get("profitMargins") is not None else None
    roe = round(float(info["returnOnEquity"]) * 100.0, 1) if info.get("returnOnEquity") is not None else None
    roic = None
    if rev_mm and rev_mm > 0 and ebit_margin is not None and mcap_mm and isinstance(pb_ltm, float) and pb_ltm > 0:
        inv_cap = (mcap_mm / pb_ltm) + net_debt_mm
        if inv_cap > 0:
            roic = round(((rev_mm * (ebit_margin / 100.0)) / inv_cap) * 100.0, 1)

    consensus_summary = est.get("consensus_summary", {})
    rev_growth_pct = round(float(rev_g) * 100.0, 1) if rev_g is not None else consensus_summary.get("revenue_growth_yoy_pct")
    target_price = info.get("targetMeanPrice")
    upside_ws_pct = round(((float(target_price) - price) / price) * 100.0, 1) if (target_price and price > 0) else None

    return {
        "ticker": ticker_upper,
        "name": info.get("shortName") or info.get("longName") or ticker_upper,
        "is_base": is_base,
        "price": round(price, 2),
        "market_cap_mm": mcap_mm,
        "enterprise_value_mm": ev_mm,
        "fcf_ltm_mm": fcf_mm,
        "fcf_yield_pct": fcf_yield_pct,
        "ev_sales_ltm": ev_sales,
        "ev_sales_ntm": ev_sales_ntm,
        "ev_ebitda_ltm": ev_ebitda,
        "pe_ltm": pe_ltm,
        "pe_ntm": pe_ntm,
        "pb_ltm": pb_ltm,
        "p_fcf_ltm": p_fcf,
        "ebit_margin_pct": ebit_margin,
        "net_margin_pct": net_margin,
        "roe_pct": roe,
        "roic_pct": roic,
        "rev_growth_yoy_pct": rev_growth_pct,
        "upside_ws_pct": upside_ws_pct,
    }


def _compute_group_stats(
    rows: list[dict[str, Any]], numeric_keys: list[str]
) -> tuple[dict[str, float | None], dict[str, float | None]]:
    """
    Calcula Promedio y Mediana ignorando strings ('N/M') y None.
    En múltiplos de valoración, winsoriza/excluye outliers extremos (> 250x) del Promedio
    para evitar distorsiones por ciclos de inversión, manteniendo la Mediana intacta.
    """
    avg_out: dict[str, float | None] = {}
    med_out: dict[str, float | None] = {}

    for k in numeric_keys:
        vals = [
            float(r[k])
            for r in rows
            if isinstance(r.get(k), (int, float)) and not isinstance(r.get(k), bool)
        ]
        if not vals:
            avg_out[k] = None
            med_out[k] = None
            continue

        med_out[k] = round(median(vals), 2)

        if k in MULTIPLE_KEYS:
            filtered_for_avg = [v for v in vals if 0 < v <= OUTLIER_MULTIPLE_CAP]
            avg_out[k] = round(mean(filtered_for_avg), 2) if filtered_for_avg else round(mean(vals), 2)
        else:
            avg_out[k] = round(mean(vals), 2)

    return avg_out, med_out


def build_peers_comparison(ticker_symbol: str, db: Session) -> dict[str, Any]:
    ticker_upper = ticker_symbol.upper()
    est = get_cached_estimates_and_guidance(ticker_upper, db)
    classification = est.get("classification", {})
    sector = classification.get("sector", "")
    industry = classification.get("industry", "")
    is_financial = "financial" in sector.lower() or any(
        k in industry.lower() for k in ("bank", "insurance", "capital markets", "credit", "asset management")
    )

    base_row = _extract_comparable_row(ticker_upper, db, is_base=True)
    if base_row is None:
        raise ValueError(f"No se encontraron datos de mercado suficientes para {ticker_upper}")

    peer_tickers = _discover_peer_tickers(ticker_upper, sector, industry)
    peer_rows: list[dict[str, Any]] = []
    for p_tk in peer_tickers:
        row = _extract_comparable_row(p_tk, db, is_base=False)
        if row is not None:
            peer_rows.append(row)

    numeric_keys = [
        "market_cap_mm",
        "enterprise_value_mm",
        "fcf_ltm_mm",
        "fcf_yield_pct",
        "ev_sales_ltm",
        "ev_sales_ntm",
        "ev_ebitda_ltm",
        "pe_ltm",
        "pe_ntm",
        "pb_ltm",
        "p_fcf_ltm",
        "ebit_margin_pct",
        "net_margin_pct",
        "roe_pct",
        "roic_pct",
        "rev_growth_yoy_pct",
        "upside_ws_pct",
    ]

    peers_avg, peers_med = _compute_group_stats(peer_rows, numeric_keys)
    relative_premium_pct: dict[str, float | None] = {}

    for k in numeric_keys:
        med_v = peers_med.get(k)
        base_v = base_row.get(k)
        if isinstance(base_v, (int, float)) and med_v is not None and med_v != 0:
            relative_premium_pct[k] = round(((float(base_v) - med_v) / abs(med_v)) * 100.0, 1)
        else:
            relative_premium_pct[k] = None

    return {
        "ticker": ticker_upper,
        "sector": sector,
        "industry": industry,
        "is_financial": is_financial,
        "base": base_row,
        "peers": peer_rows,
        "peers_avg": peers_avg,
        "peers_med": peers_med,
        "relative_premium_pct": relative_premium_pct,
    }


def build_manual_comparison(tickers: list[str], db: Session) -> dict[str, Any]:
    cleaned: list[str] = []
    for raw in tickers:
        sym = raw.strip().upper()
        if sym and sym not in cleaned:
            cleaned.append(sym)
        if len(cleaned) >= 5:
            break

    if not cleaned:
        raise ValueError("Debes indicar al menos un ticker para comparar.")

    companies: list[dict[str, Any]] = []
    errors: list[str] = []

    for sym in cleaned:
        row = _extract_comparable_row(sym, db, is_base=False)
        if row is not None:
            est = get_cached_estimates_and_guidance(sym, db)
            cls_info = est.get("classification", {})
            row["sector"] = cls_info.get("sector", "")
            row["industry"] = cls_info.get("industry", "")
            companies.append(row)
        else:
            errors.append(sym)

    if not companies:
        raise ValueError(f"No se pudieron obtener datos para los tickers indicados: {', '.join(cleaned)}")

    numeric_keys = [
        "price",
        "market_cap_mm",
        "enterprise_value_mm",
        "fcf_ltm_mm",
        "fcf_yield_pct",
        "ev_sales_ltm",
        "ev_sales_ntm",
        "ev_ebitda_ltm",
        "pe_ltm",
        "pe_ntm",
        "pb_ltm",
        "p_fcf_ltm",
        "ebit_margin_pct",
        "net_margin_pct",
        "roe_pct",
        "roic_pct",
        "rev_growth_yoy_pct",
        "upside_ws_pct",
    ]

    group_avg, group_med = _compute_group_stats(companies, numeric_keys)

    return {
        "tickers": [c["ticker"] for c in companies],
        "companies": companies,
        "group_avg": group_avg,
        "group_med": group_med,
        "missing": errors,
    }