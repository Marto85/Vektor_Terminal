import pytest

from app.services.anomaly_detector import compute_clean_baseline, detect_anomalies


def test_two_pass_clean_baseline_excludes_anomalous_years():
    # 5 años normales (~6%) + 2 años anómalos (22%, 25%) -> 5 años limpios >= 4 -> confianza alta
    series = [
        ("2019", 6.0),
        ("2020", 6.5),
        ("2021", 5.8),
        ("2022", 6.2),
        ("2023", 6.1),
        ("2024", 22.0),
        ("2025", 25.0),
    ]
    res = compute_clean_baseline(
        series,
        trigger_fn=lambda v, med: med > 0 and v >= med * 1.4 and (v - med) >= 4.0,
        min_clean=4,
        max_years=8,
    )
    assert res["confidence"] == "high"
    assert res["auto_adjust"] is True
    assert res["excluded_years"] == ["2024", "2025"]
    assert res["baseline"] == pytest.approx(6.1, abs=0.01)


def test_two_pass_clean_baseline_low_confidence_when_under_4_clean_years():
    series = [("2022", 6.0), ("2023", 6.2), ("2024", 22.0)]
    res = compute_clean_baseline(
        series,
        trigger_fn=lambda v, med: med > 0 and v >= med * 1.4 and (v - med) >= 4.0,
        min_clean=4,
    )
    assert res["confidence"] == "low"
    assert res["auto_adjust"] is False


def test_meli_like_margin_compression_vs_high_growth_capex_guard():
    # Caso tipo MELI: ventas +35%, margen EBIT cae 14% -> 7.5%, CapEx/D&A = 1.7x (no debe disparar R1 falso positivo)
    years = ["2020", "2021", "2022", "2023", "2024", "2025"]
    data = {
        "2020": {"Ingresos Totales": 4000, "Beneficio Bruto": 1900, "Beneficio Operativo": 520, "Gastos de Venta y Marketing": 450, "Gastos de capital (CapEx)": 250, "Depreciación y Amortización": 160, "Efectivo de Operaciones (CFO)": 600, "Flujo de caja libre (FCF)": 350, "Beneficio Neto": 320, "Beneficio antes de Impuestos": 450, "Gasto por Impuesto a las Ganancias": 110},
        "2021": {"Ingresos Totales": 7000, "Beneficio Bruto": 3350, "Beneficio Operativo": 950, "Gastos de Venta y Marketing": 780, "Gastos de capital (CapEx)": 420, "Depreciación y Amortización": 260, "Efectivo de Operaciones (CFO)": 1000, "Flujo de caja libre (FCF)": 580, "Beneficio Neto": 600, "Beneficio antes de Impuestos": 850, "Gasto por Impuesto a las Ganancias": 210},
        "2022": {"Ingresos Totales": 10500, "Beneficio Bruto": 5100, "Beneficio Operativo": 1470, "Gastos de Venta y Marketing": 1150, "Gastos de capital (CapEx)": 600, "Depreciación y Amortización": 380, "Efectivo de Operaciones (CFO)": 1600, "Flujo de caja libre (FCF)": 1000, "Beneficio Neto": 950, "Beneficio antes de Impuestos": 1350, "Gasto por Impuesto a las Ganancias": 330},
        "2023": {"Ingresos Totales": 14500, "Beneficio Bruto": 7100, "Beneficio Operativo": 2030, "Gastos de Venta y Marketing": 1600, "Gastos de capital (CapEx)": 820, "Depreciación y Amortización": 520, "Efectivo de Operaciones (CFO)": 2300, "Flujo de caja libre (FCF)": 1480, "Beneficio Neto": 1400, "Beneficio antes de Impuestos": 1900, "Gasto por Impuesto a las Ganancias": 470},
        "2024": {"Ingresos Totales": 20000, "Beneficio Bruto": 9800, "Beneficio Operativo": 2800, "Gastos de Venta y Marketing": 2200, "Gastos de capital (CapEx)": 1100, "Depreciación y Amortización": 700, "Efectivo de Operaciones (CFO)": 3100, "Flujo de caja libre (FCF)": 2000, "Beneficio Neto": 1950, "Beneficio antes de Impuestos": 2650, "Gasto por Impuesto a las Ganancias": 650},
        "2025": {"Ingresos Totales": 27000, "Beneficio Bruto": 13230, "Beneficio Operativo": 2025, "Gastos de Venta y Marketing": 5400, "Gastos de capital (CapEx)": 1530, "Depreciación y Amortización": 900, "Efectivo de Operaciones (CFO)": 2400, "Flujo de caja libre (FCF)": 870, "Beneficio Neto": 1350, "Beneficio antes de Impuestos": 1850, "Gasto por Impuesto a las Ganancias": 460},
    }
    res = detect_anomalies(
        valid_years=years,
        get_m=lambda m, y: float(data.get(y, {}).get(m, 0.0)),
        shares_mm=50.0,
        dcf_growth_pct=15.0,
    )
    canonical_codes = {f["canonical_code"] for f in res["flags"]}
    assert "MARGEN_COMPRIMIDO" in canonical_codes
    assert "CAPEX_CICLO" not in canonical_codes
    assert res["margin_classification"] == "investment"
    assert res["normalized_ebit_margin_pct"] == pytest.approx(14.0, abs=0.5)
    assert "BRECHA_CRECIMIENTO" in canonical_codes


def test_financial_entity_triggers_r15_and_currency_r11():
    years = ["2021", "2022", "2023", "2024", "2025"]
    data = {
        "2021": {"Ingresos Totales": 1000, "Provisiones para Pérdidas Crediticias": 80, "Beneficio antes de Impuestos": 300},
        "2022": {"Ingresos Totales": 1100, "Provisiones para Pérdidas Crediticias": 90, "Beneficio antes de Impuestos": 320},
        "2023": {"Ingresos Totales": 1200, "Provisiones para Pérdidas Crediticias": 95, "Beneficio antes de Impuestos": 340},
        "2024": {"Ingresos Totales": 1300, "Provisiones para Pérdidas Crediticias": 100, "Beneficio antes de Impuestos": 360},
        "2025": {"Ingresos Totales": 1400, "Provisiones para Pérdidas Crediticias": 320, "Beneficio antes de Impuestos": 200},
    }
    res = detect_anomalies(
        valid_years=years,
        get_m=lambda m, y: float(data.get(y, {}).get(m, 0.0)),
        is_financial=True,
        reporting_currency="ARS",
        fx_rate=0.001,
        hist_roe_pcts=[18.0, 19.0, 20.0, 18.5],
        current_roe_pct=11.0,
    )
    canonical_codes = {f["canonical_code"] for f in res["flags"]}
    assert "FINANCIERA" in canonical_codes
    assert "MONEDA_INFLACION" in canonical_codes
