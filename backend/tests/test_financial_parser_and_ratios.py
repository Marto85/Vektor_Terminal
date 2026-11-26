from datetime import datetime
import pytest

from app.models.database import CompanyMarketCache
from app.services.financial_parser import extract_annual_metrics, extract_quarterly_metrics
from app.services.ratios_calculator import calculate_ratios, build_financial_health_report


def _build_synthetic_sec_facts() -> dict:
    """
    Genera hechos XBRL sintéticos (us-gaap) para los últimos 2 ejercicios fiscales cerrados
    con mejora operativa interanual (para validar Piotroski, Altman y DuPont).
    """
    curr_y = datetime.now().year - 1
    prev_y = curr_y - 1

    def annual_entries(val_prev: float, val_curr: float, is_balance: bool = False):
        items = []
        for fy, val in [(prev_y, val_prev), (curr_y, val_curr)]:
            entry = {
                "fy": fy,
                "fp": "FY",
                "form": "10-K",
                "val": val,
                "end": f"{fy}-12-31",
            }
            if not is_balance:
                entry["start"] = f"{fy}-01-01"
            items.append(entry)
        return {"units": {"USD": items}}

    return {
        "facts": {
            "us-gaap": {
                "Revenues": annual_entries(100_000_000_000, 120_000_000_000),
                "CostOfGoodsAndServicesSold": annual_entries(45_000_000_000, 50_000_000_000),
                "OperatingIncomeLoss": annual_entries(25_000_000_000, 35_000_000_000),
                "InterestExpense": annual_entries(2_000_000_000, 1_800_000_000),
                "IncomeTaxExpenseBenefit": annual_entries(4_500_000_000, 6_500_000_000),
                "NetIncomeLoss": annual_entries(18_500_000_000, 26_700_000_000),
                "DepreciationDepletionAndAmortization": annual_entries(5_000_000_000, 6_000_000_000),
                "WeightedAverageNumberOfDilutedSharesOutstanding": annual_entries(
                    1_000_000_000, 990_000_000
                ),
                # Balance
                "CashAndCashEquivalentsAtCarryingValue": annual_entries(
                    20_000_000_000, 28_000_000_000, is_balance=True
                ),
                "AccountsReceivableNetCurrent": annual_entries(
                    10_000_000_000, 11_000_000_000, is_balance=True
                ),
                "InventoryNet": annual_entries(5_000_000_000, 5_500_000_000, is_balance=True),
                "AssetsCurrent": annual_entries(40_000_000_000, 50_000_000_000, is_balance=True),
                "Assets": annual_entries(120_000_000_000, 135_000_000_000, is_balance=True),
                "AccountsPayableCurrent": annual_entries(
                    8_000_000_000, 9_000_000_000, is_balance=True
                ),
                "ShortTermBorrowings": annual_entries(
                    5_000_000_000, 4_000_000_000, is_balance=True
                ),
                "LiabilitiesCurrent": annual_entries(
                    20_000_000_000, 21_000_000_000, is_balance=True
                ),
                "LongTermDebtNoncurrent": annual_entries(
                    30_000_000_000, 25_000_000_000, is_balance=True
                ),
                "Liabilities": annual_entries(60_000_000_000, 58_000_000_000, is_balance=True),
                "RetainedEarningsAccumulatedDeficit": annual_entries(
                    45_000_000_000, 62_000_000_000, is_balance=True
                ),
                "StockholdersEquity": annual_entries(
                    60_000_000_000, 77_000_000_000, is_balance=True
                ),
                # Flujo de efectivo
                "NetCashProvidedByUsedInOperatingActivities": annual_entries(
                    24_000_000_000, 34_000_000_000
                ),
                "PaymentsToAcquirePropertyPlantAndEquipment": annual_entries(
                    8_000_000_000, 10_000_000_000
                ),
            }
        }
    }


def test_extract_annual_metrics_and_contingency_formulas():
    raw = _build_synthetic_sec_facts()
    rows = extract_annual_metrics(raw)
    curr_y = str(datetime.now().year - 1)
    prev_y = str(datetime.now().year - 2)

    by_metric = {r["Métrica"]: r for r in rows}

    # Conversión de dólares a millones USD
    assert by_metric["Ingresos Totales"][curr_y] == 120_000.0
    # Contingencia: Beneficio Bruto = Ingresos - Coste (120.000 - 50.000)
    assert by_metric["Beneficio Bruto"][curr_y] == 70_000.0
    # Contingencia: FCF = CFO - CapEx (34.000 - 10.000)
    assert by_metric["Flujo de caja libre (FCF)"][curr_y] == 24_000.0
    # Crecimiento interanual calculado automáticamente (+20%)
    assert by_metric["% De cambio interanual"][curr_y] == 20.0
    assert by_metric["Ingresos Totales"][prev_y] == 100_000.0


