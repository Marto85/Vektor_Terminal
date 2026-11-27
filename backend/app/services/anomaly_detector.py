"""Motor de detección de eventos extraordinarios (R1–R15) con línea base limpia de 2 pasadas.

Reglas de diseño:
- Compara TTM (y run-rate de últimos 2 trimestres) contra una ventana histórica limpia
  de hasta 8 años (10 años para R12 PICO_CICLICO), excluyendo años anómalos en 2 pasadas.
- Si quedan menos de 4 ejercicios limpios, reporta confianza baja y no aplica ajuste automático.
- Distingue compresión de margen por inversión (reversible) vs deterioro estructural.
- Cubre entidades financieras (R15) en lugar de omitirlas.
"""
from __future__ import annotations

from statistics import median, stdev
from typing import Any, Callable


def compute_clean_baseline(
    yearly_series: list[tuple[str, float]],
    trigger_fn: Callable[[float, float], bool],
    min_clean: int = 4,
    max_years: int = 8,
) -> dict[str, Any]:
    """Calcula la línea base ('ventana normal') en 2 pasadas excluyendo años anómalos."""
    series = [(y, float(v)) for y, v in yearly_series if v is not None][-max_years:]
    if not series:
        return {
            "baseline": None,
            "pass1_median": None,
            "clean_years": [],
            "excluded_years": [],
            "confidence": "low",
            "auto_adjust": False,
        }

    vals = [v for _, v in series]
    pass1 = float(median(vals))
    clean = [(y, v) for y, v in series if not trigger_fn(v, pass1)]
    excluded = [y for y, v in series if trigger_fn(v, pass1)]

    if len(clean) >= min_clean:
        baseline = float(median([v for _, v in clean]))
        return {
            "baseline": baseline,
            "pass1_median": pass1,
            "clean_years": [y for y, _ in clean],
            "excluded_years": excluded,
            "confidence": "high",
            "auto_adjust": True,
        }

    # Menos de min_clean años limpios -> confianza baja, sin ajuste automático
    return {
        "baseline": pass1,
        "pass1_median": pass1,
        "clean_years": [y for y, _ in clean],
        "excluded_years": excluded,
        "confidence": "low",
        "auto_adjust": False,
    }


