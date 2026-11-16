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


def _discover_peer_tickers(ticker_upper: str, sector: str, industry: str) -> list[str]:
    if ticker_upper in CURATED_PEERS_BY_TICKER:
        return [t for t in CURATED_PEERS_BY_TICKER[ticker_upper] if t != ticker_upper][:5]

    ind_key = industry.strip().lower()
    if ind_key in CURATED_PEERS_BY_INDUSTRY:
        return [t for t in CURATED_PEERS_BY_INDUSTRY[ind_key] if t != ticker_upper][:5]

    # Respaldo dinámico mediante búsqueda pública de Yahoo Finance por industria/sector
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

    mcap_mm = round(price * shares_mm, 2) if (price > 0 and shares_mm > 0) else None
    ev_mm = round(mcap_mm + net_debt_mm, 2) if mcap_mm is not None else None

    rev_mm = ((info.get("totalRevenue") or 0) * fx_rate) / 1_000_000.0
    ebitda_mm = ((info.get("ebitda") or 0) * fx_rate) / 1_000_000.0
    net_inc_mm = ((info.get("netIncomeToCommon") or 0) * fx_rate) / 1_000_000.0
    fcf_mm = ((info.get("freeCashflow") or 0) * fx_rate) / 1_000_000.0

    def mult(num: float | None, den: float | None) -> float | None:
        if num is None or den is None or den == 0:
            return None
        v = num / den
        return round(v, 2) if abs(v) <= 500 else None

    pe_ltm = round(float(info["trailingPE"]), 2) if info.get("trailingPE") is not None else mult(mcap_mm, net_inc_mm)
    pe_ntm = round(float(info["forwardPE"]), 2) if info.get("forwardPE") is not None else None
    if pe_ntm is None and price > 0 and info.get("forwardEps"):
        f_eps = float(info["forwardEps"])
        if f_eps != 0:
            pe_ntm = round(price / f_eps, 2)

    pb_ltm = round(float(info["priceToBook"]), 2) if info.get("priceToBook") is not None else None
    ev_sales = mult(ev_mm, rev_mm)
    ev_ebitda = mult(ev_mm, ebitda_mm)
    p_fcf = mult(mcap_mm, fcf_mm)

    rev_g = info.get("revenueGrowth")
    rev_ntm = rev_mm * (1.0 + float(rev_g)) if (rev_mm > 0 and rev_g is not None) else None
    ev_sales_ntm = mult(ev_mm, rev_ntm)

    ebit_margin = round(float(info["operatingMargins"]) * 100.0, 1) if info.get("operatingMargins") is not None else None
    net_margin = round(float(info["profitMargins"]) * 100.0, 1) if info.get("profitMargins") is not None else None
    roe = round(float(info["returnOnEquity"]) * 100.0, 1) if info.get("returnOnEquity") is not None else None
    roic = None
    if rev_mm > 0 and ebit_margin is not None and mcap_mm and pb_ltm and pb_ltm > 0:
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

    peers_avg: dict[str, float | None] = {}
    peers_med: dict[str, float | None] = {}
    relative_premium_pct: dict[str, float | None] = {}

    for k in numeric_keys:
        vals = [float(r[k]) for r in peer_rows if r.get(k) is not None]
        if vals:
            avg_v = round(mean(vals), 2)
            med_v = round(median(vals), 2)
            peers_avg[k] = avg_v
            peers_med[k] = med_v

            base_v = base_row.get(k)
            if base_v is not None and med_v != 0:
                relative_premium_pct[k] = round(((float(base_v) - med_v) / abs(med_v)) * 100.0, 1)
            else:
                relative_premium_pct[k] = None
        else:
            peers_avg[k] = None
            peers_med[k] = None
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