import pandas as pd
from datetime import datetime

FINANCIAL_STATEMENTS = {
    "Cuenta de Resultados": {
        "Ingresos Totales": [
            "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet",
            "Revenue", "InterestRevenueExpenseNet", "InterestAndSimilarIncome"
        ],
        "Coste de los bienes vendidos": [
            "CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold", "CostOfSales"
        ],
        "Beneficio Bruto": ["GrossProfit"],
        "Gastos de Venta, Generales y Administrativos": [
            "SellingGeneralAndAdministrativeExpense", "GeneralAndAdministrativeExpense", "SellingAndMarketingExpense",
            "AdministrativeExpense", "SellingGeneralAndAdministrativeExpenses"
        ],
        "Investigación y Desarrollo": ["ResearchAndDevelopmentExpense"],
        "Depreciación y Amortización": [
            "DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation",
            "AmortizationOfIntangibleAssets", "DepreciationAndAmortisationExpense"
        ],
        "Otros Gastos Operativos": ["OtherOperatingIncomeExpenseNet", "OperatingCostsAndExpenses"],
        "Gastos Operativos Totales": ["OperatingExpenses"],
        "Beneficio Operativo": ["OperatingIncomeLoss", "ProfitLossFromOperatingActivities"],
        "Ingresos por Intereses": ["InvestmentIncomeInterest", "InterestIncomeExpenseNet", "InterestIncomeOperating", "FinanceIncome"],
        "Gastos por Intereses": ["InterestExpense", "InterestExpenseDebt", "InterestExpenseNet", "FinanceCosts"],
        "Ganancias (Pérdidas) Cambiarias": ["ForeignCurrencyTransactionGainLossBeforeTax"],
        "Ingresos (Gastos) No Operativos": ["OtherNonoperatingIncomeExpense", "NonoperatingIncomeExpense", "GainLossOnInvestments"],
        "Beneficio antes de Impuestos": [
            "IncomeLossFromContinuingOperationsBeforeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
            "IncomeLossFromContinuingOperationsBeforeTaxesDomestic",
            "ProfitLossBeforeTax"
        ],
        "Gasto por Impuesto a las Ganancias": ["IncomeTaxExpenseBenefit", "CurrentIncomeTaxExpenseBenefit", "IncomeTaxExpenseContinuingOperations"],
        "Beneficio Neto": ["NetIncomeLoss", "ProfitLoss", "ProfitLossAttributableToOwnersOfParent"],
        "BPA Básico": ["EarningsPerShareBasic", "BasicEarningsLossPerShare"],
        "BPA Diluido": ["EarningsPerShareDiluted", "DilutedEarningsLossPerShare"],
        "Acciones en Circulación (Básicas)": [
            "WeightedAverageNumberOfSharesOutstandingBasic",
            "WeightedAverageShares",
            "EntityCommonStockSharesOutstanding",
            "CommonStockSharesOutstanding",
        ],
        "Acciones en Circulación (Diluidas)": [
            "WeightedAverageNumberOfDilutedSharesOutstanding",
            "AdjustedWeightedAverageShares",
            "WeightedAverageNumberOfSharesOutstandingBasic",
            "EntityCommonStockSharesOutstanding",
        ],
    },
    "Balance de Situación": {
        "Efectivo y equivalentes": [
            "CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalentsFairValueDisclosure", "CashAndCashEquivalents"
        ],
        "Inversiones a corto plazo": ["ShortTermInvestments", "AvailableForSaleSecuritiesCurrent", "OtherCurrentFinancialAssets"],
        "Cuentas por cobrar": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent", "TradeAndOtherCurrentReceivables"],
        "Inventario": ["InventoryNet", "Inventories"],
        "Gastos Pagados por Adelantado": ["PrepaidExpenseCurrent"],
        "Otros activos corrientes": ["OtherAssetsCurrent", "OtherCurrentNonfinancialAssets"],
        "Total activo corriente": ["AssetsCurrent", "CurrentAssets"],
        "Inmovilizado material neto (PP&E)": ["PropertyPlantAndEquipmentNet", "PropertyPlantAndEquipment"],
        "Activos por derecho de uso (Arrendamientos)": ["OperatingLeaseRightOfUseAsset", "RightofuseAssets"],
        "Fondo de comercio": ["Goodwill"],
        "Activos intangibles": ["IntangibleAssetsNetExcludingGoodwill", "IntangibleAssetsNet", "IntangibleAssetsOtherThanGoodwill"],
        "Inversiones a largo plazo": ["LongTermInvestments", "AvailableForSaleSecuritiesNoncurrent", "NoncurrentFinancialAssets"],
        "Otros activos no corrientes": ["OtherAssetsNoncurrent"],
        "Total activo no corriente": ["AssetsNoncurrent", "NoncurrentAssets"],
        "Total activo": ["Assets"],
        "Cuentas por pagar": ["AccountsPayableCurrent", "TradeAndOtherCurrentPayables"],
        "Gastos Acumulados": ["AccruedLiabilitiesCurrent"],
        "Deuda a corto plazo": ["ShortTermBorrowings", "LongTermDebtCurrent", "DebtCurrent", "CommercialPaper", "CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings"],
        "Arrendamientos Operativos Corrientes": ["OperatingLeaseLiabilityCurrent"],
        "Ingresos diferidos corrientes": ["ContractWithCustomerLiabilityCurrent", "DeferredRevenueCurrent"],
        "Otros pasivos corrientes": ["OtherLiabilitiesCurrent"],
        "Total pasivo corriente": ["LiabilitiesCurrent", "CurrentLiabilities"],
        "Deuda a largo plazo": ["LongTermDebtNoncurrent", "LongTermDebt", "NoncurrentBorrowings"],
        "Arrendamientos Operativos No Corrientes": ["OperatingLeaseLiabilityNoncurrent"],
        "Pasivos por Impuestos Diferidos": ["DeferredIncomeTaxLiabilitiesNet", "DeferredTaxLiabilities"],
        "Otros pasivos no corrientes": ["OtherLiabilitiesNoncurrent"],
        "Total pasivo no corriente": ["LiabilitiesNoncurrent", "NoncurrentLiabilities"],
        "Total pasivo": ["Liabilities"],
        "Capital social": ["CommonStockValue", "CommonStockIncludingAdditionalPaidInCapital", "AdditionalPaidInCapital", "IssuedCapital"],
        "Ganancias retenidas": ["RetainedEarningsAccumulatedDeficit", "RetainedEarnings"],
        "Otro resultado integral acumulado": ["AccumulatedOtherComprehensiveIncomeLossNetOfTax"],
        "Patrimonio neto": [
            "StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            "Equity", "EquityAttributableToOwnersOfParent"
        ]
    },
    "Estado de Flujo de Efectivo": {
        "Beneficio Neto (Flujo)": ["NetIncomeLoss", "ProfitLoss"],
        "Depreciación y Amortización (CFO)": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation", "AdjustmentsForDepreciationAndAmortisationExpense"],
        "Compensación basada en acciones": ["ShareBasedCompensation", "ShareBasedCompensationArrangementByShareBasedPaymentAwardOptionsGrantsInPeriodGross"],
        "Impuestos diferidos": ["DeferredIncomeTaxExpenseBenefit"],
        "Ganancia/Pérdida por venta de activos": ["GainLossOnSaleOfPropertyPlantEquipment"],
        "Cambios en cuentas por cobrar": ["IncreaseDecreaseInAccountsReceivable"],
        "Cambios en inventario": ["IncreaseDecreaseInInventories"],
        "Cambios en cuentas por pagar": ["IncreaseDecreaseInAccountsPayable"],
        "Cambios en el capital de trabajo": ["IncreaseDecreaseInOperatingCapital", "ChangeInOperatingAssetsAndLiabilities"],
        "Efectivo de Operaciones (CFO)": ["NetCashProvidedByUsedInOperatingActivities", "CashFlowsFromUsedInOperatingActivities"],
        "Gastos de capital (CapEx)": [
            "PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
            "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"
        ],
        "Adquisiciones e Inversiones": ["PaymentsToAcquireBusinessesNetOfCashAcquired", "PaymentsToAcquireInvestments", "PaymentsToAcquireAvailableForSaleSecuritiesDebt"],
        "Venta de Inversiones": ["ProceedsFromSaleOfAvailableForSaleSecuritiesDebt", "ProceedsFromMaturitiesOfInvestments"],
        "Efectivo de Inversión (CFI)": ["NetCashProvidedByUsedInInvestingActivities", "CashFlowsFromUsedInInvestingActivities"],
        "Emisión de Deuda": ["ProceedsFromIssuanceOfLongTermDebt", "ProceedsFromIssuanceOfDebt"],
        "Pago de Deuda": ["RepaymentsOfLongTermDebt", "RepaymentsOfDebt"],
        "Pago de dividendos": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock", "DividendsPaidClassifiedAsFinancingActivities"],
        "Recompra de acciones": ["PaymentsForRepurchaseOfCommonStock"],
        "Efectivo de Financiación (CFF)": ["NetCashProvidedByUsedInFinancingActivities", "CashFlowsFromUsedInFinancingActivities"],
        "Efecto del tipo de cambio": ["EffectOfExchangeRateOnCashAndCashEquivalents"],
        "Efectivo Neto Generado": ["CashAndCashEquivalentsPeriodIncreaseDecrease", "IncreaseDecreaseInCashAndCashEquivalents"],
        "Flujo de caja libre (FCF)": ["FreeCashFlow"]
    }
}

