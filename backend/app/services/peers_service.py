from statistics import mean, median
from typing import Any
from urllib.parse import quote
import requests
from sqlalchemy.orm import Session

from app.core.yf_client import (
    get_cached_market_snapshot,
    get_cached_estimates_and_guidance,
    _build_summary_metrics,
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
    "BMA": ["GGAL", "BBAR", "SUPV", "ITUB", "NU"],
    "GGAL": ["BMA", "BBAR", "SUPV", "ITUB", "NU"],
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

    mcap_mm = cap.get("market_cap_mm")
    ev_mm = cap.get("enterprise_value_mm")
    fcf_mm = gcf.get("fcf_ltm_mm")

    fcf_yield_pct: float | None = None
    if fcf_mm is not None and mcap_mm and mcap_mm > 0:
        fcf_yield_pct = round((float(fcf_mm) / float(mcap_mm)) * 100.0, 2)

    rev_mm = ((info.get("totalRevenue") or 0) * fx_rate) / 1_000_000.0 if info.get("totalRevenue") is not None else sec_fb.get("revenue_mm")
    rev_g = info.get("revenueGrowth")
    rev_ntm = float(rev_mm) * (1.0 + float(rev_g)) if (rev_mm and float(rev_mm) > 0 and rev_g is not None) else None
    ev_sales_ntm = _valuation_multiple(ev_mm, rev_ntm)

    consensus_summary = est.get("consensus_summary", {})
    rev_growth_pct = gcf.get("revenue_growth_yoy_pct")
    if rev_growth_pct is None:
        rev_growth_pct = consensus_summary.get("revenue_growth_yoy_pct")

    target_price = val.get("target_price")
    upside_ws_pct = round(((float(target_price) - price) / price) * 100.0, 1) if (target_price and price > 0) else None

    pe_ltm: float | str | None = val.get("pe_ltm")
    if pe_ltm is None and sec_fb.get("net_income_mm") is not None and float(sec_fb["net_income_mm"]) <= 0:
        pe_ltm = "N/M"

    p_fcf_ltm: float | str | None = val.get("p_to_fcf_ltm")
    if p_fcf_ltm is None and fcf_mm is not None and float(fcf_mm) <= 0:
        p_fcf_ltm = "N/M"

    raw_cls = est.get("classification")
    cls_info: dict[str, Any] = raw_cls if isinstance(raw_cls, dict) else {}
    sector_val = str(
        cls_info.get("sector")
        or info.get("sector")
        or sec_fb.get("sic_description")
        or ""
    ).strip()
    industry_val = str(
        cls_info.get("industry")
        or info.get("industry")
        or cls_info.get("sic_description")
        or sec_fb.get("sic_description")
        or ""
    ).strip()

    return {
        "ticker": ticker_upper,
        "name": info.get("shortName") or info.get("longName") or sec_fb.get("entity_name") or ticker_upper,
        "sector": sector_val,
        "industry": industry_val,
        "is_base": is_base,
        "price": round(price, 2),
        "market_cap_mm": mcap_mm,
        "enterprise_value_mm": ev_mm,
        "fcf_ltm_mm": fcf_mm,
        "fcf_yield_pct": fcf_yield_pct,
        "ev_sales_ltm": val.get("ev_to_sales_ltm"),
        "ev_sales_ntm": ev_sales_ntm,
        "ev_ebitda_ltm": val.get("ev_to_ebitda_ltm"),
        "pe_ltm": pe_ltm,
        "pe_ntm": val.get("pe_ntm"),
        "pb_ltm": val.get("pb_ltm"),
        "p_fcf_ltm": p_fcf_ltm,
        "ebit_margin_pct": eff.get("ebit_margin_pct"),
        "net_margin_pct": eff.get("net_margin_pct"),
        "roe_pct": eff.get("roe_pct"),
        "roic_pct": eff.get("roic_pct"),
        "rev_growth_yoy_pct": rev_growth_pct,
        "upside_ws_pct": upside_ws_pct,
    }


def _compute_group_stats(
    rows: list[dict[str, Any]], numeric_keys: list[str]
) -> tuple[dict[str, float | None], dict[str, float | None]]:
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
    raw_cls = est.get("classification")
    classification: dict[str, Any] = raw_cls if isinstance(raw_cls, dict) else {}
    sector = str(classification.get("sector") or "")
    industry = str(classification.get("industry") or "")
    sic_desc = str(classification.get("sic_description") or "")
    is_financial = any(
        k in f"{sector} {industry} {sic_desc}".lower()
        for k in ("financial", "bank", "depository", "insurance", "capital markets", "credit", "asset management")
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