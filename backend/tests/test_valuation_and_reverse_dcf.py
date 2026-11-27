import pytest
from app.services.valuation_service import (
    _detect_sector_profile,
    _compute_reverse_dcf,
    _audit_anomalies_and_adjustments,
)


def test_detect_sector_profile_routing():
    bank_profile = _detect_sector_profile({"sector": "Financial Services", "industry": "Banks - Diversified", "sic": "6021"})
    assert bank_profile["profile"] == "financial"

    reit_profile = _detect_sector_profile({"sector": "Real Estate", "industry": "REIT - Retail", "sic": "6798"})
    assert reit_profile["profile"] == "reit"

    tech_profile = _detect_sector_profile({"sector": "Technology", "industry": "Software - Infrastructure", "sic": "7372"})
    assert tech_profile["profile"] == "standard"


def test_reverse_dcf_corporate_consistency_with_forward_dcf():
    """
    Si el precio actual coincide exactamente con el valor intrínseco generado
    por un DCF 2 Etapas con g = 12%, el DCF Inverso debe despejar g_implícito = 12.0%.
    """
    rev0 = 10_000.0
    shares = 500.0
    net_debt = 2_000.0
    ebit_m = 0.25
    tax_r = 0.20
    da_p = 0.05
    capex1 = 0.08
    capex_t = 0.05
    wacc = 0.10
    exit_m = 20.0
    g_true = 0.12
    g_term = 0.03

    # Calculamos el precio directo para g_true = 12% a 5 años con el motor DCF unificado (fade años 4-5 + ΔNWC)
    nwc_pct = 0.02
    rv = rev0
    pv1 = 0.0
    for yr in range(1, 6):
        prev_rv = rv
        g_yr = g_true if yr <= 3 else g_true + ((g_term - g_true) * (yr - 3)) / 2.0
        rv *= 1.0 + g_yr
        delta_nwc = max(rv - prev_rv, 0.0) * nwc_pct
        fcf_y = rv * (ebit_m * (1.0 - tax_r) + da_p - capex1) - delta_nwc
        pv1 += fcf_y / ((1.0 + wacc) ** yr)

    rv_next = rv * (1.0 + g_term)
    delta_nwc_term = max(rv_next - rv, 0.0) * nwc_pct
    fcf_next = rv_next * (ebit_m * (1.0 - tax_r) + da_p - capex_t) - delta_nwc_term
    tv_gordon = fcf_next / (wacc - g_term)
    fcf_last_norm = rv * (ebit_m * (1.0 - tax_r) + da_p - capex_t)
    tv_mult = fcf_last_norm * exit_m
    tv_blend = 0.5 * (tv_gordon + tv_mult)
    exact_price = (pv1 + tv_blend / ((1.0 + wacc) ** 5) - net_debt) / shares

    dcf_inputs = {
        "current_price": round(exact_price, 4),
        "shares_mm": shares,
        "net_debt_mm": net_debt,
        "revenue_base_mm": rev0,
        "ebit_margin_pct": ebit_m * 100.0,
        "tax_rate_pct": tax_r * 100.0,
        "da_sales_pct": da_p * 100.0,
        "capex_expansion_pct": capex1 * 100.0,
        "capex_maintenance_pct": capex_t * 100.0,
        "suggested_wacc_pct": wacc * 100.0,
        "exit_multiple_default": exit_m,
        "margin_step_pct_yr": 0.0,
        "nwc_pct_of_delta_rev": nwc_pct,
    }

    res = _compute_reverse_dcf(
        is_financial=False,
        dcf_inputs=dcf_inputs,
        financial_inputs={},
        hist_avg_growth_pct=11.0,
        recommended_growth_pct=12.0,
    )

    assert res["mode"] == "standard"
    assert res["horizon_5y"]["solvable"] is True
    assert res["horizon_5y"]["implied_growth_pct"] == pytest.approx(12.0, abs=0.2)
    assert res["regime"] == "aligned"


