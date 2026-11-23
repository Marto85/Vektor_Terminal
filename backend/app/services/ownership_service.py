from datetime import datetime, timedelta
import json
import math
from typing import Any
import urllib.request
import xml.etree.ElementTree as ET
import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.database import CompanyData, CompanyOwnershipCache, is_sqlite
from app.core.yf_client import get_cached_market_snapshot, SEC_HEADERS

OWNERSHIP_CACHE_TTL = timedelta(hours=12)


def _clean_num(val: Any, decimals: int = 2) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, decimals)
    except (TypeError, ValueError):
        return None


def _clean_date_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    return s[:10] if len(s) >= 10 else s


def _normalize_major_holders(df: Any, info: dict[str, Any]) -> dict[str, Any]:
    insiders_pct = _clean_num((info.get("heldPercentInsiders") or 0) * 100.0, 2) if info.get("heldPercentInsiders") is not None else None
    institutions_pct = _clean_num((info.get("heldPercentInstitutions") or 0) * 100.0, 2) if info.get("heldPercentInstitutions") is not None else None
    inst_float_pct: float | None = None
    institutions_count: int | None = None

    if isinstance(df, pd.DataFrame) and not df.empty:
        if "Value" in df.columns:
            for idx, row in df.iterrows():
                key = str(idx).strip().lower()
                raw_v = row["Value"]
                num_v = _clean_num(raw_v, 4)
                if num_v is None:
                    continue
                if "insiderspercent" in key and insiders_pct is None:
                    insiders_pct = round(num_v * 100.0, 2) if num_v <= 1.0 else round(num_v, 2)
                elif "institutionspercent" in key and institutions_pct is None:
                    institutions_pct = round(num_v * 100.0, 2) if num_v <= 1.0 else round(num_v, 2)
                elif "institutionsfloat" in key:
                    inst_float_pct = round(num_v * 100.0, 2) if num_v <= 1.0 else round(num_v, 2)
                elif "institutionscount" in key:
                    institutions_count = int(num_v)
        elif df.shape[1] >= 2:
            for _, row in df.iterrows():
                raw_str = str(row.iloc[0]).replace("%", "").strip()
                desc = str(row.iloc[1]).lower()
                num_v = _clean_num(raw_str, 2)
                if num_v is None:
                    continue
                if "insider" in desc and insiders_pct is None:
                    insiders_pct = num_v
                elif "float" in desc and inst_float_pct is None:
                    inst_float_pct = num_v
                elif "institution" in desc and ("held" in desc or "shares" in desc) and institutions_pct is None:
                    institutions_pct = num_v
                elif "number of institutions" in desc or "institutions holding" in desc:
                    institutions_count = int(num_v)

    public_other_pct: float | None = None
    if insiders_pct is not None and institutions_pct is not None:
        rem = round(max(0.0, 100.0 - insiders_pct - institutions_pct), 2)
        public_other_pct = rem

    return {
        "insiders_pct": insiders_pct,
        "institutions_pct": institutions_pct,
        "institutions_float_pct": inst_float_pct,
        "institutions_count": institutions_count,
        "public_other_pct": public_other_pct,
    }


def _normalize_holders_table(df: Any, shares_out_raw: float, price: float, limit: int = 15) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []

    rows_out: list[dict[str, Any]] = []
    for _, row in df.head(limit).iterrows():
        holder = str(row.get("Holder") or row.get("holder") or "").strip()
        if not holder:
            continue

        shares = _clean_num(row.get("Shares") or row.get("shares"), 0)
        date_rep = _clean_date_str(row.get("Date Reported") or row.get("dateReported"))

        pct_out_raw = _clean_num(row.get("pctHeld") or row.get("% Out"), 4)
        pct_out: float | None = None
        if pct_out_raw is not None:
            pct_out = round(pct_out_raw * 100.0, 2) if abs(pct_out_raw) <= 1.0 else round(pct_out_raw, 2)
        elif shares is not None and shares_out_raw > 0:
            pct_out = round((shares / shares_out_raw) * 100.0, 2)

        val_raw = _clean_num(row.get("Value") or row.get("value"), 2)
        value_mm: float | None = None
        if val_raw is not None and val_raw > 0:
            value_mm = round(val_raw / 1_000_000.0, 2)
        elif shares is not None and price > 0:
            value_mm = round((shares * price) / 1_000_000.0, 2)

        pct_chg_raw = _clean_num(row.get("pctChange") or row.get("% Change"), 4)
        pct_change: float | None = None
        if pct_chg_raw is not None:
            pct_change = round(pct_chg_raw * 100.0, 2) if abs(pct_chg_raw) <= 5.0 else round(pct_chg_raw, 2)

        rows_out.append({
            "holder": holder,
            "date_reported": date_rep,
            "shares": int(shares) if shares is not None else None,
            "pct_out": pct_out,
            "value_mm": value_mm,
            "pct_change": pct_change,
        })

    return rows_out


