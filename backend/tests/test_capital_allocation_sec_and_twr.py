from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import (
    Base,
    CompanyMarketCache,
    CompanyData,
    Watchlist,
    WatchlistItem,
    AlertNotification,
    PortfolioTransaction,
)
from app.services.ratios_calculator import calculate_ratios, build_financial_health_report
from app.services.watchlist_service import get_all_watchlists_payload
from app.services.portfolio_service import compute_portfolio_positions


def _make_in_memory_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _sample_financial_rows(y_prev: str, y_curr: str) -> list[dict]:
    """
    Construye un estado contable sintético de 2 años con números exactos
    para auditar ROIIC, Reinvestment Rate, FCF Post-SBC y TSR Bridge.
    """
    return [
        {"Categoría": "Cuenta de Resultados", "Métrica": "Ingresos Totales", y_prev: 1000.0, y_curr: 1200.0},
        {"Categoría": "Cuenta de Resultados", "Métrica": "Coste de los bienes vendidos", y_prev: 400.0, y_curr: 450.0},
        {"Categoría": "Cuenta de Resultados", "Métrica": "Beneficio Bruto", y_prev: 600.0, y_curr: 750.0},
        {"Categoría": "Cuenta de Resultados", "Métrica": "Depreciación y Amortización", y_prev: 50.0, y_curr: 60.0},
        {"Categoría": "Cuenta de Resultados", "Métrica": "Beneficio Operativo", y_prev: 200.0, y_curr: 260.0},
        {"Categoría": "Cuenta de Resultados", "Métrica": "Gastos por Intereses", y_prev: 10.0, y_curr: 10.0},
        {"Categoría": "Cuenta de Resultados", "Métrica": "Beneficio antes de Impuestos", y_prev: 190.0, y_curr: 250.0},
        {"Categoría": "Cuenta de Resultados", "Métrica": "Gasto por Impuesto a las Ganancias", y_prev: 38.0, y_curr: 50.0},
        {"Categoría": "Cuenta de Resultados", "Métrica": "Beneficio Neto", y_prev: 152.0, y_curr: 200.0},
        {"Categoría": "Cuenta de Resultados", "Métrica": "Acciones en Circulación (Diluidas)", y_prev: 100.0, y_curr: 98.0},
        {"Categoría": "Balance de Situación", "Métrica": "Efectivo y equivalentes", y_prev: 100.0, y_curr: 120.0},
        {"Categoría": "Balance de Situación", "Métrica": "Inversiones a corto plazo", y_prev: 0.0, y_curr: 0.0},
        {"Categoría": "Balance de Situación", "Métrica": "Total activo corriente", y_prev: 300.0, y_curr: 360.0},
        {"Categoría": "Balance de Situación", "Métrica": "Total activo", y_prev: 900.0, y_curr: 1050.0},
        {"Categoría": "Balance de Situación", "Métrica": "Deuda a corto plazo", y_prev: 50.0, y_curr: 50.0},
        {"Categoría": "Balance de Situación", "Métrica": "Total pasivo corriente", y_prev: 150.0, y_curr: 170.0},
        {"Categoría": "Balance de Situación", "Métrica": "Deuda a largo plazo", y_prev: 200.0, y_curr: 220.0},
        {"Categoría": "Balance de Situación", "Métrica": "Total pasivo", y_prev: 400.0, y_curr: 450.0},
        {"Categoría": "Balance de Situación", "Métrica": "Ganancias retenidas", y_prev: 300.0, y_curr: 400.0},
        {"Categoría": "Balance de Situación", "Métrica": "Patrimonio neto", y_prev: 500.0, y_curr: 600.0},
        {"Categoría": "Estado de Flujo de Efectivo", "Métrica": "Efectivo de Operaciones (CFO)", y_prev: 210.0, y_curr: 270.0},
        {"Categoría": "Estado de Flujo de Efectivo", "Métrica": "Gastos de capital (CapEx)", y_prev: 70.0, y_curr: 90.0},
        {"Categoría": "Estado de Flujo de Efectivo", "Métrica": "Compensación basada en acciones", y_prev: 40.0, y_curr: 54.0},
        {"Categoría": "Estado de Flujo de Efectivo", "Métrica": "Flujo de caja libre (FCF)", y_prev: 140.0, y_curr: 180.0},
        {"Categoría": "Estado de Flujo de Efectivo", "Métrica": "Pago de dividendos", y_prev: 20.0, y_curr: 25.0},
        {"Categoría": "Estado de Flujo de Efectivo", "Métrica": "Recompra de acciones", y_prev: 30.0, y_curr: 40.0},
    ]


