from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Any
import re
import xml.etree.ElementTree as ET
import requests
from sqlalchemy.orm import Session

from app.core.yf_client import get_company_profile, get_cached_estimates_and_guidance
from app.models.database import CompanySegmentsCache
from app.services.company_service import get_raw_financials
from app.services.financial_parser import extract_annual_metrics, extract_quarterly_metrics
from app.services.ratios_calculator import build_financial_health_report
from app.services.valuation_service import build_valuation_report


SEC_HEADERS = {"User-Agent": "VektorTerminal research@vektorterminal.local"}

SECTOR_INDUSTRY_ES: dict[str, str] = {
    "Technology": "Tecnología",
    "Software - Infrastructure": "Software e Infraestructura",
    "Software - Application": "Software de Aplicaciones",
    "Semiconductors": "Semiconductores",
    "Semiconductor Equipment & Materials": "Equipamiento y Materiales Semiconductores",
    "Consumer Electronics": "Electrónica de Consumo",
    "Information Technology Services": "Servicios de Tecnología de la Información",
    "Communication Services": "Servicios de Comunicación",
    "Internet Content & Information": "Contenido e Información en Internet",
    "Entertainment": "Entretenimiento",
    "Telecom Services": "Servicios de Telecomunicaciones",
    "Consumer Cyclical": "Consumo Cíclico",
    "Internet Retail": "Comercio Electrónico y Retail",
    "Auto Manufacturers": "Fabricantes Automotrices",
    "Restaurants": "Restaurantes y Gastronomía",
    "Apparel Retail": "Indumentaria y Retail",
    "Consumer Defensive": "Consumo Defensivo",
    "Discount Stores": "Tiendas de Descuento",
    "Beverages - Non-Alcoholic": "Bebidas Sin Alcohol",
    "Household & Personal Products": "Productos del Hogar y Cuidado Personal",
    "Packaged Foods": "Alimentos Envasados",
    "Financial Services": "Servicios Financieros",
    "Banks - Regional": "Bancos Regionales",
    "Banks - Diversified": "Bancos Diversificados",
    "Credit Services": "Servicios de Crédito y Pagos",
    "Asset Management": "Gestión de Activos",
    "Capital Markets": "Mercados de Capitales",
    "Insurance - Diversified": "Seguros Diversificados",
    "Healthcare": "Salud",
    "Drug Manufacturers - General": "Farmacéutica General",
    "Biotechnology": "Biotecnología",
    "Medical Devices": "Dispositivos Médicos",
    "Healthcare Plans": "Planes de Salud",
    "Industrials": "Industria",
    "Aerospace & Defense": "Aeroespacial y Defensa",
    "Specialty Industrial Machinery": "Maquinaria Industrial Especializada",
    "Energy": "Energía",
    "Oil & Gas Integrated": "Petróleo y Gas Integrado",
    "Oil & Gas E&P": "Exploración y Producción de Petróleo y Gas",
    "Basic Materials": "Materiales Básicos",
    "Real Estate": "Bienes Raíces",
    "Utilities": "Servicios Públicos",
}

EXACT_TRANSLATIONS_ES: dict[str, str] = {
    "united states": "Estados Unidos",
    "us": "Estados Unidos",
    "u.s.": "Estados Unidos",
    "non us": "Internacional (Fuera de EE. UU.)",
    "non-us": "Internacional (Fuera de EE. UU.)",
    "americas": "América",
    "americas excluding united states": "Resto de América (sin EE. UU.)",
    "americas excluding estados unidos": "Resto de América (sin EE. UU.)",
    "north america": "Norteamérica",
    "latin america": "Latinoamérica",
    "south america": "Sudamérica",
    "europe": "Europa",
    "emea": "Europa, Medio Oriente y África (EMEA)",
    "europe middle east and africa": "Europa, Medio Oriente y África (EMEA)",
    "apac": "Asia-Pacífico",
    "asia pacific": "Asia-Pacífico",
    "other asia pacific": "Resto de Asia-Pacífico",
    "greater china": "Gran China",
    "mainland china": "China Continental",
    "china": "China",
    "cn": "China",
    "taiwan": "Taiwán",
    "tw": "Taiwán",
    "singapore": "Singapur",
    "sg": "Singapur",
    "hong kong": "Hong Kong",
    "hk": "Hong Kong",
    "japan": "Japón",
    "jp": "Japón",
    "south korea": "Corea del Sur",
    "korea": "Corea",
    "kr": "Corea del Sur",
    "india": "India",
    "in": "India",
    "malaysia": "Malasia",
    "my": "Malasia",
    "united kingdom": "Reino Unido",
    "uk": "Reino Unido",
    "gb": "Reino Unido",
    "germany": "Alemania",
    "de": "Alemania",
    "france": "Francia",
    "fr": "Francia",
    "canada": "Canadá",
    "ca": "Canadá",
    "brazil": "Brasil",
    "brasil": "Brasil",
    "br": "Brasil",
    "mexico": "México",
    "méxico": "México",
    "mx": "México",
    "argentina": "Argentina",
    "ar": "Argentina",
    "chile": "Chile",
    "cl": "Chile",
    "colombia": "Colombia",
    "co": "Colombia",
    "cayman islands": "Islas Caimán",
    "rest of world": "Resto del mundo",
    "rest of the world": "Resto del mundo",
    "other countries": "Otros países",
    "other": "Otros",
    "others": "Otros",
    "international": "Internacional",
    "domestic": "Mercado Local (EE. UU.)",
    "foreign": "Internacional",
    "productivity and business processes": "Productividad y Procesos de Negocio",
    "intelligent cloud": "Nube Inteligente",
    "more personal computing": "Computación Personal",
    "google services": "Servicios de Google",
    "google cloud": "Google Cloud",
    "other bets": "Otras Apuestas",
    "alphabet level activities": "Actividades Corporativas Alphabet",
    "hedging gains losses": "Resultados por Cobertura",
    "family of apps": "Familia de Aplicaciones (FoA)",
    "reality labs": "Reality Labs (RL)",
    "products": "Productos",
    "product": "Venta de Productos",
    "services": "Servicios",
    "service": "Servicios y Fintech",
    "wearables home and accessories": "Wearables, Hogar y Accesorios",
    "i phone": "iPhone",
    "i pad": "iPad",
    "dram products": "Memorias DRAM",
    "nand products": "Memorias NAND",
    "other product sales": "Otros Productos",
    "commerce": "Comercio Electrónico (Marketplace)",
    "fintech": "Servicios Financieros (Fintech)",
    "net commerce revenues": "Comercio Electrónico (Marketplace)",
    "net fintech revenues": "Servicios Financieros (Fintech)",
    "aws": "Amazon Web Services (AWS)",
    "amazon web services": "Amazon Web Services (AWS)",
}

