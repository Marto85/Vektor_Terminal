from fastapi.testclient import TestClient
from app.main import app
from app.api import endpoints
from app.core.security import get_current_user
from app.models.database import User
from app.services.auth_service import ensure_default_superadmin
from app.core.config import VEKTOR_ADMIN_EMAIL, VEKTOR_ADMIN_PASSWORD


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
        ensure_default_superadmin()
        adm = client.post(
            "/api/v1/auth/login",
            json={"email": VEKTOR_ADMIN_EMAIL, "password": VEKTOR_ADMIN_PASSWORD},
        )
        headers = {"Authorization": f"Bearer {adm.json()['access_token']}"}

        # 1. Crear dos listas (regla de negocio: siempre debe quedar al menos 1 watchlist activa)
        res_first = client.post("/api/v1/watchlists", json={"name": "Principal"}, headers=headers)
        assert res_first.status_code == 200

        res_create = client.post("/api/v1/watchlists", json={"name": "Tech Quality"}, headers=headers)
        assert res_create.status_code == 200
        payload = res_create.json()
        wl = next(w for w in payload["watchlists"] if w["name"] == "Tech Quality")
        wl_id = wl["id"]

        # 2. Renombrar lista
        res_rename = client.put(f"/api/v1/watchlists/{wl_id}", json={"name": "Core Compounders"}, headers=headers)
        assert res_rename.status_code == 200
        assert any(w["name"] == "Core Compounders" for w in res_rename.json()["watchlists"])

        # 3. Eliminar segunda lista (permitido porque queda "Principal")
        res_del = client.delete(f"/api/v1/watchlists/{wl_id}", headers=headers)
        assert res_del.status_code == 200

        # 4. Intentar eliminar la última watchlist restante debe devolver 400
        remaining_id = res_del.json()["watchlists"][0]["id"]
        res_del_last = client.delete(f"/api/v1/watchlists/{remaining_id}", headers=headers)
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

    def fake_user():
        return User(id=1, username="tester", email="tester@vektor.local", full_name="Tester", role="superadmin", is_active=True)

    app.dependency_overrides[endpoints.get_db] = override_get_db
    app.dependency_overrides[get_current_user] = fake_user
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


def test_endpoints_require_authentication_and_segments_rbac():
    client = TestClient(app)

    # Sin token: endpoints de datos, sync y segmentos deben devolver 401
    assert client.get("/api/v1/company/msft/valuation").status_code == 401
    assert client.get("/api/v1/screener").status_code == 401
    assert client.post("/api/v1/screener/sync").status_code == 401
    assert client.put("/api/v1/company/msft/segments", json={}).status_code == 401
    assert client.delete("/api/v1/company/msft/segments").status_code == 401

    # Con usuario rol client: no puede modificar/borrar segmentos compartidos (403)
    def fake_client():
        return User(id=99, username="cli", email="cli@vektor.local", full_name="Cli", role="client", is_active=True)

    app.dependency_overrides[get_current_user] = fake_client
    try:
        assert client.put("/api/v1/company/msft/segments", json={}).status_code == 403
        assert client.delete("/api/v1/company/msft/segments").status_code == 403
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


def test_company_history_uses_price_history_cache(monkeypatch, db_session):
    from datetime import datetime, timezone
    from app.models.database import PriceHistoryCache

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    cached_payload = {
        "ticker": "MSFT",
        "range": "1y",
        "interval": "1d",
        "isIntraday": False,
        "years": 1.0,
        "totalReturnPct": 15.0,
        "cagrPct": 15.0,
        "capitalStructureSource": "sec_historical",
        "seriesByMetric": {"Price": [{"time": "2026-01-02", "open": 400.0, "high": 405.0, "low": 399.0, "close": 404.0, "volume": 1000, "change": 4.0, "changePct": 1.0}]},
    }
    db_session.add(
        PriceHistoryCache(
            cache_key="MSFT:1y:1d",
            ticker="MSFT",
            range_key="1y:1d",
            payload=cached_payload,
            last_updated=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    db_session.commit()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("No debería consultar Yahoo Finance cuando PriceHistoryCache está vigente")

    app.dependency_overrides[endpoints.get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1, username="tester", email="tester@vektor.local", full_name="Tester", role="superadmin", is_active=True
    )
    monkeypatch.setattr(endpoints.yf, "Ticker", fail_if_called)
    client = TestClient(app)

    try:
        res = client.get("/api/v1/company/msft/history?range=1y&interval=1d")
        assert res.status_code == 200
        assert res.json()["ticker"] == "MSFT"
        assert res.json()["capitalStructureSource"] == "sec_historical"
    finally:
        app.dependency_overrides.clear()


def test_search_ticker_falls_back_to_local_universe_when_yahoo_fails(monkeypatch, db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def fail_requests_get(*_args, **_kwargs):
        raise RuntimeError("Yahoo timeout simulado")

    endpoints._SEARCH_CACHE.clear()
    app.dependency_overrides[endpoints.get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1, username="tester", email="tester@vektor.local", full_name="Tester", role="superadmin", is_active=True
    )
    monkeypatch.setattr(endpoints.requests, "get", fail_requests_get)
    client = TestClient(app)

    try:
        res = client.get("/api/v1/search?q=AAP")
        assert res.status_code == 200
        tickers = [item["ticker"] for item in res.json()]
        assert "AAPL" in tickers
    finally:
        app.dependency_overrides.clear()


def test_screener_sync_cooldown_advances_past_failing_tickers(monkeypatch, db_session):
    from app.services import screener_service

    screener_service._FAILED_SYNC_COOLDOWN.clear()
    monkeypatch.setattr(screener_service, "SCREENER_UNIVERSE", ["FAIL1", "OK1", "OK2"])

    attempted = []

    def fake_fetch(sym: str):
        attempted.append(sym)
        if sym == "FAIL1":
            return sym, None
        return sym, {"price": 100.0, "info": {"shortName": sym}}

    monkeypatch.setattr(screener_service, "_fetch_snapshot_isolated", fake_fetch)

    res1 = screener_service.sync_screener_batch(db_session, batch_size=1)
    assert res1["synced_now"] == []
    assert "FAIL1" in screener_service._FAILED_SYNC_COOLDOWN

    # Segundo intento debe saltear FAIL1 (en cooldown) y avanzar a OK1
    res2 = screener_service.sync_screener_batch(db_session, batch_size=1)
    assert res2["synced_now"] == ["OK1"]
    assert attempted == ["FAIL1", "OK1"]