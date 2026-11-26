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
from sqlalchemy.orm import Session
import yfinance as yf

from app.models.database import ArgentinaSocialOverride

_OVERVIEW_TTL = timedelta(minutes=10)
_SERIES_TTL = timedelta(minutes=20)
_LOCK = threading.Lock()
_BUILD_LOCK = threading.Lock()
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

PROVINCIAL_BONDS: list[dict[str, Any]] = [
    {"ticker": "BA37D", "name": "Prov. Buenos Aires 2037", "law": "Provincial", "issuer": "Buenos Aires", "maturity": "2037-09-01", "coupon_pct": 6.375, "yf_candidates": ["BA37D.BA", "BA37.BA"]},
    {"ticker": "BDC28", "name": "CABA Tango 2028", "law": "Provincial", "issuer": "CABA", "maturity": "2028-02-22", "coupon_pct": 7.50, "yf_candidates": ["BDC28D.BA", "BDC28.BA"]},
    {"ticker": "CO26D", "name": "Prov. Córdoba 2027", "law": "Provincial", "issuer": "Córdoba", "maturity": "2027-12-10", "coupon_pct": 6.875, "yf_candidates": ["CO26D.BA", "CO26.BA"]},
    {"ticker": "PMM29", "name": "Prov. Mendoza 2029", "law": "Provincial", "issuer": "Mendoza", "maturity": "2029-03-19", "coupon_pct": 5.75, "yf_candidates": ["PMM29D.BA", "PMM29.BA"]},
    {"ticker": "NQN30", "name": "Prov. Neuquén 2030", "law": "Provincial", "issuer": "Neuquén", "maturity": "2030-04-27", "coupon_pct": 6.625, "yf_candidates": ["NQN30D.BA", "NQN30.BA", "NDT25.BA"]},
    {"ticker": "SF27D", "name": "Prov. Santa Fe 2027", "law": "Provincial", "issuer": "Santa Fe", "maturity": "2027-11-01", "coupon_pct": 6.90, "yf_candidates": ["SF27D.BA", "SF27.BA"]},
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

MACRO_SERIES_CONFIG: dict[str, dict[str, Any]] = {
    "ipc_mensual": {
        "label": "IPC Mensual",
        "unit": "%",
        "source": "INDEC · datos.gob.ar",
        "subtitle": "Variación mensual nivel general",
        "datos_gob_id": "148.3_INIVELNAL_DICI_M_26",
        "representation": "percent_change",
        "argentinadatos_url": "https://api.argentinadatos.com/v1/finanzas/indices/inflacion",
    },
    "ipc_interanual": {
        "label": "IPC Interanual",
        "unit": "%",
        "source": "INDEC · datos.gob.ar",
        "subtitle": "Variación últimos 12 meses",
        "datos_gob_id": "148.3_INIVELNAL_DICI_M_26",
        "representation": "percent_change_a_year_ago",
        "argentinadatos_url": "https://api.argentinadatos.com/v1/finanzas/indices/inflacionInteranual",
    },
    "emae": {
        "label": "Actividad (EMAE Desest.)",
        "unit": "Índice",
        "source": "INDEC · datos.gob.ar",
        "subtitle": "Base 2004 = 100 · Desestacionalizado",
        "datos_gob_id": "143.3_NO_PR_2004_A_31",
    },
    "reservas_internacionales": {
        "label": "Reservas Internacionales",
        "unit": "USD M",
        "source": "BCRA · Estadísticas v4.0",
        "subtitle": "Stock bruto en millones de USD",
        "bcra_var_id": 1,
        "datos_gob_id": "182.1_VARIACION_LES_0_M_43",
    },
    "base_monetaria": {
        "label": "Base Monetaria",
        "unit": "ARS M",
        "source": "BCRA · Estadísticas v4.0",
        "subtitle": "Circulación + encajes en millones ARS",
        "bcra_var_id": 15,
        "datos_gob_id": "300.1_AP_PAS_BASRIA_0_M_21",
    },
    "tasa_referencia": {
        "label": "Tasa Referencia / TNA",
        "unit": "%",
        "source": "BCRA · ArgentinaDatos",
        "subtitle": "Tasa nominal anual de referencia",
        "datos_gob_id": "89.2_TS_INTELIG_0_D_20",
        "argentinadatos_url": "https://api.argentinadatos.com/v1/finanzas/tasas/depositos30Dias",
        "scale_decimal_pct": True,
    },
    "resultado_fiscal": {
        "label": "Resultado Primario SPN",
        "unit": "ARS M",
        "source": "MECON · datos.gob.ar",
        "subtitle": "Sector Público Nacional (mensual)",
        "datos_gob_id": "452.3_RESULTADO_RIO_0_M_18_54",
    },
    "balanza_comercial": {
        "label": "Balanza Comercial",
        "unit": "USD M",
        "source": "INDEC · datos.gob.ar",
        "subtitle": "Saldo exportaciones menos importaciones",
        "datos_gob_id": "74.3_ISC_0_M_19",
    },
}

SOCIAL_SERIES_CONFIG: dict[str, dict[str, Any]] = {
    "indec_pobreza": {
        "label": "Pobreza (Personas · INDEC)",
        "unit": "%",
        "source": "INDEC · Encuesta Permanente de Hogares",
        "subtitle": "Total aglomerados urbanos (semestral)",
        "baseline_points": [
            {"date": "2018-06-30", "value": 27.3, "note": "1° Semestre 2018"},
            {"date": "2018-12-31", "value": 32.0, "note": "2° Semestre 2018"},
            {"date": "2019-06-30", "value": 35.4, "note": "1° Semestre 2019"},
            {"date": "2019-12-31", "value": 35.5, "note": "2° Semestre 2019"},
            {"date": "2020-06-30", "value": 40.9, "note": "1° Semestre 2020"},
            {"date": "2020-12-31", "value": 42.0, "note": "2° Semestre 2020"},
            {"date": "2021-06-30", "value": 40.6, "note": "1° Semestre 2021"},
            {"date": "2021-12-31", "value": 37.3, "note": "2° Semestre 2021"},
            {"date": "2022-06-30", "value": 36.5, "note": "1° Semestre 2022"},
            {"date": "2022-12-31", "value": 39.2, "note": "2° Semestre 2022"},
            {"date": "2023-06-30", "value": 40.1, "note": "1° Semestre 2023"},
            {"date": "2023-12-31", "value": 41.7, "note": "2° Semestre 2023"},
            {"date": "2024-06-30", "value": 52.9, "note": "1° Semestre 2024"},
            {"date": "2024-12-31", "value": 38.1, "note": "2° Semestre 2024"},
            {"date": "2025-06-30", "value": 31.6, "note": "1° Semestre 2025 (ref. oficial)"},
        ],
    },
    "indec_indigencia": {
        "label": "Indigencia (Personas · INDEC)",
        "unit": "%",
        "source": "INDEC · Encuesta Permanente de Hogares",
        "subtitle": "Total aglomerados urbanos (semestral)",
        "baseline_points": [
            {"date": "2018-06-30", "value": 4.9, "note": "1° Semestre 2018"},
            {"date": "2018-12-31", "value": 6.7, "note": "2° Semestre 2018"},
            {"date": "2019-06-30", "value": 7.7, "note": "1° Semestre 2019"},
            {"date": "2019-12-31", "value": 8.0, "note": "2° Semestre 2019"},
            {"date": "2020-06-30", "value": 10.5, "note": "1° Semestre 2020"},
            {"date": "2020-12-31", "value": 10.5, "note": "2° Semestre 2020"},
            {"date": "2021-06-30", "value": 10.7, "note": "1° Semestre 2021"},
            {"date": "2021-12-31", "value": 8.2, "note": "2° Semestre 2021"},
            {"date": "2022-06-30", "value": 8.8, "note": "1° Semestre 2022"},
            {"date": "2022-12-31", "value": 8.1, "note": "2° Semestre 2022"},
            {"date": "2023-06-30", "value": 9.3, "note": "1° Semestre 2023"},
            {"date": "2023-12-31", "value": 11.9, "note": "2° Semestre 2023"},
            {"date": "2024-06-30", "value": 18.1, "note": "1° Semestre 2024"},
            {"date": "2024-12-31", "value": 8.2, "note": "2° Semestre 2024"},
            {"date": "2025-06-30", "value": 6.9, "note": "1° Semestre 2025 (ref. oficial)"},
        ],
    },
    "uca_pobreza": {
        "label": "Pobreza (ODSA · UCA)",
        "unit": "%",
        "source": "Observatorio de la Deuda Social Argentina (UCA)",
        "subtitle": "Estimación por ingresos ODSA-UCA",
        "baseline_points": [
            {"date": "2018-10-31", "value": 33.6, "note": "3° Trimestre 2018"},
            {"date": "2019-10-31", "value": 39.8, "note": "3° Trimestre 2019"},
            {"date": "2020-10-31", "value": 44.7, "note": "3° Trimestre 2020"},
            {"date": "2021-10-31", "value": 42.4, "note": "3° Trimestre 2021"},
            {"date": "2022-10-31", "value": 43.1, "note": "3° Trimestre 2022"},
            {"date": "2023-10-31", "value": 44.7, "note": "3° Trimestre 2023"},
            {"date": "2024-03-31", "value": 54.9, "note": "1° Trimestre 2024"},
            {"date": "2024-09-30", "value": 49.9, "note": "3° Trimestre 2024"},
            {"date": "2025-03-31", "value": 38.9, "note": "1° Trimestre 2025 (estimación UCA)"},
        ],
    },
    "utdt_icg": {
        "label": "Confianza en el Gobierno (ICG)",
        "unit": "pts (0-5)",
        "source": "Universidad Torcuato Di Tella (UTDT)",
        "subtitle": "Escala 0 a 5 · Índice mensual",
        "baseline_points": [
            {"date": "2024-01-31", "value": 2.61, "note": "Enero 2024"},
            {"date": "2024-03-31", "value": 2.56, "note": "Marzo 2024"},
            {"date": "2024-05-31", "value": 2.51, "note": "Mayo 2024"},
            {"date": "2024-07-31", "value": 2.37, "note": "Julio 2024"},
            {"date": "2024-09-30", "value": 2.16, "note": "Septiembre 2024"},
            {"date": "2024-11-30", "value": 2.66, "note": "Noviembre 2024"},
            {"date": "2025-01-31", "value": 2.61, "note": "Enero 2025"},
            {"date": "2025-03-31", "value": 2.42, "note": "Marzo 2025"},
            {"date": "2025-05-31", "value": 2.45, "note": "Mayo 2025"},
            {"date": "2025-07-31", "value": 2.40, "note": "Julio 2025"},
        ],
    },
}

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
    if ccl_rate and ccl_rate > 0:
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
                        "label": "S&P Merval en USD (CCL)",
                        "subtitle": f"S&P Merval ARS {last_ars:,.0f}",
                    }
        except Exception:
            pass

    # Fallback a ETF MSCI Argentina (ARGT) en USD cuando Yahoo no entrega ^MERV
    try:
        hist_argt = yf.Ticker("ARGT").history(period="5d", interval="1d")
        if hist_argt is not None and not hist_argt.empty and "Close" in hist_argt.columns:
            closes = [float(v) for v in hist_argt["Close"].dropna().tolist() if float(v) > 0]
            if closes:
                last_usd = round(closes[-1], 2)
                prev_usd = closes[-2] if len(closes) >= 2 else last_usd
                chg_pct = round(((last_usd - prev_usd) / prev_usd) * 100.0, 2) if prev_usd > 0 else 0.0
                return {
                    "value_usd": last_usd,
                    "change_pct": chg_pct,
                    "value_ars": None,
                    "label": "Renta Variable Arg. (ARGT)",
                    "subtitle": "MSCI Argentina ETF en USD (proxy)",
                }
    except Exception:
        pass
    return {"value_usd": None, "change_pct": None, "value_ars": None}


