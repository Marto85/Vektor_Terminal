import yfinance as yf
from googletrans import Translator
from sqlalchemy.orm import Session
from app.models.database import CompanyProfile 

def get_company_profile(ticker_symbol: str, db: Session) -> dict:
    """
    Datos dinámicos (precio, noticias): Se extraen en vivo de YF.
    Datos estáticos (descripción, web): Se leen de SQLite o se traducen y guardan.
    Se incluye lógica de auto-reparación si un registro previo falló al traducirse.
    """
    ticker_upper = ticker_symbol.upper()
    ticker = yf.Ticker(ticker_upper)
    
    # 1. DATOS DINÁMICOS (Siempre en vivo)
    info = ticker.info
    price = info.get("currentPrice", info.get("regularMarketPrice", info.get("previousClose", 0.0)))
    prev_close = info.get("previousClose", price)
    
    change = price - prev_close if prev_close > 0 else 0.0
    change_pct = (change / prev_close) * 100 if prev_close > 0 else 0.0
    
    raw_news = ticker.news
    news_list = []
    if raw_news:
        for n in raw_news[:4]:
            news_list.append({
                "title": n.get("title", ""),
                "publisher": n.get("publisher", ""),
                "link": n.get("link", ""),
                "providerPublishTime": n.get("providerPublishTime", 0)
            })

    # 2. DATOS ESTÁTICOS (Desde SQLite)
    profile_db = db.query(CompanyProfile).filter(CompanyProfile.ticker == ticker_upper).first()
    
    # Extraemos el texto a una variable nativa para que Pylance no intente evaluar objetos de SQLAlchemy
    desc_str = str(profile_db.description) if profile_db else ""
    
    # Condición de auto-reparación limpia
    if profile_db and not desc_str.startswith("(Sin traducir)"):
        name = str(profile_db.name)
        website = str(profile_db.website)
        translated_desc = desc_str
    else:
        # No está en DB, o está pero falló la traducción la vez pasada (hay que reintentar)
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
        
        # Persistencia (Crear o Actualizar)
        if profile_db:
            # Usamos .update() para sobrescribir el registro y evitar que el linter de VS Code se queje
            db.query(CompanyProfile).filter(CompanyProfile.ticker == ticker_upper).update({
                "name": name,
                "website": website,
                "description": translated_desc
            })
        else:
            # Creamos un registro nuevo
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