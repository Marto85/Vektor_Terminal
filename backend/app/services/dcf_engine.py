"""Motor único de Valuación DCF Dual (Reportado Frío vs Escenario Normalizado 'Bis') y Puente Aditivo.

Reglas de diseño:
- Un solo motor en backend consumido por ValuationModelsTab, ValuationTab, simulador y exportaciones.
- Horizonte institucional de 10 años para compounders (crecimiento >= 10%) y 5 años para maduras,
  con convergencia gradual (Etapa 1: años 1-5, Etapa 2: años 6-10 hacia crecimiento terminal).
- Mismos supuestos de crecimiento, WACC, múltiplo terminal y horizonte para Reportado y Normalizado;
  solo cambian los parámetros explícitamente ajustados por las reglas activas.
- Devuelve proyecciones, Gordon, Múltiplo de Salida y Matriz de Sensibilidad calculadas con la
  misma fórmula exacta para garantizar consistencia total en pantalla.
"""
from __future__ import annotations

from typing import Any


BRIDGE_ORDER = (
    ("capex", {"CAPEX_CICLO", "CAPEX_EXPANSION"}),
    ("margin", {"MARGEN_COMPRIMIDO", "MARGIN_COMPRESSION_REINVESTMENT", "PICO_CICLICO"}),
    ("nwc", {"CAPITAL_TRABAJO", "WORKING_CAPITAL_SWING"}),
    ("non_recurring_and_tax", {"NO_RECURRENTE", "NON_OPERATING_SHOCK", "TASA_FISCAL"}),
    ("sbc", {"SBC_ALTA", "HIGH_SBC"}),
)


def _group_for_flag(flag: dict[str, Any]) -> str:
    codes = {str(flag.get("canonical_code") or ""), str(flag.get("code") or "")}
    for group_name, group_codes in BRIDGE_ORDER:
        if codes & group_codes:
            return group_name
    return "other"


