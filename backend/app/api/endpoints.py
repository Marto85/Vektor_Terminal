from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Any
from datetime import datetime, timezone
import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session
import requests

from app.core.security import get_current_user
from app.models.database import SessionLocal, User
from app.core.yf_client import get_company_profile, get_cached_market_snapshot
from app.services.company_service import get_raw_financials
from app.services.financial_parser import extract_annual_metrics, extract_quarterly_metrics
from app.services.ratios_calculator import calculate_ratios, build_financial_health_report
from app.services.valuation_service import build_valuation_report
from app.services.peers_service import build_peers_comparison, build_manual_comparison
from app.services.screener_service import get_screener_universe, sync_screener_batch
from app.services.market_overview_service import build_market_overview
from app.services.macro_lab_service import build_macro_lab_payload
from app.services.watchlist_service import (
    get_all_watchlists_payload,
    create_watchlist,
    rename_watchlist,
    delete_watchlist,
    reorder_watchlist_items,
    upsert_watchlist_item,
    remove_watchlist_item,
    mark_notifications_read,
    clear_all_notifications,
)
from app.services.thesis_service import (
    build_investment_thesis_onepager,
    save_custom_segments,
    reset_custom_segments,
)
from app.services.ownership_service import build_ownership_and_insiders_report
from app.services.export_service import build_company_workbook_bytes, build_company_pdf_bytes

router = APIRouter()


class WatchlistNamePayload(BaseModel):
    name: str


class WatchlistReorderPayload(BaseModel):
    tickers: list[str]


class WatchlistItemPayload(BaseModel):
    ticker: str
    buy_target_price: float | None = None
    sell_target_price: float | None = None
    thesis_note: str | None = ""
    alerts: list[dict[str, Any]] = []


