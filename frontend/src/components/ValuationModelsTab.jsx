import { useEffect, useMemo, useState } from "react";
import apiClient from "../api/client";
import {
  Calculator,
  Search,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  RotateCcw,
  SlidersHorizontal,
  Sparkles,
  Landmark,
  Coins,
  BarChart2,
  Info,
  HelpCircle,
} from "lucide-react";

function formatMoney(val) {
  if (val === null || val === undefined || Number.isNaN(val)) return "-";
  const isNeg = val < 0;
  const formatted = new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(val));
  return isNeg ? `(US$ ${formatted})` : `US$ ${formatted}`;
}

function formatMoney0(val) {
  if (val === null || val === undefined || Number.isNaN(val)) return "-";
  const isNeg = val < 0;
  const formatted = new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Math.abs(val));
  return isNeg ? `(US$ ${formatted})` : `US$ ${formatted}`;
}

const MODEL_CATALOG = [
  {
    id: "dcf",
    name: "DCF 2 Etapas (FCFF)",
    shortDesc: "Flujo de Caja Libre Descontado",
    icon: Calculator,
    howItWorks:
      "Calcula cuánto efectivo libre generará el negocio para todos sus proveedores de capital en los próximos 5 años más su valor a perpetuidad, descontado a valor presente según el riesgo (WACC) y restando la deuda neta.",
    bestFor: "Corporativos no financieros, industria, consumo y tecnología con flujo de caja positivo.",
    avoidIn: "Bancos, aseguradoras y financieras (la deuda es materia prima operativa y no existe FCF industrial).",
  },
  {
    id: "excess_return",
    name: "Excess Return (ROE)",
    shortDesc: "Retorno Excedente sobre Patrimonio",
    icon: Landmark,
    howItWorks:
      "Parte del Patrimonio Neto actual por acción (Valor Libros) y le suma el valor presente de las ganancias que superan el retorno mínimo exigido por el accionista (ROE − Ke). Si un banco rinde más que su costo de capital, vale más que su valor libros.",
    bestFor: "Bancos comerciales, aseguradoras, financieras y entidades reguladas por capital.",
    avoidIn: "Empresas tecnológicas asset-light con alto intangibles/recompras donde el Valor Libros contable es bajo.",
  },
  {
    id: "ddm",
    name: "DDM (Dividendos)",
    shortDesc: "Descuento de Dividendos 2 Etapas",
    icon: Coins,
    howItWorks:
      "Valúa la acción exclusivamente por el flujo futuro de dividendos en efectivo que recibirá el accionista (etapa de crecimiento inicial de 5 años + crecimiento perpetuo estable), descontados al Costo de Equity (Ke).",
    bestFor: "Utilities, REITs, consumo maduro y empresas con política estable de dividendos crecientes.",
    avoidIn: "Empresas de alto crecimiento que reinvierten el 100% de sus utilidades o recompran acciones en lugar de pagar dividendos.",
  },
  {
    id: "multiples",
    name: "Múltiplos Normalizados",
    shortDesc: "Valuación Relativa Histórica (5Y)",
    icon: BarChart2,
    howItWorks:
      "Estima cuánto valdría hoy la acción si el mercado volviera a pagar exactamente la mediana histórica de sus propios múltiplos de los últimos 5 años (EV/EBITDA, P/E, P/FCF o P/BV) sobre sus resultados actuales.",
    bestFor: "Triangulación rápida contra la mediana histórica propia de 5 años (EV/EBITDA, P/E, P/FCF, P/BV).",
    avoidIn: "Empresas en reestructuración o con ganancias/EBITDA cíclicamente deprimidos o negativos.",
  },
];

function evaluateSuitability(modelId, routingProfile, hasDividends) {
  const isFinancial = routingProfile === "financial";
  const isReit = routingProfile === "reit";

  if (modelId === "dcf") {
    if (isFinancial) {
      return {
        level: "invalid",
        badge: "No Recomendado en Sector Financiero",
        message:
          "ADVERTENCIA METODOLÓGICA: El DCF tradicional (FCFF) no es válido para bancos ni aseguradoras porque los depósitos y pasivos financieros forman parte del negocio operativo. Seleccioná el modelo Excess Return (ROE).",
      };
    }
    return {
      level: "optimal",
      badge: "Método Estándar para este Sector",
      message:
        "Válido para este emisor. Se proyecta una Etapa 1 de expansión (5 años) y una Etapa 2 estacionaria donde el CapEx converge a mantenimiento.",
    };
  }

  if (modelId === "excess_return") {
    if (isFinancial) {
      return {
        level: "optimal",
        badge: "Método Estándar para Bancos y Financieras",
        message:
          "Válido y recomendado. Valúa el Patrimonio Neto actual más el valor presente del retorno excedente (ROE − Ke) generado sobre el capital.",
      };
    }
    return {
      level: "caution",
      badge: "Uso Secundario fuera de Financieras",
      message:
        "ADVERTENCIA METODOLÓGICA: Este modelo fue diseñado para bancos y aseguradoras. En empresas industriales o tecnológicas con recompras de acciones o fuertes intangibles, el Valor Libros contable subestima el capital económico.",
    };
  }

  if (modelId === "ddm") {
    if (!hasDividends) {
      return {
        level: "invalid",
        badge: "Sin Dividendo Relevante Reportado",
        message:
          "ADVERTENCIA METODOLÓGICA: La empresa no paga dividendos significativos o su payout es mínimo. Aplicar DDM subvaluará severamente la compañía al ignorar la caja retenida o recompras.",
      };
    }
    if (isReit) {
      return {
        level: "optimal",
        badge: "Adecuado para REITs / Distribución",
        message:
          "Válido para emisores que distribuyen regularmente una fracción alta de su flujo recurrente vía dividendos.",
      };
    }
    return {
      level: "caution",
      badge: "Válido solo si el Payout es Estable",
      message:
        "Asegurate de que el dividendo esté respaldado por el FCF y no financiado con deuda; si la empresa prefiere recomprar acciones, priorizá DCF.",
    };
  }

  return {
    level: "optimal",
    badge: "Referencia Relativa Histórica",
    message: isFinancial
      ? "Aplica las medianas históricas de 5 años de P/E, P/BV y P/TBV sobre el beneficio y patrimonio actual."
      : "Aplica las medianas históricas de 5 años (EV/EBITDA, P/E y P/FCF) sobre los resultados operativos LTM.",
  };
}

function RangeSliderWithNumber({
  value,
  min,
  max,
  step,
  onChange,
  accentClass = "accent-orange-500",
  unit = "%",
  ariaLabel,
}) {
  return (
    <div className="flex items-center gap-2 mt-1.5">
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-label={ariaLabel}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className={`flex-1 ${accentClass} cursor-pointer`}
      />
      <div className="flex items-center gap-0.5 shrink-0">
        <input
          type="number"
          min={min}
          max={max}
          step={step}
          value={Number.isFinite(value) ? value : 0}
          aria-label={ariaLabel ? `${ariaLabel} numérico` : undefined}
          onChange={(e) => {
            const parsed = parseFloat(e.target.value);
            if (!Number.isNaN(parsed)) {
              onChange(Math.min(Math.max(parsed, min), max));
            }
          }}
          className="w-16 px-1.5 py-0.5 text-right text-[11px] font-semibold tabular-nums rounded border border-gray-300 bg-white text-gray-800 focus:outline-none focus:border-orange-500"
        />
        {unit && <span className="text-[11px] font-semibold text-gray-500">{unit}</span>}
      </div>
    </div>
  );
}

