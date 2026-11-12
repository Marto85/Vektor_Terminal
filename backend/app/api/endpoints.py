from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from sqlalchemy.orm import Session
import requests

from app.models.database import SessionLocal
from app.core.yf_client import get_company_profile
from app.services.company_service import get_raw_financials
from app.services.financial_parser import extract_annual_metrics, extract_quarterly_metrics
from app.services.ratios_calculator import calculate_ratios

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/company/{ticker}/profile")
def get_profile(ticker: str, db: Session = Depends(get_db)):
    try:
        # Pasamos la conexión de la base de datos al cliente de YF
        return get_company_profile(ticker, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/company/{ticker}/financials/annual")
def get_annual_financials(ticker: str, db: Session = Depends(get_db)):
    try:
        # 1. Obtener datos crudos de la SEC (o desde la caché en SQLite)
        raw_data = get_raw_financials(ticker, db)
        
        # 2. Parsear y armar el diccionario base de Estados Financieros
        financial_data = extract_annual_metrics(raw_data)
        
        # 3. Calcular Ratios inyectando la data parseada
        current_year = datetime.now().year
        years_range = [str(y) for y in range(current_year - 6, current_year + 1)]
        financial_data_with_ratios = calculate_ratios(financial_data, years_range)
        
        return financial_data_with_ratios
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/company/{ticker}/financials/quarterly")
def get_quarterly_financials(ticker: str, db: Session = Depends(get_db)):
    try:
        # TODO: Necesitamos adaptar company_service.py para que extraiga formularios 10-Q en vez de 10-K
        raw_data = get_raw_financials(ticker, db, is_quarterly=True) 
        
        # TODO: Crear parser específico (extract_quarterly_metrics) para lidiar con el motor de 
        # contingencias contables, ya que los trimestres tienen más baches de datos que los anuales
        financial_data = extract_quarterly_metrics(raw_data)
        
        # TODO: Calcular ratios pasando el rango de trimestres (ej: ["Q3-25", "Q4-25", "Q1-26..."])
        
        return financial_data
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/search")
def search_ticker(q: str):
    """
    Busca coincidencias parciales de tickers y nombres de empresas usando la API pública de YF.
    """
    # Separamos el string para evitar que el visor HTML convierta '"' en una comilla doble
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={q}&" + "quotesCount=6&newsCount=0"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        data = resp.json()
        quotes = data.get("quotes", [])
        
        # Filtramos para devolver solo nombre, ticker y tipo de activo
        results = [
            {
                "ticker": item.get("symbol"),
                "name": item.get("shortname", item.get("longname", "N/A")),
                "type": item.get("quoteType", "")
            }
            for item in quotes if item.get("symbol")
        ]
        return results
    except Exception:
        return []