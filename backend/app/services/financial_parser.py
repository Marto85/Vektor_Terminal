import pandas as pd
from datetime import datetime

FINANCIAL_STATEMENTS = {
    "Cuenta de Resultados": {
        "Ingresos Totales": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet"],
        "Coste de los bienes vendidos": ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"],
        "Beneficio Bruto": ["GrossProfit"],
        "Gastos de Venta, Generales y Administrativos": ["SellingGeneralAndAdministrativeExpense", "GeneralAndAdministrativeExpense", "SellingAndMarketingExpense"],
        "Investigación y Desarrollo": ["ResearchAndDevelopmentExpense"],
        "Depreciación y Amortización": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation", "AmortizationOfIntangibleAssets"],
        "Otros Gastos Operativos": ["OtherOperatingIncomeExpenseNet", "OperatingCostsAndExpenses"],
        "Gastos Operativos Totales": ["OperatingExpenses"],
        "Beneficio Operativo": ["OperatingIncomeLoss"],
        "Ingresos por Intereses": ["InvestmentIncomeInterest", "InterestIncomeExpenseNet", "InterestIncomeOperating"],
        "Gastos por Intereses": ["InterestExpense", "InterestExpenseDebt", "InterestExpenseNet"],
        "Ganancias (Pérdidas) Cambiarias": ["ForeignCurrencyTransactionGainLossBeforeTax"],
        "Ingresos (Gastos) No Operativos": ["OtherNonoperatingIncomeExpense", "NonoperatingIncomeExpense", "GainLossOnInvestments"],
        "Beneficio antes de Impuestos": ["IncomeLossFromContinuingOperationsBeforeTaxesExtraordinaryItemsNoncontrollingInterest", "IncomeLossFromContinuingOperationsBeforeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments", "IncomeLossFromContinuingOperationsBeforeTaxesDomestic"],
        "Gasto por Impuesto a las Ganancias": ["IncomeTaxExpenseBenefit", "CurrentIncomeTaxExpenseBenefit"],
        "Beneficio Neto": ["NetIncomeLoss", "ProfitLoss"],
        "BPA Básico": ["EarningsPerShareBasic"],
        "BPA Diluido": ["EarningsPerShareDiluted"],
        "Acciones en Circulación (Básicas)": ["WeightedAverageNumberOfSharesOutstandingBasic"],
        "Acciones en Circulación (Diluidas)": ["WeightedAverageNumberOfDilutedSharesOutstanding"]
    },
    "Balance de Situación": {
        "Efectivo y equivalentes": ["CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalentsFairValueDisclosure"],
        "Inversiones a corto plazo": ["ShortTermInvestments", "AvailableForSaleSecuritiesCurrent"],
        "Cuentas por cobrar": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
        "Inventario": ["InventoryNet"],
        "Gastos Pagados por Adelantado": ["PrepaidExpenseCurrent"],
        "Otros activos corrientes": ["OtherAssetsCurrent"],
        "Total activo corriente": ["AssetsCurrent"],
        "Inmovilizado material neto (PP&E)": ["PropertyPlantAndEquipmentNet"],
        "Activos por derecho de uso (Arrendamientos)": ["OperatingLeaseRightOfUseAsset"],
        "Fondo de comercio": ["Goodwill"],
        "Activos intangibles": ["IntangibleAssetsNetExcludingGoodwill", "IntangibleAssetsNet"],
        "Inversiones a largo plazo": ["LongTermInvestments", "AvailableForSaleSecuritiesNoncurrent"],
        "Otros activos no corrientes": ["OtherAssetsNoncurrent"],
        "Total activo no corriente": ["AssetsNoncurrent"],
        "Total activo": ["Assets"],
        "Cuentas por pagar": ["AccountsPayableCurrent"],
        "Gastos Acumulados": ["AccruedLiabilitiesCurrent"],
        "Deuda a corto plazo": ["ShortTermBorrowings", "LongTermDebtCurrent", "DebtCurrent", "CommercialPaper"],
        "Arrendamientos Operativos Corrientes": ["OperatingLeaseLiabilityCurrent"],
        "Ingresos diferidos corrientes": ["ContractWithCustomerLiabilityCurrent", "DeferredRevenueCurrent"],
        "Otros pasivos corrientes": ["OtherLiabilitiesCurrent"],
        "Total pasivo corriente": ["LiabilitiesCurrent"],
        "Deuda a largo plazo": ["LongTermDebtNoncurrent", "LongTermDebt"],
        "Arrendamientos Operativos No Corrientes": ["OperatingLeaseLiabilityNoncurrent"],
        "Pasivos por Impuestos Diferidos": ["DeferredIncomeTaxLiabilitiesNet"],
        "Otros pasivos no corrientes": ["OtherLiabilitiesNoncurrent"],
        "Total pasivo no corriente": ["LiabilitiesNoncurrent"],
        "Total pasivo": ["Liabilities"],
        "Capital social": ["CommonStockValue", "CommonStockIncludingAdditionalPaidInCapital", "AdditionalPaidInCapital"],
        "Ganancias retenidas": ["RetainedEarningsAccumulatedDeficit"],
        "Otro resultado integral acumulado": ["AccumulatedOtherComprehensiveIncomeLossNetOfTax"],
        "Patrimonio neto": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
    },
    "Estado de Flujo de Efectivo": {
        "Beneficio Neto (Flujo)": ["NetIncomeLoss"],
        "Depreciación y Amortización (CFO)": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation"],
        "Compensación basada en acciones": ["ShareBasedCompensation", "ShareBasedCompensationArrangementByShareBasedPaymentAwardOptionsGrantsInPeriodGross"],
        "Impuestos diferidos": ["DeferredIncomeTaxExpenseBenefit"],
        "Ganancia/Pérdida por venta de activos": ["GainLossOnSaleOfPropertyPlantEquipment"],
        "Cambios en cuentas por cobrar": ["IncreaseDecreaseInAccountsReceivable"],
        "Cambios en inventario": ["IncreaseDecreaseInInventories"],
        "Cambios en cuentas por pagar": ["IncreaseDecreaseInAccountsPayable"],
        "Cambios en el capital de trabajo": ["IncreaseDecreaseInOperatingCapital", "ChangeInOperatingAssetsAndLiabilities"],
        "Efectivo de Operaciones (CFO)": ["NetCashProvidedByUsedInOperatingActivities"],
        "Gastos de capital (CapEx)": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
        "Adquisiciones e Inversiones": ["PaymentsToAcquireBusinessesNetOfCashAcquired", "PaymentsToAcquireInvestments", "PaymentsToAcquireAvailableForSaleSecuritiesDebt"],
        "Venta de Inversiones": ["ProceedsFromSaleOfAvailableForSaleSecuritiesDebt", "ProceedsFromMaturitiesOfInvestments"],
        "Efectivo de Inversión (CFI)": ["NetCashProvidedByUsedInInvestingActivities"],
        "Emisión de Deuda": ["ProceedsFromIssuanceOfLongTermDebt", "ProceedsFromIssuanceOfDebt"],
        "Pago de Deuda": ["RepaymentsOfLongTermDebt", "RepaymentsOfDebt"],
        "Pago de dividendos": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
        "Recompra de acciones": ["PaymentsForRepurchaseOfCommonStock"],
        "Efectivo de Financiación (CFF)": ["NetCashProvidedByUsedInFinancingActivities"],
        "Efecto del tipo de cambio": ["EffectOfExchangeRateOnCashAndCashEquivalents"],
        "Efectivo Neto Generado": ["CashAndCashEquivalentsPeriodIncreaseDecrease"],
        "Flujo de caja libre (FCF)": ["FreeCashFlow"]
    }
}


