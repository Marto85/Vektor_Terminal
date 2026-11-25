from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import math
import re
from typing import Any
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import pandas as pd
import yfinance as yf
from deep_translator import GoogleTranslator, MyMemoryTranslator
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from app.models.database import (
    CompanyData,
    CompanyProfile,
    CompanyMarketCache,
    CompanyEstimatesCache,
    is_sqlite,
)

MARKET_CACHE_TTL = timedelta(hours=4)
ESTIMATES_CACHE_TTL = timedelta(hours=24)
CF_LTM_SCHEMA_VERSION = 6
SEC_HEADERS = {"User-Agent": "MiTerminalFinanciera/1.0 (contacto@miterminal.local)"}
WEB_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VektorTerminal/1.0)"}

MESES_ES = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


def _upsert_by_ticker(db: Session, model: Any, ticker_upper: str, values: dict[str, Any]) -> None:
    """
    Ejecuta INSERT ... ON CONFLICT (ticker) DO UPDATE compatible con PostgreSQL (Neon) y SQLite,
    eliminando errores `UniqueViolation` por peticiones concurrentes.
    """
    insert_fn = sqlite_insert if is_sqlite else pg_insert
    stmt = insert_fn(model).values(ticker=ticker_upper, **values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker"],
        set_=values,
    )
    db.execute(stmt)
    db.commit()


def _to_mm(val: Any, fx_rate: float = 1.0) -> float | None:
    if val is None:
        return None
    try:
        f = float(val) * fx_rate
        return None if (math.isnan(f) or math.isinf(f)) else round(f / 1_000_000.0, 2)
    except (TypeError, ValueError):
        return None


def _to_float(val: Any, decimals: int = 2) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, decimals)
    except (TypeError, ValueError):
        return None


def _to_pct(val: Any, decimals: int = 1) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else round(f * 100.0, decimals)
    except (TypeError, ValueError):
        return None


def _looks_english(text: str) -> bool:
    """
    Detecta si un texto corporativo o titular sigue redactado en inglés
    para traducirlo al español automáticamente.
    """
    sample = f" {text.lower()} "
    en_markers = (
        " engages in ",
        " operates through ",
        " provides ",
        " develops ",
        " manufactures ",
        " founded in ",
        " headquartered in ",
        " the company ",
        " its products ",
        " united states",
        " is an american ",
        " is a multinational ",
        " stock ",
        " shares ",
        " earnings ",
        " revenue ",
        " quarter ",
        " announces ",
        " reports ",
    )
    es_markers = (
        " se dedica ",
        " opera a través ",
        " proporciona ",
        " ofrece ",
        " fundada en ",
        " con sede en ",
        " la empresa ",
        " la compañía ",
        " estados unidos",
        " es una empresa ",
        " acciones ",
        " ganancias ",
        " ingresos ",
        " trimestre ",
        " anuncia ",
        " reporta ",
    )
    en_hits = sum(1 for m in en_markers if m in sample)
    es_hits = sum(1 for m in es_markers if m in sample)
    return en_hits >= 2 and es_hits == 0


def _translate_to_spanish(raw_text: str, ticker_upper: str) -> tuple[str, bool]:
    """
    Traduce al español usando GoogleTranslator como primario y MyMemoryTranslator
    (en fragmentos <= 450 caracteres) como respaldo transparente.
    Devuelve `(texto_resultante, traduccion_exitosa)`.
    """
    clean_text = raw_text.strip()
    if not clean_text:
        return "", False

    text_to_translate = clean_text[:4900] + "..." if len(clean_text) > 4900 else clean_text

    # 1. Intento primario: GoogleTranslator
    try:
        translated = GoogleTranslator(source="en", target="es").translate(text_to_translate)
        if isinstance(translated, str) and translated.strip() and not _looks_english(translated):
            return translated.strip(), True
    except Exception as e:
        print(f"FALLBACK TRADUCCION (Google -> MyMemory) para {ticker_upper}: {e}")

    # 2. Respaldo: MyMemoryTranslator dividido por oraciones <= 450 chars
    try:
        sentences = re.split(r"(?<=[.!?])\s+", text_to_translate)
        chunks: list[str] = []
        current_chunk = ""
        for sent in sentences:
            if len(sent) > 450:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                for i in range(0, len(sent), 450):
                    chunks.append(sent[i : i + 450].strip())
            elif len(current_chunk) + len(sent) + 1 <= 450:
                current_chunk = f"{current_chunk} {sent}".strip()
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sent.strip()
        if current_chunk:
            chunks.append(current_chunk.strip())

        translator_mm = MyMemoryTranslator(source="en-US", target="es-ES")
        translated_parts: list[str] = []
        for ch in chunks:
            part = translator_mm.translate(ch)
            if isinstance(part, str) and part.strip():
                translated_parts.append(part.strip())

        combined = " ".join(translated_parts).strip()
        if combined and not _looks_english(combined):
            return combined, True
    except Exception as e:
        print(f"ERROR EN TRADUCCION RESPALDO para {ticker_upper}: {e}")

    return clean_text, False


def _translate_headline_es(title: str) -> str:
    """Traduce un titular corto al español de forma segura sin bloquear en caso de fallo."""
    clean = title.strip()
    if not clean:
        return ""
    try:
        translated = GoogleTranslator(source="auto", target="es").translate(clean[:300])
        if isinstance(translated, str) and translated.strip():
            return translated.strip()
    except Exception:
        pass
    return clean


def _parse_event_datetime(raw_val: Any) -> datetime | None:
    if raw_val is None:
        return None
    if isinstance(raw_val, (list, tuple)):
        if not raw_val:
            return None
        raw_val = raw_val[0]
    if isinstance(raw_val, datetime):
        return raw_val.replace(tzinfo=None)
    if hasattr(raw_val, "year") and hasattr(raw_val, "month") and hasattr(raw_val, "day"):
        return datetime(int(raw_val.year), int(raw_val.month), int(raw_val.day))
    if isinstance(raw_val, (int, float)):
        ts = float(raw_val)
        if ts > 1e12:
            ts = ts / 1000.0
        if ts > 1_500_000_000:
            try:
                return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
            except Exception:
                return None
    if isinstance(raw_val, str) and raw_val.strip():
        clean = raw_val.strip()
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(clean[:19], fmt)
            except ValueError:
                continue
    return None


