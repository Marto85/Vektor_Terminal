import pytest

from app.services.dcf_engine import check_ddm_special_dividend, run_dcf


BASE_INPUTS = {
    "current_price": 100.0,
    "shares_mm": 100.0,
    "net_debt_mm": 500.0,
    "revenue_base_mm": 5000.0,
    "recommended_rev_growth_pct": 12.0,
    "suggested_wacc_pct": 9.5,
    "ebit_margin_pct": 8.0,
    "tax_rate_pct": 24.0,
    "da_sales_pct": 4.0,
    "capex_expansion_pct": 18.0,
    "nwc_pct_of_delta_rev": 0.05,
    "exit_multiple_default": 18.0,
    "dividend_rate": 2.0,
    "payout_ratio_pct": 30.0,
}

SAMPLE_FLAGS = [
    {
        "rule_id": "R1",
        "code": "CAPEX_EXPANSION",
        "canonical_code": "CAPEX_CICLO",
        "title": "Ciclo extraordinario de inversión",
        "enabled": True,
        "adjustment": {"param": "capex_pct", "from": 18.0, "to": 7.0},
    },
    {
        "rule_id": "R2",
        "code": "MARGIN_COMPRESSION_REINVESTMENT",
        "canonical_code": "MARGEN_COMPRIMIDO",
        "title": "Compresión por reinversión",
        "enabled": True,
        "adjustment": {"param": "ebit_margin_pct", "from": 8.0, "to": 14.0},
    },
    {
        "rule_id": "R4",
        "code": "HIGH_SBC",
        "canonical_code": "SBC_ALTA",
        "title": "Alta SBC",
        "enabled": False,
        "adjustment": {"param": "sbc_deduction_mm", "from": 0.0, "to": 120.0},
    },
]


def test_dcf_engine_property_a_zero_active_adjustments():
    res = run_dcf(BASE_INPUTS, adjustments=SAMPLE_FLAGS, enabled_codes=set())
    assert res["bridge"] == []
    assert res["total_delta_per_share"] == 0.0
    assert res["normalized"]["intrinsic_price"] == res["reported"]["intrinsic_price"]


def test_dcf_engine_property_b_exact_additive_bridge():
    res = run_dcf(BASE_INPUTS, adjustments=SAMPLE_FLAGS, enabled_codes={"CAPEX_CICLO", "MARGEN_COMPRIMIDO", "SBC_ALTA"})
    rep_p = res["reported"]["intrinsic_price"]
    norm_p = res["normalized"]["intrinsic_price"]
    sum_deltas = round(sum(b["delta_per_share"] for b in res["bridge"]), 2)
    assert rep_p + sum_deltas + res["interaction_residual_per_share"] == pytest.approx(norm_p, abs=0.02)
    # Orden canónico fijo: capex -> margin -> sbc
    assert [b["group"] for b in res["bridge"]] == ["capex", "margin", "sbc"]


def test_dcf_engine_property_c_and_d_monotonicity():
    res_capex = run_dcf(BASE_INPUTS, adjustments=[SAMPLE_FLAGS[0]], enabled_codes={"CAPEX_CICLO"})
    assert res_capex["normalized"]["intrinsic_price"] > res_capex["reported"]["intrinsic_price"]

    res_margin = run_dcf(BASE_INPUTS, adjustments=[SAMPLE_FLAGS[1]], enabled_codes={"MARGEN_COMPRIMIDO"})
    assert res_margin["normalized"]["intrinsic_price"] > res_margin["reported"]["intrinsic_price"]


def test_dcf_engine_property_e_order_invariance():
    reversed_flags = list(reversed(SAMPLE_FLAGS))
    r1 = run_dcf(BASE_INPUTS, adjustments=SAMPLE_FLAGS, enabled_codes={"CAPEX_CICLO", "MARGEN_COMPRIMIDO"})
    r2 = run_dcf(BASE_INPUTS, adjustments=reversed_flags, enabled_codes={"MARGEN_COMPRIMIDO", "CAPEX_CICLO"})
    assert r1["normalized"]["intrinsic_price"] == r2["normalized"]["intrinsic_price"]
    assert [b["code"] for b in r1["bridge"]] == [b["code"] for b in r2["bridge"]]


def test_ddm_special_dividend_alert():
    alert = check_ddm_special_dividend(dividend_rate=15.0, payout_ratio_pct=140.0, current_price=100.0)
    assert alert is not None
    assert alert["code"] == "DDM_SPECIAL_DIVIDEND"
    assert check_ddm_special_dividend(dividend_rate=2.0, payout_ratio_pct=30.0, current_price=100.0) is None
