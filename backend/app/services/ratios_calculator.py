from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session
import yfinance as yf

from app.models.database import CompanyMarketCache
from app.core.yf_client import get_company_profile


def _safe_div(num: float | None, den: float | None) -> float:
    if num is None or den is None or den == 0.0:
        return 0.0
    return num / den


def _build_lookup(financial_data: list[dict[str, Any]], years_range: list[str]) -> dict[str, dict[str, float]]:
    lookup: dict[str, dict[str, float]] = {}
    for row_data in financial_data:
        if row_data.get("is_header") or row_data.get("is_sub"):
            continue
        metric = str(row_data.get("Métrica") or "")
        if not metric:
            continue
        lookup[metric] = {}
        for y in years_range:
            val = row_data.get(y, 0.0)
            lookup[metric][y] = float(val) if isinstance(val, (int, float)) else 0.0
    return lookup


def _get_resilient_val(lookup: dict[str, dict[str, float]], metric: str, y: str) -> float:
    raw = lookup.get(metric, {}).get(y, 0.0)
    if raw != 0.0:
        return raw

    # Reconstrucciones de respaldo si el tag XBRL de SEC quedó en 0.0
    if metric == "Patrimonio neto":
        ta = lookup.get("Total activo", {}).get(y, 0.0)
        tl = lookup.get("Total pasivo", {}).get(y, 0.0)
        if ta > 0.0 and tl > 0.0:
            return ta - tl

    if metric == "Beneficio Operativo":
        ebt = lookup.get("Beneficio antes de Impuestos", {}).get(y, 0.0)
        intr = lookup.get("Gastos por Intereses", {}).get(y, 0.0)
        if ebt != 0.0:
            return ebt + intr

    return raw