ANNUAL_FORMS = ["10-K", "10-K/A", "20-F", "20-F/A", "40-F"]
QUARTERLY_FORMS = ["10-Q", "10-K", "10-Q/A", "10-K/A", "20-F", "20-F/A", "6-K"]

SUPPORTED_XBRL_TAGS: set[str] = {
    tag
    for section in FINANCIAL_STATEMENTS.values()
    for tags in section.values()
    for tag in tags
}


def _get_taxonomy_data(raw_facts: dict) -> dict:
    facts = raw_facts.get("facts", {})
    merged: dict = {}
    if isinstance(facts.get("us-gaap"), dict) and facts["us-gaap"]:
        merged.update(facts["us-gaap"])
    elif isinstance(facts.get("ifrs-full"), dict) and facts["ifrs-full"]:
        merged.update(facts["ifrs-full"])
    if isinstance(facts.get("dei"), dict):
        for k, v in facts["dei"].items():
            if k not in merged:
                merged[k] = v
    return merged


def is_foreign_adr_filer(raw_facts: dict) -> bool:
    """
    Detecta si el emisor reporta ante la SEC como extranjero (IFRS o formularios 20-F / 40-F),
    donde las acciones en circulación suelen expresarse en ordinarias locales y no en ADRs.
    """
    facts = raw_facts.get("facts") or {}
    if isinstance(facts.get("ifrs-full"), dict) and facts["ifrs-full"]:
        return True
    us_gaap = facts.get("us-gaap") or {}
    for tag in ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "Assets", "NetIncomeLoss"):
        tag_obj = us_gaap.get(tag)
        if not isinstance(tag_obj, dict):
            continue
        for entries in (tag_obj.get("units") or {}).values():
            for entry in entries:
                form = str(entry.get("form") or "").upper()
                if form in ("20-F", "20-F/A", "40-F"):
                    return True
                if form in ("10-K", "10-K/A"):
                    return False
    return False