REVENUE_LOCAL_TAGS = {
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "SalesRevenueServicesNet",
    "SalesRevenueGoodsNet",
    "InterestAndDividendIncomeOperating",
    "NoninterestIncome",
    # IFRS (20-F ADRs)
    "Revenue",
    "RevenueFromContractsWithCustomers",
    "InterestRevenueExpenseNet",
    "InterestIncomeCalculatedUsingEffectiveInterestMethod",
    "InterestAndSimilarIncome",
    "FeeAndCommissionIncome",
}

OPINC_LOCAL_TAGS = {
    "OperatingIncomeLoss",
    "ProfitLossFromOperatingActivities",
    "SegmentReportingInformationOperatingIncomeLoss",
    "ProfitLossBeforeTax",
}

ALL_SEGMENT_AXIS_KEYWORDS = (
    "StatementBusinessSegmentsAxis",
    "ProductOrServiceAxis",
    "SubsegmentsAxis",
    "MajorProductsAndServicesAxis",
    "OperatingSegmentsAxis",
    "BusinessSegmentsAxis",
    "SegmentsAxis",
    "ProductAndServiceAxis",
    "StatementGeographicalAxis",
    "GeographicalAxis",
    "DomesticAndForeignAxis",
    "CountryAxis",
    "CountriesAxis",
    "GeographicalAreasAxis",
)

GEO_AXIS_KEYWORDS = (
    "StatementGeographicalAxis",
    "GeographicalAxis",
    "DomesticAndForeignAxis",
    "CountryAxis",
    "CountriesAxis",
    "GeographicalAreasAxis",
)

GEO_MEMBER_HINTS = (
    "unitedstates",
    "brazil",
    "brasil",
    "mexico",
    "argentina",
    "chile",
    "colombia",
    "china",
    "taiwan",
    "japan",
    "europe",
    "americas",
    "asia",
    "emea",
    "apac",
    "othercountries",
    "restofworld",
    "international",
    "domestic",
    "foreign",
)

WRAPPER_AXES = {
    "ConsolidationItemsAxis",
}

DISQUALIFYING_AXES = (
    "RestatementAxis",
    "StatementScenarioAxis",
    "RevisionOfPriorPeriod",
)

IGNORE_MEMBER_KEYWORDS = (
    "Corporate",
    "Unallocated",
    "Eliminat",
    "Reconcil",
    "AllOtherSegments",
    "Consolidat",
    "Total",
    "Intersegment",
    "PreviouslyReported",
    "Restatement",
)