def calculate_ratios(financial_data: list, years_range: list) -> list:
    lookup = _build_lookup(financial_data, years_range)

    def get_val(metric: str, y: str) -> float:
        return _get_resilient_val(lookup, metric, y)

    def get_avg_balance(metric: str, idx: int) -> float:
        curr = get_val(metric, years_range[idx])
        if idx == 0:
            return curr
        prev = get_val(metric, years_range[idx - 1])
        if prev == 0.0:
            return curr
        return (curr + prev) / 2.0

    ratios = []

    for idx, y in enumerate(years_range):
        ventas = get_val("Ingresos Totales", y)
        cogs = get_val("Coste de los bienes vendidos", y)
        beneficio_bruto = get_val("Beneficio Bruto", y)
        ebit = get_val("Beneficio Operativo", y)
        ebt = get_val("Beneficio antes de Impuestos", y)
        beneficio_neto = get_val("Beneficio Neto", y)
        da = get_val("Depreciación y Amortización", y)
        intereses = get_val("Gastos por Intereses", y)

        activo_total = get_val("Total activo", y)
        activo_corr = get_val("Total activo corriente", y)
        pasivo_total = get_val("Total pasivo", y)
        pasivo_corr = get_val("Total pasivo corriente", y)
        patrimonio = get_val("Patrimonio neto", y)
        cfo = get_val("Efectivo de Operaciones (CFO)", y)

        deuda_total = get_val("Deuda a corto plazo", y) + get_val("Deuda a largo plazo", y)
        ebitda = ebit + da

        # Rentabilidad y Márgenes
        margen_bruto = _safe_div(beneficio_bruto, ventas) * 100.0
        margen_operativo = _safe_div(ebit, ventas) * 100.0
        margen_neto = _safe_div(beneficio_neto, ventas) * 100.0

        roa = _safe_div(beneficio_neto, activo_total) * 100.0
        roe = _safe_div(beneficio_neto, patrimonio) * 100.0
        rotacion_activos = _safe_div(ventas, activo_total)

        # Liquidez y Solvencia
        current_ratio = _safe_div(activo_corr, pasivo_corr)
        quick_ratio = _safe_div(activo_corr - get_val("Inventario", y), pasivo_corr)
        cfo_a_pasivo = _safe_div(cfo, pasivo_corr)

        deuda_capital = _safe_div(deuda_total, patrimonio) * 100.0
        pasivo_activo = _safe_div(pasivo_total, activo_total) * 100.0
        cobertura_intereses = _safe_div(ebit, intereses)
        deuda_ebitda = _safe_div(deuda_total, ebitda)

        # Descomposición DuPont (3 y 5 factores)
        apalancamiento_dupont = _safe_div(activo_total, patrimonio)
        carga_fiscal = _safe_div(beneficio_neto, ebt) * 100.0 if ebt != 0.0 else 0.0
        carga_intereses = _safe_div(ebt, ebit) * 100.0 if ebit != 0.0 else 0.0

        # Ciclo de Conversión de Efectivo (DSO + DIO - DPO)
        avg_ar = get_avg_balance("Cuentas por cobrar", idx)
        avg_inv = get_avg_balance("Inventario", idx)
        avg_ap = get_avg_balance("Cuentas por pagar", idx)

        dso = _safe_div(avg_ar, ventas) * 365.0 if ventas > 0 else 0.0
        dio = _safe_div(avg_inv, cogs) * 365.0 if cogs > 0 else 0.0
        dpo = _safe_div(avg_ap, cogs) * 365.0 if cogs > 0 else 0.0
        ccc = (dso + dio - dpo) if (ventas > 0 and (dso > 0 or dio > 0 or dpo > 0)) else 0.0

        ratios.append({
            "Año": y,
            "Rentabilidad sobre activos (ROA) %": {"val": roa, "pct": True},
            "Rentabilidad sobre capital (ROE) %": {"val": roe, "pct": True},
            "Margen de beneficio bruto %": {"val": margen_bruto, "pct": True},
            "Margen de beneficio operativo (EBIT) %": {"val": margen_operativo, "pct": True},
            "Margen neto %": {"val": margen_neto, "pct": True},
            "Rotación de activos (x)": {"val": rotacion_activos, "pct": False},
            "Apalancamiento financiero (Activos / Patrimonio) (x)": {"val": apalancamiento_dupont, "pct": False},
            "Carga fiscal DuPont (Beneficio Neto / EBT) %": {"val": carga_fiscal, "pct": True},
            "Carga de intereses DuPont (EBT / EBIT) %": {"val": carga_intereses, "pct": True},
            "Días de cobro (DSO)": {"val": dso, "pct": False},
            "Días de inventario (DIO)": {"val": dio, "pct": False},
            "Días de pago (DPO)": {"val": dpo, "pct": False},
            "Ciclo de conversión de efectivo (CCC) días": {"val": ccc, "pct": False},
            "Ratio de liquidez (x)": {"val": current_ratio, "pct": False},
            "Ratio de disponibilidad (Quick Ratio) (x)": {"val": quick_ratio, "pct": False},
            "Flujo de caja operativo a pasivo corriente (x)": {"val": cfo_a_pasivo, "pct": False},
            "Deuda total / Fondos propios %": {"val": deuda_capital, "pct": True},
            "Pasivo total / Activo total %": {"val": pasivo_activo, "pct": True},
            "EBIT / Gastos por intereses (x)": {"val": cobertura_intereses, "pct": False},
            "Deuda total / EBITDA (x)": {"val": deuda_ebitda, "pct": False},
        })

    secciones_tikr = [
        ("Ratios de rentabilidad:", [
            "Rentabilidad sobre activos (ROA) %",
            "Rentabilidad sobre capital (ROE) %",
        ]),
        ("Análisis de los márgenes:", [
            "Margen de beneficio bruto %",
            "Margen de beneficio operativo (EBIT) %",
            "Margen neto %",
        ]),
        ("Descomposición DuPont (ROE 3 y 5 factores):", [
            "Rotación de activos (x)",
            "Apalancamiento financiero (Activos / Patrimonio) (x)",
            "Carga de intereses DuPont (EBT / EBIT) %",
            "Carga fiscal DuPont (Beneficio Neto / EBT) %",
        ]),
        ("Ciclo de conversión de efectivo (Capital de trabajo):", [
            "Días de cobro (DSO)",
            "Días de inventario (DIO)",
            "Días de pago (DPO)",
            "Ciclo de conversión de efectivo (CCC) días",
        ]),
        ("Liquidez a corto plazo:", [
            "Ratio de liquidez (x)",
            "Ratio de disponibilidad (Quick Ratio) (x)",
            "Flujo de caja operativo a pasivo corriente (x)",
        ]),
        ("Solvencia a largo plazo:", [
            "Deuda total / Fondos propios %",
            "Pasivo total / Activo total %",
            "EBIT / Gastos por intereses (x)",
            "Deuda total / EBITDA (x)",
        ]),
    ]

    for titulo, metricas in secciones_tikr:
        header_row: dict = {"Categoría": "Ratios", "Métrica": titulo, "is_header": True}
        for y in years_range:
            header_row[y] = None
        financial_data.append(header_row)

        for met in metricas:
            row: dict = {"Categoría": "Ratios", "Métrica": met}
            for r in ratios:
                y = r["Año"]
                val_obj = r[met]
                row[y] = round(val_obj["val"], 2)
                if val_obj["pct"]:
                    row["is_pct"] = True
            financial_data.append(row)

    return financial_data