def test_extract_quarterly_reconstructs_q4_from_fy():
    curr_y = datetime.now().year - 1
    raw = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"fy": curr_y, "fp": "Q1", "form": "10-Q", "start": f"{curr_y}-01-01", "end": f"{curr_y}-03-31", "val": 20_000_000_000},
                            {"fy": curr_y, "fp": "Q2", "form": "10-Q", "start": f"{curr_y}-04-01", "end": f"{curr_y}-06-30", "val": 22_000_000_000},
                            # Registro YTD de 6 meses bajo fp=Q2 que debe ser ignorado
                            {"fy": curr_y, "fp": "Q2", "form": "10-Q", "start": f"{curr_y}-01-01", "end": f"{curr_y}-06-30", "val": 42_000_000_000},
                            {"fy": curr_y, "fp": "Q3", "form": "10-Q", "start": f"{curr_y}-07-01", "end": f"{curr_y}-09-30", "val": 25_000_000_000},
                            # Registro YTD de 9 meses bajo fp=Q3 que debe ser ignorado
                            {"fy": curr_y, "fp": "Q3", "form": "10-Q", "start": f"{curr_y}-01-01", "end": f"{curr_y}-09-30", "val": 67_000_000_000},
                            {"fy": curr_y, "fp": "FY", "form": "10-K", "start": f"{curr_y}-01-01", "end": f"{curr_y}-12-31", "val": 100_000_000_000},
                        ]
                    }
                }
            }
        }
    }
    rows = extract_quarterly_metrics(raw)
    rev_row = next(r for r in rows if r["Métrica"] == "Ingresos Totales")
    # Q4 debe reconstruirse como FY - (Q1 + Q2 + Q3) = 100.000 - 67.000 = 33.000 MM
    assert rev_row[f"{curr_y}-Q4"] == 33_000.0


def test_extract_quarterly_does_not_dump_fy_into_q4_without_prior_quarters():
    curr_y = datetime.now().year - 1
    raw = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"fy": curr_y, "fp": "FY", "form": "20-F", "start": f"{curr_y}-01-01", "end": f"{curr_y}-12-31", "val": 11_500_000_000},
                        ]
                    }
                }
            }
        }
    }
    rows = extract_quarterly_metrics(raw)
    rev_row = next(r for r in rows if r["Métrica"] == "Ingresos Totales")
    assert rev_row.get(f"{curr_y}-Q4", 0.0) == 0.0


def test_adr_share_normalization_only_applies_to_foreign_filers():
    from app.services.financial_parser import is_foreign_adr_filer, normalize_historical_shares

    facts_20f = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [{"form": "20-F"}]}}}}}
    facts_10k = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [{"form": "10-K"}]}}}}}

    assert is_foreign_adr_filer(facts_20f) is True
    assert is_foreign_adr_filer(facts_10k) is False

    # BMA (20-F, 10:1): 639 MM ordinarias vs 63.9 MM ADRs -> normaliza a 63.9 MM
    assert normalize_historical_shares(639.0, 1.0, 63.9, is_foreign_adr=True) == pytest.approx(63.9, abs=0.01)
    # Empresa US (10-K) con recompras fuertes: NO divide por ratio ADR
    assert normalize_historical_shares(300.0, 1.0, 100.0, is_foreign_adr=False) == 300.0


def test_ratios_and_financial_health_report_manufacturing_vs_bank(db_session):
    raw = _build_synthetic_sec_facts()
    annual_rows = extract_annual_metrics(raw)
    curr_y = datetime.now().year - 1
    years_range = [str(y) for y in range(datetime.now().year - 6, datetime.now().year + 1)]

    with_ratios = calculate_ratios(list(annual_rows), years_range)
    roe_row = next(r for r in with_ratios if r["Métrica"] == "Rentabilidad sobre capital (ROE) %")
    # ROE = 26.700 / 77.000 = 34.68%
    assert roe_row[str(curr_y)] == pytest.approx(34.68, abs=0.05)

    # Caso 1: Empresa industrial/manufacturera -> Piotroski = 9/9 y Altman Z original aplicable
    db_session.add(
        CompanyMarketCache(
            ticker="INDX",
            market_data={
                "name": "Industrial Test Corp",
                "sector": "Industrials",
                "industry": "Specialty Industrial Machinery",
                "summary_metrics": {"capital": {"market_cap": 250_000.0}},
            },
            last_updated=datetime.utcnow(),
        )
    )
    db_session.commit()

    health_ind = build_financial_health_report("INDX", annual_rows, db_session)
    assert health_ind["piotroski"]["score"] == 9
    assert health_ind["piotroski"]["applicable"] is True
    assert health_ind["altman"]["applicable"] is True
    assert health_ind["altman"]["recommended_variant"] == "z_original"
    assert health_ind["altman"]["z_original"]["score"] > 2.99

    # Caso 2: Entidad bancaria -> Altman y Piotroski marcados como no aplicables
    db_session.add(
        CompanyMarketCache(
            ticker="BANKX",
            market_data={
                "name": "Banco Test S.A.",
                "sector": "Financial Services",
                "industry": "Banks - Regional",
                "summary_metrics": {"capital": {"market_cap": 90_000.0}},
            },
            last_updated=datetime.utcnow(),
        )
    )
    db_session.commit()

    health_bank = build_financial_health_report("BANKX", annual_rows, db_session)
    assert health_bank["altman"]["applicable"] is False
    assert health_bank["piotroski"]["applicable"] is False