def _merge_segments_by_name(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Unifica ítems que comparten exactamente el mismo nombre tras la traducción
    (ej. dos sub-grupos residuales traducidos como 'Otros países'), sumando
    sus ingresos, ponderando margen operativo si existe y recalculando share_pct.
    """
    if len(items) <= 1:
        return items

    grouped: dict[str, dict[str, Any]] = {}
    for it in items:
        name = str(it.get("name") or "").strip()
        if not name:
            continue
        rev = float(it.get("revenue_mm") or 0.0)
        om = it.get("operating_margin_pct")

        if name not in grouped:
            grouped[name] = {
                "name": name,
                "revenue_mm": rev,
                "_om_weighted_sum": (rev * float(om)) if (om is not None and rev > 0) else 0.0,
                "_om_rev_base": rev if (om is not None and rev > 0) else 0.0,
                "_has_om": om is not None,
            }
        else:
            grouped[name]["revenue_mm"] += rev
            if om is not None and rev > 0:
                grouped[name]["_om_weighted_sum"] += rev * float(om)
                grouped[name]["_om_rev_base"] += rev
                grouped[name]["_has_om"] = True

    total_rev = sum(g["revenue_mm"] for g in grouped.values())
    merged: list[dict[str, Any]] = []
    for g in grouped.values():
        rev_rounded = round(g["revenue_mm"], 2)
        op_margin = (
            round(g["_om_weighted_sum"] / g["_om_rev_base"], 1)
            if (g["_has_om"] and g["_om_rev_base"] > 0)
            else None
        )
        merged.append({
            "name": g["name"],
            "revenue_mm": rev_rounded,
            "share_pct": round((g["revenue_mm"] / total_rev) * 100.0, 1) if total_rev > 0 else 0.0,
            "operating_margin_pct": op_margin,
        })

    merged.sort(key=lambda x: x["revenue_mm"], reverse=True)
    return merged


def _sanitize_editorial_text(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    txt = re.sub(r"\s+", " ", str(raw_text)).strip()
    txt = re.sub(r"([.;:])([A-ZÁÉÍÓÚÑa-záéíóúñ])", r"\1 \2", txt)
    txt = re.sub(r"\s{2,}", " ", txt).strip()
    return txt


def _humanize_xbrl_member(raw_member: str) -> str:
    local = raw_member.split(":")[-1]
    for prefix in ("CountryOf", "RegionOf", "StateOf", "Segment"):
        if local.startswith(prefix) and len(local) > len(prefix):
            local = local[len(prefix):]
    for suffix in ("Member", "Segment", "Domain", "ProductOrService", "Geographic", "Country", "Region"):
        if local.endswith(suffix) and len(local) > len(suffix):
            local = local[: -len(suffix)]
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", local)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    spaced = spaced.replace("_", " ").strip()
    return spaced


def _translate_label_es(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    cleaned = raw_text.strip()
    if cleaned in SECTOR_INDUSTRY_ES:
        return SECTOR_INDUSTRY_ES[cleaned]

    low = cleaned.lower()
    if low in EXACT_TRANSLATIONS_ES:
        return EXACT_TRANSLATIONS_ES[low]

    translated = cleaned
    replacements = [
        (r"^Country Of\s+", ""),
        (r"\bUnited States\b", "Estados Unidos"),
        (r"\bOther Asia Pacific\b", "Resto de Asia-Pacífico"),
        (r"\bAsia Pacific\b", "Asia-Pacífico"),
        (r"\bLatin America\b", "Latinoamérica"),
        (r"\bNorth America\b", "Norteamérica"),
        (r"\bRest of World\b", "Resto del mundo"),
        (r"\bOther countries\b", "Otros países"),
        (r"\bBrazil\b", "Brasil"),
        (r"\bMexico\b", "México"),
        (r"\bColombia\b", "Colombia"),
        (r"\bServices\b", "Servicios"),
        (r"\bProducts\b", "Productos"),
        (r"\bAdvertising\b", "Publicidad"),
        (r"\bSubscriptions?\b", "Suscripciones"),
        (r"\bDevices\b", "Dispositivos"),
        (r"\bConsumer\b", "Consumo"),
        (r"\bCommercial\b", "Comercial"),
        (r"\bEnterprise\b", "Empresas"),
        (r"\bOther\b", "Otros"),
    ]
    for pattern, repl in replacements:
        translated = re.sub(pattern, repl, translated, flags=re.IGNORECASE)
    return translated.strip()


def _is_geographic_axis(axis_name: str, members: list[str]) -> bool:
    if any(kw.lower() in axis_name.lower() for kw in GEO_AXIS_KEYWORDS):
        return True
    if not members:
        return False
    geo_hits = 0
    for m in members:
        clean = _humanize_xbrl_member(m).lower().replace(" ", "")
        if clean in ("us", "br", "mx", "ar", "cl", "co", "tw", "cn", "jp", "de", "gb", "hk", "sg"):
            geo_hits += 1
        elif any(h in clean for h in GEO_MEMBER_HINTS):
            geo_hits += 1
    return (geo_hits / len(members)) >= 0.5


class _SimpleHtmlTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_row = False
        self.in_cell = False
        self.rows: list[list[str]] = []
        self._curr_row: list[str] = []
        self._curr_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == "tr":
            self.in_row = True
            self._curr_row = []
        elif t in ("td", "th") and self.in_row:
            self.in_cell = True
            self._curr_cell = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("td", "th") and self.in_cell:
            self.in_cell = False
            text = re.sub(r"\s+", " ", "".join(self._curr_cell)).strip()
            self._curr_row.append(text)
        elif t == "tr" and self.in_row:
            self.in_row = False
            if any(c for c in self._curr_row):
                self.rows.append(self._curr_row)

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self._curr_cell.append(data)


def _parse_table_num(raw: str) -> float | None:
    if not raw:
        return None
    cleaned = raw.replace("$", "").replace(",", "").replace("\xa0", "").strip()
    if cleaned in ("", "-", "—", "–", "N/A"):
        return None
    is_neg = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        is_neg = True
        cleaned = cleaned[1:-1].strip()
    if not re.match(r"^-?\d+(\.\d+)?$", cleaned):
        return None
    val = float(cleaned)
    return -val if is_neg else val


def _fallback_parse_html_segments(
    base_archive: str,
    reference_revs: list[float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        fs_resp = requests.get(f"{base_archive}/FilingSummary.xml", headers=SEC_HEADERS, timeout=10)
        if fs_resp.status_code != 200:
            return [], []
        root = ET.fromstring(fs_resp.text)
    except Exception:
        return [], []

    biz_res: list[dict[str, Any]] = []
    geo_res: list[dict[str, Any]] = []

    bad_terms = (
        "asset", "liabilit", "equity", "expense", "cost", "depreciat", "tax",
        "interest", "cash", "consolidated", "reconcil", "eliminat",
        "corporate", "balance", "year", "month", "operating income", "profit",
        "direct contribution", "net income", "gross profit",
    )

    candidate_reps: list[tuple[int, str, str]] = []
    for rep in root.findall(".//Report"):
        short_name = (rep.findtext("ShortName") or "").strip()
        html_file = (rep.findtext("HtmlFileName") or "").strip()
        if not short_name or not html_file:
            continue
        sn_low = short_name.lower()
        if any(s in sn_low for s in ("polic", "parenthetical", "schedule", "tax", "asset", "debt")):
            continue
        if any(k in sn_low for k in ("segment", "geograph", "country", "countries", "disaggregat")):
            prio = 1 if ("revenue" in sn_low or "disaggregat" in sn_low or "geograph" in sn_low) else 2
            candidate_reps.append((prio, short_name, html_file))

    candidate_reps.sort(key=lambda x: x[0])

    for _, short_name, html_file in candidate_reps[:12]:
        try:
            r_resp = requests.get(f"{base_archive}/{html_file}", headers=SEC_HEADERS, timeout=10)
            if r_resp.status_code != 200:
                continue
        except Exception:
            continue

        sn_low = short_name.lower()
        parser = _SimpleHtmlTableParser()
        parser.feed(r_resp.text)
        rows = parser.rows
        if len(rows) < 3:
            continue

        header_blob = " ".join(" ".join(r) for r in rows[:4]).lower()
        scale = 1000.0 if "in billions" in header_blob else (0.001 if "in thousands" in header_blob else 1.0)

        blocks: list[dict[str, float]] = []
        curr_items: dict[str, float] = {}

        for r in rows[1:]:
            lbl = re.sub(r"\s*[\(\[][a-z0-9]{1,3}[\)\]]\s*$", "", r[0].strip(), flags=re.I)
            lbl_low = lbl.lower()

            num_val: float | None = None
            for cell in r[1:]:
                parsed = _parse_table_num(cell)
                if parsed is not None:
                    num_val = parsed * scale
                    break

            if lbl_low.startswith("total") or num_val is None or any(b in lbl_low for b in bad_terms):
                if len(curr_items) >= 2:
                    blocks.append(curr_items)
                curr_items = {}
                continue

            if not lbl or len(lbl) > 55:
                continue

            if num_val > 0 and lbl not in curr_items:
                curr_items[lbl] = round(num_val, 2)

        if len(curr_items) >= 2:
            blocks.append(curr_items)

        for items in blocks:
            tot = sum(items.values())
            if not any(0.88 * ref <= tot <= 1.12 * ref for ref in reference_revs if ref > 0):
                continue

            group = _merge_segments_by_name([
                {
                    "name": _translate_label_es(k),
                    "revenue_mm": v,
                    "share_pct": round((v / tot) * 100.0, 1),
                    "operating_margin_pct": None,
                }
                for k, v in items.items()
            ])

            is_geo = _is_geographic_axis(sn_low, list(items.keys()))
            if is_geo and not geo_res:
                geo_res = group
            elif not is_geo and not biz_res:
                biz_res = group

        if biz_res and geo_res:
            break

    return biz_res, geo_res


def _extract_xbrl_instance_segments(
    cik_str: str,
    total_rev_mm: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Extrae cortes dimensionales de negocio y geografía desde SEC EDGAR:
    1) Streaming XML (*_htm.xml) validando contra el total consolidado de ese mismo XML
       y clasificando cada eje según contenga países o líneas de negocio.
    2) Si falta algún corte, completa desde tablas HTML de FilingSummary.xml.
    """
    if not cik_str or total_rev_mm <= 0:
        return [], []

    cik_padded = str(cik_str).zfill(10)
    cik_int = str(int(cik_padded))
    sub_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"

    try:
        sub_resp = requests.get(sub_url, headers=SEC_HEADERS, timeout=12)
        if sub_resp.status_code != 200:
            return [], []
        sub_data = sub_resp.json()
    except Exception:
        return [], []

    recent = sub_data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    acc_nums = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    target_acc: str | None = None
    target_primary: str | None = None
    for idx, (form, acc) in enumerate(zip(forms, acc_nums)):
        if form in ("10-K", "20-F"):
            target_acc = str(acc)
            if idx < len(primary_docs):
                target_primary = str(primary_docs[idx] or "")
            break

    if not target_acc:
        return [], []

    acc_no_dash = target_acc.replace("-", "")
    base_archive = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_dash}"

    candidate_xmls: list[str] = []
    if target_primary and target_primary.lower().endswith((".htm", ".html")):
        base_doc = re.sub(r"\.html?$", "", target_primary, flags=re.IGNORECASE)
        candidate_xmls.append(f"{base_doc}_htm.xml")

    try:
        fs_resp = requests.get(f"{base_archive}/FilingSummary.xml", headers=SEC_HEADERS, timeout=10)
        if fs_resp.status_code == 200:
            fs_root = ET.fromstring(fs_resp.text)
            for rep in fs_root.findall(".//Report"):
                inst = rep.attrib.get("instance")
                if inst and inst.endswith(".xml") and inst not in candidate_xmls:
                    candidate_xmls.append(inst)
                    break
    except Exception:
        pass

    base_contexts: dict[str, str] = {}
    dim_contexts: dict[str, dict[str, Any]] = {}
    xml_total_by_year: dict[str, float] = {}
    rev_facts: list[tuple[list[tuple[str, str]], str, float]] = []
    opinc_facts: list[tuple[list[tuple[str, str]], str, float]] = []

    for xml_name in candidate_xmls[:2]:
        try:
            resp = requests.get(f"{base_archive}/{xml_name}", headers=SEC_HEADERS, timeout=25, stream=True)
            if resp.status_code != 200:
                resp.close()
                continue
            resp.raw.decode_content = True

            for _, elem in ET.iterparse(resp.raw, events=("end",)):
                tag_local = elem.tag.split("}")[-1]

                if tag_local == "context":
                    ctx_id = elem.attrib.get("id")
                    if ctx_id:
                        start_str = ""
                        end_str = ""
                        dims: list[tuple[str, str]] = []
                        has_disqualifying = False

                        for sub in elem.iter():
                            sub_local = sub.tag.split("}")[-1]
                            if sub_local == "startDate" and sub.text:
                                start_str = sub.text.strip()[:10]
                            elif sub_local == "endDate" and sub.text:
                                end_str = sub.text.strip()[:10]
                            elif sub_local in ("explicitMember", "typedMember"):
                                axis_local = sub.attrib.get("dimension", "").split(":")[-1]
                                if any(dq.lower() in axis_local.lower() for dq in DISQUALIFYING_AXES):
                                    has_disqualifying = True
                                    break
                                if sub_local == "explicitMember":
                                    member_local = (sub.text or "").strip().split(":")[-1]
                                else:
                                    member_local = "".join(sub.itertext()).strip().split(":")[-1]

                                if not member_local:
                                    continue
                                if axis_local in WRAPPER_AXES and "operatingsegments" in member_local.lower():
                                    continue
                                dims.append((axis_local, member_local))

                        if not has_disqualifying and start_str and end_str:
                            try:
                                d0 = datetime.strptime(start_str, "%Y-%m-%d")
                                d1 = datetime.strptime(end_str, "%Y-%m-%d")
                                if (d1 - d0).days >= 300:
                                    if len(dims) == 0:
                                        base_contexts[ctx_id] = end_str
                                    elif 1 <= len(dims) <= 2:
                                        if not any(
                                            ig.lower() in m.lower()
                                            for _, m in dims
                                            for ig in IGNORE_MEMBER_KEYWORDS
                                        ):
                                            dim_contexts[ctx_id] = {
                                                "end_date": end_str,
                                                "dims": dims,
                                            }
                            except ValueError:
                                pass
                    elem.clear()

                elif tag_local in REVENUE_LOCAL_TAGS or tag_local in OPINC_LOCAL_TAGS:
                    ctx_ref = elem.attrib.get("contextRef")
                    if ctx_ref and elem.text:
                        try:
                            raw_val = float(elem.text.strip())
                            val_mm = round(raw_val / 1_000_000.0, 2)
                            if ctx_ref in base_contexts and tag_local in REVENUE_LOCAL_TAGS and val_mm > 0:
                                yr = base_contexts[ctx_ref][:4]
                                if val_mm > xml_total_by_year.get(yr, 0.0):
                                    xml_total_by_year[yr] = val_mm
                            elif ctx_ref in dim_contexts:
                                ctx_info = dim_contexts[ctx_ref]
                                if tag_local in REVENUE_LOCAL_TAGS and val_mm > 0:
                                    rev_facts.append((ctx_info["dims"], ctx_info["end_date"], val_mm))
                                elif tag_local in OPINC_LOCAL_TAGS:
                                    opinc_facts.append((ctx_info["dims"], ctx_info["end_date"], val_mm))
                        except ValueError:
                            pass
                    elem.clear()

            resp.close()
            if rev_facts:
                break
        except Exception:
            continue

    biz_segments: list[dict[str, Any]] = []
    geo_segments: list[dict[str, Any]] = []

    uni_axes = {
        dims[0][0]
        for dims, _, _ in rev_facts
        if len(dims) == 1 and any(kw.lower() in dims[0][0].lower() for kw in ALL_SEGMENT_AXIS_KEYWORDS)
    }

    best_biz_diff = 999.0
    best_geo_diff = 999.0

    for ax in uni_axes:
        ax_revs = [(end_dt, dims[0][1], val) for dims, end_dt, val in rev_facts if len(dims) == 1 and dims[0][0] == ax]
        if not ax_revs:
            continue
        latest_end = max(end_dt for end_dt, _, _ in ax_revs)
        latest_year = latest_end[:4]

        by_member: dict[str, float] = {}
        for end_dt, mem, val in ax_revs:
            if end_dt.startswith(latest_year):
                if mem not in by_member or val > by_member[mem]:
                    by_member[mem] = val

        if len(by_member) < 2:
            continue

        sum_rev = sum(by_member.values())
        ref_total = xml_total_by_year.get(latest_year) or total_rev_mm
        if ref_total <= 0:
            continue

        ratio_to_total = sum_rev / ref_total
        if not (0.85 <= ratio_to_total <= 1.15):
            continue

        opinc_by_mem: dict[str, float] = {}
        for dims, end_dt, val in opinc_facts:
            if len(dims) == 1 and dims[0][0] == ax and end_dt.startswith(latest_year):
                opinc_by_mem[dims[0][1]] = val

        candidate = _merge_segments_by_name([
            {
                "name": _translate_label_es(_humanize_xbrl_member(mem)),
                "revenue_mm": seg_rev,
                "share_pct": round((seg_rev / sum_rev) * 100.0, 1),
                "operating_margin_pct": (
                    round((opinc_by_mem[mem] / seg_rev) * 100.0, 1)
                    if (mem in opinc_by_mem and seg_rev > 0)
                    else None
                ),
            }
            for mem, seg_rev in by_member.items()
        ])

        diff = abs(1.0 - ratio_to_total)
        is_geo = _is_geographic_axis(ax, list(by_member.keys()))
        if is_geo:
            if diff < best_geo_diff:
                best_geo_diff = diff
                geo_segments = candidate
        else:
            if diff < best_biz_diff:
                best_biz_diff = diff
                biz_segments = candidate

    if not biz_segments or not geo_segments:
        ref_revs = list(xml_total_by_year.values()) + [total_rev_mm]
        html_biz, html_geo = _fallback_parse_html_segments(base_archive, ref_revs)
        if not biz_segments and html_biz:
            biz_segments = html_biz
        if not geo_segments and html_geo:
            geo_segments = html_geo

    return _merge_segments_by_name(biz_segments), _merge_segments_by_name(geo_segments)


