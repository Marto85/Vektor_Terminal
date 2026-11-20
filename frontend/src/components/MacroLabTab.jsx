import { useEffect, useMemo, useState } from "react";
import apiClient from "../api/client";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import {
  Globe,
  Loader2,
  Plus,
  X,
  Info,
  TrendingUp,
  Layers,
  Calendar,
  Sparkles,
  HelpCircle,
} from "lucide-react";

const SERIES_COLORS = [
  "#f97316", // Naranja Vektor
  "#2563eb", // Azul institucional
  "#10b981", // Verde esmeralda
  "#8b5cf6", // Violeta
  "#e11d48", // Carmesí
];

const METRIC_CATALOG = [
  // Índices Nominales vs Reales (CPI)
  { key: "sp500_nom", label: "S&P 500 (Nominal)", group: "Índices USA (Nominal vs. Real)", unit: "pts", canBase100: true },
  { key: "sp500_real", label: "S&P 500 Real (Ajustado Inflación CPI)", group: "Índices USA (Nominal vs. Real)", unit: "pts", canBase100: true },
  { key: "ndx_nom", label: "Nasdaq 100 (Nominal)", group: "Índices USA (Nominal vs. Real)", unit: "pts", canBase100: true },
  { key: "ndx_real", label: "Nasdaq 100 Real (Ajustado Inflación CPI)", group: "Índices USA (Nominal vs. Real)", unit: "pts", canBase100: true },
  { key: "ixic_nom", label: "Nasdaq Composite (Nominal)", group: "Índices USA (Nominal vs. Real)", unit: "pts", canBase100: true },
  { key: "ixic_real", label: "Nasdaq Composite Real (CPI)", group: "Índices USA (Nominal vs. Real)", unit: "pts", canBase100: true },
  { key: "dji_nom", label: "Dow Jones Industrial (Nominal)", group: "Índices USA (Nominal vs. Real)", unit: "pts", canBase100: true },
  { key: "dji_real", label: "Dow Jones Real (Ajustado CPI)", group: "Índices USA (Nominal vs. Real)", unit: "pts", canBase100: true },
  { key: "rut_nom", label: "Russell 2000 Small Caps (Nominal)", group: "Índices USA (Nominal vs. Real)", unit: "pts", canBase100: true },
  { key: "rut_real", label: "Russell 2000 Real (Ajustado CPI)", group: "Índices USA (Nominal vs. Real)", unit: "pts", canBase100: true },

  // Retornos Móviles (12M, 3Y, 5Y, 10Y CAGR)
  { key: "ndx_ret_1y", label: "Nasdaq 100 Retorno Móvil 12 Meses (%)", group: "Retornos Móviles (Rolling 12M / 3Y / 5Y / 10Y)", unit: "%", canBase100: false, isRolling: true },
  { key: "ndx_cagr_3y", label: "Nasdaq 100 Retorno Anualizado Móvil 3Y (%)", group: "Retornos Móviles (Rolling 12M / 3Y / 5Y / 10Y)", unit: "%", canBase100: false, isRolling: true },
  { key: "ndx_cagr_5y", label: "Nasdaq 100 Retorno Anualizado Móvil 5Y (%)", group: "Retornos Móviles (Rolling 12M / 3Y / 5Y / 10Y)", unit: "%", canBase100: false, isRolling: true },
  { key: "ndx_cagr_10y", label: "Nasdaq 100 Retorno Anualizado Móvil 10Y (%)", group: "Retornos Móviles (Rolling 12M / 3Y / 5Y / 10Y)", unit: "%", canBase100: false, isRolling: true },
  { key: "sp500_ret_1y", label: "S&P 500 Retorno Móvil 12 Meses (%)", group: "Retornos Móviles (Rolling 12M / 3Y / 5Y / 10Y)", unit: "%", canBase100: false, isRolling: true },
  { key: "sp500_cagr_3y", label: "S&P 500 Retorno Anualizado Móvil 3Y (%)", group: "Retornos Móviles (Rolling 12M / 3Y / 5Y / 10Y)", unit: "%", canBase100: false, isRolling: true },
  { key: "sp500_cagr_5y", label: "S&P 500 Retorno Anualizado Móvil 5Y (%)", group: "Retornos Móviles (Rolling 12M / 3Y / 5Y / 10Y)", unit: "%", canBase100: false, isRolling: true },
  { key: "sp500_cagr_10y", label: "S&P 500 Retorno Anualizado Móvil 10Y (%)", group: "Retornos Móviles (Rolling 12M / 3Y / 5Y / 10Y)", unit: "%", canBase100: false, isRolling: true },

  // Indicadores Portfolio Manager & Crédito
  { key: "erp_implied", label: "Equity Risk Premium (ERP) Implícito (%)", group: "Portfolio Manager & Crédito", unit: "%", canBase100: false },
  { key: "curve_10y_2y", label: "Pendiente Curva Tesoro (10Y − 2Y) %", group: "Portfolio Manager & Crédito", unit: "%", canBase100: false },
  { key: "curve_10y_3m", label: "Pendiente Curva Tesoro (10Y − 3M) %", group: "Portfolio Manager & Crédito", unit: "%", canBase100: false },
  { key: "hy_spread", label: "Spread Crédito High Yield USA (%)", group: "Portfolio Manager & Crédito", unit: "%", canBase100: false },
  { key: "ust_10y", label: "Tasa Bono Tesoro USA 10Y Nominal (%)", group: "Portfolio Manager & Crédito", unit: "%", canBase100: false },
  { key: "real_rate_10y", label: "Tasa Real Tesoro USA 10Y TIPS (%)", group: "Portfolio Manager & Crédito", unit: "%", canBase100: false },
  { key: "vix", label: "Índice de Volatilidad Implícita (VIX)", group: "Portfolio Manager & Crédito", unit: "pts", canBase100: false },

  // Ratios Inter-Mercado y Amplitud
  { key: "rsp_spy", label: "Amplitud Mercado: S&P 500 Equal / Cap Weight (RSP/SPY)", group: "Ratios Inter-Mercado y Liquidez", unit: "ratio", canBase100: true },
  { key: "iwd_iwf", label: "Rotación Estilos: Value vs. Growth (IWD/IWF)", group: "Ratios Inter-Mercado y Liquidez", unit: "ratio", canBase100: true },
  { key: "gold_sp500", label: "Ratio Oro / S&P 500 (Activos Reales vs. Acciones)", group: "Ratios Inter-Mercado y Liquidez", unit: "ratio", canBase100: true },
  { key: "copper_gold", label: "Ratio Cobre / Oro (Actividad Cíclica vs. Refugio)", group: "Ratios Inter-Mercado y Liquidez", unit: "ratio", canBase100: true },
  { key: "sp500_m2", label: "Liquidez: S&P 500 / Masa Monetaria M2", group: "Ratios Inter-Mercado y Liquidez", unit: "ratio", canBase100: true },
  { key: "gold_nom", label: "Oro Spot / Futuros (US$ / oz Nominal)", group: "Ratios Inter-Mercado y Liquidez", unit: "US$", canBase100: true },
  { key: "gold_real", label: "Oro Real Ajustado por Inflación CPI (US$)", group: "Ratios Inter-Mercado y Liquidez", unit: "US$", canBase100: true },

  // Monedas Globales
  { key: "dxy", label: "Índice Dólar Global (DXY)", group: "Monedas Globales", unit: "pts", canBase100: true },
  { key: "eur_usd", label: "Euro / Dólar (EUR/USD)", group: "Monedas Globales", unit: "fx", canBase100: true },
  { key: "usd_jpy", label: "Dólar / Yen Japonés (USD/JPY)", group: "Monedas Globales", unit: "fx", canBase100: true },
  { key: "usd_brl", label: "Dólar / Real Brasileño (USD/BRL)", group: "Monedas Globales", unit: "fx", canBase100: true },
  { key: "usd_ars", label: "Dólar / Peso Argentino Oficial (USD/ARS)", group: "Monedas Globales", unit: "fx", canBase100: true },
];

