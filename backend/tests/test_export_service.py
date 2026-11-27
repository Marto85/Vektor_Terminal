import io
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.main import app
from app.services.export_service import build_company_workbook_bytes, build_company_pdf_bytes


def _sample_export_inputs():
    profile = {
        "name": "Microsoft Corporation",
        "price": 498.30,
        "description": "Microsoft desarrolla software, servicios en la nube e inteligencia artificial.",
        "info": {
            "sector": "Technology",
            "industry": "Software - Infrastructure",
            "country": "United States",
            "exchange": "NMS",
            "totalDebt": 60000000000,
            "totalCash": 80000000000,
            "totalRevenue": 245122000000,
            "beta": 0.92,
            "targetMeanPrice": 535.0,
        },
        "fx_rate": 1.0,
        "summary_metrics": {
            "market_data": {"beta_5y": 0.92},
            "capital_structure": {
                "market_cap_mm": 3705000.0,
                "enterprise_value_mm": 3685000.0,
                "net_debt_mm": -20000.0,
                "net_debt_to_ebitda": -0.15,
            },
            "efficiency": {
                "gross_margin_pct": 69.8,
                "ebit_margin_pct": 44.6,
                "roa_pct": 19.2,
                "roe_pct": 35.4,
                "roic_pct": 28.9,
                "net_margin_pct": 36.1,
            },
            "growth_cashflow": {
                "revenue_growth_yoy_pct": 15.7,
                "ocf_ltm_mm": 118548.0,
                "fcf_ltm_mm": 74071.0,
                "total_cash_mm": 80000.0,
            },
            "valuation": {
                "target_price": 535.0,
                "pe_ltm": 26.01,
                "pe_ntm": 23.8,
                "ev_to_ebitda_ltm": 21.4,
                "ev_to_sales_ltm": 12.8,
                "pb_ltm": 11.9,
                "p_to_fcf_ltm": 42.1,
                "dividend_yield_pct": 0.72,
            },
        },
    }
    statements = [
        {"Categoría": "Cuenta de Resultados", "Métrica": "Ingresos Totales", "2023": 211915.0, "2024": 245122.0},
        {"Categoría": "Cuenta de Resultados", "Métrica": "Beneficio Bruto", "2023": 146052.0, "2024": 171008.0},
        {"Categoría": "Cuenta de Resultados", "Métrica": "Beneficio Operativo", "2023": 88523.0, "2024": 109433.0},
        {"Categoría": "Cuenta de Resultados", "Métrica": "Beneficio Neto", "2023": 72361.0, "2024": 88136.0},
        {"Categoría": "Balance de Situación", "Métrica": "Total activo", "2023": 411976.0, "2024": 512163.0},
        {"Categoría": "Balance de Situación", "Métrica": "Patrimonio neto", "2023": 206223.0, "2024": 268477.0},
        {"Categoría": "Estado de Flujo de Efectivo", "Métrica": "Efectivo de Operaciones (CFO)", "2023": 87582.0, "2024": 118548.0},
        {"Categoría": "Estado de Flujo de Efectivo", "Métrica": "Gastos de capital (CapEx)", "2023": -28107.0, "2024": -44477.0},
        {"Categoría": "Estado de Flujo de Efectivo", "Métrica": "Flujo de caja libre (FCF)", "2023": 59475.0, "2024": 74071.0},
        {"Categoría": "Ratios", "Métrica": "Margen de beneficio operativo (EBIT) %", "is_pct": True, "2023": 41.77, "2024": 44.64},
    ]
    health = {
        "piotroski": {"score": 8, "zone": "Fortaleza Financiera Alta"},
        "altman": {
            "z_original": {"score": 8.45, "zone": "Zona Segura (> 2,99)"},
            "z_double_prime": {"score": 9.12, "zone": "Zona Segura (> 2,60)"},
        },
    }
    valuation = {
        "years": ["2023", "2024"],
        "sector_routing": {"profile": "standard", "primary_model": "DCF en 2 Etapas"},
        "rows": [
            {"section": "Trailing Multiples (Equity)", "metric": "Precio / Beneficio (P/E)", "suffix": "x", "ltm": 26.01, "avg_5y": 31.2, "med_5y": 30.8, "2023": 32.1, "2024": 29.5},
            {"section": "Trailing Multiples (EV)", "metric": "EV / EBITDA (LTM)", "suffix": "x", "ltm": 21.4, "avg_5y": 23.1, "med_5y": 22.8, "2023": 23.4, "2024": 22.1},
        ],
        "dcf_inputs": {
            "revenue_base_mm": 245122.0,
            "fcf_reported_mm": 74071.0,
            "fcf_adjusted_mm": 82000.0,
            "recommended_rev_growth_pct": 14.5,
            "ebit_margin_pct": 44.6,
            "suggested_wacc_pct": 8.4,
            "exit_multiple_default": 22.0,
        },
        "reverse_dcf": {
            "horizon_5y": {"implied_growth_pct": 13.8},
            "horizon_10y": {"implied_growth_pct": 11.2},
            "verdict": "Expectativas razonables: el precio descuenta 13.8% de crecimiento anual a 5 años.",
        },
    }
    ownership = {
        "major_holders": {
            "institutions_pct": 76.92,
            "insiders_pct": 0.12,
            "public_other_pct": 22.96,
            "institutions_count": 7250,
        },
        "institutional_holders": [
            {
                "holder": "Blackrock Inc.",
                "date_reported": "2026-09-30",
                "shares": 612000000,
                "pct_out": 8.18,
                "value_mm": 305077.4,
                "pct_change": 0.35,
            }
        ],
        "insider_summary": {"buy_count": 1, "sell_count": 12},
        "insider_transactions": [
            {
                "date": "2026-11-01",
                "insider": "DIRECTIVO EJEMPLO",
                "position": "Director",
                "transaction": "Sale",
                "shares": 1000,
                "value_usd": 498300,
            }
        ],
    }
    return profile, statements, health, valuation, ownership


