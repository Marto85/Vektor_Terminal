from datetime import datetime, timedelta
from statistics import mean, median
from typing import Any
import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from app.models.database import PriceHistoryCache
from app.services.company_service import get_raw_financials
from app.services.financial_parser import extract_annual_metrics
from app.core.yf_client import get_cached_market_snapshot


def _get_annual_closing_prices(ticker_upper: str, db: Session) -> dict[str, float]:
    """
    Obtiene el precio de cierre de fin de cada año calendario desde la serie mensual
    cacheada en SQLite (`PriceHistoryCache`). Si no existe, descarga `10y` mensual una vez.
    """
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
                    if candles:
                        by_year: dict[str, float] = {}
                        for c in candles:
                            yr = str(c.get("time", ""))[:4]
                            close_val = c.get("close")
                            if yr and isinstance(close_val, (int, float)) and close_val > 0:
                                by_year[yr] = float(close_val)
                        if by_year:
                            return by_year

    tk = yf.Ticker(ticker_upper)
    hist = tk.history(period="10y", interval="1mo", auto_adjust=False)
    if hist is None or hist.empty:
        return {}

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
    existing = db.query(PriceHistoryCache).filter(PriceHistoryCache.cache_key == cache_key).first()
    payload_to_save = {
        "ticker": ticker_upper,
        "range": "10y",
        "interval": "1mo",
        "years": 10.0,
        "totalReturnPct": 0.0,
        "cagrPct": 0.0,
        "seriesByMetric": {"Price": price_series},
    }
    if existing is not None:
        db.query(PriceHistoryCache).filter(PriceHistoryCache.cache_key == cache_key).update({
            "payload": payload_to_save,
            "last_updated": now,
        })
    else:
        db.add(
            PriceHistoryCache(
                cache_key=cache_key,
                ticker=ticker_upper,
                range_key="10y",
                payload=payload_to_save,
                last_updated=now,
            )
        )
    db.commit()
    return by_year


