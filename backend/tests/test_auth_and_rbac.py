from app.core.config import VEKTOR_ADMIN_EMAIL, VEKTOR_ADMIN_PASSWORD


def test_login_superadmin_and_rbac_user_lifecycle(api_client):
    client = api_client
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
        pass


def test_registration_modes_closed_and_invite(api_client, monkeypatch):
    from app.core import config
    from app.services import auth_service

    client = api_client

    # 1. Modo closed en producción sin código de invitación
    monkeypatch.setattr(config, "VEKTOR_ENV", "production")
    monkeypatch.setattr(config, "VEKTOR_INVITE_CODE", "")
    assert config.get_registration_mode() == "closed"
    prov_closed = client.get("/api/v1/auth/providers").json()
    assert prov_closed["registration_mode"] == "closed"
    res_closed = client.post(
        "/api/v1/auth/register",
        json={
            "username": "stranger99",
            "email": "stranger99@vektor.local",
            "full_name": "Stranger",
            "password": "Password123!",
        },
    )
    assert res_closed.status_code == 403

    # 2. Modo invite con código requerido
    monkeypatch.setattr(config, "VEKTOR_INVITE_CODE", "amigos-2026")
    monkeypatch.setattr(auth_service, "VEKTOR_INVITE_CODE", "amigos-2026")
    assert config.get_registration_mode() == "invite"
    res_bad_code = client.post(
        "/api/v1/auth/register",
        json={
            "username": "amigo99",
            "email": "amigo99@vektor.local",
            "full_name": "Amigo",
            "password": "Password123!",
            "invite_code": "wrong",
        },
    )
    assert res_bad_code.status_code == 403


def test_malformed_non_numeric_jwt_sub_returns_401(api_client):
    import jwt
    from app.core.config import JWT_ALGORITHM, VEKTOR_SECRET_KEY

    bad_token = jwt.encode({"sub": "not-an-integer", "role": "client"}, VEKTOR_SECRET_KEY, algorithm=JWT_ALGORITHM)
    res = api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bad_token}"})
    assert res.status_code == 401


def test_password_over_72_bytes_returns_400_instead_of_500(api_client):
    res = api_client.post(
        "/api/v1/auth/register",
        json={
            "username": "longpassuser",
            "email": "longpass@vektor.local",
            "full_name": "Long Pass",
            "password": "A" * 80,
        },
    )
    assert res.status_code == 400


def test_verify_email_endpoint_and_auth_rate_limit(api_client, db_session, monkeypatch):
    from datetime import datetime, timedelta
    from app.api import auth_routes
    from app.models.database import EmailVerificationToken, User
    from app.services.auth_service import _hash_reset_token, hash_password

    # 1. Verificación de email con token válido e inválido
    u = User(
        username="verifyme",
        email="verifyme@vektor.local",
        full_name="Verify User",
        hashed_password=hash_password("Password123!"),
        auth_provider="local",
        role="client",
        is_active=True,
        email_verified=False,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)

    db_session.add(
        EmailVerificationToken(
            user_id=u.id,
            token_hash=_hash_reset_token("tok-valid-1234567890"),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            used=False,
        )
    )
    db_session.commit()

    bad_res = api_client.post("/api/v1/auth/verify-email", json={"token": "tok-wrong-1234567890"})
    assert bad_res.status_code == 400

    ok_res = api_client.post("/api/v1/auth/verify-email", json={"token": "tok-valid-1234567890"})
    assert ok_res.status_code == 200
    db_session.refresh(u)
    assert u.email_verified is True

    # 2. Rate limit en /login devuelve 429 al superar umbral (max_calls=20)
    auth_routes._AUTH_RATE_BUCKETS.clear()
    for i in range(20):
        r = api_client.post(
            "/api/v1/auth/login",
            json={"email": f"nonexistent{i}@vektor.local", "password": "wrong"},
        )
        assert r.status_code == 401
    blocked = api_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent21@vektor.local", "password": "wrong"},
    )
    assert blocked.status_code == 429


def test_rate_limit_blocks_spoofed_xff_by_subject_and_purges_expired_unverified(api_client, db_session, monkeypatch):
    from datetime import datetime, timedelta
    from app.api import auth_routes
    from app.core import config
    from app.models.database import EmailVerificationToken, User
    from app.services import auth_service

    # 1. Spoofing de X-Forwarded-For con distintas IPs no esquiva el límite por usuario
    auth_routes._AUTH_RATE_BUCKETS.clear()
    for i in range(20):
        r = api_client.post(
            "/api/v1/auth/login",
            headers={"X-Forwarded-For": f"198.51.100.{i + 1}, 127.0.0.1"},
            json={"email": "target.user@vektor.local", "password": "wrong"},
        )
        assert r.status_code == 401
    blocked = api_client.post(
        "/api/v1/auth/login",
        headers={"X-Forwarded-For": "203.0.113.99, 127.0.0.1"},
        json={"email": "target.user@vektor.local", "password": "wrong"},
    )
    assert blocked.status_code == 429

    # 2. Cuenta no verificada con token expirado se reemplaza al re-registrarse
    stale_user = User(
        username="staleuser",
        email="stale@vektor.local",
        full_name="Stale User",
        hashed_password=auth_service.hash_password("Password123!"),
        auth_provider="local",
        role="client",
        is_active=True,
        email_verified=False,
    )
    db_session.add(stale_user)
    db_session.commit()
    db_session.refresh(stale_user)
    db_session.add(
        EmailVerificationToken(
            user_id=stale_user.id,
            token_hash=auth_service._hash_reset_token("expired-token-123456"),
            expires_at=datetime.utcnow() - timedelta(hours=2),
            used=False,
        )
    )
    db_session.commit()

    monkeypatch.setattr(config, "VEKTOR_INVITE_CODE", "amigos-2026")
    monkeypatch.setattr(auth_service, "VEKTOR_INVITE_CODE", "amigos-2026")
    monkeypatch.setattr(auth_service, "is_email_verification_required", lambda: False)
    auth_routes._AUTH_RATE_BUCKETS.clear()

    re_reg = api_client.post(
        "/api/v1/auth/register",
        json={
            "username": "freshuser",
            "email": "stale@vektor.local",
            "full_name": "Fresh User",
            "password": "Password123!",
            "invite_code": "amigos-2026",
        },
    )
    assert re_reg.status_code == 200
    assert re_reg.json()["user"]["username"] == "freshuser"