def _classify_insider_tx(tx_text: str) -> str:
    low = tx_text.lower()
    if any(k in low for k in ["purchase", "buy", "open market acquisition", "acquis", "(p)"]):
        return "buy"
    if any(k in low for k in ["sale", "sell", "disposition", "(s)"]):
        return "sell"
    return "other"


def _summarize_insider_tx_list(txs: list[dict[str, Any]]) -> dict[str, Any]:
    buy_count = 0
    sell_count = 0
    other_count = 0
    buy_val_total = 0.0
    sell_val_total = 0.0

    for tx in txs:
        kind = tx.get("kind") or "other"
        val = tx.get("value_usd") or 0.0
        if kind == "buy":
            buy_count += 1
            if val > 0:
                buy_val_total += float(val)
        elif kind == "sell":
            sell_count += 1
            if val > 0:
                sell_val_total += float(val)
        else:
            other_count += 1

    buy_mm = round(buy_val_total / 1_000_000.0, 2)
    sell_mm = round(sell_val_total / 1_000_000.0, 2)
    net_mm = round(buy_mm - sell_mm, 2)

    if buy_count > sell_count and net_mm > 0:
        sentiment = "bullish"
    elif sell_count > buy_count * 2 and sell_mm > 5.0:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    return {
        "total_transactions": len(txs),
        "buy_count": buy_count,
        "sell_count": sell_count,
        "other_count": other_count,
        "buy_value_mm": buy_mm,
        "sell_value_mm": sell_mm,
        "net_value_mm": net_mm,
        "sentiment": sentiment,
    }


def _normalize_insider_transactions(df: Any, limit: int = 30) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return [], _summarize_insider_tx_list([])

    txs: list[dict[str, Any]] = []
    for _, row in df.head(limit).iterrows():
        insider = str(row.get("Insider") or row.get("insider") or "").strip()
        if not insider:
            continue

        position = str(row.get("Position") or row.get("position") or "").strip()
        tx_desc = str(row.get("Transaction") or row.get("Text") or row.get("transaction") or "").strip()
        ownership_type = str(row.get("Ownership") or row.get("ownership") or "D").strip()
        start_date = _clean_date_str(row.get("Start Date") or row.get("startDate"))

        shares_val = _clean_num(row.get("Shares") or row.get("shares"), 0)
        value_raw = _clean_num(row.get("Value") or row.get("value"), 2)
        tx_kind = _classify_insider_tx(tx_desc)

        txs.append({
            "date": start_date,
            "insider": insider,
            "position": position or "Directivo / Ejecutivo",
            "transaction": tx_desc or "Operación Form 4",
            "kind": tx_kind,
            "ownership": ownership_type,
            "shares": int(abs(shares_val)) if shares_val is not None else None,
            "value_usd": round(abs(value_raw), 2) if value_raw is not None else None,
        })

    return txs, _summarize_insider_tx_list(txs)


