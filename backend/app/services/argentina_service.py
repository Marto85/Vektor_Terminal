from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import re
import threading
from typing import Any
import xml.etree.ElementTree as ET

import pandas as pd
import requests
import yfinance as yf

_OVERVIEW_TTL = timedelta(minutes=10)
_SERIES_TTL = timedelta(minutes=20)
_LOCK = threading.Lock()
_OVERVIEW_CACHE: dict[str, Any] = {"ts": None, "payload": None}
_SERIES_CACHE: dict[tuple[str, str], tuple[datetime, dict[str, Any]]] = {}

_HEADERS = {"User-Agent": "VektorTerminal/1.0 (+https://vektorterminal.local)"}

SOVEREIGN_BONDS: list[dict[str, Any]] = [
    {"ticker": "GD29", "name": "Bonar Global 2029", "law": "Ley NY", "maturity": "2029-07-09", "coupon_pct": 1.00},
    {"ticker": "GD30", "name": "Bonar Global 2030", "law": "Ley NY", "maturity": "2030-07-09", "coupon_pct": 0.75},
    {"ticker": "GD35", "name": "Bonar Global 2035", "law": "Ley NY", "maturity": "2035-07-09", "coupon_pct": 4.125},
    {"ticker": "GD38", "name": "Bonar Global 2038", "law": "Ley NY", "maturity": "2038-01-09", "coupon_pct": 5.00},
    {"ticker": "GD41", "name": "Bonar Global 2041", "law": "Ley NY", "maturity": "2041-07-09", "coupon_pct": 3.50},
    {"ticker": "GD46", "name": "Bonar Global 2046", "law": "Ley NY", "maturity": "2046-07-09", "coupon_pct": 4.125},
    {"ticker": "AL29", "name": "Bonar 2029", "law": "Ley Local", "maturity": "2029-07-09", "coupon_pct": 1.00},
    {"ticker": "AL30", "name": "Bonar 2030", "law": "Ley Local", "maturity": "2030-07-09", "coupon_pct": 0.75},
    {"ticker": "AL35", "name": "Bonar 2035", "law": "Ley Local", "maturity": "2035-07-09", "coupon_pct": 4.125},
    {"ticker": "AL41", "name": "Bonar 2041", "law": "Ley Local", "maturity": "2041-07-09", "coupon_pct": 3.50},
]

