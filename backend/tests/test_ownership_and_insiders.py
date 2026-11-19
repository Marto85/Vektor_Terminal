import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.api import endpoints
from app.services import ownership_service


def test_build_ownership_and_insiders_report_with_synthetic_data(monkeypatch, db_session):
    def fake_snapshot(ticker_symbol: str, db):
        return {
            "price": 200.0,
            "change": 2.0,
            "change_pct": 1.01,
            "fx_rate": 1.0,
            "news": [],
            "cf_ltm": {},
            "info": {
                "longName": "Alpha Tech Inc.",
                "sharesOutstanding": 1_000_000_000,
                "heldPercentInsiders": 0.045,
                "heldPercentInstitutions": 0.725,
            },
        }

    class FakeTicker:
        def __init__(self, sym: str):
            self.sym = sym

        @property
        def major_holders(self):
            return pd.DataFrame(
                {"Value": [0.045, 0.725, 0.759, 3200]},
                index=[
                    "insidersPercentHeld",
                    "institutionsPercentHeld",
                    "institutionsFloatPercentHeld",
                    "institutionsCount",
                ],
            )

        @property
        def institutional_holders(self):
            return pd.DataFrame([
                {
                    "Holder": "Vanguard Group Inc",
                    "Date Reported": pd.Timestamp("2026-09-30"),
                    "Shares": 85_000_000,
                    "pctHeld": 0.085,
                    "Value": 17_000_000_000,
                    "pctChange": 0.015,
                },
                {
                    "Holder": "BlackRock Inc.",
                    "Date Reported": pd.Timestamp("2026-09-30"),
                    "Shares": 70_000_000,
                    "pctHeld": 0.070,
                    "Value": 14_000_000_000,
                    "pctChange": -0.008,
                },
            ])

        @property
        def mutualfund_holders(self):
            return pd.DataFrame([
                {
                    "Holder": "Vanguard Total Stock Market Index Fund",
                    "Date Reported": pd.Timestamp("2026-09-30"),
                    "Shares": 31_000_000,
                    "pctHeld": 0.031,
                    "Value": 6_200_000_000,
                }
            ])

        @property
        def insider_transactions(self):
            return pd.DataFrame([
                {
                    "Insider": "Jane Doe",
                    "Position": "Chief Financial Officer",
                    "Transaction": "Purchase at price 195.00 per share.",
                    "Start Date": pd.Timestamp("2026-10-15"),
                    "Shares": 10_000,
                    "Value": 1_950_000.0,
                    "Ownership": "D",
                },
                {
                    "Insider": "John Smith",
                    "Position": "Director",
                    "Transaction": "Sale at price 202.00 per share.",
                    "Start Date": pd.Timestamp("2026-10-10"),
                    "Shares": 2_000,
                    "Value": 404_000.0,
                    "Ownership": "D",
                },
            ])

    monkeypatch.setattr(ownership_service, "get_cached_market_snapshot", fake_snapshot)
    monkeypatch.setattr(ownership_service.yf, "Ticker", FakeTicker)

    report = ownership_service.build_ownership_and_insiders_report("ALPH", db_session)
    assert report["ticker"] == "ALPH"
    assert report["major_holders"]["institutions_pct"] == 72.5
    assert report["major_holders"]["insiders_pct"] == 4.5
    assert len(report["institutional_holders"]) == 2
    assert report["institutional_holders"][0]["holder"] == "Vanguard Group Inc"
    assert report["institutional_holders"][0]["value_mm"] == 17000.0
    assert report["insider_summary"]["buy_count"] == 1
    assert report["insider_summary"]["sell_count"] == 1
    assert report["insider_summary"]["net_value_mm"] == 1.55  # 1.95M - 0.404M


def test_ownership_endpoint_route(monkeypatch, db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    monkeypatch.setattr(
        endpoints,
        "build_ownership_and_insiders_report",
        lambda ticker, db: {
            "ticker": ticker.upper(),
            "company_name": "Test Corp",
            "major_holders": {"institutions_pct": 65.0, "insiders_pct": 5.0},
            "institutional_holders": [],
            "mutualfund_holders": [],
            "insider_transactions": [],
            "insider_summary": {"buy_count": 0, "sell_count": 0, "net_value_mm": 0.0},
        },
    )
    app.dependency_overrides[endpoints.get_db] = override_get_db
    client = TestClient(app)

    try:
        res = client.get("/api/v1/company/msft/ownership")
        assert res.status_code == 200
        assert res.json()["ticker"] == "MSFT"
        assert res.json()["major_holders"]["institutions_pct"] == 65.0
    finally:
        app.dependency_overrides.clear()
