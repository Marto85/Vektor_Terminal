import { Info, TrendingUp, TrendingDown } from "lucide-react";

function extractPeriodKeys(rows) {
  if (!Array.isArray(rows) || rows.length === 0) return [];
  const sample = rows.find((r) => !r.is_header) || rows[0];
  return Object.keys(sample)
    .filter(
      (k) =>
        k !== "Categoría" &&
        k !== "Métrica" &&
        k !== "is_pct" &&
        k !== "is_sub" &&
        k !== "is_header",
    )
    .sort();
}

function findMetricRow(financialData, category, exactOrPartialNames) {
  const catRows = financialData.filter(
    (r) => r.Categoría === category && !r.is_header,
  );
  for (const name of exactOrPartialNames) {
    const exact = catRows.find(
      (r) => String(r.Métrica || "").toLowerCase() === name.toLowerCase(),
    );
    if (exact) return exact;
  }
  for (const name of exactOrPartialNames) {
    const partial = catRows.find((r) =>
      String(r.Métrica || "")
        .toLowerCase()
        .includes(name.toLowerCase()),
    );
    if (partial) return partial;
  }
  return null;
}

function numAt(row, periodKey) {
  if (!row || !periodKey) return null;
  const v = row[periodKey];
  return typeof v === "number" && !Number.isNaN(v) ? v : null;
}

function fmtMoneyMM(val) {
  if (val === null || val === undefined) return "-";
  const neg = val < 0;
  const formatted = new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(Math.abs(val));
  return neg ? `(US$ ${formatted} MM)` : `US$ ${formatted} MM`;
}

function fmtPct(val, decimals = 1) {
  if (val === null || val === undefined) return "-";
  const neg = val < 0;
  const formatted = new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Math.abs(val));
  return neg ? `(${formatted}%)` : `${formatted}%`;
}

function fmtMult(val, suffix = "x") {
  if (val === null || val === undefined) return "-";
  const formatted = new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(val);
  return `${formatted}${suffix}`;
}

function calcGrowthPct(curr, prev) {
  if (curr === null || prev === null || prev === 0) return null;
  return ((curr - prev) / Math.abs(prev)) * 100;
}

function calcDeltaPp(curr, prev) {
  if (curr === null || prev === null) return null;
  return curr - prev;
}

