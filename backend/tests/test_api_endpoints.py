from fastapi.testclient import TestClient
from app.main import app
from app.api import endpoints


def test_root_healthcheck():
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "online"


def test_watchlist_crud_lifecycle(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[endpoints.get_db] = override_get_db
    client = TestClient(app)

    try:
        # 1. Crear dos listas (regla de negocio: siempre debe quedar al menos 1 watchlist activa)
        res_first = client.post("/api/v1/watchlists", json={"name": "Principal"})
        assert res_first.status_code == 200

        res_create = client.post("/api/v1/watchlists", json={"name": "Tech Quality"})
        assert res_create.status_code == 200
        payload = res_create.json()
        wl = next(w for w in payload["watchlists"] if w["name"] == "Tech Quality")
        wl_id = wl["id"]

        # 2. Renombrar lista
        res_rename = client.put(f"/api/v1/watchlists/{wl_id}", json={"name": "Core Compounders"})
        assert res_rename.status_code == 200
        assert any(w["name"] == "Core Compounders" for w in res_rename.json()["watchlists"])

        # 3. Eliminar segunda lista (permitido porque queda "Principal")
        res_del = client.delete(f"/api/v1/watchlists/{wl_id}")
        assert res_del.status_code == 200

        # 4. Intentar eliminar la última watchlist restante debe devolver 400
        remaining_id = res_del.json()["watchlists"][0]["id"]
        res_del_last = client.delete(f"/api/v1/watchlists/{remaining_id}")
        assert res_del_last.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_valuation_endpoint_with_mocked_service(monkeypatch, db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def fake_build_valuation_report(ticker: str, db):
        return {
            "ticker": ticker.upper(),
            "sector_routing": {"profile": "standard", "label": "Corporativo Estándar"},
            "years": ["2023", "2024"],
            "rows": [],
            "audit": {"has_anomalies": False, "flags": [], "comparisons": []},
            "trajectory": {"recommended_rev_growth_pct": 12.5},
            "reverse_dcf": {
                "mode": "standard",
                "horizon_5y": {"solvable": True, "implied_growth_pct": 11.2},
            },
            "dcf_inputs": {"current_price": 150.0},
            "financial_sector_inputs": {},
        }

    app.dependency_overrides[endpoints.get_db] = override_get_db
    monkeypatch.setattr(endpoints, "build_valuation_report", fake_build_valuation_report)
    client = TestClient(app)

    try:
        res = client.get("/api/v1/company/msft/valuation")
        assert res.status_code == 200
        data = res.json()
        assert data["ticker"] == "MSFT"
        assert data["reverse_dcf"]["horizon_5y"]["implied_growth_pct"] == 11.2
    finally:
        app.dependency_overrides.clear()


def test_company_profile_translation_and_fallback(monkeypatch, db_session):
    from app.core import yf_client

    def fake_snapshot(ticker_symbol: str, db):
        return {
            "price": 100.0,
            "change": 1.0,
            "change_pct": 1.01,
            "fx_rate": 1.0,
            "news": [],
            "cf_ltm": {},
            "info": {
                "longName": "Test Corp",
                "website": "https://example.com",
                "longBusinessSummary": "Test Corp builds enterprise cloud software.",
                "sharesOutstanding": 10_000_000,
            },
        }

    class FakeTranslator:
        def __init__(self, source="en", target="es"):
            pass

        def translate(self, text: str) -> str:
            return "Test Corp desarrolla software empresarial en la nube."

    monkeypatch.setattr(yf_client, "get_cached_market_snapshot", fake_snapshot)
    monkeypatch.setattr(yf_client, "GoogleTranslator", FakeTranslator)

    profile = yf_client.get_company_profile("TST", db_session)
    assert profile["description"] == "Test Corp desarrolla software empresarial en la nube."