def _evaluate_dcf_price(params: dict[str, Any], include_details: bool = False) -> dict[str, Any]:
    """Evalúa DCF explícito (5 o 10 años, blend Gordon + Múltiplo de Salida) con parámetros explícitos."""
    shares = float(params.get("shares_mm") or 0.0)
    rev0 = float(params.get("revenue_base_mm") or 0.0)
    net_debt = float(params.get("net_debt_mm") or 0.0)
    cur_price = float(params.get("current_price") or 0.0)
    if shares <= 0 or rev0 <= 0:
        return {
            "solvable": False,
            "intrinsic_price": None,
            "upside_pct": None,
            "price_gordon": None,
            "price_mult": None,
            "steady_fcf_terminal_mm": 0.0,
            "pv_fcf_mm": 0.0,
            "pv_terminal_mm": 0.0,
            "fcf_year1_mm": 0.0,
            "fcf_year5_mm": 0.0,
            "horizon_years": 5,
            "projections": [],
        }

    g1 = float(params.get("rev_growth_pct") or 6.0) / 100.0
    g_term = min(max(float(params.get("terminal_growth_pct") or 3.0) / 100.0, 0.01), 0.045)
    wacc = max(float(params.get("wacc_pct") or 9.0) / 100.0, g_term + 0.015)
    ebit_m0 = float(params.get("ebit_margin_pct") or 15.0) / 100.0
    target_m = float(params.get("target_ebit_margin_pct") if params.get("target_ebit_margin_pct") is not None else ebit_m0 * 100.0) / 100.0
    tax_r = min(max(float(params.get("tax_rate_pct") or 21.0) / 100.0, 0.05), 0.55)
    da_p = max(float(params.get("da_sales_pct") or 4.0) / 100.0, 0.0)
    capex1 = max(float(params.get("capex_stage1_pct") or 10.0) / 100.0, 0.0)
    capex_t = max(float(params.get("capex_terminal_pct") if params.get("capex_terminal_pct") is not None else capex1 * 100.0) / 100.0, 0.0)
    nwc_pct = max(float(params.get("nwc_pct_of_delta_rev") or 0.05), 0.0)
    nwc_extra_mm = float(params.get("nwc_extra_mm") or 0.0)
    sbc_ded_mm = float(params.get("sbc_deduction_mm") or 0.0)
    non_rec_adj_mm = float(params.get("non_recurring_adj_mm") or 0.0)
    extra_adj_mm = float(params.get("extra_adj_mm") or 0.0)
    exit_mult = min(max(float(params.get("exit_multiple") or 18.0), 6.0), 40.0)

    horizon = int(params.get("horizon_years") or (10 if g1 >= 0.10 else 5))
    if horizon not in (5, 10):
        horizon = 10 if g1 >= 0.10 else 5

    margin_horizon = min(horizon, 5)
    margin_step = (target_m - ebit_m0) / float(margin_horizon)
    rv = rev0
    pv_fcf = 0.0
    fcf_y1 = 0.0
    fcf_y5 = 0.0
    last_margin = ebit_m0
    projections: list[dict[str, Any]] = []

    g_mid = 0.5 * (g1 + g_term)
    for yr in range(1, horizon + 1):
        prev_rv = rv
        if horizon == 10:
            if yr <= 3:
                g_yr = g1
            elif yr <= 5:
                g_yr = g1 + ((g_mid - g1) * (yr - 3)) / 2.0
            else:
                g_yr = g_mid + ((g_term - g_mid) * (yr - 5)) / 5.0
            # En horizonte 10Y: Etapa 1 (años 1-5) mantiene capex1, Etapa 2 (6-10) converge hacia capex_t
            if yr <= 5:
                cx_yr = capex1
            else:
                cx_yr = capex1 + ((capex_t - capex1) * (yr - 5)) / 5.0
        else:
            g_yr = g1 if yr <= 3 else g1 + ((g_term - g1) * (yr - 3)) / 2.0
            cx_yr = capex1 + ((capex_t - capex1) * (yr - 1)) / 4.0

        rv *= 1.0 + g_yr
        delta_nwc = max(rv - prev_rv, 0.0) * nwc_pct
        m_yr = min(max(ebit_m0 + margin_step * min(yr, margin_horizon), -0.25), 0.65)
        last_margin = m_yr
        fcf_y = rv * (m_yr * (1.0 - tax_r) + da_p - cx_yr) - delta_nwc - sbc_ded_mm + extra_adj_mm
        if yr == 1:
            fcf_y += nwc_extra_mm + non_rec_adj_mm
            fcf_y1 = fcf_y
        if yr == 5:
            fcf_y5 = fcf_y
        pv_y = fcf_y / ((1.0 + wacc) ** yr)
        pv_fcf += pv_y
        if include_details:
            projections.append({
                "year": f"Año +{yr}",
                "rev": round(rv, 1),
                "growthPct": round(g_yr * 100.0, 1),
                "ebitMarginPct": round(m_yr * 100.0, 1),
                "capexPct": round(cx_yr * 100.0, 1),
                "fcf": round(fcf_y, 1),
                "pv": round(pv_y, 1),
            })

    rv_next = rv * (1.0 + g_term)
    delta_nwc_term = max(rv_next - rv, 0.0) * nwc_pct
    fcf_next = rv_next * (last_margin * (1.0 - tax_r) + da_p - capex_t) - delta_nwc_term - sbc_ded_mm + extra_adj_mm
    tv_gordon = fcf_next / (wacc - g_term)
    fcf_last_norm = rv * (last_margin * (1.0 - tax_r) + da_p - capex_t) - sbc_ded_mm + extra_adj_mm
    tv_mult = fcf_last_norm * exit_mult

    price_gordon = round((pv_fcf + tv_gordon / ((1.0 + wacc) ** horizon) - net_debt) / shares, 2)
    price_mult = round((pv_fcf + tv_mult / ((1.0 + wacc) ** horizon) - net_debt) / shares, 2)

    tv_blend = 0.5 * (tv_gordon + tv_mult)
    pv_tv = tv_blend / ((1.0 + wacc) ** horizon)

    eq_val = pv_fcf + pv_tv - net_debt
    intrinsic = round(eq_val / shares, 2)
    upside = round(((intrinsic / cur_price) - 1.0) * 100.0, 2) if cur_price > 0 else None
    return {
        "solvable": True,
        "intrinsic_price": intrinsic,
        "upside_pct": upside,
        "price_gordon": price_gordon,
        "price_mult": price_mult,
        "steady_fcf_terminal_mm": round(fcf_next, 1),
        "equity_value_mm": round(eq_val, 2),
        "pv_fcf_mm": round(pv_fcf, 2),
        "pv_terminal_mm": round(pv_tv, 2),
        "fcf_year1_mm": round(fcf_y1, 2),
        "fcf_year5_mm": round(fcf_y5, 2),
        "ebit_margin_start_pct": round(ebit_m0 * 100.0, 2),
        "ebit_margin_end_pct": round(last_margin * 100.0, 2),
        "capex_stage1_pct": round(capex1 * 100.0, 2),
        "capex_terminal_pct": round(capex_t * 100.0, 2),
        "tax_rate_pct": round(tax_r * 100.0, 2),
        "horizon_years": horizon,
        "projections": projections if include_details else [],
    }


