from datetime import datetime, timedelta
from statistics import mean, median
from typing import Any
import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.database import PriceHistoryCache, is_sqlite
from app.services.company_service import get_raw_financials
from app.services.financial_parser import extract_annual_metrics
from app.core.yf_client import (
    get_cached_market_snapshot,
    get_cached_estimates_and_guidance,
)


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
    consensus_5y_pct = round(float(g_5y_raw) * 100.0, 2) if g_5y_raw is not None else None

    forward_candidates = [v for v in (rev_0y_pct, rev_1y_pct, consensus_5y_pct) if v is not None]
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
            margin_step_pct_yr = 0.30
        elif spread_eps_rev <= -2.5:
            leverage_signal = "compressing"
            leverage_label = (
                f"Compresión esperada de márgenes: el consenso proyecta BPA +{eps_1y_pct:.1f}% "
                f"vs. Ventas +{rev_1y_pct:.1f}% (presión por costos, CapEx o depreciación)."
            )
            margin_step_pct_yr = -0.30

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
                "eps_avg": round(float(e_row["avg"]), 2) if e_row.get("avg") is not None else None,
                "eps_low": round(float(e_row["low"]), 2) if e_row.get("low") is not None else None,
                "eps_high": round(float(e_row["high"]), 2) if e_row.get("high") is not None else None,
                "eps_growth_pct": round(float(eps_g_raw) * 100.0, 2) if eps_g_raw is not None else None,
                "eps_analysts": e_row.get("numberOfAnalysts"),
            })

    return {
        "recent_yoy_rates": recent_yoy,
        "hist_avg_growth_pct": hist_avg_growth,
        "is_consistent_hist": is_consistent_hist,
        "forward_avg_growth_pct": forward_avg_growth,
        "consensus_5y_pct": consensus_5y_pct,
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

    return {
        "has_anomalies": len(flags) > 0,
        "flags": flags,
        "comparisons": comparisons,
        "adjusted_fcf_mm": round(adjusted_fcf, 2),
        "capex_current_pct": capex_curr_pct,
        "capex_maint_pct": max(capex_maint_pct, 2.0),
        "ebit_margin_pct": ebit_margin_pct,
        "tax_rate_pct": round(eff_tax * 100.0, 1),
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
            g1 = min(max(roe_decimal * retention, -0.05), 0.25)
            g_term = min(max(g1, 0.01), 0.045)
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
            lo, hi = -0.05, 0.60
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

        return {
            "mode": "financial",
            "model_label": "Excess Return Inverso (ROE y Crecimiento Patrimonial Implícito)",
            "current_price": round(cur_price, 2),
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
    g_term = 0.03

    def eval_corp_price(g_decimal: float, horizon_yrs: int, tv_mode: str = "blend") -> float:
        if rev0 <= 0 or shares <= 0 or wacc <= g_term:
            return 0.0
        rv = rev0
        pv1 = 0.0
        last_margin = ebit_m
        for yr in range(1, horizon_yrs + 1):
            rv *= 1.0 + g_decimal
            step_yr = min(yr, 5)
            m_yr = min(max(ebit_m + margin_step * step_yr, 0.01), 0.65)
            last_margin = m_yr
            fcf_y = rv * (m_yr * (1.0 - tax_r) + da_p - capex1)
            pv1 += fcf_y / ((1.0 + wacc) ** yr)

        fcf_next = rv * (1.0 + g_term) * (last_margin * (1.0 - tax_r) + da_p - capex_t)
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

    return {
        "mode": "standard",
        "model_label": "DCF Inverso 2 Etapas (Crecimiento Anual Implícito en Precio)",
        "current_price": round(cur_price, 2),
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
    try:
        annual_rows = extract_annual_metrics(raw_facts)
    except ValueError:
        annual_rows = []

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
    sec_fx_rate = float(sec_fb.get("sec_fx_to_usd") or market_snapshot.get("fx_rate") or 1.0)
    yf_fx_rate = float(market_snapshot.get("fx_rate") or 1.0)

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
        if shares_raw_y > 0:
            shares = shares_raw_y * split_factors.get(y, 1.0)
            if current_shares_mm > 0 and shares < (current_shares_mm * 0.15):
                shares = current_shares_mm
        else:
            shares = current_shares_mm

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

    fcf_ltm = latest_sec_fcf if latest_sec_fcf != 0.0 else (yf_fcf if yf_fcf != 0.0 else yf_ocf)
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
            {"key": "ev_fcf", "label": "EV / Flujo de Caja Libre (Unlevered)", "suffix": "x", "section": "Trailing Multiples (EV)"},
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

    da_sales_pct = round((latest_sec_da / latest_sec_rev) * 100.0, 2) if latest_sec_rev > 0 else 8.0

    adj_ev_fcf = _safe_multiple(current_ev_mm, audit["adjusted_fcf_mm"])
    med_ev_ebitda = med_by_key.get("ev_ebitda")
    raw_exit = adj_ev_fcf or med_ev_ebitda or med_by_key.get("ev_fcf") or 20.0
    exit_ev_fcf_default = min(max(float(raw_exit), 12.0), 28.0)

    beta_val = float(info.get("beta") or 1.0)
    suggested_wacc_pct = round(min(max(4.25 + beta_val * 4.5, 7.2), 12.5), 1)
    cost_of_equity_pct = round(min(max(4.25 + beta_val * 5.0, 8.0), 14.5), 1)

    tangible_equity_mm = max(latest_equity_mm - latest_goodwill_ltm - latest_intangibles_ltm, 0.0)

    bvps = round(latest_equity_mm / current_shares_mm, 2) if (current_shares_mm > 0 and latest_equity_mm > 0) else 0.0
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

    dcf_inputs_payload = {
        "current_price": round(current_price, 2),
        "shares_mm": round(current_shares_mm, 2),
        "net_debt_mm": round(current_net_debt_mm, 2),
        "revenue_base_mm": round(rev_base, 2),
        "recommended_rev_growth_pct": trajectory["recommended_rev_growth_pct"],
        "suggested_wacc_pct": suggested_wacc_pct,
        "margin_step_pct_yr": trajectory["margin_step_pct_yr"],
        "fcf_reported_mm": round(fcf_ltm, 2),
        "fcf_adjusted_mm": audit["adjusted_fcf_mm"],
        "ebit_margin_pct": audit["ebit_margin_pct"],
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

    return {
        "ticker": ticker_upper,
        "classification": classification,
        "sector_routing": sector_routing,
        "years": valid_years,
        "rows": table_rows,
        "audit": audit,
        "trajectory": trajectory,
        "reverse_dcf": reverse_dcf,
        "dcf_inputs": dcf_inputs_payload,
        "financial_sector_inputs": financial_inputs_payload,
    }