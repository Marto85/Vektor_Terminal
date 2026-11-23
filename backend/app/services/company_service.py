import math
from datetime import datetime, timedelta, timezone
from typing import Any
import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from app.models.database import CompanyData, is_sqlite
from app.core.sec_client import get_cik_from_ticker, get_company_facts

# Caché de 7 días para no sobrecargar las APIs
CACHE_DAYS = 7

YF_ANNUAL_MAP: dict[str, dict[str, list[str]]] = {
    "Cuenta de Resultados": {
        "Ingresos Totales": ["Total Revenue", "Operating Revenue"],
        "Coste de los bienes vendidos": ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
        "Beneficio Bruto": ["Gross Profit"],
        "Gastos de Venta, Generales y Administrativos": ["Selling General And Administration"],
        "Investigación y Desarrollo": ["Research And Development"],
        "Gastos Operativos Totales": ["Operating Expense"],
        "Beneficio Operativo": ["Operating Income", "EBIT"],
        "Ingresos por Intereses": ["Interest Income", "Interest Income Non Operating"],
        "Gastos por Intereses": ["Interest Expense", "Interest Expense Non Operating"],
        "Beneficio antes de Impuestos": ["Pretax Income"],
        "Gasto por Impuesto a las Ganancias": ["Tax Provision"],
        "Beneficio Neto": ["Net Income", "Net Income Common Stockholders"],
        "BPA Básico": ["Basic EPS"],
        "BPA Diluido": ["Diluted EPS"],
        "Acciones en Circulación (Básicas)": ["Basic Average Shares"],
        "Acciones en Circulación (Diluidas)": ["Diluted Average Shares"],
    },
    "Balance de Situación": {
        "Efectivo y equivalentes": ["Cash And Cash Equivalents"],
        "Inversiones a corto plazo": ["Other Short Term Investments"],
        "Cuentas por cobrar": ["Accounts Receivable", "Receivables"],
        "Inventario": ["Inventory"],
        "Total activo corriente": ["Current Assets"],
        "Inmovilizado material neto (PP&E)": ["Net PPE"],
        "Fondo de comercio": ["Goodwill"],
        "Activos intangibles": ["Other Intangible Assets", "Goodwill And Other Intangible Assets"],
        "Total activo no corriente": ["Total Non Current Assets"],
        "Total activo": ["Total Assets"],
        "Cuentas por pagar": ["Accounts Payable"],
        "Deuda a corto plazo": ["Current Debt", "Current Debt And Capital Lease Obligation"],
        "Total pasivo corriente": ["Current Liabilities"],
        "Deuda a largo plazo": ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
        "Total pasivo no corriente": ["Total Non Current Liabilities Net Minority Interest"],
        "Total pasivo": ["Total Liabilities Net Minority Interest"],
        "Capital social": ["Common Stock", "Capital Stock"],
        "Ganancias retenidas": ["Retained Earnings"],
        "Patrimonio neto": ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"],
    },
    "Estado de Flujo de Efectivo": {
        "Beneficio Neto (Flujo)": ["Net Income", "Net Income From Continuing Operations"],
        "Depreciación y Amortización": ["Depreciation And Amortization", "Reconciled Depreciation"],
        "Depreciación y Amortización (CFO)": ["Depreciation And Amortization", "Reconciled Depreciation"],
        "Compensación basada en acciones": ["Stock Based Compensation"],
        "Cambios en el capital de trabajo": ["Change In Working Capital"],
        "Efectivo de Operaciones (CFO)": ["Operating Cash Flow"],
        "Gastos de capital (CapEx)": ["Capital Expenditure"],
        "Pago de dividendos": ["Cash Dividends Paid"],
        "Recompra de acciones": ["Repurchase Of Capital Stock"],
        "Efectivo de Inversión (CFI)": ["Investing Cash Flow"],
        "Efectivo de Financiación (CFF)": ["Financing Cash Flow"],
        "Flujo de caja libre (FCF)": ["Free Cash Flow"],
    },
}

POSITIVE_OUTFLOW_METRICS = {
    "Gastos de capital (CapEx)",
    "Pago de dividendos",
    "Recompra de acciones",
}


