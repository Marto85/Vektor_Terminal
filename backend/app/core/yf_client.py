from datetime import datetime, timedelta
from typing import Any
import yfinance as yf
from googletrans import Translator
from sqlalchemy.orm import Session
from app.models.database import CompanyProfile, CompanyMarketCache

MARKET_CACHE_TTL = timedelta(hours=4)


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


def get_company_profile(ticker_symbol: str, db: Session) -> dict:
    """
    Datos de mercado (precio, noticias): Se leen desde CompanyMarketCache (TTL 4h).
    Datos estáticos (descripción, web): Se leen de SQLite o se traducen y guardan.
    Se incluye lógica de auto-reparación si un registro previo falló al traducirse.
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
        "news": news_list
    }