def _format_market_cap_label(market_cap_mm: float) -> str | None:
    if market_cap_mm <= 0:
        return None
    if market_cap_mm >= 1_000_000:
        return f"US$ {market_cap_mm / 1_000_000:,.2f} T"
    if market_cap_mm >= 1_000:
        return f"US$ {market_cap_mm / 1_000:,.1f} B"
    return f"US$ {market_cap_mm:,.0f} MM"


def _compute_dcf_summary(val_report: dict[str, Any]) -> dict[str, Any]:
    routing = val_report.get("sector_routing", {})
    profile_type = routing.get("profile", "standard")
    inp = val_report.get("dcf_inputs", {})
    f_inp = val_report.get("financial_sector_inputs", {})
    cur_price = float(inp.get("current_price") or f_inp.get("current_price") or 0.0)
    target_ws = inp.get("target_price") or f_inp.get("target_price")

    if profile_type == "financial":
        bvps = float(f_inp.get("bvps") or 0.0)
        roe = float(f_inp.get("roe_pct") or 12.0) / 100.0
        ke = float(f_inp.get("cost_of_equity_pct") or 9.5) / 100.0
        payout = float(f_inp.get("payout_ratio_pct") or 35.0) / 100.0
        g1 = min(max(roe * (1.0 - payout), 0.01), 0.14)
        g_term = min(g1, 0.045)
        if bvps > 0 and ke > g_term:
            bv = bvps
            pv_exc = 0.0
            for yr in range(1, 6):
                pv_exc += (bv * (roe - ke)) / ((1.0 + ke) ** yr)
                bv *= 1.0 + g1
            term_roe = ke + (roe - ke) * 0.5
            tv = (bv * (term_roe - ke)) / (ke - g_term)
            fair_mid = round(bvps + pv_exc + tv / ((1.0 + ke) ** 5), 2)
            fair_low = round(fair_mid * 0.88, 2)
            fair_high = round(fair_mid * 1.12, 2)
        else:
            fair_low = fair_mid = fair_high = cur_price
        model_used = "Retorno Excedente (ROE vs. Costo del Capital)"
    else:
        rev0 = float(inp.get("revenue_base_mm") or 0.0)
        shares = float(inp.get("shares_mm") or 0.0)
        net_debt = float(inp.get("net_debt_mm") or 0.0)
        ebit_m = float(inp.get("ebit_margin_pct") or 15.0) / 100.0
        tax_r = float(inp.get("tax_rate_pct") or 21.0) / 100.0
        da_p = float(inp.get("da_sales_pct") or 8.0) / 100.0
        capex1 = float(inp.get("capex_expansion_pct") or 12.0) / 100.0
        capex_t = float(inp.get("capex_maintenance_pct") or 8.0) / 100.0
        g = float(inp.get("recommended_rev_growth_pct") or 8.0) / 100.0
        wacc = float(inp.get("suggested_wacc_pct") or 9.0) / 100.0
        exit_m = float(inp.get("exit_multiple_default") or 18.0)
        g_term = 0.03

        if rev0 > 0 and shares > 0 and wacc > g_term:
            rv = rev0
            pv1 = 0.0
            for yr in range(1, 6):
                rv *= 1.0 + g
                fcf_y = rv * (ebit_m * (1.0 - tax_r) + da_p - capex1)
                pv1 += fcf_y / ((1.0 + wacc) ** yr)
            fcf6 = rv * (1.0 + g_term) * (ebit_m * (1.0 - tax_r) + da_p - capex_t)
            p_gordon = (pv1 + (fcf6 / (wacc - g_term)) / ((1.0 + wacc) ** 5) - net_debt) / shares
            fcf5_norm = rv * (ebit_m * (1.0 - tax_r) + da_p - capex_t)
            p_mult = (pv1 + (fcf5_norm * exit_m) / ((1.0 + wacc) ** 5) - net_debt) / shares

            fair_low = round(min(p_gordon, p_mult), 2)
            fair_high = round(max(p_gordon, p_mult), 2)
            fair_mid = round((p_gordon + p_mult) / 2.0, 2)
        else:
            fair_low = fair_mid = fair_high = cur_price
        model_used = "DCF 2 Etapas (Perpetuidad Gordon + Múltiplo de Salida)"

    upside_pct = round(((fair_mid - cur_price) / cur_price) * 100.0, 1) if cur_price > 0 else 0.0
    return {
        "model_used": model_used,
        "current_price": round(cur_price, 2),
        "intrinsic_low": max(fair_low, 0.0),
        "intrinsic_mid": max(fair_mid, 0.0),
        "intrinsic_high": max(fair_high, 0.0),
        "consensus_target": round(float(target_ws), 2) if target_ws else None,
        "upside_mid_pct": upside_pct,
    }