def _extract_upcoming_events(ticker_obj: yf.Ticker, info: dict[str, Any]) -> list[dict[str, str]]:
    """
    Extrae los próximos eventos corporativos reales (Presentación de Resultados,
    Fecha Ex-Dividendo y Pago de Dividendo) desde Yahoo Finance.
    """
    now_date = datetime.utcnow().date()
    cal_dict: dict[str, Any] = {}
    try:
        raw_cal: Any = ticker_obj.calendar
        if isinstance(raw_cal, dict):
            cal_dict = raw_cal
        elif isinstance(raw_cal, pd.DataFrame) and not raw_cal.empty:
            for idx in list(raw_cal.index):
                cal_dict[str(idx)] = raw_cal.loc[idx].iloc[0]
    except Exception:
        cal_dict = {}

    raw_candidates: list[tuple[datetime, str, str]] = []

    earnings_dt = (
        _parse_event_datetime(cal_dict.get("Earnings Date"))
        or _parse_event_datetime(info.get("earningsTimestamp"))
        or _parse_event_datetime(info.get("earningsTimestampStart"))
    )
    if earnings_dt and earnings_dt.date() >= (now_date - timedelta(days=2)):
        is_confirmed = bool(info.get("isEarningsDateEstimate") is False)
        raw_candidates.append(
            (
                earnings_dt,
                "Presentación de Resultados (Earnings)",
                "Confirmado" if is_confirmed else "Fecha estimada",
            )
        )

    ex_div_dt = (
        _parse_event_datetime(cal_dict.get("Ex-Dividend Date"))
        or _parse_event_datetime(info.get("exDividendDate"))
    )
    if ex_div_dt and ex_div_dt.date() >= now_date:
        raw_candidates.append(
            (ex_div_dt, "Fecha Ex-Dividendo", "Corte de derecho a dividendo")
        )

    div_pay_dt = (
        _parse_event_datetime(cal_dict.get("Dividend Date"))
        or _parse_event_datetime(info.get("dividendDate"))
    )
    if div_pay_dt and div_pay_dt.date() >= now_date:
        raw_candidates.append(
            (div_pay_dt, "Pago de Dividendo en Efectivo", "Confirmado")
        )

    raw_candidates.sort(key=lambda item: item[0])
    events_out: list[dict[str, str]] = []
    for dt_val, title_str, status_str in raw_candidates[:4]:
        events_out.append({
            "month": MESES_ES.get(dt_val.month, str(dt_val.month)),
            "day": f"{dt_val.day:02d}",
            "date_iso": dt_val.strftime("%Y-%m-%d"),
            "title": title_str,
            "status": status_str,
        })
    return events_out


def _parse_yf_news(raw_news: list[Any], translate_to_es: bool = True) -> list[dict[str, Any]]:
    news_list: list[dict[str, Any]] = []
    for n in raw_news[:6]:
        if not isinstance(n, dict):
            continue
        raw_content = n.get("content")
        content: dict[str, Any] = raw_content if isinstance(raw_content, dict) else n
        title = str(content.get("title") or n.get("title") or "").strip()

        raw_provider = content.get("provider")
        provider_obj: dict[str, Any] = raw_provider if isinstance(raw_provider, dict) else {}
        publisher = str(
            provider_obj.get("displayName")
            or content.get("publisher")
            or n.get("publisher")
            or ""
        ).strip()

        raw_canon = content.get("canonicalUrl")
        canon: dict[str, Any] = raw_canon if isinstance(raw_canon, dict) else {}
        raw_click = content.get("clickThroughUrl")
        click: dict[str, Any] = raw_click if isinstance(raw_click, dict) else {}
        link = str(
            canon.get("url")
            or click.get("url")
            or content.get("link")
            or n.get("link")
            or ""
        ).strip()

        pub_ts = int(n.get("providerPublishTime") or content.get("providerPublishTime") or 0)
        if pub_ts <= 0:
            pub_iso = content.get("pubDate") or content.get("displayTime")
            if isinstance(pub_iso, str) and pub_iso:
                try:
                    pub_ts = int(datetime.fromisoformat(pub_iso.replace("Z", "+00:00")).timestamp())
                except Exception:
                    pub_ts = 0

        if title and pub_ts > 0:
            final_title = _translate_headline_es(title) if translate_to_es else title
            news_list.append({
                "title": final_title,
                "publisher": publisher,
                "link": link,
                "providerPublishTime": pub_ts,
            })
        if len(news_list) >= 4:
            break
    return news_list


def _fetch_google_news_rss(
    ticker_upper: str, company_name: str = "", limit: int = 4
) -> list[dict[str, Any]]:
    """
    Respaldo de noticias financieras en español vía Google News RSS cuando Yahoo Finance
    devuelve lista vacía o sufre rate-limiting en producción.
    """
    clean_co = re.sub(
        r"\b(inc|corp|corporation|ltd|plc|co|company|holdings|group|sa|nv)\b\.?",
        "",
        company_name or "",
        flags=re.IGNORECASE,
    ).strip(" ,.-")

    search_term = f'"{ticker_upper}" "{clean_co}"' if clean_co else f'"{ticker_upper}" acciones bolsa'
    encoded_q = urllib.parse.quote(search_term)

    feeds = [
        (f"https://news.google.com/rss/search?q={encoded_q}&hl=es-419&gl=AR&ceid=AR:es-419", False),
        (f"https://news.google.com/rss/search?q={urllib.parse.quote(ticker_upper + ' stock')}&hl=en-US&gl=US&ceid=US:en", True),
    ]

    collected: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    for feed_url, needs_translation in feeds:
        if len(collected) >= limit:
            break
        try:
            req = urllib.request.Request(feed_url, headers=WEB_HEADERS)
            with urllib.request.urlopen(req, timeout=6) as resp:
                xml_bytes = resp.read()
            root = ET.fromstring(xml_bytes)
        except Exception:
            continue

        for item in root.findall(".//item"):
            raw_title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date_str = (item.findtext("pubDate") or "").strip()
            source_el = item.find("source")
            publisher = (source_el.text or "").strip() if source_el is not None else "Google News"

            if " - " in raw_title:
                parts = raw_title.rsplit(" - ", 1)
                raw_title = parts[0].strip()
                if not publisher or publisher == "Google News":
                    publisher = parts[1].strip()

            if not raw_title or raw_title.lower() in seen_titles:
                continue
            seen_titles.add(raw_title.lower())

            pub_ts = 0
            if pub_date_str:
                try:
                    pub_ts = int(parsedate_to_datetime(pub_date_str).timestamp())
                except Exception:
                    pub_ts = int(datetime.utcnow().timestamp())
            else:
                pub_ts = int(datetime.utcnow().timestamp())

            final_title = _translate_headline_es(raw_title) if needs_translation else raw_title
            collected.append({
                "title": final_title,
                "publisher": publisher,
                "link": link,
                "providerPublishTime": pub_ts,
            })
            if len(collected) >= limit:
                break

    return collected


def _lookup_fx_multiplier(from_curr: str, to_curr: str = "USD") -> float:
    """
    Consulta el tipo de cambio spot `{FROM}{TO}=X` (ej. ARSUSD=X, BRLUSD=X)
    con respaldo inverso `1 / {TO}{FROM}=X` y historial de 5 días.
    """
    src = (from_curr or "USD").strip().upper()
    dst = (to_curr or "USD").strip().upper()
    if not src or not dst or src == dst:
        return 1.0

    # 1. Par directo (ej. ARSUSD=X)
    try:
        tk_dir = yf.Ticker(f"{src}{dst}=X")
        rate = float(getattr(tk_dir.fast_info, "last_price", 0.0) or 0.0)
        if rate > 0:
            return rate
        hist = tk_dir.history(period="5d", interval="1d")
        if hist is not None and not hist.empty and "Close" in hist.columns:
            closes = hist["Close"].dropna()
            if len(closes) >= 1 and float(closes.iloc[-1]) > 0:
                return float(closes.iloc[-1])
    except Exception:
        pass

    # 2. Par inverso (ej. USDARS=X -> 1 / rate)
    try:
        tk_inv = yf.Ticker(f"{dst}{src}=X")
        inv_rate = float(getattr(tk_inv.fast_info, "last_price", 0.0) or 0.0)
        if inv_rate > 0:
            return 1.0 / inv_rate
        hist_inv = tk_inv.history(period="5d", interval="1d")
        if hist_inv is not None and not hist_inv.empty and "Close" in hist_inv.columns:
            closes_inv = hist_inv["Close"].dropna()
            if len(closes_inv) >= 1 and float(closes_inv.iloc[-1]) > 0:
                return 1.0 / float(closes_inv.iloc[-1])
    except Exception:
        pass

    return 1.0