def _safe_multiple(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0.0:
        return None
    val = num / den
    if abs(val) > 500:
        return None
    return round(val, 2)


def _audit_anomalies_and_adjustments(
    valid_years: list[str],
    get_m: Any,
    current_mcap_mm: float | None,
    current_ev_mm: float | None,
    ltm_multiples: dict[str, float | None],
) -> dict[str, Any]:
    """
    Audita estadísticamente el último ejercicio 10-K frente a la mediana histórica
    de la propia empresa para detectar distorsiones materiales en CapEx, partidas no
    operativas, compensación basada en acciones (SBC) y capital de trabajo.
    """
    if not valid_years:
        return {
            "has_anomalies": False,
            "flags": [],
            "comparisons": [],
            "adjusted_fcf_mm": 0.0,
            "capex_current_pct": 10.0,
            "capex_maint_pct": 8.0,
            "ebit_margin_pct": 15.0,
            "tax_rate_pct": 21.0,
        }

    latest_y = valid_years[-1]
    prev_years = valid_years[:-1] if len(valid_years) > 1 else valid_years

    rev_curr = get_m("Ingresos Totales", latest_y)
    ebit_curr = get_m("Beneficio Operativo", latest_y)
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

    # Tasa impositiva efectiva acotada entre 10% y 35%
    eff_tax = 0.21
    if ebt_curr > 0 and tax_curr > 0:
        eff_tax = min(max(tax_curr / ebt_curr, 0.10), 0.35)

    ebit_margin_pct = round((ebit_curr / rev_curr) * 100.0, 2) if rev_curr > 0 else 15.0
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

    # 1. Auditoría de Ciclo de Expansión de CapEx
    if rev_curr > 0 and capex_curr > 0:
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

    # 2. Auditoría de Partidas No Operativas Extraordinarias (venta de activos, revaluaciones, etc.)
    nopat_curr = ebit_curr * (1.0 - eff_tax)
    non_op_gap = net_inc_curr - nopat_curr
    if abs(ebit_curr) > 0 and (
        abs(non_op_curr) > abs(ebit_curr) * 0.15
        or abs(non_op_gap) > abs(ebit_curr) * 0.25
    ):
        # Si hay partida no operativa explícita la aislamos; si no, usamos NOPAT como proxy operativo limpio
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

    # 3. Auditoría de Compensación Basada en Acciones (SBC)
    if cfo_curr > 0 and (sbc_curr / cfo_curr) > 0.25:
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

    # 4. Auditoría de Shock de Capital de Trabajo
    if abs(cfo_curr) > 0 and abs(wc_curr) > abs(cfo_curr) * 0.20:
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


def build_valuation_report(ticker_symbol: str, db: Session) -> dict[str, Any]:
    """
    Construye la tabla histórica de múltiplos, ejecuta la auditoría de anomalías contables
    y prepara los inputs para el DCF en 2 etapas con doble método de Valor Terminal.
    """
    ticker_upper = ticker_symbol.upper()

    raw_facts = get_raw_financials(ticker_upper, db)
    annual_rows = extract_annual_metrics(raw_facts)
    market_snapshot = get_cached_market_snapshot(ticker_upper, db)
    annual_prices = _get_annual_closing_prices(ticker_upper, db)

    info: dict[str, Any] = market_snapshot.get("info", {})
    current_price = float(market_snapshot.get("price") or 0.0)
    current_shares_mm = float(market_snapshot.get("shares_mm") or 0.0)
    current_net_debt_mm = float(market_snapshot.get("net_debt_mm") or 0.0)

    current_mcap_mm = round(current_price * current_shares_mm, 2) if (current_price > 0 and current_shares_mm > 0) else None
    current_ev_mm = round(current_mcap_mm + current_net_debt_mm, 2) if current_mcap_mm is not None else None

    current_year = datetime.now().year
    years_range = [str(y) for y in range(current_year - 6, current_year + 1)]

    lookup: dict[str, dict[str, float]] = {}
    for row in annual_rows:
        m = row.get("Métrica", "")
        lookup[m] = {y: float(row.get(y, 0.0) or 0.0) for y in years_range}

    def get_m(metric: str, y: str) -> float:
        return lookup.get(metric, {}).get(y, 0.0)

    yearly_multiples: dict[str, dict[str, float | None]] = {}
    valid_years: list[str] = []

    for y in years_range:
        rev = get_m("Ingresos Totales", y)
        gp = get_m("Beneficio Bruto", y)
        ebit = get_m("Beneficio Operativo", y)
        da = get_m("Depreciación y Amortización", y)
        ebitda = ebit + da if (ebit != 0.0 or da != 0.0) else 0.0
        net_inc = get_m("Beneficio Neto", y)
        fcf = get_m("Flujo de caja libre (FCF)", y)
        equity = get_m("Patrimonio neto", y)
        goodwill = get_m("Fondo de comercio", y)
        intangibles = get_m("Activos intangibles", y)
        tangible_equity = equity - goodwill - intangibles

        cash = get_m("Efectivo y equivalentes", y) + get_m("Inversiones a corto plazo", y)
        debt = get_m("Deuda a corto plazo", y) + get_m("Deuda a largo plazo", y)
        net_debt = debt - cash

        shares = get_m("Acciones en Circulación (Diluidas)", y)
        if shares <= 0:
            shares = get_m("Acciones en Circulación (Básicas)", y)
        if shares <= 0:
            shares = current_shares_mm

        price_y = annual_prices.get(y)

        if rev == 0.0 and equity == 0.0:
            continue

        valid_years.append(y)
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
            "pb": _safe_multiple(mcap_y, equity),
            "ptbv": _safe_multiple(mcap_y, tangible_equity),
            "ev_fcf": _safe_multiple(ev_y, fcf),
            "pfcf": _safe_multiple(mcap_y, fcf),
            "fcf_yield": fcf_yield,
            "factor_price": round(price_y, 2) if price_y is not None else None,
            "factor_ev": ev_y,
            "factor_mcap": mcap_y,
        }

    # Métricas LTM / Forward
    rev_ltm = (info.get("totalRevenue") or 0) / 1_000_000.0
    gp_ltm = (info.get("grossProfits") or 0) / 1_000_000.0
    ebitda_ltm = (info.get("ebitda") or 0) / 1_000_000.0
    ebit_margin = info.get("operatingMargins")
    ebit_ltm = (rev_ltm * float(ebit_margin)) if (rev_ltm > 0 and ebit_margin is not None) else 0.0
    net_inc_ltm = (info.get("netIncomeToCommon") or 0) / 1_000_000.0

    latest_sec_fcf = get_m("Flujo de caja libre (FCF)", valid_years[-1]) if valid_years else 0.0
    latest_sec_rev = get_m("Ingresos Totales", valid_years[-1]) if valid_years else 0.0
    latest_sec_da = get_m("Depreciación y Amortización", valid_years[-1]) if valid_years else 0.0
    yf_ocf = (info.get("operatingCashflow") or 0) / 1_000_000.0
    yf_fcf = (info.get("freeCashflow") or 0) / 1_000_000.0

    fcf_ltm = latest_sec_fcf if latest_sec_fcf != 0.0 else (yf_fcf if yf_fcf != 0.0 else yf_ocf)
    rev_base = rev_ltm if rev_ltm > 0 else latest_sec_rev

    pb_raw = info.get("priceToBook")
    pb_ltm = round(float(pb_raw), 2) if pb_raw is not None else None
    fcf_yield_ltm = round((fcf_ltm / current_mcap_mm) * 100.0, 2) if (current_mcap_mm and current_mcap_mm > 0 and fcf_ltm != 0.0) else None

    rev_growth = info.get("revenueGrowth")
    rev_ntm = rev_ltm * (1.0 + float(rev_growth)) if (rev_ltm > 0 and rev_growth is not None) else None
    pe_ntm_raw = info.get("forwardPE")
    pe_ntm = round(float(pe_ntm_raw), 2) if pe_ntm_raw is not None else None
    if pe_ntm is None and current_price > 0 and info.get("forwardEps"):
        fwd_eps = float(info["forwardEps"])
        if fwd_eps != 0:
            pe_ntm = round(current_price / fwd_eps, 2)

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
        "ptbv": yearly_multiples[valid_years[-1]]["ptbv"] if valid_years else None,
        "ev_fcf": _safe_multiple(current_ev_mm, fcf_ltm),
        "pfcf": _safe_multiple(current_mcap_mm, fcf_ltm),
        "fcf_yield": fcf_yield_ltm,
        "factor_price": round(current_price, 2) if current_price > 0 else None,
        "factor_ev": current_ev_mm,
        "factor_mcap": current_mcap_mm,
    }

    # Auditoría de distorsiones contables
    audit = _audit_anomalies_and_adjustments(
        valid_years=valid_years,
        get_m=get_m,
        current_mcap_mm=current_mcap_mm,
        current_ev_mm=current_ev_mm,
        ltm_multiples=ltm_multiples,
    )

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

    # Para el Múltiplo de Salida (Año +5, etapa madura), evitamos usar EV/FCF crudo si estuvo
    # distorsionado por CapEx de expansión; priorizamos EV/FCF normalizado o mediana 5Y de EV/EBITDA.
    adj_ev_fcf = _safe_multiple(current_ev_mm, audit["adjusted_fcf_mm"])
    med_ev_ebitda = med_by_key.get("ev_ebitda")
    raw_exit = adj_ev_fcf or med_ev_ebitda or med_by_key.get("ev_fcf") or 20.0
    exit_ev_fcf_default = min(max(float(raw_exit), 12.0), 28.0)

    return {
        "ticker": ticker_upper,
        "years": valid_years,
        "rows": table_rows,
        "audit": audit,
        "dcf_inputs": {
            "current_price": round(current_price, 2),
            "shares_mm": round(current_shares_mm, 2),
            "net_debt_mm": round(current_net_debt_mm, 2),
            "revenue_base_mm": round(rev_base, 2),
            "fcf_reported_mm": round(fcf_ltm, 2),
            "fcf_adjusted_mm": audit["adjusted_fcf_mm"],
            "ebit_margin_pct": audit["ebit_margin_pct"],
            "tax_rate_pct": audit["tax_rate_pct"],
            "da_sales_pct": da_sales_pct,
            "capex_expansion_pct": audit["capex_current_pct"],
            "capex_maintenance_pct": audit["capex_maint_pct"],
            "exit_multiple_default": round(exit_ev_fcf_default, 1),
            "target_price": info.get("targetMeanPrice"),
        },
    }