ARG_NEWS_FEEDS: list[dict[str, str]] = [
    {"source": "Infobae", "topic": "Economía", "url": "https://www.infobae.com/arc/outboundfeeds/rss/category/economia/"},
    {"source": "Infobae", "topic": "Política", "url": "https://www.infobae.com/arc/outboundfeeds/rss/category/politica/"},
    {"source": "Clarín", "topic": "Economía", "url": "https://www.clarin.com/rss/economia/"},
    {"source": "Clarín", "topic": "Política", "url": "https://www.clarin.com/rss/politica/"},
    {"source": "La Nación", "topic": "Economía", "url": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/category/economia/"},
    {"source": "La Nación", "topic": "Política", "url": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/category/politica/"},
    {"source": "Ámbito Financiero", "topic": "Economía", "url": "https://www.ambito.com/rss/pages/economia.xml"},
    {"source": "Ámbito Financiero", "topic": "Política", "url": "https://www.ambito.com/rss/pages/politica.xml"},
    {"source": "El Cronista", "topic": "Economía", "url": "https://www.cronista.com/files/rss/economia.xml"},
    {"source": "El Cronista", "topic": "Economía", "url": "https://www.cronista.com/files/rss/finanzas-mercados.xml"},
    {"source": "Página/12", "topic": "Economía", "url": "https://www.pagina12.com.ar/rss/secciones/economia/notas"},
    {"source": "Página/12", "topic": "Política", "url": "https://www.pagina12.com.ar/rss/secciones/el-pais/notas"},
    {"source": "C5N", "topic": "Economía", "url": "https://www.c5n.com/rss/economia.xml"},
    {"source": "C5N", "topic": "Política", "url": "https://www.c5n.com/rss/politica.xml"},
]

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def _strip_html(raw: str | None, max_len: int = 210) -> str:
    if not raw:
        return ""
    cleaned = html.unescape(_HTML_TAG_RE.sub(" ", raw))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_len:
        return cleaned[: max_len - 1].rstrip() + "…"
    return cleaned


def _fetch_json(url: str, timeout: int = 8) -> Any:
    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _fetch_dolares_snapshot() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    try:
        rows = _fetch_json("https://dolarapi.com/v1/dolares", timeout=7)
        if isinstance(rows, list):
            for item in rows:
                casa = str(item.get("casa") or "").strip().lower()
                if casa in ("mayorista", "oficial", "bolsa", "contadoconliqui"):
                    compra = float(item.get("compra") or 0.0)
                    venta = float(item.get("venta") or 0.0)
                    avg = round((compra + venta) / 2.0, 2) if (compra > 0 and venta > 0) else (venta or compra)
                    out[casa] = {
                        "compra": round(compra, 2) if compra > 0 else None,
                        "venta": round(venta, 2) if venta > 0 else None,
                        "promedio": round(avg, 2) if avg > 0 else None,
                        "fecha_actualizacion": item.get("fechaActualizacion"),
                    }
    except Exception:
        pass
    return out


def _fetch_riesgo_pais_snapshot() -> dict[str, Any]:
    try:
        data = _fetch_json("https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais", timeout=8)
        if isinstance(data, list) and data:
            valid = [d for d in data if d.get("valor") is not None and d.get("fecha")]
            if valid:
                latest = valid[-1]
                prev = valid[-2] if len(valid) >= 2 else latest
                val_curr = float(latest["valor"])
                val_prev = float(prev["valor"])
                return {
                    "valor": round(val_curr, 0),
                    "change_pb": round(val_curr - val_prev, 0),
                    "fecha": latest.get("fecha"),
                }
    except Exception:
        pass
    try:
        ultimo = _fetch_json("https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo", timeout=6)
        if isinstance(ultimo, dict) and ultimo.get("valor") is not None:
            return {
                "valor": round(float(ultimo["valor"]), 0),
                "change_pb": 0.0,
                "fecha": ultimo.get("fecha"),
            }
    except Exception:
        pass
    return {"valor": None, "change_pb": None, "fecha": None}


def _fetch_merval_usd(ccl_rate: float | None) -> dict[str, Any]:
    if not ccl_rate or ccl_rate <= 0:
        return {"value_usd": None, "change_pct": None, "value_ars": None}
    try:
        hist = yf.Ticker("^MERV").history(period="5d", interval="1d")
        if hist is not None and not hist.empty and "Close" in hist.columns:
            closes = [float(v) for v in hist["Close"].dropna().tolist() if float(v) > 0]
            if closes:
                last_ars = closes[-1]
                prev_ars = closes[-2] if len(closes) >= 2 else last_ars
                last_usd = round(last_ars / ccl_rate, 2)
                chg_pct = round(((last_ars - prev_ars) / prev_ars) * 100.0, 2) if prev_ars > 0 else 0.0
                return {
                    "value_usd": last_usd,
                    "change_pct": chg_pct,
                    "value_ars": round(last_ars, 2),
                }
    except Exception:
        pass
    return {"value_usd": None, "change_pct": None, "value_ars": None}


def _normalize_bond_price_100vn(raw_val: float) -> float:
    # En BYMA/Yahoo algunos bonos cotizan por 1 VN (ej. 0.68 USD) y otros por 100 VN (68.00 USD)
    if 0.0 < raw_val < 3.0:
        return round(raw_val * 100.0, 2)
    return round(raw_val, 2)


def _fetch_single_sovereign_bond(bond_cfg: dict[str, Any], mep_rate: float | None) -> dict[str, Any]:
    sym = bond_cfg["ticker"]
    price_usd: float | None = None
    change_pct: float | None = None
    source_used = "BYMA/Yahoo"

    for suffix, needs_fx in ((f"{sym}D.BA", False), (f"{sym}.BA", True)):
        if needs_fx and (not mep_rate or mep_rate <= 0):
            continue
        try:
            hist = yf.Ticker(suffix).history(period="5d", interval="1d")
            if hist is not None and not hist.empty and "Close" in hist.columns:
                closes = [float(v) for v in hist["Close"].dropna().tolist() if float(v) > 0]
                if closes:
                    last_raw = closes[-1]
                    prev_raw = closes[-2] if len(closes) >= 2 else last_raw
                    if needs_fx and mep_rate:
                        price_usd = _normalize_bond_price_100vn(last_raw / mep_rate)
                        prev_usd = _normalize_bond_price_100vn(prev_raw / mep_rate)
                    else:
                        price_usd = _normalize_bond_price_100vn(last_raw)
                        prev_usd = _normalize_bond_price_100vn(prev_raw)
                    change_pct = round(((price_usd - prev_usd) / prev_usd) * 100.0, 2) if prev_usd > 0 else 0.0
                    source_used = f"Yahoo ({suffix})"
                    break
        except Exception:
            continue

    return {
        "ticker": sym,
        "series_id": f"bond_{sym}",
        "name": bond_cfg["name"],
        "law": bond_cfg["law"],
        "maturity": bond_cfg["maturity"],
        "coupon_pct": bond_cfg["coupon_pct"],
        "price_usd": price_usd,
        "parity_pct": price_usd,
        "change_pct": change_pct,
        "source": source_used,
    }


def _extract_image_from_rss_item(item: ET.Element, desc_raw: str) -> str | None:
    for child in item:
        tag_l = child.tag.lower()
        if tag_l.endswith("content") or tag_l.endswith("thumbnail") or tag_l == "enclosure":
            url_attr = child.attrib.get("url") or child.attrib.get("href")
            if url_attr and url_attr.startswith(("http://", "https://")):
                return url_attr
    m = _IMG_SRC_RE.search(desc_raw or "")
    if m:
        src = m.group(1).strip()
        if src.startswith(("http://", "https://")):
            return src
    return None


def _parse_rss_date(pub_raw: str | None) -> tuple[str, float]:
    if not pub_raw:
        return "", 0.0
    try:
        dt = parsedate_to_datetime(pub_raw.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(), dt.timestamp()
    except Exception:
        return "", 0.0


def _fetch_single_rss_feed(cfg: dict[str, str]) -> list[dict[str, Any]]:
    items_out: list[dict[str, Any]] = []
    try:
        resp = requests.get(cfg["url"], headers=_HEADERS, timeout=6)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for item in root.findall(".//item")[:8]:
            title = _strip_html(item.findtext("title"), max_len=160)
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            desc_raw = item.findtext("description") or ""
            encoded_raw = ""
            for child in item:
                if child.tag.lower().endswith("encoded") and child.text:
                    encoded_raw = child.text
                    break
            bajada = _strip_html(desc_raw or encoded_raw, max_len=210)
            image_url = _extract_image_from_rss_item(item, f"{desc_raw} {encoded_raw}")
            pub_iso, pub_ts = _parse_rss_date(item.findtext("pubDate"))
            items_out.append(
                {
                    "title": title,
                    "subtitle": bajada,
                    "link": link,
                    "image_url": image_url,
                    "source": cfg["source"],
                    "topic": cfg["topic"],
                    "published_at": pub_iso,
                    "_ts": pub_ts,
                }
            )
    except Exception:
        return []
    return items_out


def _fetch_argentina_news() -> list[dict[str, Any]]:
    raw_items: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for res in pool.map(_fetch_single_rss_feed, ARG_NEWS_FEEDS):
            raw_items.extend(res)

    seen_titles: set[str] = set()
    deduped: list[dict[str, Any]] = []
    raw_items.sort(key=lambda x: x.get("_ts", 0.0), reverse=True)
    for it in raw_items:
        norm_t = re.sub(r"\W+", "", it["title"].lower())[:60]
        if not norm_t or norm_t in seen_titles:
            continue
        seen_titles.add(norm_t)
        it.pop("_ts", None)
        deduped.append(it)
        if len(deduped) >= 42:
            break
    return deduped


def build_argentina_overview() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    with _LOCK:
        ts = _OVERVIEW_CACHE.get("ts")
        payload = _OVERVIEW_CACHE.get("payload")
        if ts and payload and (now - ts) < _OVERVIEW_TTL:
            return payload

    with ThreadPoolExecutor(max_workers=4) as pool:
        f_fx = pool.submit(_fetch_dolares_snapshot)
        f_rp = pool.submit(_fetch_riesgo_pais_snapshot)
        f_news = pool.submit(_fetch_argentina_news)

        dolares = f_fx.result()
        riesgo = f_rp.result()
        news = f_news.result()

    mayorista = (dolares.get("mayorista") or {}).get("venta")
    oficial = (dolares.get("oficial") or {}).get("venta")
    mep = (dolares.get("bolsa") or {}).get("promedio") or (dolares.get("bolsa") or {}).get("venta")
    ccl = (dolares.get("contadoconliqui") or {}).get("venta") or (dolares.get("contadoconliqui") or {}).get("promedio")

    brecha_mep_pct = round(((mep - mayorista) / mayorista) * 100.0, 2) if (mep and mayorista and mayorista > 0) else None
    brecha_ccl_pct = round(((ccl - mayorista) / mayorista) * 100.0, 2) if (ccl and mayorista and mayorista > 0) else None
    canje_pct = round(((ccl - mep) / mep) * 100.0, 2) if (ccl and mep and mep > 0) else None

    merval = _fetch_merval_usd(ccl)

    with ThreadPoolExecutor(max_workers=6) as pool:
        bonds = list(pool.map(lambda cfg: _fetch_single_sovereign_bond(cfg, mep), SOVEREIGN_BONDS))

    out = {
        "updated_at": now.isoformat(),
        "cards": {
            "mayorista": {
                "series_id": "fx_mayorista",
                "label": "Dólar Mayorista (A3500)",
                "value": mayorista,
                "unit": "ARS",
                "subtitle": "Referencia oficial comercio exterior",
            },
            "oficial": {
                "series_id": "fx_oficial",
                "label": "Dólar Oficial Minorista",
                "value": oficial,
                "unit": "ARS",
                "subtitle": "BNA / Bancos minoristas",
            },
            "mep": {
                "series_id": "fx_mep",
                "label": "Dólar MEP (Promedio)",
                "value": mep,
                "unit": "ARS",
                "brecha_pct": brecha_mep_pct,
                "subtitle": f"Brecha {brecha_mep_pct:+.1f}% vs. Mayorista" if brecha_mep_pct is not None else "Dólar Bolsa",
            },
            "ccl": {
                "series_id": "fx_ccl",
                "label": "Dólar CCL",
                "value": ccl,
                "unit": "ARS",
                "brecha_pct": brecha_ccl_pct,
                "canje_pct": canje_pct,
                "subtitle": (
                    f"Brecha {brecha_ccl_pct:+.1f}% · Canje {canje_pct:+.1f}%"
                    if brecha_ccl_pct is not None and canje_pct is not None
                    else "Contado con Liquidación"
                ),
            },
            "riesgo_pais": {
                "series_id": "riesgo_pais",
                "label": "Riesgo País (EMBI+)",
                "value": riesgo.get("valor"),
                "change_pb": riesgo.get("change_pb"),
                "unit": "pb",
                "subtitle": f"Fecha ref: {riesgo.get('fecha')}" if riesgo.get("fecha") else "Spread soberano vs. UST",
            },
            "merval_usd": {
                "series_id": "merval_usd",
                "label": "S&P Merval en USD (CCL)",
                "value": merval.get("value_usd"),
                "change_pct": merval.get("change_pct"),
                "unit": "USD",
                "subtitle": f"S&P Merval ARS {merval['value_ars']:,.0f}" if merval.get("value_ars") else "Índice local en CCL",
            },
        },
        "sovereign_bonds": bonds,
        "news": news,
    }

    with _LOCK:
        _OVERVIEW_CACHE["ts"] = now
        _OVERVIEW_CACHE["payload"] = out
    return out


def _range_to_days(range_key: str) -> int | None:
    mapping = {
        "3m": 92,
        "6m": 183,
        "1y": 366,
        "3y": 365 * 3 + 1,
        "5y": 365 * 5 + 2,
        "max": None,
    }
    return mapping.get((range_key or "1y").strip().lower(), 366)


def _filter_points_by_range(points: list[dict[str, Any]], range_key: str) -> list[dict[str, Any]]:
    days = _range_to_days(range_key)
    if not days or not points:
        return points
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    filtered = [p for p in points if str(p.get("date") or "") >= cutoff]
    return filtered or points[-min(len(points), 30):]


def _fetch_argentinadatos_fx_series(casa: str) -> list[dict[str, Any]]:
    rows = _fetch_json(f"https://api.argentinadatos.com/v1/cotizaciones/dolares/{casa}", timeout=8)
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        dt = str(r.get("fecha") or "").strip()
        v = r.get("venta") or r.get("compra")
        if dt and v is not None and float(v) > 0:
            out.append({"date": dt, "value": round(float(v), 2)})
    out.sort(key=lambda x: x["date"])
    return out


def get_argentina_series(series_id: str, range_key: str = "1y") -> dict[str, Any]:
    sid = (series_id or "").strip()
    rk = (range_key or "1y").strip().lower()
    now = datetime.now(timezone.utc)
    with _LOCK:
        cached = _SERIES_CACHE.get((sid, rk))
        if cached and (now - cached[0]) < _SERIES_TTL:
            return cached[1]

    yf_period_map = {"3m": "3mo", "6m": "6mo", "1y": "1y", "3y": "3y", "5y": "5y", "max": "max"}
    yf_period = yf_period_map.get(rk, "1y")

    payload: dict[str, Any] = {
        "series_id": sid,
        "range": rk,
        "label": sid,
        "unit": "",
        "supports_candlestick": False,
        "source": "",
        "points": [],
    }

    if sid in ("fx_mayorista", "fx_oficial", "fx_mep", "fx_ccl"):
        casa_map = {
            "fx_mayorista": ("mayorista", "Dólar Mayorista (A3500)"),
            "fx_oficial": ("oficial", "Dólar Oficial Minorista"),
            "fx_mep": ("bolsa", "Dólar MEP"),
            "fx_ccl": ("contadoconliqui", "Dólar CCL"),
        }
        casa, label = casa_map[sid]
        pts = _filter_points_by_range(_fetch_argentinadatos_fx_series(casa), rk)
        payload.update({"label": label, "unit": "ARS", "supports_candlestick": False, "source": "ArgentinaDatos", "points": pts})

    elif sid == "riesgo_pais":
        rows = _fetch_json("https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais", timeout=8)
        pts = []
        if isinstance(rows, list):
            for r in rows:
                dt = str(r.get("fecha") or "").strip()
                if dt and r.get("valor") is not None:
                    pts.append({"date": dt, "value": round(float(r["valor"]), 0)})
            pts.sort(key=lambda x: x["date"])
        payload.update(
            {
                "label": "Riesgo País (EMBI+ Argentina)",
                "unit": "pb",
                "supports_candlestick": False,
                "source": "ArgentinaDatos",
                "points": _filter_points_by_range(pts, rk),
            }
        )

    elif sid == "merval_usd":
        ccl_pts = {p["date"]: p["value"] for p in _fetch_argentinadatos_fx_series("contadoconliqui")}
        hist = yf.Ticker("^MERV").history(period=yf_period, interval="1d")
        pts = []
        if hist is not None and not hist.empty:
            sorted_ccl_dates = sorted(ccl_pts.keys())
            last_ccl = ccl_pts[sorted_ccl_dates[-1]] if sorted_ccl_dates else 1100.0
            for idx, row in hist.iterrows():
                dt = idx.strftime("%Y-%m-%d")
                fx = ccl_pts.get(dt)
                if not fx and sorted_ccl_dates:
                    prior = [d for d in sorted_ccl_dates if d <= dt]
                    fx = ccl_pts[prior[-1]] if prior else last_ccl
                if fx and fx > 0 and pd.notna(row["Close"]):
                    o = round(float(row["Open"]) / fx, 2)
                    h = round(float(row["High"]) / fx, 2)
                    l = round(float(row["Low"]) / fx, 2)
                    c = round(float(row["Close"]) / fx, 2)
                    pts.append({"date": dt, "open": o, "high": h, "low": l, "close": c, "value": c})
        payload.update(
            {
                "label": "S&P Merval en USD (CCL)",
                "unit": "USD",
                "supports_candlestick": True,
                "source": "Yahoo Finance (^MERV) / ArgentinaDatos CCL",
                "points": pts,
            }
        )

    elif sid.startswith("bond_"):
        sym = sid.replace("bond_", "", 1).upper()
        pts = []
        used_sym = f"{sym}D.BA"
        hist = yf.Ticker(used_sym).history(period=yf_period, interval="1d")
        if hist is None or hist.empty:
            used_sym = f"{sym}.BA"
            hist_ars = yf.Ticker(used_sym).history(period=yf_period, interval="1d")
            mep_pts = {p["date"]: p["value"] for p in _fetch_argentinadatos_fx_series("bolsa")}
            sorted_mep = sorted(mep_pts.keys())
            last_mep = mep_pts[sorted_mep[-1]] if sorted_mep else 1100.0
            if hist_ars is not None and not hist_ars.empty:
                for idx, row in hist_ars.iterrows():
                    dt = idx.strftime("%Y-%m-%d")
                    prior = [d for d in sorted_mep if d <= dt]
                    fx = mep_pts.get(dt) or (mep_pts[prior[-1]] if prior else last_mep)
                    if fx and fx > 0 and pd.notna(row["Close"]):
                        o = _normalize_bond_price_100vn(float(row["Open"]) / fx)
                        h = _normalize_bond_price_100vn(float(row["High"]) / fx)
                        l = _normalize_bond_price_100vn(float(row["Low"]) / fx)
                        c = _normalize_bond_price_100vn(float(row["Close"]) / fx)
                        pts.append({"date": dt, "open": o, "high": h, "low": l, "close": c, "value": c})
        else:
            for idx, row in hist.iterrows():
                if pd.notna(row["Close"]):
                    dt = idx.strftime("%Y-%m-%d")
                    o = _normalize_bond_price_100vn(float(row["Open"]))
                    h = _normalize_bond_price_100vn(float(row["High"]))
                    l = _normalize_bond_price_100vn(float(row["Low"]))
                    c = _normalize_bond_price_100vn(float(row["Close"]))
                    pts.append({"date": dt, "open": o, "high": h, "low": l, "close": c, "value": c})

        payload.update(
            {
                "label": f"{sym} (USD cada 100 VN)",
                "unit": "USD",
                "supports_candlestick": True,
                "source": f"Yahoo Finance ({used_sym})",
                "points": pts,
            }
        )
    else:
        raise ValueError(f"Serie Argentina no soportada: {sid}")

    with _LOCK:
        if len(_SERIES_CACHE) >= 128:
            oldest = min(_SERIES_CACHE, key=lambda k: _SERIES_CACHE[k][0])
            _SERIES_CACHE.pop(oldest, None)
        _SERIES_CACHE[(sid, rk)] = (now, payload)
    return payload