def test_roiic_reinvestment_fcf_post_sbc_and_tsr_bridge():
    db = _make_in_memory_db()
    curr_year = datetime.now().year
    y_prev = str(curr_year - 2)
    y_curr = str(curr_year - 1)
    years_range = [str(y) for y in range(curr_year - 6, curr_year + 1)]

    db.add(
        CompanyMarketCache(
            ticker="TEST",
            market_data={
                "name": "Test Corp",
                "sector": "Technology",
                "industry": "Software",
                "summary_metrics": {"capital": {"market_cap": 2500.0}},
            },
        )
    )
    db.commit()

    rows = _sample_financial_rows(y_prev, y_curr)
    rows_with_ratios = calculate_ratios(list(rows), years_range)

    # Verificar filas nuevas en la tabla de ratios
    by_metric = {r["Métrica"]: r for r in rows_with_ratios if not r.get("is_header")}
    assert "ROIC (NOPAT / Capital Invertido) %" in by_metric
    assert "ROIIC Incremental Interanual %" in by_metric
    assert "FCF Ajustado por SBC (US$ MM)" in by_metric
    assert by_metric["FCF Ajustado por SBC (US$ MM)"][y_curr] == 126.0  # 180 FCF - 54 SBC

    # Mock de precios históricos para validar el TSR Bridge sin internet
    mock_hist = pd.DataFrame(
        {"Close": [100.0, 125.0]},
        index=pd.to_datetime(["2024-01-01", "2025-01-01"]),
    )
    mock_tk = MagicMock()
    mock_tk.history.return_value = mock_hist

    with patch("app.services.ratios_calculator.yf.Ticker", return_value=mock_tk):
        report = build_financial_health_report("TEST", rows, db)

    cap_alloc = report["capital_allocation"]
    # IC prev = 250 + 500 - 100 = 650 | IC curr = 270 + 600 - 120 = 750 => ΔIC = 100
    # NOPAT prev = 200 * (1 - 0.20) = 160 | NOPAT curr = 260 * (1 - 0.20) = 208 => ΔNOPAT = 48
    # ROIIC = 48 / 100 = 48.0%
    assert cap_alloc["invested_capital_mm"] == 750.0
    assert cap_alloc["nopat_mm"] == 208.0
    assert cap_alloc["roiic_1y_pct"] == 48.0
    assert cap_alloc["roiic_multi_pct"] == 48.0

    # Reinversión neta: (CapEx 90 - D&A 60) + ΔNWC [(360-120)-(170-50) - ((300-100)-(150-50)) = 120 - 100 = 20] = 50
    # Reinvestment Rate = 50 / 208 = 24.04%
    assert cap_alloc["reinvestment_rate_pct"] == 24.04

    # Calidad FCF post-SBC: 54 / 180 = 30.0% -> alerta amber (>= 25%)
    assert cap_alloc["fcf_reported_mm"] == 180.0
    assert cap_alloc["sbc_mm"] == 54.0
    assert cap_alloc["fcf_adj_sbc_mm"] == 126.0
    assert cap_alloc["sbc_to_fcf_pct"] == 30.0
    assert cap_alloc["sbc_color"] == "amber"

    # TSR Bridge
    tsr = cap_alloc["tsr_bridge"]
    assert tsr["fundamental_growth_pct"] == 20.0  # 1000 -> 1200 en 1 año
    assert tsr["dividend_yield_pct"] == 1.0  # 25 / 2500
    assert tsr["net_buyback_yield_pct"] == 2.0  # 100 -> 98 acciones (-2% = +2% buyback yield)
    assert tsr["capital_return_pct"] == 3.0


def test_roiic_handles_negative_incremental_capital_gracefully():
    db = _make_in_memory_db()
    curr_year = datetime.now().year
    y_prev = str(curr_year - 2)
    y_curr = str(curr_year - 1)

    db.add(
        CompanyMarketCache(
            ticker="CAPEFF",
            market_data={"name": "Capital Light Inc", "sector": "Technology", "industry": "Software"},
        )
    )
    db.commit()

    rows = _sample_financial_rows(y_prev, y_curr)
    # Aumentamos la caja final a 400 para que IC caiga de 650 a 470 mientras NOPAT sube
    for r in rows:
        if r["Métrica"] == "Efectivo y equivalentes":
            r[y_curr] = 400.0

    mock_tk = MagicMock()
    mock_tk.history.return_value = pd.DataFrame()

    with patch("app.services.ratios_calculator.yf.Ticker", return_value=mock_tk):
        report = build_financial_health_report("CAPEFF", rows, db)

    cap_alloc = report["capital_allocation"]
    assert cap_alloc["roiic_1y_pct"] is None
    assert cap_alloc["roiic_multi_pct"] is None
    assert "sin consumo neto de capital" in cap_alloc["roiic_note"]