export default function FinancialsQuickCards({
  financialData,
  activeContentTab,
  period,
  onOpenInfo,
}) {
  if (
    !Array.isArray(financialData) ||
    financialData.length === 0 ||
    activeContentTab === "Segmentos"
  ) {
    return null;
  }

  const periods = extractPeriodKeys(financialData);
  if (periods.length === 0) return null;

  const currP = periods[periods.length - 1];
  const prevP = periods.length >= 2 ? periods[periods.length - 2] : null;
  const compLabel = period === "annual" ? `vs ${prevP}` : `vs ${prevP}`;

  const revRow = findMetricRow(financialData, "Cuenta de Resultados", [
    "Ingresos Totales",
  ]);
  const gpRow = findMetricRow(financialData, "Cuenta de Resultados", [
    "Beneficio Bruto",
  ]);
  const ebitRow = findMetricRow(financialData, "Cuenta de Resultados", [
    "Beneficio Operativo",
  ]);
  const niRow = findMetricRow(financialData, "Cuenta de Resultados", [
    "Beneficio Neto",
  ]);

  const revCurr = numAt(revRow, currP);
  const revPrev = numAt(revRow, prevP);
  const gpCurr = numAt(gpRow, currP);
  const gpPrev = numAt(gpRow, prevP);
  const ebitCurr = numAt(ebitRow, currP);
  const ebitPrev = numAt(ebitRow, prevP);
  const niCurr = numAt(niRow, currP);
  const niPrev = numAt(niRow, prevP);

  let cards = [];

  if (activeContentTab === "Cuenta de Resultados") {
    const revGrowth = calcGrowthPct(revCurr, revPrev);
    const gmCurr = revCurr && gpCurr !== null ? (gpCurr / revCurr) * 100 : null;
    const gmPrev = revPrev && gpPrev !== null ? (gpPrev / revPrev) * 100 : null;
    const gmDelta = calcDeltaPp(gmCurr, gmPrev);

    const omCurr =
      revCurr && ebitCurr !== null ? (ebitCurr / revCurr) * 100 : null;
    const omPrev =
      revPrev && ebitPrev !== null ? (ebitPrev / revPrev) * 100 : null;
    const omDelta = calcDeltaPp(omCurr, omPrev);

    const nmCurr = revCurr && niCurr !== null ? (niCurr / revCurr) * 100 : null;
    const niGrowth = calcGrowthPct(niCurr, niPrev);

    cards = [
      {
        title: `Ingresos Totales (${currP})`,
        value: fmtMoneyMM(revCurr),
        sub:
          revGrowth !== null
            ? `${revGrowth >= 0 ? "+" : ""}${revGrowth.toFixed(1)}% ${compLabel}`
            : "Sin período previo",
        trend: revGrowth,
        glossaryKey: "Ingresos Totales",
      },
      {
        title: "Margen Bruto",
        value: fmtPct(gmCurr),
        sub:
          gmDelta !== null
            ? `${gmDelta >= 0 ? "+" : ""}${gmDelta.toFixed(1)} pp ${compLabel} · ${fmtMoneyMM(gpCurr)}`
            : fmtMoneyMM(gpCurr),
        trend: gmDelta,
        glossaryKey: "Margen bruto LTM",
      },
      {
        title: "Margen Operativo (EBIT)",
        value: fmtPct(omCurr),
        sub:
          omDelta !== null
            ? `${omDelta >= 0 ? "+" : ""}${omDelta.toFixed(1)} pp ${compLabel} · ${fmtMoneyMM(ebitCurr)}`
            : fmtMoneyMM(ebitCurr),
        trend: omDelta,
        glossaryKey: "Margen EBIT LTM",
      },
      {
        title: `Beneficio Neto (${currP})`,
        value: fmtMoneyMM(niCurr),
        sub: `Margen neto ${fmtPct(nmCurr)}${niGrowth !== null ? ` (${niGrowth >= 0 ? "+" : ""}${niGrowth.toFixed(1)}%)` : ""}`,
        trend: niGrowth,
        glossaryKey: "Margen neto LTM",
      },
    ];
  } else if (activeContentTab === "Balance de Situación") {
    const cashRow = findMetricRow(financialData, "Balance de Situación", [
      "Efectivo y equivalentes",
    ]);
    const stInvRow = findMetricRow(financialData, "Balance de Situación", [
      "Inversiones a corto plazo",
    ]);
    const stDebtRow = findMetricRow(financialData, "Balance de Situación", [
      "Deuda a corto plazo",
    ]);
    const ltDebtRow = findMetricRow(financialData, "Balance de Situación", [
      "Deuda a largo plazo",
    ]);
    const eqRow = findMetricRow(financialData, "Balance de Situación", [
      "Patrimonio neto",
    ]);
    const caRow = findMetricRow(financialData, "Balance de Situación", [
      "Total activo corriente",
    ]);
    const clRow = findMetricRow(financialData, "Balance de Situación", [
      "Total pasivo corriente",
    ]);

    const cashTotal =
      (numAt(cashRow, currP) || 0) + (numAt(stInvRow, currP) || 0);
    const debtTotal =
      (numAt(stDebtRow, currP) || 0) + (numAt(ltDebtRow, currP) || 0);
    const netDebt = debtTotal - cashTotal;
    const isNetCash = netDebt < 0;

    const eqCurr = numAt(eqRow, currP);
    const eqPrev = numAt(eqRow, prevP);
    const eqGrowth = calcGrowthPct(eqCurr, eqPrev);

    const caCurr = numAt(caRow, currP);
    const clCurr = numAt(clRow, currP);
    const workingCap =
      caCurr !== null && clCurr !== null ? caCurr - clCurr : null;
    const currRatio =
      caCurr !== null && clCurr !== null && clCurr > 0 ? caCurr / clCurr : null;

    cards = [
      {
        title: `Caja e Inv. Corto Plazo (${currP})`,
        value: fmtMoneyMM(cashTotal),
        sub: `Deuda financiera total: ${fmtMoneyMM(debtTotal)}`,
        trend: null,
        glossaryKey: "Efectivo e Inversiones a Corto Plazo",
      },
      {
        title: isNetCash ? "Posición de Caja Neta" : "Deuda Neta",
        value: fmtMoneyMM(Math.abs(netDebt)),
        sub: isNetCash
          ? "La caja supera a la deuda financiera"
          : "Deuda total menos caja disponible",
        trend: isNetCash ? 1 : netDebt > 0 ? -1 : 0,
        glossaryKey: "Deuda neta LTM (MM)",
      },
      {
        title: `Patrimonio Neto (${currP})`,
        value: fmtMoneyMM(eqCurr),
        sub:
          eqGrowth !== null
            ? `${eqGrowth >= 0 ? "+" : ""}${eqGrowth.toFixed(1)}% ${compLabel}`
            : "Capital contable de accionistas",
        trend: eqGrowth,
        glossaryKey: "Patrimonio Neto (Book Value)",
      },
      {
        title: "Capital de Trabajo Neto",
        value: fmtMoneyMM(workingCap),
        sub:
          currRatio !== null
            ? `Liquidez corriente: ${fmtMult(currRatio, "x")}`
            : "Activo corriente - Pasivo corriente",
        trend: workingCap !== null ? (workingCap >= 0 ? 1 : -1) : null,
        glossaryKey: "Capital de Trabajo Neto (NWC)",
      },
    ];
  } else if (activeContentTab === "Estado de Flujo de Efectivo") {
    const cfoRow = findMetricRow(
      financialData,
      "Estado de Flujo de Efectivo",
      ["Efectivo de Operaciones (CFO)"],
    );
    const capexRow = findMetricRow(
      financialData,
      "Estado de Flujo de Efectivo",
      ["Gastos de capital (CapEx)"],
    );
    const fcfRow = findMetricRow(
      financialData,
      "Estado de Flujo de Efectivo",
      ["Flujo de caja libre (FCF)"],
    );

    const cfoCurr = numAt(cfoRow, currP);
    const cfoPrev = numAt(cfoRow, prevP);
    const cfoGrowth = calcGrowthPct(cfoCurr, cfoPrev);

    const capexRaw = numAt(capexRow, currP);
    const capexAbs = capexRaw !== null ? Math.abs(capexRaw) : null;
    const capexIntensity =
      capexAbs !== null && revCurr ? (capexAbs / revCurr) * 100 : null;

    const fcfCurr = numAt(fcfRow, currP);
    const fcfPrev = numAt(fcfRow, prevP);
    const fcfGrowth = calcGrowthPct(fcfCurr, fcfPrev);
    const fcfMargin =
      fcfCurr !== null && revCurr ? (fcfCurr / revCurr) * 100 : null;

    const cashConversion =
      fcfCurr !== null && niCurr && niCurr > 0 ? (fcfCurr / niCurr) * 100 : null;

    cards = [
      {
        title: `Flujo Operativo CFO (${currP})`,
        value: fmtMoneyMM(cfoCurr),
        sub:
          cfoGrowth !== null
            ? `${cfoGrowth >= 0 ? "+" : ""}${cfoGrowth.toFixed(1)}% ${compLabel}`
            : "Caja generada por la operación",
        trend: cfoGrowth,
        glossaryKey: "Efectivo de Operaciones (CFO)",
      },
      {
        title: "Inversión en CapEx",
        value: fmtMoneyMM(capexAbs),
        sub:
          capexIntensity !== null
            ? `${capexIntensity.toFixed(1)}% sobre ingresos totales`
            : "Inversión en activos fijos",
        trend: null,
        glossaryKey: "Gastos de capital (CapEx)",
      },
      {
        title: `Flujo de Caja Libre (${currP})`,
        value: fmtMoneyMM(fcfCurr),
        sub: `Margen FCF ${fmtPct(fcfMargin)}${fcfGrowth !== null ? ` (${fcfGrowth >= 0 ? "+" : ""}${fcfGrowth.toFixed(1)}%)` : ""}`,
        trend: fcfCurr !== null && fcfCurr < 0 ? -1 : fcfGrowth,
        glossaryKey: "Flujo de caja libre (FCF)",
      },
      {
        title: "Conversión FCF / Beneficio Neto",
        value: fmtPct(cashConversion, 0),
        sub:
          cashConversion !== null
            ? cashConversion >= 90
              ? "Alta conversión de ganancias en caja"
              : "Ganancias parcialmente retenidas en CapEx/WC"
            : "Requiere beneficio neto positivo",
        trend:
          cashConversion !== null ? (cashConversion >= 90 ? 1 : 0) : null,
        glossaryKey: "Conversión de FCF (FCF / Beneficio Neto)",
      },
    ];
  } else if (activeContentTab === "Ratios") {
    const roeRow = findMetricRow(financialData, "Ratios", [
      "Rentabilidad sobre capital (ROE) %",
    ]);
    const roaRow = findMetricRow(financialData, "Ratios", [
      "Rentabilidad sobre activos (ROA) %",
    ]);
    const cccRow = findMetricRow(financialData, "Ratios", [
      "Ciclo de conversión de efectivo (CCC) días",
    ]);
    const liqRow = findMetricRow(financialData, "Ratios", [
      "Ratio de liquidez (x)",
    ]);
    const quickRow = findMetricRow(financialData, "Ratios", [
      "Ratio de disponibilidad (Quick Ratio) (x)",
    ]);
    const debtEbitdaRow = findMetricRow(financialData, "Ratios", [
      "Deuda total / EBITDA (x)",
    ]);
    const intCovRow = findMetricRow(financialData, "Ratios", [
      "EBIT / Gastos por intereses (x)",
    ]);

    const roeCurr = numAt(roeRow, currP);
    const roaCurr = numAt(roaRow, currP);
    const cccCurr = numAt(cccRow, currP);
    const liqCurr = numAt(liqRow, currP);
    const quickCurr = numAt(quickRow, currP);
    const debtEbitdaCurr = numAt(debtEbitdaRow, currP);
    const intCovCurr = numAt(intCovRow, currP);

    cards = [
      {
        title: `Rentabilidad ROE (${currP})`,
        value: fmtPct(roeCurr),
        sub: `ROA sobre activos totales: ${fmtPct(roaCurr)}`,
        trend:
          roeCurr !== null ? (roeCurr >= 15 ? 1 : roeCurr < 0 ? -1 : 0) : null,
        glossaryKey: "ROE LTM",
      },
      {
        title: "Ciclo Conversión Efectivo (CCC)",
        value:
          cccCurr !== null && cccCurr !== 0 ? `${cccCurr.toFixed(0)} días` : "-",
        sub: "DSO + DIO − DPO (menor = más eficiente)",
        trend: null,
        glossaryKey: "Ciclo de conversión de efectivo (CCC) días",
      },
      {
        title: "Liquidez Corriente",
        value: fmtMult(liqCurr, "x"),
        sub: `Quick Ratio (prueba ácida): ${fmtMult(quickCurr, "x")}`,
        trend:
          liqCurr !== null ? (liqCurr >= 1.2 ? 1 : liqCurr < 1 ? -1 : 0) : null,
        glossaryKey: "Ratio de liquidez (x)",
      },
      {
        title: "Apalancamiento Deuda / EBITDA",
        value: fmtMult(debtEbitdaCurr, "x"),
        sub:
          intCovCurr !== null && intCovCurr > 0
            ? `Cobertura intereses: ${fmtMult(intCovCurr, "x")}`
            : "Solvencia y carga financiera",
        trend:
          debtEbitdaCurr !== null
            ? debtEbitdaCurr <= 2.5
              ? 1
              : debtEbitdaCurr > 4
                ? -1
                : 0
            : null,
        glossaryKey: "Deuda neta/EBITDA LTM",
      },
    ];
  }

  if (cards.length === 0) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
      {cards.map((c, idx) => {
        const isPos = typeof c.trend === "number" && c.trend > 0;
        const isNeg = typeof c.trend === "number" && c.trend < 0;
        return (
          <div
            key={idx}
            className="bg-white border border-gray-200 rounded-lg px-4 py-3 shadow-sm flex flex-col justify-between"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-500 truncate">
                {c.title}
              </span>
              {c.glossaryKey && onOpenInfo && (
                <button
                  type="button"
                  onClick={() => onOpenInfo(c.glossaryKey, c.value)}
                  title="Ver definición y criterios de lectura"
                  className="text-gray-400 hover:text-orange-500 transition-colors cursor-pointer shrink-0"
                >
                  <Info className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            <div className="mt-1.5 flex items-baseline justify-between gap-2">
              <span className="text-lg font-bold text-gray-900 tracking-tight">
                {c.value}
              </span>
              {isPos && (
                <span className="inline-flex items-center text-[11px] font-semibold text-emerald-600">
                  <TrendingUp className="w-3.5 h-3.5 mr-0.5" />
                </span>
              )}
              {isNeg && (
                <span className="inline-flex items-center text-[11px] font-semibold text-[#d93025]">
                  <TrendingDown className="w-3.5 h-3.5 mr-0.5" />
                </span>
              )}
            </div>

            <p className="mt-1 text-[11px] text-gray-500 truncate" title={c.sub}>
              {c.sub}
            </p>
          </div>
        );
      })}
    </div>
  );
}