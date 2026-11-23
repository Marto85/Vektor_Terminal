from datetime import datetime, timedelta
import json
import math
import re
from typing import Any
import urllib.request
import pandas as pd
import yfinance as yf
from deep_translator import GoogleTranslator, MyMemoryTranslator
from sqlalchemy.orm import Session
from app.models.database import (
    CompanyData,
    CompanyProfile,
    CompanyMarketCache,
    CompanyEstimatesCache,
)

MARKET_CACHE_TTL = timedelta(hours=4)
ESTIMATES_CACHE_TTL = timedelta(hours=24)
CF_LTM_SCHEMA_VERSION = 3
SEC_HEADERS = {"User-Agent": "MiTerminalFinanciera/1.0 (contacto@miterminal.local)"}


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
    Detecta si una descripción corporativa guardada sigue redactada en inglés
    para reintentar su traducción al español automáticamente.
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


def _parse_yf_news(raw_news: list[Any]) -> list[dict[str, Any]]:
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
            news_list.append({
                "title": title,
                "publisher": publisher,
                "link": link,
                "providerPublishTime": pub_ts,
            })
        if len(news_list) >= 4:
            break
    return news_list


def _resolve_fx_rate_to_trade_currency(info: dict[str, Any]) -> float:
    """
    Si `financialCurrency` (moneda de los estados contables, ej. BRL, ARS) difiere de
    `currency` (moneda de cotización, ej. USD), devuelve el tipo de cambio multiplicador
    actualizado desde Yahoo Finance (`{FIN}{TRADE}=X`) para convertir magnitudes contables
    a la moneda de cotización.
    """
    trade_curr = str(info.get("currency") or "USD").upper()
    fin_curr = str(info.get("financialCurrency") or trade_curr).upper()
    if not fin_curr or fin_curr == trade_curr:
        return 1.0

    try:
        fx_tk = yf.Ticker(f"{fin_curr}{trade_curr}=X")
        fx_info = fx_tk.fast_info
        rate = float(getattr(fx_info, "last_price", 0.0) or 0.0)
        if rate > 0:
            return rate
    except Exception:
        pass
    return 1.0


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


