import { useEffect, useMemo, useRef, useState } from "react";
import apiClient from "../api/client";
import {
  Search,
  Filter,
  Scale,
  Compass,
  Award,
  TrendingUp,
  TrendingDown,
  Clock,
  ExternalLink,
  ArrowUpRight,
  Loader2,
  Newspaper,
  Sparkles,
} from "lucide-react";
import BrandLogo from "./BrandLogo";

function MiniSparkline({ points = [], isPositive = true }) {
  if (!points || points.length < 2) {
    return <div className="h-10 flex items-center text-[10px] text-gray-400">Sin serie</div>;
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const width = 120;
  const height = 38;
  const padY = 4;

  const coords = points.map((val, idx) => {
    const x = (idx / (points.length - 1)) * width;
    const y = height - padY - ((val - min) / span) * (height - padY * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const strokeColor = isPositive ? "#16a34a" : "#dc2626";
  const areaPoints = `0,${height} ${coords.join(" ")} ${width},${height}`;
  const gradId = `spark-${isPositive ? "pos" : "neg"}-${points.length}`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-16 sm:w-28 h-7 sm:h-9 shrink-0 overflow-visible">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.22" />
          <stop offset="100%" stopColor={strokeColor} stopOpacity="0.0" />
        </linearGradient>
      </defs>
      <polygon points={areaPoints} fill={`url(#${gradId})`} />
      <polyline
        fill="none"
        stroke={strokeColor}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={coords.join(" ")}
      />
    </svg>
  );
}

function fmtNum(val, decimals = 2) {
  if (val === null || val === undefined || Number.isNaN(val)) return "-";
  return new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(val);
}

export default function HomeOverview({
  onSelectTicker,
  onNavigateTab,
  onOpenScreenerPreset,
  recentTickers = [],
}) {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [heroQuery, setHeroQuery] = useState("");
  const [heroResults, setHeroResults] = useState([]);
  const [showHeroDropdown, setShowHeroDropdown] = useState(false);
  const heroSearchDebounceRef = useRef(null);
  const heroSearchReqIdRef = useRef(0);

  const [radarTab, setRadarTab] = useState("upside");
  const [newsFilter, setNewsFilter] = useState("ALL");

  useEffect(() => {
    let cancelled = false;
    const loadOverview = async () => {
      setLoading(true);
      try {
        const res = await apiClient.get("/market-overview");
        if (!cancelled) {
          setOverview(res.data);
        }
      } catch (err) {
        console.error("Error cargando portal inicial:", err);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    loadOverview();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleHeroSearchChange = (e) => {
    const val = e.target.value;
    setHeroQuery(val);
    if (heroSearchDebounceRef.current) {
      clearTimeout(heroSearchDebounceRef.current);
    }
    const trimmed = val.trim();
    if (trimmed.length === 0) {
      heroSearchReqIdRef.current += 1;
      setHeroResults([]);
      setShowHeroDropdown(false);
      return;
    }
    const reqId = ++heroSearchReqIdRef.current;
    heroSearchDebounceRef.current = setTimeout(async () => {
      try {
        const res = await apiClient.get(
          `/search?q=${encodeURIComponent(trimmed)}`
        );
        if (reqId !== heroSearchReqIdRef.current) return;
        setHeroResults(res.data || []);
        setShowHeroDropdown(true);
      } catch {
        if (reqId === heroSearchReqIdRef.current) {
          setHeroResults([]);
        }
      }
    }, 250);
  };

  const handleHeroKeyDown = (e) => {
    if (e.key === "Enter" && heroQuery.trim()) {
      setShowHeroDropdown(false);
      onSelectTicker(heroQuery.trim().toUpperCase());
    }
  };

  const filteredNews = useMemo(() => {
    const list = overview?.news || [];
    if (newsFilter === "ALL") return list;
    return list.filter((n) => n.category === newsFilter);
  }, [overview, newsFilter]);

  const radarList = useMemo(() => {
    if (radarTab === "recent") return recentTickers;
    if (radarTab === "fcf") return overview?.radar?.top_fcf_yield || [];
    return overview?.radar?.top_upside || [];
  }, [radarTab, overview, recentTickers]);

  const todayFormatted = useMemo(() => {
    return new Intl.DateTimeFormat("es-AR", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(new Date());
  }, []);

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* BLOQUE 1: HERO DE BIENVENIDA + BUSCADOR PROTAGONISTA + ACCESOS RÁPIDOS */}
      <section className="bg-white border border-gray-200 rounded-xl shadow-sm p-4 sm:p-6 md:p-7">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 sm:gap-6">
          <div className="space-y-1.5 sm:space-y-2 max-w-xl">
            <div className="flex items-center gap-3">
              <BrandLogo size="lg" showSubtitle />
            </div>
            <p className="text-[11px] sm:text-xs text-gray-500 capitalize pt-0.5 sm:pt-1">{todayFormatted}</p>
            <h2 className="text-base sm:text-xl font-bold text-gray-900 tracking-tight leading-snug">
              Investigación fundamental, valoración DCF y screening cuantitativo
            </h2>
            <p className="text-xs text-gray-600 leading-relaxed">
              Analizá balances estandarizados SEC, múltiplos históricos LTM/NTM y flujos descontados en 2 etapas para acciones globales y ADRs.
            </p>
          </div>

          {/* Buscador central */}
          <div className="w-full lg:max-w-md">
            <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-1.5">
              Acceso directo a emisores
            </label>
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={heroQuery}
                onChange={handleHeroSearchChange}
                onKeyDown={handleHeroKeyDown}
                onFocus={() => {
                  if (heroResults.length > 0) setShowHeroDropdown(true);
                }}
                onBlur={() => setShowHeroDropdown(false)}
                placeholder="Ingresá ticker o empresa (ej: MSFT, MELI, JPM, YPF)..."
                className="w-full pl-10 pr-16 py-2.5 bg-gray-50 border border-gray-300 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:bg-white focus:border-orange-500 shadow-2xs"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-semibold text-gray-500 bg-white px-1.5 py-0.5 rounded border border-gray-200">
                Enter
              </span>

              {showHeroDropdown && heroResults.length > 0 && (
                <div className="absolute top-full left-0 w-full mt-1.5 bg-white border border-gray-200 rounded-lg shadow-xl z-40 overflow-hidden">
                  {heroResults.map((res, idx) => (
                    <div
                      key={idx}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => {
                        setShowHeroDropdown(false);
                        onSelectTicker(res.ticker);
                      }}
                      className="px-4 py-2.5 hover:bg-orange-50 cursor-pointer flex items-center justify-between border-b border-gray-100 last:border-0"
                    >
                      <div className="flex items-center truncate mr-2">
                        <span className="font-bold text-orange-600 text-xs w-14 shrink-0">
                          {res.ticker}
                        </span>
                        <span className="text-gray-800 text-xs truncate">{res.name}</span>
                      </div>
                      <span className="text-[10px] uppercase text-gray-400 shrink-0">{res.type}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Tickers rápidos de ejemplo */}
            <div className="flex flex-wrap items-center gap-1.5 mt-2.5 text-[11px] text-gray-500">
              <span>Sugeridos:</span>
              {["MSFT", "AAPL", "NVDA", "MELI", "JPM", "YPF"].map((sym) => (
                <button
                  key={sym}
                  type="button"
                  onClick={() => onSelectTicker(sym)}
                  className="px-2 py-0.5 rounded bg-gray-100 hover:bg-orange-100 hover:text-orange-700 font-semibold text-gray-700 transition-colors cursor-pointer"
                >
                  {sym}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 4 Tarjetas de Flujos de Trabajo */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3.5 mt-4 sm:mt-6 pt-4 sm:pt-5 border-t border-gray-100">
          <button
            type="button"
            onClick={() => onNavigateTab("Screener")}
            className="text-left p-2.5 sm:p-3.5 rounded-lg border border-gray-200 hover:border-orange-300 hover:bg-orange-50/40 transition-all group cursor-pointer"
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="p-1.5 rounded-md bg-orange-100 text-orange-600">
                <Filter className="w-4 h-4" />
              </span>
              <ArrowUpRight className="w-4 h-4 text-gray-400 group-hover:text-orange-500 transition-colors" />
            </div>
            <p className="text-xs font-bold text-gray-900">Screener Fundamental</p>
            <p className="text-[11px] text-gray-500 mt-0.5">
              {overview?.radar?.total_cached
                ? `${overview.radar.total_cached} emisores listos para filtrar`
                : "Buscador multi-criterio y exportación CSV"}
            </p>
          </button>

          <button
            type="button"
            onClick={() => onNavigateTab("Comparador")}
            className="text-left p-2.5 sm:p-3.5 rounded-lg border border-gray-200 hover:border-orange-300 hover:bg-orange-50/40 transition-all group cursor-pointer"
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="p-1.5 rounded-md bg-blue-50 text-blue-600">
                <Scale className="w-4 h-4" />
              </span>
              <ArrowUpRight className="w-4 h-4 text-gray-400 group-hover:text-orange-500 transition-colors" />
            </div>
            <p className="text-xs font-bold text-gray-900">Comparador Multi-Empresa</p>
            <p className="text-[11px] text-gray-500 mt-0.5">
              Contrastá hasta 5 empresas lado a lado
            </p>
          </button>

          <button
            type="button"
            onClick={() => onOpenScreenerPreset("value_contrarian")}
            className="text-left p-2.5 sm:p-3.5 rounded-lg border border-gray-200 hover:border-orange-300 hover:bg-orange-50/40 transition-all group cursor-pointer"
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="p-1.5 rounded-md bg-emerald-50 text-emerald-600">
                <Compass className="w-4 h-4" />
              </span>
              <ArrowUpRight className="w-4 h-4 text-gray-400 group-hover:text-orange-500 transition-colors" />
            </div>
            <p className="text-xs font-bold text-gray-900">Estrategia Value Contrarian</p>
            <p className="text-[11px] text-gray-500 mt-0.5">
              P/E ≤ 18x · FCF Yield ≥ 4,5% · Deuda controlada
            </p>
          </button>

          <button
            type="button"
            onClick={() => onOpenScreenerPreset("quality_compounders")}
            className="text-left p-2.5 sm:p-3.5 rounded-lg border border-gray-200 hover:border-orange-300 hover:bg-orange-50/40 transition-all group cursor-pointer"
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="p-1.5 rounded-md bg-amber-50 text-amber-600">
                <Award className="w-4 h-4" />
              </span>
              <ArrowUpRight className="w-4 h-4 text-gray-400 group-hover:text-orange-500 transition-colors" />
            </div>
            <p className="text-xs font-bold text-gray-900">Quality Compounders</p>
            <p className="text-[11px] text-gray-500 mt-0.5">
              ROIC ≥ 15% · Margen EBIT ≥ 20% · Crecimiento
            </p>
          </button>
        </div>
      </section>

      {/* BLOQUE 2: PULSO DE MERCADO (4 REFERENCIAS CON SPARKLINE) */}
      <section>
        <div className="flex items-center justify-between mb-2.5 px-1">
          <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500">
            Pulso de Mercado y Referencia Macro (30 días)
          </h3>
          {loading && (
            <span className="inline-flex items-center text-xs text-orange-500">
              <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> Actualizando referencias...
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-4">
          {(overview?.benchmarks || [
            { symbol: "SPY", name: "S&P 500 ETF", subtitle: "Large Cap EE. UU.", unit: "US$", price: 0, change: 0, change_pct: 0, sparkline: [] },
            { symbol: "QQQ", name: "Nasdaq 100 ETF", subtitle: "Tecnología & Crecimiento", unit: "US$", price: 0, change: 0, change_pct: 0, sparkline: [] },
            { symbol: "ARGT", name: "MSCI Argentina ETF", subtitle: "Renta Variable Argentina", unit: "US$", price: 0, change: 0, change_pct: 0, sparkline: [] },
            { symbol: "^TNX", name: "Tasa Tesoro 10Y", subtitle: "Tasa Libre de Riesgo EE. UU.", unit: "%", price: 0, change: 0, change_pct: 0, sparkline: [] },
          ]).map((bm) => {
            const isPos = bm.change >= 0;
            return (
              <div
                key={bm.symbol}
                onClick={() => onSelectTicker(bm.symbol)}
                title={`Abrir gráfico histórico de ${bm.symbol}`}
                className="bg-white border border-gray-200 rounded-xl p-3 sm:p-4 shadow-2xs hover:border-orange-300 transition-colors cursor-pointer flex items-center justify-between gap-1.5"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold text-gray-900 truncate">{bm.name}</span>
                    <span className="text-[10px] font-semibold text-gray-400 shrink-0">{bm.symbol}</span>
                  </div>
                  <p className="text-[11px] text-gray-500 mb-2 truncate">{bm.subtitle}</p>
                  <p className="text-base sm:text-lg font-bold text-gray-900 tabular-nums leading-none">
                    {bm.price > 0
                      ? bm.unit === "%"
                        ? `${fmtNum(bm.price, 2)}%`
                        : `US$ ${fmtNum(bm.price, 2)}`
                      : "-"}
                  </p>
                  <p
                    className={`text-xs font-semibold mt-1 inline-flex items-center tabular-nums ${
                      isPos ? "text-emerald-600" : "text-[#d93025]"
                    }`}
                  >
                    {isPos ? (
                      <TrendingUp className="w-3 h-3 mr-1" />
                    ) : (
                      <TrendingDown className="w-3 h-3 mr-1" />
                    )}
                    {isPos ? "+" : ""}
                    {fmtNum(bm.change_pct, 2)}%
                  </p>
                </div>

                <MiniSparkline points={bm.sparkline} isPositive={isPos} />
              </div>
            );
          })}
        </div>
      </section>

      {/* BLOQUE 3 Y 4: RADAR DE OPORTUNIDADES (IZQ) + NOTICIAS DE MERCADO (DER) */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-6">
        {/* Radar Fundamental */}
        <div className="lg:col-span-6 bg-white border border-gray-200 rounded-xl shadow-sm flex flex-col overflow-hidden">
          <div className="px-4 sm:px-5 py-3.5 border-b border-gray-200 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-orange-500" />
              <h3 className="text-sm font-bold text-gray-900">Radar Fundamental</h3>
            </div>

            <div className="flex rounded-lg border border-gray-200 bg-gray-50 p-0.5 text-[11px]">
              <button
                type="button"
                onClick={() => setRadarTab("upside")}
                className={`px-2.5 py-1 rounded-md font-medium transition-colors cursor-pointer ${
                  radarTab === "upside"
                    ? "bg-white text-orange-600 shadow-2xs font-semibold"
                    : "text-gray-600 hover:text-gray-900"
                }`}
              >
                Potencial WS
              </button>
              <button
                type="button"
                onClick={() => setRadarTab("fcf")}
                className={`px-2.5 py-1 rounded-md font-medium transition-colors cursor-pointer ${
                  radarTab === "fcf"
                    ? "bg-white text-orange-600 shadow-2xs font-semibold"
                    : "text-gray-600 hover:text-gray-900"
                }`}
              >
                Alto FCF Yield
              </button>
              <button
                type="button"
                onClick={() => setRadarTab("recent")}
                className={`px-2.5 py-1 rounded-md font-medium transition-colors inline-flex items-center gap-1 cursor-pointer ${
                  radarTab === "recent"
                    ? "bg-white text-orange-600 shadow-2xs font-semibold"
                    : "text-gray-600 hover:text-gray-900"
                }`}
              >
                <Clock className="w-3 h-3" /> Recientes
              </button>
            </div>
          </div>

          <div className="flex-1 divide-y divide-gray-100">
            {radarList.length === 0 ? (
              <div className="py-12 px-5 text-center text-xs text-gray-500">
                {radarTab === "recent"
                  ? "Todavía no consultaste empresas individuales en esta sesión. Buscá un ticker arriba para comenzar."
                  : "Sincronizá emisores desde el Screener para poblar el radar fundamental."}
              </div>
            ) : (
              radarList.map((item) => (
                <div
                  key={item.ticker}
                  onClick={() => onSelectTicker(item.ticker)}
                  className="px-4 sm:px-5 py-3 hover:bg-orange-50/50 transition-colors cursor-pointer flex items-center justify-between gap-3"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs text-orange-600">{item.ticker}</span>
                      <span className="text-xs font-medium text-gray-900 truncate">{item.name}</span>
                    </div>
                    <p className="text-[11px] text-gray-500 mt-0.5">
                      {item.sector || "Renta Variable"} · P/E LTM:{" "}
                      <span className="font-semibold text-gray-700">
                        {item.pe_ltm ? `${fmtNum(item.pe_ltm, 1)}x` : "-"}
                      </span>
                    </p>
                  </div>

                  <div className="text-right shrink-0 tabular-nums">
                    <p className="text-xs font-bold text-gray-900">
                      {item.price ? `US$ ${fmtNum(item.price, 2)}` : "-"}
                    </p>
                    {radarTab === "fcf" && item.fcf_yield_pct !== null && item.fcf_yield_pct !== undefined ? (
                      <span className="inline-block text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded mt-0.5">
                        FCF Yield {fmtNum(item.fcf_yield_pct, 2)}%
                      </span>
                    ) : item.upside_ws_pct !== null && item.upside_ws_pct !== undefined ? (
                      <span
                        className={`inline-block text-[11px] font-semibold px-1.5 py-0.5 rounded mt-0.5 ${
                          item.upside_ws_pct >= 0
                            ? "text-emerald-700 bg-emerald-50"
                            : "text-red-700 bg-red-50"
                        }`}
                      >
                        WS {item.upside_ws_pct >= 0 ? "+" : ""}
                        {fmtNum(item.upside_ws_pct, 1)}%
                      </span>
                    ) : null}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Noticias de Mercado */}
        <div className="lg:col-span-6 bg-white border border-gray-200 rounded-xl shadow-sm flex flex-col overflow-hidden">
          <div className="px-4 sm:px-5 py-3.5 border-b border-gray-200 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Newspaper className="w-4 h-4 text-orange-500" />
              <h3 className="text-sm font-bold text-gray-900">Titulares de Mercado</h3>
            </div>

            <div className="flex rounded-lg border border-gray-200 bg-gray-50 p-0.5 text-[11px]">
              {[
                { id: "ALL", label: "Todos" },
                { id: "Global", label: "Global" },
                { id: "Tech & IA", label: "Tech & IA" },
                { id: "LatAm", label: "LatAm" },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setNewsFilter(tab.id)}
                  className={`px-2.5 py-1 rounded-md font-medium transition-colors cursor-pointer ${
                    newsFilter === tab.id
                      ? "bg-white text-orange-600 shadow-2xs font-semibold"
                      : "text-gray-600 hover:text-gray-900"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 divide-y divide-gray-100 max-h-95 overflow-y-auto">
            {filteredNews.length === 0 ? (
              <div className="py-12 px-5 text-center text-xs text-gray-500">
                No hay titulares disponibles en esta categoría en este momento.
              </div>
            ) : (
              filteredNews.map((n, idx) => {
                const dateLabel = n.providerPublishTime
                  ? new Date(n.providerPublishTime * 1000).toLocaleDateString("es-AR", {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "";
                return (
                  <div key={idx} className="px-4 sm:px-5 py-3 hover:bg-gray-50 transition-colors">
                    <div className="flex items-center justify-between gap-2 text-[10px] font-bold uppercase text-gray-400 mb-1">
                      <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                          {n.category}
                        </span>
                        <span>{n.publisher}</span>
                      </div>
                      <span>{dateLabel}</span>
                    </div>
                    <a
                      href={n.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs font-medium text-gray-800 hover:text-orange-600 transition-colors inline-flex items-start gap-1 leading-snug"
                    >
                      <span>{n.title}</span>
                      <ExternalLink className="w-3 h-3 shrink-0 mt-0.5 text-gray-400" />
                    </a>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </section>
    </div>
  );
}