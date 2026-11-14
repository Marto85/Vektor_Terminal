from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime
import pandas as pd
import yfinance as yf
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


@router.get("/company/{ticker}/history")
def get_company_history(
    ticker: str,
    range: str = Query("1y", pattern="^(3m|6m|ytd|1y|3y|5y|10y|max)$")
):
    """
    Devuelve series históricas OHLCV para todas las métricas del selector
    (Price, % Change, Total Return, Drawdowns, 10k Growth, Market Cap, Enterprise Value),
    junto con el retorno acumulado y CAGR del período.
    """
    range_config = {
        "3m":  ("3mo", "1d"),
        "6m":  ("6mo", "1d"),
        "ytd": ("ytd", "1d"),
        "1y":  ("1y",  "1d"),
        "3y":  ("3y",  "1d"),
        "5y":  ("5y",  "1wk"),
        "10y": ("10y", "1mo"),
        "max": ("max", "1mo"),
    }

    yf_period, yf_interval = range_config[range]

    try:
        tk = yf.Ticker(ticker.upper())
        hist = tk.history(period=yf_period, interval=yf_interval, auto_adjust=False)

        if hist is None or hist.empty:
            raise HTTPException(status_code=404, detail=f"Sin datos históricos para {ticker.upper()}")

        hist = hist.dropna(subset=["Open", "High", "Low", "Close"]).reset_index()

        date_col = "Date" if "Date" in hist.columns else hist.columns[0]
        hist[date_col] = pd.to_datetime(hist[date_col]).dt.tz_localize(None)

        # Datos de capitalización y deuda neta (en millones) para Market Cap y EV
        shares_mm = 0.0
        net_debt_mm = 0.0
        try:
            info = tk.info or {}
            shares_raw = info.get("sharesOutstanding") or 0
            total_debt_raw = info.get("totalDebt") or 0
            total_cash_raw = info.get("totalCash") or 0
            shares_mm = float(shares_raw) / 1_000_000.0
            net_debt_mm = (float(total_debt_raw) - float(total_cash_raw)) / 1_000_000.0
        except Exception:
            shares_mm = 0.0
            net_debt_mm = 0.0

        has_adj = "Adj Close" in hist.columns
        first_close = float(hist["Close"].iloc[0])
        first_adj = float(hist["Adj Close"].iloc[0]) if (has_adj and pd.notna(hist["Adj Close"].iloc[0])) else first_close

        series_by_metric: dict[str, list[dict]] = {
            "Price": [],
            "% Change": [],
            "Total Return": [],
            "Drawdowns": [],
            "10k Growth": [],
            "Market Cap": [],
            "Enterprise Value": [],
        }

        prev_vals: dict[str, float | None] = {m: None for m in series_by_metric}
        running_peak = float(hist["High"].iloc[0])

        def build_point(metric_name: str, date_str: str, o: float, h: float, l: float, c: float, v: int, is_pct: bool = False):
            prev_c = prev_vals[metric_name]
            chg = round(c - prev_c, 2) if prev_c is not None else round(c - o, 2)
            if is_pct:
                # En series ya expresadas en %, la variación diaria es la diferencia en puntos porcentuales
                chg_pct = chg
            else:
                ref = prev_c if (prev_c is not None and prev_c != 0) else o
                chg_pct = round((chg / ref) * 100, 2) if ref != 0 else 0.0

            prev_vals[metric_name] = c
            series_by_metric[metric_name].append({
                "time": date_str,
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(c, 2),
                "volume": v,
                "change": chg,
                "changePct": chg_pct,
            })

        for _, row in hist.iterrows():
            o = float(row["Open"])
            h = float(row["High"])
            l = float(row["Low"])
            c = float(row["Close"])
            v = int(row["Volume"]) if pd.notna(row["Volume"]) else 0
            date_str = row[date_col].strftime("%Y-%m-%d")

            # Factor de ajuste por dividendos y splits para Total Return y 10k Growth
            adj_c = float(row["Adj Close"]) if (has_adj and pd.notna(row["Adj Close"])) else c
            adj_factor = (adj_c / c) if c != 0 else 1.0
            adj_o = o * adj_factor
            adj_h = h * adj_factor
            adj_l = l * adj_factor

            # 1. Price
            build_point("Price", date_str, o, h, l, c, v, is_pct=False)

            # 2. % Change (variación acumulada del precio respecto al inicio del período)
            if first_close > 0:
                build_point(
                    "% Change",
                    date_str,
                    ((o - first_close) / first_close) * 100,
                    ((h - first_close) / first_close) * 100,
                    ((l - first_close) / first_close) * 100,
                    ((c - first_close) / first_close) * 100,
                    v,
                    is_pct=True,
                )

            # 3. Total Return (% acumulado con dividendos reinvertidos)
            if first_adj > 0:
                build_point(
                    "Total Return",
                    date_str,
                    ((adj_o - first_adj) / first_adj) * 100,
                    ((adj_h - first_adj) / first_adj) * 100,
                    ((adj_l - first_adj) / first_adj) * 100,
                    ((adj_c - first_adj) / first_adj) * 100,
                    v,
                    is_pct=True,
                )

                # 5. 10k Growth (evolución de USD 10.000 invertidos al inicio con dividendos)
                build_point(
                    "10k Growth",
                    date_str,
                    10000.0 * (adj_o / first_adj),
                    10000.0 * (adj_h / first_adj),
                    10000.0 * (adj_l / first_adj),
                    10000.0 * (adj_c / first_adj),
                    v,
                    is_pct=False,
                )

            # 4. Drawdowns (caída % desde el máximo alcanzado en el período)
            peak_before = running_peak
            running_peak = max(running_peak, h)
            dd_o = ((o - peak_before) / peak_before) * 100 if peak_before > 0 else 0.0
            dd_h = ((h - running_peak) / running_peak) * 100 if running_peak > 0 else 0.0
            dd_l = ((l - running_peak) / running_peak) * 100 if running_peak > 0 else 0.0
            dd_c = ((c - running_peak) / running_peak) * 100 if running_peak > 0 else 0.0
            build_point("Drawdowns", date_str, dd_o, dd_h, dd_l, dd_c, v, is_pct=True)

            # 6. Market Cap (MM) y 7. Enterprise Value (MM)
            if shares_mm > 0:
                mc_o, mc_h, mc_l, mc_c = o * shares_mm, h * shares_mm, l * shares_mm, c * shares_mm
                build_point("Market Cap", date_str, mc_o, mc_h, mc_l, mc_c, v, is_pct=False)
                build_point(
                    "Enterprise Value",
                    date_str,
                    mc_o + net_debt_mm,
                    mc_h + net_debt_mm,
                    mc_l + net_debt_mm,
                    mc_c + net_debt_mm,
                    v,
                    is_pct=False,
                )

        last_close = float(hist["Close"].iloc[-1])
        days_diff = (hist[date_col].iloc[-1] - hist[date_col].iloc[0]).days
        years = max(days_diff / 365.25, 0.01)

        total_return_pct = round(((last_close - first_close) / first_close) * 100, 1) if first_close > 0 else 0.0
        cagr_pct = round((((last_close / first_close) ** (1 / years)) - 1) * 100, 1) if first_close > 0 else 0.0

        return {
            "ticker": ticker.upper(),
            "range": range,
            "interval": yf_interval,
            "years": round(years, 2),
            "totalReturnPct": total_return_pct,
            "cagrPct": cagr_pct,
            "seriesByMetric": series_by_metric,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo historial: {str(e)}")