def normalize_historical_shares(
    shares_raw: float,
    split_factor: float,
    current_shares_mm: float,
    is_foreign_adr: bool,
) -> float:
    """
    Ajusta acciones históricas por splits y, solo en emisores extranjeros (20-F/40-F/IFRS),
    normaliza la relación ordinaria/ADR cuando supera 2.5x respecto a las acciones ADR actuales.
    """
    if shares_raw <= 0:
        return current_shares_mm
    shares = float(shares_raw) * float(split_factor or 1.0)
    if current_shares_mm > 0:
        if is_foreign_adr and shares > (current_shares_mm * 2.5):
            adr_ratio = round(shares / current_shares_mm)
            return (shares / adr_ratio) if adr_ratio >= 2 else current_shares_mm
        if shares < (current_shares_mm * 0.15):
            return current_shares_mm
    return shares


def detect_reporting_currency(raw_facts: dict) -> str:
    """
    Detecta la moneda original en la que están expresados los estados financieros de SEC EDGAR
    (ej. 'USD' para empresas estadounidenses/MELI, 'ARS' para BMA, 'BRL' para PBR/NU).
    """
    gaap_data = _get_taxonomy_data(raw_facts)
    probe_tags = (
        "Assets",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "InterestRevenueExpenseNet",
        "NetIncomeLoss",
        "ProfitLoss",
        "CashAndCashEquivalentsAtCarryingValue",
    )
    for tag in probe_tags:
        tag_obj = gaap_data.get(tag)
        if isinstance(tag_obj, dict):
            units_keys = list((tag_obj.get("units") or {}).keys())
            if "USD" in units_keys:
                return "USD"
            for uk in units_keys:
                if isinstance(uk, str) and len(uk) == 3 and uk.isalpha():
                    return uk.upper()
    return "USD"


