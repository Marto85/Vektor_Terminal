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

    # Calculamos el precio directo para g_true = 12% a 5 años
    rv = rev0
    pv1 = 0.0
    for yr in range(1, 6):
        rv *= 1.0 + g_true
        fcf_y = rv * (ebit_m * (1.0 - tax_r) + da_p - capex1)
        pv1 += fcf_y / ((1.0 + wacc) ** yr)

    fcf_next = rv * (1.0 + g_term) * (ebit_m * (1.0 - tax_r) + da_p - capex_t)
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
