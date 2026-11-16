from datetime import datetime, timedelta
import json
import math
from typing import Any
import urllib.request
import pandas as pd
import yfinance as yf
from googletrans import Translator
from sqlalchemy.orm import Session
from app.models.database import (
    CompanyData,
    CompanyProfile,
    CompanyMarketCache,
    CompanyEstimatesCache,
)

MARKET_CACHE_TTL = timedelta(hours=4)
ESTIMATES_CACHE_TTL = timedelta(hours=24)
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


def _resolve_fx_rate_to_trade_currency(info: dict[str, Any]) -> float:
    """
    Si `financialCurrency` (moneda de los estados contables, ej. BRL) difiere de
    `currency` (moneda de cotización, ej. USD), devuelve el tipo de cambio multiplicador
    para convertir magnitudes contables a la moneda de cotización.
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
) -> dict[str, float | None]:
    """
    Calcula OCF LTM, CapEx LTM y FCF LTM (OCF - |CapEx|) sumando los últimos 4 trimestres
    de `quarterly_cashflow` (o el último año de `cashflow` anual).
    Si no hay tabla de flujo de efectivo disponible, hace fallback a `info`.
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

    ocf_mm = _to_mm(ocf_raw, fx_rate) if ocf_raw is not None else _to_mm(info.get("operatingCashflow"), fx_rate)
    capex_mm = round(abs(_to_mm(capex_raw, fx_rate) or 0.0), 2) if capex_raw is not None else None

    fcf_mm: float | None = None
    if ocf_mm is not None and capex_mm is not None:
        fcf_mm = round(ocf_mm - capex_mm, 2)
    else:
        fcf_mm = _to_mm(info.get("freeCashflow"), fx_rate)

    return {
        "ocf_ltm_mm": ocf_mm,
        "capex_ltm_mm": capex_mm,
        "fcf_ltm_mm": fcf_mm,
    }


def get_cached_market_snapshot(ticker_symbol: str, db: Session) -> dict[str, Any]:
    """
    Obtiene datos de mercado (precio, cambio, acciones, deuda neta, fx_rate, cf_ltm, noticias e info)
    desde SQLite si tienen menos de 4 horas; caso contrario consulta Yahoo Finance y persiste.
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
            if (now - updated_at) < MARKET_CACHE_TTL and "fx_rate" in cached_payload and "cf_ltm" in cached_payload:
                return cached_payload

    ticker = yf.Ticker(ticker_upper)
    info: dict[str, Any] = ticker.info or {}

    price = float(
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose")
        or 0.0
    )
    prev_close = float(info.get("previousClose") or price)

    change = price - prev_close if prev_close > 0 else 0.0
    change_pct = (change / prev_close) * 100 if prev_close > 0 else 0.0

    fx_rate = _resolve_fx_rate_to_trade_currency(info)
    shares_raw = info.get("sharesOutstanding") or 0
    total_debt_raw = (info.get("totalDebt") or 0) * fx_rate
    total_cash_raw = (info.get("totalCash") or 0) * fx_rate
    shares_mm = float(shares_raw) / 1_000_000.0
    net_debt_mm = (float(total_debt_raw) - float(total_cash_raw)) / 1_000_000.0
    cf_ltm = _extract_ltm_cashflow_metrics(ticker, info, fx_rate)

    raw_news = ticker.news
    news_list: list[dict[str, Any]] = []
    if raw_news:
        for n in raw_news[:4]:
            news_list.append({
                "title": n.get("title", ""),
                "publisher": n.get("publisher", ""),
                "link": n.get("link", ""),
                "providerPublishTime": n.get("providerPublishTime", 0),
            })

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
    Obtiene y persiste en SQLite (`CompanyEstimatesCache`, TTL 24h):
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
    a partir del diccionario `info` ya cacheado en SQLite, convirtiendo magnitudes
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
    Datos estáticos (descripción, web): Se leen de SQLite o se traducen y guardan.
    """
    ticker_upper = ticker_symbol.upper()

    snapshot = get_cached_market_snapshot(ticker_upper, db)
    price = snapshot["price"]
    change = snapshot["change"]
    change_pct = snapshot["change_pct"]
    fx_rate = float(snapshot.get("fx_rate") or 1.0)
    news_list = snapshot["news"]
    info = snapshot.get("info", {})

    profile_db = db.query(CompanyProfile).filter(CompanyProfile.ticker == ticker_upper).first()

    desc_str = str(profile_db.description) if profile_db else ""

    if profile_db and not desc_str.startswith("(Sin traducir)"):
        name = str(profile_db.name)
        website = str(profile_db.website)
        translated_desc = desc_str
    else:
        name = info.get("longName", info.get("shortName", ticker_upper))
        website = info.get("website", "")
        raw_description = info.get("longBusinessSummary", "")

        translated_desc = raw_description
        if raw_description:
            try:
                if len(raw_description) > 4900:
                    raw_description = raw_description[:4900] + "..."

                translator = Translator()
                translation = translator.translate(raw_description, src='en', dest='es')
                translated_desc = translation.text
            except Exception as e:
                print(f"ERROR EN TRADUCCION para {ticker_upper}: {e}")
                translated_desc = f"(Sin traducir) {raw_description}"

        if profile_db:
            db.query(CompanyProfile).filter(CompanyProfile.ticker == ticker_upper).update({
                "name": name,
                "website": website,
                "description": translated_desc
            })
        else:
            new_profile = CompanyProfile(
                ticker=ticker_upper,
                name=name,
                website=website,
                description=translated_desc
            )
            db.add(new_profile)

        db.commit()

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