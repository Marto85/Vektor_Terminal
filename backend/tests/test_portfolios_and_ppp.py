from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import VEKTOR_ADMIN_EMAIL, VEKTOR_ADMIN_PASSWORD
from app.models.database import ClientProfile, PortfolioTransaction, SessionLocal, User
from app.services.auth_service import ensure_default_superadmin

client = TestClient(app)


def _cleanup():
    db = SessionLocal()
    try:
        emails = ["asesor.crm@vektor.local", "cliente.crm@vektor.local"]
        users = db.query(User).filter(User.email.in_(emails)).all()
        user_ids = [u.id for u in users]
        if user_ids:
            db.query(PortfolioTransaction).filter(
                PortfolioTransaction.client_id.in_(user_ids)
            ).delete(synchronize_session=False)
            db.query(ClientProfile).filter(
                ClientProfile.user_id.in_(user_ids)
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(user_ids)).delete(
                synchronize_session=False
            )
            db.commit()
    finally:
        db.close()


@patch("app.services.portfolio_service.fetch_live_quotes")
def test_ppp_calculation_and_portfolio_rbac(mock_quotes):
    mock_quotes.return_value = {
        "MSFT": {"price": 450.0, "day_change_pct": 1.25},
    }

    ensure_default_superadmin()
    _cleanup()

    try:
        # 1. Login superadmin
        adm = client.post(
            "/api/v1/auth/login",
            json={"email": VEKTOR_ADMIN_EMAIL, "password": VEKTOR_ADMIN_PASSWORD},
        )
        adm_headers = {"Authorization": f"Bearer {adm.json()['access_token']}"}

        # 2. Crear advisor y client asignado
        adv_res = client.post(
            "/api/v1/admin/users",
            headers=adm_headers,
            json={
                "email": "asesor.crm@vektor.local",
                "full_name": "Asesor CRM",
                "password": "Password123!",
                "role": "advisor",
                "must_change_password": False,
            },
        )
        advisor_id = adv_res.json()["user"]["id"]

        cli_res = client.post(
            "/api/v1/admin/users",
            headers=adm_headers,
            json={
                "email": "cliente.crm@vektor.local",
                "full_name": "Cliente CRM",
                "password": "Password123!",
                "role": "client",
                "advisor_id": advisor_id,
                "must_change_password": False,
            },
        )
        client_id = cli_res.json()["user"]["id"]

        # 3. Login como asesor
        adv_login = client.post(
            "/api/v1/auth/login",
            json={"email": "asesor.crm@vektor.local", "password": "Password123!"},
        )
        adv_headers = {"Authorization": f"Bearer {adv_login.json()['access_token']}"}

        # 4. Actualizar ficha CRM del cliente
        prof_res = client.patch(
            f"/api/v1/portfolios/{client_id}/profile",
            headers=adv_headers,
            json={
                "risk_profile": "agresivo",
                "investment_horizon": "largo_plazo",
                "notes": "Acumulación en tecnología quality.",
            },
        )
        assert prof_res.status_code == 200
        assert prof_res.json()["client"]["risk_profile"] == "agresivo"

        # 5. Cargar 2 compras de MSFT con distinta cotización y comisión
        # Compra 1: 10 a $400 + $10 comisión = $4010
        tx1 = client.post(
            f"/api/v1/portfolios/{client_id}/transactions",
            headers=adv_headers,
            json={
                "tx_type": "BUY",
                "ticker": "MSFT",
                "tx_date": "2026-01-10",
                "quantity": 10,
                "unit_price": 400.0,
                "commission": 10.0,
            },
        )
        assert tx1.status_code == 200

        # Compra 2: 10 a $420 + $10 comisión = $4210
        # Total: 20 nominales, costo total = $8220 => PPP = $411.00
        tx2 = client.post(
            f"/api/v1/portfolios/{client_id}/transactions",
            headers=adv_headers,
            json={
                "tx_type": "BUY",
                "ticker": "MSFT",
                "tx_date": "2026-02-15",
                "quantity": 10,
                "unit_price": 420.0,
                "commission": 10.0,
            },
        )
        assert tx2.status_code == 200
        holding = tx2.json()["holdings"][0]
        assert holding["quantity"] == 20.0
        assert holding["ppp"] == 411.0

        # 6. Venta parcial: 5 nominales a $440 - $5 comisión = $2195 neto
        # Costo removido: 5 * 411 = $2055 => P&L realizado = +$140
        # Remanente: 15 nominales a PPP $411 ($6165 costo), precio actual $450 => $6750 mercado (+$585 no realizado)
        tx3 = client.post(
            f"/api/v1/portfolios/{client_id}/transactions",
            headers=adv_headers,
            json={
                "tx_type": "BUY" if False else "SELL",
                "ticker": "MSFT",
                "tx_date": "2026-03-01",
                "quantity": 5,
                "unit_price": 440.0,
                "commission": 5.0,
            },
        )
        assert tx3.status_code == 200
        data3 = tx3.json()
        assert data3["holdings"][0]["quantity"] == 15.0
        assert data3["holdings"][0]["ppp"] == 411.0
        assert data3["summary"]["total_realized_pnl"] == 140.0
        assert data3["summary"]["total_market_value"] == 6750.0
        assert data3["summary"]["total_unrealized_pnl"] == 585.0

        # 7. Evitar sobreventa (intentar vender 50 cuando quedan 15)
        bad_sell = client.post(
            f"/api/v1/portfolios/{client_id}/transactions",
            headers=adv_headers,
            json={
                "tx_type": "SELL",
                "ticker": "MSFT",
                "tx_date": "2026-03-05",
                "quantity": 50,
                "unit_price": 450.0,
            },
        )
        assert bad_sell.status_code == 400

        # 8. Cliente puede leer y autogestionar su cartera; superadmin ajeno recibe 403
        cli_login = client.post(
            "/api/v1/auth/login",
            json={"email": "cliente.crm@vektor.local", "password": "Password123!"},
        )
        cli_headers = {"Authorization": f"Bearer {cli_login.json()['access_token']}"}

        my_port = client.get("/api/v1/portfolios/me", headers=cli_headers)
        assert my_port.status_code == 200
        assert my_port.json()["can_edit"] is True
        assert my_port.json()["holdings"][0]["ppp"] == 411.0

        cli_write = client.post(
            f"/api/v1/portfolios/{client_id}/transactions",
            headers=cli_headers,
            json={
                "tx_type": "BUY",
                "ticker": "AAPL",
                "tx_date": "2026-03-10",
                "quantity": 1,
                "unit_price": 200.0,
            },
        )
        assert cli_write.status_code == 200

        adm_read = client.get(f"/api/v1/portfolios/{client_id}", headers=adm_headers)
        assert adm_read.status_code == 403

        # 9. Rechazar operaciones en moneda distinta a target_currency (USD)
        bad_curr = client.post(
            f"/api/v1/portfolios/{client_id}/transactions",
            headers=cli_headers,
            json={
                "tx_type": "BUY",
                "ticker": "YPFD.BA",
                "tx_date": "2026-03-11",
                "quantity": 10,
                "unit_price": 40000.0,
                "currency": "ARS",
            },
        )
        assert bad_curr.status_code == 400
    finally:
        _cleanup()