def test_sec_filing_alert_detection_and_deduplication():
    db = _make_in_memory_db()
    wl = Watchlist(name="Seguimiento SEC")
    db.add(wl)
    db.commit()
    db.refresh(wl)

    db.add(WatchlistItem(watchlist_id=wl.id, ticker="MSFT", position=0))
    db.add(
        CompanyMarketCache(
            ticker="MSFT",
            market_data={"name": "Microsoft Corp", "price": 420.0, "summary_metrics": {}},
        )
    )
    db.add(CompanyData(ticker="MSFT", cik="0000789019", raw_facts={}))
    db.commit()

    recent_date = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
    old_date = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")

    mock_filings = [
        {
            "form": "10-Q",
            "filing_date": recent_date,
            "report_date": recent_date,
            "accession_number": "0000789019-26-000099",
            "document_url": "https://www.sec.gov/Archives/edgar/data/789019/000078901926000099/msft.htm",
        },
        {
            "form": "10-K",
            "filing_date": old_date,
            "report_date": old_date,
            "accession_number": "0000789019-26-000010",
            "document_url": "https://www.sec.gov/Archives/edgar/data/789019/000078901926000010/msft10k.htm",
        },
    ]

    with patch("app.services.watchlist_service.get_recent_sec_filings", return_value=mock_filings):
        payload_1 = get_all_watchlists_payload(db)
        # Segunda ejecución para confirmar que no duplica notificaciones
        payload_2 = get_all_watchlists_payload(db)

    sec_notifs = [n for n in payload_2["notifications"] if n["alert_type"] == "sec_filing"]
    assert len(sec_notifs) == 1
    assert sec_notifs[0]["ticker"] == "MSFT"
    assert "10-Q" in sec_notifs[0]["title"]
    assert db.query(AlertNotification).filter(AlertNotification.alert_type == "sec_filing").count() == 1
    assert payload_1["unread_notifications_count"] == 1


def test_portfolio_twr_isolates_external_cashflows():
    """
    Escenario clásico de validación TWR vs Retorno sobre Capital:
    1) Día 1: Depósito US$ 10.000 y compra de 100 acciones de AAPL a US$ 100.
    2) Día 10: AAPL sube a US$ 120 (+20% en tramo 1). Cliente deposita US$ 30.000 adicionales
       y compra 250 acciones a US$ 120 (total 350 acciones).
    3) Día 20: AAPL cae 10% hasta US$ 108.
       - Patrimonio final = 350 * 108 = US$ 37.800 (pérdida nominal frente a US$ 40.000 aportados).
       - TWR real = (1 + 0.20) * (1 - 0.10) - 1 = 1.08 - 1 = +8.00%.
    """
    txs = [
        PortfolioTransaction(id=1, client_id=1, tx_type="DEPOSIT", ticker=None, tx_date="2026-01-01", quantity=10000.0, unit_price=1.0, commission=0.0),
        PortfolioTransaction(id=2, client_id=1, tx_type="BUY", ticker="AAPL", tx_date="2026-01-01", quantity=100.0, unit_price=100.0, commission=0.0),
        PortfolioTransaction(id=3, client_id=1, tx_type="DEPOSIT", ticker=None, tx_date="2026-01-10", quantity=30000.0, unit_price=1.0, commission=0.0),
        PortfolioTransaction(id=4, client_id=1, tx_type="BUY", ticker="AAPL", tx_date="2026-01-10", quantity=250.0, unit_price=120.0, commission=0.0),
    ]

    result = compute_portfolio_positions(txs, quotes_map={"AAPL": {"price": 108.0}})
    summary = result["summary"]

    assert summary["net_contributed_capital"] == 40000.0
    assert summary["total_equity"] == 37800.0
    assert summary["total_unrealized_pnl"] == -2200.0
    assert summary["twr_pct"] == 8.0
    assert summary["subperiods_count"] == 2