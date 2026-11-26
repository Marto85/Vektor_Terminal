import { useEffect, useMemo, useRef, useState } from "react";
import * as LightweightCharts from "lightweight-charts";
import {
  Activity,
  BarChart2,
  Building2,
  CandlestickChart,
  Check,
  Copy,
  Edit3,
  ExternalLink,
  Landmark,
  LineChart,
  Loader2,
  Newspaper,
  Plus,
  RefreshCw,
  RotateCcw,
  Trash2,
  Users,
  X,
} from "lucide-react";
import apiClient from "../api/client";
import { useTheme } from "../context/themeStore";

const RANGES = [
  { id: "3m", label: "3M" },
  { id: "6m", label: "6M" },
  { id: "1y", label: "1A" },
  { id: "3y", label: "3A" },
  { id: "5y", label: "5A" },
  { id: "max", label: "MAX" },
];

function fmtArNum(val, decimals = 2) {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "-";
  return new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Number(val));
}

function fmtRelativeDate(isoStr) {
  if (!isoStr) return "";
  const dt = new Date(isoStr);
  if (Number.isNaN(dt.getTime())) return "";
  const diffMin = Math.max(0, Math.round((Date.now() - dt.getTime()) / 60000));
  if (diffMin < 60) return `Hace ${diffMin} min`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return `Hace ${diffH} h`;
  return dt.toLocaleDateString("es-AR", { day: "2-digit", month: "short" });
}