def _compute_quarterly_momentum(raw_facts: dict[str, Any]) -> dict[str, Any]:
    try:
        q_rows = extract_quarterly_metrics(raw_facts)
    except Exception:
        return {}
    if not q_rows:
        return {}

    rev_row = next((r for r in q_rows if r.get("Métrica") == "Ingresos Totales"), None)
    ebit_row = next((r for r in q_rows if r.get("Métrica") == "Beneficio Operativo"), None)
    if not rev_row:
        return {}

    q_cols = sorted(
        [k for k in rev_row.keys() if re.match(r"^\d{4}-Q[1-4]$", k) and float(rev_row.get(k) or 0.0) > 0]
    )
    if not q_cols:
        return {}

    latest_q = q_cols[-1]
    yr_str, q_str = latest_q.split("-")
    prior_year_q = f"{int(yr_str) - 1}-{q_str}"

    rev_curr = float(rev_row.get(latest_q) or 0.0)
    rev_prev = float(rev_row.get(prior_year_q) or 0.0)
    rev_yoy_pct = round(((rev_curr - rev_prev) / rev_prev) * 100.0, 1) if rev_prev > 0 else None

    ebit_curr = float(ebit_row.get(latest_q) or 0.0) if ebit_row else 0.0
    ebit_prev = float(ebit_row.get(prior_year_q) or 0.0) if ebit_row else 0.0
    ebit_yoy_pct = (
        round(((ebit_curr - ebit_prev) / abs(ebit_prev)) * 100.0, 1)
        if ebit_prev != 0
        else None
    )

    ltm_cols = q_cols[-4:]
    ltm_rev_mm = round(sum(float(rev_row.get(c) or 0.0) for c in ltm_cols), 1) if len(ltm_cols) == 4 else None

    return {
        "latest_quarter": latest_q,
        "latest_q_rev_mm": round(rev_curr, 1),
        "rev_yoy_pct": rev_yoy_pct,
        "ebit_yoy_pct": ebit_yoy_pct,
        "ltm_rev_mm": ltm_rev_mm,
    }