def test_reverse_dcf_financial_bank_mode():
    fin_inputs = {
        "current_price": 45.0,
        "bvps": 25.0,
        "roe_pct": 16.0,
        "cost_of_equity_pct": 10.0,
        "payout_ratio_pct": 30.0,
    }
    res = _compute_reverse_dcf(
        is_financial=True,
        dcf_inputs={},
        financial_inputs=fin_inputs,
        hist_avg_growth_pct=10.0,
        recommended_growth_pct=11.0,
    )
    assert res["mode"] == "financial"
    assert res["horizon_5y"]["solvable"] is True
    assert res["horizon_5y"]["implied_roe_pct"] > 10.0
    assert res["horizon_5y"]["implied_growth_pct"] is not None


def test_audit_detects_capex_expansion_anomaly():
    years = ["2022", "2023", "2024"]
    data = {
        ("Ingresos Totales", "2022"): 1000.0,
        ("Ingresos Totales", "2023"): 1100.0,
        ("Ingresos Totales", "2024"): 1200.0,
        ("Beneficio Operativo", "2024"): 300.0,
        ("Depreciación y Amortización", "2024"): 60.0,
        ("Beneficio Neto", "2024"): 230.0,
        ("Beneficio antes de Impuestos", "2024"): 290.0,
        ("Gasto por Impuesto a las Ganancias", "2024"): 60.0,
        ("Efectivo de Operaciones (CFO)", "2024"): 320.0,
        ("Gastos de capital (CapEx)", "2022"): 50.0,   # 5%
        ("Gastos de capital (CapEx)", "2023"): 55.0,   # 5%
        ("Gastos de capital (CapEx)", "2024"): 240.0,  # 20% -> ciclo de expansión
        ("Flujo de caja libre (FCF)", "2024"): 80.0,
    }

    def get_m(m: str, y: str) -> float:
        return data.get((m, y), 0.0)

    audit = _audit_anomalies_and_adjustments(
        valid_years=years,
        get_m=get_m,
        current_mcap_mm=4000.0,
        current_ev_mm=3800.0,
        ltm_multiples={"pfcf": 50.0, "ev_fcf": 47.5, "pe": 17.4},
        is_financial=False,
    )

    assert audit["has_anomalies"] is True
    assert any(f["code"] == "CAPEX_EXPANSION" for f in audit["flags"])
    assert audit["adjusted_fcf_mm"] > 80.0


def test_country_risk_premium_for_emerging_markets():
    from app.services.valuation_service import _estimate_country_risk_premium_pct

    assert _estimate_country_risk_premium_pct("Brazil", "BRL") == 2.5
    assert _estimate_country_risk_premium_pct(None, "BRL") == 2.5
    assert _estimate_country_risk_premium_pct("Argentina", "ARS") == 11.5
    assert _estimate_country_risk_premium_pct("Uruguay", "USD") == 1.2
    assert _estimate_country_risk_premium_pct(None, "TWD") == 0.6
    assert _estimate_country_risk_premium_pct("United States", "USD") == 0.0


def test_build_summary_metrics_hides_ebitda_ratios_for_banks():
    from app.core.yf_client import _build_summary_metrics

    base_info = {
        "marketCap": 100_000_000_000,
        "totalDebt": 20_000_000_000,
        "totalCash": 10_000_000_000,
        "ebitda": 5_000_000_000,
        "totalRevenue": 25_000_000_000,
    }
    bank_metrics = _build_summary_metrics(
        info={**base_info, "sector": "Financial Services"},
        price=100.0,
        fx_rate=1.0,
    )
    assert bank_metrics["capital_structure"]["net_debt_to_ebitda"] is None
    assert bank_metrics["valuation"]["ev_to_ebitda_ltm"] is None
    assert bank_metrics["efficiency"]["gross_margin_pct"] is None

    tech_metrics = _build_summary_metrics(
        info={**base_info, "sector": "Technology"},
        price=100.0,
        fx_rate=1.0,
    )
    assert tech_metrics["capital_structure"]["net_debt_to_ebitda"] is not None
    assert tech_metrics["valuation"]["ev_to_ebitda_ltm"] is not None


