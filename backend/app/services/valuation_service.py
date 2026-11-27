from datetime import datetime, timedelta
from statistics import mean, median
from typing import Any
import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.database import PriceHistoryCache, is_sqlite
from app.services.anomaly_detector import detect_anomalies
from app.services.company_service import get_raw_financials
from app.services.financial_parser import (
    build_ttm_series,
    detect_reporting_currency,
    extract_annual_metrics,
    extract_quarterly_metrics,
    is_foreign_adr_filer,
    normalize_historical_shares,
)
from app.core.yf_client import (
    _lookup_fx_multiplier,
    get_cached_market_snapshot,
    get_cached_estimates_and_guidance,
)

CRP_TABLE_UPDATED_AT = "2026-11"

_COUNTRY_RISK_PREMIUM_PCT: dict[str, float] = {
    "brazil": 2.5,
    "argentina": 11.5,
    "mexico": 1.5,
    "colombia": 2.2,
    "chile": 1.0,
    "peru": 1.5,
    "uruguay": 1.2,
    "china": 1.0,
    "taiwan": 0.6,
    "south korea": 0.6,
    "india": 1.8,
    "indonesia": 1.8,
    "thailand": 1.5,
    "philippines": 1.6,
    "malaysia": 1.2,
    "vietnam": 2.8,
    "israel": 0.9,
    "saudi arabia": 0.8,
    "poland": 0.9,
    "hungary": 1.3,
    "turkey": 4.5,
    "south africa": 2.5,
    "egypt": 5.5,
    "nigeria": 6.0,
}

_CURRENCY_RISK_PREMIUM_PCT: dict[str, float] = {
    "BRL": 2.5,
    "ARS": 11.5,
    "MXN": 1.5,
    "COP": 2.2,
    "CLP": 1.0,
    "PEN": 1.5,
    "UYU": 1.2,
    "CNY": 1.0,
    "RMB": 1.0,
    "TWD": 0.6,
    "KRW": 0.6,
    "INR": 1.8,
    "IDR": 1.8,
    "THB": 1.5,
    "PHP": 1.6,
    "MYR": 1.2,
    "VND": 2.8,
    "ILS": 0.9,
    "SAR": 0.8,
    "PLN": 0.9,
    "HUF": 1.3,
    "TRY": 4.5,
    "ZAR": 2.5,
    "EGP": 5.5,
    "NGN": 6.0,
}


def _estimate_country_risk_premium_pct(country: str | None, reporting_currency: str | None) -> float:
    c_key = str(country or "").strip().lower()
    if c_key in _COUNTRY_RISK_PREMIUM_PCT:
        return _COUNTRY_RISK_PREMIUM_PCT[c_key]
    curr_key = str(reporting_currency or "").strip().upper()
    return _CURRENCY_RISK_PREMIUM_PCT.get(curr_key, 0.0)


def _compute_split_factors_by_year(tk: yf.Ticker, years_range: list[str]) -> dict[str, float]:
    """
    Calcula para cada año calendario el factor acumulado de stock splits ocurridos
    DESPUÉS del 31/12 de ese año, para homogeneizar las acciones históricas pre-split
    de los 10-K con los precios ajustados por split de Yahoo Finance.
    """
    factors = {y: 1.0 for y in years_range}
    try:
        splits = tk.splits
        if splits is None or splits.empty:
            return factors
        splits_idx = pd.to_datetime(splits.index).tz_localize(None)
        for y in years_range:
            cutoff = datetime(int(y), 12, 31)
            mult = 1.0
            for dt, ratio in zip(splits_idx, splits.values):
                if dt > cutoff and float(ratio) > 0:
                    mult *= float(ratio)
            factors[y] = round(mult, 6)
    except Exception:
        pass
    return factors


def _get_annual_prices_and_splits(
    ticker_upper: str, years_range: list[str], db: Session
) -> tuple[dict[str, float], dict[str, float]]:
    now = datetime.utcnow()
    ttl = timedelta(hours=24)

    for rng in ("max", "10y"):
        row = (
            db.query(PriceHistoryCache)
            .filter(PriceHistoryCache.cache_key == f"{ticker_upper}:{rng}")
            .first()
        )
        if row is not None:
            updated_at: Any = row.last_updated
            payload: Any = row.payload
            if isinstance(updated_at, datetime) and isinstance(payload, dict):
                if (now - updated_at) < ttl:
                    candles = payload.get("seriesByMetric", {}).get("Price", [])
                    cached_splits = payload.get("splitFactorsByYear")
                    if candles and isinstance(cached_splits, dict):
                        by_year: dict[str, float] = {}
                        for c in candles:
                            yr = str(c.get("time", ""))[:4]
                            close_val = c.get("close")
                            if yr and isinstance(close_val, (int, float)) and close_val > 0:
                                by_year[yr] = float(close_val)
                        if by_year:
                            factors = {y: float(cached_splits.get(y, 1.0)) for y in years_range}
                            return by_year, factors

    tk = yf.Ticker(ticker_upper)
    hist = tk.history(period="10y", interval="1mo", auto_adjust=False)
    split_factors = _compute_split_factors_by_year(tk, years_range)

    if hist is None or hist.empty:
        return {}, split_factors

    hist = hist.dropna(subset=["Open", "High", "Low", "Close"]).reset_index()
    date_col = "Date" if "Date" in hist.columns else hist.columns[0]
    hist[date_col] = pd.to_datetime(hist[date_col]).dt.tz_localize(None)

    by_year = {}
    price_series: list[dict[str, Any]] = []
    for _, r in hist.iterrows():
        dt_str = r[date_col].strftime("%Y-%m-%d")
        c_val = float(r["Close"])
        by_year[dt_str[:4]] = c_val
        price_series.append({
            "time": dt_str,
            "open": round(float(r["Open"]), 2),
            "high": round(float(r["High"]), 2),
            "low": round(float(r["Low"]), 2),
            "close": round(c_val, 2),
            "volume": int(r["Volume"]) if pd.notna(r["Volume"]) else 0,
            "change": 0.0,
            "changePct": 0.0,
        })

    cache_key = f"{ticker_upper}:10y"
    payload_to_save = {
        "ticker": ticker_upper,
        "range": "10y",
        "interval": "1mo",
        "years": 10.0,
        "totalReturnPct": 0.0,
        "cagrPct": 0.0,
        "splitFactorsByYear": split_factors,
        "seriesByMetric": {"Price": price_series},
    }
    try:
        insert_fn = sqlite_insert if is_sqlite else pg_insert
        stmt = insert_fn(PriceHistoryCache).values(
            cache_key=cache_key,
            ticker=ticker_upper,
            range_key="10y",
            payload=payload_to_save,
            last_updated=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["cache_key"],
            set_={"payload": payload_to_save, "last_updated": now},
        )
        db.execute(stmt)
        db.commit()
    except Exception:
        db.rollback()

    return by_year, split_factors


