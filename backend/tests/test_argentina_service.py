from unittest.mock import patch


def test_argentina_overview_brechas_and_news_parsing(monkeypatch):
    from app.services import argentina_service

    monkeypatch.setitem(argentina_service._OVERVIEW_CACHE, "ts", None)
    monkeypatch.setitem(argentina_service._OVERVIEW_CACHE, "payload", None)

    sample_rss = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
      <channel>
        <item>
          <title>Sube el Riesgo Pais tras datos fiscales</title>
          <link>https://www.infobae.com/economia/nota-1</link>
          <description>&lt;p&gt;El indice retrocedio 20 pb.&lt;/p&gt;</description>
          <pubDate>Thu, 26 Nov 2026 10:00:00 GMT</pubDate>
          <media:content url="https://www.infobae.com/img1.jpg" />
        </item>
      </channel>
    </rss>"""

    class FakeResp:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            return None

    with (
        patch.object(
            argentina_service,
            "_fetch_dolares_snapshot",
            return_value={
                "mayorista": {"venta": 1000.0},
                "oficial": {"venta": 1040.0},
                "bolsa": {"promedio": 1150.0, "venta": 1155.0},
                "contadoconliqui": {"venta": 1200.0, "promedio": 1195.0},
            },
        ),
        patch.object(
            argentina_service,
            "_fetch_riesgo_pais_snapshot",
            return_value={"valor": 750.0, "change_pb": -15.0, "fecha": "2026-11-26"},
        ),
        patch.object(
            argentina_service,
            "_fetch_merval_usd",
            return_value={"value_usd": 1850.0, "change_pct": 1.4, "value_ars": 2220000.0},
        ),
        patch.object(
            argentina_service,
            "_fetch_single_sovereign_bond",
            side_effect=lambda cfg, mep: {
                "ticker": cfg["ticker"],
                "series_id": f"bond_{cfg['ticker']}",
                "name": cfg["name"],
                "law": cfg["law"],
                "maturity": cfg["maturity"],
                "coupon_pct": cfg["coupon_pct"],
                "price_usd": 68.5,
                "parity_pct": 68.5,
                "change_pct": 0.9,
                "source": "mock",
            },
        ),
        patch("app.services.argentina_service.requests.get", return_value=FakeResp(sample_rss)),
    ):
        res = argentina_service.build_argentina_overview()

    assert res["cards"]["mep"]["brecha_pct"] == 15.0
    assert res["cards"]["ccl"]["brecha_pct"] == 20.0
    assert res["cards"]["riesgo_pais"]["value"] == 750.0
    assert res["cards"]["merval_usd"]["value"] == 1850.0
    assert len(res["sovereign_bonds"]) == 10
    assert res["news"][0]["title"] == "Sube el Riesgo Pais tras datos fiscales"
    assert res["news"][0]["image_url"] == "https://www.infobae.com/img1.jpg"


def test_argentina_series_candlestick_flags_and_endpoints(api_client):
    from app.services import argentina_service
    from app.core.config import VEKTOR_ADMIN_EMAIL, VEKTOR_ADMIN_PASSWORD

    with patch.object(
        argentina_service,
        "_fetch_argentinadatos_fx_series",
        return_value=[{"date": "2026-11-20", "value": 1150.0}, {"date": "2026-11-25", "value": 1160.0}],
    ):
        s_mep = argentina_service.get_argentina_series("fx_mep", "3m")
        assert s_mep["supports_candlestick"] is False
        assert len(s_mep["points"]) == 2

    adm = api_client.post(
        "/api/v1/auth/login",
        json={"email": VEKTOR_ADMIN_EMAIL, "password": VEKTOR_ADMIN_PASSWORD},
    )
    headers = {"Authorization": f"Bearer {adm.json()['access_token']}"}
    with patch("app.services.argentina_service.get_argentina_series", return_value={"series_id": "riesgo_pais", "points": []}):
        r = api_client.get("/api/v1/argentina/series/riesgo_pais?range=1y", headers=headers)
        assert r.status_code == 200


def test_argentina_macro_and_social_overrides_rbac(api_client):
    from app.services import argentina_service
    from app.core.config import VEKTOR_ADMIN_EMAIL, VEKTOR_ADMIN_PASSWORD

    # Macro series parsing desde datos.gob.ar
    with patch.object(
        argentina_service,
        "_fetch_json",
        return_value={"data": [["2026-09-01", 0.035], ["2026-10-01", 0.028]]},
    ):
        s_ipc = argentina_service.get_argentina_series("ipc_mensual", "1y")
        assert s_ipc["supports_candlestick"] is False
        assert s_ipc["unit"] == "%"
        assert s_ipc["points"][-1]["value"] == 2.8

    # Login superadmin y override social
    adm = api_client.post(
        "/api/v1/auth/login",
        json={"email": VEKTOR_ADMIN_EMAIL, "password": VEKTOR_ADMIN_PASSWORD},
    )
    headers = {"Authorization": f"Bearer {adm.json()['access_token']}"}

    put_res = api_client.put(
        "/api/v1/argentina/social-overrides/indec_pobreza",
        headers=headers,
        json={
            "source": "INDEC EPH Test",
            "points": [
                {"date": "2024-12-31", "value": 38.1, "note": "2° Sem 2024"},
                {"date": "2025-12-31", "value": 29.5, "note": "2° Sem 2025"},
            ],
        },
    )
    assert put_res.status_code == 200
    assert put_res.json()["is_override"] is True
    assert put_res.json()["points"][-1]["value"] == 29.5

    ser_res = api_client.get("/api/v1/argentina/series/indec_pobreza?range=3y", headers=headers)
    assert ser_res.status_code == 200
    assert ser_res.json()["points"][-1]["value"] == 29.5

    del_res = api_client.delete("/api/v1/argentina/social-overrides/indec_pobreza", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["is_override"] is False