def test_ifrs_taxonomy_prioritized_over_stray_us_gaap_tag():
    from app.services.financial_parser import detect_reporting_currency

    curr_y = datetime.now().year - 1
    raw = {
        "facts": {
            "us-gaap": {
                "OtherAssetsCurrent": {
                    "units": {
                        "USD": [
                            {"fy": curr_y, "fp": "FY", "form": "20-F", "end": f"{curr_y}-12-31", "val": 100_000_000}
                        ]
                    }
                }
            },
            "ifrs-full": {
                "Revenue": {
                    "units": {
                        "BRL": [
                            {
                                "fy": curr_y,
                                "fp": "FY",
                                "form": "20-F",
                                "start": f"{curr_y}-01-01",
                                "end": f"{curr_y}-12-31",
                                "val": 13_400_000_000,
                            }
                        ]
                    }
                },
                "Assets": {
                    "units": {
                        "BRL": [
                            {"fy": curr_y, "fp": "FY", "form": "20-F", "end": f"{curr_y}-12-31", "val": 62_300_000_000}
                        ]
                    }
                },
            },
        }
    }

    assert detect_reporting_currency(raw) == "BRL"
    rows = extract_annual_metrics(raw)
    rev_row = next(r for r in rows if r["Métrica"] == "Ingresos Totales")
    assets_row = next(r for r in rows if r["Métrica"] == "Total activo")
    assert rev_row[str(curr_y)] == 13_400.0
    assert assets_row[str(curr_y)] == 62_300.0


def test_detect_reporting_currency_falls_back_to_yf_currency():
    from app.services.financial_parser import detect_reporting_currency

    raw = {"facts": {}, "_yf_fallback": {"currency": "CAD", "annual": {}, "quarterly": {}}}
    assert detect_reporting_currency(raw) == "CAD"


def test_sga_consolidates_ga_and_marketing_and_opex_closes_without_da():
    curr_y = datetime.now().year - 1
    raw = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {"USD": [{"fy": curr_y, "fp": "FY", "form": "10-K", "start": f"{curr_y}-01-01", "end": f"{curr_y}-12-31", "val": 100_000_000_000}]}
                },
                "CostOfRevenue": {
                    "units": {"USD": [{"fy": curr_y, "fp": "FY", "form": "10-K", "start": f"{curr_y}-01-01", "end": f"{curr_y}-12-31", "val": 30_000_000_000}]}
                },
                "GeneralAndAdministrativeExpense": {
                    "units": {"USD": [{"fy": curr_y, "fp": "FY", "form": "10-K", "start": f"{curr_y}-01-01", "end": f"{curr_y}-12-31", "val": 5_000_000_000}]}
                },
                "SellingAndMarketingExpense": {
                    "units": {"USD": [{"fy": curr_y, "fp": "FY", "form": "10-K", "start": f"{curr_y}-01-01", "end": f"{curr_y}-12-31", "val": 15_000_000_000}]}
                },
                "ResearchAndDevelopmentExpense": {
                    "units": {"USD": [{"fy": curr_y, "fp": "FY", "form": "10-K", "start": f"{curr_y}-01-01", "end": f"{curr_y}-12-31", "val": 10_000_000_000}]}
                },
                "OperatingIncomeLoss": {
                    "units": {"USD": [{"fy": curr_y, "fp": "FY", "form": "10-K", "start": f"{curr_y}-01-01", "end": f"{curr_y}-12-31", "val": 40_000_000_000}]}
                },
                "DepreciationDepletionAndAmortization": {
                    "units": {"USD": [{"fy": curr_y, "fp": "FY", "form": "10-K", "start": f"{curr_y}-01-01", "end": f"{curr_y}-12-31", "val": 8_000_000_000}]}
                },
            }
        }
    }
    rows = extract_annual_metrics(raw)
    by_m = {r["Métrica"]: r[str(curr_y)] for r in rows if not r.get("is_header")}
    assert by_m["Beneficio Bruto"] == 70_000.0
    assert by_m["Gastos de Venta, Generales y Administrativos"] == 20_000.0
    assert by_m["Gastos Operativos Totales"] == 30_000.0
    assert by_m["Beneficio Bruto"] - by_m["Gastos Operativos Totales"] == by_m["Beneficio Operativo"]


def test_52_53_week_early_january_end_date_maps_to_prior_fiscal_year():
    curr_y = datetime.now().year - 1
    next_y = curr_y + 1
    raw = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "fy": curr_y,
                                "fp": "FY",
                                "form": "10-K",
                                "start": f"{curr_y}-01-01",
                                "end": f"{next_y}-01-03",
                                "val": 12_000_000_000,
                            }
                        ]
                    }
                }
            }
        }
    }
    rows = extract_annual_metrics(raw)
    rev_row = next(r for r in rows if r["Métrica"] == "Ingresos Totales")
    assert rev_row[str(curr_y)] == 12_000.0