def save_custom_segments(
    db: Session,
    ticker_symbol: str,
    business_segments: list[dict[str, Any]],
    geo_segments: list[dict[str, Any]],
    key_clients_notes: str,
) -> dict[str, Any]:
    ticker_upper = ticker_symbol.upper().strip()
    now = datetime.utcnow()

    def normalize_list(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        clean = [it for it in items if (it.get("name") or "").strip()]
        total = sum(max(float(it.get("revenue_mm") or 0.0), 0.0) for it in clean)
        out: list[dict[str, Any]] = []
        for it in clean:
            rev = max(float(it.get("revenue_mm") or 0.0), 0.0)
            om_raw = it.get("operating_margin_pct")
            om_val = round(float(om_raw), 1) if om_raw is not None and om_raw != "" else None
            out.append({
                "name": str(it["name"]).strip(),
                "revenue_mm": round(rev, 2),
                "share_pct": round((rev / total) * 100.0, 1) if total > 0 else 0.0,
                "operating_margin_pct": om_val,
            })
        return _merge_segments_by_name(out)

    norm_biz = normalize_list(business_segments)
    norm_geo = normalize_list(geo_segments)

    db.merge(
        CompanySegmentsCache(
            ticker=ticker_upper,
            business_segments=norm_biz,
            geo_segments=norm_geo,
            key_clients_notes=key_clients_notes.strip(),
            is_custom=True,
            last_updated=now,
        )
    )
    db.commit()
    return {
        "ticker": ticker_upper,
        "business_segments": norm_biz,
        "geo_segments": norm_geo,
        "key_clients_notes": key_clients_notes.strip(),
        "is_custom": True,
    }


def reset_custom_segments(db: Session, ticker_symbol: str) -> dict[str, Any]:
    ticker_upper = ticker_symbol.upper().strip()
    db.query(CompanySegmentsCache).filter(CompanySegmentsCache.ticker == ticker_upper).delete()
    db.commit()
    return build_investment_thesis_onepager(ticker_upper, db)


def build_investment_thesis_onepager(ticker_symbol: str, db: Session) -> dict[str, Any]:
    ticker_upper = ticker_symbol.upper().strip()

    profile = get_company_profile(ticker_upper, db)
    raw_facts = get_raw_financials(ticker_upper, db)
    estimates = get_cached_estimates_and_guidance(ticker_upper, db)
    annual_rows = extract_annual_metrics(raw_facts)
    health = build_financial_health_report(ticker_upper, annual_rows, db)
    val_report = build_valuation_report(ticker_upper, db)
    quarterly_momentum = _compute_quarterly_momentum(raw_facts)

    current_year = datetime.now().year
    years_range = [str(y) for y in range(current_year - 6, current_year + 1)]

    lookup: dict[str, dict[str, float]] = {}
    for row in annual_rows:
        m = row.get("Métrica", "")
        lookup[m] = {y: float(row.get(y, 0.0) or 0.0) for y in years_range}

    valid_years = [
        y for y in years_range
        if lookup.get("Ingresos Totales", {}).get(y, 0.0) > 0
        or lookup.get("Patrimonio neto", {}).get(y, 0.0) > 0
    ][-5:]

    financial_trend: list[dict[str, Any]] = []
    for y in valid_years:
        rev = lookup.get("Ingresos Totales", {}).get(y, 0.0)
        ebit = lookup.get("Beneficio Operativo", {}).get(y, 0.0)
        net_inc = lookup.get("Beneficio Neto", {}).get(y, 0.0)
        fcf = lookup.get("Flujo de caja libre (FCF)", {}).get(y, 0.0)
        op_margin = round((ebit / rev) * 100.0, 1) if rev > 0 else 0.0
        fcf_margin = round((fcf / rev) * 100.0, 1) if rev > 0 else 0.0
        financial_trend.append({
            "year": y,
            "revenue_mm": round(rev, 1),
            "ebit_mm": round(ebit, 1),
            "net_income_mm": round(net_inc, 1),
            "fcf_mm": round(fcf, 1),
            "operating_margin_pct": op_margin,
            "fcf_margin_pct": fcf_margin,
        })

    rev_cagr_5y = None
    positive_rev_pts = [pt for pt in financial_trend if pt["revenue_mm"] > 0]
    if len(positive_rev_pts) >= 2:
        r0 = positive_rev_pts[0]["revenue_mm"]
        r1 = positive_rev_pts[-1]["revenue_mm"]
        n_yrs = max(int(positive_rev_pts[-1]["year"]) - int(positive_rev_pts[0]["year"]), 1)
        if r0 > 0 and r1 > 0:
            rev_cagr_5y = round((((r1 / r0) ** (1.0 / n_yrs)) - 1.0) * 100.0, 1)

    latest_yr = valid_years[-1] if valid_years else None
    roe_latest: float | None = None
    roic_latest: float | None = None
    if latest_yr:
        ni_last = lookup.get("Beneficio Neto", {}).get(latest_yr, 0.0)
        eq_last = lookup.get("Patrimonio neto", {}).get(latest_yr, 0.0)
        ebit_last = lookup.get("Beneficio Operativo", {}).get(latest_yr, 0.0)
        ebt_last = lookup.get("Beneficio antes de Impuestos", {}).get(latest_yr, 0.0)
        tax_last = lookup.get("Gasto por Impuesto a las Ganancias", {}).get(latest_yr, 0.0)
        st_debt = lookup.get("Deuda a corto plazo", {}).get(latest_yr, 0.0)
        lt_debt = lookup.get("Deuda a largo plazo", {}).get(latest_yr, 0.0)
        cash_last = (
            lookup.get("Efectivo y equivalentes", {}).get(latest_yr, 0.0)
            + lookup.get("Inversiones a corto plazo", {}).get(latest_yr, 0.0)
        )

        if eq_last > 0:
            roe_latest = round((ni_last / eq_last) * 100.0, 1)

        eff_tax = min(max((tax_last / ebt_last), 0.0), 0.40) if ebt_last > 0 else 0.21
        nopat = ebit_last * (1.0 - eff_tax)
        invested_cap = eq_last + st_debt + lt_debt - cash_last
        if invested_cap > 0 and ebit_last > 0:
            roic_latest = round((nopat / invested_cap) * 100.0, 1)

    latest_rev = financial_trend[-1]["revenue_mm"] if financial_trend else 0.0
    latest_om = financial_trend[-1]["operating_margin_pct"] if financial_trend else 0.0

    default_clients_note = "Base diversificada de clientes corporativos, institucionales y consumidores finales."
    now = datetime.utcnow()
    cached_seg = db.query(CompanySegmentsCache).filter(CompanySegmentsCache.ticker == ticker_upper).first()
    business_segments: list[dict[str, Any]] = []
    geo_segments: list[dict[str, Any]] = []
    clients_notes = default_clients_note
    is_custom_segments = False

    if cached_seg is not None:
        is_custom_flag = bool(getattr(cached_seg, "is_custom", False))
        c_biz = _merge_segments_by_name(list(getattr(cached_seg, "business_segments", None) or []))
        c_geo = _merge_segments_by_name(list(getattr(cached_seg, "geo_segments", None) or []))
        updated_at: Any = getattr(cached_seg, "last_updated", None)
        is_fresh = isinstance(updated_at, datetime) and (now - updated_at) < timedelta(days=30)
        if is_custom_flag or (is_fresh and (len(c_biz) > 1 or len(c_geo) > 1)):
            business_segments = c_biz
            geo_segments = c_geo
            saved_notes = getattr(cached_seg, "key_clients_notes", None)
            if saved_notes and "editable para personalizar" not in str(saved_notes).lower():
                clients_notes = str(saved_notes)
            is_custom_segments = is_custom_flag

    if not business_segments and not geo_segments:
        cik_raw = str(raw_facts.get("cik") or "")
        business_segments, geo_segments = _extract_xbrl_instance_segments(cik_raw, latest_rev)

        db.merge(
            CompanySegmentsCache(
                ticker=ticker_upper,
                business_segments=business_segments,
                geo_segments=geo_segments,
                key_clients_notes=clients_notes,
                is_custom=False,
                last_updated=now,
            )
        )
        db.commit()

    valuation_bridge = _compute_dcf_summary(val_report)
    classification = estimates.get("classification", {})
    trajectory = val_report.get("trajectory", {})
    audit = val_report.get("audit", {})
    summary_metrics = profile.get("summary_metrics", {})

    inp = val_report.get("dcf_inputs", {})
    shares_mm = float(inp.get("shares_mm") or 0.0)
    rev_ttm_mm = float(inp.get("revenue_base_mm") or 0.0)
    fcf_ttm_mm = float(inp.get("fcf_reported_mm") or 0.0)
    ttm_fcf_margin = round((fcf_ttm_mm / rev_ttm_mm) * 100.0, 1) if rev_ttm_mm > 0 else None
    ttm_ebit_margin = float(inp.get("ebit_margin_pct")) if inp.get("ebit_margin_pct") is not None else latest_om

    audit_flags = audit.get("flags") or []
    margin_flag = next(
        (f for f in audit_flags if f.get("canonical_code") in ("MARGEN_COMPRIMIDO", "CAPEX_CICLO", "PICO_CICLICO") or f.get("code") in ("MARGIN_COMPRESSION_REINVESTMENT", "CAPEX_EXPANSION")),
        None,
    )
    margin_narrative = (
        f"Evento extraordinario detectado: {margin_flag.get('title')}."
        if margin_flag
        else trajectory.get("leverage_label", "Mantiene disciplina operativa y generación recurrente de caja.")
    )
    market_cap_mm = valuation_bridge["current_price"] * shares_mm
    market_cap_formatted = (
        summary_metrics.get("capital_structure", {}).get("market_cap")
        or _format_market_cap_label(market_cap_mm)
    )

    sector_es = _translate_label_es(classification.get("sector")) or "su industria"
    industry_es = _translate_label_es(classification.get("industry"))
    piotroski_score = health.get("piotroski", {}).get("score")

    altman_block = health.get("altman") or health.get("altman_z") or {}
    altman_score = altman_block.get("z_score") if isinstance(altman_block, dict) else None
    altman_zone = altman_block.get("zone") if isinstance(altman_block, dict) else None

    roic_txt = f"{roic_latest}%" if roic_latest is not None else "N/D"
    roe_txt = f"{roe_latest}%" if roe_latest is not None else "N/D"
    cagr_txt = f"{rev_cagr_5y}%" if rev_cagr_5y is not None else "N/D"

    q_pulse_txt = ""
    if quarterly_momentum.get("latest_quarter") and quarterly_momentum.get("rev_yoy_pct") is not None:
        q_pulse_txt = (
            f" En el último trimestre ({quarterly_momentum['latest_quarter']}), las ventas crecieron "
            f"{quarterly_momentum['rev_yoy_pct']:+.1f}% interanual."
        )

    thesis_pillars = [
        {
            "title": "1. Posicionamiento Competitivo y Modelo de Negocio",
            "body": (
                f"{profile.get('name', ticker_upper)} opera en {sector_es}"
                f"{f' ({industry_es})' if industry_es else ''}, generando ventas anuales de "
                f"US$ {latest_rev:,.0f} MM con un margen operativo del {ttm_ebit_margin:.1f}%. "
                f"{margin_narrative}"
            ),
        },
        {
            "title": "2. Motor de Crecimiento y Eficiencia de Capital",
            "body": (
                f"Crecimiento compuesto histórico de ingresos de {cagr_txt} "
                f"y proyección ponderada de {trajectory.get('recommended_rev_growth_pct', 'N/D')}% anual.{q_pulse_txt} "
                f"Rentabilidad sobre capital invertido (ROIC): {roic_txt} "
                f"(ROE: {roe_txt}) y puntaje Piotroski F-Score de {piotroski_score}/9."
            ),
        },
        {
            "title": "3. Oportunidad de Valuación y Margen de Seguridad",
            "body": (
                f"Cotizando a US$ {valuation_bridge['current_price']:,.2f}, nuestro modelo {valuation_bridge['model_used']} "
                f"estima un rango intrínseco de US$ {valuation_bridge['intrinsic_low']:,.2f} a "
                f"US$ {valuation_bridge['intrinsic_high']:,.2f} (punto medio US$ {valuation_bridge['intrinsic_mid']:,.2f}, "
                f"potencial {valuation_bridge['upside_mid_pct']:+.1f}%)."
            ),
        },
    ]

    detected_risks: list[str] = []
    for fl in audit.get("flags", []):
        detected_risks.append(f"{fl.get('title')}: {fl.get('detail')}")
    if not detected_risks:
        detected_risks = [
            "Riesgo macroeconómico y sensibilidad a tasas de interés sobre múltiplos de valuación.",
            "Presión competitiva en precios o márgenes operativos ante nuevos entrantes del sector.",
            "Riesgo de ejecución en asignación de capital (CapEx y adquisiciones).",
        ]

    multiples_list: list[dict[str, Any]] = []
    for r in val_report.get("rows", []):
        m_lbl = r.get("metric", "")
        if any(k in m_lbl for k in ("P/E", "EV / EBITDA", "P/FCF", "P/BV", "FCF Yield")):
            ltm_val = r.get("ltm")
            med_val = r.get("med_5y")
            prem_pct = None
            if isinstance(ltm_val, (int, float)) and isinstance(med_val, (int, float)) and med_val != 0:
                prem_pct = round(((ltm_val - med_val) / abs(med_val)) * 100.0, 1)
            multiples_list.append({
                "metric": m_lbl,
                "ltm": ltm_val,
                "med_5y": med_val,
                "suffix": r.get("suffix", "x"),
                "vs_med_pct": prem_pct,
            })

    return {
        "ticker": ticker_upper,
        "generated_date": datetime.now().strftime("%d/%m/%Y"),
        "is_custom_segments": is_custom_segments,
        "company": {
            "name": profile.get("name", ticker_upper),
            "website": profile.get("website"),
            "description": _sanitize_editorial_text(profile.get("description", "")),
            "sector": sector_es,
            "industry": industry_es,
            "price": valuation_bridge["current_price"],
            "change_pct": profile.get("change_pct"),
            "market_cap": market_cap_formatted,
            "enterprise_value": summary_metrics.get("capital_structure", {}).get("enterprise_value"),
            "dividend_yield": summary_metrics.get("dividend", {}).get("dividend_yield"),
        },
        "kpis": {
            "rev_cagr_5y_pct": rev_cagr_5y,
            "operating_margin_pct": round(ttm_ebit_margin, 1),
            "fcf_margin_pct": ttm_fcf_margin if ttm_fcf_margin is not None else (financial_trend[-1]["fcf_margin_pct"] if financial_trend else None),
            "roic_pct": roic_latest,
            "roe_pct": roe_latest,
            "piotroski_score": piotroski_score,
            "altman_z": altman_score,
            "altman_zone": altman_zone,
        },
        "audit": audit,
        "dcf_engine": val_report.get("dcf_engine"),
        "quarterly_momentum": quarterly_momentum,
        "business_segments": business_segments,
        "geo_segments": geo_segments,
        "key_clients_notes": clients_notes,
        "financial_trend": financial_trend,
        "multiples_list": multiples_list,
        "valuation_bridge": valuation_bridge,
        "thesis_pillars": thesis_pillars,
        "risks": detected_risks,
    }