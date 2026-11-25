from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from io import StringIO
from statistics import mean, median
from typing import Any
import pandas as pd
import requests
import yfinance as yf
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.database import MacroSeriesCache, IndexValuationSnapshot


INDEX_ETFS = [
    {"code": "SP500", "name": "S&P 500 (USA Large Cap)", "proxy": "SPY", "hist_pe_avg": 19.8},
    {"code": "NDX", "name": "Nasdaq 100 (Tech / Growth)", "proxy": "QQQ", "hist_pe_avg": 26.5},
    {"code": "DJI", "name": "Dow Jones Industrial (30)", "proxy": "DIA", "hist_pe_avg": 17.6},
    {"code": "RUT", "name": "Russell 2000 (USA Small Cap)", "proxy": "IWM", "hist_pe_avg": 21.4},
    {"code": "EWZ", "name": "MSCI Brazil (Bovespa)", "proxy": "EWZ", "hist_pe_avg": 11.2},
    {"code": "EEM", "name": "MSCI Emerging Markets", "proxy": "EEM", "hist_pe_avg": 13.8},
]

YF_MACRO_TICKERS = {
    "sp500_nom": "^GSPC",
    "ndx_nom": "^NDX",
    "ixic_nom": "^IXIC",
    "dji_nom": "^DJI",
    "rut_nom": "^RUT",
    "gold_nom": "GC=F",
    "copper_nom": "HG=F",
    "dxy": "DX-Y.NYB",
    "eur_usd": "EURUSD=X",
    "usd_jpy": "JPY=X",
    "usd_brl": "BRL=X",
    "usd_ars": "ARS=X",
    "ust_10y": "^TNX",
    "ust_5y": "^FVX",
    "ust_3m": "^IRX",
    "vix": "^VIX",
    "spy": "SPY",
    "rsp": "RSP",
    "iwd": "IWD",
    "iwf": "IWF",
    "tip": "TIP",
    "ief": "IEF",
    "hyg": "HYG",
    "lqd": "LQD",
}