def _extract_yf_statements_fallback(ticker_upper: str) -> dict[str, Any]:
    """
    Descarga los estados anuales y trimestrales normalizados desde yfinance
    y los serializa por categoría/métrica/período en millones (salvo BPA)
    para almacenarlos dentro de CompanyData en Neon/SQLite.
    """
    tk = yf.Ticker(ticker_upper)

    def parse_dfs(inc_df: Any, bal_df: Any, cf_df: Any, is_quarterly: bool) -> dict[str, dict[str, float]]:
        dfs = [df for df in (inc_df, bal_df, cf_df) if isinstance(df, pd.DataFrame) and not df.empty]
        if not dfs:
            return {}

        out: dict[str, dict[str, float]] = {}

        for _cat, metrics_map in YF_ANNUAL_MAP.items():
            for std_metric, yf_keys in metrics_map.items():
                out.setdefault(std_metric, {})
                for df in dfs:
                    matched_row: Any = None
                    for k in yf_keys:
                        if k in df.index:
                            loc_res = df.loc[k]
                            matched_row = loc_res.iloc[0] if isinstance(loc_res, pd.DataFrame) else loc_res
                            break
                    if matched_row is None:
                        continue

                    for col in df.columns:
                        raw_v: Any = matched_row[col]
                        if isinstance(raw_v, pd.Series):
                            raw_v = raw_v.iloc[0] if not raw_v.empty else None
                        if raw_v is None or pd.isna(raw_v):
                            continue
                        try:
                            val = float(raw_v)
                            if math.isnan(val) or math.isinf(val):
                                continue
                        except (TypeError, ValueError):
                            continue

                        if "BPA" not in std_metric:
                            val = val / 1_000_000.0
                        if std_metric in POSITIVE_OUTFLOW_METRICS:
                            val = abs(val)

                        dt = pd.to_datetime(col)
                        if is_quarterly:
                            q_num = (dt.month - 1) // 3 + 1
                            p_key = f"{dt.year}-Q{q_num}"
                        else:
                            p_key = str(dt.year)

                        if p_key not in out[std_metric] or out[std_metric][p_key] == 0.0:
                            out[std_metric][p_key] = round(val, 4)

        return out

    try:
        annual_fb = parse_dfs(tk.income_stmt, tk.balance_sheet, tk.cashflow, is_quarterly=False)
    except Exception:
        annual_fb = {}

    try:
        quarterly_fb = parse_dfs(
            tk.quarterly_income_stmt, tk.quarterly_balance_sheet, tk.quarterly_cashflow, is_quarterly=True
        )
    except Exception:
        quarterly_fb = {}

    return {
        "annual": annual_fb,
        "quarterly": quarterly_fb,
    }


def get_raw_financials(ticker: str, db: Session, is_quarterly: bool = False) -> dict:
    """
    Obtiene los datos financieros crudos (SEC CompanyFacts + respaldo normalizado de yfinance)
    priorizando la base de datos con TTL de 7 días y upsert atómico contra concurrencia.
    """
    ticker_upper = ticker.upper()
    db_company = db.query(CompanyData).filter(CompanyData.ticker == ticker_upper).first()
    
    if db_company:
        last_updated_val = getattr(db_company, "last_updated", None)
        raw_facts_val = getattr(db_company, "raw_facts", {})
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        
        if (
            last_updated_val
            and (now_utc - last_updated_val) < timedelta(days=CACHE_DAYS)
            and isinstance(raw_facts_val, dict)
            and "_yf_fallback" in raw_facts_val
        ):
            return raw_facts_val

    cik: str | None = None
    fetched_raw_facts: dict[str, Any] = {}
    try:
        cik = get_cik_from_ticker(ticker_upper)
        fetched_raw_facts = get_company_facts(cik) or {}
    except Exception:
        fetched_raw_facts = {}

    fetched_raw_facts["_yf_fallback"] = _extract_yf_statements_fallback(ticker_upper)
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    final_cik = cik or (getattr(db_company, "cik", None) if db_company else None)

    try:
        insert_fn = sqlite_insert if is_sqlite else pg_insert
        stmt = insert_fn(CompanyData).values(
            ticker=ticker_upper,
            cik=final_cik,
            raw_facts=fetched_raw_facts,
            last_updated=now_utc,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker"],
            set_={
                "cik": final_cik,
                "raw_facts": fetched_raw_facts,
                "last_updated": now_utc,
            },
        )
        db.execute(stmt)
        db.commit()
    except Exception:
        db.rollback()

    return fetched_raw_facts