def _fetch_sec_ownership_fallback(
    cik: str | None, price: float, limit_form4: int = 12
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Respaldo directo desde SEC EDGAR (`submissions/CIK.json`) cuando Yahoo Finance
    bloquea `institutional_holders` e `insider_transactions`:
    - Parsea los XML públicos de los últimos formularios `4` (transacciones de ejecutivos/directores).
    - Extrae las presentaciones institucionales `SC 13D` / `SC 13G` recientes (> 5% de propiedad).
    """
    if not cik:
        return [], []

    cik_padded = str(cik).strip().zfill(10)
    cik_int = str(int(cik_padded))
    sub_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"

    try:
        req = urllib.request.Request(sub_url, headers=SEC_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return [], []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    primary_descs = recent.get("primaryDocDescription", [])

    form4_candidates: list[tuple[str, str, str]] = []
    inst_13dg_rows: list[dict[str, Any]] = []

    for i, form in enumerate(forms):
        f_upper = str(form or "").upper()
        f_date = str(dates[i] if i < len(dates) else "")
        acc_clean = str(accessions[i] if i < len(accessions) else "").replace("-", "")
        doc_raw = str(primary_docs[i] if i < len(primary_docs) else "")
        doc_xml = doc_raw.split("/")[-1] if "/" in doc_raw else doc_raw

        if f_upper == "4" and acc_clean and doc_xml.lower().endswith(".xml") and len(form4_candidates) < limit_form4:
            form4_candidates.append((f_date, acc_clean, doc_xml))
        elif f_upper.startswith(("SC 13D", "SC 13G", "SCHEDULE 13D", "SCHEDULE 13G")) and len(inst_13dg_rows) < 10:
            desc = str(primary_descs[i] if i < len(primary_descs) else "").strip()
            label = f"Tenedor Institucional (>5%) · {f_upper}" + (f" ({desc})" if desc and desc.upper() != f_upper else "")
            inst_13dg_rows.append({
                "holder": label,
                "date_reported": f_date,
                "shares": None,
                "pct_out": None,
                "value_mm": None,
                "pct_change": None,
            })

    sec_txs: list[dict[str, Any]] = []
    tx_code_labels = {
        "P": "Compra en mercado abierto (Form 4 · P)",
        "S": "Venta en mercado abierto (Form 4 · S)",
        "A": "Adjudicación / Grant (Form 4 · A)",
        "M": "Ejercicio de opciones (Form 4 · M)",
        "F": "Retención fiscal de acciones (Form 4 · F)",
        "G": "Donación / Transferencia (Form 4 · G)",
    }

    for f_date, acc_clean, doc_xml in form4_candidates:
        xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{doc_xml}"
        try:
            req_xml = urllib.request.Request(xml_url, headers=SEC_HEADERS)
            with urllib.request.urlopen(req_xml, timeout=5) as resp_xml:
                xml_bytes = resp_xml.read()
            root = ET.fromstring(xml_bytes)
        except Exception:
            continue

        owner_name = (root.findtext(".//reportingOwner/reportingOwnerId/rptOwnerName") or "").strip()
        if not owner_name:
            continue
        owner_title = (root.findtext(".//reportingOwner/reportingOwnerRelationship/officerTitle") or "").strip()
        is_director = (root.findtext(".//reportingOwner/reportingOwnerRelationship/isDirector") or "").strip() in ("1", "true")
        position = owner_title or ("Director" if is_director else "Ejecutivo / Insider SEC")

        for tx_el in root.findall(".//nonDerivativeTable/nonDerivativeTransaction"):
            tx_date = (tx_el.findtext(".//transactionDate/value") or f_date).strip()[:10]
            tx_code = (tx_el.findtext(".//transactionCoding/transactionCode") or "").strip().upper()
            shares_val = _clean_num(tx_el.findtext(".//transactionAmounts/transactionShares/value"), 0)
            px_val = _clean_num(tx_el.findtext(".//transactionAmounts/transactionPricePerShare/value"), 2)
            acq_disp = (tx_el.findtext(".//transactionAmounts/transactionAcquiredDisposedCode/value") or "").strip().upper()
            own_nature = (tx_el.findtext(".//ownershipNature/directOrIndirectOwnership/value") or "D").strip().upper()

            if tx_code == "P":
                kind = "buy"
            elif tx_code == "S":
                kind = "sell"
            elif acq_disp == "D" and tx_code not in ("F", "G"):
                kind = "sell"
            else:
                kind = "other"

            eff_px = px_val if (px_val is not None and px_val > 0) else (price if price > 0 else 0.0)
            val_usd = round(abs(shares_val) * eff_px, 2) if (shares_val is not None and eff_px > 0) else None

            sec_txs.append({
                "date": tx_date,
                "insider": owner_name.title(),
                "position": position,
                "transaction": tx_code_labels.get(tx_code, f"Operación SEC Form 4 ({tx_code or acq_disp or 'N/D'})"),
                "kind": kind,
                "ownership": own_nature or "D",
                "shares": int(abs(shares_val)) if shares_val is not None else None,
                "value_usd": val_usd,
            })

    return inst_13dg_rows, sec_txs[:30]


def build_ownership_and_insiders_report(ticker_symbol: str, db: Session) -> dict[str, Any]:
    """
    Construye y cachea (TTL 12h) el reporte de Propiedad Institucional (13F / 13D-13G),
    Fondos Mutuos y Operaciones de Insiders (Form 4) con respaldo directo desde SEC EDGAR.
    """
    sym = ticker_symbol.upper().strip()
    now = datetime.utcnow()

    cached_row = (
        db.query(CompanyOwnershipCache)
        .filter(CompanyOwnershipCache.ticker == sym)
        .first()
    )
    if cached_row is not None:
        updated_at: Any = cached_row.last_updated
        payload_cached: Any = cached_row.ownership_data
        if isinstance(updated_at, datetime) and isinstance(payload_cached, dict):
            has_data = bool(payload_cached.get("institutional_holders")) or bool(payload_cached.get("insider_transactions"))
            if has_data and (now - updated_at) < OWNERSHIP_CACHE_TTL:
                return payload_cached

    snapshot = get_cached_market_snapshot(sym, db)
    raw_info = snapshot.get("info")
    info: dict[str, Any] = raw_info if isinstance(raw_info, dict) else {}
    raw_sec_fb = snapshot.get("sec_fundamentals")
    sec_fb: dict[str, Any] = raw_sec_fb if isinstance(raw_sec_fb, dict) else {}
    price = float(snapshot.get("price") or 0.0)
    shares_out_raw = float(info.get("sharesOutstanding") or 0.0)
    if shares_out_raw <= 0 and sec_fb.get("shares_out_mm"):
        shares_out_raw = float(sec_fb["shares_out_mm"]) * 1_000_000.0

    tk = yf.Ticker(sym)
    try:
        major_df = tk.major_holders
    except Exception:
        major_df = None

    try:
        inst_df = tk.institutional_holders
    except Exception:
        inst_df = None

    try:
        mf_df = tk.mutualfund_holders
    except Exception:
        mf_df = None

    try:
        insider_df = tk.insider_transactions
    except Exception:
        insider_df = None

    major_summary = _normalize_major_holders(major_df, info)
    institutional_holders = _normalize_holders_table(inst_df, shares_out_raw, price, limit=15)
    mutualfund_holders = _normalize_holders_table(mf_df, shares_out_raw, price, limit=10)
    insider_txs, insider_summary = _normalize_insider_transactions(insider_df, limit=30)

    if not institutional_holders or not insider_txs:
        company_row = db.query(CompanyData).filter(CompanyData.ticker == sym).first()
        cik_str = str(company_row.cik) if (company_row is not None and company_row.cik is not None) else None
        sec_inst, sec_txs = _fetch_sec_ownership_fallback(cik_str, price)
        if not institutional_holders and sec_inst:
            institutional_holders = sec_inst
        if not insider_txs and sec_txs:
            insider_txs = sec_txs
            insider_summary = _summarize_insider_tx_list(insider_txs)

    report: dict[str, Any] = {
        "ticker": sym,
        "company_name": str(info.get("longName") or info.get("shortName") or sec_fb.get("entity_name") or sym),
        "current_price": round(price, 2),
        "shares_out_mm": round(shares_out_raw / 1_000_000.0, 2) if shares_out_raw > 0 else None,
        "as_of": now.strftime("%Y-%m-%d %H:%M UTC"),
        "major_holders": major_summary,
        "institutional_holders": institutional_holders,
        "mutualfund_holders": mutualfund_holders,
        "insider_transactions": insider_txs,
        "insider_summary": insider_summary,
    }

    try:
        insert_fn = sqlite_insert if is_sqlite else pg_insert
        stmt = insert_fn(CompanyOwnershipCache).values(
            ticker=sym,
            ownership_data=report,
            last_updated=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker"],
            set_={"ownership_data": report, "last_updated": now},
        )
        db.execute(stmt)
        db.commit()
    except Exception:
        db.rollback()

    return report