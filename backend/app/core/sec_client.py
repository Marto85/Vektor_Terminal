from datetime import datetime, timedelta, timezone
import threading
import requests
from ratelimit import limits, sleep_and_retry
from app.core.config import SEC_USER_AGENT

# Límite: 8 llamadas por cada 1 segundo (SEC permite hasta 10/seg)
CALLS = 8
RATE_LIMIT = 1

_CIK_CACHE_TTL = timedelta(hours=24)
_CIK_CACHE_LOCK = threading.Lock()
_TICKER_CIK_MAP_CACHE: dict[str, str] = {}
_TICKER_CIK_CACHE_TS: datetime | None = None


def get_cik_from_ticker(ticker: str) -> str:
    """
    Busca el CIK correspondiente a un Ticker usando el archivo oficial de la SEC,
    con caché en memoria de 24 horas para evitar descargar el JSON completo en cada consulta.
    """
    global _TICKER_CIK_MAP_CACHE, _TICKER_CIK_CACHE_TS
    clean_ticker = ticker.strip().upper()
    now = datetime.now(timezone.utc)

    with _CIK_CACHE_LOCK:
        if (
            _TICKER_CIK_CACHE_TS is not None
            and (now - _TICKER_CIK_CACHE_TS) < _CIK_CACHE_TTL
            and _TICKER_CIK_MAP_CACHE
        ):
            cached = _TICKER_CIK_MAP_CACHE.get(clean_ticker)
            if cached:
                return cached
            raise ValueError(f"Ticker {clean_ticker} no encontrado en la base de la SEC.")

    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {"User-Agent": SEC_USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        mapping: dict[str, str] = {}
        for _key, value in data.items():
            sym = str(value.get("ticker") or "").strip().upper()
            cik_val = value.get("cik_str")
            if sym and cik_val is not None:
                mapping[sym] = str(cik_val)

        with _CIK_CACHE_LOCK:
            _TICKER_CIK_MAP_CACHE = mapping
            _TICKER_CIK_CACHE_TS = now

        if clean_ticker in mapping:
            return mapping[clean_ticker]
        raise ValueError(f"Ticker {clean_ticker} no encontrado en la base de la SEC.")

    except requests.RequestException as e:
        raise RuntimeError(f"Error de conexión al obtener CIK: {str(e)}")


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
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Error al descargar datos XBRL de la SEC para CIK {cik}: {str(e)}")


@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT)
def get_recent_sec_filings(
    cik: str,
    target_forms: tuple[str, ...] = ("10-K", "10-Q", "20-F", "6-K"),
    limit: int = 5,
) -> list[dict]:
    """
    Consulta los filings recientes presentados ante la SEC (submissions API)
    y filtra los formularios relevantes (10-K, 10-Q, 20-F, 6-K).
    """
    cik_clean = str(int(str(cik).strip()))
    cik_padded = cik_clean.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Error al consultar filings SEC para CIK {cik}: {str(e)}")

    recent = (payload.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    filing_dates = recent.get("filingDate") or []
    report_dates = recent.get("reportDate") or []
    accession_numbers = recent.get("accessionNumber") or []
    primary_docs = recent.get("primaryDocument") or []

    results: list[dict] = []
    total = min(len(forms), len(filing_dates), len(accession_numbers))

    for i in range(total):
        form_name = str(forms[i] or "").strip().upper()
        if form_name not in target_forms:
            continue

        acc_num = str(accession_numbers[i] or "").strip()
        acc_nodash = acc_num.replace("-", "")
        primary_doc = str(primary_docs[i] or "").strip() if i < len(primary_docs) else ""
        doc_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc_nodash}/{primary_doc}"
            if (acc_nodash and primary_doc)
            else f"https://www.sec.gov/edgar/browse/?CIK={cik_padded}"
        )

        results.append({
            "form": form_name,
            "filing_date": str(filing_dates[i] or ""),
            "report_date": str(report_dates[i] or "") if i < len(report_dates) else "",
            "accession_number": acc_num,
            "document_url": doc_url,
        })
        if len(results) >= limit:
            break

    return results