def test_trajectory_scales_margin_step_and_computes_hist_median_ebit():
    from app.services.valuation_service import _analyze_trajectory_and_margins

    years = ["2022", "2023", "2024", "2025"]
    data = {
        ("Ingresos Totales", "2022"): 1000.0,
        ("Ingresos Totales", "2023"): 1150.0,
        ("Ingresos Totales", "2024"): 1300.0,
        ("Ingresos Totales", "2025"): 1500.0,
        ("Beneficio Bruto", "2022"): 500.0,
        ("Beneficio Bruto", "2023"): 575.0,
        ("Beneficio Bruto", "2024"): 650.0,
        ("Beneficio Bruto", "2025"): 750.0,
        ("Beneficio Operativo", "2022"): 200.0,
        ("Beneficio Operativo", "2023"): 230.0,
        ("Beneficio Operativo", "2024"): 260.0,
        ("Beneficio Operativo", "2025"): 75.0,
        ("Beneficio Neto", "2022"): 140.0,
        ("Beneficio Neto", "2023"): 160.0,
        ("Beneficio Neto", "2024"): 180.0,
        ("Beneficio Neto", "2025"): 50.0,
    }
    estimates = {
        "revenue_estimate": {"0y": {"growth": 0.15}, "+1y": {"growth": 0.20}},
        "earnings_estimate": {"0y": {"growth": 0.30}, "+1y": {"growth": 0.60}},
    }
    res = _analyze_trajectory_and_margins(
        valid_years=years,
        get_m=lambda m, y: data.get((m, y), 0.0),
        estimates_data=estimates,
    )
    assert res["margin_step_pct_yr"] == 2.5
    assert res["hist_med_ebit_margin_pct"] == 20.0


def test_looks_english_detects_short_headlines_and_spanish_text():
    from app.core.yf_client import _has_spanish_signals, _looks_english

    assert _looks_english("Vistra Stock Rises on Power Deal") is True
    assert _looks_english("Nu Holdings Beats Q3 Profit Estimates") is True
    assert _looks_english("Nu Holdings supera estimaciones del tercer trimestre") is False
    assert _has_spanish_signals("Vistra sube tras acuerdo energético en EE.UU.") is True


def test_audit_detects_reinvestment_margin_compression_and_quarterly_shift():
    from app.services.valuation_service import _audit_anomalies_and_adjustments

    years = ["2023", "2024", "2025", "2026"]
    data = {
        "Ingresos Totales": {"2023": 1000.0, "2024": 1300.0, "2025": 1700.0, "2026": 2200.0},
        "Beneficio Bruto": {"2023": 500.0, "2024": 650.0, "2025": 850.0, "2026": 1078.0},
        "Beneficio Operativo": {"2023": 160.0, "2024": 208.0, "2025": 255.0, "2026": 176.0},
        "Gastos por Intereses": {"2023": 10.0, "2024": 10.0, "2025": 10.0, "2026": 10.0},
        "Depreciación y Amortización": {"2023": 40.0, "2024": 52.0, "2025": 68.0, "2026": 88.0},
        "Beneficio Neto": {"2023": 115.0, "2024": 150.0, "2025": 185.0, "2026": 120.0},
        "Beneficio antes de Impuestos": {"2023": 150.0, "2024": 198.0, "2025": 245.0, "2026": 166.0},
        "Gasto por Impuesto a las Ganancias": {"2023": 35.0, "2024": 48.0, "2025": 60.0, "2026": 46.0},
        "Efectivo de Operaciones (CFO)": {"2023": 180.0, "2024": 220.0, "2025": 270.0, "2026": 210.0},
        "Gastos de capital (CapEx)": {"2023": 60.0, "2024": 78.0, "2025": 102.0, "2026": 132.0},
        "Flujo de caja libre (FCF)": {"2023": 120.0, "2024": 142.0, "2025": 168.0, "2026": 78.0},
        "Compensación basada en acciones": {"2023": 10.0, "2024": 12.0, "2025": 15.0, "2026": 18.0},
        "Cambios en el capital de trabajo": {"2023": 5.0, "2024": 6.0, "2025": 8.0, "2026": -10.0},
    }
    quarterly_rows = [
        {"Sección": "Cuenta de Resultados", "Métrica": "Ingresos Totales", "Q1 26": 500.0, "Q2 26": 540.0, "Q3 26": 570.0, "Q4 26": 590.0},
        {"Sección": "Cuenta de Resultados", "Métrica": "Beneficio Operativo", "Q1 26": 70.0, "Q2 26": 72.0, "Q3 26": 74.0, "Q4 26": 35.4},
    ]

    audit = _audit_anomalies_and_adjustments(
        valid_years=years,
        get_m=lambda m, y: data.get(m, {}).get(y, 0.0),
        current_mcap_mm=10000.0,
        current_ev_mm=10000.0,
        ltm_multiples={"ev_ebit": 56.8, "pe": 83.3, "pfcf": 128.2},
        is_financial=False,
        quarterly_rows=quarterly_rows,
        fx_rate=1.0,
    )
    codes = {f["code"] for f in audit["flags"]}
    assert "OPEX_SPIKE" in codes
    assert "MARGIN_COMPRESSION_REINVESTMENT" in codes
    assert "QUARTERLY_RUN_RATE_SHIFT" in codes
    assert audit["normalized_ebit_margin_pct"] > audit["ebit_margin_pct"]
    assert audit["normalized_ebit_mm"] > 176.0
    assert any(c["metric"] == "EV / EBIT (LTM)" for c in audit["comparisons"])


