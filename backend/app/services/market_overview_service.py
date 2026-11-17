from datetime import datetime, timedelta
from typing import Any
import yfinance as yf
from sqlalchemy.orm import Session

from app.services.screener_service import get_screener_universe

OVERVIEW_CACHE_TTL = timedelta(minutes=15)
_OVERVIEW_CACHE: dict[str, Any] = {
    "timestamp": None,
    "benchmarks": [],
    "news": [],
}

BENCHMARK_CONFIG: list[dict[str, str]] = [
    {
        "symbol": "SPY",
        "name": "S&P 500 ETF",
        "subtitle": "Large Cap EE. UU.",
        "unit": "US$",
    },
    {
        "symbol": "QQQ",
        "name": "Nasdaq 100 ETF",
        "subtitle": "Tecnología & Crecimiento",
        "unit": "US$",
    },
    {
        "symbol": "ARGT",
        "name": "MSCI Argentina ETF",
        "subtitle": "Renta Variable Argentina",
        "unit": "US$",
    },
    {
        "symbol": "^TNX",
        "name": "Tasa Tesoro 10Y",
        "subtitle": "Tasa Libre de Riesgo EE. UU.",
        "unit": "%",
    },
]

NEWS_SOURCES: list[tuple[str, str]] = [
    ("SPY", "Global"),
    ("QQQ", "Tech & IA"),
    ("ARGT", "LatAm"),
    ("MELI", "LatAm"),
]


def _fetch_benchmarks_and_news() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = datetime.utcnow()
    cached_ts = _OVERVIEW_CACHE.get("timestamp")
    if (
        isinstance(cached_ts, datetime)
        and (now - cached_ts) < OVERVIEW_CACHE_TTL
        and _OVERVIEW_CACHE.get("benchmarks")
    ):
        return _OVERVIEW_CACHE["benchmarks"], _OVERVIEW_CACHE["news"]

    benchmarks_out: list[dict[str, Any]] = []
    for cfg in BENCHMARK_CONFIG:
        sym = cfg["symbol"]
        try:
            tk = yf.Ticker(sym)
            hist = tk.history(period="1mo", interval="1d", auto_adjust=True)
            closes = [float(c) for c in hist["Close"].dropna().tolist()] if (hist is not None and not hist.empty) else []

            if len(closes) >= 2:
                last_price = closes[-1]
                prev_price = closes[-2]
            elif len(closes) == 1:
                last_price = closes[0]
                prev_price = closes[0]
            else:
                fi = tk.fast_info
                last_price = float(getattr(fi, "last_price", 0.0) or 0.0)
                prev_price = float(getattr(fi, "previous_close", last_price) or last_price)

            change = last_price - prev_price if prev_price > 0 else 0.0
            change_pct = (change / prev_price) * 100.0 if prev_price > 0 else 0.0

            benchmarks_out.append({
                "symbol": sym,
                "name": cfg["name"],
                "subtitle": cfg["subtitle"],
                "unit": cfg["unit"],
                "price": round(last_price, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "sparkline": [round(v, 2) for v in closes[-22:]],
            })
        except Exception:
            benchmarks_out.append({
                "symbol": sym,
                "name": cfg["name"],
                "subtitle": cfg["subtitle"],
                "unit": cfg["unit"],
                "price": 0.0,
                "change": 0.0,
                "change_pct": 0.0,
                "sparkline": [],
            })

    seen_titles: set[str] = set()
    news_out: list[dict[str, Any]] = []

    for sym, category in NEWS_SOURCES:
        try:
            raw_news = yf.Ticker(sym).news or []
            for item in raw_news[:4]:
                # Compatibilidad con estructura plana o anidada (`content`) de yfinance
                content = item.get("content") if isinstance(item.get("content"), dict) else item
                title = str(content.get("title") or item.get("title") or "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)

                provider_obj = content.get("provider")
                publisher = (
                    provider_obj.get("displayName")
                    if isinstance(provider_obj, dict)
                    else (content.get("publisher") or item.get("publisher") or "Mercado")
                )

                canon_url = content.get("canonicalUrl")
                link = (
                    canon_url.get("url")
                    if isinstance(canon_url, dict)
                    else (content.get("link") or item.get("link") or "")
                )

                pub_ts = item.get("providerPublishTime") or 0
                pub_date_str = str(content.get("pubDate") or "")

                news_out.append({
                    "title": title,
                    "publisher": str(publisher),
                    "link": str(link),
                    "category": category,
                    "related_ticker": sym,
                    "providerPublishTime": pub_ts,
                    "pubDate": pub_date_str,
                })
        except Exception:
            continue

    news_out.sort(key=lambda x: x.get("providerPublishTime") or 0, reverse=True)
    news_out = news_out[:12]

    _OVERVIEW_CACHE["timestamp"] = now
    _OVERVIEW_CACHE["benchmarks"] = benchmarks_out
    _OVERVIEW_CACHE["news"] = news_out

    return benchmarks_out, news_out


def build_market_overview(db: Session) -> dict[str, Any]:
    """
    Construye el payload del Portal Inicial:
    - 4 índices/referencias macro con sparkline de 30 días.
    - Radar de oportunidades extraído de la caché SQLite local (sin llamadas extra a YF).
    - Titulares de mercado categorizados (Global, Tech & IA, LatAm).
    """
    benchmarks, news = _fetch_benchmarks_and_news()
    universe = get_screener_universe(db, bootstrap_limit=8)
    items: list[dict[str, Any]] = universe.get("items") or []

    # Top por potencial vs consenso de Wall Street (excluyendo microcaps ilíquidas o extremos > 150%)
    upside_candidates = [
        it for it in items
        if isinstance(it.get("upside_ws_pct"), (int, float))
        and 0 < it["upside_ws_pct"] <= 150
        and (it.get("market_cap_mm") or 0) >= 5000
    ]
    top_upside = sorted(upside_candidates, key=lambda x: x["upside_ws_pct"], reverse=True)[:6]

    # Top por FCF Yield (excluyendo extremos > 35%)
    fcf_candidates = [
        it for it in items
        if isinstance(it.get("fcf_yield_pct"), (int, float))
        and 0 < it["fcf_yield_pct"] <= 35
        and (it.get("market_cap_mm") or 0) >= 5000
    ]
    top_fcf = sorted(fcf_candidates, key=lambda x: x["fcf_yield_pct"], reverse=True)[:6]

    def _compact_card(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "ticker": row["ticker"],
            "name": row["name"],
            "sector": row["sector"],
            "price": row["price"],
            "pe_ltm": row["pe_ltm"],
            "fcf_yield_pct": row["fcf_yield_pct"],
            "upside_ws_pct": row["upside_ws_pct"],
        }

    return {
        "benchmarks": benchmarks,
        "radar": {
            "top_upside": [_compact_card(r) for r in top_upside],
            "top_fcf_yield": [_compact_card(r) for r in top_fcf],
            "total_cached": universe.get("total_cached", 0),
        },
        "news": news,
    }