def extract_annual_metrics(raw_facts: dict) -> list:
    gaap_data = _get_taxonomy_data(raw_facts)
    yf_annual_fb: dict[str, dict[str, float]] = raw_facts.get("_yf_fallback", {}).get("annual", {})

    if not gaap_data and not yf_annual_fb:
        raise ValueError("No se encontraron datos contables en SEC ni en el respaldo de mercado.")
    
    extracted_data = []
    current_year = datetime.now().year
    years_range = [str(y) for y in range(current_year - 6, current_year + 1)]
    
    for statement, metrics in FINANCIAL_STATEMENTS.items():
        for standard_name, possible_tags in metrics.items():
            found_tag = False
            for tag in possible_tags:
                if tag in gaap_data:
                    units_keys = list(gaap_data[tag].get("units", {}).keys())
                    if not units_keys:
                        continue
                    
                    unit_key = "USD" if "USD" in units_keys else units_keys[0]
                    units = gaap_data[tag]["units"][unit_key]
                    
                    for entry in units:
                        if entry.get("form") in ANNUAL_FORMS and entry.get("fp") == "FY":
                            if statement != "Balance de Situación" and "Acciones" not in standard_name and entry.get("start") and entry.get("end"):
                                try:
                                    d_start = datetime.strptime(entry["start"], "%Y-%m-%d")
                                    d_end = datetime.strptime(entry["end"], "%Y-%m-%d")
                                    if (d_end - d_start).days < 300:
                                        continue
                                except ValueError:
                                    pass

                            fy = str(entry.get("fy"))
                            if entry.get("end"):
                                fy_end = str(entry["end"])[:4]
                                if fy not in years_range or fy_end in years_range:
                                    fy = fy_end

                            if fy in years_range:
                                val = entry.get("val", 0.0)
                                if "BPA" not in standard_name:
                                    val = val / 1000000.0
                                
                                extracted_data.append({
                                    "Categoría": statement,
                                    "Métrica": standard_name,
                                    "Año": fy,
                                    "Valor": val,
                                    "end": str(entry.get("end") or ""),
                                    "filed": str(entry.get("filed") or ""),
                                })
                    found_tag = True
                    # Si SG&A tomó solo GeneralAndAdministrativeExpense, sumar SellingAndMarketingExpense si existe
                    if (
                        standard_name == "Gastos de Venta, Generales y Administrativos"
                        and tag == "GeneralAndAdministrativeExpense"
                        and "SellingAndMarketingExpense" in gaap_data
                    ):
                        sm_units_keys = list(gaap_data["SellingAndMarketingExpense"].get("units", {}).keys())
                        if sm_units_keys:
                            sm_uk = "USD" if "USD" in sm_units_keys else sm_units_keys[0]
                            sm_entries: dict[str, tuple[str, str, float]] = {}
                            for sm_e in gaap_data["SellingAndMarketingExpense"]["units"][sm_uk]:
                                if sm_e.get("form") in ANNUAL_FORMS and sm_e.get("fp") == "FY":
                                    sm_fy = str(sm_e.get("end") or "")[:4] or str(sm_e.get("fy"))
                                    if sm_fy in years_range:
                                        sort_k = (str(sm_e.get("end") or ""), str(sm_e.get("filed") or ""))
                                        prev_sm = sm_entries.get(sm_fy)
                                        if not prev_sm or sort_k >= (prev_sm[0], prev_sm[1]):
                                            sm_entries[sm_fy] = (sort_k[0], sort_k[1], float(sm_e.get("val", 0.0)) / 1000000.0)
                            for row_ex in extracted_data:
                                if row_ex["Métrica"] == standard_name and row_ex["Año"] in sm_entries:
                                    row_ex["Valor"] = float(row_ex["Valor"]) + sm_entries[row_ex["Año"]][2]
                    break
            
            if not found_tag:
                for y in years_range:
                    extracted_data.append({
                        "Categoría": statement,
                        "Métrica": standard_name,
                        "Año": y,
                        "Valor": 0.0,
                        "end": "",
                        "filed": "",
                    })
    
    df = pd.DataFrame(extracted_data)
    if df.empty:
        return []
    
    df = df.sort_values(by=["end", "filed"], kind="mergesort")
    df = df.drop_duplicates(subset=["Categoría", "Métrica", "Año"], keep="last")
    df_pivot = df.pivot(index=["Categoría", "Métrica"], columns="Año", values="Valor").reset_index()
    
    for y in years_range:
        if y not in df_pivot.columns:
            df_pivot[y] = 0.0
    df_pivot = df_pivot.fillna(0.0)

    # Rellenar cualquier métrica/año que haya quedado en 0.0 desde el respaldo normalizado de yfinance
    if yf_annual_fb:
        for idx, row in df_pivot.iterrows():
            m_name = str(row["Métrica"])
            fb_years = yf_annual_fb.get(m_name, {})
            if fb_years:
                for y in years_range:
                    curr_v = float(str(df_pivot.at[idx, y] or 0.0))
                    if curr_v == 0.0 and y in fb_years and fb_years[y] != 0.0:
                        df_pivot.at[idx, y] = float(fb_years[y])

    def get_val(metric, y) -> float:
        idx = df_pivot.index[df_pivot['Métrica'] == metric].tolist()
        if idx:
            try:
                return float(str(df_pivot.at[idx[0], y]))
            except (ValueError, TypeError):
                return 0.0
        return 0.0

    def set_val(metric, y, val: float):
        idx = df_pivot.index[df_pivot['Métrica'] == metric].tolist()
        if idx:
            df_pivot.at[idx[0], y] = float(val)

    def safe_div(num, den):
        if den == 0.0 or den is None:
            return 0.0
        return num / den

    # MOTOR DE CONTINGENCIA
    for y in years_range:
        if get_val("Beneficio Bruto", y) == 0.0:
            set_val("Beneficio Bruto", y, get_val("Ingresos Totales", y) - get_val("Coste de los bienes vendidos", y))
        if get_val("Gastos Operativos Totales", y) == 0.0:
            bruto_y = get_val("Beneficio Bruto", y)
            op_y = get_val("Beneficio Operativo", y)
            if bruto_y != 0.0 and op_y != 0.0:
                set_val("Gastos Operativos Totales", y, bruto_y - op_y)
            else:
                set_val(
                    "Gastos Operativos Totales",
                    y,
                    get_val("Gastos de Venta, Generales y Administrativos", y)
                    + get_val("Investigación y Desarrollo", y)
                    + get_val("Otros Gastos Operativos", y),
                )
        if get_val("Beneficio Operativo", y) == 0.0:
            set_val("Beneficio Operativo", y, get_val("Beneficio Bruto", y) - get_val("Gastos Operativos Totales", y))
        if get_val("Beneficio antes de Impuestos", y) == 0.0:
            set_val("Beneficio antes de Impuestos", y, get_val("Beneficio Operativo", y) - get_val("Gastos por Intereses", y) + get_val("Ingresos (Gastos) No Operativos", y))

        if get_val("Total pasivo corriente", y) == 0.0:
            set_val("Total pasivo corriente", y, get_val("Cuentas por pagar", y) + get_val("Deuda a corto plazo", y) + get_val("Ingresos diferidos corrientes", y) + get_val("Gastos Acumulados", y) + get_val("Otros pasivos corrientes", y))
        if get_val("Total pasivo no corriente", y) == 0.0:
            tot_pasivo = get_val("Total pasivo", y)
            pasivo_corr = get_val("Total pasivo corriente", y)
            if tot_pasivo > 0:
                set_val("Total pasivo no corriente", y, tot_pasivo - pasivo_corr)
            else:
                set_val("Total pasivo no corriente", y, get_val("Deuda a largo plazo", y) + get_val("Arrendamientos Operativos No Corrientes", y) + get_val("Pasivos por Impuestos Diferidos", y) + get_val("Otros pasivos no corrientes", y))
        if get_val("Total pasivo", y) == 0.0:
            set_val("Total pasivo", y, get_val("Total pasivo corriente", y) + get_val("Total pasivo no corriente", y))
        if get_val("Patrimonio neto", y) == 0.0:
            tot_act = get_val("Total activo", y)
            tot_pas = get_val("Total pasivo", y)
            if tot_act > 0 and tot_pas > 0:
                set_val("Patrimonio neto", y, tot_act - tot_pas)

        if get_val("Flujo de caja libre (FCF)", y) == 0.0:
            cfo = get_val("Efectivo de Operaciones (CFO)", y)
            capex = get_val("Gastos de capital (CapEx)", y)
            set_val("Flujo de caja libre (FCF)", y, cfo - capex)

    ordered_rows = []
    for cat, metrics in FINANCIAL_STATEMENTS.items():
        for metric in metrics.keys():
            row = df_pivot[(df_pivot['Categoría'] == cat) & (df_pivot['Métrica'] == metric)]
            if not row.empty:
                r_dict = row.iloc[0].to_dict()
                clean_dict = {"Categoría": r_dict["Categoría"], "Métrica": r_dict["Métrica"]}
                for y in years_range:
                    clean_dict[y] = r_dict.get(y, 0.0)
                ordered_rows.append(clean_dict)
                
                if metric == "Ingresos Totales":
                    pct_row = {"Categoría": cat, "Métrica": "% De cambio interanual", "is_pct": True, "is_sub": True}
                    for i, y in enumerate(years_range):
                        if i == 0:
                            pct_row[y] = 0.0
                        else:
                            prev = get_val(metric, years_range[i-1])
                            curr = get_val(metric, y)
                            pct_row[y] = 0.0 if curr == 0.0 else safe_div(curr - prev, prev) * 100
                    ordered_rows.append(pct_row)

                if metric == "Beneficio Bruto":
                    pct_row = {"Categoría": cat, "Métrica": "% Márgenes brutos", "is_pct": True, "is_sub": True}
                    for y in years_range:
                        pct_row[y] = safe_div(get_val(metric, y), get_val("Ingresos Totales", y)) * 100
                    ordered_rows.append(pct_row)

                if metric == "Beneficio Operativo":
                    pct_row = {"Categoría": cat, "Métrica": "% Márgenes operativos", "is_pct": True, "is_sub": True}
                    for y in years_range:
                        pct_row[y] = safe_div(get_val(metric, y), get_val("Ingresos Totales", y)) * 100
                    ordered_rows.append(pct_row)
                    
                if metric == "Flujo de caja libre (FCF)":
                    pct_row = {"Categoría": cat, "Métrica": "% Margen FCF", "is_pct": True, "is_sub": True}
                    for y in years_range:
                        pct_row[y] = safe_div(get_val(metric, y), get_val("Ingresos Totales", y)) * 100
                    ordered_rows.append(pct_row)

    for r in ordered_rows:
        for y in years_range:
            if y in r and isinstance(r[y], (int, float)):
                r[y] = round(r[y], 2)
            
    return ordered_rows


