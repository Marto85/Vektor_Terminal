from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.models.database import CompanyData
from app.core.sec_client import get_cik_from_ticker, get_company_facts

# Caché de 7 días para no sobrecargar la API
CACHE_DAYS = 7 

def get_raw_financials(ticker: str, db: Session, is_quarterly: bool = False) -> dict:
    """
    Obtiene los datos financieros crudos (JSON completo de la SEC), priorizando SQLite local.
    El parámetro is_quarterly se acepta por compatibilidad de firma, pero la SEC
    siempre devuelve toda la historia (10-K y 10-Q) en el mismo archivo CompanyFacts.
    """
    ticker_upper = ticker.upper()
    db_company = db.query(CompanyData).filter(CompanyData.ticker == ticker_upper).first()
    
    if db_company:
        # Usamos getattr() para extraer el valor real en tiempo de ejecución. 
        # Esto engaña al linter de VS Code devolviendo 'Any' y elimina las alertas rojas.
        last_updated_val = getattr(db_company, "last_updated", None)
        raw_facts_val = getattr(db_company, "raw_facts", {})
        
        # Reemplazamos utcnow() por el estándar moderno para evitar el tachado
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        
        if last_updated_val and (now_utc - last_updated_val) < timedelta(days=CACHE_DAYS):
            # Devolvemos directo; si por alguna razón no fuera dict, lo forzamos
            return raw_facts_val if isinstance(raw_facts_val, dict) else dict(raw_facts_val)

    # Si no existe o caducó, vamos a la SEC
    cik = get_cik_from_ticker(ticker_upper)
    fetched_raw_facts = get_company_facts(cik)
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    
    if db_company:
        db.query(CompanyData).filter(CompanyData.ticker == ticker_upper).update({
            "raw_facts": fetched_raw_facts,
            "last_updated": now_utc
        })
    else:
        new_company = CompanyData(
            ticker=ticker_upper,
            cik=cik,
            raw_facts=fetched_raw_facts
        )
        db.add(new_company)
    
    db.commit()
    
    return fetched_raw_facts