export default function ArgentinaTab({ isSuperadmin = false }) {
  const { isDark } = useTheme();
  const [overview, setOverview] = useState(null);
  const [loadingOverview, setLoadingOverview] = useState(true);
  const [overviewError, setOverviewError] = useState("");

  const [selectedSeriesId, setSelectedSeriesId] = useState("riesgo_pais");
  const [compareSeriesId, setCompareSeriesId] = useState("");
  const [chartType, setChartType] = useState("line");
  const [rangeKey, setRangeKey] = useState("1y");
  const [showTrendSma, setShowTrendSma] = useState(true);
  const [seriesData, setSeriesData] = useState(null);
  const [compareSeriesData, setCompareSeriesData] = useState(null);
  const [loadingSeries, setLoadingSeries] = useState(false);

  const [bondLawFilter, setBondLawFilter] = useState("ALL");
  const [newsTopicFilter, setNewsTopicFilter] = useState("ALL");
  const [newsSourceFilter, setNewsSourceFilter] = useState("ALL");
  const [copiedLink, setCopiedLink] = useState("");

  // Modal Superadmin para editar Termómetro Social / Político
  const [socialModalOpen, setSocialModalOpen] = useState(false);
  const [socialCatalog, setSocialCatalog] = useState([]);
  const [editSocialId, setEditSocialId] = useState("indec_pobreza");
  const [editSource, setEditSource] = useState("");
  const [editPoints, setEditPoints] = useState([]);
  const [newPointDate, setNewPointDate] = useState("");
  const [newPointValue, setNewPointValue] = useState("");
  const [newPointNote, setNewPointNote] = useState("");
  const [savingSocial, setSavingSocial] = useState(false);
  const [socialMsg, setSocialMsg] = useState("");

  const chartContainerRef = useRef(null);

  const fetchOverview = async () => {
    setLoadingOverview(true);
    setOverviewError("");
    try {
      const res = await apiClient.get("/argentina/overview");
      setOverview(res.data);
    } catch (err) {
      setOverviewError(
        err.response?.data?.detail || "No se pudo cargar el panel de Argentina."
      );
    } finally {
      setLoadingOverview(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    const init = async () => {
      try {
        const res = await apiClient.get("/argentina/overview");
        if (!cancelled) setOverview(res.data);
      } catch (err) {
        if (!cancelled) {
          setOverviewError(
            err.response?.data?.detail || "No se pudo cargar el panel de Argentina."
          );
        }
      } finally {
        if (!cancelled) setLoadingOverview(false);
      }
    };
    init();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadSeries = async () => {
      setLoadingSeries(true);
      try {
        const reqs = [
          apiClient.get(
            `/argentina/series/${encodeURIComponent(selectedSeriesId)}?range=${rangeKey}`
          ),
        ];
        if (compareSeriesId && compareSeriesId !== selectedSeriesId) {
          reqs.push(
            apiClient.get(
              `/argentina/series/${encodeURIComponent(compareSeriesId)}?range=${rangeKey}`
            )
          );
        }
        const [resMain, resCompare] = await Promise.all(reqs);
        if (!cancelled) {
          setSeriesData(resMain.data);
          setCompareSeriesData(resCompare ? resCompare.data : null);
          if (chartType === "candle" && !resMain.data?.supports_candlestick) {
            setChartType("line");
          }
        }
      } catch {
        if (!cancelled) {
          setSeriesData(null);
          setCompareSeriesData(null);
        }
      } finally {
        if (!cancelled) setLoadingSeries(false);
      }
    };
    loadSeries();
    return () => {
      cancelled = true;
    };
  }, [selectedSeriesId, compareSeriesId, rangeKey, chartType]);

  useEffect(() => {
    const container = chartContainerRef.current;
    const points = seriesData?.points || [];
    if (!container || points.length === 0) return;

    const hasCompare =
      chartType === "line" &&
      compareSeriesId &&
      compareSeriesId !== selectedSeriesId &&
      (compareSeriesData?.points?.length || 0) > 0;

    const chart = LightweightCharts.createChart(container, {
      width: container.clientWidth || 720,
      height: 300,
      layout: {
        background: { color: isDark ? "#202024" : "#ffffff" },
        textColor: isDark ? "#a1a1aa" : "#4b5563",
        fontFamily: "'Inter Variable', Inter, sans-serif",
      },
      grid: {
        vertLines: { color: isDark ? "#27272a" : "#f3f4f6" },
        horzLines: { color: isDark ? "#27272a" : "#f3f4f6" },
      },
      rightPriceScale: {
        borderColor: isDark ? "#3f3f46" : "#e5e7eb",
      },
      leftPriceScale: {
        visible: hasCompare,
        borderColor: isDark ? "#3f3f46" : "#e5e7eb",
      },
      timeScale: {
        borderColor: isDark ? "#3f3f46" : "#e5e7eb",
      },
    });

    if (chartType === "candle" && seriesData?.supports_candlestick) {
      const candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
        upColor: "#16a34a",
        downColor: "#dc2626",
        borderVisible: false,
        wickUpColor: "#16a34a",
        wickDownColor: "#dc2626",
      });
      candleSeries.setData(
        points
          .filter((p) => p.open != null && p.high != null && p.low != null && p.close != null)
          .map((p) => ({
            time: p.date,
            open: p.open,
            high: p.high,
            low: p.low,
            close: p.close,
          }))
      );
    } else if (chartType === "bar") {
      const barSeries = chart.addSeries(LightweightCharts.HistogramSeries, {
        color: "#ea580c",
      });
      barSeries.setData(
        points.map((p, idx) => {
          const prev = idx > 0 ? points[idx - 1].value : p.value;
          return {
            time: p.date,
            value: p.value,
            color: p.value >= prev ? "#16a34a" : "#dc2626",
          };
        })
      );
    } else {
      const lineSeries = chart.addSeries(LightweightCharts.LineSeries, {
        color: "#ea580c",
        lineWidth: 2,
        priceScaleId: "right",
      });
      lineSeries.setData(points.map((p) => ({ time: p.date, value: p.value })));

      if (hasCompare) {
        const cmpSeries = chart.addSeries(LightweightCharts.LineSeries, {
          color: "#2563eb",
          lineWidth: 2,
          priceScaleId: "left",
        });
        cmpSeries.setData(
          compareSeriesData.points.map((p) => ({ time: p.date, value: p.value }))
        );
      } else if (showTrendSma && points.length >= 20) {
        const smaData = [];
        let sum = 0;
        for (let i = 0; i < points.length; i += 1) {
          sum += Number(points[i].value || 0);
          if (i >= 20) sum -= Number(points[i - 20].value || 0);
          if (i >= 19) {
            smaData.push({ time: points[i].date, value: Number((sum / 20).toFixed(2)) });
          }
        }
        const smaSeries = chart.addSeries(LightweightCharts.LineSeries, {
          color: "#2563eb",
          lineWidth: 1.5,
          lineStyle: 2,
        });
        smaSeries.setData(smaData);
      }
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (container.clientWidth > 0) {
        chart.applyOptions({ width: container.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [seriesData, compareSeriesData, compareSeriesId, selectedSeriesId, chartType, showTrendSma, isDark]);

  const cardsList = useMemo(() => {
    const c = overview?.cards;
    if (!c) return [];
    return [c.mayorista, c.oficial, c.mep, c.ccl, c.riesgo_pais, c.merval_usd].filter(Boolean);
  }, [overview]);

  const filteredBonds = useMemo(() => {
    const list = overview?.sovereign_bonds || [];
    if (bondLawFilter === "ALL") return list;
    return list.filter((b) => b.law === bondLawFilter);
  }, [overview, bondLawFilter]);

  const newsSources = useMemo(() => {
    const set = new Set((overview?.news || []).map((n) => n.source).filter(Boolean));
    return ["ALL", ...Array.from(set)];
  }, [overview]);

  const filteredNews = useMemo(() => {
    return (overview?.news || []).filter((n) => {
      if (newsTopicFilter !== "ALL" && n.topic !== newsTopicFilter) return false;
      if (newsSourceFilter !== "ALL" && n.source !== newsSourceFilter) return false;
      return true;
    });
  }, [overview, newsTopicFilter, newsSourceFilter]);

  const handleCopyLink = async (link) => {
    try {
      await navigator.clipboard.writeText(link);
      setCopiedLink(link);
      setTimeout(() => setCopiedLink(""), 2000);
    } catch {
      setCopiedLink("");
    }
  };

  const openSocialModal = async (targetSeriesId) => {
    setSocialMsg("");
    setSocialModalOpen(true);
    try {
      const res = await apiClient.get("/argentina/social-overrides");
      const items = res.data?.items || [];
      setSocialCatalog(items);
      const chosenId = targetSeriesId || items[0]?.series_id || "indec_pobreza";
      setEditSocialId(chosenId);
      const found = items.find((i) => i.series_id === chosenId) || items[0];
      if (found) {
        setEditSource(found.source || "");
        setEditPoints(found.points || []);
      }
    } catch {
      setSocialMsg("No se pudo cargar la configuración social/política.");
    }
  };

  const handleSelectEditSocial = (sid) => {
    setEditSocialId(sid);
    setSocialMsg("");
    const found = socialCatalog.find((i) => i.series_id === sid);
    if (found) {
      setEditSource(found.source || "");
      setEditPoints(found.points || []);
    }
  };

  const handleAddSocialPoint = () => {
    const dt = newPointDate.trim();
    const val = Number(newPointValue);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dt) || Number.isNaN(val)) {
      setSocialMsg("Ingresá una fecha válida (YYYY-MM-DD) y un valor numérico.");
      return;
    }
    const filtered = editPoints.filter((p) => p.date !== dt);
    const next = [...filtered, { date: dt, value: val, note: newPointNote.trim() || undefined }].sort(
      (a, b) => a.date.localeCompare(b.date)
    );
    setEditPoints(next);
    setNewPointDate("");
    setNewPointValue("");
    setNewPointNote("");
    setSocialMsg("");
  };

  const handleRemoveSocialPoint = (dt) => {
    if (editPoints.length <= 1) {
      setSocialMsg("Debe quedar al menos un punto histórico.");
      return;
    }
    setEditPoints((prev) => prev.filter((p) => p.date !== dt));
  };

  const handleSaveSocialOverride = async () => {
    setSavingSocial(true);
    setSocialMsg("");
    try {
      await apiClient.put(`/argentina/social-overrides/${encodeURIComponent(editSocialId)}`, {
        source: editSource,
        points: editPoints,
      });
      await fetchOverview();
      if (selectedSeriesId === editSocialId) {
        const res = await apiClient.get(
          `/argentina/series/${encodeURIComponent(editSocialId)}?range=${rangeKey}`
        );
        setSeriesData(res.data);
      }
      setSocialMsg("Guardado correctamente.");
    } catch (err) {
      setSocialMsg(err.response?.data?.detail || "Error al guardar el indicador.");
    } finally {
      setSavingSocial(false);
    }
  };

  const handleResetSocialOverride = async () => {
    setSavingSocial(true);
    setSocialMsg("");
    try {
      const res = await apiClient.delete(
        `/argentina/social-overrides/${encodeURIComponent(editSocialId)}`
      );
      setEditSource(res.data?.source || "");
      setEditPoints(res.data?.points || []);
      await fetchOverview();
      setSocialMsg("Serie restaurada a valores base.");
    } catch (err) {
      setSocialMsg(err.response?.data?.detail || "Error al restaurar la serie.");
    } finally {
      setSavingSocial(false);
    }
  };

  const compareOptions = useMemo(() => {
    const opts = [
      ...(cardsList || []).map((c) => ({ id: c.series_id, label: c.label, group: "Mercado y FX" })),
      ...((overview?.macro_indicators || []).map((m) => ({
        id: m.series_id,
        label: m.label,
        group: "Macro BCRA / INDEC",
      }))),
      ...((overview?.social_indicators || []).map((s) => ({
        id: s.series_id,
        label: s.label,
        group: "Social y Político",
      }))),
    ];
    return opts.filter((o) => o.id !== selectedSeriesId);
  }, [cardsList, overview, selectedSeriesId]);

  return (
    <div className="space-y-6">
      {/* HEADER */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg sm:text-xl font-bold text-gray-900 flex items-center gap-2">
            <Landmark className="w-5 h-5 text-orange-600" />
            Argentina · Mercado, Deuda y Coyuntura
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Tipos de cambio, brechas, Riesgo País, bonos soberanos en USD y prensa económica/política en tiempo real.
          </p>
        </div>
        <button
          type="button"
          onClick={fetchOverview}
          disabled={loadingOverview}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-xs font-semibold text-gray-700 hover:bg-gray-50 cursor-pointer disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loadingOverview ? "animate-spin" : ""}`} />
          Actualizar
        </button>
      </div>

      {overviewError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-xs text-red-700 font-medium">
          {overviewError}
        </div>
      )}

      {/* BLOQUE A: TABLERO CAMBIARIO, BRECHAS, RIESGO PAÍS Y MERVAL CCL */}
      <section>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
          {loadingOverview && cardsList.length === 0
            ? Array.from({ length: 6 }).map((_, idx) => (
                <div
                  key={idx}
                  className="bg-white border border-gray-200 rounded-xl p-3.5 animate-pulse h-24"
                />
              ))
            : cardsList.map((card) => {
                const isSelected = selectedSeriesId === card.series_id;
                const valFormatted =
                  card.value != null
                    ? card.unit === "ARS"
                      ? `$ ${fmtArNum(card.value, 2)}`
                      : card.unit === "pb"
                        ? `${fmtArNum(card.value, 0)} pb`
                        : `US$ ${fmtArNum(card.value, 2)}`
                    : "-";
                return (
                  <button
                    key={card.series_id}
                    type="button"
                    onClick={() => setSelectedSeriesId(card.series_id)}
                    className={`text-left rounded-xl border p-3.5 transition-all cursor-pointer ${
                      isSelected
                        ? "bg-orange-50/70 border-orange-400 ring-1 ring-orange-400"
                        : "bg-white border-gray-200 hover:border-orange-300"
                    }`}
                  >
                    <p className="text-[11px] font-bold text-gray-500 leading-snug">
                      {card.label}
                    </p>
                    <p className="text-lg font-extrabold text-gray-900 tabular-nums mt-1">
                      {valFormatted}
                    </p>
                    <p className="text-[11px] text-gray-600 mt-1 leading-snug">
                      {card.subtitle}
                    </p>
                  </button>
                );
              })}
        </div>
      </section>

      {/* BLOQUE B: VISOR DE TRAYECTORIA INTERACTIVA */}
      <section className="bg-white border border-gray-200 rounded-xl p-4 sm:p-5 shadow-2xs">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h3 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-orange-600" />
              Visor de Trayectoria: {seriesData?.label || selectedSeriesId}
            </h3>
            <p className="text-[11px] text-gray-500">
              Hacé clic en cualquier tarjeta superior o bono soberano para analizar su evolución histórica.
              {seriesData?.source ? ` · Fuente: ${seriesData.source}` : ""}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-0.5">
              <button
                type="button"
                onClick={() => setChartType("line")}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold cursor-pointer ${
                  chartType === "line" ? "bg-white text-orange-700 shadow-2xs" : "text-gray-600"
                }`}
              >
                <LineChart className="w-3.5 h-3.5" /> Línea
              </button>
              <button
                type="button"
                onClick={() => setChartType("bar")}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold cursor-pointer ${
                  chartType === "bar" ? "bg-white text-orange-700 shadow-2xs" : "text-gray-600"
                }`}
              >
                <BarChart2 className="w-3.5 h-3.5" /> Barras
              </button>
              <button
                type="button"
                disabled={!seriesData?.supports_candlestick}
                title={
                  seriesData?.supports_candlestick
                    ? "Velas japonesas (OHLC)"
                    : "Requiere datos OHLC diarios (disponible en Merval USD y Bonos)"
                }
                onClick={() => setChartType("candle")}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold ${
                  !seriesData?.supports_candlestick
                    ? "text-gray-400 cursor-not-allowed opacity-60"
                    : chartType === "candle"
                      ? "bg-white text-orange-700 shadow-2xs cursor-pointer"
                      : "text-gray-600 cursor-pointer"
                }`}
              >
                <CandlestickChart className="w-3.5 h-3.5" /> Velas
              </button>
            </div>

            {chartType === "line" && (
              <>
                <select
                  aria-label="Comparar trayectoria con otra serie"
                  value={compareSeriesId}
                  onChange={(e) => setCompareSeriesId(e.target.value)}
                  className="px-2.5 py-1 rounded-lg border border-gray-300 bg-white text-xs text-gray-700 max-w-[190px]"
                >
                  <option value="">Comparar con...</option>
                  {compareOptions.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </select>

                {!compareSeriesId && (
                  <label className="inline-flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer px-2">
                    <input
                      type="checkbox"
                      checked={showTrendSma}
                      onChange={(e) => setShowTrendSma(e.target.checked)}
                      className="accent-orange-600"
                    />
                    Tendencia (SMA 20)
                  </label>
                )}
              </>
            )}

            <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-0.5">
              {RANGES.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setRangeKey(r.id)}
                  className={`px-2 py-1 rounded text-xs font-semibold cursor-pointer ${
                    rangeKey === r.id ? "bg-orange-500 text-white" : "text-gray-600 hover:text-gray-900"
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="relative min-h-[300px]">
          {loadingSeries && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/70 z-10">
              <Loader2 className="w-6 h-6 animate-spin text-orange-600" />
            </div>
          )}
          {!loadingSeries && (!seriesData?.points || seriesData.points.length === 0) ? (
            <div className="h-[300px] flex items-center justify-center text-xs text-gray-500">
              Sin datos históricos disponibles para esta serie en el rango seleccionado.
            </div>
          ) : (
            <div ref={chartContainerRef} className="w-full h-[300px]" />
          )}
        </div>

        {chartType === "line" && compareSeriesId && compareSeriesData?.label && (
          <div className="mt-2 pt-2 border-t border-gray-100 flex flex-wrap items-center gap-4 text-[11px] text-gray-600">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-orange-600 inline-block" />
              Eje Derecho: <strong>{seriesData?.label}</strong> ({seriesData?.unit || "-"})
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-blue-600 inline-block" />
              Eje Izquierdo: <strong>{compareSeriesData.label}</strong> ({compareSeriesData.unit || "-"})
            </span>
          </div>
        )}
      </section>

      {/* BLOQUE B2: MACROECONOMÍA OFICIAL (BCRA · INDEC · MECON) */}
      {(overview?.macro_indicators?.length || 0) > 0 && (
        <section className="space-y-3">
          <div>
            <h3 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
              <Building2 className="w-4 h-4 text-orange-600" />
              Macroeconomía Oficial (BCRA · INDEC · MECON)
            </h3>
            <p className="text-[11px] text-gray-500">
              Hacé clic en cualquier indicador para analizar su trayectoria histórica en el visor superior.
            </p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {overview.macro_indicators.map((m) => {
              const isSelected = selectedSeriesId === m.series_id;
              const decimals = m.unit === "%" ? 2 : m.unit === "Índice" ? 1 : 0;
              return (
                <button
                  key={m.series_id}
                  type="button"
                  onClick={() => setSelectedSeriesId(m.series_id)}
                  className={`text-left rounded-xl border p-3.5 transition-all cursor-pointer ${
                    isSelected
                      ? "bg-orange-50/70 border-orange-400 ring-1 ring-orange-400"
                      : "bg-white border-gray-200 hover:border-orange-300"
                  }`}
                >
                  <div className="flex items-center justify-between gap-1">
                    <p className="text-[11px] font-bold text-gray-600">{m.label}</p>
                    {m.date && (
                      <span className="text-[10px] text-gray-500 tabular-nums">{m.date}</span>
                    )}
                  </div>
                  <p className="text-base font-extrabold text-gray-900 tabular-nums mt-1">
                    {m.value != null ? `${fmtArNum(m.value, decimals)} ${m.unit}` : "-"}
                  </p>
                  <p className="text-[11px] text-gray-500 mt-1 truncate">{m.source}</p>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* BLOQUE B3: TERMÓMETRO SOCIAL Y POLÍTICO (INDEC · UCA · DI TELLA) */}
      {(overview?.social_indicators?.length || 0) > 0 && (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
                <Users className="w-4 h-4 text-orange-600" />
                Termómetro Social y Político (INDEC · UCA · Di Tella)
              </h3>
              <p className="text-[11px] text-gray-500">
                Pobreza, indigencia y confianza en el gobierno. Hacé clic en cualquier tarjeta para ver su evolución en barras o línea.
              </p>
            </div>
            {isSuperadmin && (
              <button
                type="button"
                onClick={() => openSocialModal()}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-xs font-semibold text-gray-700 hover:bg-gray-50 cursor-pointer"
              >
                <Edit3 className="w-3.5 h-3.5 text-orange-600" />
                Editar / Cargar dato
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {overview.social_indicators.map((s) => {
              const isSelected = selectedSeriesId === s.series_id;
              const deltaPos = (s.delta || 0) >= 0;
              return (
                <button
                  key={s.series_id}
                  type="button"
                  onClick={() => setSelectedSeriesId(s.series_id)}
                  className={`text-left rounded-xl border p-3.5 transition-all cursor-pointer ${
                    isSelected
                      ? "bg-orange-50/70 border-orange-400 ring-1 ring-orange-400"
                      : "bg-white border-gray-200 hover:border-orange-300"
                  }`}
                >
                  <div className="flex items-center justify-between gap-1">
                    <p className="text-[11px] font-bold text-gray-600">{s.label}</p>
                    {s.is_override && (
                      <span className="px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 text-[10px] font-semibold">
                        Actualizado
                      </span>
                    )}
                  </div>
                  <div className="flex items-baseline justify-between gap-2 mt-1">
                    <p className="text-lg font-extrabold text-gray-900 tabular-nums">
                      {s.value != null ? `${fmtArNum(s.value, s.unit === "%" ? 1 : 2)} ${s.unit}` : "-"}
                    </p>
                    {s.delta != null && (
                      <span
                        className={`text-[11px] font-semibold tabular-nums ${
                          s.series_id === "utdt_icg"
                            ? deltaPos
                              ? "text-emerald-700"
                              : "text-[#d93025]"
                            : deltaPos
                              ? "text-[#d93025]"
                              : "text-emerald-700"
                        }`}
                      >
                        {deltaPos ? "+" : ""}
                        {fmtArNum(s.delta, s.unit === "%" ? 1 : 2)}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-gray-500 mt-1 truncate">
                    {s.note || s.date || s.subtitle} · {s.source}
                  </p>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* BLOQUE C: BONOS SOBERANOS NACIONALES EN USD */}
      <section className="bg-white border border-gray-200 rounded-xl p-4 sm:p-5 shadow-2xs">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div>
            <h3 className="text-sm font-bold text-gray-900">
              Bonos Soberanos Nacionales en Dólares (USD cada 100 VN)
            </h3>
            <p className="text-[11px] text-gray-500">
              Legislación Nueva York (GD) y Ley Argentina (AL). Hacé clic en &quot;Trayectoria&quot; para ver velas o línea histórica.
            </p>
          </div>
          <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-0.5">
            {[
              { id: "ALL", label: "Todos" },
              { id: "Ley NY", label: "Ley NY" },
              { id: "Ley Local", label: "Ley Local" },
            ].map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setBondLawFilter(f.id)}
                className={`px-2.5 py-1 rounded text-xs font-semibold cursor-pointer ${
                  bondLawFilter === f.id ? "bg-white text-orange-700 shadow-2xs" : "text-gray-600"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200 text-gray-500 text-left">
                <th className="py-2 pr-3 font-semibold">Ticker</th>
                <th className="py-2 pr-3 font-semibold">Instrumento</th>
                <th className="py-2 pr-3 font-semibold">Legislación</th>
                <th className="py-2 pr-3 font-semibold text-right">Cupón</th>
                <th className="py-2 pr-3 font-semibold">Vencimiento</th>
                <th className="py-2 pr-3 font-semibold text-right">Precio USD</th>
                <th className="py-2 pr-3 font-semibold text-right">Var. Día</th>
                <th className="py-2 font-semibold text-right">Gráfico</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredBonds.map((b) => {
                const pos = (b.change_pct || 0) >= 0;
                return (
                  <tr key={b.ticker} className="hover:bg-gray-50/70">
                    <td className="py-2 pr-3 font-bold text-gray-900">{b.ticker}</td>
                    <td className="py-2 pr-3 text-gray-700">{b.name}</td>
                    <td className="py-2 pr-3">
                      <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-[11px] font-semibold">
                        {b.law}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums text-gray-700">
                      {fmtArNum(b.coupon_pct, 2)}%
                    </td>
                    <td className="py-2 pr-3 tabular-nums text-gray-600">{b.maturity}</td>
                    <td className="py-2 pr-3 text-right font-bold tabular-nums text-gray-900">
                      {b.price_usd != null ? `US$ ${fmtArNum(b.price_usd, 2)}` : "-"}
                    </td>
                    <td
                      className={`py-2 pr-3 text-right font-semibold tabular-nums ${
                        b.change_pct == null
                          ? "text-gray-500"
                          : pos
                            ? "text-emerald-700"
                            : "text-[#d93025]"
                      }`}
                    >
                      {b.change_pct != null ? `${pos ? "+" : ""}${fmtArNum(b.change_pct, 2)}%` : "-"}
                    </td>
                    <td className="py-2 text-right">
                      <button
                        type="button"
                        onClick={() => setSelectedSeriesId(b.series_id)}
                        className="px-2 py-1 rounded border border-gray-300 bg-white text-[11px] font-semibold text-orange-700 hover:bg-orange-50 cursor-pointer"
                      >
                        Trayectoria
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* BLOQUE D: GRILLA DE NOTICIAS DE ECONOMÍA Y POLÍTICA */}
      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
              <Newspaper className="w-4 h-4 text-orange-600" />
              Noticias del Día · Economía y Política (Pluralidad Editorial)
            </h3>
            <p className="text-[11px] text-gray-500">
              Para evitar paywalls podés usar &quot;Copiar link&quot; y abrirlo en ventana privada (Ctrl+Shift+N).
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5">
              {[
                { id: "ALL", label: "Todas" },
                { id: "Economía", label: "Economía" },
                { id: "Política", label: "Política" },
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setNewsTopicFilter(t.id)}
                  className={`px-2.5 py-1 rounded text-xs font-semibold cursor-pointer ${
                    newsTopicFilter === t.id ? "bg-orange-500 text-white" : "text-gray-600"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <select
              aria-label="Filtrar noticias por medio"
              value={newsSourceFilter}
              onChange={(e) => setNewsSourceFilter(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg border border-gray-300 bg-white text-xs text-gray-700"
            >
              {newsSources.map((src) => (
                <option key={src} value={src}>
                  {src === "ALL" ? "Todos los medios" : src}
                </option>
              ))}
            </select>
          </div>
        </div>

        {filteredNews.length === 0 ? (
          <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-xs text-gray-500">
            No se encontraron noticias para los filtros seleccionados.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredNews.map((item, idx) => (
              <article
                key={`${item.link}-${idx}`}
                className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-2xs flex flex-col justify-between hover:border-orange-300 transition-colors"
              >
                <div>
                  {item.image_url ? (
                    <img
                      src={item.image_url}
                      alt={item.title}
                      loading="lazy"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                      }}
                      className="w-full h-40 object-cover bg-gray-100"
                    />
                  ) : (
                    <div className="w-full h-24 bg-gray-50 border-b border-gray-100 flex items-center justify-center text-gray-400 text-xs">
                      {item.source}
                    </div>
                  )}

                  <div className="p-4 space-y-2">
                    <div className="flex items-center justify-between gap-2 text-[11px]">
                      <div className="flex items-center gap-1.5">
                        <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-800 font-bold">
                          {item.source}
                        </span>
                        <span className="px-2 py-0.5 rounded bg-orange-50 text-orange-700 font-semibold">
                          {item.topic}
                        </span>
                      </div>
                      <span className="text-gray-500">{fmtRelativeDate(item.published_at)}</span>
                    </div>

                    <a
                      href={item.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block font-bold text-sm text-gray-900 hover:text-orange-700 leading-snug"
                    >
                      {item.title}
                    </a>

                    {item.subtitle && (
                      <p className="text-xs text-gray-600 leading-relaxed line-clamp-3">
                        {item.subtitle}
                      </p>
                    )}
                  </div>
                </div>

                <div className="px-4 py-2.5 border-t border-gray-100 flex items-center justify-between gap-2">
                  <a
                    href={item.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-semibold text-orange-700 hover:underline"
                  >
                    Leer nota <ExternalLink className="w-3 h-3" />
                  </a>
                  <button
                    type="button"
                    onClick={() => handleCopyLink(item.link)}
                    className="inline-flex items-center gap-1 text-[11px] font-medium text-gray-600 hover:text-gray-900 cursor-pointer"
                    title="Copiar enlace para abrir en ventana privada"
                  >
                    {copiedLink === item.link ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-600" /> Copiado
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" /> Copiar link
                      </>
                    )}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {/* MODAL SUPERADMIN: EDITAR / CARGAR INDICADORES SOCIALES Y POLÍTICOS */}
      {socialModalOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Editar indicadores sociales y políticos"
        >
          <div className="bg-white border border-gray-200 rounded-xl shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col">
            <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold text-gray-900">
                  Gestión de Indicadores Sociales y Políticos (Superadmin)
                </h4>
                <p className="text-[11px] text-gray-500">
                  Cargá nuevas mediciones oficiales o corregí puntos históricos si cambia un informe público.
                </p>
              </div>
              <button
                type="button"
                aria-label="Cerrar modal"
                onClick={() => setSocialModalOpen(false)}
                className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 space-y-4 overflow-y-auto text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Indicador</label>
                  <select
                    value={editSocialId}
                    onChange={(e) => handleSelectEditSocial(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 bg-white text-gray-900"
                  >
                    {socialCatalog.map((item) => (
                      <option key={item.series_id} value={item.series_id}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Fuente</label>
                  <input
                    type="text"
                    value={editSource}
                    onChange={(e) => setEditSource(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 bg-white text-gray-900"
                  />
                </div>
              </div>

              <div className="border border-gray-200 rounded-lg p-3 bg-gray-50/70 space-y-2">
                <p className="font-semibold text-gray-700">Agregar o actualizar fecha</p>
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
                  <input
                    type="date"
                    value={newPointDate}
                    onChange={(e) => setNewPointDate(e.target.value)}
                    aria-label="Fecha del dato"
                    className="px-2.5 py-1.5 rounded border border-gray-300 bg-white text-gray-900"
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="Valor"
                    value={newPointValue}
                    onChange={(e) => setNewPointValue(e.target.value)}
                    className="px-2.5 py-1.5 rounded border border-gray-300 bg-white text-gray-900"
                  />
                  <input
                    type="text"
                    placeholder="Nota (ej. 2° Sem 2025)"
                    value={newPointNote}
                    onChange={(e) => setNewPointNote(e.target.value)}
                    className="px-2.5 py-1.5 rounded border border-gray-300 bg-white text-gray-900"
                  />
                  <button
                    type="button"
                    onClick={handleAddSocialPoint}
                    className="inline-flex items-center justify-center gap-1 px-3 py-1.5 rounded bg-orange-600 text-white font-semibold hover:bg-orange-700 cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" /> Agregar
                  </button>
                </div>
              </div>

              <div className="border border-gray-200 rounded-lg max-h-52 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50 border-b border-gray-200 text-gray-600">
                    <tr>
                      <th className="py-2 px-3 text-left">Fecha</th>
                      <th className="py-2 px-3 text-right">Valor</th>
                      <th className="py-2 px-3 text-left">Nota</th>
                      <th className="py-2 px-3 text-right">Acción</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {[...editPoints].reverse().map((pt) => (
                      <tr key={pt.date}>
                        <td className="py-1.5 px-3 tabular-nums">{pt.date}</td>
                        <td className="py-1.5 px-3 text-right font-bold tabular-nums">{pt.value}</td>
                        <td className="py-1.5 px-3 text-gray-600">{pt.note || "-"}</td>
                        <td className="py-1.5 px-3 text-right">
                          <button
                            type="button"
                            aria-label={`Eliminar punto ${pt.date}`}
                            onClick={() => handleRemoveSocialPoint(pt.date)}
                            className="text-red-600 hover:text-red-800 cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5 inline" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {socialMsg && (
                <p className="text-xs font-medium text-orange-700">{socialMsg}</p>
              )}
            </div>

            <div className="px-5 py-3 border-t border-gray-200 flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                onClick={handleResetSocialOverride}
                disabled={savingSocial}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-xs font-semibold text-gray-700 hover:bg-gray-50 cursor-pointer disabled:opacity-50"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Restaurar base
              </button>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSocialModalOpen(false)}
                  className="px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-xs font-semibold text-gray-700 hover:bg-gray-50 cursor-pointer"
                >
                  Cerrar
                </button>
                <button
                  type="button"
                  onClick={handleSaveSocialOverride}
                  disabled={savingSocial}
                  className="px-4 py-1.5 rounded-lg bg-orange-600 text-white text-xs font-semibold hover:bg-orange-700 cursor-pointer disabled:opacity-50"
                >
                  {savingSocial ? "Guardando..." : "Guardar cambios"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
