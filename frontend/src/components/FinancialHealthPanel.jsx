import { useEffect, useState } from "react";
import apiClient from "../api/client";
import {
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  MinusCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
  Info,
  TrendingUp,
} from "lucide-react";

function badgeClasses(color, applicable = true) {
  if (!applicable) {
    return "bg-gray-100 text-gray-600 border-gray-300";
  }
  if (color === "emerald") {
    return "bg-emerald-50 text-emerald-800 border-emerald-200";
  }
  if (color === "amber") {
    return "bg-amber-50 text-amber-800 border-amber-200";
  }
  return "bg-red-50 text-red-800 border-red-200";
}

function criterionPillStyle(status, applicable) {
  if (!applicable) {
    return "bg-gray-100 border-gray-300 text-gray-600";
  }
  if (status === "pass") {
    return "bg-emerald-50 border-emerald-300 text-emerald-900";
  }
  if (status === "near") {
    return "bg-amber-50 border-amber-300 text-amber-900";
  }
  return "bg-red-50 border-red-300 text-red-900";
}

function criterionDotStyle(status, applicable) {
  if (!applicable) return "bg-gray-400";
  if (status === "pass") return "bg-emerald-500";
  if (status === "near") return "bg-amber-500";
  return "bg-red-500";
}

function formatSignedPct(val) {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "N/A";
  const num = Number(val);
  return `${num >= 0 ? "+" : ""}${num.toFixed(1)}%`;
}