def _build_sensitivity_matrix(params: dict[str, Any]) -> tuple[list[float], list[dict[str, Any]]]:
    """Construye la matriz WACC x g usando exactamente la misma fórmula de _evaluate_dcf_price."""
    g_term = min(max(float(params.get("terminal_growth_pct") or 3.0), 1.0), 4.5)
    wacc = max(float(params.get("wacc_pct") or 9.0), g_term + 1.5)
    w_steps = [
        round(max(wacc - 1.0, g_term + 0.5), 2),
        round(max(wacc - 0.5, g_term + 0.5), 2),
        round(wacc, 2),
        round(wacc + 0.5, 2),
        round(wacc + 1.0, 2),
    ]
    g_steps = [
        round(max(g_term - 1.0, 0.5), 2),
        round(max(g_term - 0.5, 0.5), 2),
        round(g_term, 2),
        round(g_term + 0.5, 2),
        round(g_term + 1.0, 2),
    ]
    matrix = []
    for w_val in w_steps:
        cells = []
        for g_val in g_steps:
            if w_val <= g_val + 0.25:
                cells.append(None)
                continue
            cell_params = {**params, "wacc_pct": w_val, "terminal_growth_pct": g_val}
            cells.append(_evaluate_dcf_price(cell_params, include_details=False).get("intrinsic_price"))
        matrix.append({"waccPct": w_val, "cells": cells})
    return g_steps, matrix


def _apply_flag_to_params(params: dict[str, Any], flag: dict[str, Any]) -> dict[str, Any]:
    out = dict(params)
    adj = flag.get("adjustment") or {}
    param_name = adj.get("param")
    if not param_name:
        return out

    if param_name == "capex_pct" and adj.get("to") is not None:
        to_val = float(adj["to"])
        out["capex_stage1_pct"] = to_val
        out["capex_terminal_pct"] = to_val
    elif param_name == "ebit_margin_pct" and adj.get("to") is not None:
        out["target_ebit_margin_pct"] = float(adj["to"])
    elif param_name == "tax_rate_pct" and adj.get("to") is not None:
        out["tax_rate_pct"] = float(adj["to"])
    elif param_name == "sbc_deduction_mm" and adj.get("to") is not None:
        out["sbc_deduction_mm"] = float(adj["to"])
    elif param_name == "nwc_normalization" and adj.get("from") is not None:
        out["nwc_extra_mm"] = out.get("nwc_extra_mm", 0.0) - float(adj["from"])
    elif param_name == "non_recurring_net_mm" and adj.get("from") is not None:
        out["non_recurring_adj_mm"] = out.get("non_recurring_adj_mm", 0.0) - float(adj["from"])
    return out


def check_ddm_special_dividend(
    dividend_rate: float | None,
    payout_ratio_pct: float | None,
    current_price: float | None,
) -> dict[str, Any] | None:
    """Detecta si el dividendo usado en DDM incluye un dividendo extraordinario o payout insostenible."""
    div = float(dividend_rate or 0.0)
    payout = float(payout_ratio_pct or 0.0)
    price = float(current_price or 0.0)
    div_yield_pct = (div / price * 100.0) if (div > 0 and price > 0) else 0.0
    if payout > 95.0 or div_yield_pct > 10.0:
        return {
            "code": "DDM_SPECIAL_DIVIDEND",
            "severity": "warning",
            "title": "Posible dividendo extraordinario o payout insostenible en DDM",
            "detail": (
                f"El payout ({payout:.1f}%) o rendimiento por dividendo ({div_yield_pct:.1f}%) sugiere un pago puntual. "
                f"Verificar dividendo recurrente antes de extrapolar el DDM."
            ),
        }
    return None