def _fetch_sec_8k_item_202(cik: str | None) -> list[dict[str, Any]]:
    """
    Consulta el índice público de presentaciones de la SEC (submissions/CIK.json)
    para extraer los últimos formularios 8-K con Ítem 2.02 (resultados trimestrales y guidance).
    """
    if not cik:
        return []

    cik_padded = str(cik).strip().zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"

    try:
        req = urllib.request.Request(url, headers=SEC_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

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


def _extract_ltm_cashflow_metrics(
    ticker_obj: yf.Ticker, info: dict[str, Any], fx_rate: float
) -> dict[str, Any]:
    """
    Calcula OCF LTM, CapEx LTM y FCF LTM (OCF - |CapEx|) sumando los últimos 4 trimestres
    de `quarterly_cashflow` (o el último año de `cashflow` anual).
    Incluye detección de escala cambiaria para ADRs (ej. BRL/ARS vs USD) para evitar doble
    conversión cuando `quarterly_cashflow` ya viene expresado en USD.
    """
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
    Obtiene datos de mercado (precio, cambio, acciones, deuda neta, fx_rate, cf_ltm, noticias e info)
    desde base de datos si tienen menos de 4 horas y precio válido; caso contrario consulta Yahoo Finance.
    Si un snapshot válido en caché tiene `info` vacío por un bloqueo previo, intenta rehidratarlo.
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
            if (
                cached_price > 0
                and has_info
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

    # Fallback a fast_info e historial diario si Yahoo bloquea .info en servidor
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

    # Si este intento falló por completo pero existe un snapshot previo con precio > 0, conservarlo
    if price <= 0.0 and cached_row is not None and isinstance(cached_row.market_data, dict):
        if float(cached_row.market_data.get("price") or 0.0) > 0.0:
            return cached_row.market_data

    change = price - prev_close if prev_close > 0 else 0.0
    change_pct = (change / prev_close) * 100 if prev_close > 0 else 0.0

    fx_rate = _resolve_fx_rate_to_trade_currency(info)
    shares_raw = info.get("sharesOutstanding") or 0
    total_debt_raw = (info.get("totalDebt") or 0) * fx_rate
    total_cash_raw = (info.get("totalCash") or 0) * fx_rate
    shares_mm = float(shares_raw) / 1_000_000.0
    net_debt_mm = (float(total_debt_raw) - float(total_cash_raw)) / 1_000_000.0
    cf_ltm = _extract_ltm_cashflow_metrics(ticker, info, fx_rate)

    try:
        raw_news = ticker.news or []
    except Exception:
        raw_news = []
    news_list = _parse_yf_news(raw_news)

    snapshot: dict[str, Any] = {
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "fx_rate": fx_rate,
        "shares_mm": shares_mm,
        "net_debt_mm": net_debt_mm,
        "news": news_list,
        "info": info,
        "cf_ltm": cf_ltm,
    }

    # Evitar persistir snapshots fallidos con precio 0
    if price > 0.0:
        if cached_row is not None:
            db.query(CompanyMarketCache).filter(
                CompanyMarketCache.ticker == ticker_upper
            ).update({
                "market_data": snapshot,
                "last_updated": now,
            })
        else:
            db.add(
                CompanyMarketCache(
                    ticker=ticker_upper,
                    market_data=snapshot,
                    last_updated=now,
                )
            )
        db.commit()

    return snapshot


def get_cached_estimates_and_guidance(ticker_symbol: str, db: Session) -> dict[str, Any]:
    """
    Obtiene y persiste en base de datos (`CompanyEstimatesCache`, TTL 24h):
    - Consenso de ingresos (`revenue_estimate`), BPA (`earnings_estimate`) y crecimiento (`growth_estimates`).
    - Clasificación sectorial (`sector`, `industry`, `sic`) para enrutamiento de modelos.
    - Últimos formularios SEC 8-K con Ítem 2.02 (comunicados de resultados y guidance).
    """
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
            "industry": info.get("industry") or "",
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

    if cached_row is not None:
        db.query(CompanyEstimatesCache).filter(
            CompanyEstimatesCache.ticker == ticker_upper
        ).update({
            "estimates_data": payload,
            "last_updated": now,
        })
    else:
        db.add(
            CompanyEstimatesCache(
                ticker=ticker_upper,
                estimates_data=payload,
                last_updated=now,
            )
        )

    db.commit()
    return payload


def _build_summary_metrics(
    info: dict[str, Any],
    price: float,
    fx_rate: float = 1.0,
    cf_ltm: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    """
    Construye las 4 secciones del panel derecho estilo TIKR en 2 columnas
    a partir del diccionario `info` ya cacheado, convirtiendo magnitudes
    contables a la moneda de cotización (USD) si `fx_rate != 1.0`.
    """
    shares_mm = _to_mm(info.get("sharesOutstanding"), 1.0)
    float_shares_mm = _to_mm(info.get("floatShares"), 1.0)

    market_cap_mm: float | None = None
    if shares_mm is not None and shares_mm > 0 and price > 0:
        market_cap_mm = round(shares_mm * price, 2)
    else:
        market_cap_mm = _to_mm(info.get("marketCap"), 1.0)

    total_debt_mm = _to_mm(info.get("totalDebt"), fx_rate)
    total_cash_mm = _to_mm(info.get("totalCash"), fx_rate)
    net_debt_mm: float | None = None
    if total_debt_mm is not None and total_cash_mm is not None:
        net_debt_mm = round(total_debt_mm - total_cash_mm, 2)

    ev_mm: float | None = None
    if market_cap_mm is not None and net_debt_mm is not None:
        ev_mm = round(market_cap_mm + net_debt_mm, 2)
    else:
        ev_mm = _to_mm(info.get("enterpriseValue"), 1.0)

    ebitda_mm = _to_mm(info.get("ebitda"), fx_rate)
    revenue_mm = _to_mm(info.get("totalRevenue"), fx_rate)
    gross_profit_mm = _to_mm(info.get("grossProfits"), fx_rate)
    net_income_mm = _to_mm(info.get("netIncomeToCommon"), fx_rate)
    fcf_mm = (
        cf_ltm.get("fcf_ltm_mm")
        if (cf_ltm and cf_ltm.get("fcf_ltm_mm") is not None)
        else _to_mm(info.get("freeCashflow"), fx_rate)
    )
    ocf_mm = (
        cf_ltm.get("ocf_ltm_mm")
        if (cf_ltm and cf_ltm.get("ocf_ltm_mm") is not None)
        else _to_mm(info.get("operatingCashflow"), fx_rate)
    )

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
    if pe_ltm is None and market_cap_mm is not None and net_income_mm is not None and net_income_mm != 0:
        pe_ltm = round(market_cap_mm / net_income_mm, 2)

    pe_ntm = _to_float(info.get("forwardPE"))
    if pe_ntm is None and price > 0:
        fwd_eps = _to_float(info.get("forwardEps"), 4)
        if fwd_eps is not None and fwd_eps != 0:
            pe_ntm = round(price / fwd_eps, 2)

    p_to_fcf_ltm: float | None = None
    if market_cap_mm is not None and fcf_mm is not None and fcf_mm > 0:
        p_to_fcf_ltm = round(market_cap_mm / fcf_mm, 2)

    ebit_margin_pct = _to_pct(info.get("operatingMargins"), 1)
    roa_pct = _to_pct(info.get("returnOnAssets"), 1)
    roe_pct = _to_pct(info.get("returnOnEquity"), 1)

    roic_pct: float | None = None
    if revenue_mm is not None and ebit_margin_pct is not None and market_cap_mm is not None:
        ebit_mm = revenue_mm * (ebit_margin_pct / 100.0)
        pb = _to_float(info.get("priceToBook"))
        book_equity_mm = (market_cap_mm / pb) if (pb is not None and pb > 0) else None
        if book_equity_mm is not None and net_debt_mm is not None:
            invested_capital = book_equity_mm + net_debt_mm
            if invested_capital > 0:
                roic_pct = round((ebit_mm / invested_capital) * 100.0, 1)

    is_bank_sector = "financial" in str(info.get("sector") or "").lower()
    gross_margin_out = None if is_bank_sector else _to_pct(info.get("grossMargins"), 1)
    roic_out = None if is_bank_sector else roic_pct

    raw_div_yield = info.get("dividendYield")
    div_yield_pct: float | None = None
    if raw_div_yield is not None:
        val_dy = float(raw_div_yield)
        div_yield_pct = round(val_dy if val_dy > 1 else val_dy * 100.0, 2)

    avg_vol_3m = _to_mm(info.get("averageVolume") or info.get("averageDailyVolume3Month"), 1.0)

    return {
        "market_data": {
            "high_52w": _to_float(info.get("fiftyTwoWeekHigh")),
            "low_52w": _to_float(info.get("fiftyTwoWeekLow")),
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
            "net_margin_pct": _to_pct(info.get("profitMargins"), 1),
        },
        "growth_cashflow": {
            "revenue_growth_yoy_pct": _to_pct(info.get("revenueGrowth"), 1),
            "earnings_growth_yoy_pct": _to_pct(info.get("earningsGrowth"), 1),
            "ebitda_margin_pct": _to_pct(info.get("ebitdaMargins"), 1),
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
            "pb_ltm": _to_float(info.get("priceToBook")),
            "p_to_fcf_ltm": p_to_fcf_ltm,
            "dividend_yield_pct": div_yield_pct,
            "payout_ratio_pct": _to_pct(info.get("payoutRatio"), 1),
        },
    }


def get_company_profile(ticker_symbol: str, db: Session) -> dict:
    """
    Datos de mercado (precio, noticias, estructura de capital): Se leen desde CompanyMarketCache (TTL 4h).
    Datos estáticos (descripción, web): Se leen de base de datos o se traducen (Google + respaldo MyMemory).
    Si Yahoo bloquea `.info`, sintetiza una reseña institucional desde SEC EDGAR sin bloquear futuras recargas.
    """
    ticker_upper = ticker_symbol.upper()

    snapshot = get_cached_market_snapshot(ticker_upper, db)
    price = snapshot["price"]
    change = snapshot["change"]
    change_pct = snapshot["change_pct"]
    fx_rate = float(snapshot.get("fx_rate") or 1.0)
    news_list = snapshot["news"]
    raw_info = snapshot.get("info")
    info: dict[str, Any] = raw_info if isinstance(raw_info, dict) else {}

    profile_db = db.query(CompanyProfile).filter(CompanyProfile.ticker == ticker_upper).first()
    desc_str = str(profile_db.description or "").strip() if profile_db else ""
    needs_translation = bool(desc_str) and (desc_str.startswith("(Sin traducir)") or _looks_english(desc_str))

    if profile_db and desc_str and not needs_translation:
        name = str(profile_db.name)
        website = str(profile_db.website)
        translated_desc = desc_str
    else:
        # Si info llegó vacío en el snapshot, hacer un intento directo por si el bloqueo fue transitorio
        if not info:
            try:
                fresh_info = yf.Ticker(ticker_upper).info or {}
                if isinstance(fresh_info, dict) and fresh_info:
                    info = fresh_info
            except Exception:
                pass

        sec_name = ""
        sec_sic_desc = ""
        sec_sic_code = ""
        sec_cik = ""
        company_row = db.query(CompanyData).filter(CompanyData.ticker == ticker_upper).first()
        if company_row is not None:
            if company_row.cik is not None:
                sec_cik = str(company_row.cik).strip().zfill(10)
            if isinstance(company_row.raw_facts, dict):
                sec_name = str(company_row.raw_facts.get("entityName") or "").strip()
                sec_sic_desc = str(company_row.raw_facts.get("sicDescription") or "").strip()
                if company_row.raw_facts.get("sic") is not None:
                    sec_sic_code = str(company_row.raw_facts.get("sic")).strip()

        name = info.get("longName") or info.get("shortName") or sec_name or (str(profile_db.name) if profile_db else ticker_upper)
        website = info.get("website") or (str(profile_db.website) if profile_db else "")
        raw_description = str(info.get("longBusinessSummary") or "").strip()
        if not raw_description and desc_str:
            raw_description = desc_str.removeprefix("(Sin traducir)").strip()

        translated_desc = ""
        has_real_yahoo_desc = bool(raw_description)

        if has_real_yahoo_desc:
            translated_desc, _ = _translate_to_spanish(raw_description, ticker_upper)
            if profile_db:
                db.query(CompanyProfile).filter(CompanyProfile.ticker == ticker_upper).update({
                    "name": name,
                    "website": website,
                    "description": translated_desc,
                })
            else:
                db.add(
                    CompanyProfile(
                        ticker=ticker_upper,
                        name=name,
                        website=website,
                        description=translated_desc,
                    )
                )
            db.commit()
        else:
            # Respaldo institucional transitorio desde SEC EDGAR (no se congela en CompanyProfile)
            if sec_name or sec_sic_desc:
                sector_part = f" en el sector {sec_sic_desc}" if sec_sic_desc else ""
                sic_part = f" (código SIC {sec_sic_code})" if sec_sic_code else ""
                cik_part = f" · Registro SEC CIK {sec_cik}" if sec_cik else ""
                translated_desc = (
                    f"{name} ({ticker_upper}) es un emisor público registrado ante la SEC{sector_part}{sic_part}.{cik_part}"
                )

    return {
        "name": name,
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "website": website,
        "description": translated_desc,
        "news": news_list,
        "summary_metrics": _build_summary_metrics(info, price, fx_rate, snapshot.get("cf_ltm")),
    }