export default function ValuationModelsTab({
  initialTicker = "",
  recentTickers = [],
  onSelectGlobalTicker,
  onOpenInfo,
}) {
  const [selectedTicker, setSelectedTicker] = useState(
    initialTicker ? initialTicker.toUpperCase() : ""
  );
  const [searchInput, setSearchInput] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);

  const [valData, setValData] = useState(null);
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [selectedModel, setSelectedModel] = useState("dcf");
  const [workMode, setWorkMode] = useState("auto"); // 'auto' | 'manual'

  // Parámetros DCF (Auto / Manual)
  const [revGrowth, setRevGrowth] = useState(10.0);
  const [targetEbitMargin, setTargetEbitMargin] = useState(18.0);
  const [wacc, setWacc] = useState(9.0);
  const [terminalGrowth, setTerminalGrowth] = useState(3.0);
  const [capexStage1Pct, setCapexStage1Pct] = useState(12.0);
  const [capexTerminalPct, setCapexTerminalPct] = useState(8.0);
  const [exitMultiple, setExitMultiple] = useState(20.0);
  const [extraAdjMm, setExtraAdjMm] = useState(0);

  // Parámetros Excess Return (Bancos)
  const [bankRoe, setBankRoe] = useState(15.0);
  const [bankKe, setBankKe] = useState(9.5);
  const [bankPayout, setBankPayout] = useState(35.0);
  const [bankExitPtbv, setBankExitPtbv] = useState(1.8);

  // Parámetros DDM (Dividendos)
  const [ddmDivPerShare, setDdmDivPerShare] = useState(0.0);
  const [ddmGrowthStage1, setDdmGrowthStage1] = useState(6.0);
  const [ddmTerminalGrowth, setDdmTerminalGrowth] = useState(3.0);
  const [ddmKe, setDdmKe] = useState(9.0);

  const applyDefaultsFromPayload = (vPayload, pPayload) => {
    const routing = vPayload?.sector_routing?.profile || "standard";
    const inp = vPayload?.dcf_inputs || {};
    const fInp = vPayload?.financial_sector_inputs || {};
    const divRate = Number(
      pPayload?.summary_metrics?.valuation?.dividend_rate ??
        pPayload?.summary_metrics?.dividend?.dividend_rate ??
        0
    );

    if (routing === "financial") {
      setSelectedModel("excess_return");
    } else {
      setSelectedModel("dcf");
    }

    setRevGrowth(Number(inp.recommended_rev_growth_pct ?? 10.0));
    setTargetEbitMargin(
      Number(inp.target_ebit_margin_pct ?? inp.ebit_margin_pct ?? 18.0)
    );
    setWacc(Number(inp.suggested_wacc_pct ?? 9.0));
    setTerminalGrowth(3.0);
    setCapexStage1Pct(Number(inp.capex_expansion_pct ?? 12.0));
    setCapexTerminalPct(Number(inp.capex_maintenance_pct ?? 8.0));
    setExitMultiple(Number(inp.exit_multiple_default ?? 20.0));
    setExtraAdjMm(0);

    setBankRoe(Number(fInp.roe_pct ?? 15.0));
    setBankKe(Number(fInp.cost_of_equity_pct ?? 9.5));
    setBankPayout(Number(fInp.payout_ratio_pct ?? 35.0));
    setBankExitPtbv(Number(fInp.exit_ptbv_default ?? 1.8));

    setDdmDivPerShare(divRate > 0 ? divRate : 0);
    setDdmGrowthStage1(
      Math.min(Math.max(Number(inp.recommended_rev_growth_pct ?? 6.0), 2.0), 14.0)
    );
    setDdmTerminalGrowth(3.0);
    setDdmKe(Number(fInp.cost_of_equity_pct ?? inp.suggested_wacc_pct ?? 9.0));
  };

  useEffect(() => {
    if (!selectedTicker) return;
    let cancelled = false;

    const loadCompanyModelData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [vRes, pRes] = await Promise.all([
          apiClient.get(
            `/company/${selectedTicker}/valuation`
          ),
          apiClient.get(
            `/company/${selectedTicker}/profile`
          ),
        ]);
        if (!cancelled) {
          setValData(vRes.data);
          setProfileData(pRes.data);
          applyDefaultsFromPayload(vRes.data, pRes.data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err.response?.data?.detail ||
              "No se pudieron cargar los datos contables para modelar este ticker."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadCompanyModelData();
    return () => {
      cancelled = true;
    };
  }, [selectedTicker]);

  const handleSearchChange = async (e) => {
    const val = e.target.value;
    setSearchInput(val);
    if (val.trim().length > 0) {
      try {
        const res = await apiClient.get(
          `/search?q=${encodeURIComponent(val.trim())}`
        );
        setSearchResults(res.data || []);
        setShowDropdown(true);
      } catch {
        setSearchResults([]);
      }
    } else {
      setSearchResults([]);
      setShowDropdown(false);
    }
  };

  const handleChooseTicker = (sym) => {
    const clean = (sym || "").toUpperCase().trim();
    if (!clean) return;
    setSelectedTicker(clean);
    setSearchInput("");
    setShowDropdown(false);
    setWorkMode("auto");
    if (onSelectGlobalTicker) {
      onSelectGlobalTicker(clean);
    }
  };

  // ===========================================================================
  // CÁLCULO 1: DCF EN 2 ETAPAS + MATRIZ DE SENSIBILIDAD
  // ===========================================================================
  const dcfOutput = useMemo(() => {
    const inp = valData?.dcf_inputs;
    if (!inp || !inp.shares_mm || inp.shares_mm <= 0) return null;

    const rev0 = Number(inp.revenue_base_mm || 0);
    const startMargin = Number(inp.ebit_margin_pct || 15.0) / 100;
    const endMargin = Number(targetEbitMargin) / 100;
    const taxRate = Number(inp.tax_rate_pct || 21.0) / 100;
    const daPct = Number(inp.da_sales_pct || 8.0) / 100;

    const g = revGrowth / 100;
    const r = wacc / 100;
    const gTerm = terminalGrowth / 100;
    const capex1 = capexStage1Pct / 100;
    const capexTerm = capexTerminalPct / 100;

    if (r <= gTerm || rev0 <= 0) return { invalid: true };

    const projections = [];
    let pvStage1 = 0;
    let revCurr = rev0;
    const nwcPctOfDeltaRev = Number(inp.nwc_pct_of_delta_rev ?? 0.02);

    for (let yr = 1; yr <= 5; yr += 1) {
      const prevRev = revCurr;
      // Fade gradual hacia crecimiento terminal en los años 4 y 5
      const gYr = yr <= 3 ? g : g + ((gTerm - g) * (yr - 3)) / 2;
      revCurr = revCurr * (1 + gYr);
      const deltaNwc = Math.max(revCurr - prevRev, 0) * nwcPctOfDeltaRev;
      const marginYr = startMargin + ((endMargin - startMargin) * yr) / 5;
      const nopat = revCurr * marginYr * (1 - taxRate);
      const da = revCurr * daPct;
      const capex = revCurr * capex1;
      const fcf = nopat + da - capex - deltaNwc + Number(extraAdjMm || 0);
      const pv = fcf / (1 + r) ** yr;
      pvStage1 += pv;

      projections.push({
        year: `Año +${yr}`,
        rev: revCurr,
        ebitMarginPct: marginYr * 100,
        fcf,
        pv,
      });
    }

    const rev6 = revCurr * (1 + gTerm);
    const deltaNwcTerm = Math.max(rev6 - revCurr, 0) * nwcPctOfDeltaRev;
    const steadyFcf6 =
      rev6 * (endMargin * (1 - taxRate) + daPct - capexTerm) -
      deltaNwcTerm +
      Number(extraAdjMm || 0);
    const tvGordon = steadyFcf6 / (r - gTerm);
    const priceGordon =
      (pvStage1 + tvGordon / (1 + r) ** 5 - Number(inp.net_debt_mm || 0)) /
      inp.shares_mm;

    const normFcf5 =
      revCurr * (endMargin * (1 - taxRate) + daPct - capexTerm) +
      Number(extraAdjMm || 0);
    const tvMult = normFcf5 * exitMultiple;
    const priceMult =
      (pvStage1 + tvMult / (1 + r) ** 5 - Number(inp.net_debt_mm || 0)) /
      inp.shares_mm;

    const blendedIntrinsic = (priceGordon + priceMult) / 2;
    const upsidePct =
      inp.current_price > 0
        ? ((blendedIntrinsic - inp.current_price) / inp.current_price) * 100
        : 0;

    const fcf5Raw = projections[4]?.fcf || 0;
    const tvRaw = (fcf5Raw * (1 + gTerm)) / (r - gTerm);
    const priceUnadjustedCapex =
      (pvStage1 + tvRaw / (1 + r) ** 5 - Number(inp.net_debt_mm || 0)) /
      inp.shares_mm;

    const waccSteps = [
      Math.max(r - 0.01, gTerm + 0.005),
      Math.max(r - 0.005, gTerm + 0.005),
      r,
      r + 0.005,
      r + 0.01,
    ];
    const gSteps = [
      Math.max(gTerm - 0.01, 0),
      Math.max(gTerm - 0.005, 0),
      gTerm,
      gTerm + 0.005,
      gTerm + 0.01,
    ];

    const sensitivityMatrix = waccSteps.map((wVal) => ({
      waccPct: wVal * 100,
      cells: gSteps.map((gVal) => {
        if (wVal <= gVal) return null;
        let pv1 = 0;
        let rv = rev0;
        for (let y = 1; y <= 5; y += 1) {
          rv *= 1 + g;
          const mY = startMargin + ((endMargin - startMargin) * y) / 5;
          const fY =
            rv * (mY * (1 - taxRate) + daPct - capex1) + Number(extraAdjMm || 0);
          pv1 += fY / (1 + wVal) ** y;
        }
        const f6 =
          rv * (1 + gVal) * (endMargin * (1 - taxRate) + daPct - capexTerm) +
          Number(extraAdjMm || 0);
        const tv = f6 / (wVal - gVal);
        return (pv1 + tv / (1 + wVal) ** 5 - Number(inp.net_debt_mm || 0)) / inp.shares_mm;
      }),
    }));

    return {
      invalid: false,
      projections,
      steadyFcf6,
      priceGordon,
      priceMult,
      intrinsicPrice: blendedIntrinsic,
      upsidePct,
      priceUnadjustedCapex,
      gStepsPct: gSteps.map((x) => x * 100),
      sensitivityMatrix,
    };
  }, [
    valData,
    revGrowth,
    targetEbitMargin,
    wacc,
    terminalGrowth,
    capexStage1Pct,
    capexTerminalPct,
    exitMultiple,
    extraAdjMm,
  ]);

  // ===========================================================================
  // CÁLCULO 2: EXCESS RETURN (BANCOS Y FINANCIERAS)
  // ===========================================================================
  const excessReturnOutput = useMemo(() => {
    const fInp = valData?.financial_sector_inputs;
    if (!fInp || !fInp.bvps || fInp.bvps <= 0) return null;

    const roe = bankRoe / 100;
    const ke = bankKe / 100;
    const payout = bankPayout / 100;
    const retention = 1 - payout;
    const gStage1 = Math.min(Math.max(roe * retention, 0.01), 0.14);
    const gTerm = Math.min(gStage1, 0.045);

    if (ke <= gTerm) return { invalid: true };

    let bvCurr = Number(fInp.bvps);
    let pvExcess = 0;
    let pvDivs = 0;
    const rows = [];

    for (let yr = 1; yr <= 5; yr += 1) {
      const eps = bvCurr * roe;
      const div = eps * payout;
      const excess = eps - bvCurr * ke;
      const pvE = excess / (1 + ke) ** yr;
      pvExcess += pvE;
      pvDivs += div / (1 + ke) ** yr;
      rows.push({
        year: `Año +${yr}`,
        bvps: bvCurr,
        eps,
        excessReturn: excess,
        pvExcess: pvE,
      });
      bvCurr *= 1 + gStage1;
    }

    const terminalRoe = ke + (roe - ke) * 0.5;
    const tvExcess = (bvCurr * (terminalRoe - ke)) / (ke - gTerm);
    const priceExcess = Number(fInp.bvps) + pvExcess + tvExcess / (1 + ke) ** 5;

    const tbvRatio =
      fInp.bvps > 0 ? Number(fInp.tbvps || fInp.bvps) / Number(fInp.bvps) : 1;
    const pricePtbv =
      pvDivs + (bvCurr * tbvRatio * bankExitPtbv) / (1 + ke) ** 5;

    const blended = (priceExcess + pricePtbv) / 2;
    const upsidePct =
      fInp.current_price > 0
        ? ((blended - fInp.current_price) / fInp.current_price) * 100
        : 0;

    return {
      invalid: false,
      rows,
      priceExcess,
      pricePtbv,
      intrinsicPrice: blended,
      upsidePct,
      impliedPb: fInp.bvps > 0 ? priceExcess / fInp.bvps : 0,
    };
  }, [valData, bankRoe, bankKe, bankPayout, bankExitPtbv]);

  // ===========================================================================
  // CÁLCULO 3: DDM (DESCUENTO DE DIVIDENDOS EN 2 ETAPAS)
  // ===========================================================================
  const ddmOutput = useMemo(() => {
    const curPrice = Number(valData?.dcf_inputs?.current_price || 0);
    const d0 = Number(ddmDivPerShare || 0);
    const g1 = ddmGrowthStage1 / 100;
    const gTerm = ddmTerminalGrowth / 100;
    const ke = ddmKe / 100;

    if (d0 <= 0) return { noDividend: true };
    if (ke <= gTerm) return { invalid: true };

    let pvDivs = 0;
    let dCurr = d0;
    const rows = [];
    for (let yr = 1; yr <= 5; yr += 1) {
      dCurr = dCurr * (1 + g1);
      const pv = dCurr / (1 + ke) ** yr;
      pvDivs += pv;
      rows.push({ year: `Año +${yr}`, dividend: dCurr, pv });
    }

    const d6 = dCurr * (1 + gTerm);
    const tv = d6 / (ke - gTerm);
    const intrinsicPrice = pvDivs + tv / (1 + ke) ** 5;
    const upsidePct =
      curPrice > 0 ? ((intrinsicPrice - curPrice) / curPrice) * 100 : 0;

    return {
      invalid: false,
      noDividend: false,
      rows,
      d6,
      intrinsicPrice,
      upsidePct,
    };
  }, [valData, ddmDivPerShare, ddmGrowthStage1, ddmTerminalGrowth, ddmKe]);

  // ===========================================================================
  // CÁLCULO 4: MÚLTIPLOS NORMALIZADOS (MEDIANA HISTÓRICA 5Y)
  // ===========================================================================
  const multiplesOutput = useMemo(() => {
    const rows = valData?.rows || [];
    const inp = valData?.dcf_inputs || {};
    const curPrice = Number(inp.current_price || 0);
    if (!rows.length || curPrice <= 0) return null;

    const impliedTargets = [];
    const candidateLabels = [
      "EV / EBITDA (LTM)",
      "Precio / Beneficio (P/E)",
      "Precio / Flujo de Caja Libre (P/FCF)",
      "Precio / Valor Libros (P/BV)",
    ];

    candidateLabels.forEach((label) => {
      const r = rows.find((item) => item.metric === label);
      if (
        r &&
        typeof r.ltm === "number" &&
        r.ltm > 0 &&
        typeof r.med_5y === "number" &&
        r.med_5y > 0
      ) {
        const implied = curPrice * (r.med_5y / r.ltm);
        impliedTargets.push({
          metric: label,
          ltm: r.ltm,
          med5y: r.med_5y,
          impliedPrice: implied,
        });
      }
    });

    if (!impliedTargets.length) return { empty: true };

    const avgImplied =
      impliedTargets.reduce((acc, it) => acc + it.impliedPrice, 0) /
      impliedTargets.length;
    const upsidePct = ((avgImplied - curPrice) / curPrice) * 100;

    return {
      empty: false,
      targets: impliedTargets,
      intrinsicPrice: avgImplied,
      upsidePct,
    };
  }, [valData]);

  // ===========================================================================
  // PANTALLA INICIAL VACÍA (SI NO HAY EMPRESA SELECCIONADA TODAVÍA)
  // ===========================================================================
  if (!selectedTicker) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-10 text-center max-w-3xl mx-auto mt-6">
        <div className="w-12 h-12 rounded-xl bg-orange-50 text-orange-500 flex items-center justify-center mx-auto mb-4">
          <Calculator className="w-6 h-6" />
        </div>
        <h2 className="text-lg font-bold text-gray-900">
          Modelos de Valuación Fundamental
        </h2>
        <p className="text-xs text-gray-600 max-w-xl mx-auto mt-1.5 leading-relaxed">
          Seleccioná una empresa para calcular su valor intrínseco en{" "}
          <strong>Modo Automático</strong> (auditado con SEC/EDGAR y consenso) o
          en <strong>Modo Manual</strong> parametrizando tus propios supuestos
          (DCF 2 Etapas, Excess Return, DDM y Múltiplos Normalizados).
        </p>

        <div className="relative max-w-md mx-auto mt-6 text-left">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={searchInput}
            onChange={handleSearchChange}
            onKeyDown={(e) => {
              if (e.key === "Enter" && searchInput.trim()) {
                handleChooseTicker(searchInput.trim());
              }
            }}
            onBlur={() => setShowDropdown(false)}
            placeholder="Buscá un ticker o empresa (ej: MSFT, MELI, JPM, NVDA)..."
            autoFocus
            className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-300 rounded-lg text-xs text-gray-900 focus:outline-none focus:bg-white focus:border-orange-500 shadow-2xs"
          />
          {showDropdown && searchResults.length > 0 && (
            <div className="absolute top-full left-0 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-xl z-30 overflow-hidden">
              {searchResults.map((r, i) => (
                <div
                  key={i}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => handleChooseTicker(r.ticker)}
                  className="px-3.5 py-2.5 hover:bg-orange-50 cursor-pointer flex items-center justify-between text-xs border-b border-gray-100 last:border-0"
                >
                  <span className="font-bold text-orange-600 mr-3">
                    {r.ticker}
                  </span>
                  <span className="text-gray-700 truncate flex-1">{r.name}</span>
                  <span className="text-[10px] text-gray-400 uppercase ml-2">
                    {r.type}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {recentTickers.length > 0 && (
          <div className="mt-6 pt-5 border-t border-gray-100">
            <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2.5">
              Consultadas recientemente
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {recentTickers.map((rt) => (
                <button
                  key={rt.ticker}
                  type="button"
                  onClick={() => handleChooseTicker(rt.ticker)}
                  className="px-3 py-1.5 rounded-lg border border-gray-200 bg-gray-50 hover:bg-orange-50 hover:border-orange-300 text-xs font-semibold text-gray-800 cursor-pointer transition-colors"
                >
                  <span className="text-orange-600 mr-1.5">{rt.ticker}</span>
                  <span className="text-gray-500 font-normal">{rt.name}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  const routing = valData?.sector_routing || {
    profile: "standard",
    label: "Corporativo Estándar",
  };
  const audit = valData?.audit || { has_anomalies: false, flags: [] };
  const inp = valData?.dcf_inputs || {};
  const finInp = valData?.financial_sector_inputs || {};
  const currentPrice = Number(inp.current_price || 0);
  const hasDividends =
    Number(
      profileData?.summary_metrics?.valuation?.dividend_rate ??
        profileData?.summary_metrics?.dividend?.dividend_rate ??
        0
    ) > 0;

  const activeCatalogItem =
    MODEL_CATALOG.find((m) => m.id === selectedModel) || MODEL_CATALOG[0];

  const suitability = evaluateSuitability(
    selectedModel,
    routing.profile,
    hasDividends
  );

  let activeIntrinsic = null;
  let activeUpside = null;
  if (selectedModel === "dcf" && dcfOutput && !dcfOutput.invalid) {
    activeIntrinsic = dcfOutput.intrinsicPrice;
    activeUpside = dcfOutput.upsidePct;
  } else if (
    selectedModel === "excess_return" &&
    excessReturnOutput &&
    !excessReturnOutput.invalid
  ) {
    activeIntrinsic = excessReturnOutput.intrinsicPrice;
    activeUpside = excessReturnOutput.upsidePct;
  } else if (
    selectedModel === "ddm" &&
    ddmOutput &&
    !ddmOutput.invalid &&
    !ddmOutput.noDividend
  ) {
    activeIntrinsic = ddmOutput.intrinsicPrice;
    activeUpside = ddmOutput.upsidePct;
  } else if (
    selectedModel === "multiples" &&
    multiplesOutput &&
    !multiplesOutput.empty
  ) {
    activeIntrinsic = multiplesOutput.intrinsicPrice;
    activeUpside = multiplesOutput.upsidePct;
  }

  return (
    <div className="space-y-5 text-xs">
      {/* BARRA SUPERIOR: BUSCADOR DE EMPRESA + MODO AUTOMÁTICO VS MANUAL */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gray-900 text-orange-400 font-bold text-base flex items-center justify-center shrink-0">
              {selectedTicker.charAt(0)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-gray-900">
                  {selectedTicker}
                </h2>
                <span className="text-gray-500 font-medium">
                  {profileData?.name || ""}
                </span>
                <span className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200 text-[11px] font-semibold text-gray-700">
                  {routing.label}
                </span>
              </div>
              <p className="text-[11px] text-gray-500 mt-0.5">
                Cotización actual:{" "}
                <strong className="text-gray-900">
                  {formatMoney(currentPrice)}
                </strong>{" "}
                · Consenso WS:{" "}
                <strong className="text-gray-800">
                  {inp.target_price ? formatMoney(inp.target_price) : "-"}
                </strong>
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="relative w-64">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchInput}
                onChange={handleSearchChange}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && searchInput.trim()) {
                    handleChooseTicker(searchInput.trim());
                  }
                }}
                onBlur={() => setShowDropdown(false)}
                placeholder="Cambiar empresa (ej: NVDA, JPM)..."
                className="w-full pl-8 pr-3 py-1.5 bg-gray-50 border border-gray-300 rounded-lg text-xs text-gray-900 focus:outline-none focus:bg-white focus:border-orange-500"
              />
              {showDropdown && searchResults.length > 0 && (
                <div className="absolute top-full left-0 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-xl z-40 overflow-hidden">
                  {searchResults.map((r, i) => (
                    <div
                      key={i}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => handleChooseTicker(r.ticker)}
                      className="px-3 py-2 hover:bg-orange-50 cursor-pointer flex items-center justify-between text-xs border-b border-gray-100 last:border-0"
                    >
                      <span className="font-bold text-orange-600">
                        {r.ticker}
                      </span>
                      <span className="text-gray-700 truncate mx-2 flex-1">
                        {r.name}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="inline-flex rounded-lg border border-gray-300 bg-gray-100 p-0.5">
              <button
                type="button"
                onClick={() => {
                  setWorkMode("auto");
                  if (valData) applyDefaultsFromPayload(valData, profileData);
                }}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold inline-flex items-center gap-1.5 transition-colors cursor-pointer ${
                  workMode === "auto"
                    ? "bg-white text-orange-600 shadow-2xs"
                    : "text-gray-600 hover:text-gray-900"
                }`}
              >
                <Sparkles className="w-3.5 h-3.5" />
                Modo Automático
              </button>
              <button
                type="button"
                onClick={() => setWorkMode("manual")}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold inline-flex items-center gap-1.5 transition-colors cursor-pointer ${
                  workMode === "manual"
                    ? "bg-gray-900 text-white shadow-2xs"
                    : "text-gray-600 hover:text-gray-900"
                }`}
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
                Modo Manual (Supuestos)
              </button>
            </div>
          </div>
        </div>

        {/* Selector de los 4 métodos estándar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 mt-4 pt-4 border-t border-gray-100">
          {MODEL_CATALOG.map((m) => {
            const Icon = m.icon;
            const active = selectedModel === m.id;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => setSelectedModel(m.id)}
                className={`p-3 rounded-lg border text-left transition-all cursor-pointer ${
                  active
                    ? "bg-orange-50/70 border-orange-400 ring-1 ring-orange-400"
                    : "bg-gray-50/70 border-gray-200 hover:bg-gray-100"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-gray-900 flex items-center gap-1.5">
                    <Icon
                      className={`w-3.5 h-3.5 ${
                        active ? "text-orange-600" : "text-gray-500"
                      }`}
                    />
                    {m.name}
                  </span>
                </div>
                <p className="text-[11px] text-gray-500 mt-1">{m.shortDesc}</p>
              </button>
            );
          })}
        </div>

        {/* GUÍA DIDÁCTICA DEL MODELO SELECCIONADO */}
        <div className="mt-3.5 p-3.5 rounded-lg bg-slate-50 border border-slate-200/90 flex items-start gap-2.5 text-[11.5px] text-slate-700 leading-relaxed">
          <HelpCircle className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p>
              <strong className="text-slate-900">
                ¿Cómo calcula el valor este modelo ({activeCatalogItem.name})?
              </strong>{" "}
              {activeCatalogItem.howItWorks}
            </p>
            <p className="text-[11px] text-slate-600">
              <strong className="text-emerald-800">Ideal para:</strong> {activeCatalogItem.bestFor}{" "}
              <span className="mx-1.5 text-slate-300">|</span>
              <strong className="text-amber-800">Evitar en:</strong> {activeCatalogItem.avoidIn}
            </p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="bg-white border border-gray-200 rounded-xl p-16 flex flex-col items-center justify-center text-orange-500">
          <Loader2 className="w-8 h-8 mb-2 animate-spin" />
          <p className="font-medium">
            Extrayendo estados SEC/EDGAR y calibrando modelos para{" "}
            {selectedTicker}...
          </p>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center text-red-700 font-semibold">
          {error}
        </div>
      ) : (
        valData && (
          <>
            {/* BANNER DE APLICABILIDAD SECTORIAL DEL MÉTODO ELEGIDO */}
            <div
              className={`rounded-xl border p-4 flex items-start gap-3 ${
                suitability.level === "invalid"
                  ? "bg-red-50 border-red-200 text-red-950"
                  : suitability.level === "caution"
                  ? "bg-amber-50 border-amber-200 text-amber-950"
                  : "bg-emerald-50/70 border-emerald-200 text-emerald-950"
              }`}
            >
              {suitability.level === "optimal" ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle
                  className={`w-4 h-4 shrink-0 mt-0.5 ${
                    suitability.level === "invalid"
                      ? "text-red-600"
                      : "text-amber-600"
                  }`}
                />
              )}
              <div>
                <p className="font-bold">{suitability.badge}</p>
                <p className="text-[11px] mt-0.5 leading-relaxed">
                  {suitability.message}
                </p>
              </div>
            </div>

            {/* ALERTAS DE ANOMALÍAS CONTABLES */}
            {audit.has_anomalies && (
              <div className="bg-amber-50/80 border border-amber-300 rounded-xl p-4 space-y-2">
                <div className="flex items-center gap-2 font-bold text-amber-950">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  <span>
                    Detector de Distorsiones Contables en {selectedTicker} (Impacto en Valuación)
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                  {audit.flags.map((f) => (
                    <div
                      key={f.code}
                      className="bg-white border border-amber-200 rounded-lg p-3 text-[11px]"
                    >
                      <p className="font-bold text-gray-900">{f.title}</p>
                      <p className="text-gray-600 mt-1 leading-relaxed">
                        {f.detail}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TARJETA DE VEREDICTO SINTÉTICO (PRECIO INTRÍNSECO VS COTIZACIÓN) */}
            {activeIntrinsic !== null && activeUpside !== null && (
              <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400">
                    Resultado del Modelo ·{" "}
                    {workMode === "auto"
                      ? "Calibración Automática"
                      : "Simulación Manual"}
                  </span>
                  <div className="flex items-baseline gap-3 mt-1">
                    <span className="text-2xl font-extrabold text-gray-900">
                      Valor Intrínseco: {formatMoney(activeIntrinsic)}
                    </span>
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                        activeUpside >= 12
                          ? "bg-emerald-100 text-emerald-800"
                          : activeUpside <= -12
                          ? "bg-red-100 text-red-800"
                          : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {activeUpside >= 12
                        ? `Subvaluada (${activeUpside >= 0 ? "+" : ""}${activeUpside.toFixed(1)}% potencial)`
                        : activeUpside <= -12
                        ? `Sobrevaluada (${activeUpside.toFixed(1)}% vs. precio)`
                        : `En Rango Justo (${activeUpside >= 0 ? "+" : ""}${activeUpside.toFixed(1)}%)`}
                    </span>
                  </div>
                </div>

                {workMode === "manual" && (
                  <button
                    type="button"
                    onClick={() => applyDefaultsFromPayload(valData, profileData)}
                    className="inline-flex items-center px-3 py-1.5 rounded-lg border border-gray-300 bg-gray-50 hover:bg-gray-100 text-xs font-semibold text-gray-700 cursor-pointer"
                  >
                    <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
                    Restablecer supuestos base
                  </button>
                )}
              </div>
            )}

            {/* =============================================================== */}
            {/* DETALLE MODELO 1: DCF 2 ETAPAS (FCFF)                           */}
            {/* =============================================================== */}
            {selectedModel === "dcf" && dcfOutput && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                <div className="lg:col-span-5 bg-white border border-gray-200 rounded-xl shadow-sm p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-gray-100 pb-2.5">
                    <h3 className="text-sm font-bold text-gray-900">
                      {workMode === "auto"
                        ? "Supuestos Calibrados Automáticamente"
                        : "Panel de Supuestos Manuales (DCF)"}
                    </h3>
                    <span className="text-[11px] text-orange-600 font-semibold">
                      {workMode === "auto" ? "Solo lectura" : "Editable"}
                    </span>
                  </div>

                  <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                    <div className="flex justify-between font-bold text-gray-800">
                      <span>Crecimiento Anual Ventas (Años 1–5)</span>
                      <span className="text-orange-600">
                        {revGrowth.toFixed(1)}%
                      </span>
                    </div>
                    {workMode === "manual" && (
                      <RangeSliderWithNumber
                        min={-5}
                        max={35}
                        step={0.5}
                        value={revGrowth}
                        onChange={setRevGrowth}
                        ariaLabel="Crecimiento Anual Ventas"
                      />
                    )}
                    <p className="text-[11px] text-gray-500 mt-1">
                      Tasa compuesta anual de expansión de ingresos en la etapa
                      explícita (pondera histórico SEC y consenso).
                    </p>
                  </div>

                  <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                    <div className="flex justify-between font-bold text-gray-800">
                      <span>Margen Operativo (EBIT) Objetivo Año 5</span>
                      <span className="text-orange-600">
                        {targetEbitMargin.toFixed(1)}%
                      </span>
                    </div>
                    {workMode === "manual" && (
                      <RangeSliderWithNumber
                        min={Math.min(-25, Math.floor(targetEbitMargin - 5))}
                        max={Math.max(60, Math.ceil(targetEbitMargin + 5))}
                        step={0.5}
                        value={targetEbitMargin}
                        onChange={setTargetEbitMargin}
                        ariaLabel="Margen Operativo EBIT Objetivo"
                      />
                    )}
                    <p className="text-[11px] text-gray-500 mt-1">
                      Rentabilidad operativa hacia la cual converge la empresa
                      desde su margen base actual ({inp.ebit_margin_pct}%).
                    </p>
                    {inp.margin_reversion_note && (
                      <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-1 mt-1.5">
                        {inp.margin_reversion_note}
                      </p>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                      <div className="flex justify-between font-bold text-gray-800">
                        <span>CapEx Etapa 1</span>
                        <span>{capexStage1Pct.toFixed(1)}%</span>
                      </div>
                      {workMode === "manual" && (
                        <RangeSliderWithNumber
                          min={1}
                          max={45}
                          step={0.5}
                          value={capexStage1Pct}
                          onChange={setCapexStage1Pct}
                          ariaLabel="CapEx Etapa 1"
                        />
                      )}
                      <p className="text-[10px] text-gray-500 mt-1">
                        % de ventas invertido en expansión (años 1–5).
                      </p>
                    </div>

                    <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                      <div className="flex justify-between font-bold text-emerald-700">
                        <span>CapEx Terminal</span>
                        <span>{capexTerminalPct.toFixed(1)}%</span>
                      </div>
                      {workMode === "manual" && (
                        <RangeSliderWithNumber
                          min={1}
                          max={30}
                          step={0.5}
                          value={capexTerminalPct}
                          onChange={setCapexTerminalPct}
                          accentClass="accent-emerald-600"
                          ariaLabel="CapEx Terminal"
                        />
                      )}
                      <p className="text-[10px] text-gray-500 mt-1">
                        % de ventas de mantenimiento en perpetuidad.
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                      <div className="flex justify-between font-bold text-gray-800">
                        <span>Tasa WACC</span>
                        <span className="text-orange-600">
                          {wacc.toFixed(1)}%
                        </span>
                      </div>
                      {workMode === "manual" && (
                        <RangeSliderWithNumber
                          min={Math.min(5.5, Math.floor(wacc))}
                          max={Math.max(22, Math.ceil(wacc + 2))}
                          step={0.5}
                          value={wacc}
                          onChange={setWacc}
                          ariaLabel="Tasa WACC"
                        />
                      )}
                      <p className="text-[10px] text-gray-500 mt-1">
                        Costo promedio ponderado del capital (tasa de descuento).
                        {Number(inp.country_risk_premium_pct || 0) > 0 &&
                          ` Incluye prima país ${inp.country_risk_premium_pct}% (ref. ${inp.crp_updated_at || "vigente"}).`}
                      </p>
                    </div>

                    <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                      <div className="flex justify-between font-bold text-gray-800">
                        <span>Crec. Perpetuo (g)</span>
                        <span>{terminalGrowth.toFixed(1)}%</span>
                      </div>
                      {workMode === "manual" && (
                        <RangeSliderWithNumber
                          min={0}
                          max={5.5}
                          step={0.25}
                          value={terminalGrowth}
                          onChange={setTerminalGrowth}
                          ariaLabel="Crecimiento Perpetuo"
                        />
                      )}
                      <p className="text-[10px] text-gray-500 mt-1">
                        Expansión a perpetuidad (no debe superar el PIB nominal ~3–4%).
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                      <div className="flex justify-between font-bold text-gray-800">
                        <span>EV/FCF Salida</span>
                        <span>{exitMultiple.toFixed(1)}x</span>
                      </div>
                      {workMode === "manual" && (
                        <RangeSliderWithNumber
                          min={8}
                          max={40}
                          step={0.5}
                          value={exitMultiple}
                          onChange={setExitMultiple}
                          unit="x"
                          ariaLabel="EV/FCF Salida"
                        />
                      )}
                      <p className="text-[10px] text-gray-500 mt-1">
                        Múltiplo terminal alternativo al año 5.
                      </p>
                    </div>

                    <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                      <div className="flex justify-between font-bold text-gray-800">
                        <span>Ajuste FCF (MM)</span>
                        <span>{extraAdjMm}</span>
                      </div>
                      {workMode === "manual" ? (
                        <input
                          type="number"
                          value={extraAdjMm}
                          onChange={(e) =>
                            setExtraAdjMm(Number(e.target.value) || 0)
                          }
                          className="w-full mt-1.5 px-2 py-1 border border-gray-300 rounded bg-white text-right font-semibold"
                        />
                      ) : (
                        <p className="text-[11px] font-semibold text-gray-700 mt-1.5">
                          US$ 0 MM
                        </p>
                      )}
                      <p className="text-[10px] text-gray-500 mt-1">
                        Restar SBC o sumar sinergias recurrentes.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="lg:col-span-7 space-y-5">
                  {dcfOutput.invalid ? (
                    <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700 font-semibold">
                      El WACC debe ser estrictamente mayor que la tasa de
                      crecimiento perpetuo (g) para que el valor terminal
                      converja.
                    </div>
                  ) : (
                    <>
                      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
                          <span className="font-bold text-gray-800">
                            Proyección Explícita de Flujos de Caja (Millones USD)
                          </span>
                          <span className="text-[11px] text-gray-500">
                            Deuda Neta LTM: {formatMoney0(inp.net_debt_mm)} MM
                          </span>
                        </div>
                        <table className="w-full text-xs text-right">
                          <thead>
                            <tr className="bg-[#333333] text-white">
                              <th className="py-2 px-3.5 text-left">Período</th>
                              <th className="py-2 px-3">Ventas Est.</th>
                              <th className="py-2 px-3">Margen EBIT</th>
                              <th className="py-2 px-3">FCF Proyectado</th>
                              <th className="py-2 px-3">Valor Presente</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100">
                            {dcfOutput.projections.map((p) => (
                              <tr key={p.year} className="hover:bg-gray-50">
                                <td className="py-2 px-3.5 text-left font-bold text-gray-800">
                                  {p.year}
                                </td>
                                <td className="py-2 px-3 tabular-nums">
                                  {formatMoney0(p.rev)}
                                </td>
                                <td className="py-2 px-3 tabular-nums">
                                  {p.ebitMarginPct.toFixed(1)}%
                                </td>
                                <td className="py-2 px-3 tabular-nums font-semibold">
                                  {formatMoney0(p.fcf)}
                                </td>
                                <td className="py-2 px-3 tabular-nums text-orange-600 font-bold">
                                  {formatMoney0(p.pv)}
                                </td>
                              </tr>
                            ))}
                            <tr className="bg-emerald-50/70 font-bold text-emerald-900">
                              <td className="py-2 px-3.5 text-left">
                                Año +6 (Estacionario)
                              </td>
                              <td className="py-2 px-3">-</td>
                              <td className="py-2 px-3">
                                {targetEbitMargin.toFixed(1)}%
                              </td>
                              <td className="py-2 px-3 tabular-nums">
                                {formatMoney0(dcfOutput.steadyFcf6)}
                              </td>
                              <td className="py-2 px-3 text-[11px]">
                                Base perpetuidad
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm flex flex-col justify-between">
                          <div>
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-[11px] font-bold text-gray-500 uppercase">
                                1. Perpetuidad Gordon (g = {terminalGrowth.toFixed(1)}%)
                              </p>
                              {onOpenInfo && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    onOpenInfo(
                                      "Perpetuidad de Gordon (Valor Terminal)",
                                      formatMoney(dcfOutput.priceGordon)
                                    )
                                  }
                                  title="¿Qué es y cuándo usar Perpetuidad Gordon?"
                                  className="text-gray-400 hover:text-orange-500 cursor-pointer"
                                >
                                  <Info className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </div>
                            <p className="text-xl font-extrabold text-gray-900 mt-1">
                              {formatMoney(dcfOutput.priceGordon)}
                            </p>
                            <p className="text-[11px] text-gray-600 mt-1.5 leading-relaxed">
                              Asume que <strong>conservás la empresa para siempre</strong> y desde el año 6 crece al {terminalGrowth.toFixed(1)}% anual, sin depender de múltiplos futuros.
                            </p>
                          </div>
                          {Math.abs(capexStage1Pct - capexTerminalPct) >= 3 && (
                            <p className="text-[11px] text-amber-700 mt-2 pt-2 border-t border-gray-100">
                              Sin normalizar CapEx terminal daría:{" "}
                              <strong>
                                {formatMoney(dcfOutput.priceUnadjustedCapex)}
                              </strong>
                            </p>
                          )}
                        </div>

                        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm flex flex-col justify-between">
                          <div>
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-[11px] font-bold text-gray-500 uppercase">
                                2. Múltiplo de Salida ({exitMultiple.toFixed(1)}x FCF)
                              </p>
                              {onOpenInfo && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    onOpenInfo(
                                      "Múltiplo de Salida (Valor Terminal)",
                                      formatMoney(dcfOutput.priceMult)
                                    )
                                  }
                                  title="¿Qué es y cuándo usar Múltiplo de Salida?"
                                  className="text-gray-400 hover:text-orange-500 cursor-pointer"
                                >
                                  <Info className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </div>
                            <p className="text-xl font-extrabold text-gray-900 mt-1">
                              {formatMoney(dcfOutput.priceMult)}
                            </p>
                            <p className="text-[11px] text-gray-600 mt-1.5 leading-relaxed">
                              Asume que <strong>vendés la empresa al año 5</strong> a un múltiplo de mercado de {exitMultiple.toFixed(1)}x su flujo de caja libre normalizado.
                            </p>
                          </div>
                          <p className="text-[11px] text-gray-500 mt-2 pt-2 border-t border-gray-100">
                            Promedio triangulado (punto medio):{" "}
                            <strong className="text-gray-900">
                              {formatMoney(dcfOutput.intrinsicPrice)}
                            </strong>
                          </p>
                        </div>
                      </div>

                      <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 text-[11px] text-slate-700 leading-relaxed">
                        <strong className="text-slate-900">¿A cuál prestarle atención?</strong>{" "}
                        Si buscás un <strong>criterio conservador de largo plazo</strong> (protegido ante caídas de múltiplos en bolsa), mirá <strong>Perpetuidad Gordon</strong>. En <strong>empresas líderes de crecimiento</strong> (donde asumir un 3% perpetuo al año 6 suele ser demasiado estricto), el <strong>Múltiplo de Salida</strong> y el <strong>promedio triangulado</strong> reflejan mejor su calidad competitiva.
                      </div>

                      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                        <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-200 font-bold text-gray-800">
                          Matriz de Sensibilidad — Valor Intrínseco (US$ / acción): WACC vs. Crecimiento Perpetuo (g)
                        </div>
                        <div className="overflow-x-auto">
                          <table className="w-full text-xs text-right">
                            <thead>
                              <tr className="bg-gray-100 text-gray-700">
                                <th className="py-2 px-3 text-left">
                                  WACC \ g
                                </th>
                                {dcfOutput.gStepsPct.map((gVal, idx) => (
                                  <th key={idx} className="py-2 px-3">
                                    g = {gVal.toFixed(2)}%
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                              {dcfOutput.sensitivityMatrix.map((row, rIdx) => (
                                <tr key={rIdx}>
                                  <td className="py-2 px-3 text-left font-bold bg-gray-50">
                                    {row.waccPct.toFixed(2)}%
                                  </td>
                                  {row.cells.map((cellPrice, cIdx) => {
                                    const isCenter = rIdx === 2 && cIdx === 2;
                                    const isUndervalued =
                                      cellPrice !== null &&
                                      cellPrice > currentPrice;
                                    return (
                                      <td
                                        key={cIdx}
                                        className={`py-2 px-3 tabular-nums ${
                                          isCenter
                                            ? "bg-orange-500 text-white font-bold"
                                            : isUndervalued
                                            ? "text-emerald-700 font-medium"
                                            : "text-gray-700"
                                        }`}
                                      >
                                        {cellPrice !== null
                                          ? formatMoney(cellPrice)
                                          : "N/A"}
                                      </td>
                                    );
                                  })}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}

            {/* =============================================================== */}
            {/* DETALLE MODELO 2: EXCESS RETURN (BANCOS Y FINANCIERAS)          */}
            {/* =============================================================== */}
            {selectedModel === "excess_return" && excessReturnOutput && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                <div className="lg:col-span-5 bg-white border border-gray-200 rounded-xl shadow-sm p-5 space-y-4">
                  <h3 className="text-sm font-bold text-gray-900 border-b border-gray-100 pb-2.5">
                    Parámetros Patrimoniales (Excess Return)
                  </h3>

                  <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                    <div className="flex justify-between font-bold">
                      <span>ROE Sostenible Esperado (Años 1–5)</span>
                      <span className="text-orange-600">
                        {bankRoe.toFixed(1)}%
                      </span>
                    </div>
                    {workMode === "manual" && (
                      <RangeSliderWithNumber
                        min={4}
                        max={30}
                        step={0.5}
                        value={bankRoe}
                        onChange={setBankRoe}
                        ariaLabel="ROE Sostenible Esperado"
                      />
                    )}
                    <p className="text-[11px] text-gray-500 mt-1">
                      Rentabilidad sobre patrimonio neto (mediana histórica 5Y:{" "}
                      {finInp.roe_hist_med_pct}%).
                    </p>
                  </div>

                  <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                    <div className="flex justify-between font-bold">
                      <span>Costo del Capital Accionario (Ke)</span>
                      <span className="text-orange-600">
                        {bankKe.toFixed(1)}%
                      </span>
                    </div>
                    {workMode === "manual" && (
                      <RangeSliderWithNumber
                        min={6}
                        max={16}
                        step={0.5}
                        value={bankKe}
                        onChange={setBankKe}
                        ariaLabel="Costo del Capital Accionario"
                      />
                    )}
                    <p className="text-[11px] text-gray-500 mt-1">
                      Retorno mínimo exigido por el accionista (CAPM). Si ROE{" "}
                      {">"} Ke, el banco crea valor sobre libros.
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                      <div className="flex justify-between font-bold">
                        <span>Payout Ratio</span>
                        <span>{bankPayout.toFixed(0)}%</span>
                      </div>
                      {workMode === "manual" && (
                        <RangeSliderWithNumber
                          min={10}
                          max={80}
                          step={2.5}
                          value={bankPayout}
                          onChange={setBankPayout}
                          ariaLabel="Payout Ratio"
                        />
                      )}
                      <p className="text-[10px] text-gray-500 mt-1">
                        % de ganancias repartidas (el resto capitaliza BVPS).
                      </p>
                    </div>

                    <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                      <div className="flex justify-between font-bold">
                        <span>P/TBV Salida</span>
                        <span>{bankExitPtbv.toFixed(2)}x</span>
                      </div>
                      {workMode === "manual" && (
                        <RangeSliderWithNumber
                          min={0.8}
                          max={3.5}
                          step={0.1}
                          value={bankExitPtbv}
                          onChange={setBankExitPtbv}
                          unit="x"
                          ariaLabel="P/TBV Salida"
                        />
                      )}
                      <p className="text-[10px] text-gray-500 mt-1">
                        Múltiplo sobre patrimonio tangible al año 5.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="lg:col-span-7 space-y-4">
                  {excessReturnOutput.invalid ? (
                    <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700 font-semibold">
                      El Costo de Equity (Ke) debe superar la tasa de
                      crecimiento patrimonial terminal.
                    </div>
                  ) : (
                    <>
                      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 font-bold text-gray-800">
                          Proyección de Retorno Excedente por Acción (BVPS base:{" "}
                          {formatMoney(finInp.bvps)})
                        </div>
                        <table className="w-full text-xs text-right">
                          <thead>
                            <tr className="bg-[#333333] text-white">
                              <th className="py-2 px-3.5 text-left">Período</th>
                              <th className="py-2 px-3">Valor Libros (BVPS)</th>
                              <th className="py-2 px-3">BPA Est. (EPS)</th>
                              <th className="py-2 px-3">Exceso (EPS − Ke·BV)</th>
                              <th className="py-2 px-3">VP Exceso</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100">
                            {excessReturnOutput.rows.map((r) => (
                              <tr key={r.year}>
                                <td className="py-2 px-3.5 text-left font-bold">
                                  {r.year}
                                </td>
                                <td className="py-2 px-3 tabular-nums">
                                  {formatMoney(r.bvps)}
                                </td>
                                <td className="py-2 px-3 tabular-nums">
                                  {formatMoney(r.eps)}
                                </td>
                                <td className="py-2 px-3 tabular-nums">
                                  {formatMoney(r.excessReturn)}
                                </td>
                                <td className="py-2 px-3 tabular-nums font-bold text-emerald-700">
                                  {formatMoney(r.pvExcess)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                          <p className="text-[11px] font-bold text-gray-500 uppercase">
                            1. Excess Return Intrínseco
                          </p>
                          <p className="text-xl font-extrabold text-gray-900 mt-1">
                            {formatMoney(excessReturnOutput.priceExcess)}
                          </p>
                          <p className="text-[11px] text-gray-600 mt-1 leading-relaxed">
                            Valor libros actual + retorno excedente perpetuo. P/BV justificado:{" "}
                            <strong>
                              {excessReturnOutput.impliedPb.toFixed(2)}x
                            </strong>
                          </p>
                        </div>

                        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                          <p className="text-[11px] font-bold text-gray-500 uppercase">
                            2. Salida P/TBV ({bankExitPtbv.toFixed(2)}x) + Div.
                          </p>
                          <p className="text-xl font-extrabold text-gray-900 mt-1">
                            {formatMoney(excessReturnOutput.pricePtbv)}
                          </p>
                          <p className="text-[11px] text-gray-600 mt-1 leading-relaxed">
                            Dividendos cobrados en 5 años + venta a múltiplo sobre capital tangible ({formatMoney(finInp.tbvps)}).
                          </p>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}

            {/* =============================================================== */}
            {/* DETALLE MODELO 3: DDM (DESCUENTO DE DIVIDENDOS)                 */}
            {/* =============================================================== */}
            {selectedModel === "ddm" && ddmOutput && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                <div className="lg:col-span-5 bg-white border border-gray-200 rounded-xl shadow-sm p-5 space-y-4">
                  <h3 className="text-sm font-bold text-gray-900 border-b border-gray-100 pb-2.5">
                    Parámetros de Dividendos (DDM 2 Etapas)
                  </h3>

                  <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                    <div className="flex justify-between font-bold">
                      <span>Dividendo Anual Base por Acción (D0)</span>
                      <span className="text-orange-600">
                        {formatMoney(ddmDivPerShare)}
                      </span>
                    </div>
                    {workMode === "manual" && (
                      <input
                        type="number"
                        step="0.05"
                        value={ddmDivPerShare}
                        onChange={(e) =>
                          setDdmDivPerShare(parseFloat(e.target.value) || 0)
                        }
                        className="w-full mt-1.5 px-2.5 py-1 border border-gray-300 rounded bg-white text-right font-semibold"
                      />
                    )}
                    <p className="text-[11px] text-gray-500 mt-1">
                      Dividendo anualizado vigente por acción ordinaria.
                    </p>
                  </div>

                  <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                    <div className="flex justify-between font-bold">
                      <span>Crecimiento Dividendo Etapa 1 (Años 1–5)</span>
                      <span>{ddmGrowthStage1.toFixed(1)}%</span>
                    </div>
                    {workMode === "manual" && (
                      <RangeSliderWithNumber
                        min={0}
                        max={18}
                        step={0.5}
                        value={ddmGrowthStage1}
                        onChange={setDdmGrowthStage1}
                        ariaLabel="Crecimiento Dividendo Etapa 1"
                      />
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                      <div className="flex justify-between font-bold">
                        <span>Costo Equity (Ke)</span>
                        <span>{ddmKe.toFixed(1)}%</span>
                      </div>
                      {workMode === "manual" && (
                        <RangeSliderWithNumber
                          min={6}
                          max={16}
                          step={0.5}
                          value={ddmKe}
                          onChange={setDdmKe}
                          ariaLabel="Costo Equity DDM"
                        />
                      )}
                    </div>

                    <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                      <div className="flex justify-between font-bold">
                        <span>Crec. Perpetuo (g)</span>
                        <span>{ddmTerminalGrowth.toFixed(1)}%</span>
                      </div>
                      {workMode === "manual" && (
                        <RangeSliderWithNumber
                          min={0}
                          max={5.5}
                          step={0.25}
                          value={ddmTerminalGrowth}
                          onChange={setDdmTerminalGrowth}
                          ariaLabel="Crecimiento Perpetuo DDM"
                        />
                      )}
                    </div>
                  </div>
                </div>

                <div className="lg:col-span-7">
                  {ddmOutput.noDividend ? (
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-amber-900">
                      <p className="font-bold">
                        Dividendo base D0 = US$ 0,00
                      </p>
                      <p className="mt-1">
                        Esta compañía no distribuye dividendos actualmente. Pasá
                        al modelo <strong>DCF 2 Etapas</strong> para valuarla por
                        su generación de flujo de caja libre, o ingresá un
                        dividendo proyectado en <strong>Modo Manual</strong>.
                      </p>
                    </div>
                  ) : ddmOutput.invalid ? (
                    <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700 font-semibold">
                      El Costo de Equity (Ke) debe superar la tasa de
                      crecimiento perpetuo de dividendos.
                    </div>
                  ) : (
                    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 font-bold text-gray-800">
                        Proyección de Dividendos Descontados por Acción
                      </div>
                      <table className="w-full text-xs text-right">
                        <thead>
                          <tr className="bg-[#333333] text-white">
                            <th className="py-2 px-3.5 text-left">Período</th>
                            <th className="py-2 px-3">Dividendo Est.</th>
                            <th className="py-2 px-3">Valor Presente</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {ddmOutput.rows.map((r) => (
                            <tr key={r.year}>
                              <td className="py-2 px-3.5 text-left font-bold">
                                {r.year}
                              </td>
                              <td className="py-2 px-3 tabular-nums">
                                {formatMoney(r.dividend)}
                              </td>
                              <td className="py-2 px-3 tabular-nums font-bold text-orange-600">
                                {formatMoney(r.pv)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* =============================================================== */}
            {/* DETALLE MODELO 4: MÚLTIPLOS NORMALIZADOS (5Y)                   */}
            {/* =============================================================== */}
            {selectedModel === "multiples" && multiplesOutput && (
              <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex flex-wrap justify-between items-center gap-2">
                  <span className="font-bold text-gray-800">
                    Valuación Implícita por Reversión a la Mediana Histórica de 5 Años
                  </span>
                  <span className="text-[11px] text-gray-500">
                    Precio Implícito = Precio Actual × (Mediana 5Y / Múltiplo Actual)
                  </span>
                </div>
                {multiplesOutput.empty ? (
                  <div className="p-6 text-gray-500">
                    No hay suficientes múltiplos positivos históricos para
                    triangular este ticker.
                  </div>
                ) : (
                  <table className="w-full text-xs text-right">
                    <thead>
                      <tr className="bg-[#333333] text-white">
                        <th className="py-2.5 px-4 text-left">Múltiplo</th>
                        <th className="py-2.5 px-4">Actual (LTM)</th>
                        <th className="py-2.5 px-4">Mediana 5Y</th>
                        <th className="py-2.5 px-4">Precio Implícito</th>
                        <th className="py-2.5 px-4">Potencial vs. Actual</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {multiplesOutput.targets.map((t) => {
                        const diff =
                          ((t.impliedPrice - currentPrice) / currentPrice) * 100;
                        return (
                          <tr key={t.metric} className="hover:bg-gray-50">
                            <td className="py-2.5 px-4 text-left font-bold text-gray-900">
                              {t.metric}
                            </td>
                            <td className="py-2.5 px-4 tabular-nums">
                              {t.ltm.toFixed(2)}x
                            </td>
                            <td className="py-2.5 px-4 tabular-nums font-semibold">
                              {t.med5y.toFixed(2)}x
                            </td>
                            <td className="py-2.5 px-4 tabular-nums font-bold text-gray-900">
                              {formatMoney(t.impliedPrice)}
                            </td>
                            <td
                              className={`py-2.5 px-4 tabular-nums font-bold ${
                                diff >= 0 ? "text-emerald-700" : "text-[#d93025]"
                              }`}
                            >
                              {diff >= 0 ? "+" : ""}
                              {diff.toFixed(1)}%
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </>
        )
      )}
    </div>
  );
}