const PM_PRESETS = [
  {
    id: "nominal_vs_real",
    title: "S&P 500 Nominal vs. Real (CPI)",
    metrics: ["sp500_nom", "sp500_real"],
    scaleMode: "base100",
    range: "20y",
    explanation:
      "Compara el crecimiento nominal del S&P 500 frente a su poder adquisitivo real descontando la inflación acumulada de EE. UU. (CPI). Permite ver cuánto de la suba bursátil es creación real de riqueza y cuánto es efecto monetario.",
  },
  {
    id: "ndx_vs_sp500_ytd",
    title: "Nasdaq 100 vs. S&P 500 (Rendimiento Acumulado)",
    metrics: ["ndx_nom", "sp500_nom"],
    scaleMode: "base100",
    range: "ytd",
    explanation:
      "Compara el rendimiento acumulado en Base 100 del Nasdaq 100 frente al S&P 500. Podés alternar en el eje horizontal entre YTD (año en curso), 1Y (últimos 12 meses), 3Y, 5Y o 10Y para medir el desempeño acumulado exacto en cada ventana.",
  },
  {
    id: "erp_vs_10y",
    title: "ERP Implícito vs. Tasa Real 10Y",
    metrics: ["erp_implied", "real_rate_10y"],
    scaleMode: "raw",
    range: "10y",
    explanation:
      "El Equity Risk Premium (ERP) mide el rendimiento extra que ofrecen las ganancias del S&P 500 (Earnings Yield = 1 ÷ P/E) por encima del bono del Tesoro a 10 años. Cuando el ERP se comprime cerca de 0% o pasa a negativo mientras suben las tasas reales TIPS, la renta variable ofrece menor colchón de valuación frente a bonos soberanos.",
  },
  {
    id: "yield_curve",
    title: "Pendiente Curva Tasas (10Y − 2Y)",
    metrics: ["curve_10y_2y", "curve_10y_3m"],
    scaleMode: "raw",
    range: "20y",
    explanation:
      "Mide la diferencia entre la tasa larga del Tesoro (10 años) y las tasas cortas (2 años y 3 meses). Cuando el diferencial cae por debajo de 0% (curva invertida), indica política monetaria restrictiva; históricamente las recesiones y correcciones fuertes ocurren cuando la curva vuelve a empinarse positivamente tras haber estado invertida.",
  },
  {
    id: "credit_stress",
    title: "Spread Crédito High Yield vs. VIX",
    metrics: ["hy_spread", "vix"],
    scaleMode: "dual",
    range: "10y",
    explanation:
      "Cruza el diferencial de tasa que pagan los bonos corporativos basura (High Yield OAS) contra la volatilidad implícita (VIX). Los spreads de crédito suelen ampliarse antes de que caiga la bolsa, funcionando como alerta temprana de restricción financiera.",
  },
  {
    id: "market_breadth",
    title: "Amplitud: Equal Weight vs. Cap Weight",
    metrics: ["rsp_spy"],
    scaleMode: "raw",
    range: "10y",
    explanation:
      "Cociente entre el S&P 500 equiponderado (RSP) y el S&P 500 ponderado por capitalización (SPY). Cuando sube, el mercado amplio lidera la suba; cuando cae, el índice está sostenido por pocas mega-caps.",
  },
  {
    id: "value_vs_growth",
    title: "Rotación Value vs. Growth (IWD / IWF)",
    metrics: ["iwd_iwf", "real_rate_10y"],
    scaleMode: "dual",
    range: "10y",
    explanation:
      "Compara el desempeño relativo de acciones Value (IWD) frente a Growth (IWF) junto con la tasa real a 10 años. Repuntes de tasas reales suelen impulsar rotaciones hacia Value.",
  },
  {
    id: "gold_vs_sp500",
    title: "Ratio Oro / S&P 500",
    metrics: ["gold_sp500"],
    scaleMode: "raw",
    range: "max",
    explanation:
      "Mide cuántas unidades del índice S&P 500 se compran con una onza de oro. Identifica ciclos seculares entre activos reales (materias primas) y activos financieros.",
  },
  {
    id: "copper_gold",
    title: "Cobre / Oro vs. Tasa Tesoro 10Y",
    metrics: ["copper_gold", "ust_10y"],
    scaleMode: "dual",
    range: "10y",
    explanation:
      "El cociente Cobre / Oro actúa como termómetro cíclico de actividad industrial global y expectativas de inflación, correlacionando estrechamente con la tasa a 10 años.",
  },
  {
    id: "sp500_m2",
    title: "Liquidez: S&P 500 / Masa Monetaria M2",
    metrics: ["sp500_m2"],
    scaleMode: "raw",
    range: "max",
    explanation:
      "Divide el nivel del S&P 500 por la oferta monetaria M2 de la Reserva Federal para evaluar si las valuaciones bursátiles crecen más rápido que la liquidez sistémica.",
  },
  {
    id: "rolling_cagr",
    title: "Retornos Móviles 10 Años (CAGR)",
    metrics: ["sp500_cagr_10y", "ndx_cagr_10y"],
    scaleMode: "raw",
    range: "max",
    explanation:
      "Cada punto indica el retorno anual compuesto (CAGR) ganado en los 10 años previos a esa fecha. Muestra la reversión a la media: tras décadas con retornos mayores al 15% anual, los retornos siguientes tienden a moderarse.",
  },
  {
    id: "currencies",
    title: "Dólar Global (DXY) y Monedas Emergentes",
    metrics: ["dxy", "usd_brl", "usd_jpy"],
    scaleMode: "base100",
    range: "10y",
    explanation:
      "Compara la fortaleza global del dólar (DXY) frente al Real brasileño y el Yen japonés en Base 100.",
  },
];

