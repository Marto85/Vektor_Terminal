"""Suite de calibración con casos históricos congelados (sin red):
1. MSFT FY2026 (hyperscaler CapEx ciclo IA)
2. META 2022 (compresión + CapEx seguido de recuperación)
3. AMZN 2021-22 (ciclo logístico + compresión)
4. MELI 2025-26 (compresión de margen intencional + alto crecimiento)
5. Entidad financiera (JPM-like: provisiones y ROE de ciclo)
6. Cíclica 10 años (XOM-like: margen en pico cíclico R12)
7. Empresa limpia (AAPL-like: sin falsos positivos materiales)
"""
import pytest

from app.services.anomaly_detector import detect_anomalies
from app.services.dcf_engine import run_dcf


def _make_getter(data: dict[str, dict[str, float]]):
    return lambda metric, year: float(data.get(year, {}).get(metric, 0.0))


def test_fixture_msft_hyperscaler_capex_cycle():
    years = ["2020", "2021", "2022", "2023", "2024", "2025", "2026"]
    data = {
        "2020": {"Ingresos Totales": 143000, "Beneficio Operativo": 53000, "Gastos de capital (CapEx)": 15400, "Depreciación y Amortización": 12700, "Efectivo de Operaciones (CFO)": 60600, "Flujo de caja libre (FCF)": 45200, "Beneficio Neto": 44200, "Beneficio antes de Impuestos": 53000, "Gasto por Impuesto a las Ganancias": 8750},
        "2021": {"Ingresos Totales": 168000, "Beneficio Operativo": 69900, "Gastos de capital (CapEx)": 20600, "Depreciación y Amortización": 11600, "Efectivo de Operaciones (CFO)": 76700, "Flujo de caja libre (FCF)": 56100, "Beneficio Neto": 61200, "Beneficio antes de Impuestos": 71100, "Gasto por Impuesto a las Ganancias": 9830},
        "2022": {"Ingresos Totales": 198200, "Beneficio Operativo": 83300, "Gastos de capital (CapEx)": 23800, "Depreciación y Amortización": 14400, "Efectivo de Operaciones (CFO)": 89000, "Flujo de caja libre (FCF)": 65200, "Beneficio Neto": 72700, "Beneficio antes de Impuestos": 83700, "Gasto por Impuesto a las Ganancias": 10970},
        "2023": {"Ingresos Totales": 211900, "Beneficio Operativo": 88500, "Gastos de capital (CapEx)": 28100, "Depreciación y Amortización": 13800, "Efectivo de Operaciones (CFO)": 87500, "Flujo de caja libre (FCF)": 59400, "Beneficio Neto": 72300, "Beneficio antes de Impuestos": 89300, "Gasto por Impuesto a las Ganancias": 16950},
        "2024": {"Ingresos Totales": 245100, "Beneficio Operativo": 109400, "Gastos de capital (CapEx)": 44400, "Depreciación y Amortización": 22200, "Efectivo de Operaciones (CFO)": 118500, "Flujo de caja libre (FCF)": 74100, "Beneficio Neto": 88100, "Beneficio antes de Impuestos": 107700, "Gasto por Impuesto a las Ganancias": 19650},
        "2025": {"Ingresos Totales": 272000, "Beneficio Operativo": 122000, "Gastos de capital (CapEx)": 68000, "Depreciación y Amortización": 29000, "Efectivo de Operaciones (CFO)": 130000, "Flujo de caja libre (FCF)": 62000, "Beneficio Neto": 96000, "Beneficio antes de Impuestos": 120000, "Gasto por Impuesto a las Ganancias": 22000},
        "2026": {"Ingresos Totales": 300000, "Beneficio Operativo": 135000, "Gastos de capital (CapEx)": 93000, "Depreciación y Amortización": 36000, "Efectivo de Operaciones (CFO)": 141000, "Flujo de caja libre (FCF)": 48000, "Beneficio Neto": 105000, "Beneficio antes de Impuestos": 133000, "Gasto por Impuesto a las Ganancias": 25000},
    }
    res = detect_anomalies(valid_years=years, get_m=_make_getter(data), shares_mm=7430.0)
    codes = {f["canonical_code"] for f in res["flags"]}
    assert "CAPEX_CICLO" in codes
    assert res["adjusted_fcf_mm"] > 90000.0
    dcf = run_dcf(
        {
            "current_price": 420.0,
            "shares_mm": 7430.0,
            "net_debt_mm": -20000.0,
            "revenue_base_mm": 300000.0,
            "recommended_rev_growth_pct": 12.0,
            "suggested_wacc_pct": 8.5,
            "ebit_margin_pct": res["ebit_margin_pct"],
            "tax_rate_pct": res["tax_rate_pct"],
            "da_sales_pct": 12.0,
            "capex_expansion_pct": res["capex_current_pct"],
            "nwc_pct_of_delta_rev": 0.02,
            "exit_multiple_default": 22.0,
        },
        adjustments=res["flags"],
    )
    assert dcf["normalized"]["intrinsic_price"] > dcf["reported"]["intrinsic_price"]


