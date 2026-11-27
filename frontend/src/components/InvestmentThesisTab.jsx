import { useEffect, useState } from "react";
import apiClient from "../api/client";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";
import {
  Presentation,
  Search,
  Loader2,
  Printer,
  Edit3,
  Check,
  Plus,
  Trash2,
  RotateCcw,
  ShieldCheck,
  AlertTriangle,
  Target,
  Building2,
  Globe2,
  Users,
  BarChart2,
} from "lucide-react";

const PIE_COLORS = [
  "#f97316", // Naranja Vektor
  "#1e293b", // Slate oscuro
  "#2563eb", // Azul institucional
  "#10b981", // Esmeralda
  "#8b5cf6", // Violeta
  "#eab308", // Ámbar
  "#ec4899", // Magenta
  "#06b6d4", // Cian
];

function formatMoney(val) {
  if (val === null || val === undefined || Number.isNaN(val)) return "-";
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(val);
}

export default function InvestmentThesisTab({
  initialTicker = "",
  recentTickers = [],
  onSelectGlobalTicker,
}) {
  const [selectedTicker, setSelectedTicker] = useState(
    initialTicker ? initialTicker.toUpperCase() : ""
  );
  const [searchInput, setSearchInput] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(Boolean(initialTicker));
  const [savingSegments, setSavingSegments] = useState(false);
  const [error, setError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);

  const [pillars, setPillars] = useState([]);
  const [risks, setRisks] = useState([]);
  const [bizSegments, setBizSegments] = useState([]);
  const [geoSegments, setGeoSegments] = useState([]);
  const [clientsNote, setClientsNote] = useState("");
  const [isCustomSegments, setIsCustomSegments] = useState(false);
  const [advisorNote, setAdvisorNote] = useState(
    "Tesis elaborada con estados auditados SEC/EDGAR y modelos propios de valoración intrínseca."
  );

  useEffect(() => {
    if (!selectedTicker) return;
    let cancelled = false;

    apiClient
      .get(
        `/company/${selectedTicker}/thesis-onepager`
      )
      .then((res) => {
        if (!cancelled) {
          setError(null);
          setData(res.data);
          setPillars(res.data.thesis_pillars || []);
          setRisks(res.data.risks || []);
          setBizSegments(res.data.business_segments || []);
          setGeoSegments(res.data.geo_segments || []);
          setClientsNote(res.data.key_clients_notes || "");
          setIsCustomSegments(Boolean(res.data.is_custom_segments));
          setIsEditing(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err.response?.data?.detail ||
              "No se pudo generar el dashboard de tesis para este ticker."
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

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
    setLoading(true);
    setError(null);
    setSelectedTicker(clean);
    setSearchInput("");
    setShowDropdown(false);
    if (onSelectGlobalTicker) onSelectGlobalTicker(clean);
  };

  const recalculateShares = (list) => {
    const total = list.reduce((acc, s) => acc + (Number(s.revenue_mm) || 0), 0);
    return list.map((s) => ({
      ...s,
      share_pct:
        total > 0
          ? Number((((Number(s.revenue_mm) || 0) / total) * 100).toFixed(1))
          : 0,
    }));
  };

  const handleToggleEditOrSave = async () => {
    if (!isEditing) {
      setIsEditing(true);
      return;
    }
    setSavingSegments(true);
    try {
      const res = await apiClient.put(
        `/company/${selectedTicker}/segments`,
        {
          business_segments: bizSegments,
          geo_segments: geoSegments,
          key_clients_notes: clientsNote,
        }
      );
      setBizSegments(res.data.business_segments || []);
      setGeoSegments(res.data.geo_segments || []);
      setClientsNote(res.data.key_clients_notes || "");
      setIsCustomSegments(true);
      setIsEditing(false);
    } catch (err) {
      console.error("Error guardando segmentos:", err);
      setIsEditing(false);
    } finally {
      setSavingSegments(false);
    }
  };

  const handleResetSegmentsFromSec = async () => {
    setLoading(true);
    try {
      const res = await apiClient.delete(
        `/company/${selectedTicker}/segments`
      );
      setData(res.data);
      setBizSegments(res.data.business_segments || []);
      setGeoSegments(res.data.geo_segments || []);
      setClientsNote(res.data.key_clients_notes || "");
      setIsCustomSegments(false);
      setIsEditing(false);
    } catch (err) {
      console.error("Error restaurando segmentos:", err);
    } finally {
      setLoading(false);
    }
  };

  if (!selectedTicker) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-10 text-center max-w-3xl mx-auto mt-6">
        <div className="w-12 h-12 rounded-xl bg-orange-50 text-orange-500 flex items-center justify-center mx-auto mb-4">
          <Presentation className="w-6 h-6" />
        </div>
        <h2 className="text-lg font-bold text-gray-900">
          One-Pager Ejecutivo de Tesis de Inversión
        </h2>
        <p className="text-xs text-gray-600 max-w-xl mx-auto mt-1.5 leading-relaxed">
          Generá una ficha visual ejecutiva lista para presentar a clientes: resumen del negocio, desglose por unidades y regiones, trayectoria 5Y, múltiplos, rango de valuación y riesgos.
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
            placeholder="Elegí una empresa para armar su presentación (ej: MSFT, AAPL, NVDA)..."
            autoFocus
            className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-300 rounded-lg text-xs text-gray-900 focus:outline-none focus:bg-white focus:border-orange-500"
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
                  className="px-3 py-1.5 rounded-lg border border-gray-200 bg-gray-50 hover:bg-orange-50 hover:border-orange-300 text-xs font-semibold text-gray-800 cursor-pointer"
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

  const company = data?.company || {};
  const kpis = data?.kpis || {};
  const qMom = data?.quarterly_momentum || {};
  const valBridge = data?.valuation_bridge || {};
  const trend = data?.financial_trend || [];
  const multiplesList = data?.multiples_list || [];

  const hasBizChart = bizSegments.length > 1 || isEditing;
  const hasGeoChart = geoSegments.length > 1 || isEditing;

  // Escala común para gráfico estilo Football Field
  const allPrices = [
    valBridge.current_price || 0,
    valBridge.intrinsic_low || 0,
    valBridge.intrinsic_high || 0,
    valBridge.consensus_target || 0,
  ].filter((v) => v > 0);
  const maxAxisPrice = allPrices.length ? Math.max(...allPrices) * 1.15 : 100;

  const pctPos = (priceVal) =>
    maxAxisPrice > 0
      ? Math.min(Math.max(((priceVal || 0) / maxAxisPrice) * 100, 0), 100)
      : 0;

  const lowPct = pctPos(valBridge.intrinsic_low);
  const highPct = pctPos(valBridge.intrinsic_high);
  const midPct = pctPos(valBridge.intrinsic_mid);
  const curPct = pctPos(valBridge.current_price);
  const wsPct = pctPos(valBridge.consensus_target);

  return (
    <div className="space-y-5 text-xs pb-10">
      {/* BARRA DE ACCIONES (OCULTA AL IMPRIMIR PDF) */}
      <div className="print:hidden bg-white border border-gray-200 rounded-xl shadow-sm p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="relative w-72">
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
            placeholder="Cambiar empresa (ej: AAPL, MSFT, NVDA)..."
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
                  <span className="font-bold text-orange-600">{r.ticker}</span>
                  <span className="text-gray-700 truncate mx-2 flex-1">
                    {r.name}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {isCustomSegments && (
            <button
              type="button"
              onClick={handleResetSegmentsFromSec}
              title="Descartar personalización y volver a leer XBRL desde SEC"
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-gray-600 font-medium cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Restaurar SEC
            </button>
          )}

          <button
            type="button"
            disabled={savingSegments}
            onClick={handleToggleEditOrSave}
            className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border font-semibold cursor-pointer transition-colors ${
              isEditing
                ? "bg-emerald-600 border-emerald-600 text-white"
                : "bg-gray-50 border-gray-300 text-gray-800 hover:bg-gray-100"
            }`}
          >
            {isEditing ? (
              <>
                <Check className="w-3.5 h-3.5" />
                {savingSegments ? "Guardando..." : "Guardar y Ver Ficha"}
              </>
            ) : (
              <>
                <Edit3 className="w-3.5 h-3.5" /> Personalizar Tesis y Segmentos
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-orange-500 hover:bg-orange-600 text-white font-semibold cursor-pointer shadow-2xs"
          >
            <Printer className="w-3.5 h-3.5" />
            Exportar PDF / Presentar
          </button>
        </div>
      </div>

      {loading ? (
        <div className="bg-white border border-gray-200 rounded-xl p-20 flex flex-col items-center justify-center text-orange-500">
          <Loader2 className="w-8 h-8 mb-3 animate-spin" />
          <p className="font-medium">
            Compilando ficha ejecutiva, estados auditados y modelos de valuación para{" "}
            {selectedTicker}...
          </p>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center text-red-700 font-semibold">
          {error}
        </div>
      ) : (
        data && (
          <div className="space-y-5">
            {/* 1. CABECERA EJECUTIVA ESTILO MEMO DE INVERSIÓN */}
            <div className="bg-slate-900 text-white rounded-2xl p-6 shadow-md flex flex-wrap items-center justify-between gap-6">
              <div className="flex items-start gap-4 max-w-2xl">
                <div className="w-14 h-14 rounded-xl bg-orange-500 text-white font-extrabold text-2xl flex items-center justify-center shrink-0 shadow-sm">
                  {data.ticker.charAt(0)}
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span className="px-2 py-0.5 rounded bg-orange-500/20 text-orange-300 font-bold text-[11px] uppercase tracking-wider">
                      Ficha de Tesis de Inversión
                    </span>
                    <span className="text-slate-400 text-[11px]">
                      Emisión: {data.generated_date}
                    </span>
                    {qMom.latest_quarter && qMom.rev_yoy_pct !== null && (
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-emerald-300 text-[10px] font-semibold">
                        Último Trim. ({qMom.latest_quarter}): Ventas{" "}
                        {qMom.rev_yoy_pct >= 0 ? "+" : ""}
                        {qMom.rev_yoy_pct}% YoY
                      </span>
                    )}
                  </div>
                  <h1 className="text-2xl font-extrabold tracking-tight mt-1">
                    {company.name}{" "}
                    <span className="text-orange-400">({data.ticker})</span>
                  </h1>
                  <p className="text-slate-300 text-xs mt-1">
                    {company.sector || "Sector Corporativo"}
                    {company.industry ? ` · ${company.industry}` : ""}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-5 bg-slate-800/80 border border-slate-700 rounded-xl p-4 text-right">
                <div>
                  <span className="text-[10px] uppercase tracking-wider text-slate-400 block">
                    Precio Actual
                  </span>
                  <span className="text-lg font-extrabold text-white">
                    {formatMoney(company.price)}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] uppercase tracking-wider text-slate-400 block">
                    Valor Intrínseco Est.
                  </span>
                  <span className="text-lg font-extrabold text-emerald-400">
                    {formatMoney(valBridge.intrinsic_mid)}
                  </span>
                </div>
                <div className="col-span-2 sm:col-span-1">
                  <span className="text-[10px] uppercase tracking-wider text-slate-400 block">
                    Potencial Estimado
                  </span>
                  <span
                    className={`text-lg font-extrabold ${
                      (valBridge.upside_mid_pct || 0) >= 0
                        ? "text-emerald-400"
                        : "text-rose-400"
                    }`}
                  >
                    {(valBridge.upside_mid_pct || 0) >= 0 ? "+" : ""}
                    {(valBridge.upside_mid_pct || 0).toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>

            {/* 2. BARRA DE 6 INDICADORES CLAVE */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="bg-white border border-gray-200 rounded-xl p-3.5 shadow-2xs">
                <span className="text-[10px] font-bold uppercase text-gray-400">
                  CAGR Ventas (5Y)
                </span>
                <p className="text-lg font-extrabold text-gray-900 mt-1">
                  {kpis.rev_cagr_5y_pct !== null
                    ? `${kpis.rev_cagr_5y_pct >= 0 ? "+" : ""}${kpis.rev_cagr_5y_pct}%`
                    : "-"}
                </p>
              </div>
              <div className="bg-white border border-gray-200 rounded-xl p-3.5 shadow-2xs">
                <span className="text-[10px] font-bold uppercase text-gray-400">
                  Margen Operativo
                </span>
                <p className="text-lg font-extrabold text-gray-900 mt-1">
                  {kpis.operating_margin_pct !== null
                    ? `${kpis.operating_margin_pct}%`
                    : "-"}
                </p>
              </div>
              <div className="bg-white border border-gray-200 rounded-xl p-3.5 shadow-2xs">
                <span className="text-[10px] font-bold uppercase text-gray-400">
                  Margen FCF
                </span>
                <p className="text-lg font-extrabold text-gray-900 mt-1">
                  {kpis.fcf_margin_pct !== null
                    ? `${kpis.fcf_margin_pct}%`
                    : "-"}
                </p>
              </div>
              <div className="bg-white border border-gray-200 rounded-xl p-3.5 shadow-2xs">
                <span className="text-[10px] font-bold uppercase text-gray-400">
                  {kpis.roic_pct !== null ? "ROIC" : "ROE"}
                </span>
                <p className="text-lg font-extrabold text-gray-900 mt-1">
                  {kpis.roic_pct !== null
                    ? `${kpis.roic_pct}%`
                    : kpis.roe_pct !== null
                    ? `${kpis.roe_pct}%`
                    : "-"}
                </p>
              </div>
              <div className="bg-white border border-gray-200 rounded-xl p-3.5 shadow-2xs">
                <span className="text-[10px] font-bold uppercase text-gray-400">
                  Piotroski F-Score
                </span>
                <p className="text-lg font-extrabold text-emerald-700 mt-1">
                  {kpis.piotroski_score !== null
                    ? `${kpis.piotroski_score} / 9`
                    : "-"}
                </p>
              </div>
              <div className="bg-white border border-gray-200 rounded-xl p-3.5 shadow-2xs">
                <span className="text-[10px] font-bold uppercase text-gray-400">
                  Cap. Bursátil
                </span>
                <p className="text-lg font-extrabold text-gray-900 mt-1">
                  {company.market_cap || "-"}
                </p>
              </div>
            </div>
            {data?.audit?.has_anomalies && data?.dcf_engine?.reported?.solvable && (
              <div className="bg-amber-50/80 border border-amber-200 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs">
                <div>
                  <span className="font-bold text-amber-950">
                    Eventos extraordinarios detectados ({data.audit.flags?.length || 0})
                  </span>
                  <span className="text-amber-800 ml-2">
                    Realidad fría: US$ {data.dcf_engine.reported.intrinsic_price} vs Normalizado: US$ {data.dcf_engine.normalized.intrinsic_price}
                  </span>
                </div>
                <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 font-bold tabular-nums">
                  {data.dcf_engine.total_delta_per_share >= 0 ? "+" : ""}
                  {data.dcf_engine.total_delta_per_share} US$/acc
                </span>
              </div>
            )}

            {/* 3. RESUMEN DEL NEGOCIO Y TESIS EN 3 PILARES */}
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 space-y-4">
              <div>
                <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-orange-500" />
                  Resumen del Negocio y Propuesta de Valor
                </h3>
                <p className="text-gray-600 mt-1.5 leading-relaxed line-clamp-3">
                  {company.description}
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                {pillars.map((pil, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1.5"
                  >
                    {isEditing ? (
                      <>
                        <input
                          type="text"
                          value={pil.title}
                          onChange={(e) =>
                            setPillars((prev) =>
                              prev.map((p, i) =>
                                i === idx ? { ...p, title: e.target.value } : p
                              )
                            )
                          }
                          className="w-full px-2 py-1 border border-gray-300 rounded bg-white font-bold text-gray-900"
                        />
                        <textarea
                          rows={4}
                          value={pil.body}
                          onChange={(e) =>
                            setPillars((prev) =>
                              prev.map((p, i) =>
                                i === idx ? { ...p, body: e.target.value } : p
                              )
                            )
                          }
                          className="w-full px-2 py-1 border border-gray-300 rounded bg-white text-gray-700"
                        />
                      </>
                    ) : (
                      <>
                        <p className="font-bold text-slate-900">{pil.title}</p>
                        <p className="text-slate-700 leading-relaxed">
                          {pil.body}
                        </p>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* 4. BLOQUE ADAPTATIVO: UNIDADES DE NEGOCIO / REGIONES O MÚLTIPLOS Y CALIDAD */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* PANEL IZQUIERDO: Unidades de Negocio (si hay desglose) o Múltiplos de Valuación */}
              {hasBizChart ? (
                <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-gray-900">
                      Ingresos y Márgenes por Unidad de Negocio
                    </h3>
                    {isEditing && (
                      <button
                        type="button"
                        onClick={() =>
                          setBizSegments((prev) =>
                            recalculateShares([
                              ...prev,
                              {
                                name: "Nueva Unidad",
                                revenue_mm: 1000,
                                operating_margin_pct: 20,
                              },
                            ])
                          )
                        }
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-orange-50 text-orange-700 font-semibold cursor-pointer"
                      >
                        <Plus className="w-3 h-3" /> Agregar unidad
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-center">
                    <div className="h-52">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={bizSegments}
                            dataKey="share_pct"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            innerRadius={45}
                            outerRadius={78}
                            paddingAngle={2}
                          >
                            {bizSegments.map((_, i) => (
                              <Cell
                                key={i}
                                fill={PIE_COLORS[i % PIE_COLORS.length]}
                              />
                            ))}
                          </Pie>
                          <Tooltip
                            formatter={(val) => `${Number(val).toFixed(1)}%`}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>

                    <div className="space-y-2">
                      {bizSegments.map((seg, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between text-[11px] border-b border-gray-100 pb-1.5"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <span
                              className="w-2.5 h-2.5 rounded-full shrink-0"
                              style={{
                                backgroundColor:
                                  PIE_COLORS[i % PIE_COLORS.length],
                              }}
                            />
                            {isEditing ? (
                              <input
                                type="text"
                                value={seg.name}
                                onChange={(e) =>
                                  setBizSegments((prev) =>
                                    prev.map((item, idx) =>
                                      idx === i
                                        ? { ...item, name: e.target.value }
                                        : item
                                    )
                                  )
                                }
                                className="px-1.5 py-0.5 border border-gray-300 rounded w-28"
                              />
                            ) : (
                              <span className="font-semibold text-gray-800 truncate">
                                {seg.name}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 shrink-0 tabular-nums">
                            {isEditing ? (
                              <>
                                <input
                                  type="number"
                                  value={seg.revenue_mm}
                                  onChange={(e) =>
                                    setBizSegments((prev) =>
                                      recalculateShares(
                                        prev.map((item, idx) =>
                                          idx === i
                                            ? {
                                                ...item,
                                                revenue_mm:
                                                  Number(e.target.value) || 0,
                                              }
                                            : item
                                        )
                                      )
                                    )
                                  }
                                  className="w-16 px-1 py-0.5 border border-gray-300 rounded text-right"
                                />
                                <button
                                  type="button"
                                  onClick={() =>
                                    setBizSegments((prev) =>
                                      recalculateShares(
                                        prev.filter((_, idx) => idx !== i)
                                      )
                                    )
                                  }
                                  className="text-red-500 cursor-pointer"
                                >
                                  <Trash2 className="w-3 h-3" />
                                </button>
                              </>
                            ) : (
                              <>
                                <span className="font-bold text-gray-900">
                                  {seg.share_pct}%
                                </span>
                                {seg.operating_margin_pct !== null && (
                                  <span className="text-gray-500">
                                    (M.Op {seg.operating_margin_pct}%)
                                  </span>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
                      <BarChart2 className="w-4 h-4 text-orange-500" />
                      Múltiplos de Valuación (Actual vs. Mediana 5Y)
                    </h3>
                    <button
                      type="button"
                      onClick={() => setIsEditing(true)}
                      className="print:hidden text-[11px] text-orange-600 font-semibold hover:underline cursor-pointer"
                    >
                      + Cargar unidades
                    </button>
                  </div>

                  <table className="w-full text-xs text-right">
                    <thead>
                      <tr className="bg-gray-100 text-gray-700">
                        <th className="py-2 px-3 text-left">Múltiplo</th>
                        <th className="py-2 px-3">Actual (LTM)</th>
                        <th className="py-2 px-3">Mediana 5Y</th>
                        <th className="py-2 px-3">vs. Historia</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {multiplesList.map((m, idx) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          <td className="py-2 px-3 text-left font-semibold text-gray-800">
                            {m.metric}
                          </td>
                          <td className="py-2 px-3 tabular-nums font-bold text-gray-900">
                            {typeof m.ltm === "number"
                              ? `${m.ltm.toFixed(1)}${m.suffix}`
                              : "-"}
                          </td>
                          <td className="py-2 px-3 tabular-nums text-gray-600">
                            {typeof m.med_5y === "number"
                              ? `${m.med_5y.toFixed(1)}${m.suffix}`
                              : "-"}
                          </td>
                          <td
                            className={`py-2 px-3 tabular-nums font-semibold ${
                              m.vs_med_pct === null
                                ? "text-gray-400"
                                : m.vs_med_pct <= 0
                                ? "text-emerald-700"
                                : "text-amber-700"
                            }`}
                          >
                            {m.vs_med_pct !== null
                              ? `${m.vs_med_pct > 0 ? "+" : ""}${m.vs_med_pct}%`
                              : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* PANEL DERECHO: Geografía (si hay desglose) o Múltiplos + Clientes */}
              {hasGeoChart ? (
                <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 flex flex-col justify-between space-y-3">
                  <div>
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
                        <Globe2 className="w-4 h-4 text-orange-500" />
                        Distribución Geográfica de Ingresos
                      </h3>
                      {isEditing && (
                        <button
                          type="button"
                          onClick={() =>
                            setGeoSegments((prev) =>
                              recalculateShares([
                                ...prev,
                                { name: "Nuevo País / Región", revenue_mm: 1000 },
                              ])
                            )
                          }
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-orange-50 text-orange-700 font-semibold cursor-pointer"
                        >
                          <Plus className="w-3 h-3" /> Agregar región
                        </button>
                      )}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-center mt-2">
                      <div className="h-44">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={geoSegments}
                              dataKey="share_pct"
                              nameKey="name"
                              cx="50%"
                              cy="50%"
                              innerRadius={40}
                              outerRadius={70}
                              paddingAngle={2}
                            >
                              {geoSegments.map((_, i) => (
                                <Cell
                                  key={i}
                                  fill={PIE_COLORS[(i + 2) % PIE_COLORS.length]}
                                />
                              ))}
                            </Pie>
                            <Tooltip
                              formatter={(val) => `${Number(val).toFixed(1)}%`}
                            />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>

                      <div className="space-y-2">
                        {geoSegments.map((geo, i) => (
                          <div
                            key={i}
                            className="flex items-center justify-between text-[11px] border-b border-gray-100 pb-1.5"
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span
                                className="w-2.5 h-2.5 rounded-full shrink-0"
                                style={{
                                  backgroundColor:
                                    PIE_COLORS[(i + 2) % PIE_COLORS.length],
                                }}
                              />
                              {isEditing ? (
                                <input
                                  type="text"
                                  value={geo.name}
                                  onChange={(e) =>
                                    setGeoSegments((prev) =>
                                      prev.map((item, idx) =>
                                        idx === i
                                          ? { ...item, name: e.target.value }
                                          : item
                                      )
                                    )
                                  }
                                  className="px-1.5 py-0.5 border border-gray-300 rounded w-28"
                                />
                              ) : (
                                <span className="font-semibold text-gray-800 truncate">
                                  {geo.name}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2 tabular-nums">
                              {isEditing ? (
                                <>
                                  <input
                                    type="number"
                                    value={geo.revenue_mm}
                                    onChange={(e) =>
                                      setGeoSegments((prev) =>
                                        recalculateShares(
                                          prev.map((item, idx) =>
                                            idx === i
                                              ? {
                                                  ...item,
                                                  revenue_mm:
                                                    Number(e.target.value) || 0,
                                                }
                                              : item
                                          )
                                        )
                                      )
                                    }
                                    className="w-16 px-1 py-0.5 border border-gray-300 rounded text-right"
                                  />
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setGeoSegments((prev) =>
                                        recalculateShares(
                                          prev.filter((_, idx) => idx !== i)
                                        )
                                      )
                                    }
                                    className="text-red-500 cursor-pointer"
                                  >
                                    <Trash2 className="w-3 h-3" />
                                  </button>
                                </>
                              ) : (
                                <span className="font-bold text-gray-900">
                                  {geo.share_pct}%
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                    <span className="font-bold text-gray-800 flex items-center gap-1.5 text-[11px]">
                      <Users className="w-3.5 h-3.5 text-orange-500" />
                      Principales Clientes, Contratos y Canales
                    </span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={clientsNote}
                        onChange={(e) => setClientsNote(e.target.value)}
                        className="w-full mt-1 px-2 py-1 border border-gray-300 rounded bg-white text-gray-800"
                      />
                    ) : (
                      <p className="text-gray-600 mt-1 text-[11px]">
                        {clientsNote}
                      </p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 flex flex-col justify-between space-y-3">
                  {hasBizChart ? (
                    <>
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
                          <BarChart2 className="w-4 h-4 text-orange-500" />
                          Múltiplos de Valuación (Actual vs. Mediana 5Y)
                        </h3>
                        <button
                          type="button"
                          onClick={() => setIsEditing(true)}
                          className="print:hidden text-[11px] text-orange-600 font-semibold hover:underline cursor-pointer"
                        >
                          + Cargar regiones
                        </button>
                      </div>
                      <table className="w-full text-xs text-right">
                        <thead>
                          <tr className="bg-gray-100 text-gray-700">
                            <th className="py-1.5 px-3 text-left">Múltiplo</th>
                            <th className="py-1.5 px-3">Actual (LTM)</th>
                            <th className="py-1.5 px-3">Mediana 5Y</th>
                            <th className="py-1.5 px-3">vs. Historia</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {multiplesList.slice(0, 4).map((m, idx) => (
                            <tr key={idx}>
                              <td className="py-1.5 px-3 text-left font-semibold text-gray-800">
                                {m.metric}
                              </td>
                              <td className="py-1.5 px-3 tabular-nums font-bold text-gray-900">
                                {typeof m.ltm === "number"
                                  ? `${m.ltm.toFixed(1)}${m.suffix}`
                                  : "-"}
                              </td>
                              <td className="py-1.5 px-3 tabular-nums text-gray-600">
                                {typeof m.med_5y === "number"
                                  ? `${m.med_5y.toFixed(1)}${m.suffix}`
                                  : "-"}
                              </td>
                              <td
                                className={`py-1.5 px-3 tabular-nums font-semibold ${
                                  m.vs_med_pct === null
                                    ? "text-gray-400"
                                    : m.vs_med_pct <= 0
                                    ? "text-emerald-700"
                                    : "text-amber-700"
                                }`}
                              >
                                {m.vs_med_pct !== null
                                  ? `${m.vs_med_pct > 0 ? "+" : ""}${m.vs_med_pct}%`
                                  : "-"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
                          <ShieldCheck className="w-4 h-4 text-orange-500" />
                          Rentabilidad sobre Capital y Solidez
                        </h3>
                        <button
                          type="button"
                          onClick={() => setIsEditing(true)}
                          className="print:hidden text-[11px] text-orange-600 font-semibold hover:underline cursor-pointer"
                        >
                          + Cargar regiones
                        </button>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/80">
                          <span className="text-[10px] font-bold uppercase text-gray-400">
                            ROIC / ROE
                          </span>
                          <p className="text-sm font-extrabold text-gray-900 mt-0.5">
                            {kpis.roic_pct !== null ? `${kpis.roic_pct}%` : "N/D"} /{" "}
                            {kpis.roe_pct !== null ? `${kpis.roe_pct}%` : "N/D"}
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/80">
                          <span className="text-[10px] font-bold uppercase text-gray-400">
                            Altman Z-Score
                          </span>
                          <p className="text-sm font-extrabold text-gray-900 mt-0.5">
                            {kpis.altman_z !== null
                              ? `${Number(kpis.altman_z).toFixed(2)} (${kpis.altman_zone || "Zona"})`
                              : "N/A Sector"}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="p-3 rounded-lg bg-gray-50 border border-gray-200/80">
                    <span className="font-bold text-gray-800 flex items-center gap-1.5 text-[11px]">
                      <Users className="w-3.5 h-3.5 text-orange-500" />
                      Principales Clientes, Contratos y Canales
                    </span>
                    <p className="text-gray-600 mt-1 text-[11px]">
                      {clientsNote}
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* 5. EVOLUCIÓN FINANCIERA 5Y + PUENTE DE VALUACIÓN FOOTBALL FIELD Y RIESGOS */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              {/* Gráfico 5Y con Leyenda explícita */}
              <div className="lg:col-span-6 bg-white border border-gray-200 rounded-xl shadow-sm p-5">
                <h3 className="text-sm font-bold text-gray-900 mb-3">
                  Trayectoria Financiera 5Y (US$ Millones y Margen Operativo %)
                </h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={trend}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                      <YAxis
                        yAxisId="left"
                        tick={{ fontSize: 10 }}
                        tickFormatter={(v) =>
                          Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(0)}k` : v
                        }
                      />
                      <YAxis
                        yAxisId="right"
                        orientation="right"
                        tick={{ fontSize: 10 }}
                        unit="%"
                      />
                      <Tooltip
                        formatter={(val, name) =>
                          String(name).includes("%")
                            ? `${Number(val).toFixed(1)}%`
                            : `US$ ${Number(val).toLocaleString("es-AR")} MM`
                        }
                      />
                      <Legend wrapperStyle={{ fontSize: "11px" }} />
                      <Bar
                        yAxisId="left"
                        dataKey="revenue_mm"
                        name="Ingresos (US$ MM)"
                        fill="#1e293b"
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar
                        yAxisId="left"
                        dataKey="fcf_mm"
                        name="FCF (US$ MM)"
                        fill="#f97316"
                        radius={[4, 4, 0, 0]}
                      />
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="operating_margin_pct"
                        name="Margen Op. (%)"
                        stroke="#10b981"
                        strokeWidth={2.5}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Puente de Valuación Football Field + Riesgos Clave */}
              <div className="lg:col-span-6 bg-white border border-gray-200 rounded-xl shadow-sm p-5 flex flex-col justify-between space-y-4">
                <div>
                  <h3 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
                    <Target className="w-4 h-4 text-orange-500" />
                    Valuación Intrínseca ({valBridge.model_used})
                  </h3>

                  <div className="mt-4 space-y-3.5 text-[11px]">
                    {/* Banda de rango intrínseco con marcador de cotización actual */}
                    <div>
                      <div className="flex justify-between font-semibold mb-1.5">
                        <span className="text-emerald-800">
                          Rango Intrínseco Estimado (Bajo – Medio – Alto)
                        </span>
                        <span className="text-emerald-700 font-bold">
                          {formatMoney(valBridge.intrinsic_low)} –{" "}
                          {formatMoney(valBridge.intrinsic_mid)} –{" "}
                          {formatMoney(valBridge.intrinsic_high)}
                        </span>
                      </div>

                      <div className="relative h-5 bg-gray-100 rounded-full overflow-hidden border border-gray-200/80">
                        {/* Banda desde Bajo hasta Alto */}
                        <div
                          className="absolute top-0 bottom-0 bg-emerald-500/80 rounded-full"
                          style={{
                            left: `${lowPct}%`,
                            width: `${Math.max(highPct - lowPct, 3)}%`,
                          }}
                        />
                        {/* Punto medio intrínseco */}
                        <div
                          title={`Punto medio: ${formatMoney(valBridge.intrinsic_mid)}`}
                          className="absolute top-0 bottom-0 w-1 bg-emerald-950"
                          style={{ left: `${midPct}%` }}
                        />
                        {/* Marcador vertical del Precio Actual */}
                        <div
                          title={`Cotización Actual: ${formatMoney(valBridge.current_price)}`}
                          className="absolute top-0 bottom-0 w-1 bg-slate-900 z-10"
                          style={{ left: `${curPct}%` }}
                        />
                      </div>

                      <div className="flex justify-between text-[10px] text-gray-500 mt-1">
                        <span>
                          Cotización Actual:{" "}
                          <strong className="text-slate-900">
                            {formatMoney(valBridge.current_price)}
                          </strong>
                        </span>
                        <span>
                          Potencial Medio:{" "}
                          <strong
                            className={
                              (valBridge.upside_mid_pct || 0) >= 0
                                ? "text-emerald-700"
                                : "text-rose-700"
                            }
                          >
                            {(valBridge.upside_mid_pct || 0) >= 0 ? "+" : ""}
                            {(valBridge.upside_mid_pct || 0).toFixed(1)}%
                          </strong>
                        </span>
                      </div>
                    </div>

                    {valBridge.consensus_target && (
                      <div>
                        <div className="flex justify-between font-semibold mb-1">
                          <span className="text-orange-800">
                            Precio Objetivo Consenso Wall Street
                          </span>
                          <span className="text-orange-600 font-bold">
                            {formatMoney(valBridge.consensus_target)}
                          </span>
                        </div>
                        <div className="relative h-3 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-orange-500 rounded-full"
                            style={{ width: `${wsPct}%` }}
                          />
                          <div
                            className="absolute top-0 bottom-0 w-1 bg-slate-900"
                            style={{ left: `${curPct}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Riesgos y Mitigantes */}
                <div className="p-3.5 rounded-xl bg-amber-50/70 border border-amber-200 space-y-1.5">
                  <p className="font-bold text-amber-950 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                    Riesgos Clave a Monitorear
                  </p>
                  <ul className="list-disc pl-4 space-y-1 text-[11px] text-amber-900">
                    {risks.map((rk, i) => (
                      <li key={i}>
                        {isEditing ? (
                          <input
                            type="text"
                            value={rk}
                            onChange={(e) =>
                              setRisks((prev) =>
                                prev.map((item, idx) =>
                                  idx === i ? e.target.value : item
                                )
                              )
                            }
                            className="w-full px-1.5 py-0.5 border border-amber-300 rounded bg-white"
                          />
                        ) : (
                          rk
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            {/* PIE DE PRESENTACIÓN PROFESIONAL */}
            <div className="bg-white border border-gray-200 rounded-xl px-5 py-3 flex flex-wrap items-center justify-between gap-2 text-[11px] text-gray-500">
              <div className="flex items-center gap-2 flex-1 min-w-64">
                <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                {isEditing ? (
                  <input
                    type="text"
                    value={advisorNote}
                    onChange={(e) => setAdvisorNote(e.target.value)}
                    className="w-full px-2 py-0.5 border border-gray-300 rounded text-gray-800"
                  />
                ) : (
                  <span>{advisorNote}</span>
                )}
              </div>
              <span className="font-semibold text-gray-700">
                Vektor · Equity Research & Portfolio Advisory
              </span>
            </div>
          </div>
        )
      )}
    </div>
  );
}