def _classify_sector_profile(sector: str, industry: str) -> dict[str, Any]:
    sec_low = (sector or "").lower()
    ind_low = (industry or "").lower()
    combined = f"{sec_low} {ind_low}"

    is_financial = any(
        k in combined
        for k in ["financial", "bank", "insurance", "credit", "capital markets", "asset management", "reit", "real estate"]
    )
    is_manufacturing = any(
        k in combined
        for k in ["industrial", "manufacturing", "auto", "aerospace", "machinery", "chemical", "basic materials", "metals", "semiconductor", "hardware", "consumer defensive", "consumer cyclical"]
    )

    if is_financial:
        return {
            "profile": "financial",
            "label": "Sector Financiero / Seguros / Inmobiliario",
            "altman_applicable": False,
            "altman_recommended_variant": "none",
            "altman_warning": (
                "ADVERTENCIA SECTORIAL: El modelo Altman Z-Score NO ES VÁLIDO para bancos, aseguradoras, financieras ni REITs. "
                "En estas entidades los depósitos y pasivos financieros son materia prima operativa y no existe capital de trabajo industrial, "
                "lo que arrojaría falsos positivos de estrés financiero. Evaluá solvencia mediante Tier 1 Capital, ROE vs. Ke y P/TBV."
            ),
            "piotroski_applicable": False,
            "piotroski_warning": (
                "ADVERTENCIA SECTORIAL: El Piotroski F-Score original fue diseñado para empresas no financieras. "
                "En bancos y aseguradoras los criterios de liquidez corriente (Activo Corriente / Pasivo Corriente) y rotación de activos "
                "no aplican por la estructura del balance bancario; interpretá este puntaje solo como referencia parcial de rentabilidad."
            ),
        }

    if is_manufacturing:
        return {
            "profile": "manufacturing",
            "label": "Manufactura / Industrial / Comercio con Activos Físicos",
            "altman_applicable": True,
            "altman_recommended_variant": "z_original",
            "altman_warning": (
                "APLICABILIDAD SECTORIAL: El Altman Z-Score original (1968) fue calibrado específicamente para compañías manufactureras e industriales "
                "cotizantes como esta. Se muestra también el Z''-Score como referencia complementaria."
            ),
            "piotroski_applicable": True,
            "piotroski_warning": (
                "APLICABILIDAD SECTORIAL: El Piotroski F-Score (0–9) es plenamente válido para este sector y resulta especialmente efectivo "
                "para separar empresas sólidas de trampas de valor (value traps)."
            ),
        }

    return {
        "profile": "services_tech",
        "label": "Servicios / Tecnología / Modelos Asset-Light",
        "altman_applicable": True,
        "altman_recommended_variant": "z_double_prime",
        "altman_warning": (
            "APLICABILIDAD SECTORIAL: En empresas de tecnología, software y servicios asset-light se recomienda priorizar el Altman Z''-Score "
            "(variante sin rotación de activos Ventas/Activos) frente al Z-Score original de 1968, ya que el modelo original fue diseñado para "
            "fábricas y tiende a subestimar empresas con pocos activos físicos o fuerte caja/intangibles."
        ),
        "piotroski_applicable": True,
        "piotroski_warning": (
            "APLICABILIDAD SECTORIAL: El Piotroski F-Score (0–9) es válido para empresas no financieras de tecnología y servicios; "
            "tené en cuenta que en negocios sin inventarios físicos la expansión de margen bruto y la conversión de CFO a utilidad neta tienen mayor peso analítico."
        ),
    }