def _resolve_fx_rate_to_trade_currency(info: dict[str, Any], sec_currency: str = "USD") -> float:
    """
    Si `financialCurrency` (Yahoo) o `sec_currency` (moneda detectada en SEC XBRL, ej. ARS, BRL)
    difiere de `currency` (moneda de cotización, ej. USD), devuelve el multiplicador actualizado
    para convertir magnitudes contables a la moneda de cotización.
    """
    trade_curr = str(info.get("currency") or "USD").upper()
    fin_curr = str(info.get("financialCurrency") or sec_currency or trade_curr).upper()
    if not fin_curr or fin_curr == trade_curr:
        return 1.0
    return _lookup_fx_multiplier(fin_curr, trade_curr)


def _df_to_clean_dict(df: Any) -> dict[str, dict[str, Any]]:
    """
    Convierte un DataFrame de yfinance (revenue_estimate, earnings_estimate, growth_estimates)
    a un diccionario JSON-serializable libre de NaN/Inf.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {}

    result: dict[str, dict[str, Any]] = {}
    for idx, row in df.iterrows():
        period_key = str(idx)
        row_dict: dict[str, Any] = {}
        for col in df.columns:
            raw_val = row[col]
            if raw_val is None or (isinstance(raw_val, float) and (math.isnan(raw_val) or math.isinf(raw_val))):
                row_dict[str(col)] = None
            elif isinstance(raw_val, (int, float)):
                row_dict[str(col)] = round(float(raw_val), 4)
            else:
                row_dict[str(col)] = str(raw_val)
        result[period_key] = row_dict
    return result


def _fetch_sec_submissions_json(cik: str | None) -> dict[str, Any]:
    """Descarga el índice oficial de presentaciones y metadatos corporativos desde SEC EDGAR."""
    if not cik:
        return {}
    cik_padded = str(cik).strip().zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    try:
        req = urllib.request.Request(url, headers=SEC_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _fetch_sec_8k_item_202(cik: str | None) -> list[dict[str, Any]]:
    """
    Consulta el índice público de presentaciones de la SEC (submissions/CIK.json)
    para extraer los últimos formularios 8-K con Ítem 2.02 (resultados trimestrales y guidance).
    """
    data = _fetch_sec_submissions_json(cik)
    if not data:
        return []

    cik_padded = str(cik).strip().zfill(10)
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    items_list = recent.get("items", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    cik_int = str(int(cik_padded))
    filings_202: list[dict[str, Any]] = []

    for i, form in enumerate(forms):
        if form in ("8-K", "8-K/A"):
            raw_items = items_list[i] if i < len(items_list) else ""
            items_str = ",".join(raw_items) if isinstance(raw_items, list) else str(raw_items)
            if "2.02" in items_str:
                acc_no = accessions[i] if i < len(accessions) else ""
                acc_clean = acc_no.replace("-", "")
                doc_name = primary_docs[i] if i < len(primary_docs) else ""
                sec_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{doc_name}"
                    if (acc_clean and doc_name)
                    else ""
                )
                filings_202.append({
                    "form": form,
                    "filing_date": dates[i] if i < len(dates) else "",
                    "report_date": report_dates[i] if i < len(report_dates) else "",
                    "items": items_str,
                    "url": sec_url,
                })
                if len(filings_202) >= 3:
                    break

    return filings_202


def _fetch_wikipedia_summary_es(company_name: str, ticker_upper: str) -> str:
    """
    Obtiene una descripción enciclopédica de la empresa desde Wikipedia (ES primario,
    EN traducido al español como respaldo) cuando Yahoo Finance bloquea `.info`.
    """
    clean_name = re.sub(
        r"\b(inc|incorporated|corp|corporation|ltd|limited|plc|co|company|holdings|group|se|nv|sa|ag)\b\.?",
        "",
        company_name or "",
        flags=re.IGNORECASE,
    ).strip(" ,.-")
    if not clean_name or clean_name.upper() == ticker_upper:
        return ""

    candidates = [clean_name]
    if company_name and company_name.strip() != clean_name:
        candidates.append(company_name.strip())

    tokens = [t.lower() for t in re.split(r"\W+", clean_name) if len(t) >= 3]

    # 1. Wikipedia en Español
    for cand in candidates:
        slug = urllib.parse.quote(cand.replace(" ", "_"))
        url_es = f"https://es.wikipedia.org/api/rest_v1/page/summary/{slug}"
        try:
            req = urllib.request.Request(url_es, headers=WEB_HEADERS)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("type") == "standard":
                extract = str(data.get("extract") or "").strip()
                extract_low = extract.lower()
                if len(extract) >= 90 and (not tokens or any(tok in extract_low for tok in tokens)):
                    return extract
        except Exception:
            continue

    # 2. Wikipedia en Inglés -> traducida al español
    for cand in candidates:
        slug = urllib.parse.quote(cand.replace(" ", "_"))
        url_en = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
        try:
            req = urllib.request.Request(url_en, headers=WEB_HEADERS)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("type") == "standard":
                extract_en = str(data.get("extract") or "").strip()
                extract_low = extract_en.lower()
                if len(extract_en) >= 90 and (not tokens or any(tok in extract_low for tok in tokens)):
                    translated, ok = _translate_to_spanish(extract_en, ticker_upper)
                    if ok and translated:
                        return translated
        except Exception:
            continue

    return ""


def _extract_1y_market_fallbacks(ticker_obj: yf.Ticker) -> dict[str, float | None]:
    """
    Extrae máximo/mínimo de 52 semanas y volumen promedio de 3 meses desde `history(period="1y")`
    para cubrir vacíos cuando Yahoo bloquea `.info`.
    """
    try:
        hist = ticker_obj.history(period="1y", interval="1d", auto_adjust=False)
        if hist is None or hist.empty:
            return {}
        high_52w = float(hist["High"].dropna().max()) if "High" in hist.columns and not hist["High"].dropna().empty else None
        low_52w = float(hist["Low"].dropna().min()) if "Low" in hist.columns and not hist["Low"].dropna().empty else None
        avg_vol_3m_mm: float | None = None
        if "Volume" in hist.columns:
            vols = hist["Volume"].dropna().tail(63)
            if len(vols) > 0:
                avg_vol_3m_mm = round(float(vols.mean()) / 1_000_000.0, 2)
        return {
            "high_52w": round(high_52w, 2) if high_52w and high_52w > 0 else None,
            "low_52w": round(low_52w, 2) if low_52w and low_52w > 0 else None,
            "avg_volume_3m_mm": avg_vol_3m_mm,
        }
    except Exception:
        return {}


def _extract_sec_fundamental_fallbacks(ticker_upper: str, db: Session) -> dict[str, Any]:
    """
    Calcula métricas contables LTM/FY desde SEC EDGAR (`CompanyData` + `financial_parser`),
    detectando automáticamente la moneda original del reporte (`ARS`, `BRL`, `USD`, etc.) y
    convirtiendo todas las cifras monetarias a `USD` para que sean comparables con la cotización.
    """
    try:
        from app.services.company_service import get_raw_financials
        from app.services.financial_parser import extract_annual_metrics, detect_reporting_currency

        raw_data = get_raw_financials(ticker_upper, db)
        rows = extract_annual_metrics(raw_data)
        reporting_currency = detect_reporting_currency(raw_data)
    except Exception:
        return {}

    if not rows:
        return {}

    sec_fx_to_usd = _lookup_fx_multiplier(reporting_currency, "USD")

    year_keys = sorted(
        k
        for k in rows[0].keys()
        if k not in ("Categoría", "Métrica", "is_pct", "is_sub", "is_header") and str(k).isdigit()
    )
    if not year_keys:
        return {}

    by_metric: dict[str, dict[str, Any]] = {}
    for r in rows:
        if not r.get("is_header"):
            by_metric[str(r.get("Métrica") or "").strip()] = r

    active_years = [
        y
        for y in year_keys
        if any(
            isinstance(by_metric.get(m, {}).get(y), (int, float))
            and float(by_metric[m][y]) != 0.0
            for m in ("Ingresos Totales", "Total activo", "Beneficio Neto", "Patrimonio neto")
        )
    ]
    if not active_years:
        return {}

    latest_yr = active_years[-1]
    prev_yr = active_years[-2] if len(active_years) >= 2 else None

    def _val_raw(metric_name: str, yr: str | None) -> float | None:
        if not yr:
            return None
        row = by_metric.get(metric_name)
        if not row:
            return None
        v = row.get(yr)
        if isinstance(v, (int, float)) and not math.isnan(float(v)) and not math.isinf(float(v)):
            return float(v)
        return None

    def _val_usd(metric_name: str, yr: str | None) -> float | None:
        raw_v = _val_raw(metric_name, yr)
        return raw_v * sec_fx_to_usd if raw_v is not None else None

    rev_curr = _val_usd("Ingresos Totales", latest_yr)
    rev_prev = _val_usd("Ingresos Totales", prev_yr)
    gp_curr = _val_usd("Beneficio Bruto", latest_yr)
    ebit_curr = _val_usd("Beneficio Operativo", latest_yr)
    da_curr = _val_usd("Depreciación y Amortización", latest_yr)
    ebt_curr = _val_usd("Beneficio antes de Impuestos", latest_yr)
    tax_curr = _val_usd("Gasto por Impuesto a las Ganancias", latest_yr)
    ni_curr = _val_usd("Beneficio Neto", latest_yr)
    ni_prev = _val_usd("Beneficio Neto", prev_yr)

    shares_mm = None
    for sy in reversed(active_years):
        s_cand = _val_raw("Acciones en Circulación (Diluidas)", sy) or _val_raw(
            "Acciones en Circulación (Básicas)", sy
        )
        if s_cand is not None and s_cand > 0:
            shares_mm = s_cand
            break

    cash_raw_val = _val_usd("Efectivo y equivalentes", latest_yr)
    st_inv_val = _val_usd("Inversiones a corto plazo", latest_yr)
    has_cash = (cash_raw_val is not None and cash_raw_val != 0.0) or (st_inv_val is not None and st_inv_val != 0.0)
    cash_mm = (cash_raw_val or 0.0) + (st_inv_val or 0.0)

    st_debt_val = _val_usd("Deuda a corto plazo", latest_yr)
    lt_debt_val = _val_usd("Deuda a largo plazo", latest_yr)
    has_debt = (st_debt_val is not None and st_debt_val != 0.0) or (lt_debt_val is not None and lt_debt_val != 0.0)
    debt_mm = (st_debt_val or 0.0) + (lt_debt_val or 0.0)

    equity_mm = _val_usd("Patrimonio neto", latest_yr)
    assets_mm = _val_usd("Total activo", latest_yr)
    ocf_mm = _val_usd("Efectivo de Operaciones (CFO)", latest_yr)
    capex_raw = _val_usd("Gastos de capital (CapEx)", latest_yr)
    capex_mm = abs(capex_raw) if capex_raw is not None else None
    fcf_mm = _val_usd("Flujo de caja libre (FCF)", latest_yr)
    if (fcf_mm is None or fcf_mm == 0.0) and ocf_mm is not None and capex_mm is not None:
        fcf_mm = round(ocf_mm - capex_mm, 2)

    div_raw = _val_usd("Pago de dividendos", latest_yr)
    div_paid_mm = abs(div_raw) if (div_raw is not None and div_raw != 0.0) else None

    ebitda_mm: float | None = None
    if ebit_curr is not None and da_curr is not None:
        ebitda_mm = round(ebit_curr + abs(da_curr), 2)
    elif ebit_curr is not None:
        ebitda_mm = round(ebit_curr, 2)

    rev_growth_pct: float | None = None
    if rev_curr is not None and rev_prev is not None and abs(rev_prev) > 0 and rev_curr != 0.0:
        rev_growth_pct = round(((rev_curr - rev_prev) / abs(rev_prev)) * 100.0, 1)

    ni_growth_pct: float | None = None
    if ni_curr is not None and ni_prev is not None and abs(ni_prev) > 0 and ni_curr != 0.0:
        ni_growth_pct = round(((ni_curr - ni_prev) / abs(ni_prev)) * 100.0, 1)

    eff_tax = 0.21
    if ebt_curr is not None and ebt_curr > 0 and tax_curr is not None and tax_curr >= 0:
        eff_tax = min(max(tax_curr / ebt_curr, 0.0), 0.45)

    company_row = db.query(CompanyData).filter(CompanyData.ticker == ticker_upper).first()
    sic_desc = ""
    entity_name = ""
    if company_row is not None and isinstance(company_row.raw_facts, dict):
        sic_desc = str(company_row.raw_facts.get("sicDescription") or "")
        entity_name = str(company_row.raw_facts.get("entityName") or "")

    return {
        "fiscal_year": latest_yr,
        "reporting_currency": reporting_currency,
        "sec_fx_to_usd": sec_fx_to_usd,
        "entity_name": entity_name,
        "sic_description": sic_desc,
        "shares_out_mm": round(shares_mm, 2) if shares_mm is not None else None,
        "total_cash_mm": round(cash_mm, 2) if has_cash else None,
        "total_debt_mm": round(debt_mm, 2) if has_debt else None,
        "revenue_mm": round(rev_curr, 2) if (rev_curr is not None and rev_curr != 0.0) else None,
        "gross_profit_mm": round(gp_curr, 2) if (gp_curr is not None and gp_curr != 0.0) else None,
        "ebit_mm": round(ebit_curr, 2) if (ebit_curr is not None and ebit_curr != 0.0) else None,
        "ebitda_mm": ebitda_mm if (ebitda_mm is not None and ebitda_mm != 0.0) else None,
        "net_income_mm": round(ni_curr, 2) if (ni_curr is not None and ni_curr != 0.0) else None,
        "book_equity_mm": round(equity_mm, 2) if (equity_mm is not None and equity_mm != 0.0) else None,
        "total_assets_mm": round(assets_mm, 2) if (assets_mm is not None and assets_mm != 0.0) else None,
        "ocf_ltm_mm": round(ocf_mm, 2) if (ocf_mm is not None and ocf_mm != 0.0) else None,
        "capex_ltm_mm": round(capex_mm, 2) if capex_mm is not None else None,
        "fcf_ltm_mm": round(fcf_mm, 2) if (fcf_mm is not None and fcf_mm != 0.0) else None,
        "dividends_paid_mm": round(div_paid_mm, 2) if div_paid_mm is not None else None,
        "revenue_growth_yoy_pct": rev_growth_pct,
        "earnings_growth_yoy_pct": ni_growth_pct,
        "effective_tax_rate": round(eff_tax, 4),
    }


def _extract_ltm_cashflow_metrics(
    ticker_obj: yf.Ticker, info: dict[str, Any], fx_rate: float
) -> dict[str, Any]:
    ocf_raw: float | None = None
    capex_raw: float | None = None

    ocf_keys = (
        "Operating Cash Flow",
        "Cash Flow From Continuing Operating Activities",
        "Total Cash From Operating Activities",
    )
    capex_keys = (
        "Capital Expenditure",
        "Capital Expenditures",
        "Purchase Of Property Plant And Equipment",
    )

    def _sum_first_matching_row(df: Any, keys: tuple[str, ...], max_cols: int) -> float | None:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return None
        idx_map = {str(i).strip().lower(): i for i in df.index}
        for k in keys:
            orig_idx = idx_map.get(k.lower())
            if orig_idx is not None:
                series = pd.to_numeric(df.loc[orig_idx].iloc[:max_cols], errors="coerce").dropna()
                if len(series) >= max_cols:
                    return float(series.sum())
        return None

    try:
        q_cf = ticker_obj.quarterly_cashflow
        ocf_raw = _sum_first_matching_row(q_cf, ocf_keys, 4)
        capex_raw = _sum_first_matching_row(q_cf, capex_keys, 4)
    except Exception:
        pass

    if ocf_raw is None or capex_raw is None:
        try:
            a_cf = ticker_obj.cashflow
            if ocf_raw is None:
                ocf_raw = _sum_first_matching_row(a_cf, ocf_keys, 1)
            if capex_raw is None:
                capex_raw = _sum_first_matching_row(a_cf, capex_keys, 1)
        except Exception:
            pass

    info_ocf_mm = _to_mm(info.get("operatingCashflow"), fx_rate)
    info_fcf_mm = _to_mm(info.get("freeCashflow"), fx_rate)

    effective_cf_fx = fx_rate
    if ocf_raw is not None and info_ocf_mm is not None and fx_rate != 1.0 and abs(info_ocf_mm) > 0:
        ocf_unconverted_mm = abs(ocf_raw) / 1_000_000.0
        ocf_converted_mm = ocf_unconverted_mm * fx_rate
        if abs(ocf_unconverted_mm - abs(info_ocf_mm)) < abs(ocf_converted_mm - abs(info_ocf_mm)):
            effective_cf_fx = 1.0

    ocf_mm = _to_mm(ocf_raw, effective_cf_fx) if ocf_raw is not None else info_ocf_mm
    capex_mm = round(abs(_to_mm(capex_raw, effective_cf_fx) or 0.0), 2) if capex_raw is not None else None

    fcf_mm: float | None = None
    if ocf_mm is not None and capex_mm is not None:
        fcf_mm = round(ocf_mm - capex_mm, 2)
    else:
        fcf_mm = info_fcf_mm

    return {
        "schema_version": CF_LTM_SCHEMA_VERSION,
        "ocf_ltm_mm": ocf_mm,
        "capex_ltm_mm": capex_mm,
        "fcf_ltm_mm": fcf_mm,
    }


def get_cached_market_snapshot(ticker_symbol: str, db: Session) -> dict[str, Any]:
    """
    Obtiene datos de mercado (precio, cambio, acciones, deuda neta, fx_rate, cf_ltm, noticias,
    eventos próximos, respaldo fundamental SEC EDGAR e info) desde Neon usando upsert atómico.
    """
    ticker_upper = ticker_symbol.upper()
    now = datetime.utcnow()

    cached_row = (
        db.query(CompanyMarketCache)
        .filter(CompanyMarketCache.ticker == ticker_upper)
        .first()
    )

    if cached_row is not None:
        updated_at: Any = cached_row.last_updated
        cached_payload: Any = cached_row.market_data
        if isinstance(updated_at, datetime) and isinstance(cached_payload, dict):
            cf_block = cached_payload.get("cf_ltm")
            has_valid_cf = isinstance(cf_block, dict) and cf_block.get("schema_version") == CF_LTM_SCHEMA_VERSION
            cached_price = float(cached_payload.get("price") or 0.0)
            cached_info = cached_payload.get("info")
            has_info = isinstance(cached_info, dict) and len(cached_info) > 0
            has_sec_fb = isinstance(cached_payload.get("sec_fundamentals"), dict) and len(cached_payload["sec_fundamentals"]) > 0
            if (
                cached_price > 0
                and (has_info or has_sec_fb)
                and (now - updated_at) < MARKET_CACHE_TTL
                and "fx_rate" in cached_payload
                and has_valid_cf
            ):
                return cached_payload

    ticker = yf.Ticker(ticker_upper)
    try:
        info: dict[str, Any] = ticker.info or {}
    except Exception:
        info = {}

    price = float(
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose")
        or 0.0
    )
    prev_close = float(info.get("previousClose") or price)

    if price <= 0.0:
        try:
            fi = ticker.fast_info
            price = float(getattr(fi, "last_price", 0.0) or 0.0)
            prev_close = float(getattr(fi, "previous_close", 0.0) or price)
        except Exception:
            pass

    if price <= 0.0:
        try:
            hist_5d = ticker.history(period="5d", interval="1d", auto_adjust=False)
            if hist_5d is not None and not hist_5d.empty and "Close" in hist_5d.columns:
                closes = hist_5d["Close"].dropna()
                if len(closes) >= 1:
                    price = float(closes.iloc[-1])
                    prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else price
        except Exception:
            pass

    if price <= 0.0 and cached_row is not None and isinstance(cached_row.market_data, dict):
        if float(cached_row.market_data.get("price") or 0.0) > 0.0:
            return cached_row.market_data

    change = price - prev_close if prev_close > 0 else 0.0
    change_pct = (change / prev_close) * 100 if prev_close > 0 else 0.0

    sec_fundamentals = _extract_sec_fundamental_fallbacks(ticker_upper, db)
    sec_rep_curr = str(
        sec_fundamentals.get("reporting_currency")
        or info.get("financialCurrency")
        or "USD"
    ).upper()
    fx_rate = _resolve_fx_rate_to_trade_currency(info, sec_currency=sec_rep_curr)
    market_1y_fallback = _extract_1y_market_fallbacks(ticker) if not info else {}
    upcoming_events = _extract_upcoming_events(ticker, info)

    shares_raw = info.get("sharesOutstanding")
    if shares_raw:
        shares_mm = float(shares_raw) / 1_000_000.0
    else:
        shares_mm = float(sec_fundamentals.get("shares_out_mm") or 0.0)

    if info.get("totalDebt") is not None and info.get("totalCash") is not None:
        total_debt_raw = float(info.get("totalDebt") or 0) * fx_rate
        total_cash_raw = float(info.get("totalCash") or 0) * fx_rate
        net_debt_mm = (total_debt_raw - total_cash_raw) / 1_000_000.0
    elif sec_fundamentals.get("total_debt_mm") is not None and sec_fundamentals.get("total_cash_mm") is not None:
        net_debt_mm = float(sec_fundamentals["total_debt_mm"]) - float(sec_fundamentals["total_cash_mm"])
    else:
        net_debt_mm = 0.0

    cf_ltm = _extract_ltm_cashflow_metrics(ticker, info, fx_rate)
    if cf_ltm.get("ocf_ltm_mm") is None and sec_fundamentals.get("ocf_ltm_mm") is not None:
        cf_ltm["ocf_ltm_mm"] = sec_fundamentals["ocf_ltm_mm"]
    if cf_ltm.get("capex_ltm_mm") is None and sec_fundamentals.get("capex_ltm_mm") is not None:
        cf_ltm["capex_ltm_mm"] = sec_fundamentals["capex_ltm_mm"]
    if cf_ltm.get("fcf_ltm_mm") is None and sec_fundamentals.get("fcf_ltm_mm") is not None:
        cf_ltm["fcf_ltm_mm"] = sec_fundamentals["fcf_ltm_mm"]

    try:
        raw_news = ticker.news or []
    except Exception:
        raw_news = []
    news_list = _parse_yf_news(raw_news, translate_to_es=True)
    if len(news_list) < 2:
        co_label = str(
            info.get("longName")
            or info.get("shortName")
            or sec_fundamentals.get("entity_name")
            or ""
        )
        rss_news = _fetch_google_news_rss(ticker_upper, co_label, limit=4)
        existing_titles = {item["title"].lower() for item in news_list}
        for rn in rss_news:
            if rn["title"].lower() not in existing_titles:
                news_list.append(rn)
                existing_titles.add(rn["title"].lower())
            if len(news_list) >= 4:
                break

    snapshot: dict[str, Any] = {
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "fx_rate": fx_rate,
        "reporting_currency": sec_rep_curr,
        "shares_mm": shares_mm,
        "net_debt_mm": net_debt_mm,
        "news": news_list,
        "upcoming_events": upcoming_events,
        "info": info,
        "cf_ltm": cf_ltm,
        "sec_fundamentals": sec_fundamentals,
        "market_1y_fallback": market_1y_fallback,
    }

    if price > 0.0:
        try:
            _upsert_by_ticker(
                db,
                CompanyMarketCache,
                ticker_upper,
                {"market_data": snapshot, "last_updated": now},
            )
        except Exception:
            db.rollback()

    return snapshot


def get_cached_estimates_and_guidance(ticker_symbol: str, db: Session) -> dict[str, Any]:
    ticker_upper = ticker_symbol.upper()
    now = datetime.utcnow()

    cached_row = (
        db.query(CompanyEstimatesCache)
        .filter(CompanyEstimatesCache.ticker == ticker_upper)
        .first()
    )

    if cached_row is not None:
        updated_at: Any = cached_row.last_updated
        cached_payload: Any = cached_row.estimates_data
        if isinstance(updated_at, datetime) and isinstance(cached_payload, dict):
            if (now - updated_at) < ESTIMATES_CACHE_TTL:
                return cached_payload

    snapshot = get_cached_market_snapshot(ticker_upper, db)
    info: dict[str, Any] = snapshot.get("info", {})

    company_row = db.query(CompanyData).filter(CompanyData.ticker == ticker_upper).first()
    cik_str = str(company_row.cik) if (company_row is not None and company_row.cik is not None) else None
    sic_code: str | None = None
    sic_description: str | None = None
    if company_row is not None and isinstance(company_row.raw_facts, dict):
        raw_sic = company_row.raw_facts.get("sic")
        if raw_sic is not None:
            sic_code = str(raw_sic)
        sic_description = company_row.raw_facts.get("sicDescription")

    tk = yf.Ticker(ticker_upper)
    try:
        rev_est = _df_to_clean_dict(tk.revenue_estimate)
    except Exception:
        rev_est = {}

    try:
        eps_est = _df_to_clean_dict(tk.earnings_estimate)
    except Exception:
        eps_est = {}

    try:
        growth_est = _df_to_clean_dict(tk.growth_estimates)
    except Exception:
        growth_est = {}

    sec_8k_filings = _fetch_sec_8k_item_202(cik_str)

    payload: dict[str, Any] = {
        "ticker": ticker_upper,
        "classification": {
            "sector": info.get("sector") or "",
            "industry": info.get("industry") or sic_description or "",
            "sic": sic_code,
            "sic_description": sic_description or "",
        },
        "consensus_summary": {
            "forward_eps": _to_float(info.get("forwardEps"), 2),
            "trailing_eps": _to_float(info.get("trailingEps"), 2),
            "forward_pe": _to_float(info.get("forwardPE"), 2),
            "revenue_growth_yoy_pct": _to_pct(info.get("revenueGrowth"), 2),
            "earnings_growth_yoy_pct": _to_pct(info.get("earningsGrowth"), 2),
            "target_mean_price": _to_float(info.get("targetMeanPrice"), 2),
            "target_low_price": _to_float(info.get("targetLowPrice"), 2),
            "target_high_price": _to_float(info.get("targetHighPrice"), 2),
            "analyst_count": info.get("numberOfAnalystOpinions"),
        },
        "revenue_estimate": rev_est,
        "earnings_estimate": eps_est,
        "growth_estimates": growth_est,
        "sec_8k_guidance_filings": sec_8k_filings,
    }

    try:
        _upsert_by_ticker(
            db,
            CompanyEstimatesCache,
            ticker_upper,
            {"estimates_data": payload, "last_updated": now},
        )
    except Exception:
        db.rollback()

    return payload


def _build_summary_metrics(
    info: dict[str, Any],
    price: float,
    fx_rate: float = 1.0,
    cf_ltm: dict[str, float | None] | None = None,
    sec_fundamentals: dict[str, Any] | None = None,
    market_1y_fallback: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    sec = sec_fundamentals if isinstance(sec_fundamentals, dict) else {}
    mkt_1y = market_1y_fallback if isinstance(market_1y_fallback, dict) else {}

    shares_mm = _to_mm(info.get("sharesOutstanding"), 1.0)
    if shares_mm is None or shares_mm <= 0:
        shares_mm = _to_float(sec.get("shares_out_mm"), 2)

    float_shares_mm = _to_mm(info.get("floatShares"), 1.0)

    market_cap_mm: float | None = None
    if shares_mm is not None and shares_mm > 0 and price > 0:
        market_cap_mm = round(shares_mm * price, 2)
    else:
        market_cap_mm = _to_mm(info.get("marketCap"), 1.0)

    total_debt_mm = _to_mm(info.get("totalDebt"), fx_rate)
    if total_debt_mm is None:
        total_debt_mm = _to_float(sec.get("total_debt_mm"), 2)

    total_cash_mm = _to_mm(info.get("totalCash"), fx_rate)
    if total_cash_mm is None:
        total_cash_mm = _to_float(sec.get("total_cash_mm"), 2)

    net_debt_mm: float | None = None
    if total_debt_mm is not None and total_cash_mm is not None:
        net_debt_mm = round(total_debt_mm - total_cash_mm, 2)

    ev_mm: float | None = None
    if market_cap_mm is not None and net_debt_mm is not None:
        ev_mm = round(market_cap_mm + net_debt_mm, 2)
    else:
        ev_mm = _to_mm(info.get("enterpriseValue"), 1.0)

    ebitda_mm = _to_mm(info.get("ebitda"), fx_rate)
    if ebitda_mm is None:
        ebitda_mm = _to_float(sec.get("ebitda_mm"), 2)

    revenue_mm = _to_mm(info.get("totalRevenue"), fx_rate)
    if revenue_mm is None:
        revenue_mm = _to_float(sec.get("revenue_mm"), 2)

    gross_profit_mm = _to_mm(info.get("grossProfits"), fx_rate)
    if gross_profit_mm is None:
        gross_profit_mm = _to_float(sec.get("gross_profit_mm"), 2)

    net_income_mm = _to_mm(info.get("netIncomeToCommon"), fx_rate)
    if net_income_mm is None:
        net_income_mm = _to_float(sec.get("net_income_mm"), 2)

    ebit_sec_mm = _to_float(sec.get("ebit_mm"), 2)
    book_equity_sec_mm = _to_float(sec.get("book_equity_mm"), 2)
    total_assets_sec_mm = _to_float(sec.get("total_assets_mm"), 2)
    dividends_sec_mm = _to_float(sec.get("dividends_paid_mm"), 2)

    fcf_mm = (
        cf_ltm.get("fcf_ltm_mm")
        if (cf_ltm and cf_ltm.get("fcf_ltm_mm") is not None)
        else _to_mm(info.get("freeCashflow"), fx_rate)
    )
    if fcf_mm is None:
        fcf_mm = _to_float(sec.get("fcf_ltm_mm"), 2)

    ocf_mm = (
        cf_ltm.get("ocf_ltm_mm")
        if (cf_ltm and cf_ltm.get("ocf_ltm_mm") is not None)
        else _to_mm(info.get("operatingCashflow"), fx_rate)
    )
    if ocf_mm is None:
        ocf_mm = _to_float(sec.get("ocf_ltm_mm"), 2)

    float_pct: float | None = None
    if float_shares_mm is not None and shares_mm is not None and shares_mm > 0:
        float_pct = round(min((float_shares_mm / shares_mm) * 100.0, 100.0), 1)

    net_debt_to_ebitda: float | None = None
    if net_debt_mm is not None and ebitda_mm is not None and ebitda_mm != 0:
        net_debt_to_ebitda = round(net_debt_mm / ebitda_mm, 2)

    ev_to_sales_ltm: float | None = None
    if ev_mm is not None and revenue_mm is not None and revenue_mm != 0:
        ev_to_sales_ltm = round(ev_mm / revenue_mm, 2)
    else:
        ev_to_sales_ltm = _to_float(info.get("enterpriseToRevenue"))

    ev_to_ebitda_ltm: float | None = None
    if ev_mm is not None and ebitda_mm is not None and ebitda_mm != 0:
        ev_to_ebitda_ltm = round(ev_mm / ebitda_mm, 2)
    else:
        ev_to_ebitda_ltm = _to_float(info.get("enterpriseToEbitda"))

    ev_to_gross_profit_ltm: float | None = None
    if ev_mm is not None and gross_profit_mm is not None and gross_profit_mm != 0:
        ev_to_gross_profit_ltm = round(ev_mm / gross_profit_mm, 2)

    pe_ltm = _to_float(info.get("trailingPE"))
    if pe_ltm is None and market_cap_mm is not None and net_income_mm is not None and net_income_mm > 0:
        pe_ltm = round(market_cap_mm / net_income_mm, 2)

    pe_ntm = _to_float(info.get("forwardPE"))
    if pe_ntm is None and price > 0:
        fwd_eps = _to_float(info.get("forwardEps"), 4)
        if fwd_eps is not None and fwd_eps != 0:
            pe_ntm = round(price / fwd_eps, 2)

    pb_ltm = _to_float(info.get("priceToBook"))
    if pb_ltm is None and market_cap_mm is not None and book_equity_sec_mm is not None and book_equity_sec_mm > 0:
        pb_ltm = round(market_cap_mm / book_equity_sec_mm, 2)

    p_to_fcf_ltm: float | None = None
    if market_cap_mm is not None and fcf_mm is not None and fcf_mm > 0:
        p_to_fcf_ltm = round(market_cap_mm / fcf_mm, 2)

    gross_margin_yf = _to_pct(info.get("grossMargins"), 1)
    if gross_margin_yf is None and gross_profit_mm is not None and revenue_mm is not None and revenue_mm != 0:
        gross_margin_yf = round((gross_profit_mm / revenue_mm) * 100.0, 1)

    ebit_margin_pct = _to_pct(info.get("operatingMargins"), 1)
    if ebit_margin_pct is None and ebit_sec_mm is not None and revenue_mm is not None and revenue_mm != 0:
        ebit_margin_pct = round((ebit_sec_mm / revenue_mm) * 100.0, 1)

    ebitda_margin_pct = _to_pct(info.get("ebitdaMargins"), 1)
    if ebitda_margin_pct is None and ebitda_mm is not None and revenue_mm is not None and revenue_mm != 0:
        ebitda_margin_pct = round((ebitda_mm / revenue_mm) * 100.0, 1)

    net_margin_pct = _to_pct(info.get("profitMargins"), 1)
    if net_margin_pct is None and net_income_mm is not None and revenue_mm is not None and revenue_mm != 0:
        net_margin_pct = round((net_income_mm / revenue_mm) * 100.0, 1)

    roa_pct = _to_pct(info.get("returnOnAssets"), 1)
    if roa_pct is None and net_income_mm is not None and total_assets_sec_mm is not None and total_assets_sec_mm > 0:
        roa_pct = round((net_income_mm / total_assets_sec_mm) * 100.0, 1)

    roe_pct = _to_pct(info.get("returnOnEquity"), 1)
    if roe_pct is None and net_income_mm is not None and book_equity_sec_mm is not None and book_equity_sec_mm > 0:
        roe_pct = round((net_income_mm / book_equity_sec_mm) * 100.0, 1)

    roic_pct: float | None = None
    if revenue_mm is not None and ebit_margin_pct is not None:
        ebit_val = ebit_sec_mm if ebit_sec_mm is not None else (revenue_mm * (ebit_margin_pct / 100.0))
        eff_tax = float(sec.get("effective_tax_rate") or 0.21)
        nopat_mm = ebit_val * (1.0 - eff_tax) if ebit_sec_mm is not None else ebit_val
        book_eq = book_equity_sec_mm
        if book_eq is None and market_cap_mm is not None and pb_ltm is not None and pb_ltm > 0:
            book_eq = market_cap_mm / pb_ltm
        if book_eq is not None and net_debt_mm is not None:
            invested_capital = book_eq + net_debt_mm
            if invested_capital > 0:
                roic_pct = round((nopat_mm / invested_capital) * 100.0, 1)

    sector_str = str(info.get("sector") or sec.get("sic_description") or "").lower()
    is_bank_sector = any(k in sector_str for k in ("financial", "bank", "depository", "insurance"))
    gross_margin_out = None if is_bank_sector else gross_margin_yf
    roic_out = None if is_bank_sector else roic_pct

    raw_div_yield = info.get("dividendYield")
    div_yield_pct: float | None = None
    if raw_div_yield is not None:
        val_dy = float(raw_div_yield)
        div_yield_pct = round(val_dy if val_dy > 1 else val_dy * 100.0, 2)
    elif dividends_sec_mm is not None and market_cap_mm is not None and market_cap_mm > 0:
        div_yield_pct = round((dividends_sec_mm / market_cap_mm) * 100.0, 2)

    payout_ratio_pct = _to_pct(info.get("payoutRatio"), 1)
    if payout_ratio_pct is None and dividends_sec_mm is not None and net_income_mm is not None and net_income_mm > 0:
        payout_ratio_pct = round((dividends_sec_mm / net_income_mm) * 100.0, 1)

    rev_growth_yoy = _to_pct(info.get("revenueGrowth"), 1)
    if rev_growth_yoy is None:
        rev_growth_yoy = _to_float(sec.get("revenue_growth_yoy_pct"), 1)

    earn_growth_yoy = _to_pct(info.get("earningsGrowth"), 1)
    if earn_growth_yoy is None:
        earn_growth_yoy = _to_float(sec.get("earnings_growth_yoy_pct"), 1)

    high_52w = _to_float(info.get("fiftyTwoWeekHigh")) or _to_float(mkt_1y.get("high_52w"))
    low_52w = _to_float(info.get("fiftyTwoWeekLow")) or _to_float(mkt_1y.get("low_52w"))
    avg_vol_3m = _to_mm(info.get("averageVolume") or info.get("averageDailyVolume3Month"), 1.0)
    if avg_vol_3m is None:
        avg_vol_3m = _to_float(mkt_1y.get("avg_volume_3m_mm"), 2)

    return {
        "market_data": {
            "high_52w": high_52w,
            "low_52w": low_52w,
            "avg_volume_3m_mm": avg_vol_3m,
            "beta_5y": _to_float(info.get("beta")),
            "float_pct": float_pct,
        },
        "capital_structure": {
            "market_cap_mm": market_cap_mm,
            "enterprise_value_mm": ev_mm,
            "shares_out_mm": shares_mm,
            "net_debt_mm": net_debt_mm,
            "net_debt_to_ebitda": net_debt_to_ebitda,
        },
        "efficiency": {
            "gross_margin_pct": gross_margin_out,
            "ebit_margin_pct": ebit_margin_pct,
            "roa_pct": roa_pct,
            "roe_pct": roe_pct,
            "roic_pct": roic_out,
            "net_margin_pct": net_margin_pct,
        },
        "growth_cashflow": {
            "revenue_growth_yoy_pct": rev_growth_yoy,
            "earnings_growth_yoy_pct": earn_growth_yoy,
            "ebitda_margin_pct": ebitda_margin_pct,
            "ocf_ltm_mm": ocf_mm,
            "fcf_ltm_mm": fcf_mm,
            "total_cash_mm": total_cash_mm,
        },
        "valuation": {
            "target_price": _to_float(info.get("targetMeanPrice")),
            "ev_to_sales_ltm": ev_to_sales_ltm,
            "ev_to_ebitda_ltm": ev_to_ebitda_ltm,
            "ev_to_gross_profit_ltm": ev_to_gross_profit_ltm,
            "pe_ltm": pe_ltm,
            "pe_ntm": pe_ntm,
            "pb_ltm": pb_ltm,
            "p_to_fcf_ltm": p_to_fcf_ltm,
            "dividend_yield_pct": div_yield_pct,
            "payout_ratio_pct": payout_ratio_pct,
        },
    }


def get_company_profile(ticker_symbol: str, db: Session) -> dict:
    ticker_upper = ticker_symbol.upper()

    snapshot = get_cached_market_snapshot(ticker_upper, db)
    price = snapshot["price"]
    change = snapshot["change"]
    change_pct = snapshot["change_pct"]
    fx_rate = float(snapshot.get("fx_rate") or 1.0)
    news_list = snapshot["news"]
    upcoming_events = snapshot.get("upcoming_events") if isinstance(snapshot.get("upcoming_events"), list) else []
    raw_info = snapshot.get("info")
    info: dict[str, Any] = raw_info if isinstance(raw_info, dict) else {}
    raw_sec_fb = snapshot.get("sec_fundamentals")
    sec_fundamentals: dict[str, Any] = raw_sec_fb if isinstance(raw_sec_fb, dict) else {}
    raw_mkt_1y = snapshot.get("market_1y_fallback")
    market_1y_fallback: dict[str, float | None] = raw_mkt_1y if isinstance(raw_mkt_1y, dict) else {}

    profile_db = db.query(CompanyProfile).filter(CompanyProfile.ticker == ticker_upper).first()
    desc_str = str(profile_db.description or "").strip() if profile_db else ""
    is_synthetic_fallback = "es un emisor público registrado ante la sec" in desc_str.lower()
    needs_translation = bool(desc_str) and (desc_str.startswith("(Sin traducir)") or _looks_english(desc_str))

    if profile_db and desc_str and not needs_translation and not is_synthetic_fallback:
        name = str(profile_db.name)
        website = str(profile_db.website)
        translated_desc = desc_str
    else:
        if not info:
            try:
                fresh_info = yf.Ticker(ticker_upper).info or {}
                if isinstance(fresh_info, dict) and fresh_info:
                    info = fresh_info
            except Exception:
                pass

        sec_name = str(sec_fundamentals.get("entity_name") or "").strip()
        sec_sic_desc = str(sec_fundamentals.get("sic_description") or "").strip()
        sec_sic_code = ""
        sec_cik = ""
        company_row = db.query(CompanyData).filter(CompanyData.ticker == ticker_upper).first()
        if company_row is not None:
            if company_row.cik is not None:
                sec_cik = str(company_row.cik).strip().zfill(10)
            if isinstance(company_row.raw_facts, dict):
                if not sec_name:
                    sec_name = str(company_row.raw_facts.get("entityName") or "").strip()
                if not sec_sic_desc:
                    sec_sic_desc = str(company_row.raw_facts.get("sicDescription") or "").strip()
                if company_row.raw_facts.get("sic") is not None:
                    sec_sic_code = str(company_row.raw_facts.get("sic")).strip()

        sec_sub_meta: dict[str, Any] = {}
        if (not info or not sec_name) and sec_cik:
            sec_sub_meta = _fetch_sec_submissions_json(sec_cik)
            if not sec_name and sec_sub_meta.get("name"):
                sec_name = str(sec_sub_meta["name"]).strip()
            if not sec_sic_desc and sec_sub_meta.get("sicDescription"):
                sec_sic_desc = str(sec_sub_meta["sicDescription"]).strip()
            if not sec_sic_code and sec_sub_meta.get("sic"):
                sec_sic_code = str(sec_sub_meta["sic"]).strip()

        db_name = str(getattr(profile_db, "name", None) or "").strip() if profile_db else ""
        db_website = str(getattr(profile_db, "website", None) or "").strip() if profile_db else ""

        name = (
            info.get("longName")
            or info.get("shortName")
            or sec_name
            or db_name
            or ticker_upper
        )
        sec_website = str(
            sec_sub_meta.get("website") or sec_sub_meta.get("investorWebsite") or ""
        ).strip()
        if sec_website and not sec_website.startswith(("http://", "https://")):
            sec_website = f"https://{sec_website}"

        website = (
            info.get("website")
            or sec_website
            or db_website
        )

        raw_description = str(info.get("longBusinessSummary") or "").strip()
        if not raw_description and desc_str and not is_synthetic_fallback:
            raw_description = desc_str.removeprefix("(Sin traducir)").strip()

        translated_desc = ""
        persist_permanent = False

        if raw_description:
            translated_desc, ok = _translate_to_spanish(raw_description, ticker_upper)
            persist_permanent = ok or len(translated_desc) >= 60
        else:
            wiki_desc = _fetch_wikipedia_summary_es(str(name), ticker_upper)
            if wiki_desc:
                translated_desc = wiki_desc
                persist_permanent = True

        if persist_permanent and translated_desc:
            try:
                _upsert_by_ticker(
                    db,
                    CompanyProfile,
                    ticker_upper,
                    {"name": name, "website": website, "description": translated_desc},
                )
            except Exception:
                db.rollback()
        elif not translated_desc:
            exchanges = sec_sub_meta.get("exchanges") if isinstance(sec_sub_meta.get("exchanges"), list) else []
            exch_str = f" (cotiza en {', '.join(str(x) for x in exchanges[:2])})" if exchanges else ""
            sector_part = f" en el sector {sec_sic_desc}" if sec_sic_desc else ""
            sic_part = f" (código SIC {sec_sic_code})" if sec_sic_code else ""
            cik_part = f" · Registro SEC CIK {sec_cik}" if sec_cik else ""
            if sec_name or sec_sic_desc:
                translated_desc = (
                    f"{name} ({ticker_upper}) es un emisor público registrado ante la SEC{exch_str}{sector_part}{sic_part}.{cik_part}"
                )

    return {
        "name": name,
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "website": website,
        "description": translated_desc,
        "reporting_currency": str(
            sec_fundamentals.get("reporting_currency")
            or snapshot.get("reporting_currency")
            or info.get("financialCurrency")
            or "USD"
        ).upper(),
        "news": news_list,
        "upcoming_events": upcoming_events,
        "summary_metrics": _build_summary_metrics(
            info=info,
            price=price,
            fx_rate=fx_rate,
            cf_ltm=snapshot.get("cf_ltm"),
            sec_fundamentals=sec_fundamentals,
            market_1y_fallback=market_1y_fallback,
        ),
    }