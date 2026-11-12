import requests
from ratelimit import limits, sleep_and_retry
from app.core.config import SEC_USER_AGENT

# Límite: 8 llamadas por cada 1 segundo
CALLS = 8
RATE_LIMIT = 1

@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT)
def get_company_facts(cik: str) -> dict:
    """
    Obtiene el JSON crudo con el historial contable (XBRL) de la SEC.
    El CIK debe ser un string y se rellena con ceros a la izquierda hasta 10 dígitos.
    """
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    
    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate"
    }
    
    response = requests.get(url, headers=headers)
    
    # Manejo de errores explícito: falla si la respuesta no es 200 OK
    response.raise_for_status()
    
    return response.json()

def get_cik_from_ticker(ticker: str) -> str:
    """
    Busca el CIK correspondiente a un Ticker usando el archivo oficial de la SEC.
    """
    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {"User-Agent": SEC_USER_AGENT}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # El JSON de la SEC tiene formato: {"0": {"cik_str": 320193, "ticker": "AAPL", ...}, ...}
        for key, value in data.items():
            if value.get("ticker") == ticker.upper():
                return str(value.get("cik_str"))
        
        raise ValueError(f"Ticker {ticker.upper()} no encontrado en la base de la SEC.")
    
    except requests.RequestException as e:
        raise RuntimeError(f"Error de conexión al obtener CIK: {str(e)}")

@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT)
def get_company_facts(cik: str) -> dict:
    """
    Obtiene el JSON crudo con el historial contable (XBRL) de la SEC.
    """
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Error al descargar datos XBRL de la SEC para CIK {cik}: {str(e)}")