class CustomSegmentsPayload(BaseModel):
    business_segments: list[dict[str, Any]] = []
    geo_segments: list[dict[str, Any]] = []
    key_clients_notes: str = ""


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/market-overview")
def get_market_overview(db: Session = Depends(get_db)):
    try:
        return build_market_overview(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cargando panorama de mercado: {str(e)}")


@router.get("/macro-lab")
def get_macro_lab(db: Session = Depends(get_db)):
    try:
        return build_macro_lab_payload(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cargando Macro Lab: {str(e)}")


@router.get("/watchlists")
def list_watchlists(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return get_all_watchlists_payload(
            db,
            user_id=int(current_user.id),
            claim_legacy=(current_user.role == "superadmin"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cargando listas de seguimiento: {str(e)}")


@router.post("/watchlists")
def post_watchlist(
    body: WatchlistNamePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return create_watchlist(db, user_id=int(current_user.id), name=body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando lista de seguimiento: {str(e)}")


@router.put("/watchlists/{watchlist_id}")
def put_watchlist(
    watchlist_id: int,
    body: WatchlistNamePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return rename_watchlist(
            db,
            user_id=int(current_user.id),
            watchlist_id=watchlist_id,
            new_name=body.name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error renombrando lista: {str(e)}")


@router.delete("/watchlists/{watchlist_id}")
def remove_watchlist(
    watchlist_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return delete_watchlist(
            db,
            user_id=int(current_user.id),
            watchlist_id=watchlist_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando lista: {str(e)}")


@router.put("/watchlists/{watchlist_id}/reorder")
def put_watchlist_reorder(
    watchlist_id: int,
    body: WatchlistReorderPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return reorder_watchlist_items(
            db,
            user_id=int(current_user.id),
            watchlist_id=watchlist_id,
            ordered_tickers=body.tickers,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reordenando lista: {str(e)}")


@router.post("/watchlists/{watchlist_id}/items")
def post_watchlist_item(
    watchlist_id: int,
    body: WatchlistItemPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return upsert_watchlist_item(
            db=db,
            user_id=int(current_user.id),
            watchlist_id=watchlist_id,
            ticker=body.ticker,
            buy_target_price=body.buy_target_price,
            sell_target_price=body.sell_target_price,
            thesis_note=body.thesis_note,
            alerts=body.alerts,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando empresa en lista: {str(e)}")


@router.delete("/watchlists/{watchlist_id}/items/{ticker}")
def delete_watchlist_item(
    watchlist_id: int,
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return remove_watchlist_item(
            db,
            user_id=int(current_user.id),
            watchlist_id=watchlist_id,
            ticker=ticker,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error quitando empresa de lista: {str(e)}")


@router.post("/notifications/read-all")
def post_notifications_read_all(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return mark_notifications_read(db, user_id=int(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error marcando notificaciones como leídas: {str(e)}")


@router.post("/notifications/{notification_id}/read")
def post_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return mark_notifications_read(
            db,
            user_id=int(current_user.id),
            notification_id=notification_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error marcando notificación como leída: {str(e)}")


@router.delete("/notifications")
def delete_all_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return clear_all_notifications(db, user_id=int(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error limpiando historial de notificaciones: {str(e)}")


@router.get("/company/{ticker}/profile")
def get_profile(ticker: str, db: Session = Depends(get_db)):
    try:
        return get_company_profile(ticker, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/company/{ticker}/financials/annual")
def get_annual_financials(ticker: str, db: Session = Depends(get_db)):
    try:
        raw_data = get_raw_financials(ticker, db)
        financial_data = extract_annual_metrics(raw_data)

        current_year = datetime.now().year
        years_range = [str(y) for y in range(current_year - 6, current_year + 1)]
        financial_data_with_ratios = calculate_ratios(financial_data, years_range)

        return financial_data_with_ratios

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/company/{ticker}/health")
def get_company_health(ticker: str, db: Session = Depends(get_db)):
    try:
        raw_data = get_raw_financials(ticker, db)
        financial_data = extract_annual_metrics(raw_data)
        return build_financial_health_report(ticker, financial_data, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error evaluando salud financiera: {str(e)}")


@router.get("/company/{ticker}/financials/quarterly")
def get_quarterly_financials(ticker: str, db: Session = Depends(get_db)):
    try:
        raw_data = get_raw_financials(ticker, db, is_quarterly=True)
        financial_data = extract_quarterly_metrics(raw_data)
        return financial_data

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/company/{ticker}/valuation")
def get_company_valuation(ticker: str, db: Session = Depends(get_db)):
    try:
        return build_valuation_report(ticker, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculando valoración: {str(e)}")


@router.get("/company/{ticker}/ownership")
def get_company_ownership(ticker: str, db: Session = Depends(get_db)):
    try:
        return build_ownership_and_insiders_report(ticker, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo propiedad institucional e insiders: {str(e)}")


def _collect_company_export_payload(ticker: str, period: str, db: Session) -> dict[str, Any]:
    clean_ticker = ticker.strip().upper()
    profile = dict(get_company_profile(clean_ticker, db) or {})

    try:
        snapshot = get_cached_market_snapshot(clean_ticker, db) or {}
        info = snapshot.get("info") if isinstance(snapshot.get("info"), dict) else {}
        profile["info"] = info
        profile["fx_rate"] = snapshot.get("fx_rate") or 1.0
    except Exception:
        profile["info"] = {}
        profile["fx_rate"] = 1.0

    raw_annual = get_raw_financials(clean_ticker, db)
    annual_metrics = extract_annual_metrics(raw_annual)
    current_year = datetime.now().year
    years_range = [str(y) for y in range(current_year - 6, current_year + 1)]
    annual_with_ratios = calculate_ratios(list(annual_metrics), years_range)

    if period == "quarterly":
        raw_q = get_raw_financials(clean_ticker, db, is_quarterly=True)
        statements = extract_quarterly_metrics(raw_q)
    else:
        statements = annual_with_ratios

    try:
        health = build_financial_health_report(clean_ticker, annual_metrics, db)
    except Exception:
        health = {}

    try:
        valuation = build_valuation_report(clean_ticker, db)
    except Exception:
        valuation = {}

    try:
        ownership = build_ownership_and_insiders_report(clean_ticker, db)
    except Exception:
        ownership = {}

    return {
        "ticker": clean_ticker,
        "profile": profile,
        "market": profile,
        "statements": statements,
        "health": health,
        "valuation": valuation,
        "ownership": ownership,
    }


@router.get("/company/{ticker}/export/xlsx")
def export_company_xlsx(
    ticker: str,
    period: str = Query("annual", pattern="^(annual|quarterly)$"),
    db: Session = Depends(get_db),
):
    try:
        payload = _collect_company_export_payload(ticker, period, db)
        xlsx_bytes = build_company_workbook_bytes(
            ticker=payload["ticker"],
            period=period,
            profile=payload["profile"],
            market=payload["market"],
            statements=payload["statements"],
            valuation=payload["valuation"],
            ownership=payload["ownership"],
            health=payload.get("health") or {},
        )
        filename = f"{payload['ticker']}_VektorTerminal_{period}.xlsx"
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exportando libro Excel: {str(e)}")


@router.get("/company/{ticker}/export/pdf")
def export_company_pdf(ticker: str, db: Session = Depends(get_db)):
    try:
        payload = _collect_company_export_payload(ticker, "annual", db)
        pdf_bytes = build_company_pdf_bytes(
            ticker=payload["ticker"],
            profile=payload["profile"],
            market=payload["market"],
            statements=payload["statements"],
            valuation=payload["valuation"],
            ownership=payload["ownership"],
            health=payload.get("health") or {},
        )
        filename = f"{payload['ticker']}_Informe_Ejecutivo.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exportando informe PDF: {str(e)}")


@router.get("/company/{ticker}/thesis-onepager")
def get_company_thesis_onepager(ticker: str, db: Session = Depends(get_db)):
    try:
        return build_investment_thesis_onepager(ticker, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando ficha ejecutiva de tesis: {str(e)}")


@router.put("/company/{ticker}/segments")
def put_company_segments(ticker: str, body: CustomSegmentsPayload, db: Session = Depends(get_db)):
    try:
        return save_custom_segments(
            db=db,
            ticker_symbol=ticker,
            business_segments=body.business_segments,
            geo_segments=body.geo_segments,
            key_clients_notes=body.key_clients_notes,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando segmentos personalizados: {str(e)}")


@router.delete("/company/{ticker}/segments")
def delete_company_custom_segments(ticker: str, db: Session = Depends(get_db)):
    try:
        return reset_custom_segments(db, ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restaurando segmentos desde SEC: {str(e)}")


@router.get("/company/{ticker}/peers")
def get_company_peers(ticker: str, db: Session = Depends(get_db)):
    try:
        return build_peers_comparison(ticker, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo comparables: {str(e)}")


@router.get("/compare")
def compare_companies(
    tickers: str = Query(..., description="Lista de hasta 5 tickers separados por coma"),
    db: Session = Depends(get_db),
):
    try:
        ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
        return build_manual_comparison(ticker_list, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando comparador: {str(e)}")


@router.get("/screener")
def get_screener(db: Session = Depends(get_db)):
    try:
        return get_screener_universe(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cargando screener: {str(e)}")


@router.post("/screener/sync")
def post_screener_sync(
    batch_size: int = Query(15, ge=1, le=25),
    db: Session = Depends(get_db),
):
    try:
        return sync_screener_batch(db, batch_size=batch_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sincronizando lote de screener: {str(e)}")


@router.get("/search")
def search_ticker(q: str):
    """
    Busca coincidencias parciales de tickers y nombres de empresas usando la API pública de YF.
    """
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={q}&" + "quotesCount=6&newsCount=0"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        data = resp.json()
        quotes = data.get("quotes", [])

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
    range: str = Query("1y", pattern="^(3m|6m|ytd|1y|3y|5y|10y|max)$"),
    interval: str | None = Query(None, pattern="^(15m|1h|1d|1wk|1mo)$"),
):
    """
    Devuelve series históricas OHLCV para todas las métricas del selector
    (Price, % Change, Total Return, Drawdowns, 10k Growth, Market Cap, Enterprise Value),
    soportando temporalidades intradiarias (15m, 1h) y de cierre (1d, 1wk, 1mo).
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

    yf_period, default_interval = range_config[range]
    yf_interval = interval or default_interval
    is_intraday = yf_interval in ("15m", "1h")

    # Yahoo Finance limita 15m a 60 días y 1h a 730 días
    if yf_interval == "15m":
        yf_period = "60d"
    elif yf_interval == "1h" and range in ("3y", "5y", "10y", "max"):
        yf_period = "730d"

    try:
        tk = yf.Ticker(ticker.upper())
        hist = tk.history(period=yf_period, interval=yf_interval, auto_adjust=False)

        if hist is None or hist.empty:
            raise HTTPException(status_code=404, detail=f"Sin datos históricos para {ticker.upper()}")

        hist = hist.dropna(subset=["Open", "High", "Low", "Close"]).reset_index()

        date_col = "Datetime" if "Datetime" in hist.columns else ("Date" if "Date" in hist.columns else hist.columns[0])
        ts_series = pd.to_datetime(hist[date_col])
        if ts_series.dt.tz is not None:
            ts_series = ts_series.dt.tz_convert("UTC").dt.tz_localize(None)
        hist[date_col] = ts_series

        # Deduplicar marcas temporales por seguridad en Lightweight Charts
        hist = hist.drop_duplicates(subset=[date_col], keep="last").reset_index(drop=True)

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

        def build_point(metric_name: str, time_val: str | int, o: float, h: float, l: float, c: float, v: int, is_pct: bool = False):
            prev_c = prev_vals[metric_name]
            chg = round(c - prev_c, 2) if prev_c is not None else round(c - o, 2)
            if is_pct:
                chg_pct = chg
            else:
                ref = prev_c if (prev_c is not None and prev_c != 0) else o
                chg_pct = round((chg / ref) * 100, 2) if ref != 0 else 0.0

            prev_vals[metric_name] = c
            series_by_metric[metric_name].append({
                "time": time_val,
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

            dt_val = row[date_col]
            if is_intraday:
                time_val: str | int = int(dt_val.replace(tzinfo=timezone.utc).timestamp())
            else:
                time_val = dt_val.strftime("%Y-%m-%d")

            adj_c = float(row["Adj Close"]) if (has_adj and pd.notna(row["Adj Close"])) else c
            adj_factor = (adj_c / c) if c != 0 else 1.0
            adj_o = o * adj_factor
            adj_h = h * adj_factor
            adj_l = l * adj_factor

            build_point("Price", time_val, o, h, l, c, v, is_pct=False)

            if first_close > 0:
                build_point(
                    "% Change",
                    time_val,
                    ((o - first_close) / first_close) * 100,
                    ((h - first_close) / first_close) * 100,
                    ((l - first_close) / first_close) * 100,
                    ((c - first_close) / first_close) * 100,
                    v,
                    is_pct=True,
                )

            if first_adj > 0:
                build_point(
                    "Total Return",
                    time_val,
                    ((adj_o - first_adj) / first_adj) * 100,
                    ((adj_h - first_adj) / first_adj) * 100,
                    ((adj_l - first_adj) / first_adj) * 100,
                    ((adj_c - first_adj) / first_adj) * 100,
                    v,
                    is_pct=True,
                )

                build_point(
                    "10k Growth",
                    time_val,
                    10000.0 * (adj_o / first_adj),
                    10000.0 * (adj_h / first_adj),
                    10000.0 * (adj_l / first_adj),
                    10000.0 * (adj_c / first_adj),
                    v,
                    is_pct=False,
                )

            peak_before = running_peak
            running_peak = max(running_peak, h)
            dd_o = ((o - peak_before) / peak_before) * 100 if peak_before > 0 else 0.0
            dd_h = ((h - running_peak) / running_peak) * 100 if running_peak > 0 else 0.0
            dd_l = ((l - running_peak) / running_peak) * 100 if running_peak > 0 else 0.0
            dd_c = ((c - running_peak) / running_peak) * 100 if running_peak > 0 else 0.0
            build_point("Drawdowns", time_val, dd_o, dd_h, dd_l, dd_c, v, is_pct=True)

            if shares_mm > 0:
                mc_o, mc_h, mc_l, mc_c = o * shares_mm, h * shares_mm, l * shares_mm, c * shares_mm
                build_point("Market Cap", time_val, mc_o, mc_h, mc_l, mc_c, v, is_pct=False)
                build_point(
                    "Enterprise Value",
                    time_val,
                    mc_o + net_debt_mm,
                    mc_h + net_debt_mm,
                    mc_l + net_debt_mm,
                    mc_c + net_debt_mm,
                    v,
                    is_pct=False,
                )

        last_close = float(hist["Close"].iloc[-1])
        seconds_diff = (hist[date_col].iloc[-1] - hist[date_col].iloc[0]).total_seconds()
        days_diff = max(seconds_diff / 86400.0, 0.01)
        years = max(days_diff / 365.25, 0.01)

        total_return_pct = round(((last_close - first_close) / first_close) * 100, 1) if first_close > 0 else 0.0
        cagr_pct = round((((last_close / first_close) ** (1 / years)) - 1) * 100, 1) if first_close > 0 else 0.0

        return {
            "ticker": ticker.upper(),
            "range": range,
            "interval": yf_interval,
            "isIntraday": is_intraday,
            "years": round(years, 2),
            "totalReturnPct": total_return_pct,
            "cagrPct": cagr_pct,
            "seriesByMetric": series_by_metric,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo historial: {str(e)}")