def _normalize_bond_price_100vn(raw_val: float) -> float:
    # En BYMA/Yahoo algunos bonos cotizan por 1 VN (ej. 0.68 USD) y otros por 100 VN (68.00 USD)
    if 0.0 < raw_val < 3.0:
        return round(raw_val * 100.0, 2)
    return round(raw_val, 2)


def _fetch_data912_bonds_map() -> dict[str, dict[str, Any]]:
    try:
        rows = _fetch_json("https://data912.com/live/arg_bonds", timeout=6)
        if isinstance(rows, list):
            return {
                str(r.get("symbol") or "").strip().upper(): r
                for r in rows
                if r.get("symbol")
            }
    except Exception:
        pass
    return {}


def _fetch_single_sovereign_bond(
    bond_cfg: dict[str, Any],
    mep_rate: float | None,
    live_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    sym = bond_cfg["ticker"]
    price_usd: float | None = None
    change_pct: float | None = None
    source_used = "BYMA/data912"

    if live_map:
        d912_candidates = [sym] if sym.endswith("D") else [f"{sym}D", sym]
        for cand in d912_candidates:
            row = live_map.get(cand)
            if not row:
                continue
            raw_px = float(row.get("c") or row.get("px_bid") or row.get("px_ask") or 0.0)
            if raw_px <= 0:
                continue
            needs_fx = not cand.endswith("D")
            if needs_fx or raw_px > 500:
                if not mep_rate or mep_rate <= 0:
                    continue
                price_usd = _normalize_bond_price_100vn(raw_px / mep_rate)
            else:
                price_usd = _normalize_bond_price_100vn(raw_px)
            pct = row.get("pct_change")
            change_pct = round(float(pct), 2) if pct is not None else None
            source_used = f"data912 ({cand})"
            break

    if price_usd is None and not live_map:
        raw_candidates = bond_cfg.get("yf_candidates") or [f"{sym}D.BA", f"{sym}.BA"]
        candidates = [(c, not c.upper().endswith("D.BA")) for c in raw_candidates]
        for suffix, needs_fx in candidates:
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
        "issuer": bond_cfg.get("issuer", "Nación"),
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


def _fetch_datos_gob_series(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    bcra_var_id = cfg.get("bcra_var_id")
    gid = cfg.get("datos_gob_id")
    rep = cfg.get("representation")
    pts: list[dict[str, Any]] = []

    if bcra_var_id:
        try:
            url = f"https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/{bcra_var_id}?limit=1000"
            resp = requests.get(url, headers=_HEADERS, timeout=7, verify=False)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results") if isinstance(data, dict) else None
            detalle = results[0].get("detalle") if isinstance(results, list) and results else None
            if isinstance(detalle, list):
                for row in detalle:
                    dt = str(row.get("fecha") or "").strip()[:10]
                    val = row.get("valor")
                    if dt and val is not None:
                        pts.append({"date": dt, "value": round(float(val), 2)})
                pts.sort(key=lambda x: x["date"])
        except Exception:
            pts = []

    if not pts and gid:
        try:
            rep_param = f"&representation_mode={rep}" if rep else ""
            url = f"https://apis.datos.gob.ar/series/api/series/?ids={gid}{rep_param}&limit=1000&format=json"
            data = _fetch_json(url, timeout=8)
            rows = data.get("data") if isinstance(data, dict) else None
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, (list, tuple)) and len(row) >= 2 and row[1] is not None:
                        dt = str(row[0]).strip()[:10]
                        val = float(row[1])
                        if rep in ("percent_change", "percent_change_a_year_ago"):
                            val = val * 100.0
                        pts.append({"date": dt, "value": round(val, 2)})
                pts.sort(key=lambda x: x["date"])
        except Exception:
            pts = []

    if not pts and cfg.get("argentinadatos_url"):
        try:
            rows = _fetch_json(cfg["argentinadatos_url"], timeout=8)
            if isinstance(rows, list):
                for row in rows:
                    dt = str(row.get("fecha") or "").strip()[:10]
                    val = row.get("valor")
                    if dt and val is not None:
                        fval = float(val)
                        if cfg.get("scale_decimal_pct") and 0 < abs(fval) < 3.0:
                            fval = fval * 100.0
                        pts.append({"date": dt, "value": round(fval, 2)})
                pts.sort(key=lambda x: x["date"])
        except Exception:
            pass
    return pts


def _fetch_single_macro_card(series_id: str, cfg: dict[str, Any]) -> dict[str, Any]:
    pts = _fetch_datos_gob_series(cfg)
    latest = pts[-1] if pts else None
    prev = pts[-2] if len(pts) >= 2 else None
    val = latest["value"] if latest else None
    delta = round(val - prev["value"], 2) if (val is not None and prev is not None) else None
    return {
        "series_id": series_id,
        "label": cfg["label"],
        "value": val,
        "prev_value": prev["value"] if prev else None,
        "delta": delta,
        "unit": cfg["unit"],
        "date": latest["date"] if latest else None,
        "source": cfg["source"],
        "subtitle": cfg["subtitle"],
    }


def _load_social_series_data(series_id: str, db: Session | None = None) -> dict[str, Any]:
    cfg = SOCIAL_SERIES_CONFIG[series_id]
    points = [dict(p) for p in cfg["baseline_points"]]
    source = cfg["source"]
    is_override = False
    updated_at = None
    updated_by = None

    if db is not None:
        row = db.query(ArgentinaSocialOverride).filter(ArgentinaSocialOverride.series_id == series_id).first()
        if row and isinstance(row.points_json, list) and row.points_json:
            cleaned: list[dict[str, Any]] = []
            for p in row.points_json:
                dt = str(p.get("date") or "").strip()[:10]
                if dt and p.get("value") is not None:
                    item = {"date": dt, "value": round(float(p["value"]), 2)}
                    if p.get("note"):
                        item["note"] = str(p["note"])[:160]
                    cleaned.append(item)
            if cleaned:
                cleaned.sort(key=lambda x: x["date"])
                points = cleaned
                source = row.source or source
                is_override = True
                updated_at = row.updated_at.isoformat() if row.updated_at else None
                updated_by = row.updated_by

    return {
        "series_id": series_id,
        "label": cfg["label"],
        "unit": cfg["unit"],
        "source": source,
        "subtitle": cfg["subtitle"],
        "is_override": is_override,
        "updated_at": updated_at,
        "updated_by": updated_by,
        "points": points,
    }


def _build_social_cards(db: Session | None = None) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for sid in SOCIAL_SERIES_CONFIG:
        data = _load_social_series_data(sid, db=db)
        pts = data["points"]
        latest = pts[-1] if pts else None
        prev = pts[-2] if len(pts) >= 2 else None
        val = latest["value"] if latest else None
        delta = round(val - prev["value"], 2) if (val is not None and prev is not None) else None
        cards.append(
            {
                "series_id": sid,
                "label": data["label"],
                "value": val,
                "prev_value": prev["value"] if prev else None,
                "delta": delta,
                "unit": data["unit"],
                "date": latest["date"] if latest else None,
                "note": latest.get("note") if latest else None,
                "source": data["source"],
                "subtitle": data["subtitle"],
                "is_override": data["is_override"],
            }
        )
    return cards


def get_social_overrides(db: Session) -> list[dict[str, Any]]:
    return [_load_social_series_data(sid, db=db) for sid in SOCIAL_SERIES_CONFIG]


def upsert_social_override(
    db: Session,
    series_id: str,
    points: list[dict[str, Any]],
    source: str | None = None,
    updated_by: str | None = None,
) -> dict[str, Any]:
    sid = (series_id or "").strip()
    if sid not in SOCIAL_SERIES_CONFIG:
        raise ValueError(f"Indicador social/político inválido: {sid}")
    cfg = SOCIAL_SERIES_CONFIG[sid]
    cleaned: list[dict[str, Any]] = []
    seen_dates: dict[str, dict[str, Any]] = {}
    for p in points:
        dt = str(p.get("date") or "").strip()[:10]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", dt):
            raise ValueError(f"Fecha inválida '{dt}'. Usá formato YYYY-MM-DD.")
        val = round(float(p["value"]), 2)
        item: dict[str, Any] = {"date": dt, "value": val}
        if p.get("note"):
            item["note"] = str(p["note"]).strip()[:160]
        seen_dates[dt] = item
    cleaned = [seen_dates[k] for k in sorted(seen_dates.keys())]
    if not cleaned:
        raise ValueError("Debe incluir al menos un punto histórico válido.")

    row = db.query(ArgentinaSocialOverride).filter(ArgentinaSocialOverride.series_id == sid).first()
    if row is None:
        row = ArgentinaSocialOverride(
            series_id=sid,
            label=cfg["label"],
            unit=cfg["unit"],
            source=(source or cfg["source"]).strip()[:160],
            points_json=cleaned,
            updated_by=(updated_by or "")[:120],
            updated_at=datetime.utcnow(),
        )
        db.add(row)
    else:
        row.source = (source or row.source or cfg["source"]).strip()[:160]
        row.points_json = cleaned
        row.updated_by = (updated_by or "")[:120]
        row.updated_at = datetime.utcnow()
    db.commit()

    with _LOCK:
        _OVERVIEW_CACHE["ts"] = None
        _OVERVIEW_CACHE["payload"] = None
        for k in [key for key in list(_SERIES_CACHE.keys()) if key[0] == sid]:
            _SERIES_CACHE.pop(k, None)

    return _load_social_series_data(sid, db=db)


def reset_social_override(db: Session, series_id: str) -> dict[str, Any]:
    sid = (series_id or "").strip()
    if sid not in SOCIAL_SERIES_CONFIG:
        raise ValueError(f"Indicador social/político inválido: {sid}")
    db.query(ArgentinaSocialOverride).filter(ArgentinaSocialOverride.series_id == sid).delete()
    db.commit()

    with _LOCK:
        _OVERVIEW_CACHE["ts"] = None
        _OVERVIEW_CACHE["payload"] = None
        for k in [key for key in list(_SERIES_CACHE.keys()) if key[0] == sid]:
            _SERIES_CACHE.pop(k, None)

    return _load_social_series_data(sid, db=db)


def build_argentina_overview(db: Session | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    with _LOCK:
        ts = _OVERVIEW_CACHE.get("ts")
        payload = _OVERVIEW_CACHE.get("payload")
        if ts and payload and (now - ts) < _OVERVIEW_TTL:
            out = dict(payload)
            out["social_indicators"] = _build_social_cards(db=db)
            return out

    with _BUILD_LOCK:
        now = datetime.now(timezone.utc)
        with _LOCK:
            ts = _OVERVIEW_CACHE.get("ts")
            payload = _OVERVIEW_CACHE.get("payload")
            if ts and payload and (now - ts) < _OVERVIEW_TTL:
                out = dict(payload)
                out["social_indicators"] = _build_social_cards(db=db)
                return out

        with ThreadPoolExecutor(max_workers=12) as pool:
            f_fx = pool.submit(_fetch_dolares_snapshot)
            f_rp = pool.submit(_fetch_riesgo_pais_snapshot)
            f_news = pool.submit(_fetch_argentina_news)
            f_d912 = pool.submit(_fetch_data912_bonds_map)
            f_macro = {
                sid: pool.submit(_fetch_single_macro_card, sid, cfg)
                for sid, cfg in MACRO_SERIES_CONFIG.items()
            }

            dolares = f_fx.result()
            riesgo = f_rp.result()
            news = f_news.result()
            live_bonds_map = f_d912.result()
            macro_indicators = [fut.result() for fut in f_macro.values()]

        mayorista = (dolares.get("mayorista") or {}).get("venta")
        oficial = (dolares.get("oficial") or {}).get("venta")
        mep = (dolares.get("bolsa") or {}).get("promedio") or (dolares.get("bolsa") or {}).get("venta")
        ccl = (dolares.get("contadoconliqui") or {}).get("venta") or (dolares.get("contadoconliqui") or {}).get("promedio")

        brecha_mep_pct = round(((mep - mayorista) / mayorista) * 100.0, 2) if (mep and mayorista and mayorista > 0) else None
        brecha_ccl_pct = round(((ccl - mayorista) / mayorista) * 100.0, 2) if (ccl and mayorista and mayorista > 0) else None
        canje_pct = round(((ccl - mep) / mep) * 100.0, 2) if (ccl and mep and mep > 0) else None

        merval = _fetch_merval_usd(ccl)
        bonds = [_fetch_single_sovereign_bond(cfg, mep, live_map=live_bonds_map) for cfg in SOVEREIGN_BONDS]
        provincial_bonds = [_fetch_single_sovereign_bond(cfg, mep, live_map=live_bonds_map) for cfg in PROVINCIAL_BONDS]

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
                    "label": merval.get("label") or "S&P Merval en USD (CCL)",
                    "value": merval.get("value_usd"),
                    "change_pct": merval.get("change_pct"),
                    "unit": "USD",
                    "subtitle": merval.get("subtitle") or (f"S&P Merval ARS {merval['value_ars']:,.0f}" if merval.get("value_ars") else "Índice local en CCL"),
                },
            },
            "macro_indicators": macro_indicators,
            "social_indicators": _build_social_cards(db=db),
            "sovereign_bonds": bonds,
            "provincial_bonds": provincial_bonds,
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


