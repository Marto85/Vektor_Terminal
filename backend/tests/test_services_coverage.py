from datetime import datetime
from unittest.mock import MagicMock, patch
import pandas as pd

from app.models.database import (
    CompanyData,
    CompanySegmentsCache,
    MacroSeriesCache,
)


def test_company_service_compact_sec_and_cache_hit(db_session):
    from app.services.company_service import _compact_sec_companyfacts, get_raw_financials

    raw = {
        "cik": "0000789019",
        "entityName": "MICROSOFT CORP",
        "facts": {
            "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": []}}},
            "us-gaap": {
                "Revenues": {"units": {"USD": [{"val": 100}]}},
                "UnusedObscureTagXYZ": {"units": {"USD": [{"val": 999}]}},
            },
        },
    }
    compacted = _compact_sec_companyfacts(raw)
    assert "Revenues" in compacted["facts"]["us-gaap"]
    assert "UnusedObscureTagXYZ" not in compacted["facts"]["us-gaap"]
    assert "dei" in compacted["facts"]

    db_session.add(
        CompanyData(
            ticker="CACHEDX",
            cik="0000000001",
            raw_facts={"_yf_fallback": {"annual": {}, "quarterly": {}}, "facts": {}},
            last_updated=datetime.utcnow(),
        )
    )
    db_session.commit()
    res = get_raw_financials("CACHEDX", db_session)
    assert "_yf_fallback" in res


def test_email_service_delivery_and_fallback(monkeypatch):
    from app.services import email_service

    monkeypatch.setattr(email_service, "RESEND_API_KEY", "")
    monkeypatch.setattr(email_service, "SMTP_HOST", "")
    assert email_service.is_email_delivery_configured() is False
    res_no_key = email_service.send_recovery_email("user@vektor.local", "User Test", "usertest", "tok123")
    assert isinstance(res_no_key, dict)

    monkeypatch.setattr(email_service, "RESEND_API_KEY", "re_test_123")
    assert email_service.is_email_delivery_configured() is True

    with patch.object(email_service, "_deliver_email", return_value={"delivered": True, "provider": "resend"}) as mock_send:
        sent_rec = email_service.send_recovery_email("user@vektor.local", "User Test", "usertest", "tok123")
        sent_ver = email_service.send_verification_email("user@vektor.local", "User Test", "usertest", "tok456")
        assert sent_rec["delivered"] is True
        assert sent_ver["delivered"] is True
        assert mock_send.call_count == 2


def test_market_overview_service_uses_cache_and_builds(db_session, monkeypatch):
    from app.services import market_overview_service

    monkeypatch.setitem(market_overview_service._OVERVIEW_CACHE, "timestamp", datetime.utcnow())
    monkeypatch.setitem(
        market_overview_service._OVERVIEW_CACHE,
        "benchmarks",
        [{"symbol": "SPY", "price": 550.0}],
    )
    monkeypatch.setitem(market_overview_service._OVERVIEW_CACHE, "news", [])

    cached = market_overview_service.build_market_overview(db_session)
    assert cached["benchmarks"][0]["symbol"] == "SPY"

    # Con caché expirado, reconstruye usando _fetch_benchmarks_and_news mockeado
    monkeypatch.setitem(market_overview_service._OVERVIEW_CACHE, "timestamp", None)
    with patch(
        "app.services.market_overview_service._fetch_benchmarks_and_news",
        return_value=([{"symbol": "QQQ", "price": 500.0}], [{"title": "Mercado sube"}]),
    ):
        fresh = market_overview_service.build_market_overview(db_session)
        assert fresh["benchmarks"][0]["symbol"] == "QQQ"
        assert fresh["news"][0]["title"] == "Mercado sube"