def test_build_company_workbook_bytes_generates_seven_populated_sheets():
    profile, statements, health, valuation, ownership = _sample_export_inputs()
    raw_xlsx = build_company_workbook_bytes(
        ticker="MSFT",
        period="annual",
        profile=profile,
        market=profile,
        statements=statements,
        valuation=valuation,
        ownership=ownership,
        health=health,
    )

    wb = load_workbook(io.BytesIO(raw_xlsx))
    assert wb.sheetnames == [
        "Resumen & Múltiplos",
        "Resultados",
        "Balance",
        "Flujo de Efectivo",
        "Ratios",
        "Valoración",
        "Reportado vs normalizado",
        "Propiedad e Insiders",
    ]

    ws_summary = wb["Resumen & Múltiplos"]
    summary_vals = {ws_summary.cell(r, 1).value: ws_summary.cell(r, 2).value for r in range(1, ws_summary.max_row + 1)}
    assert summary_vals["Sector"] == "Technology"
    assert summary_vals["Market Cap (US$ MM)"] == 3705000.0
    assert summary_vals["EV / EBITDA"] == 21.4
    assert summary_vals["ROIC (%)"] == 28.9

    ws_val = wb["Valoración"]
    val_vals = [cell.value for row in ws_val.iter_rows() for cell in row if cell.value is not None]
    assert "Precio / Beneficio (P/E)" in val_vals
    assert 26.01 in val_vals


def test_build_company_pdf_bytes_generates_valid_pdf():
    profile, statements, health, valuation, ownership = _sample_export_inputs()
    raw_pdf = build_company_pdf_bytes(
        ticker="MSFT",
        profile=profile,
        market=profile,
        statements=statements,
        valuation=valuation,
        ownership=ownership,
        health=health,
    )

    assert isinstance(raw_pdf, bytes)
    assert raw_pdf.startswith(b"%PDF-")
    assert len(raw_pdf) > 2000


def test_export_endpoints_return_attachment_headers(monkeypatch):
    from app.core.security import get_current_user
    from app.models.database import User

    profile, statements, health, valuation, ownership = _sample_export_inputs()

    monkeypatch.setattr(
        "app.api.endpoints._collect_company_export_payload",
        lambda ticker, period, db: {
            "ticker": ticker.upper(),
            "profile": profile,
            "market": profile,
            "statements": statements,
            "health": health,
            "valuation": valuation,
            "ownership": ownership,
        },
    )

    app.dependency_overrides[get_current_user] = lambda: User(
        id=1, username="tester", email="tester@vektor.local", full_name="Tester", role="superadmin", is_active=True
    )
    client = TestClient(app)

    try:
        resp_xlsx = client.get("/api/v1/company/MSFT/export/xlsx?period=annual")
        assert resp_xlsx.status_code == 200
        assert "spreadsheetml.sheet" in resp_xlsx.headers["content-type"]

        resp_pdf = client.get("/api/v1/company/MSFT/export/pdf")
        assert resp_pdf.status_code == 200
        assert resp_pdf.headers["content-type"] == "application/pdf"
        assert resp_pdf.content.startswith(b"%PDF-")
    finally:
        app.dependency_overrides.clear()