def get_argentina_series(series_id: str, range_key: str = "1y", db: Session | None = None) -> dict[str, Any]:
    sid = (series_id or "").strip()
    rk = (range_key or "1y").strip().lower()
    now = datetime.now(timezone.utc)
    if sid not in SOCIAL_SERIES_CONFIG:
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
        pts = []
        label = "S&P Merval en USD (CCL)"
        source = "Yahoo Finance (^MERV) / ArgentinaDatos CCL"
        try:
            hist = yf.Ticker("^MERV").history(period=yf_period, interval="1d")
            if hist is not None and not hist.empty:
                ccl_pts = {p["date"]: p["value"] for p in _fetch_argentinadatos_fx_series("contadoconliqui")}
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
        except Exception:
            pts = []

        if not pts:
            try:
                hist_argt = yf.Ticker("ARGT").history(period=yf_period, interval="1d")
                if hist_argt is not None and not hist_argt.empty:
                    for idx, row in hist_argt.iterrows():
                        if pd.notna(row["Close"]):
                            dt = idx.strftime("%Y-%m-%d")
                            o = round(float(row["Open"]), 2)
                            h = round(float(row["High"]), 2)
                            l = round(float(row["Low"]), 2)
                            c = round(float(row["Close"]), 2)
                            pts.append({"date": dt, "open": o, "high": h, "low": l, "close": c, "value": c})
                    label = "Renta Variable Argentina (ARGT · USD)"
                    source = "Yahoo Finance (ARGT ETF)"
            except Exception:
                pass

        payload.update(
            {
                "label": label,
                "unit": "USD",
                "supports_candlestick": True,
                "source": source,
                "points": pts,
            }
        )

    elif sid.startswith("bond_"):
        sym = sid.replace("bond_", "", 1).upper()
        pts = []
        bond_cfg = next((b for b in PROVINCIAL_BONDS + SOVEREIGN_BONDS if b["ticker"] == sym), None)
        d912_candidates = [sym] if sym.endswith("D") else [f"{sym}D", sym]
        used_sym = d912_candidates[0]
        source_str = ""
        mep_pts: dict[str, float] | None = None

        # 1) Fuente primaria rápida con OHLC diario: data912.com
        for cand in d912_candidates:
            try:
                rows = _fetch_json(f"https://data912.com/historical/bonds/{cand}", timeout=6)
                if not isinstance(rows, list) or not rows:
                    continue
                first_c = float(rows[-1].get("c") or 0.0)
                needs_fx = (not cand.endswith("D")) or first_c > 500
                if needs_fx:
                    if mep_pts is None:
                        mep_pts = {p["date"]: p["value"] for p in _fetch_argentinadatos_fx_series("bolsa")}
                    sorted_mep = sorted(mep_pts.keys())
                    last_mep = mep_pts[sorted_mep[-1]] if sorted_mep else 1100.0
                for row in rows:
                    dt = str(row.get("date") or "").strip()[:10]
                    if not dt or row.get("c") is None:
                        continue
                    o_raw = float(row.get("o") or row["c"])
                    h_raw = float(row.get("h") or row["c"])
                    l_raw = float(row.get("l") or row["c"])
                    c_raw = float(row["c"])
                    if needs_fx:
                        prior = [d for d in sorted_mep if d <= dt]
                        fx = mep_pts.get(dt) or (mep_pts[prior[-1]] if prior else last_mep)
                        if not fx or fx <= 0:
                            continue
                        o_raw, h_raw, l_raw, c_raw = o_raw / fx, h_raw / fx, l_raw / fx, c_raw / fx
                    pts.append(
                        {
                            "date": dt,
                            "open": _normalize_bond_price_100vn(o_raw),
                            "high": _normalize_bond_price_100vn(h_raw),
                            "low": _normalize_bond_price_100vn(l_raw),
                            "close": _normalize_bond_price_100vn(c_raw),
                            "value": _normalize_bond_price_100vn(c_raw),
                        }
                    )
                if pts:
                    pts.sort(key=lambda x: x["date"])
                    pts = _filter_points_by_range(pts, rk)
                    used_sym = cand
                    source_str = f"data912 ({cand})"
                    break
            except Exception:
                continue

        # 2) Fallback a Yahoo Finance si data912 no devolvió serie
        if not pts:
            candidates = (bond_cfg.get("yf_candidates") if bond_cfg else None) or [f"{sym}D.BA", f"{sym}.BA"]
            for cand in candidates:
                try:
                    hist = yf.Ticker(cand).history(period=yf_period, interval="1d")
                    if hist is None or hist.empty:
                        continue
                    used_sym = cand
                    needs_fx = not cand.upper().endswith("D.BA")
                    if needs_fx:
                        if mep_pts is None:
                            mep_pts = {p["date"]: p["value"] for p in _fetch_argentinadatos_fx_series("bolsa")}
                        sorted_mep = sorted(mep_pts.keys())
                        last_mep = mep_pts[sorted_mep[-1]] if sorted_mep else 1100.0
                        for idx, row in hist.iterrows():
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
                    if pts:
                        source_str = f"Yahoo Finance ({used_sym})"
                        break
                except Exception:
                    continue

        payload.update(
            {
                "label": f"{sym} (USD cada 100 VN)",
                "unit": "USD",
                "supports_candlestick": True,
                "source": source_str or f"data912 / BYMA ({used_sym})",
                "points": pts,
            }
        )
    elif sid in MACRO_SERIES_CONFIG:
        cfg = MACRO_SERIES_CONFIG[sid]
        pts = _filter_points_by_range(_fetch_datos_gob_series(cfg), rk)
        payload.update(
            {
                "label": cfg["label"],
                "unit": cfg["unit"],
                "supports_candlestick": False,
                "source": cfg["source"],
                "points": pts,
            }
        )
    elif sid in SOCIAL_SERIES_CONFIG:
        data = _load_social_series_data(sid, db=db)
        pts = _filter_points_by_range(data["points"], rk)
        payload.update(
            {
                "label": data["label"],
                "unit": data["unit"],
                "supports_candlestick": False,
                "source": data["source"],
                "is_override": data["is_override"],
                "points": pts,
            }
        )
    else:
        raise ValueError(f"Serie Argentina no soportada: {sid}")

    if sid not in SOCIAL_SERIES_CONFIG:
        with _LOCK:
            if len(_SERIES_CACHE) >= 128:
                oldest = min(_SERIES_CACHE, key=lambda k: _SERIES_CACHE[k][0])
                _SERIES_CACHE.pop(oldest, None)
            _SERIES_CACHE[(sid, rk)] = (now, payload)
    return payload