def _safe_multiple(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0.0:
        return None
    val = num / den
    if abs(val) > 500:
        return None
    return round(val, 2)


def _detect_sector_profile(classification: dict[str, Any]) -> dict[str, Any]:
    sector = str(classification.get("sector") or "").lower()
    industry = str(classification.get("industry") or "").lower()
    sic_desc = str(classification.get("sic_description") or "").lower()
    combined = f"{sector} {industry} {sic_desc}"
    sic_raw = classification.get("sic")

    sic_int: int | None = None
    if sic_raw is not None:
        try:
            sic_int = int(str(sic_raw).strip())
        except ValueError:
            sic_int = None

    is_reit = (sic_int == 6798) or ("reit" in combined)

    is_financial = (
        not is_reit
        and (
            (sic_int is not None and 6000 <= sic_int <= 6499)
            or any(
                k in combined
                for k in ("financial", "bank", "depository", "insurance", "capital markets", "credit", "asset management")
            )
        )
    )

    if is_financial:
        return {
            "profile": "financial",
            "label": "Entidad Financiera / Bancaria",
            "primary_model": "Excess Return (ROE vs. Costo de Equity) & P/TBV",
            "rationale": (
                "En bancos y financieras la deuda es materia prima operativa y el CapEx tradicional "
                "no refleja reinversión. Se priorizan ROE, P/BV, P/TBV y generación de retorno excedente."
            ),
        }

    if is_reit:
        return {
            "profile": "reit",
            "label": "REIT / Inmobiliaria",
            "primary_model": "DCF sobre Flujo Operativo Ajustado (FFO proxy) & Dividend Yield",
            "rationale": (
                "La amortización contable de inmuebles deprime el Beneficio Neto GAAP; "
                "se prioriza la generación de caja operativa recurrente."
            ),
        }

    return {
        "profile": "standard",
        "label": "Corporativo Estándar / Crecimiento",
        "primary_model": "DCF en 2 Etapas (Expansión vs. Mantenimiento) + Doble Valor Terminal",
        "rationale": (
            "Se proyectan ingresos, márgenes operativos y reinversión de capital diferenciando "
            "la etapa de expansión del estado estacionario."
        ),
    }


def _analyze_trajectory_and_margins(
    valid_years: list[str],
    get_m: Any,
    estimates_data: dict[str, Any],
    fallback_ebit_margin_pct: float = 15.0,
    fx_rate: float = 1.0,
) -> dict[str, Any]:
    rev_est = estimates_data.get("revenue_estimate", {})
    eps_est = estimates_data.get("earnings_estimate", {})
    growth_est = estimates_data.get("growth_estimates", {})
    consensus_summary = estimates_data.get("consensus_summary", {})

    yoy_rates: list[float] = []
    for i in range(1, len(valid_years)):
        prev_r = get_m("Ingresos Totales", valid_years[i - 1])
        curr_r = get_m("Ingresos Totales", valid_years[i])
        if prev_r > 0 and curr_r > 0:
            yoy = ((curr_r - prev_r) / prev_r) * 100.0
            if -40.0 <= yoy <= 85.0:
                yoy_rates.append(round(yoy, 2))

    recent_yoy = yoy_rates[-3:] if len(yoy_rates) >= 3 else yoy_rates
    hist_avg_growth = round(mean(recent_yoy), 2) if recent_yoy else 8.0
    spread_yoy = (max(recent_yoy) - min(recent_yoy)) if len(recent_yoy) >= 2 else 99.0
    is_consistent_hist = len(recent_yoy) >= 2 and spread_yoy <= 8.0 and hist_avg_growth > 0

    g_rev_0y = rev_est.get("0y", {}).get("growth")
    g_rev_1y = rev_est.get("+1y", {}).get("growth")
    g_eps_0y = eps_est.get("0y", {}).get("growth")
    g_eps_1y = eps_est.get("+1y", {}).get("growth")

    rev_0y_pct = round(float(g_rev_0y) * 100.0, 2) if g_rev_0y is not None else consensus_summary.get("revenue_growth_yoy_pct")
    rev_1y_pct = round(float(g_rev_1y) * 100.0, 2) if g_rev_1y is not None else rev_0y_pct
    eps_0y_pct = round(float(g_eps_0y) * 100.0, 2) if g_eps_0y is not None else consensus_summary.get("earnings_growth_yoy_pct")
    eps_1y_pct = round(float(g_eps_1y) * 100.0, 2) if g_eps_1y is not None else eps_0y_pct

    g_5y_raw = None
    for period_k in ("+5y", "5y"):
        if period_k in growth_est:
            row_g = growth_est[period_k]
            g_5y_raw = row_g.get("stockTrend") or row_g.get("stock")
            if g_5y_raw is not None:
                break
    # V5: stockTrend de Yahoo es crecimiento esperado de EPS a 5Y, no de ventas.
    # No mezclarlo en forward_candidates de crecimiento de ingresos.
    consensus_5y_eps_pct = round(float(g_5y_raw) * 100.0, 2) if g_5y_raw is not None else None

    forward_candidates = [v for v in (rev_0y_pct, rev_1y_pct) if v is not None]
    forward_avg_growth = round(mean(forward_candidates), 2) if forward_candidates else hist_avg_growth

    if forward_candidates:
        weight_hist = 0.45 if is_consistent_hist else 0.30
        blended_growth = (hist_avg_growth * weight_hist) + (forward_avg_growth * (1.0 - weight_hist))
    else:
        blended_growth = hist_avg_growth

    recommended_rev_growth = round(min(max(blended_growth, -5.0), 35.0), 1)

    margin_history: list[dict[str, Any]] = []
    for y in valid_years[-5:]:
        rev = get_m("Ingresos Totales", y)
        if rev > 0:
            gm = round((get_m("Beneficio Bruto", y) / rev) * 100.0, 1)
            ebit_y = get_m("Beneficio Operativo", y)
            om = round((ebit_y / rev) * 100.0, 1) if ebit_y != 0.0 else round(fallback_ebit_margin_pct, 1)
            nm = round((get_m("Beneficio Neto", y) / rev) * 100.0, 1)
            margin_history.append({
                "year": y,
                "gross_margin_pct": gm,
                "operating_margin_pct": om,
                "net_margin_pct": nm,
            })

    gm_delta = 0.0
    om_delta = 0.0
    nm_delta = 0.0
    if len(margin_history) >= 2:
        first_m = margin_history[0]
        last_m = margin_history[-1]
        gm_delta = round(last_m["gross_margin_pct"] - first_m["gross_margin_pct"], 1)
        om_delta = round(last_m["operating_margin_pct"] - first_m["operating_margin_pct"], 1)
        nm_delta = round(last_m["net_margin_pct"] - first_m["net_margin_pct"], 1)

    leverage_signal = "stable"
    leverage_label = "Márgenes estables (crecimiento alineado de ventas y beneficios)"
    margin_step_pct_yr = 0.0

    if rev_1y_pct is not None and eps_1y_pct is not None:
        spread_eps_rev = eps_1y_pct - rev_1y_pct
        if spread_eps_rev >= 2.5:
            leverage_signal = "expanding"
            leverage_label = (
                f"Expansión esperada de márgenes: el consenso proyecta BPA +{eps_1y_pct:.1f}% "
                f"vs. Ventas +{rev_1y_pct:.1f}% (apalancamiento operativo positivo)."
            )
            # Escala proporcional al apalancamiento operativo esperado (0.30 pp/año base hasta 2.50 pp/año)
            margin_step_pct_yr = round(min(max(0.30 + (spread_eps_rev - 2.5) * 0.08, 0.30), 2.50), 2)
        elif spread_eps_rev <= -2.5:
            leverage_signal = "compressing"
            leverage_label = (
                f"Compresión esperada de márgenes: el consenso proyecta BPA +{eps_1y_pct:.1f}% "
                f"vs. Ventas +{rev_1y_pct:.1f}% (presión por costos, CapEx o depreciación)."
            )
            margin_step_pct_yr = -0.30

    hist_ebit_margins = [float(m["operating_margin_pct"]) for m in margin_history if m.get("operating_margin_pct") is not None]
    hist_med_ebit_margin_pct = round(median(hist_ebit_margins), 2) if len(hist_ebit_margins) >= 2 else None

    period_labels = {
        "0q": "Trimestre Actual (0Q)",
        "+1q": "Próximo Trimestre (+1Q)",
        "0y": "Año Fiscal Actual (0Y)",
        "+1y": "Próximo Año Fiscal (+1Y)",
    }
    consensus_rows: list[dict[str, Any]] = []
    for p_key, p_label in period_labels.items():
        r_row = rev_est.get(p_key, {})
        e_row = eps_est.get(p_key, {})
        if r_row or e_row:
            rev_avg_raw = r_row.get("avg")
            rev_low_raw = r_row.get("low")
            rev_high_raw = r_row.get("high")
            rev_g_raw = r_row.get("growth")
            eps_g_raw = e_row.get("growth")

            consensus_rows.append({
                "period_key": p_key,
                "period_label": p_label,
                "rev_avg_mm": round((float(rev_avg_raw) * fx_rate) / 1_000_000.0, 2) if rev_avg_raw is not None else None,
                "rev_low_mm": round((float(rev_low_raw) * fx_rate) / 1_000_000.0, 2) if rev_low_raw is not None else None,
                "rev_high_mm": round((float(rev_high_raw) * fx_rate) / 1_000_000.0, 2) if rev_high_raw is not None else None,
                "rev_growth_pct": round(float(rev_g_raw) * 100.0, 2) if rev_g_raw is not None else None,
                "rev_analysts": r_row.get("numberOfAnalysts"),
                "eps_avg": round(float(e_row["avg"]) * fx_rate, 2) if e_row.get("avg") is not None else None,
                "eps_low": round(float(e_row["low"]) * fx_rate, 2) if e_row.get("low") is not None else None,
                "eps_high": round(float(e_row["high"]) * fx_rate, 2) if e_row.get("high") is not None else None,
                "eps_growth_pct": round(float(eps_g_raw) * 100.0, 2) if eps_g_raw is not None else None,
                "eps_analysts": e_row.get("numberOfAnalysts"),
            })

    return {
        "recent_yoy_rates": recent_yoy,
        "hist_avg_growth_pct": hist_avg_growth,
        "is_consistent_hist": is_consistent_hist,
        "forward_avg_growth_pct": forward_avg_growth,
        "consensus_5y_pct": consensus_5y_eps_pct,
        "consensus_5y_eps_pct": consensus_5y_eps_pct,
        "recommended_rev_growth_pct": recommended_rev_growth,
        "margin_history": margin_history,
        "margin_deltas": {
            "gross_margin_delta_pct": gm_delta,
            "operating_margin_delta_pct": om_delta,
            "net_margin_delta_pct": nm_delta,
        },
        "leverage_signal": leverage_signal,
        "leverage_label": leverage_label,
        "margin_step_pct_yr": margin_step_pct_yr,
        "hist_med_ebit_margin_pct": hist_med_ebit_margin_pct,
        "consensus_rows": consensus_rows,
        "sec_8k_filings": estimates_data.get("sec_8k_guidance_filings", []),
    }


def _audit_anomalies_and_adjustments(
    valid_years: list[str],
    get_m: Any,
    current_mcap_mm: float | None,
    current_ev_mm: float | None,
    ltm_multiples: dict[str, float | None],
    is_financial: bool = False,
    fallback_ebit_margin_pct: float = 15.0,
    quarterly_rows: list[dict[str, Any]] | None = None,
    fx_rate: float = 1.0,
    ttm_data: dict[str, Any] | None = None,
    reporting_currency: str = "USD",
    shares_mm: float | None = None,
    sector: str = "",
    dcf_growth_pct: float | None = None,
    hist_roe_pcts: list[float] | None = None,
    current_roe_pct: float | None = None,
) -> dict[str, Any]:
    return detect_anomalies(
        valid_years=valid_years,
        get_m=get_m,
        ttm_data=ttm_data,
        quarterly_rows=quarterly_rows,
        fx_rate=fx_rate,
        reporting_currency=reporting_currency,
        current_mcap_mm=current_mcap_mm,
        current_ev_mm=current_ev_mm,
        shares_mm=shares_mm,
        ltm_multiples=ltm_multiples,
        is_financial=is_financial,
        sector=sector,
        fallback_ebit_margin_pct=fallback_ebit_margin_pct,
        dcf_growth_pct=dcf_growth_pct,
        hist_roe_pcts=hist_roe_pcts,
        current_roe_pct=current_roe_pct,
    )


def _legacy_audit_unused(
    valid_years: list[str],
    get_m: Any,
    current_mcap_mm: float | None,
    current_ev_mm: float | None,
    ltm_multiples: dict[str, float | None],
    is_financial: bool = False,
    fallback_ebit_margin_pct: float = 15.0,
    quarterly_rows: list[dict[str, Any]] | None = None,
    fx_rate: float = 1.0,
) -> dict[str, Any]:
    if not valid_years:
        return {
            "has_anomalies": False,
            "flags": [],
            "comparisons": [],
            "adjusted_fcf_mm": 0.0,
            "capex_current_pct": 10.0,
            "capex_maint_pct": 8.0,
            "ebit_margin_pct": round(fallback_ebit_margin_pct, 2),
            "tax_rate_pct": 21.0,
            "normalized_ebit_margin_pct": round(fallback_ebit_margin_pct, 2),
            "normalized_tax_rate_pct": 21.0,
            "normalized_ebit_mm": 0.0,
            "normalized_net_inc_mm": 0.0,
            "normalized_fcf_mm": 0.0,
            "rev_growth_yoy_pct": None,
        }

    latest_y = valid_years[-1]
    prev_years = valid_years[:-1] if len(valid_years) > 1 else valid_years

    rev_curr = get_m("Ingresos Totales", latest_y)
    ebit_curr = get_m("Beneficio Operativo", latest_y)
    if ebit_curr == 0.0 and rev_curr > 0 and fallback_ebit_margin_pct > 0:
        ebit_curr = rev_curr * (fallback_ebit_margin_pct / 100.0)

    int_exp_curr = abs(get_m("Gastos por Intereses", latest_y))
    effective_operating_profit = ebit_curr
    if not is_financial and ebit_curr > 0 and int_exp_curr > (ebit_curr * 0.20):
        effective_operating_profit = max(ebit_curr - int_exp_curr, 0.0)

    da_curr = get_m("Depreciación y Amortización", latest_y)
    net_inc_curr = get_m("Beneficio Neto", latest_y)
    ebt_curr = get_m("Beneficio antes de Impuestos", latest_y)
    tax_curr = get_m("Gasto por Impuesto a las Ganancias", latest_y)
    cfo_curr = get_m("Efectivo de Operaciones (CFO)", latest_y)
    capex_curr = abs(get_m("Gastos de capital (CapEx)", latest_y))
    fcf_curr = get_m("Flujo de caja libre (FCF)", latest_y)
    sbc_curr = abs(get_m("Compensación basada en acciones", latest_y))
    wc_curr = get_m("Cambios en el capital de trabajo", latest_y)
    non_op_curr = get_m("Ingresos (Gastos) No Operativos", latest_y) + get_m("Ganancia/Pérdida por venta de activos", latest_y)

    eff_tax = 0.21
    if ebt_curr > 0 and tax_curr > 0:
        eff_tax = min(max(tax_curr / ebt_curr, 0.10), 0.35)

    ebit_margin_pct = (
        round((effective_operating_profit / rev_curr) * 100.0, 2)
        if (rev_curr > 0 and effective_operating_profit != 0.0)
        else round(fallback_ebit_margin_pct, 2)
    )
    capex_curr_pct = round((capex_curr / rev_curr) * 100.0, 2) if rev_curr > 0 else 10.0

    hist_capex_ratios = [
        abs(get_m("Gastos de capital (CapEx)", y)) / get_m("Ingresos Totales", y)
        for y in prev_years
        if get_m("Ingresos Totales", y) > 0 and get_m("Gastos de capital (CapEx)", y) != 0.0
    ]
    med_capex_ratio = median(hist_capex_ratios) if hist_capex_ratios else (da_curr / rev_curr if rev_curr > 0 else 0.08)
    capex_maint_pct = round(med_capex_ratio * 100.0, 2)

    flags: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []

    adjusted_fcf = fcf_curr
    adjusted_net_inc = net_inc_curr

    if not is_financial and rev_curr > 0 and capex_curr > 0:
        maint_capex_mm = max(rev_curr * med_capex_ratio, da_curr * 0.85)
        excess_capex_mm = capex_curr - maint_capex_mm

        if excess_capex_mm > 0 and (
            (med_capex_ratio > 0 and (capex_curr / rev_curr) > med_capex_ratio * 1.45)
            or (da_curr > 0 and capex_curr > da_curr * 1.5)
        ):
            adjusted_fcf = round(cfo_curr - maint_capex_mm, 2)
            flags.append({
                "code": "CAPEX_EXPANSION",
                "severity": "warning",
                "title": "Ciclo extraordinario de inversión (CapEx de crecimiento)",
                "detail": (
                    f"El CapEx del último ejercicio (US$ {capex_curr:,.2f} MM, {capex_curr_pct:.1f}% de ventas) "
                    f"supera ampliamente la mediana histórica ({capex_maint_pct:.1f}% de ventas). "
                    f"El excedente de expansión estimado es de US$ {excess_capex_mm:,.2f} MM, deprimiendo el FCF reportado."
                ),
                "impact_mm": round(-excess_capex_mm, 2),
            })

            rep_pfcf = ltm_multiples.get("pfcf")
            adj_pfcf = _safe_multiple(current_mcap_mm, adjusted_fcf)
            if rep_pfcf is not None and adj_pfcf is not None:
                comparisons.append({
                    "metric": "P / FCF (LTM)",
                    "reported": f"{rep_pfcf:.2f}x",
                    "adjusted": f"{adj_pfcf:.2f}x",
                    "note": "Normalizando CapEx a tasa histórica",
                })

            rep_evfcf = ltm_multiples.get("ev_fcf")
            adj_evfcf = _safe_multiple(current_ev_mm, adjusted_fcf)
            if rep_evfcf is not None and adj_evfcf is not None:
                comparisons.append({
                    "metric": "EV / FCF (LTM)",
                    "reported": f"{rep_evfcf:.2f}x",
                    "adjusted": f"{adj_evfcf:.2f}x",
                    "note": "Normalizando CapEx a tasa histórica",
                })

    if not is_financial and abs(ebit_curr) > 0:
        nopat_curr = ebit_curr * (1.0 - eff_tax)
        non_op_gap = net_inc_curr - nopat_curr
        if abs(non_op_curr) > abs(ebit_curr) * 0.15 or abs(non_op_gap) > abs(ebit_curr) * 0.25:
            extra_item = non_op_curr * (1.0 - eff_tax) if abs(non_op_curr) > abs(ebit_curr) * 0.10 else non_op_gap
            adjusted_net_inc = round(net_inc_curr - extra_item, 2)
            direction = "inflando" if extra_item > 0 else "reduciendo"
            flags.append({
                "code": "NON_OPERATING_SHOCK",
                "severity": "info" if extra_item > 0 else "warning",
                "title": "Partidas no operativas materiales debajo del EBIT",
                "detail": (
                    f"Se detectan resultados no operativos / extraordinarios por US$ {extra_item:,.2f} MM netos, "
                    f"{direction} el Beneficio Neto reportado (US$ {net_inc_curr:,.2f} MM) respecto al resultado operativo recurrente."
                ),
                "impact_mm": round(extra_item, 2),
            })

            rep_pe = ltm_multiples.get("pe")
            adj_pe = _safe_multiple(current_mcap_mm, adjusted_net_inc)
            if rep_pe is not None and adj_pe is not None:
                comparisons.append({
                    "metric": "P / E (LTM)",
                    "reported": f"{rep_pe:.2f}x",
                    "adjusted": f"{adj_pe:.2f}x",
                    "note": "Excluyendo impacto no operativo neto",
                })

    if not is_financial and cfo_curr > 0 and (sbc_curr / cfo_curr) > 0.25:
        fcf_ex_sbc = round(fcf_curr - sbc_curr, 2)
        flags.append({
            "code": "HIGH_SBC",
            "severity": "warning",
            "title": "Alta dilución por Compensación Basada en Acciones (SBC)",
            "detail": (
                f"La SBC asciende a US$ {sbc_curr:,.2f} MM ({(sbc_curr / cfo_curr) * 100:.1f}% del CFO). "
                f"Descontando este costo económico real, el FCF ex-SBC sería US$ {fcf_ex_sbc:,.2f} MM."
            ),
            "impact_mm": round(-sbc_curr, 2),
        })
        adj_pfcf_sbc = _safe_multiple(current_mcap_mm, fcf_ex_sbc)
        rep_pfcf = ltm_multiples.get("pfcf")
        if rep_pfcf is not None and adj_pfcf_sbc is not None:
            comparisons.append({
                "metric": "P / FCF (ex-SBC)",
                "reported": f"{rep_pfcf:.2f}x",
                "adjusted": f"{adj_pfcf_sbc:.2f}x",
                "note": "Restando SBC como salida económica real",
            })

    if not is_financial and abs(cfo_curr) > 0 and abs(wc_curr) > abs(cfo_curr) * 0.20:
        direction_wc = "consumo" if wc_curr < 0 else "liberación puntual"
        flags.append({
            "code": "WORKING_CAPITAL_SWING",
            "severity": "info",
            "title": "Variación extraordinaria en Capital de Trabajo",
            "detail": (
                f"El capital de trabajo tuvo un {direction_wc} de US$ {abs(wc_curr):,.2f} MM "
                f"({(abs(wc_curr) / abs(cfo_curr)) * 100:.1f}% del CFO), alterando transitoriamente la conversión de caja."
            ),
            "impact_mm": round(wc_curr, 2),
        })

    # --- DETECTOR GENERAL DE RUBROS OPERATIVOS / FISCALES ANUALES Y TRIMESTRALES ---
    rev_prev_y = get_m("Ingresos Totales", prev_years[-1]) if len(valid_years) > 1 else 0.0
    rev_growth_yoy = (
        round(((rev_curr - rev_prev_y) / rev_prev_y) * 100.0, 2)
        if (len(valid_years) > 1 and rev_prev_y > 0 and rev_curr > 0)
        else None
    )

    hist_ebit_margins = [
        (get_m("Beneficio Operativo", y) / get_m("Ingresos Totales", y)) * 100.0
        for y in prev_years
        if get_m("Ingresos Totales", y) > 0 and get_m("Beneficio Operativo", y) != 0.0
    ]
    med_ebit_margin = round(median(hist_ebit_margins), 2) if hist_ebit_margins else ebit_margin_pct

    hist_gm = [
        (get_m("Beneficio Bruto", y) / get_m("Ingresos Totales", y)) * 100.0
        for y in prev_years
        if get_m("Ingresos Totales", y) > 0 and get_m("Beneficio Bruto", y) > 0
    ]
    gp_curr = get_m("Beneficio Bruto", latest_y)
    gm_curr = round((gp_curr / rev_curr) * 100.0, 2) if (rev_curr > 0 and gp_curr > 0) else None
    if not is_financial and gm_curr is not None and len(hist_gm) >= 2:
        med_gm = round(median(hist_gm), 2)
        gm_diff = round(gm_curr - med_gm, 2)
        if abs(gm_diff) >= 2.5:
            gm_impact_mm = round((gm_diff / 100.0) * rev_curr, 2)
            flags.append({
                "code": "GROSS_MARGIN_SHIFT",
                "severity": "warning" if gm_diff < 0 else "info",
                "title": (
                    "Compresión extraordinaria de Margen Bruto"
                    if gm_diff < 0
                    else "Expansión extraordinaria de Margen Bruto"
                ),
                "detail": (
                    f"El margen bruto del último ejercicio ({gm_curr:.1f}%) se desvió {gm_diff:+.1f} pp "
                    f"respecto a la mediana de años previos ({med_gm:.1f}%)."
                ),
                "impact_mm": gm_impact_mm,
            })

    # Salto extraordinario en Gastos Operativos (SG&A + R&D o GP - EBIT)
    opex_curr = max(gp_curr - effective_operating_profit, 0.0) if (gp_curr > 0) else 0.0
    hist_opex_ratios = [
        ((get_m("Beneficio Bruto", y) - get_m("Beneficio Operativo", y)) / get_m("Ingresos Totales", y)) * 100.0
        for y in prev_years
        if get_m("Ingresos Totales", y) > 0 and get_m("Beneficio Bruto", y) > 0
    ]
    if not is_financial and rev_curr > 0 and opex_curr > 0 and len(hist_opex_ratios) >= 2:
        opex_curr_pct = round((opex_curr / rev_curr) * 100.0, 2)
        med_opex_pct = round(median(hist_opex_ratios), 2)
        opex_diff = round(opex_curr_pct - med_opex_pct, 2)
        if opex_diff >= 2.5:
            opex_excess_mm = round((opex_diff / 100.0) * rev_curr, 2)
            flags.append({
                "code": "OPEX_SPIKE",
                "severity": "warning",
                "title": "Salto extraordinario en Gastos Operativos (SG&A / Expansión)",
                "detail": (
                    f"Los gastos operativos sobre ventas ({opex_curr_pct:.1f}%) superan en +{opex_diff:.1f} pp "
                    f"su mediana histórica ({med_opex_pct:.1f}%), absorbiendo US$ {opex_excess_mm:,.2f} MM de margen."
                ),
                "impact_mm": round(-opex_excess_mm, 2),
            })

    # Tasa impositiva efectiva atípica
    hist_tax_rates = [
        (get_m("Gasto por Impuesto a las Ganancias", y) / get_m("Beneficio antes de Impuestos", y)) * 100.0
        for y in prev_years
        if get_m("Beneficio antes de Impuestos", y) > 0 and get_m("Gasto por Impuesto a las Ganancias", y) > 0
    ]
    med_tax_pct = round(min(max(median(hist_tax_rates), 10.0), 35.0), 1) if hist_tax_rates else round(eff_tax * 100.0, 1)
    raw_tax_curr_pct = round((tax_curr / ebt_curr) * 100.0, 1) if (ebt_curr > 0 and tax_curr >= 0) else round(eff_tax * 100.0, 1)
    if not is_financial and len(hist_tax_rates) >= 2 and abs(raw_tax_curr_pct - med_tax_pct) >= 7.0 and ebt_curr > 0:
        tax_impact_mm = round(ebt_curr * ((med_tax_pct - raw_tax_curr_pct) / 100.0), 2)
        flags.append({
            "code": "TAX_RATE_ANOMALY",
            "severity": "info",
            "title": "Tasa impositiva efectiva atípica (cargo/crédito puntual)",
            "detail": (
                f"La tasa impositiva efectiva ({raw_tax_curr_pct:.1f}%) difiere significativamente de su mediana histórica ({med_tax_pct:.1f}%)."
            ),
            "impact_mm": tax_impact_mm,
        })

    # Compresión de margen operativo EBIT vs mediana histórica (distinguiendo reinversión con crecimiento vs deterioro)
    norm_ebit_margin_pct = ebit_margin_pct
    normalized_ebit_mm = round(effective_operating_profit, 2)
    if not is_financial and rev_curr > 0 and len(hist_ebit_margins) >= 2 and (med_ebit_margin - ebit_margin_pct) >= 2.5:
        norm_ebit_margin_pct = med_ebit_margin
        normalized_ebit_mm = round(rev_curr * (med_ebit_margin / 100.0), 2)
        ebit_gap_mm = round(normalized_ebit_mm - effective_operating_profit, 2)
        is_reinvest = rev_growth_yoy is not None and rev_growth_yoy >= 8.0
        flags.append({
            "code": "MARGIN_COMPRESSION_REINVESTMENT" if is_reinvest else "MARGIN_COMPRESSION_DECLINE",
            "severity": "warning",
            "title": (
                "Compresión de margen operativo por reinversión / expansión"
                if is_reinvest
                else "Compresión de margen operativo respecto a mediana histórica"
            ),
            "detail": (
                f"El margen EBIT actual ({ebit_margin_pct:.1f}%) está {med_ebit_margin - ebit_margin_pct:.1f} pp por debajo "
                f"de su mediana histórica ({med_ebit_margin:.1f}%)"
                + (
                    f" mientras los ingresos crecen {rev_growth_yoy:+.1f}% YoY (señal de inversión en market share)."
                    if is_reinvest
                    else "."
                )
            ),
            "impact_mm": round(-ebit_gap_mm, 2),
        })

        rep_ev_ebit = ltm_multiples.get("ev_ebit")
        adj_ev_ebit = _safe_multiple(current_ev_mm, normalized_ebit_mm)
        if rep_ev_ebit is not None and adj_ev_ebit is not None:
            comparisons.append({
                "metric": "EV / EBIT (LTM)",
                "reported": f"{rep_ev_ebit:.2f}x",
                "adjusted": f"{adj_ev_ebit:.2f}x",
                "note": f"Normalizando margen EBIT ({ebit_margin_pct:.1f}% → {med_ebit_margin:.1f}%)",
            })

    # Chequeo trimestral reciente (Run-Rate) para detectar cambios en trimestres antes del cierre anual
    if not is_financial and quarterly_rows:
        q_rev_row = next((r for r in quarterly_rows if r.get("Métrica") == "Ingresos Totales"), None)
        q_ebit_row = next((r for r in quarterly_rows if r.get("Métrica") == "Beneficio Operativo"), None)
        if q_rev_row and q_ebit_row:
            def _as_float(v: Any) -> float | None:
                if v is None or isinstance(v, bool):
                    return None
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None

            q_cols = [
                k for k in q_rev_row.keys()
                if k not in ("Métrica", "Sección", "is_pct")
                and (_as_float(q_rev_row.get(k)) or 0.0) > 0
                and _as_float(q_ebit_row.get(k)) is not None
            ]
            if len(q_cols) >= 4:
                q_margins = [
                    (k, (_as_float(q_ebit_row[k]) * fx_rate) / (_as_float(q_rev_row[k]) * fx_rate) * 100.0)
                    for k in q_cols
                ]
                recent_q = q_margins[-1]
                prior_med_q = median([m for _, m in q_margins[:-1]])
                q_diff = round(recent_q[1] - prior_med_q, 2)
                if abs(q_diff) >= 2.5:
                    last_q_rev_mm = float(q_rev_row[recent_q[0]]) * fx_rate
                    flags.append({
                        "code": "QUARTERLY_RUN_RATE_SHIFT",
                        "severity": "warning" if q_diff < 0 else "info",
                        "title": f"Desvío notable en último trimestre ({recent_q[0]})",
                        "detail": (
                            f"El margen EBIT del trimestre {recent_q[0]} ({recent_q[1]:.1f}%) muestra una variación de "
                            f"{q_diff:+.1f} pp frente a la mediana de trimestres previos ({prior_med_q:.1f}%)."
                        ),
                        "impact_mm": round((q_diff / 100.0) * last_q_rev_mm, 2),
                    })

    # Beneficio neto y FCF normalizados combinados (sin circunstancias extraordinarias)
    norm_tax_dec = med_tax_pct / 100.0
    normalized_net_inc_mm = round(
        max(normalized_ebit_mm - int_exp_curr, 0.0) * (1.0 - norm_tax_dec)
        if normalized_ebit_mm > 0
        else adjusted_net_inc,
        2,
    )
    maint_capex_final_mm = (
        max(rev_curr * med_capex_ratio, da_curr * 0.85)
        if (rev_curr > 0 and capex_curr > 0)
        else capex_curr
    )
    normalized_fcf_mm = round(
        (normalized_ebit_mm * (1.0 - norm_tax_dec) + da_curr - maint_capex_final_mm)
        if rev_curr > 0
        else adjusted_fcf,
        2,
    )

    if norm_ebit_margin_pct > ebit_margin_pct and current_mcap_mm:
        rep_pe = ltm_multiples.get("pe")
        norm_pe = _safe_multiple(current_mcap_mm, normalized_net_inc_mm)
        if rep_pe is not None and norm_pe is not None and abs(norm_pe - rep_pe) >= 0.5:
            comparisons.append({
                "metric": "P / E (Normalizado)",
                "reported": f"{rep_pe:.2f}x",
                "adjusted": f"{norm_pe:.2f}x",
                "note": f"Margen EBIT {med_ebit_margin:.1f}% + tasa {med_tax_pct:.1f}%",
            })

    return {
        "has_anomalies": len(flags) > 0,
        "flags": flags,
        "comparisons": comparisons,
        "adjusted_fcf_mm": round(adjusted_fcf, 2),
        "capex_current_pct": capex_curr_pct,
        "capex_maint_pct": max(capex_maint_pct, 2.0),
        "ebit_margin_pct": ebit_margin_pct,
        "tax_rate_pct": round(eff_tax * 100.0, 1),
        "normalized_ebit_margin_pct": norm_ebit_margin_pct,
        "normalized_tax_rate_pct": med_tax_pct,
        "normalized_ebit_mm": normalized_ebit_mm,
        "normalized_net_inc_mm": normalized_net_inc_mm,
        "normalized_fcf_mm": normalized_fcf_mm,
        "rev_growth_yoy_pct": rev_growth_yoy,
    }


def _compute_reverse_dcf(
    is_financial: bool,
    dcf_inputs: dict[str, Any],
    financial_inputs: dict[str, Any],
    hist_avg_growth_pct: float,
    recommended_growth_pct: float,
) -> dict[str, Any]:
    """
    DCF Inverso (Expectations Investing):
    Resuelve por bisección numérica la tasa de crecimiento anual implícita en la
    cotización actual del mercado (a 5 y 10 años).
    """
    if is_financial:
        cur_price = float(financial_inputs.get("current_price") or 0.0)
        bvps = float(financial_inputs.get("bvps") or 0.0)
        base_roe_pct = float(financial_inputs.get("roe_pct") or 12.0)
        ke = float(financial_inputs.get("cost_of_equity_pct") or 9.5) / 100.0
        payout = float(financial_inputs.get("payout_ratio_pct") or 35.0) / 100.0
        retention = max(1.0 - payout, 0.10)

        def eval_bank_price(roe_decimal: float, horizon_yrs: int) -> float:
            if bvps <= 0:
                return 0.0
            g1 = min(max(roe_decimal * retention, -0.25), 0.25)
            g_term = min(max(g1, 0.0), 0.045)
            if ke <= g_term:
                return 0.0
            bv = bvps
            pv_exc = 0.0
            for yr in range(1, horizon_yrs + 1):
                pv_exc += (bv * (roe_decimal - ke)) / ((1.0 + ke) ** yr)
                bv *= 1.0 + g1
            term_roe = ke + (roe_decimal - ke) * 0.5
            tv = (bv * (term_roe - ke)) / (ke - g_term)
            return bvps + pv_exc + tv / ((1.0 + ke) ** horizon_yrs)

        def solve_bank_implied(horizon_yrs: int) -> dict[str, Any]:
            if cur_price <= 0 or bvps <= 0:
                return {
                    "solvable": False,
                    "implied_growth_pct": None,
                    "implied_roe_pct": None,
                    "note": "Datos patrimoniales insuficientes para resolver el modelo inverso.",
                }
            lo, hi = -0.35, 0.60
            p_lo = eval_bank_price(lo, horizon_yrs)
            p_hi = eval_bank_price(hi, horizon_yrs)
            if cur_price <= p_lo:
                roe_sol = lo
            elif cur_price >= p_hi:
                roe_sol = hi
            else:
                for _ in range(60):
                    mid = (lo + hi) / 2.0
                    if eval_bank_price(mid, horizon_yrs) < cur_price:
                        lo = mid
                    else:
                        hi = mid
                roe_sol = (lo + hi) / 2.0

            implied_bv_growth = round(roe_sol * retention * 100.0, 1)
            return {
                "solvable": True,
                "implied_growth_pct": implied_bv_growth,
                "implied_roe_pct": round(roe_sol * 100.0, 1),
                "note": f"Exige un ROE sostenible de {roe_sol * 100.0:.1f}% (crecimiento patrimonial de {implied_bv_growth:.1f}% anual).",
            }

        res_5y = solve_bank_implied(5)
        res_10y = solve_bank_implied(10)
        imp_5y = res_5y.get("implied_growth_pct")
        expected_bank_g = round(base_roe_pct * retention, 1)
        gap_vs_expected = round(imp_5y - expected_bank_g, 1) if imp_5y is not None else None

        if gap_vs_expected is None:
            regime = "indeterminate"
            verdict = "No se pudo determinar la expectativa implícita para esta entidad."
        elif gap_vs_expected >= 3.0:
            regime = "demanding"
            verdict = (
                f"Expectativas exigentes: el precio actual descuenta un crecimiento patrimonial de "
                f"{imp_5y:.1f}% anual (+{gap_vs_expected:.1f} pp por encima de su generación orgánica actual de {expected_bank_g:.1f}%)."
            )
        elif gap_vs_expected <= -2.5:
            regime = "conservative"
            verdict = (
                f"Expectativas conservadoras (margen de seguridad): el mercado solo exige {imp_5y:.1f}% anual "
                f"({gap_vs_expected:.1f} pp debajo de su capacidad orgánica de {expected_bank_g:.1f}%)."
            )
        else:
            regime = "aligned"
            verdict = (
                f"Expectativas alineadas: la cotización descuenta {imp_5y:.1f}% de expansión patrimonial anual, "
                f"en línea con su rentabilidad operativa actual ({expected_bank_g:.1f}%)."
            )

        bank_iv = round(eval_bank_price(base_roe_pct / 100.0, 5), 2) if bvps > 0 else 0.0
        bank_upside = round(((bank_iv - cur_price) / cur_price) * 100.0, 1) if (cur_price > 0 and bank_iv > 0) else None

        return {
            "mode": "financial",
            "model_label": "Excess Return Inverso (ROE y Crecimiento Patrimonial Implícito)",
            "current_price": round(cur_price, 2),
            "intrinsic_value_per_share": bank_iv,
            "upside_pct": bank_upside,
            "horizon_5y": res_5y,
            "horizon_10y": res_10y,
            "benchmarks": {
                "hist_growth_pct": round(hist_avg_growth_pct, 1),
                "expected_growth_pct": expected_bank_g,
                "base_roe_pct": round(base_roe_pct, 1),
                "cost_of_equity_pct": round(ke * 100.0, 1),
                "payout_ratio_pct": round(payout * 100.0, 1),
            },
            "gap_vs_expected_pp": gap_vs_expected,
            "regime": regime,
            "verdict": verdict,
        }

    cur_price = float(dcf_inputs.get("current_price") or 0.0)
    rev0 = float(dcf_inputs.get("revenue_base_mm") or 0.0)
    shares = float(dcf_inputs.get("shares_mm") or 0.0)
    net_debt = float(dcf_inputs.get("net_debt_mm") or 0.0)
    ebit_m = float(dcf_inputs.get("ebit_margin_pct") or 15.0) / 100.0
    tax_r = float(dcf_inputs.get("tax_rate_pct") or 21.0) / 100.0
    da_p = float(dcf_inputs.get("da_sales_pct") or 8.0) / 100.0
    capex1 = float(dcf_inputs.get("capex_expansion_pct") or 12.0) / 100.0
    capex_t = float(dcf_inputs.get("capex_maintenance_pct") or 8.0) / 100.0
    wacc = float(dcf_inputs.get("suggested_wacc_pct") or 9.0) / 100.0
    exit_m = float(dcf_inputs.get("exit_multiple_default") or 18.0)
    margin_step = float(dcf_inputs.get("margin_step_pct_yr") or 0.0) / 100.0
    nwc_pct = float(dcf_inputs.get("nwc_pct_of_delta_rev") or 0.02)
    g_term = 0.03

    def eval_corp_price(g_decimal: float, horizon_yrs: int, tv_mode: str = "blend") -> float:
        if rev0 <= 0 or shares <= 0 or wacc <= g_term:
            return 0.0
        rv = rev0
        pv1 = 0.0
        last_margin = ebit_m
        for yr in range(1, horizon_yrs + 1):
            prev_rv = rv
            g_yr = g_decimal if yr <= 3 else g_decimal + ((g_term - g_decimal) * (yr - 3)) / 2.0
            rv *= 1.0 + g_yr
            delta_nwc = max(rv - prev_rv, 0.0) * nwc_pct
            step_yr = min(yr, 5)
            m_yr = min(max(ebit_m + margin_step * step_yr, -0.20), 0.65)
            last_margin = m_yr
            fcf_y = rv * (m_yr * (1.0 - tax_r) + da_p - capex1) - delta_nwc
            pv1 += fcf_y / ((1.0 + wacc) ** yr)

        rv_next = rv * (1.0 + g_term)
        delta_nwc_term = max(rv_next - rv, 0.0) * nwc_pct
        fcf_next = rv_next * (last_margin * (1.0 - tax_r) + da_p - capex_t) - delta_nwc_term
        tv_gordon = fcf_next / (wacc - g_term)
        fcf_last_norm = rv * (last_margin * (1.0 - tax_r) + da_p - capex_t)
        tv_mult = fcf_last_norm * exit_m

        if tv_mode == "gordon":
            tv = tv_gordon
        elif tv_mode == "multiple":
            tv = tv_mult
        else:
            tv = 0.5 * (tv_gordon + tv_mult)

        return (pv1 + tv / ((1.0 + wacc) ** horizon_yrs) - net_debt) / shares

    def solve_corp_implied(horizon_yrs: int) -> dict[str, Any]:
        if cur_price <= 0 or rev0 <= 0 or shares <= 0:
            return {
                "solvable": False,
                "implied_growth_pct": None,
                "implied_growth_gordon_pct": None,
                "implied_growth_mult_pct": None,
                "note": "Faltan datos operativos o de capitalización para resolver el crecimiento implícito.",
            }

        def bisect(mode: str) -> tuple[float, bool]:
            lo, hi = -0.25, 0.85
            p_lo = eval_corp_price(lo, horizon_yrs, mode)
            p_hi = eval_corp_price(hi, horizon_yrs, mode)
            if p_hi <= 0:
                return 0.0, False
            if cur_price <= p_lo:
                return lo, True
            if cur_price >= p_hi:
                return hi, False
            for _ in range(60):
                mid = (lo + hi) / 2.0
                if eval_corp_price(mid, horizon_yrs, mode) < cur_price:
                    lo = mid
                else:
                    hi = mid
            return (lo + hi) / 2.0, True

        g_blend, ok_b = bisect("blend")
        g_gord, _ = bisect("gordon")
        g_mult, _ = bisect("multiple")

        if not ok_b and eval_corp_price(0.85, horizon_yrs, "blend") <= 0:
            return {
                "solvable": False,
                "implied_growth_pct": None,
                "implied_growth_gordon_pct": None,
                "implied_growth_mult_pct": None,
                "note": "Con el margen operativo y CapEx actual el FCF proyectado es negativo; requiere expansión de márgenes.",
            }

        g_b_pct = round(g_blend * 100.0, 1)
        g_g_pct = round(g_gord * 100.0, 1)
        g_m_pct = round(g_mult * 100.0, 1)

        return {
            "solvable": True,
            "implied_growth_pct": g_b_pct,
            "implied_growth_gordon_pct": g_g_pct,
            "implied_growth_mult_pct": g_m_pct,
            "note": (
                f"El precio actual descuenta un crecimiento anual de ventas de {g_b_pct:.1f}% "
                f"(rango {min(g_g_pct, g_m_pct):.1f}% – {max(g_g_pct, g_m_pct):.1f}% según método terminal)."
            ),
        }

    res_5y = solve_corp_implied(5)
    res_10y = solve_corp_implied(10)
    imp_5y = res_5y.get("implied_growth_pct")
    gap_vs_expected = round(imp_5y - recommended_growth_pct, 1) if imp_5y is not None else None
    gap_vs_hist = round(imp_5y - hist_avg_growth_pct, 1) if imp_5y is not None else None

    if imp_5y is None:
        regime = "indeterminate"
        verdict = "Con los márgenes actuales la empresa no cubre la valuación solo con crecimiento de ventas; el mercado descuenta mejora estructural de márgenes."
    elif gap_vs_expected is not None and gap_vs_expected >= 3.5:
        regime = "demanding"
        verdict = (
            f"Expectativas exigentes: el mercado descuenta {imp_5y:.1f}% de crecimiento anual a 5 años "
            f"(+{gap_vs_expected:.1f} pp por encima de la proyección base de {recommended_growth_pct:.1f}%)."
        )
    elif gap_vs_expected is not None and gap_vs_expected <= -2.5:
        regime = "conservative"
        verdict = (
            f"Expectativas conservadoras (margen de seguridad): la cotización solo exige {imp_5y:.1f}% anual "
            f"({gap_vs_expected:.1f} pp por debajo de la proyección base de {recommended_growth_pct:.1f}%)."
        )
    else:
        regime = "aligned"
        verdict = (
            f"Expectativas razonables: el precio descuenta {imp_5y:.1f}% de crecimiento anual, "
            f"alineado con la proyección ponderada ({recommended_growth_pct:.1f}%) y su historia ({hist_avg_growth_pct:.1f}%)."
        )

    corp_iv = round(eval_corp_price(recommended_growth_pct / 100.0, 5, "blend"), 2) if (rev0 > 0 and shares > 0) else 0.0
    corp_upside = round(((corp_iv - cur_price) / cur_price) * 100.0, 1) if (cur_price > 0 and corp_iv > 0) else None

    return {
        "mode": "standard",
        "model_label": "DCF Inverso 2 Etapas (Crecimiento Anual Implícito en Precio)",
        "current_price": round(cur_price, 2),
        "intrinsic_value_per_share": corp_iv,
        "upside_pct": corp_upside,
        "horizon_5y": res_5y,
        "horizon_10y": res_10y,
        "benchmarks": {
            "hist_growth_pct": round(hist_avg_growth_pct, 1),
            "expected_growth_pct": round(recommended_growth_pct, 1),
            "ebit_margin_pct": round(ebit_m * 100.0, 1),
            "wacc_pct": round(wacc * 100.0, 1),
            "exit_multiple": round(exit_m, 1),
        },
        "gap_vs_expected_pp": gap_vs_expected,
        "gap_vs_hist_pp": gap_vs_hist,
        "regime": regime,
        "verdict": verdict,
    }


def build_valuation_report(ticker_symbol: str, db: Session) -> dict[str, Any]:
    ticker_upper = ticker_symbol.upper()

    raw_facts = get_raw_financials(ticker_upper, db)
    is_foreign_adr = is_foreign_adr_filer(raw_facts)
    try:
        annual_rows = extract_annual_metrics(raw_facts)
    except ValueError:
        annual_rows = []
    try:
        quarterly_rows = extract_quarterly_metrics(raw_facts)
    except Exception:
        quarterly_rows = []

    market_snapshot = get_cached_market_snapshot(ticker_upper, db)
    estimates_data = get_cached_estimates_and_guidance(ticker_upper, db)

    current_year = datetime.now().year
    years_range = [str(y) for y in range(current_year - 6, current_year + 1)]
    annual_prices, split_factors = _get_annual_prices_and_splits(ticker_upper, years_range, db)

    classification = estimates_data.get("classification", {})
    sector_routing = _detect_sector_profile(classification)
    is_financial = sector_routing["profile"] == "financial"

    info: dict[str, Any] = market_snapshot.get("info", {})
    sec_fb: dict[str, Any] = market_snapshot.get("sec_fundamentals") or {}
    reporting_currency = detect_reporting_currency(raw_facts)
    if reporting_currency == "USD" and info.get("financialCurrency"):
        reporting_currency = str(info.get("financialCurrency")).upper()
    yf_fx_rate = float(market_snapshot.get("fx_rate") or 1.0)
    cached_sec_fx = float(sec_fb.get("sec_fx_to_usd") or 0.0)
    stale_sec_fb_fx = False
    if reporting_currency != "USD" and (cached_sec_fx <= 0.0 or cached_sec_fx == 1.0):
        sec_fx_rate = yf_fx_rate if yf_fx_rate != 1.0 else _lookup_fx_multiplier(reporting_currency, "USD")
        stale_sec_fb_fx = True
    else:
        sec_fx_rate = float(cached_sec_fx or yf_fx_rate or 1.0)

    current_price = float(market_snapshot.get("price") or 0.0)
    current_shares_mm = float(market_snapshot.get("shares_mm") or sec_fb.get("shares_out_mm") or 0.0)
    current_net_debt_mm = float(market_snapshot.get("net_debt_mm") or 0.0)

    current_mcap_mm = round(current_price * current_shares_mm, 2) if (current_price > 0 and current_shares_mm > 0) else None
    current_ev_mm = round(current_mcap_mm + current_net_debt_mm, 2) if current_mcap_mm is not None else None

    ebit_margin_raw = info.get("operatingMargins")
    if ebit_margin_raw is not None:
        fallback_ebit_margin_pct = round(float(ebit_margin_raw) * 100.0, 2)
    elif sec_fb.get("ebit_mm") and sec_fb.get("revenue_mm") and float(sec_fb["revenue_mm"]) > 0:
        fallback_ebit_margin_pct = round((float(sec_fb["ebit_mm"]) / float(sec_fb["revenue_mm"])) * 100.0, 2)
    else:
        fallback_ebit_margin_pct = 15.0

    lookup: dict[str, dict[str, float]] = {}
    for row in annual_rows:
        m = row.get("Métrica", "")
        is_share_metric = "Acciones" in m or "BPA" in m or row.get("is_pct")
        mult = 1.0 if is_share_metric else sec_fx_rate
        lookup[m] = {y: float(row.get(y, 0.0) or 0.0) * mult for y in years_range}

    def get_m(metric: str, y: str) -> float:
        return lookup.get(metric, {}).get(y, 0.0)

    yearly_multiples: dict[str, dict[str, float | None]] = {}
    valid_years: list[str] = []
    roe_series: list[float] = []

    for y in years_range:
        rev = get_m("Ingresos Totales", y)
        gp = get_m("Beneficio Bruto", y)
        ebit = get_m("Beneficio Operativo", y)
        if ebit == 0.0 and rev > 0 and fallback_ebit_margin_pct:
            ebit = rev * (fallback_ebit_margin_pct / 100.0)

        da = get_m("Depreciación y Amortización", y)
        ebitda = ebit + da if (ebit != 0.0 or da != 0.0) else 0.0
        net_inc = get_m("Beneficio Neto", y)
        fcf = get_m("Flujo de caja libre (FCF)", y)
        equity = get_m("Patrimonio neto", y)
        goodwill = get_m("Fondo de comercio", y)
        intangibles = get_m("Activos intangibles", y)

        tangible_equity = (equity - goodwill - intangibles) if equity > 0 else 0.0

        cash = get_m("Efectivo y equivalentes", y) + get_m("Inversiones a corto plazo", y)
        debt = get_m("Deuda a corto plazo", y) + get_m("Deuda a largo plazo", y)
        net_debt = debt - cash

        shares_raw_y = get_m("Acciones en Circulación (Diluidas)", y)
        if shares_raw_y <= 0:
            shares_raw_y = get_m("Acciones en Circulación (Básicas)", y)
        shares = normalize_historical_shares(
            shares_raw=shares_raw_y,
            split_factor=split_factors.get(y, 1.0),
            current_shares_mm=current_shares_mm,
            is_foreign_adr=is_foreign_adr,
        )

        price_y = annual_prices.get(y)

        if rev == 0.0 and equity == 0.0:
            continue

        valid_years.append(y)
        if equity > 0 and net_inc != 0.0:
            roe_series.append(round((net_inc / equity) * 100.0, 2))

        mcap_y = round(price_y * shares, 2) if (price_y is not None and shares > 0) else None
        ev_y = round(mcap_y + net_debt, 2) if mcap_y is not None else None
        fcf_yield = round((fcf / mcap_y) * 100.0, 2) if (mcap_y is not None and mcap_y > 0 and fcf != 0.0) else None

        yearly_multiples[y] = {
            "ev_sales_ntm": None,
            "pe_ntm": None,
            "ev_sales": _safe_multiple(ev_y, rev),
            "ps": _safe_multiple(mcap_y, rev),
            "ev_ebitda": _safe_multiple(ev_y, ebitda),
            "ev_ebit": _safe_multiple(ev_y, ebit),
            "ev_gp": _safe_multiple(ev_y, gp),
            "pe": _safe_multiple(mcap_y, net_inc),
            "pb": _safe_multiple(mcap_y, equity) if equity > 0 else None,
            "ptbv": _safe_multiple(mcap_y, tangible_equity) if tangible_equity > 0 else None,
            "ev_fcf": _safe_multiple(ev_y, fcf),
            "pfcf": _safe_multiple(mcap_y, fcf),
            "fcf_yield": fcf_yield,
            "factor_price": round(price_y, 2) if price_y is not None else None,
            "factor_ev": ev_y,
            "factor_mcap": mcap_y,
        }

    latest_y_sec = valid_years[-1] if valid_years else None
    rev_ltm = ((info.get("totalRevenue") or 0) * yf_fx_rate) / 1_000_000.0
    if rev_ltm <= 0 and latest_y_sec:
        rev_ltm = get_m("Ingresos Totales", latest_y_sec)

    gp_ltm = ((info.get("grossProfits") or 0) * yf_fx_rate) / 1_000_000.0
    if gp_ltm <= 0 and latest_y_sec:
        gp_ltm = get_m("Beneficio Bruto", latest_y_sec)

    ebitda_ltm = ((info.get("ebitda") or 0) * yf_fx_rate) / 1_000_000.0
    if ebitda_ltm <= 0:
        ebitda_ltm = float(sec_fb.get("ebitda_mm") or 0.0)

    ebit_ltm = (rev_ltm * float(ebit_margin_raw)) if (rev_ltm > 0 and ebit_margin_raw is not None) else float(sec_fb.get("ebit_mm") or 0.0)

    net_inc_ltm = ((info.get("netIncomeToCommon") or 0) * yf_fx_rate) / 1_000_000.0
    if net_inc_ltm == 0.0 and latest_y_sec:
        net_inc_ltm = get_m("Beneficio Neto", latest_y_sec)

    latest_sec_fcf = get_m("Flujo de caja libre (FCF)", latest_y_sec) if latest_y_sec else 0.0
    latest_sec_rev = get_m("Ingresos Totales", latest_y_sec) if latest_y_sec else 0.0
    latest_sec_da = get_m("Depreciación y Amortización", latest_y_sec) if latest_y_sec else 0.0
    yf_ocf = ((info.get("operatingCashflow") or 0) * yf_fx_rate) / 1_000_000.0
    yf_fcf = ((info.get("freeCashflow") or 0) * yf_fx_rate) / 1_000_000.0

    # V1: TTM real de 4 trimestres aislados para flujos (reemplaza latest_sec_fcf anual)
    ttm_data = build_ttm_series(raw_facts, fx_rate=sec_fx_rate, quarterly_rows=quarterly_rows)
    ttm_flows = ttm_data.get("ttm") or {}
    ttm_fcf = float(ttm_flows.get("Flujo de caja libre (FCF)") or 0.0) if ttm_data.get("is_complete") else 0.0
    if ttm_data.get("is_complete") and ttm_fcf == 0.0:
        ttm_cfo = float(ttm_flows.get("Efectivo de Operaciones (CFO)") or 0.0)
        ttm_capex = abs(float(ttm_flows.get("Gastos de capital (CapEx)") or 0.0))
        if ttm_cfo != 0.0:
            ttm_fcf = round(ttm_cfo - ttm_capex, 2)

    fcf_ltm = ttm_fcf if ttm_fcf != 0.0 else (yf_fcf if yf_fcf != 0.0 else (latest_sec_fcf if latest_sec_fcf != 0.0 else yf_ocf))
    if ttm_data.get("is_complete") and float(ttm_flows.get("Ingresos Totales") or 0.0) > 0 and rev_ltm <= 0:
        rev_ltm = float(ttm_flows["Ingresos Totales"])
    rev_base = rev_ltm if rev_ltm > 0 else latest_sec_rev

    latest_equity_mm = get_m("Patrimonio neto", latest_y_sec) if latest_y_sec else float(sec_fb.get("book_equity_mm") or 0.0)
    pb_raw = info.get("priceToBook")
    pb_ltm = round(float(pb_raw), 2) if pb_raw is not None else (_safe_multiple(current_mcap_mm, latest_equity_mm) if latest_equity_mm > 0 else None)
    if latest_equity_mm <= 0 and pb_ltm and pb_ltm > 0 and current_mcap_mm:
        latest_equity_mm = round(current_mcap_mm / pb_ltm, 2)

    fcf_yield_ltm = round((fcf_ltm / current_mcap_mm) * 100.0, 2) if (current_mcap_mm and current_mcap_mm > 0 and fcf_ltm != 0.0) else None

    rev_growth = info.get("revenueGrowth")
    rev_ntm = rev_ltm * (1.0 + float(rev_growth)) if (rev_ltm > 0 and rev_growth is not None) else None
    pe_ntm_raw = info.get("forwardPE")
    pe_ntm = round(float(pe_ntm_raw), 2) if pe_ntm_raw is not None else None
    if pe_ntm is None and current_price > 0 and info.get("forwardEps"):
        fwd_eps = float(info["forwardEps"])
        if fwd_eps != 0:
            pe_ntm = round(current_price / fwd_eps, 2)

    latest_goodwill_ltm = get_m("Fondo de comercio", latest_y_sec) if latest_y_sec else 0.0
    latest_intangibles_ltm = get_m("Activos intangibles", latest_y_sec) if latest_y_sec else 0.0
    tangible_eq_ltm = latest_equity_mm - latest_goodwill_ltm - latest_intangibles_ltm
    ptbv_ltm = _safe_multiple(current_mcap_mm, tangible_eq_ltm) if tangible_eq_ltm > 0 else (
        yearly_multiples[latest_y_sec]["ptbv"] if latest_y_sec else None
    )

    ltm_multiples: dict[str, float | None] = {
        "ev_sales_ntm": _safe_multiple(current_ev_mm, rev_ntm),
        "pe_ntm": pe_ntm,
        "ev_sales": _safe_multiple(current_ev_mm, rev_ltm),
        "ps": _safe_multiple(current_mcap_mm, rev_ltm),
        "ev_ebitda": _safe_multiple(current_ev_mm, ebitda_ltm),
        "ev_ebit": _safe_multiple(current_ev_mm, ebit_ltm),
        "ev_gp": _safe_multiple(current_ev_mm, gp_ltm),
        "pe": _safe_multiple(current_mcap_mm, net_inc_ltm),
        "pb": pb_ltm,
        "ptbv": ptbv_ltm,
        "ev_fcf": _safe_multiple(current_ev_mm, fcf_ltm),
        "pfcf": _safe_multiple(current_mcap_mm, fcf_ltm),
        "fcf_yield": fcf_yield_ltm,
        "factor_price": round(current_price, 2) if current_price > 0 else None,
        "factor_ev": current_ev_mm,
        "factor_mcap": current_mcap_mm,
    }

    audit = _audit_anomalies_and_adjustments(
        valid_years=valid_years,
        get_m=get_m,
        current_mcap_mm=current_mcap_mm,
        current_ev_mm=current_ev_mm,
        ltm_multiples=ltm_multiples,
        is_financial=is_financial,
        fallback_ebit_margin_pct=fallback_ebit_margin_pct,
        quarterly_rows=quarterly_rows,
        fx_rate=sec_fx_rate,
        ttm_data=ttm_data,
        reporting_currency=reporting_currency,
        shares_mm=current_shares_mm if current_shares_mm > 0 else None,
        sector=str(classification.get("sector") or ""),
        hist_roe_pcts=roe_series,
        current_roe_pct=round(float(info["returnOnEquity"]) * 100.0, 2) if info.get("returnOnEquity") is not None else None,
    )

    trajectory = _analyze_trajectory_and_margins(
        valid_years=valid_years,
        get_m=get_m,
        estimates_data=estimates_data,
        fallback_ebit_margin_pct=fallback_ebit_margin_pct,
        fx_rate=sec_fx_rate,
    )

    if is_financial:
        metric_definitions = [
            {"key": "pe_ntm", "label": "NTM Price / Earnings (P/E)", "suffix": "x", "section": "Múltiplos Futuros (NTM)"},
            {"key": "pe", "label": "Precio / Beneficio (P/E)", "suffix": "x", "section": "Múltiplos Bancarios y Patrimoniales"},
            {"key": "pb", "label": "Precio / Valor Libros (P/BV)", "suffix": "x", "section": "Múltiplos Bancarios y Patrimoniales"},
            {"key": "ptbv", "label": "Precio / Valor Contable Tangible (P/TBV)", "suffix": "x", "section": "Múltiplos Bancarios y Patrimoniales"},
            {"key": "ps", "label": "Precio / Ingresos Financieros (P/S)", "suffix": "x", "section": "Múltiplos Bancarios y Patrimoniales"},
            {"key": "factor_price", "label": "Precio de cierre (US$)", "suffix": "", "section": "Price Factors"},
            {"key": "factor_mcap", "label": "Capitalización Bursátil (MM)", "suffix": "", "section": "Price Factors"},
        ]
    else:
        metric_definitions = [
            {"key": "ev_sales_ntm", "label": "EV / Ingresos NTM", "suffix": "x", "section": "Múltiplos Futuros (NTM)"},
            {"key": "pe_ntm", "label": "NTM Price / Earnings (P/E)", "suffix": "x", "section": "Múltiplos Futuros (NTM)"},
            {"key": "ev_sales", "label": "EV / Ventas (LTM)", "suffix": "x", "section": "Trailing Multiples (EV)"},
            {"key": "ev_ebitda", "label": "EV / EBITDA (LTM)", "suffix": "x", "section": "Trailing Multiples (EV)"},
            {"key": "ev_ebit", "label": "EV / EBIT (LTM)", "suffix": "x", "section": "Trailing Multiples (EV)"},
            {"key": "ev_gp", "label": "EV / Beneficio Bruto (LTM)", "suffix": "x", "section": "Trailing Multiples (EV)"},
            {"key": "ev_fcf", "label": "EV / Flujo de Caja Libre (LTM)", "suffix": "x", "section": "Trailing Multiples (EV)"},
            {"key": "ps", "label": "Precio / Ventas (P/S)", "suffix": "x", "section": "Trailing Multiples (Equity)"},
            {"key": "pe", "label": "Precio / Beneficio (P/E)", "suffix": "x", "section": "Trailing Multiples (Equity)"},
            {"key": "pb", "label": "Precio / Valor Libros (P/BV)", "suffix": "x", "section": "Trailing Multiples (Equity)"},
            {"key": "ptbv", "label": "Precio / Valor Contable Tangible (P/TBV)", "suffix": "x", "section": "Trailing Multiples (Equity)"},
            {"key": "pfcf", "label": "Precio / Flujo de Caja Libre (P/FCF)", "suffix": "x", "section": "Trailing Multiples (Equity)"},
            {"key": "fcf_yield", "label": "FCF Yield %", "suffix": "%", "section": "Trailing Multiples (Equity)"},
            {"key": "factor_price", "label": "Precio de cierre (US$)", "suffix": "", "section": "Price Factors"},
            {"key": "factor_ev", "label": "Valor Empresarial Total (MM)", "suffix": "", "section": "Price Factors"},
            {"key": "factor_mcap", "label": "Capitalización Bursátil (MM)", "suffix": "", "section": "Price Factors"},
        ]

    table_rows: list[dict[str, Any]] = []
    med_by_key: dict[str, float | None] = {}

    for m_def in metric_definitions:
        k = m_def["key"]
        hist_vals = [
            yearly_multiples[y][k]
            for y in valid_years
            if yearly_multiples[y][k] is not None
        ]
        last_5 = [float(v) for v in hist_vals[-5:] if v is not None]
        avg_5y = round(mean(last_5), 2) if last_5 else None
        med_5y = round(median(last_5), 2) if last_5 else None
        med_by_key[k] = med_5y

        row_obj: dict[str, Any] = {
            "section": m_def["section"],
            "metric": m_def["label"],
            "suffix": m_def["suffix"],
            "ltm": ltm_multiples[k],
            "avg_5y": avg_5y,
            "med_5y": med_5y,
        }
        for y in valid_years:
            row_obj[y] = yearly_multiples[y][k]

        table_rows.append(row_obj)

    da_ltm_src = (
        float(ttm_flows.get("Depreciación y Amortización") or 0.0)
        if ttm_data.get("is_complete") and float(ttm_flows.get("Depreciación y Amortización") or 0.0) > 0
        else latest_sec_da
    )
    da_sales_pct = round((da_ltm_src / rev_base) * 100.0, 2) if rev_base > 0 else 8.0

    # V6: Múltiplo de salida basado en mediana histórica propia (no circular al EV de hoy)
    med_ev_fcf = med_by_key.get("ev_fcf")
    med_ev_ebitda = med_by_key.get("ev_ebitda")
    raw_exit = med_ev_fcf or med_ev_ebitda or 18.0
    exit_ev_fcf_default = min(max(float(raw_exit), 12.0), 28.0)

    rf_pct = 4.25
    try:
        from app.models.database import MacroSeriesCache

        macro_row = db.query(MacroSeriesCache).filter(MacroSeriesCache.cache_key == "macro_lab_v1").first()
        macro_payload = getattr(macro_row, "payload", None) if macro_row else None
        if isinstance(macro_payload, dict):
            tl = macro_payload.get("timeline") or []
            for pt in reversed(tl):
                u10 = pt.get("ust_10y") if isinstance(pt, dict) else None
                if isinstance(u10, (int, float)) and 1.5 <= float(u10) <= 9.0:
                    rf_pct = round(float(u10), 2)
                    break
    except Exception:
        rf_pct = 4.25

    crp_pct = _estimate_country_risk_premium_pct(info.get("country"), reporting_currency)
    beta_val = float(info.get("beta") or 1.0)
    cost_of_equity_pct = round(
        min(max(rf_pct + beta_val * 5.0 + crp_pct, 8.0 + crp_pct * 0.7), 14.5 + crp_pct),
        1,
    )
    latest_y_for_debt = valid_years[-1] if valid_years else None
    debt_from_bs = (
        (get_m("Deuda a corto plazo", latest_y_for_debt) + get_m("Deuda a largo plazo", latest_y_for_debt))
        if latest_y_for_debt
        else 0.0
    )
    raw_fb_debt = float(sec_fb.get("total_debt_mm") or 0.0)
    if stale_sec_fb_fx and raw_fb_debt > 0.0:
        raw_fb_debt = raw_fb_debt * sec_fx_rate
    total_debt_mm = max(float(raw_fb_debt or debt_from_bs or 0.0), 0.0)
    eff_tax_rate = float(sec_fb.get("effective_tax_rate") or 0.21)
    if current_mcap_mm is not None and current_mcap_mm > 0:
        total_cap_mm = current_mcap_mm + total_debt_mm
        w_e = current_mcap_mm / total_cap_mm
        w_d = total_debt_mm / total_cap_mm
        kd_after_tax = max(rf_pct + 1.5 + crp_pct * 0.6, 4.0) * (1.0 - min(max(eff_tax_rate, 0.0), 0.35))
        raw_wacc = w_e * cost_of_equity_pct + w_d * kd_after_tax
    else:
        raw_wacc = rf_pct + beta_val * 4.5 + crp_pct
    wacc_floor = 7.2 + crp_pct * 0.7
    wacc_cap = 12.5 + crp_pct
    suggested_wacc_pct = round(min(max(raw_wacc, wacc_floor), wacc_cap), 1)

    tangible_equity_mm = max(latest_equity_mm - latest_goodwill_ltm - latest_intangibles_ltm, 0.0)

    if current_shares_mm > 0 and latest_equity_mm > 0:
        bvps = round(latest_equity_mm / current_shares_mm, 2)
    elif current_price > 0 and pb_ltm is not None and pb_ltm > 0:
        bvps = round(current_price / pb_ltm, 2)
    elif info.get("bookValue"):
        bvps = round(float(info["bookValue"]) * yf_fx_rate, 2)
    else:
        bvps = 0.0

    tbvps = round(tangible_equity_mm / current_shares_mm, 2) if (current_shares_mm > 0 and tangible_equity_mm > 0) else bvps

    yf_roe = info.get("returnOnEquity")
    yf_roe_pct = round(float(yf_roe) * 100.0, 2) if yf_roe is not None else None
    hist_roe_med = round(median(roe_series[-5:]), 2) if roe_series else 12.0
    base_roe_pct = yf_roe_pct if (yf_roe_pct is not None and -20.0 <= yf_roe_pct <= 45.0) else hist_roe_med

    div_paid_sec_mm = float(sec_fb.get("dividends_paid_mm") or 0.0)
    if div_paid_sec_mm <= 0 and latest_y_sec:
        div_paid_sec_mm = abs(get_m("Pago de dividendos", latest_y_sec))

    dividend_rate = float(info.get("dividendRate") or 0.0)
    if dividend_rate <= 0 and div_paid_sec_mm > 0 and current_shares_mm > 0:
        dividend_rate = round(div_paid_sec_mm / current_shares_mm, 2)

    payout_raw = info.get("payoutRatio")
    if payout_raw is not None:
        payout_pct = round(min(max(float(payout_raw) * 100.0, 10.0), 75.0), 1)
    elif div_paid_sec_mm > 0 and net_inc_ltm > 0:
        payout_pct = round(min(max((div_paid_sec_mm / net_inc_ltm) * 100.0, 10.0), 75.0), 1)
    else:
        payout_pct = 35.0

    med_ptbv = med_by_key.get("ptbv") or ltm_multiples.get("ptbv") or 1.8
    exit_ptbv_default = round(min(max(float(med_ptbv), 1.0), 2.8), 2)

    base_ebit_margin = float(audit["ebit_margin_pct"])
    step_yr = float(trajectory["margin_step_pct_yr"])
    raw_step_yr = step_yr
    hist_med_ebit = trajectory.get("hist_med_ebit_margin_pct")
    hist_margins = [
        float(m["operating_margin_pct"])
        for m in (trajectory.get("margin_history") or [])
        if m.get("operating_margin_pct") is not None
    ]
    rev_growth_yoy = audit.get("rev_growth_yoy_pct")
    rec_growth_pct = float(trajectory.get("recommended_rev_growth_pct") or 0.0)
    has_strong_rev_growth = (rev_growth_yoy is not None and rev_growth_yoy >= 8.0) or rec_growth_pct >= 8.0

    is_structural_decline = (
        len(hist_margins) >= 3
        and hist_margins[-1] < hist_margins[-2] < hist_margins[-3]
        and (hist_margins[-3] - hist_margins[-1]) >= 3.0
        and not has_strong_rev_growth
    )
    consensus_target_ebit = base_ebit_margin + (5.0 * step_yr)
    margin_reversion_applied = False
    margin_reversion_note: str | None = None
    if hist_med_ebit is not None and float(hist_med_ebit) > base_ebit_margin + 4.0 and not is_structural_decline:
        # Reversión parcial (75%) hacia la mediana histórica ante compresión transitoria o por reinversión
        reversion_target = base_ebit_margin + (float(hist_med_ebit) - base_ebit_margin) * 0.75
        target_ebit_margin_pct = round(min(max(max(consensus_target_ebit, reversion_target), -20.0), 60.0), 1)
        step_yr = round((target_ebit_margin_pct - base_ebit_margin) / 5.0, 2)
        trajectory["margin_step_pct_yr"] = step_yr
        margin_reversion_applied = True
        if has_strong_rev_growth and len(hist_margins) >= 3 and hist_margins[-1] < hist_margins[-2]:
            margin_reversion_note = (
                f"Compresión de margen durante expansión de ventas: margen EBIT normalizado hacia mediana histórica "
                f"({base_ebit_margin:.1f}% → {target_ebit_margin_pct:.1f}%)."
            )
        else:
            margin_reversion_note = (
                f"Margen EBIT objetivo normalizado hacia mediana histórica "
                f"({base_ebit_margin:.1f}% → {target_ebit_margin_pct:.1f}%)."
            )
    else:
        target_ebit_margin_pct = round(min(max(consensus_target_ebit, -20.0), 60.0), 1)
        if is_structural_decline and hist_med_ebit is not None and float(hist_med_ebit) > base_ebit_margin + 4.0:
            margin_reversion_note = (
                "Sin reversión automática a mediana histórica: margen EBIT y ventas muestran deterioro continuo sin señales de expansión."
            )

    sector_txt = f"{classification.get('sector') or ''} {classification.get('industry') or ''}".lower()
    if any(k in sector_txt for k in ("software", "internet", "saas", "cloud", "media", "communication")):
        nwc_pct_of_delta_rev = 0.02
    elif any(k in sector_txt for k in ("industrial", "manufacturing", "machinery", "auto", "aerospace")):
        nwc_pct_of_delta_rev = 0.12
    elif any(k in sector_txt for k in ("retail", "apparel", "wholesale", "grocery", "merchandise")):
        nwc_pct_of_delta_rev = 0.10
    elif any(k in sector_txt for k in ("energy", "materials", "chemicals", "consumer")):
        nwc_pct_of_delta_rev = 0.08
    else:
        nwc_pct_of_delta_rev = 0.05

    dcf_inputs_payload = {
        "current_price": round(current_price, 2),
        "shares_mm": round(current_shares_mm, 2),
        "net_debt_mm": round(current_net_debt_mm, 2),
        "revenue_base_mm": round(rev_base, 2),
        "ebitda_ltm_mm": round(ebitda_ltm, 2),
        "recommended_rev_growth_pct": trajectory["recommended_rev_growth_pct"],
        "suggested_wacc_pct": suggested_wacc_pct,
        "country_risk_premium_pct": crp_pct,
        "crp_updated_at": CRP_TABLE_UPDATED_AT,
        "margin_step_pct_yr": step_yr,
        "fcf_reported_mm": round(fcf_ltm, 2),
        "fcf_adjusted_mm": audit["adjusted_fcf_mm"],
        "ebit_margin_pct": audit["ebit_margin_pct"],
        "target_ebit_margin_pct": target_ebit_margin_pct,
        "margin_reversion_applied": margin_reversion_applied,
        "margin_reversion_note": margin_reversion_note,
        "nwc_pct_of_delta_rev": nwc_pct_of_delta_rev,
        "tax_rate_pct": audit["tax_rate_pct"],
        "da_sales_pct": da_sales_pct,
        "capex_expansion_pct": audit["capex_current_pct"],
        "capex_maintenance_pct": audit["capex_maint_pct"],
        "exit_multiple_default": round(exit_ev_fcf_default, 1),
        "dividend_rate": round(dividend_rate, 2),
        "payout_ratio_pct": payout_pct,
        "target_price": info.get("targetMeanPrice"),
    }

    financial_inputs_payload = {
        "current_price": round(current_price, 2),
        "shares_mm": round(current_shares_mm, 2),
        "book_value_mm": round(latest_equity_mm, 2),
        "tangible_book_value_mm": round(tangible_equity_mm, 2),
        "bvps": bvps,
        "tbvps": tbvps,
        "roe_pct": round(base_roe_pct, 1),
        "roe_hist_med_pct": hist_roe_med,
        "roa_pct": round(float(info["returnOnAssets"]) * 100.0, 2) if info.get("returnOnAssets") is not None else None,
        "cost_of_equity_pct": cost_of_equity_pct,
        "payout_ratio_pct": payout_pct,
        "dividend_rate": round(dividend_rate, 2),
        "exit_ptbv_default": exit_ptbv_default,
        "target_price": info.get("targetMeanPrice"),
    }

    reverse_dcf = _compute_reverse_dcf(
        is_financial=is_financial,
        dcf_inputs=dcf_inputs_payload,
        financial_inputs=financial_inputs_payload,
        hist_avg_growth_pct=trajectory["hist_avg_growth_pct"],
        recommended_growth_pct=trajectory["recommended_rev_growth_pct"],
    )

    # Doble entrega: Valuación "Realidad Fría" (números reportados actuales) vs "Sin Circunstancia Extraordinaria" (normalizado)
    cold_dcf_inputs = {
        **dcf_inputs_payload,
        "margin_step_pct_yr": min(raw_step_yr, 0.0) if (audit.get("has_anomalies") and raw_step_yr < 0) else 0.0,
        "target_ebit_margin_pct": base_ebit_margin,
        "capex_expansion_pct": audit["capex_current_pct"],
        "tax_rate_pct": audit["tax_rate_pct"],
        "fcf_adjusted_mm": round(fcf_ltm, 2),
    }
    cold_reverse = _compute_reverse_dcf(
        is_financial=is_financial,
        dcf_inputs=cold_dcf_inputs,
        financial_inputs=financial_inputs_payload,
        hist_avg_growth_pct=trajectory["hist_avg_growth_pct"],
        recommended_growth_pct=trajectory["recommended_rev_growth_pct"],
    )

    norm_ebit_target = float(audit.get("normalized_ebit_margin_pct") or target_ebit_margin_pct)
    norm_target_margin = max(target_ebit_margin_pct, round(base_ebit_margin + (norm_ebit_target - base_ebit_margin) * 0.75, 1))
    norm_step_yr = round((norm_target_margin - base_ebit_margin) / 5.0, 2)
    norm_dcf_inputs = {
        **dcf_inputs_payload,
        "margin_step_pct_yr": norm_step_yr,
        "target_ebit_margin_pct": norm_target_margin,
        "capex_expansion_pct": audit["capex_maint_pct"],
        "tax_rate_pct": float(audit.get("normalized_tax_rate_pct") or audit["tax_rate_pct"]),
        "fcf_adjusted_mm": float(audit.get("normalized_fcf_mm") or audit["adjusted_fcf_mm"]),
    }
    norm_reverse = _compute_reverse_dcf(
        is_financial=is_financial,
        dcf_inputs=norm_dcf_inputs,
        financial_inputs=financial_inputs_payload,
        hist_avg_growth_pct=trajectory["hist_avg_growth_pct"],
        recommended_growth_pct=trajectory["recommended_rev_growth_pct"],
    )

    cold_iv = float(cold_reverse.get("intrinsic_value_per_share") or 0.0)
    norm_iv = float(norm_reverse.get("intrinsic_value_per_share") or 0.0)
    delta_iv = round(norm_iv - cold_iv, 2)
    delta_pct = round(((norm_iv - cold_iv) / cold_iv) * 100.0, 1) if cold_iv > 0 else None

    norm_ebit_mm = float(audit.get("normalized_ebit_mm") or 0.0)
    norm_net_mm = float(audit.get("normalized_net_inc_mm") or 0.0)
    norm_fcf_mm = float(audit.get("normalized_fcf_mm") or 0.0)
    da_ltm_mm = rev_base * (da_sales_pct / 100.0)
    norm_ebitda_mm = round(norm_ebit_mm + da_ltm_mm, 2) if norm_ebit_mm > 0 else None

    valuation_comparison = {
        "has_material_diff": bool(audit.get("has_anomalies") or (delta_pct is not None and abs(delta_pct) >= 5.0)),
        "as_reported": {
            "label": "Realidad fría (números actuales)",
            "intrinsic_value_per_share": cold_iv,
            "upside_pct": cold_reverse.get("upside_pct"),
            "ebit_margin_pct": base_ebit_margin,
            "target_ebit_margin_pct": base_ebit_margin,
            "capex_pct": audit["capex_current_pct"],
            "tax_rate_pct": audit["tax_rate_pct"],
        },
        "normalized": {
            "label": "Sin circunstancia extraordinaria (normalizado)",
            "intrinsic_value_per_share": norm_iv,
            "upside_pct": norm_reverse.get("upside_pct"),
            "ebit_margin_pct": norm_ebit_target,
            "target_ebit_margin_pct": norm_target_margin,
            "capex_pct": audit["capex_maint_pct"],
            "tax_rate_pct": float(audit.get("normalized_tax_rate_pct") or audit["tax_rate_pct"]),
        },
        "delta_per_share": delta_iv,
        "delta_pct": delta_pct,
        "normalized_ltm_metrics": {
            "ebit_mm": norm_ebit_mm,
            "ebitda_mm": norm_ebitda_mm,
            "net_income_mm": norm_net_mm,
            "fcf_mm": norm_fcf_mm,
            "ebit_margin_pct": norm_ebit_target,
            "pe": _safe_multiple(current_mcap_mm, norm_net_mm),
            "ev_ebit": _safe_multiple(current_ev_mm, norm_ebit_mm),
            "ev_ebitda": _safe_multiple(current_ev_mm, norm_ebitda_mm),
            "pfcf": _safe_multiple(current_mcap_mm, norm_fcf_mm),
            "fcf_yield": round((norm_fcf_mm / current_mcap_mm) * 100.0, 2) if (current_mcap_mm and current_mcap_mm > 0) else None,
        },
    }

    return {
        "ticker": ticker_upper,
        "classification": classification,
        "sector_routing": sector_routing,
        "years": valid_years,
        "rows": table_rows,
        "audit": audit,
        "trajectory": trajectory,
        "reverse_dcf": reverse_dcf,
        "valuation_comparison": valuation_comparison,
        "ttm_meta": {
            "is_complete": ttm_data.get("is_complete"),
            "source": ttm_data.get("source"),
            "cutoff_label": ttm_data.get("cutoff_label"),
            "quarters_used": ttm_data.get("quarters_used"),
            "rev_yoy_2q_pct": ttm_data.get("rev_yoy_2q_pct"),
            "quality_warning": ttm_data.get("quality_warning"),
        },
        "dcf_inputs": dcf_inputs_payload,
        "financial_sector_inputs": financial_inputs_payload,
    }