def test_fixture_cyclical_10y_peak_margin_r12():
    years = [str(y) for y in range(2016, 2026)]
    data = {
        y: {
            "Ingresos Totales": 250000.0,
            "Beneficio Operativo": 22500.0 if int(y) < 2025 else 50000.0,  # 9% ciclo vs 20% pico
            "Gastos de capital (CapEx)": 18000.0,
            "Depreciación y Amortización": 17000.0,
            "Efectivo de Operaciones (CFO)": 32000.0,
            "Flujo de caja libre (FCF)": 14000.0,
            "Beneficio Neto": 16000.0 if int(y) < 2025 else 38000.0,
            "Beneficio antes de Impuestos": 21000.0 if int(y) < 2025 else 48000.0,
            "Gasto por Impuesto a las Ganancias": 5000.0 if int(y) < 2025 else 10000.0,
        }
        for y in years
    }
    res = detect_anomalies(valid_years=years, get_m=_make_getter(data), sector="Energy", shares_mm=4000.0)
    assert any(f["canonical_code"] == "PICO_CICLICO" for f in res["flags"])
    assert res["normalized_ebit_margin_pct"] == pytest.approx(9.0, abs=0.5)


def test_fixture_clean_company_no_false_positives():
    years = ["2021", "2022", "2023", "2024", "2025"]
    data = {
        y: {
            "Ingresos Totales": 380000.0 + idx * 10000.0,
            "Beneficio Bruto": 170000.0 + idx * 4500.0,
            "Beneficio Operativo": 114000.0 + idx * 3000.0,
            "Gastos de capital (CapEx)": 11000.0,
            "Depreciación y Amortización": 11500.0,
            "Efectivo de Operaciones (CFO)": 110000.0,
            "Flujo de caja libre (FCF)": 99000.0,
            "Beneficio Neto": 95000.0,
            "Beneficio antes de Impuestos": 112000.0,
            "Gasto por Impuesto a las Ganancias": 17000.0,
            "Compensación basada en acciones": 10000.0,
            "Cambios en el capital de trabajo": 2000.0,
        }
        for idx, y in enumerate(years)
    }
    res = detect_anomalies(valid_years=years, get_m=_make_getter(data), shares_mm=15000.0)
    assert res["has_anomalies"] is False
    dcf = run_dcf(
        {
            "current_price": 220.0,
            "shares_mm": 15000.0,
            "net_debt_mm": 50000.0,
            "revenue_base_mm": 420000.0,
            "recommended_rev_growth_pct": 6.0,
            "suggested_wacc_pct": 8.5,
            "ebit_margin_pct": res["ebit_margin_pct"],
            "tax_rate_pct": res["tax_rate_pct"],
            "da_sales_pct": 3.0,
            "capex_expansion_pct": res["capex_current_pct"],
            "nwc_pct_of_delta_rev": 0.02,
            "exit_multiple_default": 22.0,
        },
        adjustments=res["flags"],
    )
    assert dcf["total_delta_per_share"] == 0.0
