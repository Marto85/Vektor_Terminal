from fastapi.testclient import TestClient
from app.main import app
from app.core.config import VEKTOR_ADMIN_EMAIL, VEKTOR_ADMIN_PASSWORD
from app.models.database import SessionLocal, User
from app.services.auth_service import ensure_default_superadmin

client = TestClient(app)


def _cleanup_test_users():
    db = SessionLocal()
    try:
        db.query(User).filter(
            User.email.in_(
                [
                    "advisor.test@vektor.local",
                    "client.test@vektor.local",
                ]
            )
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_login_superadmin_and_rbac_user_lifecycle():
    ensure_default_superadmin()
    _cleanup_test_users()

    try:
        # 1. Login fallido devuelve 401
        bad_login = client.post(
            "/api/v1/auth/login",
            json={"email": VEKTOR_ADMIN_EMAIL, "password": "wrong-password"},
        )
        assert bad_login.status_code == 401

        # 2. Login exitoso como superadmin
        admin_login = client.post(
            "/api/v1/auth/login",
            json={
                "email": VEKTOR_ADMIN_EMAIL,
                "password": VEKTOR_ADMIN_PASSWORD,
            },
        )
        assert admin_login.status_code == 200
        admin_data = admin_login.json()
        admin_token = admin_data["access_token"]
        assert admin_data["user"]["role"] == "superadmin"
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 3. Verificar /auth/me
        me_res = client.get("/api/v1/auth/me", headers=admin_headers)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == VEKTOR_ADMIN_EMAIL

        # 4. Superadmin crea un advisor y luego un client asignado a ese advisor
        create_adv = client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "email": "advisor.test@vektor.local",
                "full_name": "Asesor Prueba",
                "password": "Password123!",
                "role": "advisor",
                "must_change_password": False,
            },
        )
        assert create_adv.status_code == 200
        advisor_id = create_adv.json()["user"]["id"]

        create_cli = client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "email": "client.test@vektor.local",
                "full_name": "Cliente Prueba",
                "password": "Password123!",
                "role": "client",
                "advisor_id": advisor_id,
                "must_change_password": False,
            },
        )
        assert create_cli.status_code == 200
        client_id = create_cli.json()["user"]["id"]
        assert create_cli.json()["user"]["advisor_id"] == advisor_id

        # 5. Advisor puede listar solo sus clientes asignados, pero NO crear usuarios
        adv_login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "advisor.test@vektor.local",
                "password": "Password123!",
            },
        )
        adv_headers = {
            "Authorization": f"Bearer {adv_login.json()['access_token']}"
        }
        adv_list = client.get("/api/v1/admin/users", headers=adv_headers)
        assert adv_list.status_code == 200
        listed_emails = [u["email"] for u in adv_list.json()["users"]]
        assert "client.test@vektor.local" in listed_emails

        adv_forbidden = client.post(
            "/api/v1/admin/users",
            headers=adv_headers,
            json={
                "email": "otro@vektor.local",
                "full_name": "Otro",
                "password": "Password123!",
                "role": "client",
            },
        )
        assert adv_forbidden.status_code == 403

        # 6. Client recibe 403 al intentar acceder a /admin/users
        cli_login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "client.test@vektor.local",
                "password": "Password123!",
            },
        )
        cli_headers = {
            "Authorization": f"Bearer {cli_login.json()['access_token']}"
        }
        cli_forbidden = client.get("/api/v1/admin/users", headers=cli_headers)
        assert cli_forbidden.status_code == 403

        # 7. Superadmin desactiva al cliente y verifica bloqueo de login
        patch_res = client.patch(
            f"/api/v1/admin/users/{client_id}",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert patch_res.status_code == 200
        blocked_login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "client.test@vektor.local",
                "password": "Password123!",
            },
        )
        assert blocked_login.status_code == 403
    finally:
        _cleanup_test_users()