def test_macro_lab_service_helpers_and_cache(db_session):
    from app.services.macro_lab_service import (
        _compute_rolling_cagr,
        _summarize_series,
        build_macro_lab_payload,
    )

    months = [f"2024-{m:02d}" for m in range(1, 13)] + ["2025-01"]
    series = {m: 100.0 for m in months[:-1]}
    series["2025-01"] = 110.0
    cagr = _compute_rolling_cagr(months, series, 1)
    assert cagr["2025-01"] == 10.0

    summary = _summarize_series([10.0, 20.0, 30.0])
    assert summary["median"] == 20.0
    assert summary["min"] == 10.0
    assert summary["max"] == 30.0

    db_session.add(
        MacroSeriesCache(
            cache_key="macro_lab_v4",
            payload={"timeline": [{"date": "2026-01", "ust_10y": 4.2}], "etfs": []},
            last_updated=datetime.utcnow(),
        )
    )
    db_session.commit()
    with patch(
        "app.services.macro_lab_service._update_daily_index_pe_snapshots",
        return_value={"indices": [], "snapshot_date": "2026-01-01"},
    ):
        macro = build_macro_lab_payload(db_session)
    assert macro["timeline"][0]["ust_10y"] == 4.2


def test_peers_service_group_stats_and_manual_comparison(db_session):
    from app.services.peers_service import (
        _compute_group_stats,
        _discover_peer_tickers,
        build_manual_comparison,
    )

    discovered = _discover_peer_tickers("MSFT", "Technology", "Software - Infrastructure")
    assert isinstance(discovered, list) and len(discovered) > 0

    rows = [
        {"ticker": "A", "pe_ltm": 10.0, "ev_ebitda_ltm": 8.0},
        {"ticker": "B", "pe_ltm": 20.0, "ev_ebitda_ltm": 12.0},
    ]
    avg_out, med_out = _compute_group_stats(rows, ["pe_ltm", "ev_ebitda_ltm"])
    assert med_out["pe_ltm"] == 15.0
    assert avg_out["ev_ebitda_ltm"] == 10.0

    with patch(
        "app.services.peers_service._extract_comparable_row",
        side_effect=[
            {"ticker": "MSFT", "pe_ltm": 25.0},
            {"ticker": "AAPL", "pe_ltm": 30.0},
        ],
    ):
        comp = build_manual_comparison(["MSFT", "AAPL"], db_session)
        assert len(comp["companies"]) == 2
        assert comp["group_med"]["pe_ltm"] == 27.5


def test_thesis_service_helpers_and_custom_segments(db_session):
    from app.services.thesis_service import (
        _format_market_cap_label,
        _humanize_xbrl_member,
        _is_geographic_axis,
        reset_custom_segments,
        save_custom_segments,
    )

    assert "Cloud" in _humanize_xbrl_member("IntelligentCloudMember")
    assert _is_geographic_axis("StatementGeographicalAxis", ["US", "EMEA"]) is True
    assert _format_market_cap_label(500_000.0) is not None

    saved = save_custom_segments(
        db_session,
        "TESTX",
        [{"name": "Software", "revenue_mm": 100.0}],
        [],
        "Clientes empresariales B2B",
    )
    assert saved["is_custom"] is True
    row = db_session.query(CompanySegmentsCache).filter(CompanySegmentsCache.ticker == "TESTX").first()
    assert row is not None

    with patch("app.services.thesis_service.build_investment_thesis_onepager", return_value={"ticker": "TESTX"}):
        reset_res = reset_custom_segments(db_session, "TESTX")
        assert reset_res["ticker"] == "TESTX"


def test_valuation_service_reit_routing_and_split_factors():
    from app.services.valuation_service import (
        _compute_split_factors_by_year,
        _detect_sector_profile,
    )

    reit_routing = _detect_sector_profile({"sector": "Real Estate", "industry": "REIT - Retail"})
    assert reit_routing["profile"] == "reit"

    tk = MagicMock()
    tk.splits = pd.Series(
        [2.0],
        index=pd.to_datetime(["2024-06-10"]),
    )
    factors = _compute_split_factors_by_year(tk, ["2022", "2023", "2024", "2025"])
    assert factors["2022"] == 2.0
    assert factors["2023"] == 2.0
    assert factors["2024"] == 1.0
    assert factors["2025"] == 1.0