def run_dcf(
    inputs: dict[str, Any],
    adjustments: list[dict[str, Any]] | None = None,
    enabled_codes: set[str] | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ejecuta el motor DCF dual (reportado frío vs normalizado 'bis') y construye el puente acumulativo."""
    overrides = overrides or {}
    capex_reported = float(overrides.get("capex_stage1_pct", inputs.get("capex_expansion_pct", 10.0)))
    da_pct = float(inputs.get("da_sales_pct", 4.0))
    # En realidad fría, Stage 1 respeta el CapEx reportado, pero en perpetuidad converge a un piso
    # operativo razonable si el CapEx actual es extraordinario (evita perpetuar 43% de CapEx con g=3%).
    cold_capex_term = float(
        overrides.get(
            "capex_terminal_pct",
            min(capex_reported, max(da_pct * 1.15, capex_reported * 0.55)),
        )
    )
    reported_ebit_m = float(overrides.get("ebit_margin_pct", inputs.get("ebit_margin_pct", 15.0)))
    reported_target_m = float(overrides.get("target_ebit_margin_pct", reported_ebit_m))

    reported_params = {
        "current_price": inputs.get("current_price"),
        "shares_mm": inputs.get("shares_mm"),
        "net_debt_mm": inputs.get("net_debt_mm"),
        "revenue_base_mm": inputs.get("revenue_base_mm"),
        "rev_growth_pct": overrides.get("rev_growth_pct", inputs.get("recommended_rev_growth_pct", 6.0)),
        "terminal_growth_pct": overrides.get("terminal_growth_pct", 3.0),
        "wacc_pct": overrides.get("wacc_pct", inputs.get("suggested_wacc_pct", 9.0)),
        "ebit_margin_pct": reported_ebit_m,
        "target_ebit_margin_pct": reported_target_m,
        "tax_rate_pct": inputs.get("tax_rate_pct", 21.0),
        "da_sales_pct": da_pct,
        "capex_stage1_pct": capex_reported,
        "capex_terminal_pct": cold_capex_term,
        "nwc_pct_of_delta_rev": inputs.get("nwc_pct_of_delta_rev", 0.05),
        "exit_multiple": overrides.get("exit_multiple", inputs.get("exit_multiple_default", 18.0)),
        "extra_adj_mm": overrides.get("extra_adj_mm", 0.0),
        "horizon_years": overrides.get("horizon_years"),
        "nwc_extra_mm": 0.0,
        "sbc_deduction_mm": 0.0,
        "non_recurring_adj_mm": 0.0,
    }

    reported_res = _evaluate_dcf_price(reported_params, include_details=True)

    flags = [f for f in (adjustments or []) if isinstance(f, dict) and f.get("adjustment")]
    active_flags: list[dict[str, Any]] = []
    for f in flags:
        if enabled_codes is not None:
            is_on = (f.get("canonical_code") in enabled_codes) or (f.get("code") in enabled_codes)
        else:
            is_on = bool(f.get("enabled", True))
        if is_on:
            active_flags.append(f)

    group_rank = {name: idx for idx, (name, _) in enumerate(BRIDGE_ORDER)}
    active_flags.sort(key=lambda fl: group_rank.get(_group_for_flag(fl), 99))

    bridge: list[dict[str, Any]] = []
    curr_params = dict(reported_params)
    prev_price = reported_res.get("intrinsic_price")

    for f in active_flags:
        next_params = _apply_flag_to_params(curr_params, f)
        next_res = _evaluate_dcf_price(next_params, include_details=False)
        next_price = next_res.get("intrinsic_price")
        delta = (
            round(next_price - prev_price, 2)
            if (next_price is not None and prev_price is not None)
            else 0.0
        )
        adj = f.get("adjustment") or {}
        bridge.append({
            "rule_id": f.get("rule_id"),
            "code": f.get("canonical_code") or f.get("code"),
            "legacy_code": f.get("code"),
            "group": _group_for_flag(f),
            "title": f.get("title"),
            "param": adj.get("param"),
            "from": adj.get("from"),
            "to": adj.get("to"),
            "delta_per_share": delta,
            "price_after": next_price,
        })
        curr_params = next_params
        prev_price = next_price

    normalized_res = _evaluate_dcf_price(curr_params, include_details=True) if active_flags else dict(reported_res)
    g_steps, sens_matrix = _build_sensitivity_matrix(curr_params)

    rep_p = reported_res.get("intrinsic_price")
    norm_p = normalized_res.get("intrinsic_price")
    total_delta = round(norm_p - rep_p, 2) if (rep_p is not None and norm_p is not None) else 0.0
    sum_bridge = round(sum(b["delta_per_share"] for b in bridge), 2)
    interaction_residual = round(total_delta - sum_bridge, 2)

    ddm_alert = check_ddm_special_dividend(
        inputs.get("dividend_rate"),
        inputs.get("payout_ratio_pct"),
        inputs.get("current_price"),
    )

    return {
        "reported": reported_res,
        "normalized": normalized_res,
        "bridge": bridge,
        "g_steps_pct": g_steps,
        "sensitivity_matrix": sens_matrix,
        "total_delta_per_share": total_delta,
        "interaction_residual_per_share": interaction_residual,
        "active_codes": [f.get("canonical_code") or f.get("code") for f in active_flags],
        "ddm_alert": ddm_alert,
    }