export default function FinancialHealthPanel({ ticker, onOpenInfo }) {
  const [fetchState, setFetchState] = useState({
    ticker: null,
    data: null,
    error: null,
  });
  const [selectedCriterionId, setSelectedCriterionId] = useState(null);
  const [showPiotroskiDetails, setShowPiotroskiDetails] = useState(false);
  const [showAltmanDetails, setShowAltmanDetails] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    let active = true;

    apiClient
      .get(`/company/${ticker}/health`)
      .then((res) => {
        if (active) {
          setFetchState({ ticker, data: res.data, error: null });
          setSelectedCriterionId(null);
        }
      })
      .catch((err) => {
        if (active) {
          setFetchState({
            ticker,
            data: null,
            error:
              err.response?.data?.detail ||
              "No se pudo calcular la salud financiera.",
          });
        }
      });

    return () => {
      active = false;
    };
  }, [ticker]);

  const loading = Boolean(ticker) && fetchState.ticker !== ticker;
  const healthData = fetchState.ticker === ticker ? fetchState.data : null;
  const error = fetchState.ticker === ticker ? fetchState.error : null;

  if (loading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-5 flex items-center justify-center text-xs text-orange-500">
        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
        Evaluando Piotroski F-Score, Altman Z-Score, ROIIC y TSR Bridge para {ticker}...
      </div>
    );
  }

  if (error || !healthData) {
    return null;
  }

  const {
    sector,
    industry,
    fiscal_year_curr,
    fiscal_year_prev,
    sector_applicability,
    piotroski,
    altman,
    dupont,
    capital_allocation,
  } = healthData;

  const isFinancialSector = sector_applicability?.profile === "financial";
  const preferDoublePrime = altman?.recommended_variant === "z_double_prime";
  const inspectedCriterion =
    piotroski.criteria.find((c) => c.id === selectedCriterionId) || null;

  return (
    <div className="space-y-4 mb-6 text-xs">
      {/* Banner superior de contexto sectorial */}
      <div
        className={`rounded-xl border p-4 flex flex-wrap items-start justify-between gap-3 ${
          isFinancialSector
            ? "bg-amber-50 border-amber-300 text-amber-950"
            : "bg-slate-50 border-slate-200 text-slate-800"
        }`}
      >
        <div className="flex items-start gap-2.5">
          {isFinancialSector ? (
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          ) : (
            <ShieldCheck className="w-4 h-4 text-orange-500 shrink-0 mt-0.5" />
          )}
          <div>
            <p className="font-bold text-gray-900">
              Diagnóstico de Salud Financiera y Asignación de Capital (
              {fiscal_year_prev} → {fiscal_year_curr})
            </p>
            <p className="text-[11px] text-gray-600 mt-0.5">
              Sector detectado: <strong>{sector}</strong> ({industry}) ·
              Clasificación metodológica:{" "}
              <strong>{sector_applicability?.label}</strong>
            </p>
          </div>
        </div>
      </div>

      {/* GRID PRINCIPAL: PIOTROSKI F-SCORE | ALTMAN Z / Z''-SCORE | DUPONT */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* TARJETA 1: PIOTROSKI F-SCORE */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between gap-2 pb-2.5 border-b border-gray-100">
              <div className="flex items-center gap-1.5">
                <h4 className="font-bold text-sm text-gray-900">
                  Piotroski F-Score
                </h4>
                {onOpenInfo && (
                  <button
                    type="button"
                    onClick={() =>
                      onOpenInfo(
                        "Piotroski F-Score",
                        `${piotroski.score} / ${piotroski.max_score}`
                      )
                    }
                    className="text-gray-400 hover:text-orange-500 cursor-pointer"
                  >
                    <Info className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
              <span
                className={`px-2 py-0.5 rounded border text-[11px] font-bold ${badgeClasses(
                  piotroski.color,
                  piotroski.applicable
                )}`}
              >
                {piotroski.applicable
                  ? `${piotroski.score} / 9 pts`
                  : "Uso restringido"}
              </span>
            </div>

            <div className="mt-2.5 flex items-baseline justify-between">
              <span className="text-2xl font-extrabold text-gray-900">
                {piotroski.score}
                <span className="text-sm font-medium text-gray-400"> / 9</span>
              </span>
              <span className="text-[11px] font-semibold text-gray-700">
                {piotroski.zone}
              </span>
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-gray-600">
              <span className="inline-flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                Cumple (+1 pt)
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                Cerca (0 pts)
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-red-500" />
                Lejos (0 pts)
              </span>
            </div>

            <div className="grid grid-cols-3 gap-1.5 mt-2.5">
              {piotroski.criteria.map((c) => {
                const isSelected = selectedCriterionId === c.id;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onMouseEnter={() => setSelectedCriterionId(c.id)}
                    onClick={() =>
                      setSelectedCriterionId((prev) =>
                        prev === c.id ? null : c.id
                      )
                    }
                    className={`px-2 py-1.5 rounded border text-left transition-all cursor-pointer ${criterionPillStyle(
                      c.status,
                      piotroski.applicable
                    )} ${isSelected ? "ring-2 ring-orange-400" : ""}`}
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-[10px] font-extrabold opacity-75">
                        {c.id}
                      </span>
                      <span
                        className={`w-2 h-2 rounded-full shrink-0 ${criterionDotStyle(
                          c.status,
                          piotroski.applicable
                        )}`}
                      />
                    </div>
                    <p className="text-[11px] font-semibold truncate mt-0.5">
                      {c.short_label}
                    </p>
                  </button>
                );
              })}
            </div>

            {inspectedCriterion ? (
              <div className="mt-2.5 p-2.5 rounded-lg bg-slate-900 text-white text-[11px] space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-orange-400">
                    {inspectedCriterion.id} · {inspectedCriterion.name}
                  </span>
                  <span
                    className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                      inspectedCriterion.status === "pass"
                        ? "bg-emerald-500/20 text-emerald-300"
                        : inspectedCriterion.status === "near"
                        ? "bg-amber-500/20 text-amber-300"
                        : "bg-red-500/20 text-red-300"
                    }`}
                  >
                    {inspectedCriterion.status === "pass"
                      ? "Cumple (+1)"
                      : inspectedCriterion.status === "near"
                      ? "Cerca (0)"
                      : "No cumple (0)"}
                  </span>
                </div>
                <p className="text-gray-300">
                  Actual ({fiscal_year_curr}):{" "}
                  <strong className="text-white">
                    {inspectedCriterion.curr_display}
                  </strong>{" "}
                  · Condición:{" "}
                  <strong className="text-orange-300">
                    {inspectedCriterion.target_rule}
                  </strong>
                </p>
              </div>
            ) : (
              <p className="mt-2 text-[10px] text-gray-400 italic">
                Pasá el cursor o tocá cualquier criterio (F1–F9) para ver su
                valor actual y la condición requerida.
              </p>
            )}

            <div
              className={`mt-2.5 p-2.5 rounded-lg border text-[11px] leading-relaxed ${
                piotroski.applicable
                  ? "bg-gray-50 border-gray-200 text-gray-600"
                  : "bg-amber-50 border-amber-200 text-amber-900"
              }`}
            >
              {piotroski.warning}
            </div>
          </div>

          <button
            type="button"
            onClick={() => setShowPiotroskiDetails((prev) => !prev)}
            className="mt-3 pt-2.5 border-t border-gray-100 w-full flex items-center justify-between text-[11px] font-semibold text-orange-600 hover:text-orange-700 cursor-pointer"
          >
            <span>
              {showPiotroskiDetails
                ? "Ocultar tabla completa de criterios"
                : "Ver tabla completa de los 9 criterios"}
            </span>
            {showPiotroskiDetails ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>
        </div>

        {/* TARJETA 2: ALTMAN Z-SCORE & Z''-SCORE */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between gap-2 pb-2.5 border-b border-gray-100">
              <div className="flex items-center gap-1.5">
                <h4 className="font-bold text-sm text-gray-900">
                  Altman Z-Score
                </h4>
                {onOpenInfo && (
                  <button
                    type="button"
                    onClick={() =>
                      onOpenInfo(
                        "Altman Z-Score",
                        altman.applicable
                          ? `${
                              preferDoublePrime
                                ? altman.z_double_prime.score
                                : altman.z_original.score
                            }`
                          : "No aplicable a financieras"
                      )
                    }
                    className="text-gray-400 hover:text-orange-500 cursor-pointer"
                  >
                    <Info className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
              <span
                className={`px-2 py-0.5 rounded border text-[11px] font-bold ${
                  !altman.applicable
                    ? "bg-red-50 text-red-700 border-red-200"
                    : badgeClasses(
                        preferDoublePrime
                          ? altman.z_double_prime.color
                          : altman.z_original.color,
                        true
                      )
                }`}
              >
                {!altman.applicable
                  ? "No Válido en Sector"
                  : preferDoublePrime
                  ? altman.z_double_prime.zone
                  : altman.z_original.zone}
              </span>
            </div>

            {!altman.applicable ? (
              <div className="mt-3 p-3 rounded-lg bg-red-50 border border-red-200 text-red-900 text-[11px] leading-relaxed">
                <p className="font-bold mb-1">
                  Indicador excluido por incompatibilidad sectorial
                </p>
                <p>{altman.warning}</p>
              </div>
            ) : (
              <>
                <div className="mt-3 grid grid-cols-2 gap-2.5">
                  <div
                    className={`p-2.5 rounded-lg border ${
                      !preferDoublePrime
                        ? "bg-orange-50/50 border-orange-300"
                        : "bg-gray-50 border-gray-200"
                    }`}
                  >
                    <p className="text-[10px] font-bold uppercase text-gray-500">
                      Z-Score Original {!preferDoublePrime && "★"}
                    </p>
                    <p className="text-lg font-extrabold text-gray-900 mt-0.5">
                      {altman.z_original.score.toFixed(2)}
                    </p>
                    <p className="text-[10px] text-gray-600 mt-0.5">
                      {altman.z_original.zone}
                    </p>
                  </div>

                  <div
                    className={`p-2.5 rounded-lg border ${
                      preferDoublePrime
                        ? "bg-orange-50/50 border-orange-300"
                        : "bg-gray-50 border-gray-200"
                    }`}
                  >
                    <p className="text-[10px] font-bold uppercase text-gray-500">
                      Z''-Score Servicios {preferDoublePrime && "★"}
                    </p>
                    <p className="text-lg font-extrabold text-gray-900 mt-0.5">
                      {altman.z_double_prime.score.toFixed(2)}
                    </p>
                    <p className="text-[10px] text-gray-600 mt-0.5">
                      {altman.z_double_prime.zone}
                    </p>
                  </div>
                </div>

                <div className="mt-3 p-2.5 rounded-lg bg-gray-50 border border-gray-200 text-[11px] text-gray-600 leading-relaxed">
                  {altman.warning}
                </div>
              </>
            )}
          </div>

          {altman.applicable && (
            <button
              type="button"
              onClick={() => setShowAltmanDetails((prev) => !prev)}
              className="mt-3 pt-2.5 border-t border-gray-100 w-full flex items-center justify-between text-[11px] font-semibold text-orange-600 hover:text-orange-700 cursor-pointer"
            >
              <span>
                {showAltmanDetails
                  ? "Ocultar factores X1–X5"
                  : "Ver desglose de factores X1–X5"}
              </span>
              {showAltmanDetails ? (
                <ChevronUp className="w-3.5 h-3.5" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5" />
              )}
            </button>
          )}
        </div>

        {/* TARJETA 3: DESCOMPOSICIÓN DUPONT (ROE 3 Y 5 FACTORES) */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between gap-2 pb-2.5 border-b border-gray-100">
              <div className="flex items-center gap-1.5">
                <h4 className="font-bold text-sm text-gray-900">
                  Descomposición DuPont ({fiscal_year_curr})
                </h4>
                {onOpenInfo && (
                  <button
                    type="button"
                    onClick={() =>
                      onOpenInfo("Descomposición DuPont", `${dupont.roe_pct}%`)
                    }
                    className="text-gray-400 hover:text-orange-500 cursor-pointer"
                  >
                    <Info className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
              <span className="px-2 py-0.5 rounded bg-orange-50 border border-orange-200 text-orange-800 text-[11px] font-bold">
                ROE {dupont.roe_pct.toFixed(2)}%
              </span>
            </div>

            <div className="mt-3 space-y-2.5">
              <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-200">
                <p className="text-[10px] font-bold uppercase text-gray-500 mb-1.5">
                  Identidad de 3 Factores
                </p>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div>
                    <p className="text-[10px] text-gray-500">Margen Neto</p>
                    <p className="font-bold text-gray-900">
                      {dupont.three_factor.net_margin_pct.toFixed(2)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-gray-500">Rot. Activos</p>
                    <p className="font-bold text-gray-900">
                      {dupont.three_factor.asset_turnover.toFixed(2)}x
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-gray-500">Apalancamiento</p>
                    <p className="font-bold text-gray-900">
                      {dupont.three_factor.equity_multiplier.toFixed(2)}x
                    </p>
                  </div>
                </div>
              </div>

              <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-200">
                <p className="text-[10px] font-bold uppercase text-gray-500 mb-1.5">
                  Identidad Extendida de 5 Factores
                </p>
                <div className="space-y-1 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-gray-600">
                      Carga Fiscal (Net Income / EBT):
                    </span>
                    <span className="font-semibold text-gray-900">
                      {dupont.five_factor.tax_burden.toFixed(2)}x
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">
                      Carga de Intereses (EBT / EBIT):
                    </span>
                    <span className="font-semibold text-gray-900">
                      {dupont.five_factor.interest_burden.toFixed(2)}x
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">
                      Margen Operativo (EBIT / Ventas):
                    </span>
                    <span className="font-semibold text-gray-900">
                      {dupont.five_factor.ebit_margin_pct.toFixed(2)}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <p className="mt-3 pt-2 border-t border-gray-100 text-[11px] text-gray-500">
            Permite distinguir si el ROE proviene de eficiencia operativa o de deuda/impuestos.
          </p>
        </div>
      </div>

      {/* BLOQUE 4: ROIIC, REINVESTMENT RATE, FCF POST-SBC Y TSR BRIDGE (ETAPA 14C) */}
      {capital_allocation && !isFinancialSector && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Sub-tarjeta A: ROIIC & Reinvestment Rate */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-2.5 border-b border-gray-100">
                <h4 className="font-bold text-sm text-gray-900">
                  ROIIC & Tasa de Reinversión
                </h4>
                <span className="px-2 py-0.5 rounded bg-blue-50 border border-blue-200 text-blue-800 text-[11px] font-bold">
                  ROIC {capital_allocation.roic_pct.toFixed(1)}%
                </span>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2.5">
                <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-200">
                  <p className="text-[10px] font-bold uppercase text-gray-500">
                    ROIIC ({capital_allocation.base_year}→{capital_allocation.curr_year})
                  </p>
                  <p className="text-lg font-extrabold text-gray-900 mt-0.5">
                    {capital_allocation.roiic_multi_pct !== null
                      ? `${capital_allocation.roiic_multi_pct.toFixed(1)}%`
                      : "N/A"}
                  </p>
                  <p className="text-[10px] text-gray-500 mt-0.5">
                    1Y:{" "}
                    {capital_allocation.roiic_1y_pct !== null
                      ? `${capital_allocation.roiic_1y_pct.toFixed(1)}%`
                      : "ΔIC ≤ 0"}
                  </p>
                </div>

                <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-200">
                  <p className="text-[10px] font-bold uppercase text-gray-500">
                    Reinvestment Rate
                  </p>
                  <p className="text-lg font-extrabold text-gray-900 mt-0.5">
                    {capital_allocation.reinvestment_rate_pct.toFixed(1)}%
                  </p>
                  <p className="text-[10px] text-gray-500 mt-0.5">
                    Crec. intrínseco: {capital_allocation.intrinsic_growth_pct.toFixed(1)}%
                  </p>
                </div>
              </div>

              <p className="mt-2.5 p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-700 leading-relaxed">
                {capital_allocation.roiic_note}
              </p>
            </div>
          </div>

          {/* Sub-tarjeta B: Calidad de FCF Post-SBC */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-2.5 border-b border-gray-100">
                <h4 className="font-bold text-sm text-gray-900">
                  Calidad de FCF (Post-SBC)
                </h4>
                <span
                  className={`px-2 py-0.5 rounded border text-[11px] font-bold ${badgeClasses(
                    capital_allocation.sbc_color,
                    true
                  )}`}
                >
                  SBC / FCF: {capital_allocation.sbc_to_fcf_pct.toFixed(1)}%
                </span>
              </div>

              <div className="mt-3 space-y-1.5 text-[11px]">
                <div className="flex justify-between py-1 border-b border-gray-100">
                  <span className="text-gray-600">FCF Reportado ({fiscal_year_curr}):</span>
                  <span className="font-bold text-gray-900 tabular-nums">
                    US$ {capital_allocation.fcf_reported_mm.toLocaleString("en-US", { maximumFractionDigits: 0 })} MM
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-gray-100">
                  <span className="text-gray-600">(-) Compensación en Acciones (SBC):</span>
                  <span className="font-semibold text-red-600 tabular-nums">
                    -US$ {capital_allocation.sbc_mm.toLocaleString("en-US", { maximumFractionDigits: 0 })} MM
                  </span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="font-bold text-gray-900">FCF Real (Post-SBC):</span>
                  <span
                    className={`font-extrabold tabular-nums ${
                      capital_allocation.fcf_adj_sbc_mm >= 0
                        ? "text-emerald-700"
                        : "text-red-700"
                    }`}
                  >
                    US$ {capital_allocation.fcf_adj_sbc_mm.toLocaleString("en-US", { maximumFractionDigits: 0 })} MM
                  </span>
                </div>
              </div>

              <div
                className={`mt-2.5 p-2.5 rounded-lg border text-[11px] leading-relaxed ${badgeClasses(
                  capital_allocation.sbc_color,
                  true
                )}`}
              >
                {capital_allocation.sbc_verdict}
              </div>
            </div>
          </div>

          {/* Sub-tarjeta C: TSR Bridge (Descomposición del Retorno al Accionista) */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-2.5 border-b border-gray-100">
                <div className="flex items-center gap-1.5">
                  <TrendingUp className="w-4 h-4 text-orange-500" />
                  <h4 className="font-bold text-sm text-gray-900">
                    TSR Bridge ({capital_allocation.span_years}Y CAGR)
                  </h4>
                </div>
                <span className="px-2 py-0.5 rounded bg-orange-50 border border-orange-200 text-orange-800 text-[11px] font-bold">
                  TSR {formatSignedPct(capital_allocation.tsr_bridge.total_tsr_cagr_pct)}
                </span>
              </div>

              <div className="mt-3 space-y-1.5 text-[11px]">
                <div className="flex justify-between py-1 border-b border-gray-100">
                  <span className="text-gray-600">1. Crecimiento Fundamental (Ventas):</span>
                  <span className="font-bold text-gray-900 tabular-nums">
                    {formatSignedPct(capital_allocation.tsr_bridge.fundamental_growth_pct)}
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-gray-100">
                  <span className="text-gray-600">2. Retorno de Capital (Div + Recompras):</span>
                  <span className="font-bold text-gray-900 tabular-nums">
                    {formatSignedPct(capital_allocation.tsr_bridge.capital_return_pct)}
                  </span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-gray-600">3. Expansión / Contracción Múltiplo:</span>
                  <span
                    className={`font-bold tabular-nums ${
                      capital_allocation.tsr_bridge.multiple_change_pct >= 0
                        ? "text-emerald-700"
                        : "text-red-700"
                    }`}
                  >
                    {formatSignedPct(capital_allocation.tsr_bridge.multiple_change_pct)}
                  </span>
                </div>
              </div>

              <p className="mt-2.5 p-2.5 rounded-lg bg-gray-50 border border-gray-200 text-[11px] text-gray-600 leading-relaxed">
                Dividendo: {capital_allocation.tsr_bridge.dividend_yield_pct.toFixed(1)}% ·
                Recompra neta: {formatSignedPct(capital_allocation.tsr_bridge.net_buyback_yield_pct)} anual.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* DESPLEGABLE DETALLADO DE LOS 9 CRITERIOS PIOTROSKI */}
      {showPiotroskiDetails && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-4 overflow-x-auto">
          <h5 className="font-bold text-gray-900 mb-2.5">
            Auditoría Punto por Punto — Piotroski F-Score ({fiscal_year_prev} vs{" "}
            {fiscal_year_curr})
          </h5>
          <table className="w-full text-[12px] text-left">
            <thead>
              <tr className="bg-gray-100 text-gray-700 border-b border-gray-200">
                <th className="py-2 px-3">ID</th>
                <th className="py-2 px-3">Criterio y Qué Evalúa</th>
                <th className="py-2 px-3">Condición Requerida</th>
                <th className="py-2 px-3 text-right">{fiscal_year_prev}</th>
                <th className="py-2 px-3 text-right">{fiscal_year_curr}</th>
                <th className="py-2 px-3 text-center">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {piotroski.criteria.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="py-2 px-3 font-bold text-gray-700">{c.id}</td>
                  <td className="py-2 px-3">
                    <p className="font-medium text-gray-900">
                      {c.name}{" "}
                      <span className="text-[10px] text-gray-400">
                        ({c.group})
                      </span>
                    </p>
                    <p className="text-[11px] text-gray-500">{c.detail}</p>
                  </td>
                  <td className="py-2 px-3 text-[11px] font-semibold text-gray-700">
                    {c.target_rule}
                  </td>
                  <td className="py-2 px-3 text-right tabular-nums text-gray-600">
                    {c.prev_display}
                  </td>
                  <td className="py-2 px-3 text-right tabular-nums font-semibold text-gray-900">
                    {c.curr_display}
                  </td>
                  <td className="py-2 px-3 text-center">
                    {c.status === "pass" ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold text-[11px]">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Cumple (+1 pt)
                      </span>
                    ) : c.status === "near" ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 font-semibold text-[11px]">
                        <MinusCircle className="w-3.5 h-3.5" /> Cerca (0 pts)
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-red-50 text-red-700 border border-red-200 font-medium text-[11px]">
                        <XCircle className="w-3.5 h-3.5" /> Lejos (0 pts)
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* DESPLEGABLE DETALLADO DE FACTORES ALTMAN Z */}
      {showAltmanDetails && altman.applicable && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-4">
          <h5 className="font-bold text-gray-900 mb-2.5">
            Componentes del Modelo Altman ({fiscal_year_curr})
          </h5>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
            {altman.components.map((comp) => (
              <div
                key={comp.code}
                className="p-2.5 rounded-lg bg-gray-50 border border-gray-200 flex items-center justify-between"
              >
                <div>
                  <span className="font-bold text-orange-600 mr-1.5">
                    {comp.code}
                  </span>
                  <span className="text-gray-700">{comp.label}</span>
                </div>
                <span className="font-bold text-gray-900 tabular-nums">
                  {comp.value.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