def _evaluate_criterion_status(passed: bool, near: bool) -> str:
    if passed:
        return "pass"
    if near:
        return "near"
    return "fail"


def build_financial_health_report(
    ticker: str,
    financial_data: list[dict[str, Any]],
    db: Session,
) -> dict[str, Any]:
    sym = ticker.upper().strip()
    current_year = datetime.now().year
    years_range = [str(y) for y in range(current_year - 6, current_year + 1)]
    lookup = _build_lookup(financial_data, years_range)

    def get_val(metric: str, y: str) -> float:
        return _get_resilient_val(lookup, metric, y)

    valid_years = [
        y for y in years_range
        if get_val("Total activo", y) > 0.0 or get_val("Ingresos Totales", y) > 0.0
    ]
    if len(valid_years) < 2:
        raise ValueError(f"Se necesitan al menos 2 ejercicios anuales cerrados para evaluar la salud financiera de {sym}.")

    y_curr = valid_years[-1]
    y_prev = valid_years[-2]

    cache_row = db.query(CompanyMarketCache).filter(CompanyMarketCache.ticker == sym).first()
    raw_md = getattr(cache_row, "market_data", None) if cache_row else None
    md: dict[str, Any] = dict(raw_md) if isinstance(raw_md, dict) else {}

    if len(md) == 0:
        try:
            get_company_profile(sym, db)
            cache_row = db.query(CompanyMarketCache).filter(CompanyMarketCache.ticker == sym).first()
            raw_md = getattr(cache_row, "market_data", None) if cache_row else None
            if isinstance(raw_md, dict):
                md = dict(raw_md)
        except Exception:
            pass

    sector = str(md.get("sector") or "").strip()
    industry = str(md.get("industry") or "").strip()
    company_name = str(md.get("name") or "").strip()

    if not sector or not company_name or company_name.upper() == sym:
        try:
            info = yf.Ticker(sym).info or {}
            sector = str(info.get("sector") or sector or "").strip()
            industry = str(info.get("industry") or industry or "").strip()
            company_name = str(info.get("shortName") or info.get("longName") or company_name or sym).strip()
            if cache_row and isinstance(md, dict):
                md["sector"] = sector
                md["industry"] = industry
                md["name"] = company_name
                setattr(cache_row, "market_data", md)
                db.commit()
        except Exception:
            pass

    company_name = company_name or sym
    mcap_mm = float((md.get("summary_metrics") or {}).get("capital", {}).get("market_cap") or 0.0)
    sector_info = _classify_sector_profile(sector, industry)

    # =========================================================================
    # 1. PIOTROSKI F-SCORE (0 a 9 puntos) con semáforo de proximidad y condición
    # =========================================================================
    ni_curr = get_val("Beneficio Neto", y_curr)
    ni_prev = get_val("Beneficio Neto", y_prev)
    ta_curr = get_val("Total activo", y_curr)
    ta_prev = get_val("Total activo", y_prev)
    cfo_curr = get_val("Efectivo de Operaciones (CFO)", y_curr)

    roa_curr = _safe_div(ni_curr, ta_curr) * 100.0
    roa_prev = _safe_div(ni_prev, ta_prev) * 100.0

    ltd_curr = get_val("Deuda a largo plazo", y_curr)
    ltd_prev = get_val("Deuda a largo plazo", y_prev)
    ltd_ratio_curr = _safe_div(ltd_curr, ta_curr) * 100.0
    ltd_ratio_prev = _safe_div(ltd_prev, ta_prev) * 100.0

    cr_curr = _safe_div(get_val("Total activo corriente", y_curr), get_val("Total pasivo corriente", y_curr))
    cr_prev = _safe_div(get_val("Total activo corriente", y_prev), get_val("Total pasivo corriente", y_prev))

    shares_curr = get_val("Acciones en Circulación (Diluidas)", y_curr) or get_val("Acciones en Circulación (Básicas)", y_curr)
    shares_prev = get_val("Acciones en Circulación (Diluidas)", y_prev) or get_val("Acciones en Circulación (Básicas)", y_prev)

    gm_curr = _safe_div(get_val("Beneficio Bruto", y_curr), get_val("Ingresos Totales", y_curr)) * 100.0
    gm_prev = _safe_div(get_val("Beneficio Bruto", y_prev), get_val("Ingresos Totales", y_prev)) * 100.0

    at_curr = _safe_div(get_val("Ingresos Totales", y_curr), ta_curr)
    at_prev = _safe_div(get_val("Ingresos Totales", y_prev), ta_prev)

    f1_pass = roa_curr > 0
    f1_near = (not f1_pass) and (roa_curr >= -1.5)

    f2_pass = cfo_curr > 0
    f2_near = (not f2_pass) and (ta_curr > 0 and _safe_div(cfo_curr, ta_curr) >= -0.015)

    f3_pass = roa_curr > roa_prev
    f3_near = (not f3_pass) and ((roa_curr - roa_prev) >= -1.0)

    f4_pass = cfo_curr > ni_curr
    f4_near = (not f4_pass) and (abs(ni_curr) > 0 and _safe_div(cfo_curr, abs(ni_curr)) >= 0.85)

    f5_pass = ltd_ratio_curr <= ltd_ratio_prev
    f5_near = (not f5_pass) and ((ltd_ratio_curr - ltd_ratio_prev) <= 2.0)

    f6_pass = cr_curr > cr_prev
    f6_near = (not f6_pass) and (cr_prev > 0 and (cr_prev - cr_curr) <= 0.10)

    f7_pass = (shares_curr <= shares_prev * 1.005) if (shares_curr > 0 and shares_prev > 0) else True
    f7_near = (not f7_pass) and (shares_prev > 0 and shares_curr <= shares_prev * 1.02)

    f8_pass = gm_curr > gm_prev
    f8_near = (not f8_pass) and ((gm_prev - gm_curr) <= 1.0)

    f9_pass = at_curr > at_prev
    f9_near = (not f9_pass) and (at_prev > 0 and (at_prev - at_curr) <= 0.05)

    piotroski_criteria = [
        {
            "id": "F1",
            "short_label": "ROA > 0",
            "group": "Rentabilidad",
            "name": "ROA Positivo (Beneficio Neto / Activos)",
            "target_rule": "Debe ser > 0,00%",
            "passed": f1_pass,
            "status": _evaluate_criterion_status(f1_pass, f1_near),
            "curr_display": f"{roa_curr:.2f}%",
            "prev_display": f"{roa_prev:.2f}%",
            "detail": "Genera utilidad neta positiva sobre su base de activos.",
        },
        {
            "id": "F2",
            "short_label": "CFO > 0",
            "group": "Rentabilidad",
            "name": "Flujo de Caja Operativo Positivo",
            "target_rule": "Debe ser > US$ 0 MM",
            "passed": f2_pass,
            "status": _evaluate_criterion_status(f2_pass, f2_near),
            "curr_display": f"US$ {cfo_curr:,.0f} MM",
            "prev_display": f"US$ {get_val('Efectivo de Operaciones (CFO)', y_prev):,.0f} MM",
            "detail": "La operación principal genera caja real positiva.",
        },
        {
            "id": "F3",
            "short_label": "ΔROA > 0",
            "group": "Rentabilidad",
            "name": "Mejora interanual del ROA",
            "target_rule": f"Debe superar {roa_prev:.2f}% ({y_prev})",
            "passed": f3_pass,
            "status": _evaluate_criterion_status(f3_pass, f3_near),
            "curr_display": f"{roa_curr:.2f}%",
            "prev_display": f"{roa_prev:.2f}%",
            "detail": "La rentabilidad sobre activos creció respecto al ejercicio anterior.",
        },
        {
            "id": "F4",
            "short_label": "CFO > BN",
            "group": "Rentabilidad",
            "name": "Calidad de ganancias (Caja > Contable)",
            "target_rule": f"CFO debe superar US$ {ni_curr:,.0f} MM",
            "passed": f4_pass,
            "status": _evaluate_criterion_status(f4_pass, f4_near),
            "curr_display": f"CFO {cfo_curr:,.0f} vs BN {ni_curr:,.0f}",
            "prev_display": "-",
            "detail": "Evita ganancias contables artificiales respaldadas solo por devengamientos.",
        },
        {
            "id": "F5",
            "short_label": "Deuda ↓",
            "group": "Apalancamiento y Liquidez",
            "name": "Reducción de deuda largo plazo / Activos",
            "target_rule": f"Debe ser ≤ {ltd_ratio_prev:.2f}% ({y_prev})",
            "passed": f5_pass,
            "status": _evaluate_criterion_status(f5_pass, f5_near),
            "curr_display": f"{ltd_ratio_curr:.2f}%",
            "prev_display": f"{ltd_ratio_prev:.2f}%",
            "detail": "No incrementó el peso de la deuda financiera de largo plazo.",
        },
        {
            "id": "F6",
            "short_label": "Liq. ↑",
            "group": "Apalancamiento y Liquidez",
            "name": "Mejora de liquidez corriente",
            "target_rule": f"Debe superar {cr_prev:.2f}x ({y_prev})",
            "passed": f6_pass,
            "status": _evaluate_criterion_status(f6_pass, f6_near),
            "curr_display": f"{cr_curr:.2f}x",
            "prev_display": f"{cr_prev:.2f}x",
            "detail": "Mayor cobertura de pasivos de corto plazo con activos corrientes.",
        },
        {
            "id": "F7",
            "short_label": "Sin dilución",
            "group": "Apalancamiento y Liquidez",
            "name": "Sin emisión dilutiva de acciones",
            "target_rule": f"Acciones ≤ {shares_prev:,.1f} MM ({y_prev})" if shares_prev > 0 else "Sin nuevas emisiones netas",
            "passed": f7_pass,
            "status": _evaluate_criterion_status(f7_pass, f7_near),
            "curr_display": f"{shares_curr:,.1f} MM" if shares_curr > 0 else "N/D",
            "prev_display": f"{shares_prev:,.1f} MM" if shares_prev > 0 else "N/D",
            "detail": "No financió operaciones emitiendo nuevas acciones que diluyan al inversor.",
        },
        {
            "id": "F8",
            "short_label": "M. Bruto ↑",
            "group": "Eficiencia Operativa",
            "name": "Expansión de Margen Bruto",
            "target_rule": f"Debe superar {gm_prev:.2f}% ({y_prev})",
            "passed": f8_pass,
            "status": _evaluate_criterion_status(f8_pass, f8_near),
            "curr_display": f"{gm_curr:.2f}%",
            "prev_display": f"{gm_prev:.2f}%",
            "detail": "Mayor poder de fijación de precios o eficiencia de costos directos.",
        },
        {
            "id": "F9",
            "short_label": "Rotación ↑",
            "group": "Eficiencia Operativa",
            "name": "Mayor rotación de activos",
            "target_rule": f"Debe superar {at_prev:.2f}x ({y_prev})",
            "passed": f9_pass,
            "status": _evaluate_criterion_status(f9_pass, f9_near),
            "curr_display": f"{at_curr:.2f}x",
            "prev_display": f"{at_prev:.2f}x",
            "detail": "Genera más facturación por cada dólar de activo invertido.",
        },
    ]

    f_score = sum(1 for c in piotroski_criteria if c["passed"])
    if f_score >= 7:
        f_zone = "Fortaleza Financiera Alta"
        f_color = "emerald"
    elif f_score >= 4:
        f_zone = "Salud Financiera Moderada / Neutra"
        f_color = "amber"
    else:
        f_zone = "Debilidad Operativa / Balance Frágil"
        f_color = "red"

    # =========================================================================
    # 2. ALTMAN Z-SCORE (1968) Y Z''-SCORE (NO MANUFACTURERAS / SERVICIOS)
    # =========================================================================
    wc = get_val("Total activo corriente", y_curr) - get_val("Total pasivo corriente", y_curr)
    re = get_val("Ganancias retenidas", y_curr)
    ebit_curr = get_val("Beneficio Operativo", y_curr)
    tl_curr = get_val("Total pasivo", y_curr)
    bv_equity = get_val("Patrimonio neto", y_curr)
    sales_curr = get_val("Ingresos Totales", y_curr)

    x1 = _safe_div(wc, ta_curr)
    x2 = _safe_div(re, ta_curr)
    x3 = _safe_div(ebit_curr, ta_curr)
    x4_mkt = _safe_div(mcap_mm if mcap_mm > 0 else bv_equity, tl_curr)
    x4_book = _safe_div(bv_equity, tl_curr)
    x5 = _safe_div(sales_curr, ta_curr)

    z_original = round((1.2 * x1) + (1.4 * x2) + (3.3 * x3) + (0.6 * x4_mkt) + (1.0 * x5), 2)
    z_double_prime = round((6.56 * x1) + (3.26 * x2) + (6.72 * x3) + (1.05 * x4_book), 2)

    if z_original > 2.99:
        z_orig_zone = "Zona Segura (> 2,99)"
        z_orig_color = "emerald"
    elif z_original >= 1.81:
        z_orig_zone = "Zona Gris / Precaución (1,81 – 2,99)"
        z_orig_color = "amber"
    else:
        z_orig_zone = "Zona de Estrés Financiero (< 1,81)"
        z_orig_color = "red"

    if z_double_prime > 2.60:
        z_dp_zone = "Zona Segura (> 2,60)"
        z_dp_color = "emerald"
    elif z_double_prime >= 1.10:
        z_dp_zone = "Zona Gris / Precaución (1,10 – 2,60)"
        z_dp_color = "amber"
    else:
        z_dp_zone = "Zona de Estrés Financiero (< 1,10)"
        z_dp_color = "red"

    # =========================================================================
    # 3. RESUMEN DUPONT (3 Y 5 FACTORES) DEL ÚLTIMO EJERCICIO
    # =========================================================================
    ebt_curr = get_val("Beneficio antes de Impuestos", y_curr)
    net_margin_pct = _safe_div(ni_curr, sales_curr) * 100.0
    asset_turnover = _safe_div(sales_curr, ta_curr)
    equity_multiplier = _safe_div(ta_curr, bv_equity)
    roe_dupont = _safe_div(ni_curr, bv_equity) * 100.0

    tax_burden = _safe_div(ni_curr, ebt_curr)
    interest_burden = _safe_div(ebt_curr, ebit_curr)
    ebit_margin_pct = _safe_div(ebit_curr, sales_curr) * 100.0

    return {
        "ticker": sym,
        "company_name": company_name,
        "sector": sector or "No especificado",
        "industry": industry or "No especificada",
        "fiscal_year_curr": y_curr,
        "fiscal_year_prev": y_prev,
        "sector_applicability": sector_info,
        "piotroski": {
            "score": f_score,
            "max_score": 9,
            "zone": f_zone,
            "color": f_color,
            "applicable": sector_info["piotroski_applicable"],
            "warning": sector_info["piotroski_warning"],
            "criteria": piotroski_criteria,
        },
        "altman": {
            "applicable": sector_info["altman_applicable"],
            "recommended_variant": sector_info["altman_recommended_variant"],
            "warning": sector_info["altman_warning"],
            "z_original": {
                "score": z_original,
                "zone": z_orig_zone,
                "color": z_orig_color,
                "thresholds": "Segura > 2,99 | Gris 1,81–2,99 | Estrés < 1,81",
            },
            "z_double_prime": {
                "score": z_double_prime,
                "zone": z_dp_zone,
                "color": z_dp_color,
                "thresholds": "Segura > 2,60 | Gris 1,10–2,60 | Estrés < 1,10",
            },
            "components": [
                {"code": "X1", "label": "Capital de Trabajo / Activos Totales", "value": round(x1, 3)},
                {"code": "X2", "label": "Ganancias Retenidas / Activos Totales", "value": round(x2, 3)},
                {"code": "X3", "label": "EBIT / Activos Totales", "value": round(x3, 3)},
                {"code": "X4 (Mkt)", "label": "Market Cap / Pasivo Total", "value": round(x4_mkt, 3)},
                {"code": "X4 (Book)", "label": "Patrimonio Contable / Pasivo Total", "value": round(x4_book, 3)},
                {"code": "X5", "label": "Ventas / Activos Totales (solo Z original)", "value": round(x5, 3)},
            ],
        },
        "dupont": {
            "roe_pct": round(roe_dupont, 2),
            "three_factor": {
                "net_margin_pct": round(net_margin_pct, 2),
                "asset_turnover": round(asset_turnover, 2),
                "equity_multiplier": round(equity_multiplier, 2),
            },
            "five_factor": {
                "tax_burden": round(tax_burden, 2),
                "interest_burden": round(interest_burden, 2),
                "ebit_margin_pct": round(ebit_margin_pct, 2),
                "asset_turnover": round(asset_turnover, 2),
                "equity_multiplier": round(equity_multiplier, 2),
            },
        },
    }