import io
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeGuard

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_text(value: Any, fallback: str = "-") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    replacements = {
        "—": "-",
        "–": "-",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "•": "*",
        "…": "...",
        "≥": ">=",
        "≤": "<=",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def _is_number(val: Any) -> TypeGuard[int | float]:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    return not (math.isnan(val) or math.isinf(val))


def _fmt_num(val: Any, decimals: int = 2, suffix: str = "", prefix: str = "") -> str:
    if not _is_number(val):
        return "-"
    if val < 0:
        return f"({prefix}{abs(val):,.{decimals}f}{suffix})"
    return f"{prefix}{val:,.{decimals}f}{suffix}"


def _normalize_statements_by_category(statements: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Convierte la lista plana de filas contables de VektorTerminal en un mapa por categoría."""
    if isinstance(statements, dict):
        return {
            "income_statement": statements.get("income_statement", []),
            "balance_sheet": statements.get("balance_sheet", []),
            "cash_flow": statements.get("cash_flow", []),
            "ratios": statements.get("ratios", []),
        }

    grouped: Dict[str, List[Dict[str, Any]]] = {
        "income_statement": [],
        "balance_sheet": [],
        "cash_flow": [],
        "ratios": [],
    }
    if not isinstance(statements, list):
        return grouped

    cat_map = {
        "Cuenta de Resultados": "income_statement",
        "Balance de Situación": "balance_sheet",
        "Estado de Flujo de Efectivo": "cash_flow",
        "Ratios": "ratios",
    }
    meta_keys = {"Categoría", "Métrica", "metric", "is_pct", "is_sub", "is_header"}

    for row in statements:
        if not isinstance(row, dict) or row.get("is_header"):
            continue
        target_key = cat_map.get(str(row.get("Categoría", "")))
        if not target_key:
            continue
        metric_label = row.get("Métrica") or row.get("metric") or ""
        normalized_row: Dict[str, Any] = {
            "metric": str(metric_label),
            "is_pct": bool(row.get("is_pct", False)),
            "is_sub": bool(row.get("is_sub", False)),
        }
        for k, v in row.items():
            if k not in meta_keys:
                normalized_row[str(k)] = v
        grouped[target_key].append(normalized_row)

    return grouped


def _extract_market_snapshot(
    profile: Dict[str, Any],
    market: Dict[str, Any],
    valuation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Unifica métricas anidadas en summary_metrics, info de YF y valuation_report."""
    src: Dict[str, Any] = market or profile or {}
    info = _as_dict(src.get("info"))
    fx_rate = float(src.get("fx_rate") or 1.0)
    sm = _as_dict(src.get("summary_metrics"))

    cap = _as_dict(sm.get("capital_structure"))
    eff = _as_dict(sm.get("efficiency"))
    gcf = _as_dict(sm.get("growth_cashflow"))
    val = _as_dict(sm.get("valuation"))
    mkt_sec = _as_dict(sm.get("market_data"))

    val_dict = _as_dict(valuation)
    cls_dict = _as_dict(val_dict.get("classification"))

    def pick(*candidates: Any) -> Any:
        for item in candidates:
            if item is not None and item != "" and item != "-":
                return item
        return None

    total_debt_mm: Optional[float] = None
    if info.get("totalDebt") is not None:
        try:
            total_debt_mm = round((float(info["totalDebt"]) * fx_rate) / 1_000_000.0, 2)
        except (TypeError, ValueError):
            total_debt_mm = None

    total_cash_mm = pick(src.get("cash_mm"), gcf.get("total_cash_mm"))
    if total_cash_mm is None and info.get("totalCash") is not None:
        try:
            total_cash_mm = round((float(info["totalCash"]) * fx_rate) / 1_000_000.0, 2)
        except (TypeError, ValueError):
            total_cash_mm = None

    mcap_mm = pick(src.get("market_cap_mm"), cap.get("market_cap_mm"))
    fcf_ltm_mm = pick(src.get("fcf_ltm_mm"), gcf.get("fcf_ltm_mm"))
    fcf_yield_pct = pick(src.get("fcf_yield_pct"))
    if fcf_yield_pct is None and _is_number(mcap_mm) and mcap_mm > 0 and _is_number(fcf_ltm_mm):
        fcf_yield_pct = round((float(fcf_ltm_mm) / float(mcap_mm)) * 100.0, 2)

    rev_ltm_mm: Optional[float] = None
    if info.get("totalRevenue") is not None:
        try:
            rev_ltm_mm = (float(info["totalRevenue"]) * fx_rate) / 1_000_000.0
        except (TypeError, ValueError):
            rev_ltm_mm = None

    ps_ltm = pick(src.get("price_to_sales"))
    if ps_ltm is None and _is_number(mcap_mm) and _is_number(rev_ltm_mm) and rev_ltm_mm > 0:
        ps_ltm = round(float(mcap_mm) / float(rev_ltm_mm), 2)

    return {
        "sector": pick(src.get("sector"), info.get("sector"), cls_dict.get("sector")),
        "industry": pick(src.get("industry"), info.get("industry"), cls_dict.get("industry")),
        "country": pick(src.get("country"), info.get("country")),
        "exchange": pick(src.get("exchange"), info.get("exchange")),
        "price": pick(src.get("price")),
        "beta_5y": pick(mkt_sec.get("beta_5y"), info.get("beta")),
        "target_price": pick(val.get("target_price"), info.get("targetMeanPrice")),
        "market_cap_mm": mcap_mm,
        "enterprise_value_mm": pick(src.get("enterprise_value_mm"), cap.get("enterprise_value_mm")),
        "total_debt_mm": pick(src.get("total_debt_mm"), total_debt_mm),
        "cash_mm": total_cash_mm,
        "net_debt_mm": pick(src.get("net_debt_mm"), cap.get("net_debt_mm")),
        "net_debt_to_ebitda": pick(cap.get("net_debt_to_ebitda")),
        "ocf_ltm_mm": pick(gcf.get("ocf_ltm_mm")),
        "fcf_ltm_mm": fcf_ltm_mm,
        "revenue_growth_yoy_pct": pick(gcf.get("revenue_growth_yoy_pct")),
        "pe_trailing": pick(src.get("pe_trailing"), val.get("pe_ltm")),
        "pe_forward": pick(src.get("pe_forward"), val.get("pe_ntm")),
        "ev_ebitda": pick(src.get("ev_ebitda"), val.get("ev_to_ebitda_ltm")),
        "ev_sales": pick(src.get("ev_sales"), val.get("ev_to_sales_ltm")),
        "price_to_sales": ps_ltm,
        "price_to_book": pick(src.get("price_to_book"), val.get("pb_ltm")),
        "price_to_fcf": pick(src.get("price_to_fcf"), val.get("p_to_fcf_ltm")),
        "fcf_yield_pct": fcf_yield_pct,
        "dividend_yield_pct": pick(src.get("dividend_yield_pct"), val.get("dividend_yield_pct")),
        "gross_margin_pct": pick(eff.get("gross_margin_pct")),
        "roe_pct": pick(src.get("roe_pct"), eff.get("roe_pct")),
        "roa_pct": pick(eff.get("roa_pct")),
        "roic_pct": pick(src.get("roic_pct"), eff.get("roic_pct")),
        "operating_margin_pct": pick(src.get("operating_margin_pct"), eff.get("ebit_margin_pct")),
        "profit_margin_pct": pick(src.get("profit_margin_pct"), eff.get("net_margin_pct")),
    }


def _auto_fit_columns(ws: Any, min_width: int = 12, max_width: int = 46) -> None:
    for col_idx in range(1, ws.max_column + 1):
        col_letter = get_column_letter(col_idx)
        longest = min_width
        for row_idx in range(1, ws.max_row + 1):
            cell_val = ws.cell(row=row_idx, column=col_idx).value
            if cell_val is None:
                continue
            length = len(str(cell_val)) + 3
            if length > longest:
                longest = length
        ws.column_dimensions[col_letter].width = min(longest, max_width)


def _write_kv_table(
    ws: Any,
    start_row: int,
    section_title: str,
    rows: List[tuple],
    header_fill: PatternFill,
    section_fill: PatternFill,
    header_font: Font,
    section_font: Font,
    border: Border,
) -> int:
    ws.cell(row=start_row, column=1, value=section_title)
    ws.cell(row=start_row, column=1).font = section_font
    ws.cell(row=start_row, column=1).fill = section_fill
    ws.cell(row=start_row, column=2).fill = section_fill
    start_row += 1

    ws.cell(row=start_row, column=1, value="Métrica").font = header_font
    ws.cell(row=start_row, column=1).fill = header_fill
    ws.cell(row=start_row, column=2, value="Valor").font = header_font
    ws.cell(row=start_row, column=2).fill = header_fill
    ws.cell(row=start_row, column=2).alignment = Alignment(horizontal="right")
    start_row += 1

    for label, value, num_fmt in rows:
        c1 = ws.cell(row=start_row, column=1, value=label)
        c2 = ws.cell(row=start_row, column=2)
        c1.border = border
        c2.border = border
        if _is_number(value):
            c2.value = float(value)
            if num_fmt:
                c2.number_format = num_fmt
            c2.alignment = Alignment(horizontal="right")
        else:
            c2.value = "-" if value is None else str(value)
            c2.alignment = Alignment(horizontal="right")
        start_row += 1

    return start_row + 1


def _write_statement_sheet(
    wb: Workbook,
    title: str,
    statement_rows: List[Dict[str, Any]],
    header_fill: PatternFill,
    header_font: Font,
    bold_font: Font,
    border: Border,
) -> None:
    ws = wb.create_sheet(title=title)
    if not statement_rows:
        ws.cell(row=1, column=1, value="Sin datos disponibles para este período.")
        return

    skip_keys = {"metric", "Métrica", "Categoría", "is_pct", "is_sub", "is_header"}
    period_keys = sorted([k for k in statement_rows[0].keys() if k not in skip_keys])
    ws.cell(row=1, column=1, value="Concepto (US$ MM)").font = header_font
    ws.cell(row=1, column=1).fill = header_fill

    for idx, p_key in enumerate(period_keys, start=2):
        cell = ws.cell(row=1, column=idx, value=str(p_key))
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="right")

    ws.freeze_panes = "B2"

    is_ratio_sheet = title.lower() == "ratios"

    for r_idx, row in enumerate(statement_rows, start=2):
        metric_name = str(row.get("metric") or row.get("Métrica") or "")
        c_label = ws.cell(row=r_idx, column=1, value=metric_name)
        c_label.border = border
        if metric_name.startswith("Total") or "Margen" in metric_name or "Score" in metric_name:
            c_label.font = bold_font

        is_pct = (
            bool(row.get("is_pct"))
            or "%" in metric_name
            or "Margen" in metric_name
            or "ROE" in metric_name
            or "ROA" in metric_name
            or "ROIC" in metric_name
        )
        num_fmt = "0.00" if is_ratio_sheet else '#,##0.0;(#,##0.0);"-"'
        if is_pct:
            num_fmt = '0.00"%"'

        for c_idx, p_key in enumerate(period_keys, start=2):
            val = row.get(p_key)
            cell = ws.cell(row=r_idx, column=c_idx)
            cell.border = border
            cell.alignment = Alignment(horizontal="right")
            if _is_number(val):
                cell.value = float(val)
                cell.number_format = num_fmt
            else:
                cell.value = "-" if val is None else str(val)

    _auto_fit_columns(ws)


def build_company_workbook_bytes(
    ticker: str,
    period: str,
    profile: Dict[str, Any],
    market: Dict[str, Any],
    statements: Any,
    valuation: Dict[str, Any],
    ownership: Dict[str, Any],
    health: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Genera un libro Excel (.xlsx) multi-solapa con el análisis integral del emisor."""
    grouped_statements = _normalize_statements_by_category(statements)
    val_dict = _as_dict(valuation)
    health_dict = _as_dict(health)
    mkt = _extract_market_snapshot(profile, market, val_dict)

    wb = Workbook()
    ws_summary = wb.active
    assert ws_summary is not None
    ws_summary.title = "Resumen & Múltiplos"

    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    section_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    section_font = Font(name="Calibri", size=11, bold=True, color="0F172A")
    title_font = Font(name="Calibri", size=14, bold=True, color="0F172A")
    bold_font = Font(name="Calibri", size=10, bold=True)
    thin_side = Side(border_style="thin", color="CBD5E1")
    border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    company_name = profile.get("name") or ticker
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    period_label = "Anual" if period == "annual" else "Trimestral"

    ws_summary.cell(row=1, column=1, value=f"VektorTerminal — {company_name} ({ticker})").font = title_font
    ws_summary.cell(row=2, column=1, value=f"Reporte Exportado: {now_str} | Periodicidad Contable: {period_label}")

    row_cursor = 4
    row_cursor = _write_kv_table(
        ws_summary,
        row_cursor,
        "1. Perfil del Emisor y Estructura de Capital",
        [
            ("Empresa", company_name, None),
            ("Ticker", ticker, None),
            ("Sector", mkt.get("sector"), None),
            ("Industria / Rubro", mkt.get("industry"), None),
            ("País / Bolsa", f"{mkt.get('country') or '-'} / {mkt.get('exchange') or '-'}", None),
            ("Precio Actual (USD)", mkt.get("price"), "$#,##0.00"),
            ("Precio Objetivo Consenso (USD)", mkt.get("target_price"), "$#,##0.00"),
            ("Beta 5Y", mkt.get("beta_5y"), "0.00"),
            ("Market Cap (US$ MM)", mkt.get("market_cap_mm"), "#,##0.0"),
            ("Enterprise Value (US$ MM)", mkt.get("enterprise_value_mm"), "#,##0.0"),
            ("Deuda Total (US$ MM)", mkt.get("total_debt_mm"), "#,##0.0"),
            ("Caja e Inversiones CP (US$ MM)", mkt.get("cash_mm"), "#,##0.0"),
            ("Deuda Neta (US$ MM)", mkt.get("net_debt_mm"), '#,##0.0;(#,##0.0);"-"'),
            ("Deuda Neta / EBITDA", mkt.get("net_debt_to_ebitda"), '0.00"x"'),
            ("Flujo Operativo LTM (US$ MM)", mkt.get("ocf_ltm_mm"), "#,##0.0"),
            ("Free Cash Flow LTM (US$ MM)", mkt.get("fcf_ltm_mm"), "#,##0.0"),
        ],
        header_fill,
        section_fill,
        header_font,
        section_font,
        border,
    )

    row_cursor = _write_kv_table(
        ws_summary,
        row_cursor,
        "2. Múltiplos de Valoración y Rentabilidad (LTM)",
        [
            ("P/E Trailing (LTM)", mkt.get("pe_trailing"), '0.00"x"'),
            ("P/E Forward (NTM)", mkt.get("pe_forward"), '0.00"x"'),
            ("EV / EBITDA", mkt.get("ev_ebitda"), '0.00"x"'),
            ("EV / Ventas", mkt.get("ev_sales"), '0.00"x"'),
            ("Precio / Ventas (P/S)", mkt.get("price_to_sales"), '0.00"x"'),
            ("Precio / Valor Libros (P/B)", mkt.get("price_to_book"), '0.00"x"'),
            ("Precio / FCF (P/FCF)", mkt.get("price_to_fcf"), '0.00"x"'),
            ("FCF Yield (%)", mkt.get("fcf_yield_pct"), '0.00"%"'),
            ("Dividend Yield (%)", mkt.get("dividend_yield_pct"), '0.00"%"'),
            ("Crecimiento Ventas YoY (%)", mkt.get("revenue_growth_yoy_pct"), '0.00"%"'),
            ("Margen Bruto (%)", mkt.get("gross_margin_pct"), '0.00"%"'),
            ("Margen Operativo (%)", mkt.get("operating_margin_pct"), '0.00"%"'),
            ("Margen Neto (%)", mkt.get("profit_margin_pct"), '0.00"%"'),
            ("ROA (%)", mkt.get("roa_pct"), '0.00"%"'),
            ("ROE (%)", mkt.get("roe_pct"), '0.00"%"'),
            ("ROIC (%)", mkt.get("roic_pct"), '0.00"%"'),
        ],
        header_fill,
        section_fill,
        header_font,
        section_font,
        border,
    )

    piotroski = _as_dict(health_dict.get("piotroski"))
    altman = _as_dict(health_dict.get("altman"))
    if piotroski or altman:
        z_orig = _as_dict(altman.get("z_original"))
        z_dp = _as_dict(altman.get("z_double_prime"))
        row_cursor = _write_kv_table(
            ws_summary,
            row_cursor,
            "3. Salud Financiera y Solvencia (Piotroski & Altman)",
            [
                ("Piotroski F-Score (0-9)", f"{piotroski.get('score')}/9 — {piotroski.get('zone')}" if piotroski else "-", None),
                ("Altman Z-Score (1968)", f"{z_orig.get('score')} — {z_orig.get('zone')}" if z_orig else "-", None),
                ("Altman Z''-Score (Servicios/Tech)", f"{z_dp.get('score')} — {z_dp.get('zone')}" if z_dp else "-", None),
            ],
            header_fill,
            section_fill,
            header_font,
            section_font,
            border,
        )

    _auto_fit_columns(ws_summary)

    # Solapas de Estados Contables y Ratios
    _write_statement_sheet(wb, "Resultados", grouped_statements.get("income_statement", []), header_fill, header_font, bold_font, border)
    _write_statement_sheet(wb, "Balance", grouped_statements.get("balance_sheet", []), header_fill, header_font, bold_font, border)
    _write_statement_sheet(wb, "Flujo de Efectivo", grouped_statements.get("cash_flow", []), header_fill, header_font, bold_font, border)
    _write_statement_sheet(wb, "Ratios", grouped_statements.get("ratios", []), header_fill, header_font, bold_font, border)

    # Solapa 6: Valoración Histórica y Parámetros DCF / Reverse DCF
    ws_val = wb.create_sheet(title="Valoración")
    val_row = 1
    ws_val.cell(row=val_row, column=1, value="Múltiplos Históricos vs Actual (LTM) y Mediana 5Y").font = section_font
    ws_val.cell(row=val_row, column=1).fill = section_fill
    val_row += 1

    val_years = [str(y) for y in (val_dict.get("years") or [])]
    val_rows = val_dict.get("rows") or val_dict.get("historical_multiples") or []
    if val_rows:
        if "metric" in val_rows[0]:
            col_specs = [("Sección", "section"), ("Métrica", "metric"), ("Actual (LTM)", "ltm"), ("Promedio 5Y", "avg_5y"), ("Mediana 5Y", "med_5y")] + [
                (y, y) for y in val_years
            ]
            for idx, (header_label, _) in enumerate(col_specs, start=1):
                c = ws_val.cell(row=val_row, column=idx, value=header_label)
                c.font = header_font
                c.fill = header_fill
                if idx > 2:
                    c.alignment = Alignment(horizontal="right")
            val_row += 1

            for item in val_rows:
                suffix = str(item.get("suffix") or "")
                num_fmt = '0.00"x"' if suffix == "x" else ('0.00"%"' if suffix == "%" else "#,##0.00")
                for idx, (_, key) in enumerate(col_specs, start=1):
                    v = item.get(key)
                    c = ws_val.cell(row=val_row, column=idx)
                    c.border = border
                    if idx <= 2:
                        c.value = str(v or "")
                        if idx == 2:
                            c.font = bold_font
                    elif _is_number(v):
                        c.value = float(v)
                        c.number_format = num_fmt
                        c.alignment = Alignment(horizontal="right")
                    else:
                        c.value = "-" if v is None else str(v)
                        c.alignment = Alignment(horizontal="right")
                val_row += 1
        else:
            h_cols = list(val_rows[0].keys())
            for idx, col_name in enumerate(h_cols, start=1):
                c = ws_val.cell(row=val_row, column=idx, value=str(col_name))
                c.font = header_font
                c.fill = header_fill
                if idx > 1:
                    c.alignment = Alignment(horizontal="right")
            val_row += 1
            for item in val_rows:
                for idx, col_name in enumerate(h_cols, start=1):
                    v = item.get(col_name)
                    c = ws_val.cell(row=val_row, column=idx)
                    c.border = border
                    if idx == 1:
                        c.value = str(v or "")
                        c.font = bold_font
                    elif _is_number(v):
                        c.value = float(v)
                        c.number_format = '0.00"x"'
                        c.alignment = Alignment(horizontal="right")
                    else:
                        c.value = "-" if v is None else str(v)
                        c.alignment = Alignment(horizontal="right")
                val_row += 1
        val_row += 1

    sector_routing = _as_dict(val_dict.get("sector_routing"))
    dcf_inputs = _as_dict(val_dict.get("dcf_inputs"))
    fin_inputs = _as_dict(val_dict.get("financial_sector_inputs"))
    rev_dcf = _as_dict(val_dict.get("reverse_dcf"))
    h5 = _as_dict(rev_dcf.get("horizon_5y"))
    h10 = _as_dict(rev_dcf.get("horizon_10y"))

    if dcf_inputs or fin_inputs:
        is_fin = sector_routing.get("profile") == "financial"
        param_rows = [
            ("Enfoque Recomendado", sector_routing.get("primary_model") or ("Excess Return" if is_fin else "DCF 2 Etapas"), None),
            ("Ingresos Base LTM (US$ MM)", dcf_inputs.get("revenue_base_mm"), "#,##0.0"),
            ("FCF Reportado LTM (US$ MM)", dcf_inputs.get("fcf_reported_mm"), "#,##0.0"),
            ("FCF Normalizado CapEx (US$ MM)", dcf_inputs.get("fcf_adjusted_mm"), "#,##0.0"),
            ("Crecimiento Ventas Sugerido (%)", dcf_inputs.get("recommended_rev_growth_pct"), '0.00"%"'),
            ("Margen Operativo Base (%)", dcf_inputs.get("ebit_margin_pct"), '0.00"%"'),
            ("WACC Sugerido (%)", dcf_inputs.get("suggested_wacc_pct"), '0.00"%"'),
            ("Múltiplo de Salida EV/FCF", dcf_inputs.get("exit_multiple_default"), '0.0"x"'),
            ("Crecimiento Implícito Precio 5Y (%)", h5.get("implied_growth_pct"), '0.00"%"'),
            ("Crecimiento Implícito Precio 10Y (%)", h10.get("implied_growth_pct"), '0.00"%"'),
            ("Diagnóstico Expectativas Mercado", rev_dcf.get("verdict"), None),
        ]
        val_row = _write_kv_table(
            ws_val,
            val_row,
            "Parámetros Fundamentales y Expectativas Implícitas (DCF Inverso)",
            param_rows,
            header_fill,
            section_fill,
            header_font,
            section_font,
            border,
        )
    _auto_fit_columns(ws_val)

    # Solapa adicional: Reportado vs normalizado (Eventos Extraordinarios & Puente DCF)
    ws_dual = wb.create_sheet(title="Reportado vs normalizado")
    dcf_eng = _as_dict(val_dict.get("dcf_engine"))
    rep_eng = _as_dict(dcf_eng.get("reported"))
    norm_eng = _as_dict(dcf_eng.get("normalized"))
    dual_rows = [
        ("Valor Intrínseco Reportado Frío (US$/acc)", rep_eng.get("intrinsic_price"), "$#,##0.00"),
        ("Valor Intrínseco Normalizado Bis (US$/acc)", norm_eng.get("intrinsic_price"), "$#,##0.00"),
        ("Diferencia Total (US$/acc)", dcf_eng.get("total_delta_per_share"), "+$#,##0.00;-$#,##0.00;$0.00"),
        ("Margen EBIT Reportado (%)", rep_eng.get("ebit_margin_start_pct"), '0.00"%"'),
        ("Margen EBIT Normalizado Final (%)", norm_eng.get("ebit_margin_end_pct"), '0.00"%"'),
        ("CapEx Reportado Etapa 1 (%)", rep_eng.get("capex_stage1_pct"), '0.00"%"'),
        ("CapEx Normalizado (%)", norm_eng.get("capex_stage1_pct"), '0.00"%"'),
    ]
    dual_r = _write_kv_table(
        ws_dual,
        1,
        "Comparativa Reportado Frío vs Escenario Normalizado (Bis)",
        dual_rows,
        header_fill,
        section_fill,
        header_font,
        section_font,
        border,
    )
    bridge_steps = dcf_eng.get("bridge") if isinstance(dcf_eng.get("bridge"), list) else []
    if bridge_steps:
        b_headers = ["Regla", "Parámetro", "Desde", "Hasta", "Delta / acción (US$)", "Acumulado (US$)"]
        b_rows = [
            [
                s.get("title"),
                s.get("param"),
                s.get("from"),
                s.get("to"),
                s.get("delta_per_share"),
                s.get("price_after"),
            ]
            for s in bridge_steps
        ]
        _write_kv_table(
            ws_dual,
            dual_r + 1,
            "Puente Acumulativo por Ajuste",
            [(f"{r[0]} ({r[1]}: {r[2]} -> {r[3]})", r[4], "$#,##0.00") for r in b_rows],
            header_fill,
            section_fill,
            header_font,
            section_font,
            border,
        )
    _auto_fit_columns(ws_dual)

    # Solapa 7: Propiedad Institucional (13F) e Insiders (Form 4)
    ws_own = wb.create_sheet(title="Propiedad e Insiders")
    own_dict = _as_dict(ownership)
    major = _as_dict(own_dict.get("major_holders"))
    own_row = _write_kv_table(
        ws_own,
        1,
        "Estructura de Capital (SEC 13F / Form 4)",
        [
            ("Participación Institucional (%)", major.get("institutions_pct"), '0.00"%"'),
            ("Participación Insiders (%)", major.get("insiders_pct"), '0.00"%"'),
            ("Capital Flotante / Retail (%)", major.get("public_other_pct"), '0.00"%"'),
            ("Instituciones Reportantes", major.get("institutions_count"), "#,##0"),
        ],
        header_fill,
        section_fill,
        header_font,
        section_font,
        border,
    )

    ws_own.cell(row=own_row, column=1, value="Top Inversores Institucionales (13F)").font = section_font
    ws_own.cell(row=own_row, column=1).fill = section_fill
    own_row += 1

    inst_headers = ["Inversor / Gestora", "Fecha Reporte", "Acciones", "% Capital", "Valuación (US$ MM)", "Var. Trimestral (%)"]
    for idx, h in enumerate(inst_headers, start=1):
        c = ws_own.cell(row=own_row, column=idx, value=h)
        c.font = header_font
        c.fill = header_fill
        if idx > 2:
            c.alignment = Alignment(horizontal="right")
    own_row += 1

    for holder in own_dict.get("institutional_holders", [])[:15]:
        vals = [
            holder.get("holder") or "-",
            holder.get("date_reported") or "-",
            holder.get("shares"),
            holder.get("pct_out"),
            holder.get("value_mm"),
            holder.get("pct_change"),
        ]
        fmts = [None, None, "#,##0", '0.00"%"', "#,##0.0", '+0.00"%";-0.00"%";0.00"%"']
        for idx, (v, f) in enumerate(zip(vals, fmts), start=1):
            c = ws_own.cell(row=own_row, column=idx)
            c.border = border
            if _is_number(v):
                c.value = float(v)
                if f:
                    c.number_format = f
                c.alignment = Alignment(horizontal="right")
            else:
                c.value = str(v or "-")
                if idx > 2:
                    c.alignment = Alignment(horizontal="right")
        own_row += 1

    own_row += 1
    ws_own.cell(row=own_row, column=1, value="Operaciones Recientes de Insiders (Form 4)").font = section_font
    ws_own.cell(row=own_row, column=1).fill = section_fill
    own_row += 1

    ins_headers = ["Fecha", "Directivo / Ejecutivo", "Cargo", "Operación", "Acciones", "Monto (USD)"]
    for idx, h in enumerate(ins_headers, start=1):
        c = ws_own.cell(row=own_row, column=idx, value=h)
        c.font = header_font
        c.fill = header_fill
        if idx > 4:
            c.alignment = Alignment(horizontal="right")
    own_row += 1

    for tx in own_dict.get("insider_transactions", [])[:25]:
        vals = [
            tx.get("date") or "-",
            tx.get("insider") or "-",
            tx.get("position") or "-",
            tx.get("transaction") or "-",
            tx.get("shares"),
            tx.get("value_usd"),
        ]
        fmts = [None, None, None, None, "#,##0", "$#,##0"]
        for idx, (v, f) in enumerate(zip(vals, fmts), start=1):
            c = ws_own.cell(row=own_row, column=idx)
            c.border = border
            if _is_number(v):
                c.value = float(v)
                if f:
                    c.number_format = f
                c.alignment = Alignment(horizontal="right")
            else:
                c.value = str(v or "-")
                if idx > 4:
                    c.alignment = Alignment(horizontal="right")
        own_row += 1

    _auto_fit_columns(ws_own)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


class _VektorReportPDF(FPDF):
    def __init__(self, ticker: str, company_name: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.ticker = ticker
        self.company_name = company_name
        self.set_auto_page_break(auto=True, margin=14)

    def header(self):
        self.set_fill_color(15, 23, 42)
        self.rect(0, 0, 210, 18, style="F")
        self.set_xy(10, 5)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(255, 255, 255)
        self.cell(120, 8, _safe_text(f"VektorTerminal | {self.company_name} ({self.ticker})"), align="L")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(203, 213, 225)
        self.cell(70, 8, _safe_text("Informe Ejecutivo Fundamental"), align="R")
        self.ln(15)

    def footer(self):
        self.set_y(-11)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(100, 116, 139)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self.cell(130, 6, _safe_text(f"Fuente: SEC EDGAR & Yahoo Finance | Generado: {now_str}"), align="L")
        self.cell(60, 6, _safe_text(f"Pagina {self.page_no()}"), align="R")


def build_company_pdf_bytes(
    ticker: str,
    profile: Dict[str, Any],
    market: Dict[str, Any],
    statements: Any,
    valuation: Dict[str, Any],
    ownership: Dict[str, Any],
    health: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Genera un informe ejecutivo PDF vectorial con métricas, salud financiera, resultados, valoración y 13F/Form 4."""
    grouped_statements = _normalize_statements_by_category(statements)
    val_dict = _as_dict(valuation)
    health_dict = _as_dict(health)
    mkt = _extract_market_snapshot(profile, market, val_dict)

    company_name = profile.get("name") or ticker
    pdf = _VektorReportPDF(ticker=ticker, company_name=company_name)
    pdf.add_page()

    # Título y metadatos del emisor
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 7, _safe_text(f"{company_name} ({ticker})"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(71, 85, 105)
    meta_line = (
        f"Sector: {mkt.get('sector') or '-'}  |  "
        f"Industria: {mkt.get('industry') or '-'}  |  "
        f"Bolsa: {mkt.get('exchange') or '-'} ({mkt.get('country') or '-'})"
    )
    pdf.cell(0, 5.5, _safe_text(meta_line), new_x="LMARGIN", new_y="NEXT")

    desc = str(profile.get("description") or "").strip()
    if desc and not desc.startswith("(Sin traducir)"):
        short_desc = desc[:340] + ("..." if len(desc) > 340 else "")
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(0, 4.2, _safe_text(short_desc))
    pdf.ln(2.5)

    # Tarjetas KPI principales (2 filas x 4 columnas)
    kpis = [
        ("Precio / Obj. Consenso", f"{_fmt_num(mkt.get('price'), 2, prefix='$')} / {_fmt_num(mkt.get('target_price'), 2, prefix='$')}"),
        ("Market Cap", _fmt_num(mkt.get('market_cap_mm'), 1, " MM", "$")),
        ("Enterprise Value", _fmt_num(mkt.get('enterprise_value_mm'), 1, " MM", "$")),
        ("Free Cash Flow LTM", _fmt_num(mkt.get('fcf_ltm_mm'), 1, " MM", "$")),
        ("P/E LTM / Forward", f"{_fmt_num(mkt.get('pe_trailing'), 1, 'x')} / {_fmt_num(mkt.get('pe_forward'), 1, 'x')}"),
        ("EV / EBITDA", _fmt_num(mkt.get("ev_ebitda"), 2, "x")),
        ("ROE / ROIC", f"{_fmt_num(mkt.get('roe_pct'), 1, '%')} / {_fmt_num(mkt.get('roic_pct'), 1, '%')}"),
        ("Margen Op. / Neto", f"{_fmt_num(mkt.get('operating_margin_pct'), 1, '%')} / {_fmt_num(mkt.get('profit_margin_pct'), 1, '%')}"),
    ]

    box_w = 45.5
    box_h = 13.5
    start_x = 10
    start_y = pdf.get_y()
    for idx, (label, val_str) in enumerate(kpis):
        col = idx % 4
        row = idx // 4
        x = start_x + col * (box_w + 2.5)
        y = start_y + row * (box_h + 2.5)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(203, 213, 225)
        pdf.rect(x, y, box_w, box_h, style="DF")
        pdf.set_xy(x + 2, y + 1.8)
        pdf.set_font("Helvetica", "", 7.2)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(box_w - 4, 3.8, _safe_text(label), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(x + 2)
        pdf.set_font("Helvetica", "B", 9.2)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(box_w - 4, 5.8, _safe_text(val_str))

    pdf.set_y(start_y + 2 * (box_h + 2.5) + 3.5)

    def _section_header(title: str) -> None:
        pdf.set_fill_color(226, 232, 240)
        pdf.set_text_color(15, 23, 42)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.cell(0, 6.5, _safe_text(f"  {title}"), new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(1.5)

    # Salud Financiera (Piotroski F-Score y Altman Z-Score)
    piotroski = _as_dict(health_dict.get("piotroski"))
    altman = _as_dict(health_dict.get("altman"))
    if piotroski or altman:
        z_orig = _as_dict(altman.get("z_original"))
        z_dp = _as_dict(altman.get("z_double_prime"))
        pdf.set_fill_color(241, 245, 249)
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "B", 8)
        health_line = (
            f"Salud Financiera: Piotroski F-Score {piotroski.get('score', '-')}/9 ({piotroski.get('zone', '-')})  |  "
            f"Altman Z: {z_orig.get('score', '-')} / Z'': {z_dp.get('score', '-')}"
        )
        pdf.cell(0, 6, _safe_text(f"  {health_line}"), new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(3)

    # Sección 1: Evolución Financiera Anual (Líneas clave de Resultados y Flujo de Caja)
    _section_header("1. Evolucion Financiera Anual (US$ MM)")
    inc_rows = grouped_statements.get("income_statement", [])
    cf_rows = grouped_statements.get("cash_flow", [])

    target_inc_names = ("Ingresos Totales", "Beneficio Bruto", "Beneficio Operativo", "Beneficio Neto")
    target_cf_names = ("Efectivo de Operaciones (CFO)", "Gastos de capital (CapEx)", "Flujo de caja libre (FCF)")

    selected_inc = [r for r in inc_rows if str(r.get("metric", "")) in target_inc_names] or inc_rows[:4]
    selected_cf = [r for r in cf_rows if str(r.get("metric", "")) in target_cf_names] or cf_rows[:2]
    combined_rows = selected_inc + selected_cf

    if combined_rows:
        skip_keys = {"metric", "Métrica", "Categoría", "is_pct", "is_sub", "is_header"}
        periods = sorted([k for k in combined_rows[0].keys() if k not in skip_keys])[-5:]
        label_w = 72
        col_w = (190 - label_w) / max(len(periods), 1)

        pdf.set_fill_color(15, 23, 42)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(label_w, 5.8, _safe_text("Concepto (US$ MM)"), fill=True)
        for p in periods:
            pdf.cell(col_w, 5.8, _safe_text(str(p)), align="R", fill=True)
        pdf.ln()

        pdf.set_text_color(15, 23, 42)
        for idx, r in enumerate(combined_rows):
            m_name = str(r.get("metric", ""))
            is_bold_row = m_name in ("Ingresos Totales", "Beneficio Operativo", "Beneficio Neto", "Flujo de caja libre (FCF)")
            pdf.set_font("Helvetica", "B" if is_bold_row else "", 8)
            pdf.set_fill_color(248, 250, 252) if idx % 2 == 1 else pdf.set_fill_color(255, 255, 255)
            pdf.cell(label_w, 5.3, _safe_text(m_name[:42]), fill=True)
            for p in periods:
                pdf.cell(col_w, 5.3, _safe_text(_fmt_num(r.get(p), 1)), align="R", fill=True)
            pdf.ln()
        pdf.ln(3.5)

    # Sección 2: Múltiplos Históricos vs Mediana 5Y + Expectativas Implícitas
    _section_header("2. Multiplos Historicos vs Mediana 5Y y Valoracion")
    raw_val_rows = val_dict.get("rows") or val_dict.get("historical_multiples") or []
    filtered_val = [
        r for r in raw_val_rows
        if not str(r.get("section", "")).startswith("Price")
        and any(k in str(r.get("metric", "")).lower() for k in ("p/e", "ev / ebitda", "ev / ventas", "p/bv", "p/fcf", "fcf yield"))
    ][:6] or raw_val_rows[:6]

    if filtered_val:
        if "metric" in filtered_val[0]:
            val_years = sorted([str(y) for y in (val_dict.get("years") or [])])[-3:]
            col_headers = ["Metrica", "Actual", "Med. 5Y"] + val_years
            col_keys = ["metric", "ltm", "med_5y"] + val_years
            label_w = 72
            col_w = (190 - label_w) / max(len(col_keys) - 1, 1)

            pdf.set_fill_color(15, 23, 42)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(label_w, 5.8, _safe_text(col_headers[0]), fill=True)
            for h_lbl in col_headers[1:]:
                pdf.cell(col_w, 5.8, _safe_text(h_lbl), align="R", fill=True)
            pdf.ln()

            pdf.set_text_color(15, 23, 42)
            pdf.set_font("Helvetica", "", 8)
            for idx, r in enumerate(filtered_val):
                suffix = str(r.get("suffix") or "x")
                pdf.set_fill_color(248, 250, 252) if idx % 2 == 1 else pdf.set_fill_color(255, 255, 255)
                pdf.cell(label_w, 5.3, _safe_text(str(r.get("metric", ""))[:42]), fill=True)
                for k in col_keys[1:]:
                    v = r.get(k)
                    txt = _fmt_num(v, 2, suffix) if _is_number(v) else "-"
                    pdf.cell(col_w, 5.3, _safe_text(txt), align="R", fill=True)
                pdf.ln()
        else:
            h_cols = list(filtered_val[0].keys())[:6]
            label_w = 55
            col_w = (190 - label_w) / max(len(h_cols) - 1, 1)
            pdf.set_fill_color(15, 23, 42)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(label_w, 5.8, _safe_text(str(h_cols[0])), fill=True)
            for c_name in h_cols[1:]:
                pdf.cell(col_w, 5.8, _safe_text(str(c_name)), align="R", fill=True)
            pdf.ln()
            pdf.set_text_color(15, 23, 42)
            pdf.set_font("Helvetica", "", 8)
            for idx, r in enumerate(filtered_val):
                pdf.set_fill_color(248, 250, 252) if idx % 2 == 1 else pdf.set_fill_color(255, 255, 255)
                pdf.cell(label_w, 5.3, _safe_text(str(r.get(h_cols[0], ""))[:32]), fill=True)
                for c_name in h_cols[1:]:
                    val = r.get(c_name)
                    txt = _fmt_num(val, 2, "x") if _is_number(val) else "-"
                    pdf.cell(col_w, 5.3, _safe_text(txt), align="R", fill=True)
                pdf.ln()

    rev_dcf = _as_dict(val_dict.get("reverse_dcf"))
    verdict_txt = str(rev_dcf.get("verdict") or "").strip()
    if verdict_txt:
        pdf.ln(1.5)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(0, 4.2, _safe_text(f"DCF Inverso: {verdict_txt}"))
    dcf_eng_pdf = _as_dict(val_dict.get("dcf_engine"))
    rep_pdf = _as_dict(dcf_eng_pdf.get("reported"))
    norm_pdf = _as_dict(dcf_eng_pdf.get("normalized"))
    if rep_pdf.get("intrinsic_price") is not None:
        pdf.ln(1.5)
        pdf.set_font("Helvetica", "B", 8.2)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(
            0,
            5.0,
            _safe_text(
                f"Reportado vs Normalizado: Frio US$ {rep_pdf.get('intrinsic_price')} | "
                f"Normalizado US$ {norm_pdf.get('intrinsic_price')} "
                f"(Delta {dcf_eng_pdf.get('total_delta_per_share', 0):+.2f}/acc)"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
    pdf.ln(3)

    # Sección 3: Propiedad Institucional (13F) e Insiders (Form 4)
    _section_header("3. Propiedad Institucional (SEC 13F) e Insiders (Form 4)")
    own_dict = _as_dict(ownership)
    major = _as_dict(own_dict.get("major_holders"))
    ins_sum = _as_dict(own_dict.get("insider_summary"))
    summary_txt = (
        f"Institucionales: {_fmt_num(major.get('institutions_pct'), 2, '%')}  |  "
        f"Insiders: {_fmt_num(major.get('insiders_pct'), 2, '%')}  |  "
        f"Flotante/Retail: {_fmt_num(major.get('public_other_pct'), 2, '%')}  |  "
        f"Form 4 (Compras/Ventas): {ins_sum.get('buy_count', 0)} / {ins_sum.get('sell_count', 0)}"
    )
    pdf.set_font("Helvetica", "", 8.2)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 5.5, _safe_text(summary_txt), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    top_holders = own_dict.get("institutional_holders", [])[:5]
    if top_holders:
        pdf.set_fill_color(15, 23, 42)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(85, 5.8, _safe_text("Top Inversor Institucional (13F)"), fill=True)
        pdf.cell(30, 5.8, _safe_text("Fecha"), align="R", fill=True)
        pdf.cell(35, 5.8, _safe_text("% Capital"), align="R", fill=True)
        pdf.cell(40, 5.8, _safe_text("Valuacion (US$ MM)"), align="R", fill=True)
        pdf.ln()

        pdf.set_text_color(15, 23, 42)
        pdf.set_font("Helvetica", "", 8)
        for idx, h in enumerate(top_holders):
            pdf.set_fill_color(248, 250, 252) if idx % 2 == 1 else pdf.set_fill_color(255, 255, 255)
            pdf.cell(85, 5.2, _safe_text(str(h.get("holder") or "-")[:46]), fill=True)
            pdf.cell(30, 5.2, _safe_text(str(h.get("date_reported") or "-")), align="R", fill=True)
            pdf.cell(35, 5.2, _safe_text(_fmt_num(h.get("pct_out"), 2, "%")), align="R", fill=True)
            pdf.cell(40, 5.2, _safe_text(_fmt_num(h.get("value_mm"), 1)), align="R", fill=True)
            pdf.ln()

    recent_insiders = own_dict.get("insider_transactions", [])[:4]
    if recent_insiders:
        pdf.ln(2.5)
        pdf.set_fill_color(30, 41, 59)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 7.8)
        pdf.cell(24, 5.5, _safe_text("Fecha"), fill=True)
        pdf.cell(62, 5.5, _safe_text("Directivo / Insider (Form 4)"), fill=True)
        pdf.cell(44, 5.5, _safe_text("Operacion"), fill=True)
        pdf.cell(28, 5.5, _safe_text("Acciones"), align="R", fill=True)
        pdf.cell(32, 5.5, _safe_text("Monto (USD)"), align="R", fill=True)
        pdf.ln()

        pdf.set_text_color(15, 23, 42)
        pdf.set_font("Helvetica", "", 7.8)
        for idx, tx in enumerate(recent_insiders):
            pdf.set_fill_color(248, 250, 252) if idx % 2 == 1 else pdf.set_fill_color(255, 255, 255)
            pdf.cell(24, 5.0, _safe_text(str(tx.get("date") or "-")), fill=True)
            pdf.cell(62, 5.0, _safe_text(str(tx.get("insider") or "-")[:34]), fill=True)
            pdf.cell(44, 5.0, _safe_text(str(tx.get("transaction") or "-")[:24]), fill=True)
            pdf.cell(28, 5.0, _safe_text(_fmt_num(tx.get("shares"), 0)), align="R", fill=True)
            pdf.cell(32, 5.0, _safe_text(_fmt_num(tx.get("value_usd"), 0, prefix="$")), align="R", fill=True)
            pdf.ln()

    raw_pdf = pdf.output()
    if isinstance(raw_pdf, (bytes, bytearray)):
        return bytes(raw_pdf)
    return str(raw_pdf).encode("latin-1")