def test_build_ttm_series_and_v5_eps_separation():
    from app.services.financial_parser import build_ttm_series
    from app.services.valuation_service import _analyze_trajectory_and_margins

    q_rows = [
        {"Categoría": "Cuenta de Resultados", "Métrica": "Ingresos Totales", "2025-Q1": 100.0, "2025-Q2": 110.0, "2025-Q3": 120.0, "2025-Q4": 130.0, "2026-Q1": 140.0, "2026-Q2": 150.0},
        {"Categoría": "Flujo de Efectivo", "Métrica": "Flujo de caja libre (FCF)", "2025-Q1": 10.0, "2025-Q2": 12.0, "2025-Q3": 15.0, "2025-Q4": 18.0, "2026-Q1": 20.0, "2026-Q2": 22.0},
        {"Categoría": "Balance de Situación", "Métrica": "Deuda Total", "2025-Q1": 50.0, "2025-Q2": 50.0, "2025-Q3": 50.0, "2025-Q4": 50.0, "2026-Q1": 55.0, "2026-Q2": 60.0},
    ]
    ttm = build_ttm_series({}, fx_rate=1.0, quarterly_rows=q_rows)
    assert ttm["is_complete"] is True
    assert ttm["cutoff_label"] == "2026-Q2"
    assert ttm["ttm"]["Ingresos Totales"] == 540.0
    assert ttm["ttm"]["Flujo de caja libre (FCF)"] == 75.0
    assert ttm["runrate2"]["Ingresos Totales"] == 580.0
    assert ttm["latest_balance"]["Deuda Total"] == 60.0
    assert ttm["rev_yoy_2q_pct"] == 38.1

    # Hueco en trimestres -> fallback anual
    q_gap = [
        {"Categoría": "Cuenta de Resultados", "Métrica": "Ingresos Totales", "2025-Q1": 100.0, "2025-Q3": 120.0, "2025-Q4": 130.0, "2026-Q1": 140.0},
    ]
    ttm_gap = build_ttm_series({}, fx_rate=1.0, quarterly_rows=q_gap)
    assert ttm_gap["is_complete"] is False
    assert ttm_gap["quality_warning"] is not None

    # V5: stockTrend (50% EPS growth) no contamina el crecimiento de ventas (10%)
    traj = _analyze_trajectory_and_margins(
        valid_years=["2024", "2025"],
        get_m=lambda m, y: {"2024": 100.0, "2025": 110.0}.get(y, 0.0) if m == "Ingresos Totales" else 15.0,
        estimates_data={
            "revenue_estimate": {"0y": {"growth": 0.10}, "+1y": {"growth": 0.10}},
            "earnings_estimate": {},
            "growth_estimates": {"+5y": {"stockTrend": 0.50}},
            "consensus_summary": {},
        },
    )
    assert traj["recommended_rev_growth_pct"] == 10.0