FRED_SERIES = {
    "cpi": "CPIAUCSL",           # Índice de Precios al Consumidor EE. UU.
    "m2": "M2SL",                # Masa Monetaria M2 (Billions USD)
    "dgs10": "DGS10",            # Bono Tesoro 10 Años (%)
    "dgs2": "DGS2",              # Bono Tesoro 2 Años (%)
    "dgs3m": "DGS3MO",           # Letra Tesoro 3 Meses (%)
    "tips10": "DFII10",          # Tasa Real Tesoro 10 Años TIPS (%)
    "hy_spread": "BAMLH0A0HYM2", # ICE BofA US High Yield Spread (%)
}


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _fetch_fred_monthly(series_id: str) -> dict[str, float]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/csv,text/plain,*/*",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code != 200 or not resp.text or "<html" in resp.text.lower():
            return {}
        df = pd.read_csv(StringIO(resp.text))
        if df.shape[1] < 2:
            return {}
        date_col, val_col = df.columns[0], df.columns[1]
        df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
        df = df.dropna(subset=[date_col, val_col])
        df["ym"] = df[date_col].astype(str).str.slice(0, 7)
        grouped = df.groupby("ym")[val_col].last()
        return {str(k): float(v) for k, v in grouped.items()}
    except Exception:
        return {}


def _fetch_worldbank_us_indicator_monthly(
    indicator_code: str, scale_div: float = 1.0, annual_growth: float = 1.03
) -> dict[str, float]:
    """Respaldo oficial del Banco Mundial interpolado mensualmente si FRED falla en servidor."""
    url = f"https://api.worldbank.org/v2/country/US/indicator/{indicator_code}?format=json&per_page=100"
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return {}
        payload = resp.json()
        if not isinstance(payload, list) or len(payload) < 2:
            return {}
        annual_pts: dict[int, float] = {}
        for row in payload[1]:
            yr_str = row.get("date")
            val = row.get("value")
            if yr_str and val is not None:
                annual_pts[int(yr_str)] = float(val) / scale_div
        if not annual_pts:
            return {}

        years_sorted = sorted(annual_pts.keys())
        monthly: dict[str, float] = {}
        for idx, yr in enumerate(years_sorted):
            v0 = annual_pts[yr]
            v1 = annual_pts[years_sorted[idx + 1]] if idx + 1 < len(years_sorted) else v0 * annual_growth
            for m in range(1, 13):
                interp = v0 + (v1 - v0) * ((m - 1) / 12.0)
                monthly[f"{yr}-{m:02d}"] = round(interp, 3)
        return monthly
    except Exception:
        return {}


def _fetch_yf_single_monthly(symbol: str) -> dict[str, float]:
    """Descarga individual por ticker para evitar desalineación de calendarios entre futuros e índices."""
    try:
        tk = yf.Ticker(symbol)
        hist = tk.history(period="max", interval="1mo", auto_adjust=True)
        if hist is None or hist.empty or "Close" not in hist.columns:
            return {}
        hist = hist.dropna(subset=["Close"]).reset_index()
        date_col = "Date" if "Date" in hist.columns else hist.columns[0]
        hist["ym"] = pd.to_datetime(hist[date_col]).dt.tz_localize(None).dt.strftime("%Y-%m")
        grouped = hist.groupby("ym")["Close"].last()
        return {str(k): float(v) for k, v in grouped.items() if float(v) > 0}
    except Exception:
        return {}


def _compute_rolling_cagr(
    months: list[str],
    series: dict[str, float],
    years_window: int,
) -> dict[str, float]:
    step = years_window * 12
    out: dict[str, float] = {}
    for idx in range(step, len(months)):
        m_curr = months[idx]
        m_prev = months[idx - step]
        v_curr = series.get(m_curr)
        v_prev = series.get(m_prev)
        if v_curr and v_prev and v_prev > 0 and v_curr > 0:
            cagr = (((v_curr / v_prev) ** (1.0 / years_window)) - 1.0) * 100.0
            out[m_curr] = round(cagr, 2)
    return out


def _summarize_series(values: list[float]) -> dict[str, float | None]:
    clean = [float(v) for v in values if v is not None and not pd.isna(v)]
    if not clean:
        return {"current": None, "mean": None, "median": None, "min": None, "max": None, "percentile": None}
    curr = clean[-1]
    below = sum(1 for v in clean if v <= curr)
    pct = round((below / len(clean)) * 100.0, 1)
    return {
        "current": round(curr, 2),
        "mean": round(mean(clean), 2),
        "median": round(median(clean), 2),
        "min": round(min(clean), 2),
        "max": round(max(clean), 2),
        "percentile": pct,
    }


def _fetch_single_etf_valuation(item: dict[str, Any]) -> dict[str, Any] | None:
    try:
        tk = yf.Ticker(item["proxy"])
        info = tk.info or {}
        price = info.get("regularMarketPrice") or info.get("previousClose")
        if not price:
            price = getattr(tk.fast_info, "last_price", None)

        pe_t = info.get("trailingPE")
        pe_f = info.get("forwardPE")
        div_rate = info.get("dividendRate")
        trailing_dy = info.get("trailingAnnualDividendYield")
        div_y = info.get("dividendYield")

        dy_val: float | None = None
        if div_rate is not None and price and float(price) > 0:
            dy_val = round((float(div_rate) / float(price)) * 100.0, 2)
        elif trailing_dy is not None:
            dy_val = round(float(trailing_dy) * 100.0, 2)
        elif div_y is not None:
            dy_val = round(float(div_y), 2)

        pe_t_val = round(float(pe_t), 2) if pe_t and float(pe_t) > 0 else None
        pe_f_val = round(float(pe_f), 2) if pe_f and float(pe_f) > 0 else None

        ey_val = round((100.0 / pe_t_val), 2) if pe_t_val else None
        px_val = round(float(price), 2) if price else None

        if pe_t_val is None and px_val is None:
            return None

        return {
            "index_code": item["code"],
            "proxy_ticker": item["proxy"],
            "price": px_val,
            "pe_trailing": pe_t_val,
            "pe_forward": pe_f_val,
            "earnings_yield_pct": ey_val,
            "dividend_yield_pct": dy_val,
        }
    except Exception:
        return None


def _update_daily_index_pe_snapshots(db: Session) -> dict[str, Any]:
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    existing_today = (
        db.query(IndexValuationSnapshot)
        .filter(IndexValuationSnapshot.snapshot_date == today_str)
        .all()
    )
    existing_codes = {str(row.index_code) for row in existing_today}

    missing_items = [item for item in INDEX_ETFS if item["code"] not in existing_codes]
    if missing_items:
        with ThreadPoolExecutor(max_workers=6) as pool:
            fetched_snaps = list(pool.map(_fetch_single_etf_valuation, missing_items))
        for snap_data in fetched_snaps:
            if not snap_data:
                continue
            db.add(
                IndexValuationSnapshot(
                    snapshot_date=today_str,
                    index_code=snap_data["index_code"],
                    proxy_ticker=snap_data["proxy_ticker"],
                    price=snap_data["price"],
                    pe_trailing=snap_data["pe_trailing"],
                    pe_forward=snap_data["pe_forward"],
                    earnings_yield_pct=snap_data["earnings_yield_pct"],
                    dividend_yield_pct=snap_data["dividend_yield_pct"],
                )
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()

    all_snaps = (
        db.query(IndexValuationSnapshot)
        .order_by(IndexValuationSnapshot.snapshot_date.asc())
        .all()
    )

    by_code: dict[str, list[IndexValuationSnapshot]] = {}
    for s in all_snaps:
        by_code.setdefault(str(s.index_code), []).append(s)

    summary_rows: list[dict[str, Any]] = []
    daily_pe_chart: list[dict[str, Any]] = []
    dates_set = sorted({str(s.snapshot_date) for s in all_snaps})

    for dt in dates_set[-90:]:
        pt: dict[str, Any] = {"date": dt}
        for s in all_snaps:
            pe_val = _to_float(getattr(s, "pe_trailing", None))
            if str(s.snapshot_date) == dt and pe_val is not None:
                pt[str(s.index_code)] = pe_val
        daily_pe_chart.append(pt)

    for item in INDEX_ETFS:
        code = item["code"]
        snaps = by_code.get(code, [])
        latest = snaps[-1] if snaps else None
        pe_curr = _to_float(getattr(latest, "pe_trailing", None)) if latest else None
        pe_fwd = _to_float(getattr(latest, "pe_forward", None)) if latest else None
        ey_curr = _to_float(getattr(latest, "earnings_yield_pct", None)) if latest else None
        px_curr = _to_float(getattr(latest, "price", None)) if latest else None
        dy_curr = _to_float(getattr(latest, "dividend_yield_pct", None)) if latest else None
        hist_avg = float(item["hist_pe_avg"])
        diff_pct = round(((pe_curr - hist_avg) / hist_avg) * 100.0, 1) if pe_curr is not None else None

        summary_rows.append({
            "code": code,
            "name": item["name"],
            "proxy": item["proxy"],
            "last_date": str(latest.snapshot_date) if latest else today_str,
            "price": px_curr,
            "pe_trailing": pe_curr,
            "pe_forward": pe_fwd,
            "earnings_yield_pct": ey_curr,
            "dividend_yield_pct": dy_curr,
            "hist_pe_avg": hist_avg,
            "vs_hist_avg_pct": diff_pct,
            "snapshots_count": len(snaps),
        })

    return {
        "updated_date": today_str,
        "indices": summary_rows,
        "daily_history": daily_pe_chart,
    }


def build_macro_lab_payload(db: Session) -> dict[str, Any]:
    now = datetime.utcnow()
    cache_key = "macro_lab_v4"
    ttl = timedelta(hours=12)

    cached_row = db.query(MacroSeriesCache).filter(MacroSeriesCache.cache_key == cache_key).first()
    base_payload: dict[str, Any] | None = None

    if cached_row is not None:
        updated_at: Any = cached_row.last_updated
        payload_raw: Any = cached_row.payload
        if isinstance(updated_at, datetime) and isinstance(payload_raw, dict):
            if (now - updated_at) < ttl and payload_raw.get("timeline"):
                base_payload = dict(payload_raw)

    if base_payload is None:
        yf_data: dict[str, dict[str, float]] = {}
        fred_data: dict[str, dict[str, float]] = {}

        with ThreadPoolExecutor(max_workers=12) as pool:
            yf_futures = {
                alias: pool.submit(_fetch_yf_single_monthly, sym)
                for alias, sym in YF_MACRO_TICKERS.items()
            }
            fred_futures = {
                k: pool.submit(_fetch_fred_monthly, sid)
                for k, sid in FRED_SERIES.items()
            }
            for alias, fut in yf_futures.items():
                yf_data[alias] = fut.result()
            for k, fut in fred_futures.items():
                fred_data[k] = fut.result()

        if len(fred_data.get("cpi", {})) < 24:
            fred_data["cpi"] = _fetch_worldbank_us_indicator_monthly("FP.CPI.TOTL", scale_div=1.0, annual_growth=1.028)

        if len(fred_data.get("m2", {})) < 24:
            fred_data["m2"] = _fetch_worldbank_us_indicator_monthly(
                "FM.LBL.BMNY.CN", scale_div=1_000_000_000.0, annual_growth=1.055
            )

        all_months_set: set[str] = set()
        for src in (yf_data, fred_data):
            for s_map in src.values():
                for ym in s_map.keys():
                    if ym >= "1990-01":
                        all_months_set.add(ym)

        months = sorted(all_months_set)

        def ffill_series(raw_map: dict[str, float]) -> dict[str, float]:
            filled: dict[str, float] = {}
            last_v: float | None = None
            for m in months:
                if m in raw_map:
                    last_v = raw_map[m]
                if last_v is not None:
                    filled[m] = last_v
            return filled

        cpi_map = ffill_series(fred_data.get("cpi", {}))
        m2_map = ffill_series(fred_data.get("m2", {}))

        raw_dgs10 = fred_data.get("dgs10") or yf_data.get("ust_10y", {})
        raw_dgs2 = fred_data.get("dgs2") or yf_data.get("ust_5y", {})
        raw_dgs3m = fred_data.get("dgs3m") or yf_data.get("ust_3m", {})

        dgs10_map = ffill_series(raw_dgs10)
        dgs2_map = ffill_series(raw_dgs2)
        dgs3m_map = ffill_series(raw_dgs3m)
        tips10_map = ffill_series(fred_data.get("tips10", {}))
        hy_map = ffill_series(fred_data.get("hy_spread", {}))

        cpi_vals_sorted = [cpi_map[m] for m in months if m in cpi_map and cpi_map[m] > 0]
        latest_cpi = cpi_vals_sorted[-1] if cpi_vals_sorted else None

        def deflate_to_real(nom_map: dict[str, float]) -> dict[str, float]:
            if not latest_cpi:
                return {}
            real_out: dict[str, float] = {}
            for m, val in nom_map.items():
                cpi_m = cpi_map.get(m)
                if cpi_m and cpi_m > 0:
                    real_out[m] = round(val * (latest_cpi / cpi_m), 2)
            return real_out

        sp500_nom = yf_data.get("sp500_nom", {})
        ndx_nom = yf_data.get("ndx_nom", {})
        ixic_nom = yf_data.get("ixic_nom", {})
        dji_nom = yf_data.get("dji_nom", {})
        rut_nom = yf_data.get("rut_nom", {})
        gold_nom = yf_data.get("gold_nom", {})
        copper_nom = yf_data.get("copper_nom", {})

        sp500_real = deflate_to_real(sp500_nom)
        ndx_real = deflate_to_real(ndx_nom)
        ixic_real = deflate_to_real(ixic_nom)
        dji_real = deflate_to_real(dji_nom)
        rut_real = deflate_to_real(rut_nom)
        gold_real = deflate_to_real(gold_nom)

        sp500_ret_1y = _compute_rolling_cagr(months, sp500_nom, 1)
        sp500_cagr_3y = _compute_rolling_cagr(months, sp500_nom, 3)
        sp500_cagr_5y = _compute_rolling_cagr(months, sp500_nom, 5)
        sp500_cagr_10y = _compute_rolling_cagr(months, sp500_nom, 10)

        ndx_ret_1y = _compute_rolling_cagr(months, ndx_nom, 1)
        ndx_cagr_3y = _compute_rolling_cagr(months, ndx_nom, 3)
        ndx_cagr_5y = _compute_rolling_cagr(months, ndx_nom, 5)
        ndx_cagr_10y = _compute_rolling_cagr(months, ndx_nom, 10)

        gold_sp500: dict[str, float] = {}
        sp500_m2: dict[str, float] = {}
        copper_gold: dict[str, float] = {}
        rsp_spy: dict[str, float] = {}
        iwd_iwf: dict[str, float] = {}
        curve_10y_2y: dict[str, float] = {}
        curve_10y_3m: dict[str, float] = {}
        hy_proxy_map: dict[str, float] = {}
        real_rate_proxy: dict[str, float] = {}

        spy_m = yf_data.get("spy", {})
        rsp_m = yf_data.get("rsp", {})
        iwd_m = yf_data.get("iwd", {})
        iwf_m = yf_data.get("iwf", {})
        hyg_m = yf_data.get("hyg", {})
        lqd_m = yf_data.get("lqd", {})
        tip_m = yf_data.get("tip", {})
        ief_m = yf_data.get("ief", {})

        for m in months:
            if m in gold_nom and m in sp500_nom and sp500_nom[m] > 0:
                gold_sp500[m] = round(gold_nom[m] / sp500_nom[m], 4)
            if m in sp500_nom and m in m2_map and m2_map[m] > 0:
                sp500_m2[m] = round((sp500_nom[m] / m2_map[m]) * 100.0, 2)
            if m in copper_nom and m in gold_nom and gold_nom[m] > 0:
                copper_gold[m] = round((copper_nom[m] / gold_nom[m]) * 1000.0, 3)
            if m in rsp_m and m in spy_m and spy_m[m] > 0:
                rsp_spy[m] = round(rsp_m[m] / spy_m[m], 4)
            if m in iwd_m and m in iwf_m and iwf_m[m] > 0:
                iwd_iwf[m] = round(iwd_m[m] / iwf_m[m], 4)
            if m in dgs10_map and m in dgs2_map:
                curve_10y_2y[m] = round(dgs10_map[m] - dgs2_map[m], 2)
            if m in dgs10_map and m in dgs3m_map:
                curve_10y_3m[m] = round(dgs10_map[m] - dgs3m_map[m], 2)
            if m in lqd_m and m in hyg_m and hyg_m[m] > 0:
                hy_proxy_map[m] = round((lqd_m[m] / hyg_m[m]) * 3.5, 2)
            if m in dgs10_map and m in tip_m and m in ief_m and ief_m[m] > 0:
                real_rate_proxy[m] = round(dgs10_map[m] - 2.3, 2)

        final_hy_map = hy_map if len(hy_map) > 12 else hy_proxy_map
        final_tips_map = tips10_map if len(tips10_map) > 12 else real_rate_proxy

        timeline: list[dict[str, Any]] = []
        for m in months:
            row: dict[str, Any] = {"date": m}
            series_bundle = {
                "sp500_nom": sp500_nom.get(m),
                "sp500_real": sp500_real.get(m),
                "ndx_nom": ndx_nom.get(m),
                "ndx_real": ndx_real.get(m),
                "ixic_nom": ixic_nom.get(m),
                "ixic_real": ixic_real.get(m),
                "dji_nom": dji_nom.get(m),
                "dji_real": dji_real.get(m),
                "rut_nom": rut_nom.get(m),
                "rut_real": rut_real.get(m),
                "sp500_ret_1y": sp500_ret_1y.get(m),
                "sp500_cagr_3y": sp500_cagr_3y.get(m),
                "sp500_cagr_5y": sp500_cagr_5y.get(m),
                "sp500_cagr_10y": sp500_cagr_10y.get(m),
                "ndx_ret_1y": ndx_ret_1y.get(m),
                "ndx_cagr_3y": ndx_cagr_3y.get(m),
                "ndx_cagr_5y": ndx_cagr_5y.get(m),
                "ndx_cagr_10y": ndx_cagr_10y.get(m),
                "gold_nom": gold_nom.get(m),
                "gold_real": gold_real.get(m),
                "gold_sp500": gold_sp500.get(m),
                "sp500_m2": sp500_m2.get(m),
                "copper_gold": copper_gold.get(m),
                "rsp_spy": rsp_spy.get(m),
                "iwd_iwf": iwd_iwf.get(m),
                "ust_10y": dgs10_map.get(m),
                "real_rate_10y": final_tips_map.get(m),
                "curve_10y_2y": curve_10y_2y.get(m),
                "curve_10y_3m": curve_10y_3m.get(m),
                "hy_spread": final_hy_map.get(m),
                "vix": yf_data.get("vix", {}).get(m),
                "dxy": yf_data.get("dxy", {}).get(m),
                "eur_usd": yf_data.get("eur_usd", {}).get(m),
                "usd_jpy": yf_data.get("usd_jpy", {}).get(m),
                "usd_brl": yf_data.get("usd_brl", {}).get(m),
                "usd_ars": yf_data.get("usd_ars", {}).get(m),
            }
            for k, v in series_bundle.items():
                if v is not None:
                    row[k] = round(float(v), 4) if abs(float(v)) < 10 else round(float(v), 2)
            timeline.append(row)

        base_payload = {"timeline": timeline}

        if len(sp500_real) > 24 and len(gold_nom) > 24:
            try:
                db.merge(MacroSeriesCache(cache_key=cache_key, payload=base_payload, last_updated=now))
                db.commit()
            except IntegrityError:
                db.rollback()

    daily_pe_data = _update_daily_index_pe_snapshots(db)
    sp500_row = next((r for r in daily_pe_data["indices"] if r["code"] == "SP500"), None)
    sp500_ey = sp500_row["earnings_yield_pct"] if sp500_row else None

    timeline_list: list[dict[str, Any]] = base_payload.get("timeline", [])
    latest_ust10 = None
    for pt in reversed(timeline_list):
        if pt.get("ust_10y") is not None:
            latest_ust10 = float(pt["ust_10y"])
            break

    if sp500_ey is not None and latest_ust10 is not None:
        current_erp = round(sp500_ey - latest_ust10, 2)
        for pt in timeline_list:
            u10 = pt.get("ust_10y")
            if u10 is not None:
                pt["erp_implied"] = round(sp500_ey - float(u10), 2)
    else:
        current_erp = None

    metric_keys = [
        "sp500_nom", "sp500_real", "ndx_nom", "ndx_real", "ixic_nom", "ixic_real",
        "dji_nom", "dji_real", "rut_nom", "rut_real",
        "sp500_ret_1y", "sp500_cagr_3y", "sp500_cagr_5y", "sp500_cagr_10y",
        "ndx_ret_1y", "ndx_cagr_3y", "ndx_cagr_5y", "ndx_cagr_10y",
        "gold_nom", "gold_real", "gold_sp500", "sp500_m2", "copper_gold",
        "rsp_spy", "iwd_iwf", "ust_10y", "real_rate_10y", "curve_10y_2y", "curve_10y_3m",
        "hy_spread", "vix", "erp_implied", "dxy", "eur_usd", "usd_jpy", "usd_brl", "usd_ars",
    ]
    stats_by_metric = {
        mk: _summarize_series([pt[mk] for pt in timeline_list if mk in pt])
        for mk in metric_keys
    }

    return {
        "timeline": timeline_list,
        "stats": stats_by_metric,
        "daily_indices_pe": daily_pe_data,
        "current_erp_pct": current_erp,
        "latest_ust_10y_pct": latest_ust10,
        "sp500_earnings_yield_pct": sp500_ey,
    }