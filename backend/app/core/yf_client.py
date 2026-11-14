from datetime import datetime, timedelta
from typing import Any
import yfinance as yf
from googletrans import Translator
from sqlalchemy.orm import Session
from app.models.database import CompanyProfile, CompanyMarketCache

MARKET_CACHE_TTL = timedelta(hours=4)


def _to_mm(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return round(float(val) / 1_000_000.0, 2)
    except (TypeError, ValueError):
        return None


def _to_float(val: Any, decimals: int = 2) -> float | None:
    if val is None:
        return None
    try:
        return round(float(val), decimals)
    except (TypeError, ValueError):
        return None


def _to_pct(val: Any, decimals: int = 1) -> float | None:
    if val is None:
        return None
    try:
        return round(float(val) * 100.0, decimals)
    except (TypeError, ValueError):
        return None


def get_cached_market_snapshot(ticker_symbol: str, db: Session) -> dict[str, Any]:
    """
    Obtiene datos de mercado (precio, cambio, acciones, deuda neta, noticias e info)
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
            if (now - updated_at) < MARKET_CACHE_TTL:
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

    shares_raw = info.get("sharesOutstanding") or 0
    total_debt_raw = info.get("totalDebt") or 0
    total_cash_raw = info.get("totalCash") or 0
    shares_mm = float(shares_raw) / 1_000_000.0
    net_debt_mm = (float(total_debt_raw) - float(total_cash_raw)) / 1_000_000.0

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
        "shares_mm": shares_mm,
        "net_debt_mm": net_debt_mm,
        "news": news_list,
        "info": info,
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


def _build_summary_metrics(info: dict[str, Any], price: float) -> dict[str, Any]:
    """
    Construye las 4 secciones del panel derecho estilo TIKR en 2 columnas
    a partir del diccionario `info` ya cacheado en SQLite (sin peticiones extra).
    """
    shares_mm = _to_mm(info.get("sharesOutstanding"))
    float_shares_mm = _to_mm(info.get("floatShares"))

    # Capitalización bursátil basada en acciones ordinarias (coincide con TIKR)
    market_cap_mm: float | None = None
    if shares_mm is not None and shares_mm > 0 and price > 0:
        market_cap_mm = round(shares_mm * price, 2)
    else:
        market_cap_mm = _to_mm(info.get("marketCap"))

    total_debt_mm = _to_mm(info.get("totalDebt"))
    total_cash_mm = _to_mm(info.get("totalCash"))
    net_debt_mm: float | None = None
    if total_debt_mm is not None and total_cash_mm is not None:
        net_debt_mm = round(total_debt_mm - total_cash_mm, 2)

    ev_mm = _to_mm(info.get("enterpriseValue"))
    if ev_mm is None and market_cap_mm is not None and net_debt_mm is not None:
        ev_mm = round(market_cap_mm + net_debt_mm, 2)

    ebitda_mm = _to_mm(info.get("ebitda"))
    revenue_mm = _to_mm(info.get("totalRevenue"))
    gross_profit_mm = _to_mm(info.get("grossProfits"))
    net_income_mm = _to_mm(info.get("netIncomeToCommon"))
    fcf_mm = _to_mm(info.get("freeCashflow"))
    ocf_mm = _to_mm(info.get("operatingCashflow"))

    # Flotante %
    float_pct: float | None = None
    if float_shares_mm is not None and shares_mm is not None and shares_mm > 0:
        float_pct = round(min((float_shares_mm / shares_mm) * 100.0, 100.0), 1)

    # Deuda neta / EBITDA LTM (permite valores negativos cuando EBITDA < 0)
    net_debt_to_ebitda: float | None = None
    if net_debt_mm is not None and ebitda_mm is not None and ebitda_mm != 0:
        net_debt_to_ebitda = round(net_debt_mm / ebitda_mm, 2)

    # Múltiplos LTM y NTM
    ev_to_sales_ltm = _to_float(info.get("enterpriseToRevenue"))
    if ev_to_sales_ltm is None and ev_mm is not None and revenue_mm is not None and revenue_mm != 0:
        ev_to_sales_ltm = round(ev_mm / revenue_mm, 2)

    ev_to_ebitda_ltm = _to_float(info.get("enterpriseToEbitda"))
    if ev_to_ebitda_ltm is None and ev_mm is not None and ebitda_mm is not None and ebitda_mm != 0:
        ev_to_ebitda_ltm = round(ev_mm / ebitda_mm, 2)

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
    if market_cap_mm is not None and fcf_mm is not None and fcf_mm != 0:
        p_to_fcf_ltm = round(market_cap_mm / fcf_mm, 2)

    # Eficiencia (ROIC / ROCE aproximados si hay capital invertido)
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

    # Dividendos (Yahoo devuelve dividendYield ya en % en algunos tickers o decimal en otros)
    raw_div_yield = info.get("dividendYield")
    div_yield_pct: float | None = None
    if raw_div_yield is not None:
        val_dy = float(raw_div_yield)
        div_yield_pct = round(val_dy if val_dy > 1 else val_dy * 100.0, 2)

    avg_vol_3m = _to_mm(info.get("averageVolume") or info.get("averageDailyVolume3Month"))

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
            "gross_margin_pct": _to_pct(info.get("grossMargins"), 1),
            "ebit_margin_pct": ebit_margin_pct,
            "roa_pct": roa_pct,
            "roe_pct": roe_pct,
            "roic_pct": roic_pct,
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

    # 1. DATOS DE MERCADO (Cache-first en SQLite)
    snapshot = get_cached_market_snapshot(ticker_upper, db)
    price = snapshot["price"]
    change = snapshot["change"]
    change_pct = snapshot["change_pct"]
    news_list = snapshot["news"]
    info = snapshot.get("info", {})

    # 2. DATOS ESTÁTICOS (Desde SQLite)
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
        "summary_metrics": _build_summary_metrics(info, price),
    }