const RANGE_MONTHS = {
  "1y": 13,
  "3y": 37,
  "5y": 61,
  "10y": 121,
  "20y": 241,
  max: 9999,
};

function getMetricMeta(key) {
  return (
    METRIC_CATALOG.find((m) => m.key === key) || {
      key,
      label: key,
      group: "Otros",
      unit: "",
      canBase100: false,
    }
  );
}

export default function MacroLabTab() {
  const [macroData, setMacroData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [activeMetrics, setActiveMetrics] = useState(["sp500_nom", "sp500_real"]);
  const [metricToAdd, setMetricToAdd] = useState("ndx_nom");
  const [timeRange, setTimeRange] = useState("20y");
  const [scaleMode, setScaleMode] = useState("base100"); // 'base100' | 'raw' | 'dual'
  const [showMeanLine, setShowMeanLine] = useState(false);
  const [activePreset, setActivePreset] = useState(PM_PRESETS[0]);
  const [showTechnicalGuide, setShowTechnicalGuide] = useState(false);

  useEffect(() => {
    let cancelled = false;
    axios
      .get("/macro-lab")
      .then((res) => {
        if (!cancelled) setMacroData(res.data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err.response?.data?.detail ||
              "No se pudieron cargar las series macroeconómicas."
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // Validación automática de compatibilidad de escala con las métricas elegidas
  const activeMetas = activeMetrics.map(getMetricMeta);
  const supportsBase100 = activeMetas.every((m) => m.canBase100 !== false);
  const hasRollingMetric = activeMetas.some((m) => m.isRolling);
  const uniqueUnits = new Set(activeMetas.map((m) => m.unit));
  const hasMixedUnits = uniqueUnits.size > 1;

  const effectiveScaleMode =
    !supportsBase100 && scaleMode === "base100"
      ? hasMixedUnits
        ? "dual"
        : "raw"
      : scaleMode;

  const handleApplyPreset = (preset) => {
    setActivePreset(preset);
    setActiveMetrics([...preset.metrics]);
    setScaleMode(preset.scaleMode);
    setTimeRange(preset.range);
    setShowMeanLine(preset.metrics.length === 1);
  };

  const handleAddMetric = () => {
    if (!metricToAdd || activeMetrics.includes(metricToAdd)) return;
    if (activeMetrics.length >= 5) return;
    const next = [...activeMetrics, metricToAdd];
    setActiveMetrics(next);
    setActivePreset(null);

    const nextMetas = next.map(getMetricMeta);
    const nextCanBase100 = nextMetas.every((m) => m.canBase100 !== false);
    const nextUnits = new Set(nextMetas.map((m) => m.unit));
    if (nextUnits.size > 1 && !nextCanBase100) {
      setScaleMode("dual");
    } else if (!nextCanBase100 && scaleMode === "base100") {
      setScaleMode("raw");
    }
  };

  const handleRemoveMetric = (keyToRemove) => {
    if (activeMetrics.length <= 1) return;
    setActiveMetrics((prev) => prev.filter((k) => k !== keyToRemove));
    setActivePreset(null);
  };

  const { chartPoints, periodStats, primaryMean } = useMemo(() => {
    const rawTimeline = macroData?.timeline || [];
    if (!rawTimeline.length) {
      return { chartPoints: [], periodStats: [], primaryMean: null };
    }

    let sliced = rawTimeline;
    if (timeRange === "ytd") {
      const latestDate = rawTimeline[rawTimeline.length - 1]?.date || "";
      const currYear = latestDate.slice(0, 4);
      const prevDec = `${Number(currYear) - 1}-12`;
      const ytdSlice = rawTimeline.filter((pt) => pt.date >= prevDec);
      sliced = ytdSlice.length >= 2 ? ytdSlice : rawTimeline.slice(-12);
    } else {
      const maxMonths = RANGE_MONTHS[timeRange] || 9999;
      sliced =
        maxMonths >= rawTimeline.length
          ? rawTimeline
          : rawTimeline.slice(rawTimeline.length - maxMonths);
    }

    const firstValidByKey = {};
    activeMetrics.forEach((mk) => {
      const firstPt = sliced.find(
        (pt) => typeof pt[mk] === "number" && pt[mk] !== 0
      );
      if (firstPt) {
        firstValidByKey[mk] = firstPt[mk];
      }
    });

    const points = sliced.map((pt) => {
      const row = { date: pt.date };
      activeMetrics.forEach((mk) => {
        const rawVal = pt[mk];
        if (typeof rawVal === "number") {
          if (effectiveScaleMode === "base100" && firstValidByKey[mk]) {
            row[mk] = Number(((rawVal / firstValidByKey[mk]) * 100).toFixed(2));
          } else {
            row[mk] = rawVal;
          }
        }
      });
      return row;
    });

    const statsList = activeMetrics.map((mk, idx) => {
      const meta = getMetricMeta(mk);
      const vals = sliced
        .map((pt) => pt[mk])
        .filter((v) => typeof v === "number" && !Number.isNaN(v));
      if (!vals.length) {
        return {
          key: mk,
          label: meta.label,
          unit: meta.unit,
          color: SERIES_COLORS[idx % SERIES_COLORS.length],
          current: null,
          mean: null,
          min: null,
          max: null,
          changeDisplay: "-",
          isPositive: true,
        };
      }
      const first = vals[0];
      const last = vals[vals.length - 1];
      const avg = vals.reduce((a, b) => a + b, 0) / vals.length;

      let changeDisplay = "-";
      let isPositive = true;
      if (meta.unit === "%") {
        const diffPp = last - first;
        isPositive = diffPp >= 0;
        changeDisplay = `${diffPp >= 0 ? "+" : ""}${diffPp.toFixed(2)} pp`;
      } else if (first !== 0) {
        const chgPct = ((last - first) / Math.abs(first)) * 100;
        isPositive = chgPct >= 0;
        changeDisplay = `${chgPct >= 0 ? "+" : ""}${chgPct.toFixed(1)}%`;
      }

      return {
        key: mk,
        label: meta.label,
        unit: meta.unit,
        color: SERIES_COLORS[idx % SERIES_COLORS.length],
        current: last,
        mean: avg,
        min: Math.min(...vals),
        max: Math.max(...vals),
        changeDisplay,
        isPositive,
      };
    });

    const plottedVals = points
      .map((p) => p[activeMetrics[0]])
      .filter((v) => typeof v === "number");
    const meanLineVal = plottedVals.length
      ? Number(
          (
            plottedVals.reduce((a, b) => a + b, 0) / plottedVals.length
          ).toFixed(2)
        )
      : null;

    return {
      chartPoints: points,
      periodStats: statsList,
      primaryMean: meanLineVal,
    };
  }, [macroData, activeMetrics, timeRange, effectiveScaleMode]);

  if (loading) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm py-24 flex flex-col items-center justify-center text-orange-500">
        <Loader2 className="w-8 h-8 mb-3 animate-spin" />
        <p className="text-sm font-medium">
          Sincronizando series macroeconómicas, inflación CPI, tasas FRED y P/E diario de índices...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center text-red-700 text-xs font-semibold">
        {error}
      </div>
    );
  }

  const dailyPeInfo = macroData?.daily_indices_pe || { indices: [], daily_history: [] };
  const groupedCatalog = METRIC_CATALOG.reduce((acc, item) => {
    acc[item.group] = acc[item.group] || [];
    acc[item.group].push(item);
    return acc;
  }, {});

  return (
    <div className="space-y-6 text-xs">
      {/* ENCABEZADO MACRO LAB */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-gray-900 text-orange-400 flex items-center justify-center shrink-0">
            <Globe className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900">
              Macro Lab & Perspectiva Histórica Global
            </h2>
            <p className="text-[11px] text-gray-500 mt-0.5">
              Comparador multi-serie de índices nominales vs. reales (CPI), valuación diaria de índices, crédito, tasas y divisas.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-[11px]">
          {macroData?.sp500_earnings_yield_pct != null && (
            <div className="px-3 py-1.5 rounded-lg bg-gray-50 border border-gray-200">
              <span className="text-gray-500">Earnings Yield S&P 500: </span>
              <strong className="text-gray-900">
                {macroData.sp500_earnings_yield_pct.toFixed(2)}%
              </strong>
            </div>
          )}
          {macroData?.latest_ust_10y_pct != null && (
            <div className="px-3 py-1.5 rounded-lg bg-gray-50 border border-gray-200">
              <span className="text-gray-500">Tesoro USA 10Y: </span>
              <strong className="text-gray-900">
                {macroData.latest_ust_10y_pct.toFixed(2)}%
              </strong>
            </div>
          )}
          {macroData?.current_erp_pct != null && (
            <div className="px-3 py-1.5 rounded-lg bg-orange-50 border border-orange-200">
              <span className="text-orange-800">ERP Implícito Hoy: </span>
              <strong className="text-orange-950">
                {macroData.current_erp_pct >= 0 ? "+" : ""}
                {macroData.current_erp_pct.toFixed(2)}%
              </strong>
            </div>
          )}
        </div>
      </div>

      {/* BLOQUE 1: BOTONES RÁPIDOS DE PORTFOLIO MANAGER (1 CLIC + EXPLICACIÓN) */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 space-y-4">
        <div className="flex items-center justify-between">
          <span className="font-bold text-gray-900 flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-orange-500" />
            Análisis Rápidos de Portfolio Manager (1 clic para graficar y explicar)
          </span>
          <span className="text-[11px] text-gray-400">
            Configura automáticamente las series y la escala óptima
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
          {PM_PRESETS.map((p) => {
            const isSelected = activePreset?.id === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => handleApplyPreset(p)}
                className={`px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all cursor-pointer ${
                  isSelected
                    ? "bg-orange-500 text-white border-orange-500 shadow-2xs"
                    : "bg-gray-50 text-gray-700 border-gray-200 hover:bg-orange-50 hover:border-orange-300"
                }`}
              >
                {p.title}
              </button>
            );
          })}
        </div>

        {/* Tarjeta explicativa de la métrica/preset activo */}
        {activePreset && (
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-start gap-2.5 text-[11.5px] text-slate-800 leading-relaxed">
            <Info className="w-4 h-4 text-orange-500 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-slate-900">
                Qué estás mirando: {activePreset.title}
              </p>
              <p className="mt-0.5 text-slate-700">{activePreset.explanation}</p>
            </div>
          </div>
        )}
      </div>

      {/* BLOQUE 2: CONSTRUCTOR MULTI-SERIE INTERACTIVO CON GUÍA TÉCNICA */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 space-y-4">
        {/* Encabezado del constructor con botón de guía técnica */}
        <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-gray-100">
          <span className="font-bold text-gray-900">
            Constructor Multi-Serie Personalizado
          </span>
          <button
            type="button"
            onClick={() => setShowTechnicalGuide((prev) => !prev)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-800 text-[11px] font-semibold cursor-pointer transition-colors"
          >
            <HelpCircle className="w-3.5 h-3.5 text-orange-500" />
            {showTechnicalGuide
              ? "Ocultar guía de escalas y ventanas móviles"
              : "¿Qué significan Rolling, Base 100, Valor Directo y Eje Dual?"}
          </button>
        </div>

        {/* Panel desplegable de explicación de conceptos técnicos */}
        {showTechnicalGuide && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-4 rounded-xl bg-slate-900 text-gray-200 text-[11px] leading-relaxed">
            <div className="space-y-1.5">
              <p className="font-bold text-orange-400">
                1. Diferencia entre "Métrica (12M / 3Y / 5Y / 10Y)" y "Rango del Gráfico"
              </p>
              <p>
                • <strong>Métrica (ej. Retorno Móvil / Rolling 10Y):</strong> Indica <em>qué calcula cada punto</em>. En un retorno Rolling 10Y, cada fecha muestra el rendimiento anual compuesto (CAGR) que obtuvo alguien que compró 10 años antes y vendió en esa fecha.
              </p>
              <p>
                • <strong>Rango de fechas en pantalla (YTD, 1Y, 5Y, 20Y, MAX):</strong> Controla únicamente <em>cuántos años de historia se muestran en el eje horizontal (X)</em>.
              </p>
            </div>
            <div className="space-y-1.5">
              <p className="font-bold text-orange-400">
                2. Cómo elegir la Escala del Eje Vertical (Y)
              </p>
              <p>
                • <strong>Base 100:</strong> Iguala todas las series a 100 en la primera fecha visible para comparar <em>rendimientos acumulados</em> (solo válido para precios, índices o ratios positivos; deshabilitado en porcentajes).
              </p>
              <p>
                • <strong>Valor Directo:</strong> Grafica el número real exacto (obligatorio para porcentajes %, tasas o spreads).
              </p>
              <p>
                • <strong>Eje Dual:</strong> Usa el eje izquierdo para la 1ª serie y el derecho para las siguientes cuando comparás variables con unidades distintas (ej. S&P 500 en puntos vs. Tasa 10Y en %).
              </p>
            </div>
          </div>
        )}

        {/* Controles estructurados en 3 bloques claros */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 pb-3 border-b border-gray-100 items-end">
          {/* Control 1: Selector de Métrica */}
          <div className="lg:col-span-5 space-y-1">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-gray-500">
              1. Métrica a evaluar (qué calcula cada punto)
            </label>
            <div className="flex items-center gap-2">
              <select
                value={metricToAdd}
                onChange={(e) => setMetricToAdd(e.target.value)}
                className="flex-1 min-w-0 px-3 py-1.5 border border-gray-300 rounded-lg bg-gray-50 text-gray-900 font-medium focus:outline-none focus:border-orange-500"
              >
                {Object.entries(groupedCatalog).map(([groupName, items]) => (
                  <optgroup key={groupName} label={groupName}>
                    {items.map((it) => (
                      <option key={it.key} value={it.key}>
                        {it.label}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>

              <button
                type="button"
                onClick={handleAddMetric}
                disabled={
                  activeMetrics.includes(metricToAdd) || activeMetrics.length >= 5
                }
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gray-900 hover:bg-gray-800 text-white font-semibold cursor-pointer disabled:opacity-40 shrink-0"
              >
                <Plus className="w-3.5 h-3.5" />
                Agregar
              </button>
            </div>
          </div>

          {/* Control 2: Escala del eje Y */}
          <div className="lg:col-span-4 space-y-1">
            <div className="flex items-center justify-between">
              <label className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
                2. Escala del eje Y
              </label>
              {!supportsBase100 && (
                <span className="text-[10px] text-amber-700 font-semibold">
                  Base 100 desactivado (hay series en % o ≤ 0)
                </span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <div className="inline-flex rounded-lg border border-gray-300 bg-gray-100 p-0.5">
                <button
                  type="button"
                  disabled={!supportsBase100}
                  title={
                    !supportsBase100
                      ? "No disponible: al menos una métrica activa está en % o puede tomar valores negativos/cero"
                      : "Iguala todas las series a 100 al inicio del período para comparar rendimiento acumulado"
                  }
                  onClick={() => setScaleMode("base100")}
                  className={`px-2.5 py-1 rounded text-[11px] font-semibold ${
                    !supportsBase100
                      ? "text-gray-400 cursor-not-allowed"
                      : effectiveScaleMode === "base100"
                      ? "bg-white text-orange-600 shadow-2xs cursor-pointer"
                      : "text-gray-600 cursor-pointer"
                  }`}
                >
                  Base 100
                </button>
                <button
                  type="button"
                  title="Grafica el valor real exacto de cada métrica sin reescalar"
                  onClick={() => setScaleMode("raw")}
                  className={`px-2.5 py-1 rounded text-[11px] font-semibold cursor-pointer ${
                    effectiveScaleMode === "raw"
                      ? "bg-white text-orange-600 shadow-2xs"
                      : "text-gray-600"
                  }`}
                >
                  Valor Directo
                </button>
                <button
                  type="button"
                  title="Eje izquierdo para la 1ª métrica y eje derecho para las siguientes"
                  onClick={() => setScaleMode("dual")}
                  className={`px-2.5 py-1 rounded text-[11px] font-semibold cursor-pointer ${
                    effectiveScaleMode === "dual"
                      ? "bg-white text-orange-600 shadow-2xs"
                      : "text-gray-600"
                  }`}
                >
                  Eje Dual
                </button>
              </div>

              <button
                type="button"
                onClick={() => setShowMeanLine((prev) => !prev)}
                className={`px-2.5 py-1.5 rounded-lg border text-[11px] font-semibold cursor-pointer ${
                  showMeanLine
                    ? "bg-orange-50 border-orange-300 text-orange-700"
                    : "bg-white border-gray-300 text-gray-600"
                }`}
              >
                Promedio
              </button>
            </div>
          </div>

          {/* Control 3: Rango temporal visible en el gráfico */}
          <div className="lg:col-span-3 space-y-1">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-gray-500">
              3. Rango de fechas en pantalla (Eje X)
            </label>
            <div className="inline-flex rounded-lg border border-gray-300 bg-gray-100 p-0.5 w-full justify-between">
              {["ytd", "1y", "3y", "5y", "10y", "20y", "max"].map((rng) => (
                <button
                  key={rng}
                  type="button"
                  onClick={() => setTimeRange(rng)}
                  className={`px-2 py-1 rounded text-[11px] font-bold uppercase cursor-pointer ${
                    timeRange === rng
                      ? "bg-orange-500 text-white"
                      : "text-gray-600 hover:text-gray-900"
                  }`}
                >
                  {rng}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Aviso contextual automático cuando se grafica una serie Rolling */}
        {hasRollingMetric && (
          <div className="p-2.5 rounded-lg bg-amber-50/80 border border-amber-200 text-[11px] text-amber-950 flex items-start gap-2">
            <Info className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
            <span>
              <strong>Lectura de Retorno Móvil (Rolling):</strong> Cada punto de la curva muestra el rendimiento anualizado que habrías obtenido comprando al inicio de esa ventana móvil (12M, 3Y, 5Y o 10Y) y vendiendo en la fecha marcada en el eje horizontal.
            </span>
          </div>
        )}

        {/* Chips de métricas activas en el gráfico (quitar de a 1) */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold text-gray-500 flex items-center gap-1 mr-1">
            <Layers className="w-3.5 h-3.5" /> Series en gráfico ({activeMetrics.length}/5):
          </span>
          {activeMetrics.map((mk, idx) => {
            const meta = getMetricMeta(mk);
            const color = SERIES_COLORS[idx % SERIES_COLORS.length];
            const axisTag =
              effectiveScaleMode === "dual"
                ? idx === 0
                  ? " · Eje Izq."
                  : " · Eje Der."
                : "";
            return (
              <span
                key={mk}
                className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full border border-gray-200 bg-gray-50 text-gray-800 font-semibold"
              >
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: color }}
                />
                <span>
                  {meta.label}
                  {axisTag && (
                    <span className="text-[10px] text-gray-500 font-normal">
                      {axisTag}
                    </span>
                  )}
                </span>
                {activeMetrics.length > 1 && (
                  <button
                    type="button"
                    onClick={() => handleRemoveMetric(mk)}
                    title="Quitar métrica del gráfico"
                    className="text-gray-400 hover:text-red-600 cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </span>
            );
          })}
        </div>

        {/* Gráfico Multi-Serie Recharts */}
        <div className="h-96 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={chartPoints}
              margin={{ top: 10, right: 20, left: 5, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: "#6b7280" }}
                minTickGap={35}
              />
              <YAxis
                yAxisId="left"
                tick={{ fontSize: 11, fill: "#6b7280" }}
                domain={["auto", "auto"]}
              />
              {effectiveScaleMode === "dual" && activeMetrics.length > 1 && (
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fontSize: 11, fill: "#2563eb" }}
                  domain={["auto", "auto"]}
                />
              )}
              <Tooltip
                contentStyle={{
                  backgroundColor: "#18181b",
                  borderColor: "#3f3f46",
                  borderRadius: "8px",
                  color: "#f4f4f5",
                  fontSize: "12px",
                }}
              />
              {showMeanLine && primaryMean !== null && (
                <ReferenceLine
                  yAxisId="left"
                  y={primaryMean}
                  stroke="#f97316"
                  strokeDasharray="5 5"
                  label={{
                    value: `Prom: ${primaryMean}`,
                    position: "insideTopLeft",
                    fill: "#ea580c",
                    fontSize: 11,
                  }}
                />
              )}
              {activeMetrics.map((mk, idx) => {
                const meta = getMetricMeta(mk);
                const axisId =
                  effectiveScaleMode === "dual" && idx >= 1 ? "right" : "left";
                return (
                  <Line
                    key={mk}
                    yAxisId={axisId}
                    type="monotone"
                    dataKey={mk}
                    name={
                      effectiveScaleMode === "base100"
                        ? `${meta.label} (Base 100)`
                        : meta.label
                    }
                    stroke={SERIES_COLORS[idx % SERIES_COLORS.length]}
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                );
              })}
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Tabla resumen estadístico del período visible */}
        <div className="overflow-x-auto pt-2 border-t border-gray-100">
          <table className="w-full text-xs text-right">
            <thead>
              <tr className="bg-gray-100 text-gray-700">
                <th className="py-2 px-3 text-left">Métrica Analizada</th>
                <th className="py-2 px-3">Último Valor</th>
                <th className="py-2 px-3">Promedio Período</th>
                <th className="py-2 px-3">Mínimo</th>
                <th className="py-2 px-3">Máximo</th>
                <th className="py-2 px-3">Cambio en Período</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {periodStats.map((st) => {
                const suf = st.unit === "%" ? "%" : "";
                return (
                  <tr key={st.key} className="hover:bg-gray-50">
                    <td className="py-2 px-3 text-left font-bold text-gray-900 flex items-center gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: st.color }}
                      />
                      {st.label}
                    </td>
                    <td className="py-2 px-3 tabular-nums font-bold text-gray-900">
                      {st.current !== null ? `${st.current.toFixed(2)}${suf}` : "-"}
                    </td>
                    <td className="py-2 px-3 tabular-nums text-gray-700">
                      {st.mean !== null ? `${st.mean.toFixed(2)}${suf}` : "-"}
                    </td>
                    <td className="py-2 px-3 tabular-nums text-gray-600">
                      {st.min !== null ? `${st.min.toFixed(2)}${suf}` : "-"}
                    </td>
                    <td className="py-2 px-3 tabular-nums text-gray-600">
                      {st.max !== null ? `${st.max.toFixed(2)}${suf}` : "-"}
                    </td>
                    <td
                      className={`py-2 px-3 tabular-nums font-semibold ${
                        st.isPositive ? "text-emerald-700" : "text-[#d93025]"
                      }`}
                    >
                      {st.changeDisplay}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* BLOQUE 3: VALUACIÓN DIARIA DE ÍNDICES GLOBALES (P/E ACTUALIZADO DIARIAMENTE) */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-5 py-3.5 bg-gray-50 border-b border-gray-200 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-orange-500" />
            <h3 className="text-sm font-bold text-gray-900">
              P/E Actual de los Principales Índices (Registro Diario Automático)
            </h3>
          </div>
          <span className="text-[11px] text-gray-500 flex items-center gap-1">
            <Calendar className="w-3.5 h-3.5" /> Último snapshot diario:{" "}
            <strong>{dailyPeInfo.updated_date}</strong>
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-right">
            <thead>
              <tr className="bg-[#333333] text-white">
                <th className="py-2.5 px-4 text-left">Índice Bursátil</th>
                <th className="py-2.5 px-3 text-left">ETF Proxy</th>
                <th className="py-2.5 px-3">Cotización</th>
                <th className="py-2.5 px-3">P/E Actual (LTM)</th>
                <th className="py-2.5 px-3">P/E Forward (NTM)</th>
                <th className="py-2.5 px-3">Earnings Yield</th>
                <th className="py-2.5 px-3">Prom. Histórico P/E</th>
                <th className="py-2.5 px-4">Prima / (Descuento)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {(dailyPeInfo.indices || []).map((idxRow) => {
                const prem = idxRow.vs_hist_avg_pct;
                return (
                  <tr key={idxRow.code} className="hover:bg-gray-50">
                    <td className="py-2.5 px-4 text-left font-bold text-gray-900">
                      {idxRow.name}
                    </td>
                    <td className="py-2.5 px-3 text-left font-semibold text-orange-600">
                      {idxRow.proxy}
                    </td>
                    <td className="py-2.5 px-3 tabular-nums">
                      {idxRow.price ? `US$ ${idxRow.price.toFixed(2)}` : "-"}
                    </td>
                    <td className="py-2.5 px-3 tabular-nums font-bold text-gray-900">
                      {idxRow.pe_trailing ? `${idxRow.pe_trailing.toFixed(2)}x` : "-"}
                    </td>
                    <td className="py-2.5 px-3 tabular-nums text-gray-700">
                      {idxRow.pe_forward ? `${idxRow.pe_forward.toFixed(2)}x` : "-"}
                    </td>
                    <td className="py-2.5 px-3 tabular-nums text-gray-700">
                      {idxRow.earnings_yield_pct
                        ? `${idxRow.earnings_yield_pct.toFixed(2)}%`
                        : "-"}
                    </td>
                    <td className="py-2.5 px-3 tabular-nums text-gray-600">
                      {idxRow.hist_pe_avg.toFixed(1)}x
                    </td>
                    <td
                      className={`py-2.5 px-4 tabular-nums font-bold ${
                        prem === null
                          ? "text-gray-400"
                          : prem <= 0
                          ? "text-emerald-700"
                          : "text-[#d93025]"
                      }`}
                    >
                      {prem !== null
                        ? `${prem > 0 ? "+" : ""}${prem.toFixed(1)}%`
                        : "-"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}