def extract_annual_metrics(raw_facts: dict) -> list:
    if "us-gaap" not in raw_facts.get("facts", {}):
        raise ValueError("El JSON no contiene la sección 'us-gaap'.")
    
    gaap_data = raw_facts["facts"]["us-gaap"]
    
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
                    
                    unit_key = units_keys[0] 
                    units = gaap_data[tag]["units"][unit_key]
                    
                    for entry in units:
                        if entry.get("form") in ["10-K", "10-K/A"] and entry.get("fp") == "FY":
                            # Descartar comparativos trimestrales (< 300 días) incluidos dentro de algunos 10-K
                            if statement != "Balance de Situación" and entry.get("start") and entry.get("end"):
                                try:
                                    d_start = datetime.strptime(entry["start"], "%Y-%m-%d")
                                    d_end = datetime.strptime(entry["end"], "%Y-%m-%d")
                                    if (d_end - d_start).days < 300:
                                        continue
                                except ValueError:
                                    pass

                            fy = str(entry.get("fy"))
                            if fy in years_range:
                                val = entry.get("val", 0.0)
                                if "BPA" not in standard_name:
                                    val = val / 1000000.0
                                
                                extracted_data.append({
                                    "Categoría": statement,
                                    "Métrica": standard_name,
                                    "Año": fy,
                                    "Valor": val
                                })
                    found_tag = True
                    break
            
            if not found_tag:
                for y in years_range:
                    extracted_data.append({
                        "Categoría": statement,
                        "Métrica": standard_name,
                        "Año": y,
                        "Valor": 0.0
                    })
    
    df = pd.DataFrame(extracted_data)
    if df.empty:
        return []
    
    df = df.drop_duplicates(subset=["Categoría", "Métrica", "Año"], keep="last")
    df_pivot = df.pivot(index=["Categoría", "Métrica"], columns="Año", values="Valor").reset_index()
    
    for y in years_range:
        if y not in df_pivot.columns:
            df_pivot[y] = 0.0
    df_pivot = df_pivot.fillna(0.0)

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
            set_val("Gastos Operativos Totales", y, get_val("Gastos de Venta, Generales y Administrativos", y) + get_val("Investigación y Desarrollo", y) + get_val("Depreciación y Amortización", y))
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
            set_val("Patrimonio neto", y, get_val("Total activo", y) - get_val("Total pasivo", y))

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
                
                # LIMPIEZA ESTRUCTURAL: Solo enviamos columnas autorizadas
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
                            pct_row[y] = safe_div(curr - prev, prev) * 100
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
    if "us-gaap" not in raw_facts.get("facts", {}):
        raise ValueError("El JSON no contiene la sección 'us-gaap'.")
    
    gaap_data = raw_facts["facts"]["us-gaap"]
    
    current_year = datetime.now().year
    target_years = [current_year - i for i in range(5)]
    
    found_periods = set()
    for tag_data in gaap_data.values():
        for units in tag_data.get("units", {}).values():
            for entry in units:
                fy = entry.get("fy", 0)
                fp = entry.get("fp", "")
                form = entry.get("form", "")
                
                if fy in target_years and form in ["10-Q", "10-K", "10-Q/A", "10-K/A"]:
                    if fp in ["Q1", "Q2", "Q3", "Q4", "FY"]:
                        found_periods.add(f"{fy}-{fp}")
                        
    extracted_data = []
    for statement, metrics in FINANCIAL_STATEMENTS.items():
        for standard_name, possible_tags in metrics.items():
            found_tag = False
            for tag in possible_tags:
                if tag in gaap_data:
                    units_keys = list(gaap_data[tag].get("units", {}).keys())
                    if not units_keys:
                        continue
                    
                    unit_key = units_keys[0] 
                    units = gaap_data[tag]["units"][unit_key]
                    
                    for entry in units:
                        fy = entry.get("fy", 0)
                        fp = entry.get("fp", "")
                        form = entry.get("form", "")
                        
                        if fy in target_years and form in ["10-Q", "10-K", "10-Q/A", "10-K/A"]:
                            if fp in ["Q1", "Q2", "Q3", "Q4", "FY"]:
                                period_key = f"{fy}-{fp}"
                                
                                val = entry.get("val", 0.0)
                                if "BPA" not in standard_name:
                                    val = val / 1000000.0
                                
                                extracted_data.append({
                                    "Categoría": statement,
                                    "Métrica": standard_name,
                                    "Periodo": period_key,
                                    "Valor": val
                                })
                    found_tag = True
                    break
            
            if not found_tag:
                for fp in found_periods:
                    extracted_data.append({
                        "Categoría": statement,
                        "Métrica": standard_name,
                        "Periodo": fp,
                        "Valor": 0.0
                    })
                    
    df = pd.DataFrame(extracted_data)
    if df.empty:
        return []
    
    df = df.drop_duplicates(subset=["Categoría", "Métrica", "Periodo"], keep="last")
    df_pivot = df.pivot(index=["Categoría", "Métrica"], columns="Periodo", values="Valor").reset_index()
    
    for y in target_years:
        for p in ["Q1", "Q2", "Q3", "Q4", "FY"]:
            col = f"{y}-{p}"
            if col not in df_pivot.columns:
                df_pivot[col] = 0.0
    df_pivot = df_pivot.fillna(0.0)

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
                else:
                    calc_q4 = fy_val - (q1_val + q2_val + q3_val)
                    df_pivot.at[idx, q4_col] = calc_q4

    # Generamos la lista de todos los trimestres puros (sin FY)
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
            set_val("Gastos Operativos Totales", p, get_val("Gastos de Venta, Generales y Administrativos", p) + get_val("Investigación y Desarrollo", p) + get_val("Depreciación y Amortización", p))
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
            set_val("Patrimonio neto", p, get_val("Total activo", p) - get_val("Total pasivo", p))

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
                            pct_row[p] = safe_div(curr - prev, prev) * 100
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