def extract_quarterly_metrics(raw_facts: dict) -> list:
    gaap_data = _get_taxonomy_data(raw_facts)
    yf_q_fb: dict[str, dict[str, float]] = raw_facts.get("_yf_fallback", {}).get("quarterly", {})

    if not gaap_data and not yf_q_fb:
        raise ValueError("No se encontraron datos trimestrales en SEC ni en el respaldo de mercado.")
    
    current_year = datetime.now().year
    target_years = [current_year - i for i in range(5)]
    
    found_periods = set()
    for tag_data in gaap_data.values():
        for units in tag_data.get("units", {}).values():
            for entry in units:
                fy = entry.get("fy", 0)
                fp = entry.get("fp", "")
                form = entry.get("form", "")
                
                if fy in target_years and form in QUARTERLY_FORMS:
                    if fp in ["Q1", "Q2", "Q3", "Q4", "FY"]:
                        found_periods.add(f"{fy}-{fp}")

    for p_map in yf_q_fb.values():
        for p_k in p_map.keys():
            found_periods.add(p_k)
                        
    extracted_data = []
    for statement, metrics in FINANCIAL_STATEMENTS.items():
        for standard_name, possible_tags in metrics.items():
            found_tag = False
            for tag in possible_tags:
                if tag in gaap_data:
                    units_keys = list(gaap_data[tag].get("units", {}).keys())
                    if not units_keys:
                        continue
                    
                    unit_key = "USD" if "USD" in units_keys else units_keys[0]
                    units = gaap_data[tag]["units"][unit_key]
                    
                    for entry in units:
                        fy = entry.get("fy", 0)
                        fp = entry.get("fp", "")
                        form = entry.get("form", "")
                        
                        if fy in target_years and form in QUARTERLY_FORMS:
                            if fp in ["Q1", "Q2", "Q3", "Q4", "FY"]:
                                if (
                                    statement != "Balance de Situación"
                                    and "Acciones" not in standard_name
                                    and entry.get("start")
                                    and entry.get("end")
                                ):
                                    try:
                                        d_start = datetime.strptime(entry["start"], "%Y-%m-%d")
                                        d_end = datetime.strptime(entry["end"], "%Y-%m-%d")
                                        days = (d_end - d_start).days
                                        if fp == "FY" and days < 300:
                                            continue
                                        if fp in ("Q1", "Q2", "Q3", "Q4") and (days < 65 or days > 120):
                                            continue
                                    except ValueError:
                                        pass
                                period_key = f"{fy}-{fp}"
                                val = entry.get("val", 0.0)
                                if "BPA" not in standard_name:
                                    val = val / 1000000.0
                                
                                extracted_data.append({
                                    "Categoría": statement,
                                    "Métrica": standard_name,
                                    "Periodo": period_key,
                                    "Valor": val,
                                    "end": str(entry.get("end") or ""),
                                    "filed": str(entry.get("filed") or ""),
                                })
                    found_tag = True
                    break
            
            if not found_tag:
                for fp in found_periods:
                    extracted_data.append({
                        "Categoría": statement,
                        "Métrica": standard_name,
                        "Periodo": fp,
                        "Valor": 0.0,
                        "end": "",
                        "filed": "",
                    })
                    
    df = pd.DataFrame(extracted_data)
    if df.empty:
        return []
    
    df = df.sort_values(by=["end", "filed"], kind="mergesort")
    df = df.drop_duplicates(subset=["Categoría", "Métrica", "Periodo"], keep="last")
    df_pivot = df.pivot(index=["Categoría", "Métrica"], columns="Periodo", values="Valor").reset_index()
    
    for y in target_years:
        for p in ["Q1", "Q2", "Q3", "Q4", "FY"]:
            col = f"{y}-{p}"
            if col not in df_pivot.columns:
                df_pivot[col] = 0.0
    df_pivot = df_pivot.fillna(0.0)

    if yf_q_fb:
        for idx, row in df_pivot.iterrows():
            m_name = str(row["Métrica"])
            fb_periods = yf_q_fb.get(m_name, {})
            for p_k, val in fb_periods.items():
                if p_k in df_pivot.columns:
                    curr_v = float(str(df_pivot.at[idx, p_k] or 0.0))
                    if curr_v == 0.0 and val != 0.0:
                        df_pivot.at[idx, p_k] = float(val)

    for y in target_years:
        fy_col = f"{y}-FY"
        q1_col = f"{y}-Q1"
        q2_col = f"{y}-Q2"
        q3_col = f"{y}-Q3"
        q4_col = f"{y}-Q4"
        
        for idx, row in df_pivot.iterrows():
            cat = row['Categoría']
            fy_val = float(str(df_pivot.at[idx, fy_col]))
            q1_val = float(str(df_pivot.at[idx, q1_col]))
            q2_val = float(str(df_pivot.at[idx, q2_col]))
            q3_val = float(str(df_pivot.at[idx, q3_col]))
            q4_val = float(str(df_pivot.at[idx, q4_col]))
            
            if q4_val == 0.0 and fy_val != 0.0:
                if cat == "Balance de Situación":
                    df_pivot.at[idx, q4_col] = fy_val
                elif sum(1 for v in (q1_val, q2_val, q3_val) if v != 0.0) >= 2:
                    calc_q4 = fy_val - (q1_val + q2_val + q3_val)
                    df_pivot.at[idx, q4_col] = calc_q4

    active_quarters = set()
    for fp in found_periods:
        parts = fp.split('-')
        if len(parts) == 2:
            y, q = parts
            if q == 'FY':
                active_quarters.add(f"{y}-Q4")
            else:
                active_quarters.add(fp)
                
    all_quarters = []
    for y in sorted(target_years):
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            all_quarters.append(f"{y}-{q}")
            
    periods_range = [q for q in all_quarters if q in active_quarters][-16:]

    def get_val(metric, p) -> float:
        idx = df_pivot.index[df_pivot['Métrica'] == metric].tolist()
        if idx:
            try:
                return float(str(df_pivot.at[idx[0], p]))
            except (ValueError, TypeError):
                return 0.0
        return 0.0

    def set_val(metric, p, val: float):
        idx = df_pivot.index[df_pivot['Métrica'] == metric].tolist()
        if idx:
            df_pivot.at[idx[0], p] = float(val)

    def safe_div(num, den):
        if den == 0.0 or den is None:
            return 0.0
        return num / den

    for p in periods_range:
        if get_val("Beneficio Bruto", p) == 0.0:
            set_val("Beneficio Bruto", p, get_val("Ingresos Totales", p) - get_val("Coste de los bienes vendidos", p))
        if get_val("Gastos Operativos Totales", p) == 0.0:
            bruto_p = get_val("Beneficio Bruto", p)
            op_p = get_val("Beneficio Operativo", p)
            if bruto_p != 0.0 and op_p != 0.0:
                set_val("Gastos Operativos Totales", p, bruto_p - op_p)
            else:
                set_val(
                    "Gastos Operativos Totales",
                    p,
                    get_val("Gastos de Venta, Generales y Administrativos", p)
                    + get_val("Investigación y Desarrollo", p)
                    + get_val("Otros Gastos Operativos", p),
                )
        if get_val("Beneficio Operativo", p) == 0.0:
            set_val("Beneficio Operativo", p, get_val("Beneficio Bruto", p) - get_val("Gastos Operativos Totales", p))
        if get_val("Beneficio antes de Impuestos", p) == 0.0:
            set_val("Beneficio antes de Impuestos", p, get_val("Beneficio Operativo", p) - get_val("Gastos por Intereses", p) + get_val("Ingresos (Gastos) No Operativos", p))

        if get_val("Total pasivo corriente", p) == 0.0:
            set_val("Total pasivo corriente", p, get_val("Cuentas por pagar", p) + get_val("Deuda a corto plazo", p) + get_val("Ingresos diferidos corrientes", p) + get_val("Gastos Acumulados", p) + get_val("Otros pasivos corrientes", p))
        if get_val("Total pasivo no corriente", p) == 0.0:
            tot_pasivo = get_val("Total pasivo", p)
            pasivo_corr = get_val("Total pasivo corriente", p)
            if tot_pasivo > 0:
                set_val("Total pasivo no corriente", p, tot_pasivo - pasivo_corr)
            else:
                set_val("Total pasivo no corriente", p, get_val("Deuda a largo plazo", p) + get_val("Arrendamientos Operativos No Corrientes", p) + get_val("Pasivos por Impuestos Diferidos", p) + get_val("Otros pasivos no corrientes", p))
        if get_val("Total pasivo", p) == 0.0:
            set_val("Total pasivo", p, get_val("Total pasivo corriente", p) + get_val("Total pasivo no corriente", p))
        if get_val("Patrimonio neto", p) == 0.0:
            tot_act = get_val("Total activo", p)
            tot_pas = get_val("Total pasivo", p)
            if tot_act > 0 and tot_pas > 0:
                set_val("Patrimonio neto", p, tot_act - tot_pas)

        if get_val("Flujo de caja libre (FCF)", p) == 0.0:
            cfo = get_val("Efectivo de Operaciones (CFO)", p)
            capex = get_val("Gastos de capital (CapEx)", p)
            set_val("Flujo de caja libre (FCF)", p, cfo - capex)

    ordered_rows = []
    for cat, metrics in FINANCIAL_STATEMENTS.items():
        for metric in metrics.keys():
            row = df_pivot[(df_pivot['Categoría'] == cat) & (df_pivot['Métrica'] == metric)]
            if not row.empty:
                r_dict = row.iloc[0].to_dict()
                clean_dict = {"Categoría": r_dict["Categoría"], "Métrica": r_dict["Métrica"]}
                for p in periods_range:
                    clean_dict[p] = r_dict.get(p, 0.0)
                ordered_rows.append(clean_dict)
                
                if metric == "Ingresos Totales":
                    pct_row = {"Categoría": cat, "Métrica": "% De cambio intertrimestral", "is_pct": True, "is_sub": True}
                    for p in periods_range:
                        idx_all = all_quarters.index(p)
                        if idx_all > 0:
                            prev_p = all_quarters[idx_all - 1]
                            prev = get_val(metric, prev_p)
                            curr = get_val(metric, p)
                            pct_row[p] = 0.0 if curr == 0.0 else safe_div(curr - prev, prev) * 100
                        else:
                            pct_row[p] = 0.0
                    ordered_rows.append(pct_row)

                if metric == "Beneficio Bruto":
                    pct_row = {"Categoría": cat, "Métrica": "% Márgenes brutos", "is_pct": True, "is_sub": True}
                    for p in periods_range:
                        pct_row[p] = safe_div(get_val(metric, p), get_val("Ingresos Totales", p)) * 100
                    ordered_rows.append(pct_row)

                if metric == "Beneficio Operativo":
                    pct_row = {"Categoría": cat, "Métrica": "% Márgenes operativos", "is_pct": True, "is_sub": True}
                    for p in periods_range:
                        pct_row[p] = safe_div(get_val(metric, p), get_val("Ingresos Totales", p)) * 100
                    ordered_rows.append(pct_row)
                    
                if metric == "Flujo de caja libre (FCF)":
                    pct_row = {"Categoría": cat, "Métrica": "% Margen FCF", "is_pct": True, "is_sub": True}
                    for p in periods_range:
                        pct_row[p] = safe_div(get_val(metric, p), get_val("Ingresos Totales", p)) * 100
                    ordered_rows.append(pct_row)

    for r in ordered_rows:
        for p in periods_range:
            if p in r and isinstance(r[p], (int, float)):
                r[p] = round(r[p], 2)
            
    return ordered_rows