def _safe_multiple(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den <= 0:
        return None
    val = num / den
    if val <= 0 or val > 1000:
        return None
    return round(val, 2)


def _impact_per_share(impact_mm: float | None, shares_mm: float | None) -> float | None:
    if impact_mm is None or shares_mm is None or shares_mm <= 0:
        return None
    return round(impact_mm / shares_mm, 2)


def _extract_q_series(
    quarterly_rows: list[dict[str, Any]] | None,
    metric_name: str,
    fx_rate: float = 1.0,
) -> list[tuple[str, float]]:
    if not quarterly_rows:
        return []
    row = next((r for r in quarterly_rows if r.get("Métrica") == metric_name), None)
    if not row:
        return []
    q_cols = [
        k for k in row.keys()
        if k not in ("Métrica", "Sección", "is_pct")
        and ("-Q" in str(k) or str(k).strip().startswith("Q"))
    ]
    out: list[tuple[str, float]] = []
    for k in q_cols:
        v = row.get(k)
        if isinstance(v, (int, float)):
            out.append((str(k), float(v) * fx_rate))
    return out


def detect_anomalies(
    *,
    valid_years: list[str],
    get_m: Callable[[str, str], float],
    ttm_data: dict[str, Any] | None = None,
    quarterly_rows: list[dict[str, Any]] | None = None,
    fx_rate: float = 1.0,
    reporting_currency: str = "USD",
    current_mcap_mm: float | None = None,
    current_ev_mm: float | None = None,
    shares_mm: float | None = None,
    ltm_multiples: dict[str, float | None] | None = None,
    is_financial: bool = False,
    sector: str = "",
    fallback_ebit_margin_pct: float = 15.0,
    dcf_growth_pct: float | None = None,
    hist_roe_pcts: list[float] | None = None,
    current_roe_pct: float | None = None,
) -> dict[str, Any]:
    """Ejecuta el catálogo completo R1–R15 y devuelve flags, comparaciones y parámetros normalizados."""
    ltm_multiples = ltm_multiples or {}
    ttm_data = ttm_data or {}
    ttm_flows = ttm_data.get("ttm") or {}
    ttm_complete = bool(ttm_data.get("is_complete"))
    cutoff_label = ttm_data.get("cutoff_label") or (f"FY {valid_years[-1]}" if valid_years else "N/D")

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
            "margin_classification": "uncertain",
            "roic_incremental_ttm_pct": None,
            "confidence": "low",
        }

    latest_y = valid_years[-1]
    prev_y = valid_years[-2] if len(valid_years) >= 2 else None

    def _ttm_or_annual(metric: str, default: float = 0.0) -> float:
        if ttm_complete and metric in ttm_flows and ttm_flows[metric] is not None:
            return float(ttm_flows[metric])
        return float(get_m(metric, latest_y) or default)

    rev_curr = _ttm_or_annual("Ingresos Totales")
    ebit_curr = _ttm_or_annual("Beneficio Operativo")
    if ebit_curr == 0.0 and rev_curr > 0 and fallback_ebit_margin_pct > 0:
        ebit_curr = rev_curr * (fallback_ebit_margin_pct / 100.0)

    int_exp_curr = abs(_ttm_or_annual("Gastos por Intereses"))
    effective_op = ebit_curr
    if not is_financial and ebit_curr > 0 and int_exp_curr > (ebit_curr * 0.20):
        effective_op = max(ebit_curr - int_exp_curr, 0.0)

    da_curr = abs(_ttm_or_annual("Depreciación y Amortización"))
    net_inc_curr = _ttm_or_annual("Beneficio Neto")
    ebt_curr = _ttm_or_annual("Beneficio antes de Impuestos")
    tax_curr = _ttm_or_annual("Gasto por Impuesto a las Ganancias")
    cfo_curr = _ttm_or_annual("Efectivo de Operaciones (CFO)")
    capex_curr = abs(_ttm_or_annual("Gastos de capital (CapEx)"))
    fcf_curr = _ttm_or_annual("Flujo de caja libre (FCF)")
    if ttm_complete and "Efectivo de Operaciones (CFO)" in ttm_flows and "Gastos de capital (CapEx)" in ttm_flows:
        fcf_curr = cfo_curr - capex_curr
    sbc_curr = abs(_ttm_or_annual("Compensación basada en acciones"))
    wc_curr = _ttm_or_annual("Cambios en el capital de trabajo")
    non_op_curr = _ttm_or_annual("Ingresos (Gastos) No Operativos") + _ttm_or_annual("Ganancia/Pérdida por venta de activos")
    gross_profit_curr = _ttm_or_annual("Beneficio Bruto")
    sga_curr = abs(_ttm_or_annual("Gastos Generales y Administrativos"))
    mkt_curr = abs(_ttm_or_annual("Gastos de Venta y Marketing"))
    fulfill_curr = abs(_ttm_or_annual("Costos de Logística y Fulfillment"))
    rnd_curr = abs(_ttm_or_annual("Investigación y Desarrollo"))
    acq_curr = abs(_ttm_or_annual("Adquisiciones de Negocios"))

    # Crecimiento de ingresos (TTM 2Q YoY o anual)
    rev_growth_yoy_pct = ttm_data.get("rev_yoy_2q_pct")
    if rev_growth_yoy_pct is None and prev_y:
        rev_prev = get_m("Ingresos Totales", prev_y)
        if rev_prev > 0 and get_m("Ingresos Totales", latest_y) > 0:
            rev_growth_yoy_pct = round(((get_m("Ingresos Totales", latest_y) / rev_prev) - 1.0) * 100.0, 2)

    eff_tax = 0.21
    if ebt_curr > 0 and tax_curr > 0:
        eff_tax = min(max(tax_curr / ebt_curr, 0.05), 0.55)

    ebit_margin_pct = (
        round((effective_op / rev_curr) * 100.0, 2)
        if (rev_curr > 0 and effective_op != 0.0)
        else round(fallback_ebit_margin_pct, 2)
    )
    capex_curr_pct = round((capex_curr / rev_curr) * 100.0, 2) if rev_curr > 0 else 10.0

    flags: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []

    def _add_flag(
        *,
        rule_id: str,
        code: str,
        severity: str,
        ftype: str,
        title: str,
        detail: str,
        evidence: dict[str, Any] | None = None,
        adjustment: dict[str, Any] | None = None,
        impact_mm: float | None = None,
        confidence: str = "high",
        enabled: bool = True,
        legacy_code: str | None = None,
    ) -> None:
        flags.append({
            "rule_id": rule_id,
            "code": legacy_code or code,
            "canonical_code": code,
            "severity": severity,
            "type": ftype,
            "title": title,
            "detail": detail,
            "evidence": evidence or {},
            "adjustment": adjustment,
            "impact_mm": round(impact_mm, 2) if impact_mm is not None else None,
            "impact_per_share": _impact_per_share(impact_mm, shares_mm),
            "confidence": confidence,
            "enabled": enabled,
            "cutoff": cutoff_label,
        })

    # ------------------------------------------------------------------
    # R14 CALIDAD_DATO (se evalúa primero para informar confianza)
    # ------------------------------------------------------------------
    missing_reasons: list[str] = []
    if not ttm_complete and len(valid_years) < 4:
        missing_reasons.append("menos de 4 trimestres consecutivos y menos de 4 ejercicios anuales")
    elif not ttm_complete and ttm_data.get("quality_warning"):
        missing_reasons.append(str(ttm_data["quality_warning"]))
    if len(valid_years) < 4:
        missing_reasons.append(f"solo {len(valid_years)} ejercicios anuales disponibles (mínimo 4 para línea base robusta)")

    overall_confidence = "high" if (len(valid_years) >= 4) else "low"
    if missing_reasons:
        overall_confidence = "low" if len(valid_years) < 4 else "medium"
        _add_flag(
            rule_id="R14",
            code="CALIDAD_DATO",
            severity="info",
            ftype="data_quality",
            title="Cobertura histórica / trimestral parcial (CALIDAD_DATO)",
            detail=f"Advertencia de calidad de datos ({cutoff_label}): {'; '.join(missing_reasons)}.",
            evidence={"valid_years": len(valid_years), "ttm_complete": ttm_complete, "reasons": missing_reasons},
            adjustment=None,
            confidence=overall_confidence,
            enabled=False,
        )

    # ------------------------------------------------------------------
    # Líneas base de 2 pasadas (hasta 8 años)
    # ------------------------------------------------------------------
    hist_capex_series = [
        (y, (abs(get_m("Gastos de capital (CapEx)", y)) / get_m("Ingresos Totales", y)) * 100.0)
        for y in valid_years[:-1]
        if get_m("Ingresos Totales", y) > 0 and get_m("Gastos de capital (CapEx)", y) != 0.0
    ]
    capex_base_info = compute_clean_baseline(
        hist_capex_series,
        trigger_fn=lambda v, med: (med > 0 and v >= med * 1.4 and (v - med) >= 4.0),
        min_clean=4,
        max_years=8,
    )
    med_capex_pct = (
        float(capex_base_info["baseline"])
        if capex_base_info["baseline"] is not None
        else ((da_curr / rev_curr) * 100.0 if rev_curr > 0 else 8.0)
    )
    capex_maint_pct = round(med_capex_pct, 2)

    hist_margin_series = [
        (y, (get_m("Beneficio Operativo", y) / get_m("Ingresos Totales", y)) * 100.0)
        for y in valid_years[:-1]
        if get_m("Ingresos Totales", y) > 0 and get_m("Beneficio Operativo", y) != 0.0
    ]
    margin_base_info = compute_clean_baseline(
        hist_margin_series,
        trigger_fn=lambda v, med: v <= med - max(3.0, 0.25 * abs(med)),
        min_clean=4,
        max_years=8,
    )
    base_margin_pct = float(margin_base_info["baseline"]) if margin_base_info["baseline"] is not None else ebit_margin_pct

    hist_tax_series = [
        (y, (get_m("Gasto por Impuesto a las Ganancias", y) / get_m("Beneficio antes de Impuestos", y)) * 100.0)
        for y in valid_years[:-1]
        if get_m("Beneficio antes de Impuestos", y) > 0 and get_m("Gasto por Impuesto a las Ganancias", y) > 0
    ]
    tax_base_info = compute_clean_baseline(
        hist_tax_series,
        trigger_fn=lambda v, med: v < 10.0 or v > 35.0 or abs(v - med) >= 8.0,
        min_clean=4,
        max_years=8,
    )
    base_tax_pct = float(tax_base_info["baseline"]) if tax_base_info["baseline"] is not None else round(eff_tax * 100.0, 2)

    adjusted_fcf = fcf_curr
    adjusted_net_inc = net_inc_curr
    normalized_ebit_margin_pct = ebit_margin_pct
    normalized_tax_rate_pct = round(min(max(eff_tax * 100.0, 10.0), 35.0), 2)
    margin_classification = "normal"
    roic_incremental_ttm_pct: float | None = None

    # ------------------------------------------------------------------
    # R15 FINANCIERA (bancos / seguros / fintechs reguladas)
    # ------------------------------------------------------------------
    if is_financial:
        prov_curr = abs(_ttm_or_annual("Provisiones para Pérdidas Crediticias"))
        prov_series = [
            (y, (abs(get_m("Provisiones para Pérdidas Crediticias", y)) / get_m("Ingresos Totales", y)) * 100.0)
            for y in valid_years[:-1]
            if get_m("Ingresos Totales", y) > 0 and get_m("Provisiones para Pérdidas Crediticias", y) != 0.0
        ]
        prov_base = compute_clean_baseline(
            prov_series,
            trigger_fn=lambda v, med: med > 0 and (v >= med * 1.5 or (v - med) >= 2.0),
            min_clean=3,
            max_years=8,
        )
        prov_ratio_curr = (prov_curr / rev_curr) * 100.0 if rev_curr > 0 else 0.0
        prov_med = float(prov_base["baseline"]) if prov_base["baseline"] is not None else None

        fin_issues: list[str] = []
        if prov_med is not None and prov_curr > 0 and (prov_ratio_curr >= prov_med * 1.5 or (prov_ratio_curr - prov_med) >= 2.0):
            fin_issues.append(f"provisiones crediticias en {prov_ratio_curr:.1f}% de ingresos vs base {prov_med:.1f}%")
        if ebt_curr != 0 and abs(non_op_curr) > abs(ebt_curr) * 0.15:
            fin_issues.append(f"resultados no recurrentes de cartera/inversiones por US$ {non_op_curr:,.1f} MM")
        if current_roe_pct is not None and hist_roe_pcts and len(hist_roe_pcts) >= 3:
            roe_med = float(median(hist_roe_pcts))
            if abs(current_roe_pct - roe_med) >= 4.0:
                fin_issues.append(f"ROE actual ({current_roe_pct:.1f}%) alejado de mediana del ciclo ({roe_med:.1f}%)")

        if fin_issues:
            _add_flag(
                rule_id="R15",
                code="FINANCIERA",
                severity="warning",
                ftype="financial_entity",
                title="Desviación extraordinaria en entidad financiera",
                detail=f"Evaluación específica financiera ({cutoff_label}): {'; '.join(fin_issues)}.",
                evidence={"prov_ratio_pct": round(prov_ratio_curr, 2), "prov_baseline_pct": prov_med, "roe_pct": current_roe_pct},
                adjustment=None,
                confidence="medium",
                enabled=False,
            )

    # ------------------------------------------------------------------
    # Reglas operativas no financieras (R1–R10, R12)
    # ------------------------------------------------------------------
    if not is_financial:
        # Calculamos ROIC incremental TTM informativo si hay ejercicio previo
        if prev_y and rev_curr > 0:
            ebit_prev = get_m("Beneficio Operativo", prev_y)
            delta_nopat = (effective_op - ebit_prev) * (1.0 - eff_tax)
            reinv_capital = max(capex_curr - da_curr, 0.0) + max(-wc_curr, 0.0)
            if reinv_capital > rev_curr * 0.02:
                roic_incremental_ttm_pct = round((delta_nopat / reinv_capital) * 100.0, 2)

        # R1 CAPEX_CICLO
        if rev_curr > 0 and capex_curr > 0:
            q_capex = _extract_q_series(quarterly_rows, "Gastos de capital (CapEx)", fx_rate)
            q_rev = dict(_extract_q_series(quarterly_rows, "Ingresos Totales", fx_rate))
            q_da = dict(_extract_q_series(quarterly_rows, "Depreciación y Amortización", fx_rate))
            high_growth = rev_growth_yoy_pct is not None and rev_growth_yoy_pct >= 25.0
            da_mult_threshold = 2.5 if high_growth else 1.8

            q_persist_ok = True
            q_hit_count = 0
            if len(q_capex) >= 4:
                for qk, q_cx in q_capex[-4:]:
                    qv_rev = q_rev.get(qk, 0.0)
                    qv_da = abs(q_da.get(qk, 0.0))
                    cx_pct = (abs(q_cx) / qv_rev * 100.0) if qv_rev > 0 else 0.0
                    cond_q_base = med_capex_pct > 0 and cx_pct >= med_capex_pct * 1.35 and (cx_pct - med_capex_pct) >= 3.0
                    cond_q_da = qv_da > 0 and abs(q_cx) >= qv_da * da_mult_threshold
                    if cond_q_base or cond_q_da:
                        q_hit_count += 1
                q_persist_ok = q_hit_count >= 2

            cond_ratio = med_capex_pct > 0 and capex_curr_pct >= med_capex_pct * 1.4 and (capex_curr_pct - med_capex_pct) >= 4.0
            cond_da = da_curr > 0 and capex_curr >= da_curr * da_mult_threshold
            if (cond_ratio or cond_da) and q_persist_ok:
                maint_capex_mm = max(rev_curr * (med_capex_pct / 100.0), da_curr * 0.90)
                excess_capex_mm = max(capex_curr - maint_capex_mm, 0.0)
                if excess_capex_mm > 0:
                    adjusted_fcf = round(cfo_curr - maint_capex_mm, 2)
                    lease_debt = abs(get_m("Pasivo por Arrendamientos", latest_y))
                    lease_note = (
                        f" Nota: existen pasivos por arrendamientos de US$ {lease_debt:,.1f} MM (parte de la expansión puede estar capitalizada vía leasing)."
                        if lease_debt > rev_curr * 0.05
                        else ""
                    )
                    roic_note = (
                        f" ROIC incremental TTM estimado: {roic_incremental_ttm_pct:.1f}%."
                        if roic_incremental_ttm_pct is not None
                        else ""
                    )
                    can_auto = bool(capex_base_info["auto_adjust"] or cond_da)
                    _add_flag(
                        rule_id="R1",
                        code="CAPEX_CICLO",
                        legacy_code="CAPEX_EXPANSION",
                        severity="warning",
                        ftype="investment_cycle",
                        title="Ciclo extraordinario de inversión (CapEx de crecimiento)",
                        detail=(
                            f"El CapEx ({cutoff_label}: US$ {capex_curr:,.2f} MM, {capex_curr_pct:.1f}% de ventas) "
                            f"supera la línea base limpia ({capex_maint_pct:.1f}% de ventas). "
                            f"Excedente de expansión: US$ {excess_capex_mm:,.2f} MM.{roic_note}{lease_note}"
                        ),
                        evidence={
                            "capex_curr_pct": capex_curr_pct,
                            "capex_baseline_pct": capex_maint_pct,
                            "clean_years": capex_base_info["clean_years"],
                            "quarters_persisted": q_hit_count,
                            "roic_incremental_ttm_pct": roic_incremental_ttm_pct,
                        },
                        adjustment={
                            "param": "capex_pct",
                            "from": capex_curr_pct,
                            "to": capex_maint_pct,
                            "maint_capex_mm": round(maint_capex_mm, 2),
                            "adjusted_fcf_mm": adjusted_fcf,
                        },
                        impact_mm=-excess_capex_mm,
                        confidence=capex_base_info["confidence"],
                        enabled=can_auto,
                    )
                    rep_pfcf = ltm_multiples.get("pfcf")
                    adj_pfcf = _safe_multiple(current_mcap_mm, adjusted_fcf)
                    if rep_pfcf is not None and adj_pfcf is not None:
                        comparisons.append({
                            "metric": "P / FCF (LTM)",
                            "reported": f"{rep_pfcf:.2f}x",
                            "adjusted": f"{adj_pfcf:.2f}x",
                            "note": "Normalizando CapEx a tasa histórica limpia",
                        })
                    rep_evfcf = ltm_multiples.get("ev_fcf")
                    adj_evfcf = _safe_multiple(current_ev_mm, adjusted_fcf)
                    if rep_evfcf is not None and adj_evfcf is not None:
                        comparisons.append({
                            "metric": "EV / FCF (LTM)",
                            "reported": f"{rep_evfcf:.2f}x",
                            "adjusted": f"{adj_evfcf:.2f}x",
                            "note": "Normalizando CapEx a tasa histórica limpia",
                        })

        # R2 MARGEN_COMPRIMIDO
        if rev_curr > 0 and len(hist_margin_series) >= 2:
            margin_drop_pp = base_margin_pct - ebit_margin_pct
            threshold_pp = max(3.0, 0.25 * abs(base_margin_pct))

            q_ebit_s = dict(_extract_q_series(quarterly_rows, "Beneficio Operativo", fx_rate))
            q_rev_s = _extract_q_series(quarterly_rows, "Ingresos Totales", fx_rate)
            q_margins = {qk: (q_ebit_s[qk] / qv) * 100.0 for qk, qv in q_rev_s if qv > 0 and qk in q_ebit_s}
            q_yoy_drops = 0
            for qk in list(q_margins.keys())[-2:]:
                if "-Q" in qk:
                    yr_str, q_str = qk.split("-Q")
                    prev_qk = f"{int(yr_str) - 1}-Q{q_str}"
                else:
                    prev_qk = ""
                if prev_qk and prev_qk in q_margins and (q_margins[prev_qk] - q_margins[qk]) >= 1.5:
                    q_yoy_drops += 1

            # Chequeo de desvío en el último trimestre frente a trimestres previos
            if len(q_margins) >= 4:
                q_keys_ordered = [qk for qk, _ in q_rev_s if qk in q_margins]
                last_qk = q_keys_ordered[-1]
                prior_med_q = float(median([q_margins[k] for k in q_keys_ordered[:-1]]))
                q_diff = round(q_margins[last_qk] - prior_med_q, 2)
                if abs(q_diff) >= 2.5:
                    last_q_rev_mm = dict(q_rev_s).get(last_qk, 0.0)
                    _add_flag(
                        rule_id="R2",
                        code="QUARTERLY_RUN_RATE_SHIFT",
                        severity="warning" if q_diff < 0 else "info",
                        ftype="quarterly_shift",
                        title=f"Desvío notable en último trimestre ({last_qk})",
                        detail=(
                            f"El margen EBIT del trimestre {last_qk} ({q_margins[last_qk]:.1f}%) muestra una variación de "
                            f"{q_diff:+.1f} pp frente a la mediana de trimestres previos ({prior_med_q:.1f}%)."
                        ),
                        evidence={"quarter": last_qk, "q_margin_pct": round(q_margins[last_qk], 2), "prior_med_pct": round(prior_med_q, 2)},
                        adjustment=None,
                        impact_mm=(q_diff / 100.0) * last_q_rev_mm,
                        confidence="high",
                        enabled=False,
                    )

            if margin_drop_pp >= threshold_pp or q_yoy_drops >= 2:
                # Desglose de márgenes brutos y gastos operativos
                gp_curr_pct = (gross_profit_curr / rev_curr * 100.0) if gross_profit_curr > 0 else None
                hist_gp = [
                    get_m("Beneficio Bruto", y) / get_m("Ingresos Totales", y) * 100.0
                    for y in valid_years[:-1]
                    if get_m("Ingresos Totales", y) > 0 and get_m("Beneficio Bruto", y) > 0
                ]
                gp_base_pct = float(median(hist_gp)) if hist_gp else None
                gp_delta_pp = (gp_curr_pct - gp_base_pct) if (gp_curr_pct is not None and gp_base_pct is not None) else None

                reinv_opex_curr_pct = ((sga_curr + mkt_curr + fulfill_curr + rnd_curr) / rev_curr * 100.0)
                hist_reinv = [
                    (abs(get_m("Gastos Generales y Administrativos", y))
                     + abs(get_m("Gastos de Venta y Marketing", y))
                     + abs(get_m("Costos de Logística y Fulfillment", y))
                     + abs(get_m("Investigación y Desarrollo", y))) / get_m("Ingresos Totales", y) * 100.0
                    for y in valid_years[:-1]
                    if get_m("Ingresos Totales", y) > 0
                ]
                reinv_base_pct = float(median(hist_reinv)) if hist_reinv else 0.0
                reinv_delta_pp = reinv_opex_curr_pct - reinv_base_pct

                is_growing = (rev_growth_yoy_pct is not None and rev_growth_yoy_pct >= 10.0)
                is_high_growth = (rev_growth_yoy_pct is not None and rev_growth_yoy_pct >= 15.0)
                is_shrinking = (rev_growth_yoy_pct is not None and rev_growth_yoy_pct < 0.0)
                gross_deteriorated = gp_delta_pp is not None and gp_delta_pp < -2.0

                # Si las ventas crecen >= 15% (ej. MELI +35% o AMZN logística), una baja de margen bruto por
                # costos de envío/fulfillment en COGS sigue siendo inversión comercial, no deterioro estructural.
                if (is_growing and not gross_deteriorated and (reinv_delta_pp >= 1.5 or gp_delta_pp is None or gp_delta_pp >= -1.5)) or is_high_growth:
                    margin_classification = "investment"
                    can_auto_margin = bool(margin_base_info["auto_adjust"] or len(hist_margin_series) >= 3)
                    normalized_ebit_margin_pct = round(base_margin_pct, 2)
                    ebit_gap_mm = rev_curr * (margin_drop_pp / 100.0)
                    prov_fintech = abs(_ttm_or_annual("Provisiones para Pérdidas Crediticias"))
                    fintech_note = (
                        f" Incluye provisiones/crédito por US$ {prov_fintech:,.1f} MM (verificar componente fintech/float)."
                        if prov_fintech > 0
                        else ""
                    )
                    _add_flag(
                        rule_id="R2",
                        code="MARGEN_COMPRIMIDO",
                        legacy_code="MARGIN_COMPRESSION_REINVESTMENT",
                        severity="warning",
                        ftype="investment",
                        title="Compresión intencional de márgenes por reinversión",
                        detail=(
                            f"El margen EBIT ({ebit_margin_pct:.1f}%) cayó {margin_drop_pp:.1f} pp frente a la línea base limpia "
                            f"({base_margin_pct:.1f}%) mientras las ventas crecen {rev_growth_yoy_pct or 0:.1f}% interanual. "
                            f"El margen bruto se mantiene estable y el gasto operativo de expansión subió {reinv_delta_pp:+.1f} pp.{fintech_note}"
                        ),
                        evidence={
                            "ebit_margin_pct": ebit_margin_pct,
                            "baseline_margin_pct": round(base_margin_pct, 2),
                            "rev_growth_yoy_pct": rev_growth_yoy_pct,
                            "gross_margin_delta_pp": round(gp_delta_pp, 2) if gp_delta_pp is not None else None,
                            "opex_reinvest_delta_pp": round(reinv_delta_pp, 2),
                            "q_yoy_drops": q_yoy_drops,
                        },
                        adjustment={
                            "param": "ebit_margin_pct",
                            "from": ebit_margin_pct,
                            "to": normalized_ebit_margin_pct,
                            "ebit_gap_mm": round(ebit_gap_mm, 2),
                        },
                        impact_mm=-ebit_gap_mm * (1.0 - eff_tax),
                        confidence=margin_base_info["confidence"],
                        enabled=can_auto_margin,
                    )

                    # Si hay salto de gastos operativos implícitos (GP - EBIT) o declarados, informar OPEX_SPIKE
                    imp_opex_curr_pct = ((gross_profit_curr - effective_op) / rev_curr * 100.0) if gross_profit_curr > 0 else reinv_opex_curr_pct
                    hist_imp_opex = [
                        ((get_m("Beneficio Bruto", y) - get_m("Beneficio Operativo", y)) / get_m("Ingresos Totales", y) * 100.0)
                        for y in valid_years[:-1]
                        if get_m("Ingresos Totales", y) > 0 and get_m("Beneficio Bruto", y) > 0
                    ]
                    imp_opex_base = float(median(hist_imp_opex)) if hist_imp_opex else reinv_base_pct
                    if (imp_opex_curr_pct - imp_opex_base) >= 3.0 or reinv_delta_pp >= 3.0:
                        _add_flag(
                            rule_id="R2",
                            code="OPEX_SPIKE",
                            severity="info",
                            ftype="opex_reinvestment",
                            title="Salto relevante en gastos operativos (SG&A / expansión)",
                            detail=(
                                f"Los gastos operativos pasaron de {imp_opex_base:.1f}% a {imp_opex_curr_pct:.1f}% de ventas "
                                f"({imp_opex_curr_pct - imp_opex_base:+.1f} pp) acompañando el crecimiento de ingresos."
                            ),
                            evidence={"opex_curr_pct": round(imp_opex_curr_pct, 2), "opex_base_pct": round(imp_opex_base, 2)},
                            adjustment=None,
                            impact_mm=-ebit_gap_mm,
                            confidence="high",
                            enabled=False,
                        )

                    rep_ev_ebit = ltm_multiples.get("ev_ebit")
                    norm_ebit_preview = rev_curr * (normalized_ebit_margin_pct / 100.0)
                    adj_ev_ebit = _safe_multiple(current_ev_mm, norm_ebit_preview)
                    if rep_ev_ebit is not None and adj_ev_ebit is not None:
                        comparisons.append({
                            "metric": "EV / EBIT (LTM)",
                            "reported": f"{rep_ev_ebit:.2f}x",
                            "adjusted": f"{adj_ev_ebit:.2f}x",
                            "note": f"Normalizando margen EBIT ({ebit_margin_pct:.1f}% → {normalized_ebit_margin_pct:.1f}%)",
                        })
                elif gross_deteriorated or is_shrinking:
                    margin_classification = "structural"
                    _add_flag(
                        rule_id="R2",
                        code="MARGEN_COMPRIMIDO",
                        severity="warning",
                        ftype="structural",
                        title="Compresión de margen de origen estructural / mix",
                        detail=(
                            f"El margen EBIT ({ebit_margin_pct:.1f}% vs base {base_margin_pct:.1f}%) cae acompañado por "
                            f"{'deterioro de margen bruto' if gross_deteriorated else 'contracción de ventas'}. "
                            f"No se aplica reversión automática a mediana histórica."
                        ),
                        evidence={"ebit_margin_pct": ebit_margin_pct, "baseline_margin_pct": round(base_margin_pct, 2), "gross_margin_delta_pp": gp_delta_pp},
                        adjustment=None,
                        confidence="high",
                        enabled=False,
                    )
                else:
                    margin_classification = "uncertain"
                    _add_flag(
                        rule_id="R2",
                        code="MARGEN_COMPRIMIDO",
                        severity="info",
                        ftype="uncertain",
                        title="Compresión de margen operativa (causa mixta/incierta)",
                        detail=(
                            f"El margen EBIT bajó de {base_margin_pct:.1f}% a {ebit_margin_pct:.1f}% sin confirmación clara "
                            f"de expansión comercial ni deterioro bruto severo. Podés habilitar la normalización manualmente."
                        ),
                        evidence={"ebit_margin_pct": ebit_margin_pct, "baseline_margin_pct": round(base_margin_pct, 2)},
                        adjustment={"param": "ebit_margin_pct", "from": ebit_margin_pct, "to": round(base_margin_pct, 2)},
                        confidence="medium",
                        enabled=False,
                    )

        # R3 NO_RECURRENTE
        if abs(ebit_curr) > 0:
            nopat_curr = ebit_curr * (1.0 - eff_tax)
            non_op_gap = net_inc_curr - nopat_curr
            if abs(non_op_curr) > abs(ebit_curr) * 0.10 or abs(non_op_gap) > abs(ebit_curr) * 0.25:
                extra_item = non_op_curr * (1.0 - eff_tax) if abs(non_op_curr) > abs(ebit_curr) * 0.10 else non_op_gap
                adjusted_net_inc = round(net_inc_curr - extra_item, 2)
                direction = "inflando" if extra_item > 0 else "reduciendo"
                _add_flag(
                    rule_id="R3",
                    code="NO_RECURRENTE",
                    legacy_code="NON_OPERATING_SHOCK",
                    severity="info" if extra_item > 0 else "warning",
                    ftype="non_recurring",
                    title="Partidas no operativas / extraordinarias materiales",
                    detail=(
                        f"Resultados no recurrentes por US$ {extra_item:,.2f} MM netos están {direction} "
                        f"el Beneficio Neto reportado (US$ {net_inc_curr:,.2f} MM)."
                    ),
                    evidence={"non_op_pretax_mm": round(non_op_curr, 2), "net_extra_mm": round(extra_item, 2)},
                    adjustment={"param": "non_recurring_net_mm", "from": round(extra_item, 2), "to": 0.0},
                    impact_mm=extra_item,
                    confidence="high",
                    enabled=True,
                )
                rep_pe = ltm_multiples.get("pe")
                adj_pe = _safe_multiple(current_mcap_mm, adjusted_net_inc)
                if rep_pe is not None and adj_pe is not None:
                    comparisons.append({
                        "metric": "P / E (LTM)",
                        "reported": f"{rep_pe:.2f}x",
                        "adjusted": f"{adj_pe:.2f}x",
                        "note": "Excluyendo impacto no operativo neto",
                    })

        # R4 SBC_ALTA
        sbc_prev = abs(get_m("Compensación basada en acciones", prev_y)) if prev_y else 0.0
        sbc_growth = ((sbc_curr / sbc_prev) - 1.0) * 100.0 if sbc_prev > 0 else None
        sbc_outpacing = (
            sbc_growth is not None
            and rev_growth_yoy_pct is not None
            and (sbc_growth - rev_growth_yoy_pct) > 5.0
            and sbc_curr > 0
        )
        if cfo_curr > 0 and ((sbc_curr / cfo_curr) > 0.25 or sbc_outpacing):
            fcf_ex_sbc = round(fcf_curr - sbc_curr, 2)
            _add_flag(
                rule_id="R4",
                code="SBC_ALTA",
                legacy_code="HIGH_SBC",
                severity="warning",
                ftype="dilution_economic_cost",
                title="Alta Compensación Basada en Acciones (SBC)",
                detail=(
                    f"La SBC asciende a US$ {sbc_curr:,.2f} MM ({(sbc_curr / cfo_curr) * 100:.1f}% del CFO). "
                    f"El FCF ex-SBC sería US$ {fcf_ex_sbc:,.2f} MM."
                ),
                evidence={"sbc_mm": round(sbc_curr, 2), "sbc_pct_cfo": round(sbc_curr / cfo_curr * 100.0, 1)},
                adjustment={"param": "sbc_deduction_mm", "from": 0.0, "to": round(sbc_curr, 2)},
                impact_mm=-sbc_curr,
                confidence="high",
                enabled=False,
            )
            adj_pfcf_sbc = _safe_multiple(current_mcap_mm, fcf_ex_sbc)
            rep_pfcf = ltm_multiples.get("pfcf")
            if rep_pfcf is not None and adj_pfcf_sbc is not None:
                comparisons.append({
                    "metric": "P / FCF (ex-SBC)",
                    "reported": f"{rep_pfcf:.2f}x",
                    "adjusted": f"{adj_pfcf_sbc:.2f}x",
                    "note": "Restando SBC como salida económica real",
                })

        # R5 CAPITAL_TRABAJO (CFO swing o DSO/DIO/DPO > 2 std)
        wc_sigma_alert = False
        if len(valid_years) >= 4 and rev_curr > 0:
            for bal_metric in ("Cuentas por Cobrar", "Inventarios", "Cuentas por Pagar"):
                hist_days = [
                    (get_m(bal_metric, y) / get_m("Ingresos Totales", y)) * 365.0
                    for y in valid_years[:-1]
                    if get_m("Ingresos Totales", y) > 0 and get_m(bal_metric, y) > 0
                ]
                curr_bal = get_m(bal_metric, latest_y)
                if len(hist_days) >= 3 and curr_bal > 0:
                    curr_days = (curr_bal / rev_curr) * 365.0
                    sd = stdev(hist_days)
                    if sd > 1.0 and abs(curr_days - float(median(hist_days))) > 2.0 * sd:
                        wc_sigma_alert = True
                        break

        if (abs(cfo_curr) > 0 and abs(wc_curr) > abs(cfo_curr) * 0.20) or wc_sigma_alert:
            # Si el NWC es positivo de forma recurrente (>=2 de los últimos 3 años o float fintech en alto crecimiento),
            # no debe restarse automáticamente como una "liberación puntual".
            hist_wc_pos = sum(1 for y in valid_years[-4:-1] if get_m("Cambios en el capital de trabajo", y) > 0)
            is_recurring_float = wc_curr > 0 and (hist_wc_pos >= 2 or (rev_growth_yoy_pct is not None and rev_growth_yoy_pct >= 15.0))
            direction_wc = "consumo" if wc_curr < 0 else ("flujo favorable recurrente (float)" if is_recurring_float else "liberación puntual")
            _add_flag(
                rule_id="R5",
                code="CAPITAL_TRABAJO",
                legacy_code="WORKING_CAPITAL_SWING",
                severity="info",
                ftype="working_capital",
                title="Variación relevante en Capital de Trabajo",
                detail=(
                    f"El capital de trabajo registró un {direction_wc} de US$ {abs(wc_curr):,.2f} MM"
                    f"{' y desvío >2σ en días de giro (DSO/DIO/DPO)' if wc_sigma_alert else ''}"
                    f"{'. Al ser recurrente por modelo comercial/fintech no se descuenta automáticamente.' if is_recurring_float else ', alterando la conversión de caja.'}"
                ),
                evidence={"wc_curr_mm": round(wc_curr, 2), "wc_sigma_alert": wc_sigma_alert, "is_recurring_float": is_recurring_float},
                adjustment=None if is_recurring_float else {"param": "nwc_normalization", "from": round(wc_curr, 2), "to": 0.0},
                impact_mm=wc_curr,
                confidence="medium",
                enabled=False if is_recurring_float else (True if abs(wc_curr) > abs(cfo_curr or 1.0) * 0.20 else False),
            )

        # R6 CONVERSION_CAJA
        if net_inc_curr > 0:
            conv_curr = fcf_curr / net_inc_curr
            conv_prev = (
                get_m("Flujo de caja libre (FCF)", prev_y) / get_m("Beneficio Neto", prev_y)
                if prev_y and get_m("Beneficio Neto", prev_y) > 0
                else None
            )
            if (conv_curr < 0.50 or conv_curr > 1.50) and (conv_prev is not None and (conv_prev < 0.50 or conv_prev > 1.50)):
                _add_flag(
                    rule_id="R6",
                    code="CONVERSION_CAJA",
                    severity="info",
                    ftype="cash_conversion",
                    title="Conversión de caja (FCF / Utilidad Neta) atípica por 2 períodos",
                    detail=f"El ratio FCF / Beneficio Neto se ubica en {conv_curr * 100:.0f}% (previo {conv_prev * 100:.0f}%).",
                    evidence={"conversion_curr_pct": round(conv_curr * 100.0, 1), "conversion_prev_pct": round(conv_prev * 100.0, 1)},
                    adjustment=None,
                    confidence="high",
                    enabled=False,
                )

        # R7 TASA_FISCAL
        if ebt_curr > 0 and tax_curr > 0:
            eff_tax_pct = (tax_curr / ebt_curr) * 100.0
            if eff_tax_pct < 10.0 or eff_tax_pct > 35.0 or abs(eff_tax_pct - base_tax_pct) >= 8.0:
                normalized_tax_rate_pct = round(min(max(base_tax_pct, 10.0), 35.0), 2)
                tax_impact_mm = ebt_curr * ((eff_tax_pct - normalized_tax_rate_pct) / 100.0)
                _add_flag(
                    rule_id="R7",
                    code="TASA_FISCAL",
                    severity="info",
                    ftype="tax_anomaly",
                    title="Tasa impositiva efectiva atípica",
                    detail=(
                        f"La tasa efectiva ({eff_tax_pct:.1f}%) se aleja de la línea base limpia ({normalized_tax_rate_pct:.1f}%)."
                    ),
                    evidence={"eff_tax_pct": round(eff_tax_pct, 2), "baseline_tax_pct": normalized_tax_rate_pct},
                    adjustment={"param": "tax_rate_pct", "from": round(eff_tax_pct, 2), "to": normalized_tax_rate_pct},
                    impact_mm=-tax_impact_mm,
                    confidence=tax_base_info["confidence"],
                    enabled=bool(tax_base_info["auto_adjust"]),
                )

        # R8 FINANCIACION_CICLO
        ebitda_curr = effective_op + da_curr
        total_debt_curr = abs(get_m("Deuda Total", latest_y))
        cash_curr = abs(get_m("Efectivo y Equivalentes", latest_y))
        net_debt_curr = total_debt_curr - cash_curr
        nd_ebitda_curr = (net_debt_curr / ebitda_curr) if ebitda_curr > 0 else None
        int_cov = (effective_op / int_exp_curr) if int_exp_curr > 0 else None
        nd_ebitda_prev = None
        if prev_y:
            ebitda_prev = get_m("Beneficio Operativo", prev_y) + abs(get_m("Depreciación y Amortización", prev_y))
            nd_prev = abs(get_m("Deuda Total", prev_y)) - abs(get_m("Efectivo y Equivalentes", prev_y))
            if ebitda_prev > 0:
                nd_ebitda_prev = nd_prev / ebitda_prev
        if (nd_ebitda_curr is not None and nd_ebitda_prev is not None and (nd_ebitda_curr - nd_ebitda_prev) >= 1.0) or (int_cov is not None and int_cov < 3.0):
            lease_debt = abs(get_m("Pasivo por Arrendamientos", latest_y))
            lease_share = (lease_debt / total_debt_curr * 100.0) if total_debt_curr > 0 else 0.0
            _add_flag(
                rule_id="R8",
                code="FINANCIACION_CICLO",
                severity="warning",
                ftype="leverage",
                title="Salto de apalancamiento o cobertura de intereses ajustada",
                detail=(
                    f"Deuda Neta/EBITDA: {nd_ebitda_curr:.2f}x"
                    f"{f' (vs {nd_ebitda_prev:.2f}x previo)' if nd_ebitda_prev is not None else ''}; "
                    f"cobertura de intereses: {f'{int_cov:.2f}x' if int_cov is not None else 'N/D'}."
                    f"{f' Arrendamientos representan {lease_share:.0f}% de la deuda.' if lease_share >= 15 else ''}"
                ),
                evidence={"nd_ebitda": round(nd_ebitda_curr, 2) if nd_ebitda_curr is not None else None, "interest_coverage": round(int_cov, 2) if int_cov is not None else None},
                adjustment=None,
                confidence="high",
                enabled=False,
            )

        # R9 INORGANICO
        tot_assets_curr = abs(get_m("Activos Totales", latest_y))
        goodwill_curr = abs(get_m("Fondo de Comercio (Goodwill)", latest_y))
        goodwill_prev = abs(get_m("Fondo de Comercio (Goodwill)", prev_y)) if prev_y else 0.0
        goodwill_jump = max(goodwill_curr - goodwill_prev, 0.0)
        if (tot_assets_curr > 0 and max(acq_curr, goodwill_jump) > tot_assets_curr * 0.15) or (cfo_curr > 0 and acq_curr > cfo_curr * 0.50):
            _add_flag(
                rule_id="R9",
                code="INORGANICO",
                severity="info",
                ftype="inorganic_growth",
                title="Crecimiento inorgánico relevante (M&A / Goodwill)",
                detail=f"Adquisiciones por US$ {acq_curr:,.1f} MM (salto de goodwill US$ {goodwill_jump:,.1f} MM) pueden inflar el crecimiento aparente de ventas.",
                evidence={"acquisitions_mm": round(acq_curr, 2), "goodwill_jump_mm": round(goodwill_jump, 2)},
                adjustment=None,
                confidence="high",
                enabled=False,
            )

        # R10 DILUCION
        sh_curr = abs(get_m("Acciones en Circulación", latest_y))
        sh_prev = abs(get_m("Acciones en Circulación", prev_y)) if prev_y else 0.0
        sh_3y = abs(get_m("Acciones en Circulación", valid_years[-4])) if len(valid_years) >= 4 else 0.0
        sh_yoy = ((sh_curr / sh_prev) - 1.0) * 100.0 if (sh_curr > 0 and sh_prev > 0) else 0.0
        sh_3y_pct = ((sh_curr / sh_3y) - 1.0) * 100.0 if (sh_curr > 0 and sh_3y > 0) else 0.0
        if sh_yoy > 3.0 or sh_3y_pct > 8.0:
            _add_flag(
                rule_id="R10",
                code="DILUCION",
                severity="warning" if sh_yoy > 5.0 else "info",
                ftype="share_dilution",
                title="Dilución accionaria neta relevante",
                detail=f"Las acciones en circulación crecieron {sh_yoy:+.1f}% interanual ({sh_3y_pct:+.1f}% en 3 años), reduciendo el valor por acción.",
                evidence={"shares_yoy_pct": round(sh_yoy, 2), "shares_3y_pct": round(sh_3y_pct, 2)},
                adjustment=None,
                confidence="high",
                enabled=False,
            )

        # R12 PICO_CICLICO (10 años)
        hist_10y_margins = [
            (y, (get_m("Beneficio Operativo", y) / get_m("Ingresos Totales", y)) * 100.0)
            for y in valid_years[:-1]
            if get_m("Ingresos Totales", y) > 0 and get_m("Beneficio Operativo", y) != 0.0
        ][-10:]
        if len(hist_10y_margins) >= 5:
            med_10y_m = float(median([v for _, v in hist_10y_margins]))
            cyc_sectors = ("energy", "basic materials", "materials", "industrials", "semiconductor", "auto")
            is_cyc = any(k in (sector or "").lower() for k in cyc_sectors)
            if ebit_margin_pct >= med_10y_m + 5.0 and (is_cyc or (med_10y_m > 0 and ebit_margin_pct >= med_10y_m * 1.45)):
                margin_classification = "cyclical_peak"
                normalized_ebit_margin_pct = round(med_10y_m, 2)
                _add_flag(
                    rule_id="R12",
                    code="PICO_CICLICO",
                    severity="warning",
                    ftype="cyclical_peak",
                    title="Margen en pico cíclico respecto a mediana de 10 años",
                    detail=(
                        f"El margen EBIT actual ({ebit_margin_pct:.1f}%) supera en {ebit_margin_pct - med_10y_m:.1f} pp "
                        f"la mediana de ciclo largo ({med_10y_m:.1f}%). La normalización proyecta reversión hacia el promedio del ciclo."
                    ),
                    evidence={"ebit_margin_pct": ebit_margin_pct, "median_10y_pct": round(med_10y_m, 2), "is_cyclical_sector": is_cyc},
                    adjustment={"param": "ebit_margin_pct", "from": ebit_margin_pct, "to": normalized_ebit_margin_pct},
                    impact_mm=rev_curr * ((ebit_margin_pct - med_10y_m) / 100.0) * (1.0 - eff_tax),
                    confidence="high",
                    enabled=True,
                )

    # ------------------------------------------------------------------
    # R11 MONEDA_INFLACION
    # ------------------------------------------------------------------
    high_inf_ccy = {"ARS", "TRY", "VES", "BRL", "MXN", "COP", "CLP"}
    if reporting_currency and reporting_currency.upper() != "USD":
        is_hi = reporting_currency.upper() in high_inf_ccy
        _add_flag(
            rule_id="R11",
            code="MONEDA_INFLACION",
            severity="warning" if is_hi else "info",
            ftype="currency_fx",
            title=f"Reporte en moneda extranjera ({reporting_currency.upper()})",
            detail=(
                f"Los estados contables originales están en {reporting_currency.upper()} (convertidos a USD con tipo de cambio {fx_rate:.4f}). "
                f"{'En economías de alta inflación o devaluación, los márgenes y CapEx históricos pueden distorsionarse.' if is_hi else 'Considerar efecto tipo de cambio al comparar múltiplos históricos.'}"
            ),
            evidence={"reporting_currency": reporting_currency.upper(), "fx_rate": fx_rate},
            adjustment=None,
            confidence="high",
            enabled=False,
        )

    # ------------------------------------------------------------------
    # R13 BRECHA_CRECIMIENTO (RUNRATE2 / 2Q YoY vs crecimiento DCF)
    # ------------------------------------------------------------------
    if dcf_growth_pct is not None and rev_growth_yoy_pct is not None:
        gap_pp = dcf_growth_pct - rev_growth_yoy_pct
        if abs(gap_pp) >= 6.0:
            _add_flag(
                rule_id="R13",
                code="BRECHA_CRECIMIENTO",
                severity="warning" if gap_pp > 6.0 else "info",
                ftype="growth_divergence",
                title="Brecha entre crecimiento reciente y supuesto DCF",
                detail=(
                    f"El modelo asume {dcf_growth_pct:.1f}% anual de ventas mientras los últimos trimestres crecen "
                    f"al {rev_growth_yoy_pct:.1f}% interanual (brecha de {gap_pp:+.1f} pp)."
                ),
                evidence={"dcf_growth_pct": dcf_growth_pct, "recent_yoy_pct": rev_growth_yoy_pct, "gap_pp": round(gap_pp, 2)},
                adjustment=None,
                confidence="high",
                enabled=False,
            )

    normalized_ebit_mm = round(rev_curr * (normalized_ebit_margin_pct / 100.0), 2) if rev_curr > 0 else round(effective_op, 2)
    normalized_net_inc_mm = round(
        adjusted_net_inc + (normalized_ebit_mm - effective_op) * (1.0 - normalized_tax_rate_pct / 100.0),
        2,
    )
    normalized_fcf_mm = round(
        adjusted_fcf + (normalized_ebit_mm - effective_op) * (1.0 - normalized_tax_rate_pct / 100.0),
        2,
    )

    material_flags = [f for f in flags if f.get("code") not in ("CALIDAD_DATO", "MONEDA_INFLACION") or f.get("severity") == "warning"]
    return {
        "has_anomalies": len(material_flags) > 0,
        "flags": flags,
        "comparisons": comparisons,
        "adjusted_fcf_mm": round(adjusted_fcf, 2),
        "capex_current_pct": capex_curr_pct,
        "capex_maint_pct": capex_maint_pct,
        "ebit_margin_pct": ebit_margin_pct,
        "tax_rate_pct": round(eff_tax * 100.0, 2),
        "normalized_ebit_margin_pct": normalized_ebit_margin_pct,
        "normalized_tax_rate_pct": normalized_tax_rate_pct,
        "normalized_ebit_mm": normalized_ebit_mm,
        "normalized_net_inc_mm": normalized_net_inc_mm,
        "normalized_fcf_mm": normalized_fcf_mm,
        "rev_growth_yoy_pct": rev_growth_yoy_pct,
        "margin_classification": margin_classification,
        "roic_incremental_ttm_pct": roic_incremental_ttm_pct,
        "confidence": overall_confidence,
        "cutoff_label": cutoff_label,
    }
