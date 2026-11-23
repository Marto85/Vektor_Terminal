from datetime import datetime, timedelta
from typing import Any
import yfinance as yf
from sqlalchemy.orm import Session

from app.core.yf_client import _fetch_google_news_rss, _translate_headline_es
from app.models.database import PriceHistoryCache
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


def _fallback_benchmark_from_db(db: Session, cfg: dict[str, str]) -> dict[str, Any] | None:
    """Recupera el último cierre guardado en PriceHistoryCache si Yahoo falla en frío."""
    sym = cfg["symbol"]
    row = (
        db.query(PriceHistoryCache)
        .filter(PriceHistoryCache.ticker == sym)
        .order_by(PriceHistoryCache.last_updated.desc())
        .first()
    )
    if row is None or not isinstance(row.payload, dict):
        return None
    series = row.payload.get("seriesByMetric", {}).get("Price", [])
    if not isinstance(series, list) or not series:
        return None
    closes = [float(p["close"]) for p in series if isinstance(p, dict) and p.get("close") is not None]
    if not closes:
        return None
    last_price = closes[-1]
    prev_price = closes[-2] if len(closes) >= 2 else last_price
    change = last_price - prev_price
    change_pct = (change / prev_price) * 100.0 if prev_price > 0 else 0.0
    return {
        "symbol": sym,
        "name": cfg["name"],
        "subtitle": cfg["subtitle"],
        "unit": cfg["unit"],
        "price": round(last_price, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "sparkline": [round(v, 2) for v in closes[-22:]],
    }


def _fetch_benchmarks_and_news(db: Session) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = datetime.utcnow()
    cached_ts = _OVERVIEW_CACHE.get("timestamp")
    prev_benchmarks: list[dict[str, Any]] = _OVERVIEW_CACHE.get("benchmarks") or []
    prev_news: list[dict[str, Any]] = _OVERVIEW_CACHE.get("news") or []

    if (
        isinstance(cached_ts, datetime)
        and (now - cached_ts) < OVERVIEW_CACHE_TTL
        and any(float(b.get("price") or 0) > 0 for b in prev_benchmarks)
    ):
        return prev_benchmarks, prev_news

    prev_by_sym = {b["symbol"]: b for b in prev_benchmarks if isinstance(b, dict) and float(b.get("price") or 0) > 0}

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

            if last_price <= 0:
                raise ValueError("Precio nulo desde YF")

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
            if sym in prev_by_sym:
                benchmarks_out.append(prev_by_sym[sym])
            else:
                db_fb = _fallback_benchmark_from_db(db, cfg)
                if db_fb:
                    benchmarks_out.append(db_fb)
                else:
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
                content = item.get("content") if isinstance(item.get("content"), dict) else item
                raw_title = str(content.get("title") or item.get("title") or "").strip()
                if not raw_title:
                    continue

                title_es = _translate_headline_es(raw_title)
                if title_es.lower() in seen_titles:
                    continue
                seen_titles.add(title_es.lower())

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

                pub_ts = int(item.get("providerPublishTime") or content.get("providerPublishTime") or 0)
                if pub_ts <= 0:
                    pub_iso = content.get("pubDate") or content.get("displayTime")
                    if isinstance(pub_iso, str) and pub_iso:
                        try:
                            pub_ts = int(datetime.fromisoformat(pub_iso.replace("Z", "+00:00")).timestamp())
                        except Exception:
                            pub_ts = int(now.timestamp())

                news_out.append({
                    "title": title_es,
                    "publisher": str(publisher),
                    "link": str(link),
                    "category": category,
                    "related_ticker": sym,
                    "providerPublishTime": pub_ts,
                    "pubDate": str(content.get("pubDate") or ""),
                })
        except Exception:
            continue

    # Respaldo de noticias en español vía Google News RSS si YF devolvió pocas en Render
    if len(news_out) < 4:
        rss_queries = [
            ("Wall Street S&P 500 bolsa", "Global"),
            ("Nasdaq acciones tecnologia inteligencia artificial", "Tech & IA"),
            ("acciones argentinas ADR Wall Street", "LatAm"),
        ]
        for query_str, cat_label in rss_queries:
            if len(news_out) >= 12:
                break
            for rn in _fetch_google_news_rss(query_str, "", limit=4):
                t_low = rn["title"].lower()
                if t_low in seen_titles:
                    continue
                seen_titles.add(t_low)
                news_out.append({
                    "title": rn["title"],
                    "publisher": rn["publisher"],
                    "link": rn["link"],
                    "category": cat_label,
                    "related_ticker": "SPY" if cat_label == "Global" else ("QQQ" if cat_label == "Tech & IA" else "ARGT"),
                    "providerPublishTime": rn["providerPublishTime"],
                    "pubDate": "",
                })

    if not news_out and prev_news:
        news_out = prev_news

    news_out.sort(key=lambda x: x.get("providerPublishTime") or 0, reverse=True)
    news_out = news_out[:12]

    if any(float(b.get("price") or 0) > 0 for b in benchmarks_out):
        _OVERVIEW_CACHE["timestamp"] = now
        _OVERVIEW_CACHE["benchmarks"] = benchmarks_out
    if news_out:
        _OVERVIEW_CACHE["news"] = news_out

    return benchmarks_out, news_out


def build_market_overview(db: Session) -> dict[str, Any]:
    """
    Construye el payload del Portal Inicial:
    - 4 índices/referencias macro con sparkline de 30 días.
    - Radar de oportunidades extraído de la caché local (sin llamadas extra a YF).
    - Titulares de mercado categorizados en español (Global, Tech & IA, LatAm).
    """
    benchmarks, news = _fetch_benchmarks_and_news(db)
    try:
        universe = get_screener_universe(db, bootstrap_limit=8)
    except Exception:
        db.rollback()
        universe = {"items": [], "total_cached": 0}
    items: list[dict[str, Any]] = universe.get("items") or []

    upside_candidates = [
        it for it in items
        if isinstance(it.get("upside_ws_pct"), (int, float))
        and 0 < it["upside_ws_pct"] <= 150
        and (it.get("market_cap_mm") or 0) >= 5000
    ]
    top_upside = sorted(upside_candidates, key=lambda x: x["upside_ws_pct"], reverse=True)[:6]

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