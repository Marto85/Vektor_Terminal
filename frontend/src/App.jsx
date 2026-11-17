import { useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  Home,
  Bookmark,
  FileText,
  BarChart3,
  PieChart,
  Scale,
  Filter,
  Search,
  Bell,
  Settings,
  Download,
  Maximize2,
  Loader2,
  ExternalLink,
  Heart,
  ChevronUp,
  ChevronDown,
  Info,
  X,
  Check,
  CheckCheck,
} from "lucide-react";
import BrandLogo from "./components/BrandLogo";
import HomeOverview from "./components/HomeOverview";
import WatchlistTab from "./components/WatchlistTab";
import { ALERTABLE_METRICS } from "./data/watchlistConstants";
import StockChart from "./components/StockChart";
import CapitalStructurePanel from "./components/CapitalStructurePanel";
import ValuationTab from "./components/ValuationTab";
import ComparatorTab from "./components/ComparatorTab";
import ScreenerTab from "./components/ScreenerTab";
import FinancialHealthPanel from "./components/FinancialHealthPanel";
import MetricInfoDrawer from "./components/MetricInfoDrawer";
import { getGlossaryEntry } from "./data/metricsGlossary";

const RECENT_STORAGE_KEY = "tf_recent_tickers_v1";

function loadRecentTickers() {
  try {
    const raw = localStorage.getItem(RECENT_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function App() {
  const [activeSidebarTab, setActiveSidebarTab] = useState("Inicio");
  const [tableroInitialSubView, setTableroInitialSubView] = useState("lists");
  const [activeContentTab, setActiveContentTab] = useState(
    "Cuenta de Resultados",
  );
  const [period, setPeriod] = useState("annual");
  const [showChart, setShowChart] = useState(true);
  const [activeGlossaryInfo, setActiveGlossaryInfo] = useState(null);
  const [screenerPresetId, setScreenerPresetId] = useState("all");

  const [tickerInput, setTickerInput] = useState("");
  const [currentTicker, setCurrentTicker] = useState("MSFT");
  const [hasLoadedCompany, setHasLoadedCompany] = useState(false);
  const [financialData, setFinancialData] = useState([]);

  const [profileData, setProfileData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [recentTickers, setRecentTickers] = useState(loadRecentTickers);

  const [searchResults, setSearchResults] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);

  // Estado Multi-Watchlist y Notificaciones (Etapa 4)
  const [watchlistData, setWatchlistData] = useState(null);
  const [showAlertsPopover, setShowAlertsPopover] = useState(false);
  const alertsPopoverRef = useRef(null);

  // Modal rápido "Agregar al tablero" desde la cabecera de empresa
  const [showAddToBoardModal, setShowAddToBoardModal] = useState(false);
  const [modalTargetWlId, setModalTargetWlId] = useState("");
  const [modalBuyTarget, setModalBuyTarget] = useState("");
  const [modalSellTarget, setModalSellTarget] = useState("");
  const [modalThesis, setModalThesis] = useState("");
  const [modalAlerts, setModalAlerts] = useState([]);
  const [savingToBoard, setSavingToBoard] = useState(false);

  useEffect(() => {
    axios
      .get("http://127.0.0.1:8000/api/v1/watchlists")
      .then((res) => setWatchlistData(res.data))
      .catch((err) => console.error("Error cargando watchlists:", err));
  }, []);

  useEffect(() => {
    const handleOutside = (e) => {
      if (
        alertsPopoverRef.current &&
        !alertsPopoverRef.current.contains(e.target)
      ) {
        setShowAlertsPopover(false);
      }
    };
    if (showAlertsPopover) {
      document.addEventListener("mousedown", handleOutside);
    }
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [showAlertsPopover]);

  const openGlossary = (metricKey, formattedVal = null) => {
    const entry = getGlossaryEntry(metricKey);
    if (entry) {
      setActiveGlossaryInfo({ entry, currentValue: formattedVal });
    }
  };

  const globalNavItems = [
    { id: "Inicio", name: "Inicio y Mercado", icon: Home },
    { id: "Tablero", name: "Mi Tablero", icon: Bookmark },
    { id: "Screener", name: "Screener", icon: Filter },
    { id: "Comparador", name: "Comparador", icon: Scale },
  ];

  const companyNavItems = [
    { id: "Resumen", name: "Resumen y noticias", icon: FileText },
    { id: "Finanzas", name: "Finanzas", icon: BarChart3 },
    { id: "Valoracion", name: "Valoración", icon: PieChart },
  ];

  const contentTabs = [
    "Cuenta de Resultados",
    "Balance de Situación",
    "Estado de Flujo de Efectivo",
    "Ratios",
    "Segmentos",
  ];

  const saveToRecent = (sym, prof) => {
    const entry = {
      ticker: sym,
      name: prof?.name || sym,
      sector: "",
      price: prof?.price || null,
      pe_ltm: prof?.summary_metrics?.valuation?.pe_ltm || null,
      fcf_yield_pct: null,
      upside_ws_pct:
        prof?.summary_metrics?.valuation?.target_price && prof?.price
          ? Number(
              (
                ((prof.summary_metrics.valuation.target_price - prof.price) /
                  prof.price) *
                100
              ).toFixed(1),
            )
          : null,
    };

    setRecentTickers((prev) => {
      const next = [entry, ...prev.filter((p) => p.ticker !== sym)].slice(0, 6);
      try {
        localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Ignorar si localStorage no está disponible
      }
      return next;
    });
  };

  const executeSearch = async (
    tickerToSearch,
    selectedPeriod = period,
    switchToSummary = false,
  ) => {
    if (!tickerToSearch) return;
    const upperTicker = tickerToSearch.toUpperCase();
    setIsLoading(true);
    setError(null);

    if (switchToSummary) {
      setActiveSidebarTab("Resumen");
    }

    try {
      const [finResponse, profResponse] = await Promise.all([
        axios.get(
          `http://127.0.0.1:8000/api/v1/company/${upperTicker}/financials/${selectedPeriod}`,
        ),
        axios.get(
          `http://127.0.0.1:8000/api/v1/company/${upperTicker}/profile`,
        ),
      ]);

      setFinancialData(finResponse.data);
      setProfileData(profResponse.data);
      setCurrentTicker(upperTicker);
      setHasLoadedCompany(true);
      saveToRecent(upperTicker, profResponse.data);
    } catch (err) {
      console.error("Error al buscar datos:", err);
      setError(
        err.response?.data?.detail || "Error de conexión con el servidor",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenCompanyTab = (tabId) => {
    setActiveSidebarTab(tabId);
    if (!hasLoadedCompany) {
      executeSearch(currentTicker, period, false);
    }
  };

  const handleOpenScreenerWithPreset = (presetId = "all") => {
    setScreenerPresetId(presetId);
    setActiveSidebarTab("Screener");
  };

  const handleOpenTablero = (sub = "lists") => {
    setTableroInitialSubView(sub);
    setActiveSidebarTab("Tablero");
  };

  const handleMarkNotifRead = async (notifId) => {
    try {
      const res = await axios.post(
        `http://127.0.0.1:8000/api/v1/notifications/${notifId}/read`,
      );
      setWatchlistData(res.data);
    } catch (err) {
      console.error("Error marcando notificación como leída:", err);
    }
  };

  const handleMarkAllNotifsRead = async () => {
    try {
      const res = await axios.post(
        "http://127.0.0.1:8000/api/v1/notifications/read-all",
      );
      setWatchlistData(res.data);
    } catch (err) {
      console.error("Error marcando todas como leídas:", err);
    }
  };

  const handlePeriodChange = (newPeriod) => {
    if (newPeriod === period) return;
    setPeriod(newPeriod);
    executeSearch(currentTicker, newPeriod, false);
  };

  const handleSearchChange = async (e) => {
    const value = e.target.value;
    setTickerInput(value);

    if (value.trim().length > 0) {
      try {
        const response = await axios.get(
          `http://127.0.0.1:8000/api/v1/search?q=${value}`,
        );
        setSearchResults(response.data);
        setShowDropdown(true);
      } catch (err) {
        console.error("Error buscando tickers", err);
      }
    } else {
      setSearchResults([]);
      setShowDropdown(false);
    }
  };

  const handleSelectTicker = (selectedTicker) => {
    setTickerInput(selectedTicker);
    setShowDropdown(false);
    setSearchResults([]);
    const shouldSwitch =
      activeSidebarTab === "Inicio" ||
      activeSidebarTab === "Tablero" ||
      activeSidebarTab === "Screener" ||
      activeSidebarTab === "Comparador";
    executeSearch(selectedTicker, period, shouldSwitch);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      setShowDropdown(false);
      const shouldSwitch =
        activeSidebarTab === "Inicio" ||
        activeSidebarTab === "Tablero" ||
        activeSidebarTab === "Screener" ||
        activeSidebarTab === "Comparador";
      executeSearch(tickerInput.trim(), period, shouldSwitch);
    }
  };

  const openAddToBoardModal = () => {
    const wls = watchlistData?.watchlists || [];
    const defaultWl = wls[0];
    const targetId = defaultWl ? String(defaultWl.id) : "";
    setModalTargetWlId(targetId);

    const existingItem = defaultWl?.items?.find(
      (it) => it.ticker === currentTicker,
    );
    setModalBuyTarget(
      existingItem?.buy_target_price
        ? String(existingItem.buy_target_price)
        : "",
    );
    setModalSellTarget(
      existingItem?.sell_target_price
        ? String(existingItem.sell_target_price)
        : "",
    );
    setModalThesis(existingItem?.thesis_note || "");
    setModalAlerts(
      Array.isArray(existingItem?.alerts)
        ? existingItem.alerts.map((a) => ({ ...a }))
        : [],
    );
    setShowAddToBoardModal(true);
  };

  const handleModalWatchlistSelect = (newId) => {
    setModalTargetWlId(newId);
    const wl = (watchlistData?.watchlists || []).find(
      (w) => String(w.id) === String(newId),
    );
    const existingItem = wl?.items?.find((it) => it.ticker === currentTicker);
    setModalBuyTarget(
      existingItem?.buy_target_price
        ? String(existingItem.buy_target_price)
        : "",
    );
    setModalSellTarget(
      existingItem?.sell_target_price
        ? String(existingItem.sell_target_price)
        : "",
    );
    setModalThesis(existingItem?.thesis_note || "");
    setModalAlerts(
      Array.isArray(existingItem?.alerts)
        ? existingItem.alerts.map((a) => ({ ...a }))
        : [],
    );
  };

  const handleConfirmAddToBoard = async (e) => {
    e.preventDefault();
    if (!modalTargetWlId) return;
    setSavingToBoard(true);
    const parsedAlerts = modalAlerts
      .filter((r) => r.value !== "" && !Number.isNaN(Number(r.value)))
      .map((r) => ({
        metric: r.metric,
        op: r.op,
        value: Number(r.value),
      }));

    try {
      const res = await axios.post(
        `http://127.0.0.1:8000/api/v1/watchlists/${modalTargetWlId}/items`,
        {
          ticker: currentTicker,
          buy_target_price:
            modalBuyTarget !== "" ? Number(modalBuyTarget) : null,
          sell_target_price:
            modalSellTarget !== "" ? Number(modalSellTarget) : null,
          thesis_note: modalThesis,
          alerts: parsedAlerts,
        },
      );
      setWatchlistData(res.data);
      setShowAddToBoardModal(false);
    } catch (err) {
      console.error("Error guardando en tablero:", err);
    } finally {
      setSavingToBoard(false);
    }
  };

  const currentTabData = financialData.filter(
    (item) => item.Categoría === activeContentTab,
  );

  const availableYears =
    currentTabData.length > 0
      ? Object.keys(currentTabData[0])
          .filter(
            (key) =>
              key !== "Categoría" &&
              key !== "Métrica" &&
              key !== "is_pct" &&
              key !== "is_sub" &&
              key !== "is_header",
          )
          .sort()
      : [];

  const formatNumber = (value, isPct = false) => {
    if (
      value === 0 ||
      value === 0.0 ||
      value === "-" ||
      value === null ||
      value === undefined
    )
      return "-";

    const isNegative = value < 0;
    const absValue = Math.abs(value);

    let formatted = new Intl.NumberFormat("es-AR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(absValue);

    formatted = isPct ? `${formatted}%` : formatted;

    return isNegative ? `(${formatted})` : formatted;
  };

  const getDomain = (url) => {
    try {
      if (!url) return null;
      const parsed = new URL(url);
      return parsed.hostname.replace("www.", "");
    } catch {
      return null;
    }
  };

  const domain = getDomain(profileData?.website);
  const isCompanyContextTab =
    activeSidebarTab === "Resumen" ||
    activeSidebarTab === "Finanzas" ||
    activeSidebarTab === "Valoracion";

  const notificationsList = watchlistData?.notifications || [];
  const unreadNotifications = notificationsList.filter((n) => !n.is_read);
  const unreadNotifCount = unreadNotifications.length;
  const isCurrentTickerInAnyWatchlist = (watchlistData?.watchlists || []).some(
    (wl) => (wl.items || []).some((it) => it.ticker === currentTicker),
  );

  return (
    <div className="flex h-screen bg-[#1e1e1e] font-sans text-gray-200 overflow-hidden">
      {/* SIDEBAR */}
      <aside className="w-56 bg-[#252526] border-r border-gray-700 flex flex-col shrink-0">
        <button
          type="button"
          onClick={() => setActiveSidebarTab("Inicio")}
          title="Volver a Inicio y Mercado"
          className="h-12 flex items-center px-4 border-b border-gray-700 bg-[#1e1e1e] hover:bg-[#232325] transition-colors cursor-pointer text-left"
        >
          <BrandLogo size="md" />
        </button>

        <div className="flex-1 overflow-y-auto py-4 space-y-5">
          {/* Sección Global */}
          <div>
            <div className="px-3 mb-2">
              <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                Mercado y Descubrimiento
              </p>
            </div>
            <nav className="space-y-0.5 px-2">
              {globalNavItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeSidebarTab === item.id;

                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      if (item.id === "Screener") {
                        handleOpenScreenerWithPreset("all");
                      } else if (item.id === "Tablero") {
                        handleOpenTablero("lists");
                      } else {
                        setActiveSidebarTab(item.id);
                      }
                    }}
                    className={`w-full flex items-center justify-between px-3 py-1.5 text-xs rounded transition-colors ${
                      isActive
                        ? "bg-orange-500/10 text-orange-500 font-medium cursor-default"
                        : "text-gray-400 hover:bg-gray-800 hover:text-gray-200 cursor-pointer"
                    }`}
                  >
                    <span className="flex items-center">
                      <Icon className="w-3.5 h-3.5 mr-2" />
                      {item.name}
                    </span>
                    {item.id === "Tablero" && unreadNotifCount > 0 && (
                      <span className="px-1.5 py-0.2 rounded-full bg-orange-500 text-white text-[10px] font-bold">
                        {unreadNotifCount}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Sección Empresa Activa */}
          <div>
            <div className="px-3 mb-2">
              <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                {currentTicker} Fundamental Analysis
              </p>
            </div>
            <nav className="space-y-0.5 px-2">
              {companyNavItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeSidebarTab === item.id;

                return (
                  <button
                    key={item.id}
                    onClick={() => handleOpenCompanyTab(item.id)}
                    className={`w-full flex items-center px-3 py-1.5 text-xs rounded transition-colors ${
                      isActive
                        ? "bg-orange-500/10 text-orange-500 font-medium cursor-default"
                        : "text-gray-400 hover:bg-gray-800 hover:text-gray-200 cursor-pointer"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5 mr-2" />
                    {item.name}
                  </button>
                );
              })}
            </nav>
          </div>
        </div>
      </aside>

      {/* CONTENIDO PRINCIPAL */}
      <main className="flex-1 flex flex-col min-w-0 bg-[#f9fafb]">
        {/* HEADER CON AUTOCOMPLETADO Y CAMPANA DE NOTIFICACIONES */}
        <header className="h-12 bg-[#252526] border-b border-gray-700 flex items-center justify-between px-4 shrink-0 z-50">
          <div className="flex items-center flex-1 max-w-xl">
            <div className="relative w-full">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500" />
              <input
                type="text"
                value={tickerInput}
                onChange={handleSearchChange}
                onKeyDown={handleKeyDown}
                onFocus={() => {
                  if (searchResults.length > 0) setShowDropdown(true);
                }}
                onBlur={() => setShowDropdown(false)}
                placeholder="Busca entre 100.000 empresas en todo el mundo (Ej: AAPL + Enter)"
                className="w-full pl-9 pr-4 py-1 bg-[#333333] border border-gray-600 rounded text-xs text-white placeholder-gray-400 focus:outline-none focus:border-orange-500 focus:bg-[#1e1e1e]"
              />
              <div className="absolute right-2 top-1/2 transform -translate-y-1/2 text-[10px] text-gray-500 bg-[#252526] px-1 rounded border border-gray-600">
                Enter
              </div>

              {showDropdown && searchResults.length > 0 && (
                <div className="absolute top-full left-0 w-full mt-1 bg-[#252526] border border-gray-600 rounded shadow-lg overflow-hidden">
                  {searchResults.map((res, idx) => (
                    <div
                      key={idx}
                      className="px-4 py-2 hover:bg-[#333333] cursor-pointer flex justify-between items-center border-b border-gray-700/50 last:border-0"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => handleSelectTicker(res.ticker)}
                    >
                      <div className="flex items-center truncate mr-2">
                        <span className="font-bold text-orange-500 mr-3 w-12 shrink-0">
                          {res.ticker}
                        </span>
                        <span className="text-gray-300 text-xs truncate">
                          {res.name}
                        </span>
                      </div>
                      <span className="text-gray-500 text-[10px] uppercase shrink-0">
                        {res.type}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center space-x-4 text-gray-400">
            {/* Campana de notificaciones persistentes */}
            <div className="relative" ref={alertsPopoverRef}>
              <button
                type="button"
                onClick={() => setShowAlertsPopover((prev) => !prev)}
                title="Notificaciones y Alertas"
                className="relative p-1 hover:text-white cursor-pointer"
              >
                <Bell className="w-4 h-4" />
                {unreadNotifCount > 0 && (
                  <span className="absolute -top-1 -right-1 min-w-4 h-4 px-1 rounded-full bg-orange-500 text-white text-[10px] font-bold flex items-center justify-center">
                    {unreadNotifCount}
                  </span>
                )}
              </button>

              {showAlertsPopover && (
                <div className="absolute right-0 mt-2 w-96 bg-white border border-gray-200 rounded-xl shadow-2xl z-50 overflow-hidden text-xs">
                  <div className="px-4 py-2.5 bg-gray-900 text-white flex items-center justify-between gap-2">
                    <span className="font-bold">
                      Notificaciones ({unreadNotifCount} nuevas)
                    </span>
                    <div className="flex items-center gap-3">
                      {unreadNotifCount > 0 && (
                        <button
                          type="button"
                          onClick={handleMarkAllNotifsRead}
                          title="Marcar todas como leídas"
                          className="inline-flex items-center gap-1 text-[11px] text-emerald-400 hover:underline cursor-pointer"
                        >
                          <CheckCheck className="w-3.5 h-3.5" />
                          Marcar todas
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          setShowAlertsPopover(false);
                          handleOpenTablero("notifications");
                        }}
                        className="text-[11px] text-orange-400 hover:underline cursor-pointer"
                      >
                        Historial
                      </button>
                    </div>
                  </div>
                  <div className="max-h-72 overflow-y-auto divide-y divide-gray-100">
                    {unreadNotifications.length === 0 ? (
                      <div className="p-5 text-center text-gray-500">
                        No tenés notificaciones pendientes de lectura.
                      </div>
                    ) : (
                      unreadNotifications.map((n) => (
                        <div
                          key={n.id}
                          className="p-3 bg-orange-50/60 hover:bg-orange-100/60 transition-colors flex items-start justify-between gap-2"
                        >
                          <div
                            onClick={async () => {
                              setShowAlertsPopover(false);
                              await handleMarkNotifRead(n.id);
                              executeSearch(n.ticker, period, true);
                            }}
                            className="flex-1 min-w-0 cursor-pointer"
                          >
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-orange-600 truncate">
                                {n.ticker} · {n.title}
                              </span>
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white border border-gray-200 text-gray-600 font-medium shrink-0">
                                {n.watchlist_name}
                              </span>
                            </div>
                            <p className="text-gray-700 mt-0.5">{n.detail}</p>
                            <p className="text-[10px] text-gray-400 mt-0.5">
                              {n.triggered_at}
                            </p>
                          </div>

                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleMarkNotifRead(n.id);
                            }}
                            title="Marcar como leída"
                            className="p-1.5 rounded-lg border border-gray-200 bg-white text-gray-500 hover:text-emerald-600 hover:border-emerald-300 transition-colors cursor-pointer shrink-0"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            <Settings className="w-4 h-4 hover:text-white cursor-pointer" />
            <div className="w-6 h-6 rounded-full bg-orange-600 flex items-center justify-center text-white text-xs font-bold">
              M
            </div>
          </div>
        </header>

        {/* CABECERA EMPRESA GLOBAL (Visible solo en contexto de empresa individual) */}
        {isCompanyContextTab && (
          <div className="bg-white border-b border-gray-200 shrink-0">
            <div className="max-w-7xl mx-auto px-6 py-4">
              <div className="flex justify-between items-start">
                <div className="flex items-start space-x-4">
                  <div className="w-12 h-12 bg-[#dc2626] rounded flex items-center justify-center text-white text-3xl font-bold shrink-0 shadow-sm">
                    {currentTicker.charAt(0)}
                  </div>

                  <div className="flex flex-col">
                    <h1 className="text-[32px] font-bold text-gray-900 leading-none tracking-tight">
                      {currentTicker}
                    </h1>
                    <p className="text-[15px] text-gray-500 mt-1">
                      {profileData ? profileData.name : "Cargando..."}
                    </p>

                    <div className="flex items-center space-x-2 mt-3">
                      <button
                        type="button"
                        onClick={openAddToBoardModal}
                        className={`flex items-center px-3 py-1.5 border rounded text-xs font-medium transition-colors cursor-pointer shadow-sm ${
                          isCurrentTickerInAnyWatchlist
                            ? "border-orange-300 bg-orange-50 text-orange-700 hover:bg-orange-100"
                            : "border-gray-300 text-gray-700 hover:bg-gray-50"
                        }`}
                      >
                        <Heart
                          className={`w-3.5 h-3.5 mr-1.5 text-orange-500 ${
                            isCurrentTickerInAnyWatchlist
                              ? "fill-orange-500"
                              : ""
                          }`}
                        />
                        {isCurrentTickerInAnyWatchlist
                          ? "En tu tablero"
                          : "Agregar al tablero"}
                      </button>
                      <button className="px-3 py-1.5 border border-gray-300 rounded text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer shadow-sm">
                        USD
                      </button>
                      <button
                        onClick={() => setShowChart((prev) => !prev)}
                        className="flex items-center px-3 py-1.5 border border-gray-300 rounded text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer shadow-sm"
                      >
                        {showChart ? (
                          <>
                            Ocultar gráfico{" "}
                            <ChevronUp className="w-3.5 h-3.5 ml-1.5" />
                          </>
                        ) : (
                          <>
                            Mostrar gráfico{" "}
                            <ChevronDown className="w-3.5 h-3.5 ml-1.5" />
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="text-right flex flex-col items-end">
                  <h2 className="text-[36px] font-bold text-gray-900 leading-none tracking-tight">
                    US$ {profileData ? formatNumber(profileData.price) : "0.00"}
                  </h2>
                  <p
                    className={`text-[15px] font-bold mt-1 ${profileData?.change < 0 ? "text-[#d93025]" : "text-green-600"}`}
                  >
                    {profileData
                      ? `${profileData.change < 0 ? "-US$ " : profileData.change > 0 ? "+US$ " : "US$ "}${formatNumber(Math.abs(profileData.change))} (${profileData.change > 0 ? "+" : profileData.change < 0 ? "-" : ""}${formatNumber(Math.abs(profileData.change_pct), true)})`
                      : "US$ 0,00 (0,00%)"}
                  </p>
                  <p className="text-[11px] text-gray-400 mt-1">
                    Datos de mercado actualizados · GMT-3
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ÁREA DE CONTENIDO CONDICIONAL */}
        <div className="flex-1 overflow-auto">
          <div className="max-w-7xl mx-auto px-6 py-6">
            {/* VISTA PORTAL INICIAL */}
            {activeSidebarTab === "Inicio" && (
              <HomeOverview
                onSelectTicker={(sym) => executeSearch(sym, period, true)}
                onNavigateTab={(tabId) => setActiveSidebarTab(tabId)}
                onOpenScreenerPreset={(presetId) =>
                  handleOpenScreenerWithPreset(presetId)
                }
                recentTickers={recentTickers}
              />
            )}

            {/* VISTA MI TABLERO / WATCHLISTS Y CENTRO DE NOTIFICACIONES */}
            {activeSidebarTab === "Tablero" && (
              <WatchlistTab
                key={tableroInitialSubView}
                initialSubView={tableroInitialSubView}
                watchlistData={watchlistData}
                onWatchlistUpdated={(updated) => setWatchlistData(updated)}
                onSelectCompany={(sym) => executeSearch(sym, period, true)}
              />
            )}

            {/* BLOQUE GLOBAL EMPRESA: Gráfico (Izq) y Panel de Datos 2 Columnas (Der) */}
            {showChart && isCompanyContextTab && (
              <div className="bg-white border border-gray-200 rounded-lg shadow-sm flex flex-col lg:flex-row mb-6 overflow-hidden">
                <StockChart
                  ticker={currentTicker}
                  companyName={profileData?.name}
                />

                <CapitalStructurePanel
                  summaryMetrics={profileData?.summary_metrics}
                  onOpenInfo={openGlossary}
                />
              </div>
            )}

            {/* Sub-Nav de Empresa Individual */}
            {isCompanyContextTab && (
              <div className="flex border-b border-gray-200 mb-6 space-x-8 px-2">
                {companyNavItems.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleOpenCompanyTab(item.id)}
                    className={`pb-3 text-[15px] transition-colors relative ${
                      activeSidebarTab === item.id
                        ? "text-orange-500 font-semibold cursor-default"
                        : "text-gray-500 hover:text-gray-800 font-medium cursor-pointer"
                    }`}
                  >
                    {item.name}
                    {activeSidebarTab === item.id && (
                      <span className="absolute -bottom-px left-0 w-full h-0.5 bg-orange-500"></span>
                    )}
                  </button>
                ))}
              </div>
            )}

            {/* PESTAÑA: RESUMEN Y NOTICIAS */}
            {activeSidebarTab === "Resumen" && (
              <div className="space-y-6">
                <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-5">
                  <h3 className="text-sm font-bold text-gray-900 mb-2">
                    Acerca de la empresa
                  </h3>
                  <p className="text-sm text-gray-600 leading-relaxed mb-3">
                    {profileData?.description || "Buscando descripción..."}
                  </p>
                  {domain && (
                    <a
                      href={profileData.website}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center text-xs font-medium text-blue-600 hover:text-blue-800"
                    >
                      <ExternalLink className="w-3 h-3 mr-1" /> {domain}
                    </a>
                  )}
                </div>

                <div className="flex space-x-6">
                  <div className="flex-1 bg-white border border-gray-200 rounded-lg shadow-sm">
                    <div className="px-4 py-3 border-b border-gray-200">
                      <span className="text-sm font-bold text-gray-800">
                        Noticias y desarrollos significativos
                      </span>
                    </div>
                    <div className="p-4 space-y-4">
                      {profileData?.news && profileData.news.length > 0 ? (
                        profileData.news.map((n, i) => {
                          const date = new Date(
                            n.providerPublishTime * 1000,
                          ).toLocaleDateString();
                          return (
                            <div
                              key={i}
                              className="border-b border-gray-100 pb-3 last:border-0 last:pb-0"
                            >
                              <span className="text-[10px] font-bold text-gray-400 uppercase">
                                {date} · {n.publisher}
                              </span>
                              <a
                                href={n.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="block text-sm font-medium text-gray-800 hover:text-blue-600 cursor-pointer mt-1 transition-colors"
                              >
                                {n.title}
                              </a>
                            </div>
                          );
                        })
                      ) : (
                        <p className="text-sm text-gray-500">
                          No hay noticias recientes.
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="w-1/3 bg-white border border-gray-200 rounded-lg shadow-sm">
                    <div className="px-4 py-3 border-b border-gray-200">
                      <span className="text-sm font-bold text-gray-800">
                        Eventos próximos
                      </span>
                    </div>
                    <div className="p-4 space-y-3 text-sm">
                      <div className="flex items-start">
                        <div className="w-10 text-center mr-3">
                          <span className="block text-[10px] font-bold text-gray-400 uppercase">
                            Dic
                          </span>
                          <span className="block text-lg font-bold text-gray-800 leading-none">
                            12
                          </span>
                        </div>
                        <div>
                          <p className="font-medium text-gray-800 text-xs">
                            Junta Anual de Accionistas
                          </p>
                          <p className="text-[10px] text-gray-500">
                            Confirmado
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* PESTAÑA: FINANZAS */}
            {activeSidebarTab === "Finanzas" && (
              <div>
                <div className="flex border-b border-gray-200 mb-5 space-x-6 px-2">
                  {contentTabs.map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveContentTab(tab)}
                      className={`pb-2.5 text-sm transition-colors relative ${
                        activeContentTab === tab
                          ? "text-orange-500 font-semibold cursor-default"
                          : "text-gray-500 hover:text-gray-800 font-medium cursor-pointer"
                      }`}
                    >
                      {tab}
                      {activeContentTab === tab && (
                        <span className="absolute -bottom-px left-0 w-full h-0.5 bg-orange-500"></span>
                      )}
                    </button>
                  ))}
                </div>
                {activeContentTab === "Ratios" && period === "annual" && (
                  <FinancialHealthPanel
                    ticker={currentTicker}
                    onOpenInfo={openGlossary}
                  />
                )}

                <div className="bg-white rounded-lg border border-gray-200 shadow-sm min-h-100 flex flex-col overflow-hidden">
                  <div className="flex justify-between items-center px-4 py-3 border-b border-gray-200 bg-gray-50">
                    <div className="flex space-x-2">
                      <div className="flex border border-gray-300 rounded overflow-hidden">
                        <button
                          onClick={() => handlePeriodChange("annual")}
                          className={`text-xs px-3 py-1 font-medium transition-colors ${period === "annual" ? "bg-orange-500 text-white cursor-default" : "bg-white text-gray-600 hover:bg-gray-50 cursor-pointer"}`}
                        >
                          Anual
                        </button>
                        <button
                          onClick={() => handlePeriodChange("quarterly")}
                          className={`text-xs px-3 py-1 font-medium transition-colors border-l border-gray-300 ${period === "quarterly" ? "bg-orange-500 text-white cursor-default" : "bg-white text-gray-600 hover:bg-gray-50 cursor-pointer"}`}
                        >
                          Trimestral
                        </button>
                      </div>
                    </div>
                    <div className="flex space-x-2 text-gray-400 text-xs italic items-center px-2">
                      Cifras en millones (salvo métricas por acción)
                    </div>
                    <div className="flex space-x-2">
                      <button className="p-1.5 text-gray-500 hover:text-gray-900 border border-gray-300 rounded bg-white cursor-pointer">
                        <Maximize2 className="w-3.5 h-3.5" />
                      </button>
                      <button className="flex items-center text-xs px-2 py-1 border border-gray-300 rounded bg-white text-gray-700 hover:bg-gray-50 cursor-pointer">
                        <Download className="w-3.5 h-3.5 mr-1.5" /> Exportar
                      </button>
                    </div>
                  </div>

                  <div className="flex-1 flex flex-col">
                    {isLoading ? (
                      <div className="flex-1 flex flex-col items-center justify-center text-orange-500 py-20">
                        <Loader2 className="w-10 h-10 mb-3 animate-spin" />
                        <p className="text-sm font-medium">
                          Extrayendo datos contables...
                        </p>
                      </div>
                    ) : error ? (
                      <div className="flex-1 flex flex-col items-center justify-center text-red-500 py-20">
                        <p className="text-sm font-bold">Error: {error}</p>
                      </div>
                    ) : currentTabData.length > 0 ? (
                      <div className="w-full overflow-x-auto">
                        <table className="w-full text-[13px] text-left whitespace-nowrap">
                          <thead>
                            <tr className="bg-[#333333] text-white">
                              <th className="py-2.5 px-4 font-bold sticky left-0 bg-[#333333] z-10 w-72">
                                {activeContentTab} | Vektor
                              </th>
                              {availableYears.map((year) => (
                                <th
                                  key={year}
                                  className="py-2.5 px-4 font-bold text-right"
                                >
                                  {year}
                                </th>
                              ))}
                            </tr>
                          </thead>

                          <tbody>
                            {currentTabData.map((row, idx) => {
                              if (row.is_header) {
                                return (
                                  <tr
                                    key={idx}
                                    className="border-b border-gray-100 bg-gray-50/80"
                                  >
                                    <td
                                      colSpan={availableYears.length + 1}
                                      className="py-3 px-4 font-bold text-gray-900 sticky left-0 shadow-[1px_0_0_0_#f3f4f6]"
                                    >
                                      {row.Métrica}
                                    </td>
                                  </tr>
                                );
                              }

                              const isMainMetric =
                                row.Métrica.toLowerCase().includes("total") ||
                                row.Métrica.toLowerCase().includes(
                                  "beneficio bruto",
                                ) ||
                                row.Métrica.toLowerCase().includes(
                                  "beneficio operativo",
                                ) ||
                                row.Métrica.toLowerCase().includes(
                                  "beneficio neto",
                                );

                              const glossaryEntry = getGlossaryEntry(
                                row.Métrica,
                              );
                              const latestYear =
                                availableYears[availableYears.length - 1];
                              const latestFormatted = latestYear
                                ? formatNumber(row[latestYear], row.is_pct)
                                : null;

                              return (
                                <tr
                                  key={idx}
                                  className={`border-b border-gray-100 hover:bg-gray-50 transition-colors group`}
                                >
                                  <td
                                    className={`
                                    py-2.5 px-4 sticky left-0 bg-white group-hover:bg-gray-50 z-10 shadow-[1px_0_0_0_#f3f4f6]
                                    ${row.is_sub ? "pl-8 text-gray-600 italic" : ""}
                                    ${isMainMetric && !row.is_sub ? "font-bold text-gray-900" : "text-gray-700"}
                                  `}
                                  >
                                    <div className="flex items-center justify-between gap-1.5">
                                      <span className="truncate">
                                        {row.Métrica}
                                      </span>
                                      {glossaryEntry && (
                                        <button
                                          type="button"
                                          onClick={() =>
                                            openGlossary(
                                              row.Métrica,
                                              latestFormatted,
                                            )
                                          }
                                          title="Ver explicación y rangos de referencia"
                                          className="text-gray-400 hover:text-orange-500 transition-colors cursor-pointer shrink-0"
                                        >
                                          <Info className="w-3.5 h-3.5" />
                                        </button>
                                      )}
                                    </div>
                                  </td>

                                  {availableYears.map((year) => {
                                    const value = row[year];
                                    const isNegative =
                                      typeof value === "number" && value < 0;

                                    return (
                                      <td
                                        key={year}
                                        className={`
                                          py-2.5 px-4 text-right
                                          ${isNegative ? "text-[#d93025]" : "text-gray-800"}
                                          ${isMainMetric && !row.is_sub ? "font-bold" : ""}
                                          ${row.is_sub ? "italic" : ""}
                                        `}
                                      >
                                        {formatNumber(value, row.is_pct)}
                                      </td>
                                    );
                                  })}
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : financialData.length > 0 ? (
                      <div className="flex-1 flex flex-col items-center justify-center text-gray-400 py-20">
                        <PieChart className="w-10 h-10 mb-3 text-gray-300" />
                        <p className="text-sm font-medium text-gray-500">
                          No hay datos disponibles para la pestaña de{" "}
                          <span className="text-orange-500">
                            {activeContentTab}
                          </span>
                          .
                        </p>
                      </div>
                    ) : (
                      <div className="flex-1 flex flex-col items-center justify-center text-gray-400 py-20">
                        <BarChart3 className="w-12 h-12 mb-3 text-gray-200" />
                        <p className="text-sm font-medium text-gray-500">
                          Buscá un Ticker en la cabecera (ej: AAPL) para cargar
                          la{" "}
                          <span className="text-orange-500">
                            {activeContentTab}
                          </span>
                          .
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* PESTAÑA: VALORACIÓN */}
            {activeSidebarTab === "Valoracion" && (
              <ValuationTab ticker={currentTicker} onOpenInfo={openGlossary} />
            )}

            {/* PESTAÑA: COMPARADOR MANUAL (HASTA 5 EMPRESAS) */}
            {activeSidebarTab === "Comparador" && (
              <ComparatorTab
                currentTicker={currentTicker}
                onOpenInfo={openGlossary}
              />
            )}

            {/* PESTAÑA: SCREENER FUNDAMENTAL */}
            {activeSidebarTab === "Screener" && (
              <ScreenerTab
                key={screenerPresetId}
                initialPresetId={screenerPresetId}
                onSelectCompany={(sym) => executeSearch(sym, period, true)}
              />
            )}
          </div>
        </div>

        {/* MODAL AGREGAR AL TABLERO DESDE CABECERA DE EMPRESA */}
        {showAddToBoardModal && (
          <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl border border-gray-200 shadow-2xl w-full max-w-lg overflow-hidden text-xs">
              <div className="px-5 py-3.5 bg-[#252526] text-white flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-bold">
                    Agregar{" "}
                    <span className="text-orange-400">{currentTicker}</span> a
                    Watchlist
                  </h4>
                  <p className="text-[11px] text-gray-400">
                    Elegí la watchlist y definí objetivos o alertas opcionales
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowAddToBoardModal(false)}
                  className="text-gray-400 hover:text-white cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form
                onSubmit={handleConfirmAddToBoard}
                className="p-5 space-y-4"
              >
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Watchlist destino ({watchlistData?.count || 1}/
                    {watchlistData?.max_watchlists || 10} listas creadas)
                  </label>
                  <select
                    value={modalTargetWlId}
                    onChange={(e) => handleModalWatchlistSelect(e.target.value)}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-900 font-medium focus:outline-none focus:border-orange-500"
                  >
                    {(watchlistData?.watchlists || []).map((wl) => (
                      <option key={wl.id} value={wl.id}>
                        {wl.name} ({wl.item_count} empresas)
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-gray-700 mb-1">
                      Obj. Compra (≤ US$)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      value={modalBuyTarget}
                      onChange={(e) => setModalBuyTarget(e.target.value)}
                      placeholder="Opcional"
                      className="w-full px-3 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-900"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold text-gray-700 mb-1">
                      Obj. Venta (≥ US$)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      value={modalSellTarget}
                      onChange={(e) => setModalSellTarget(e.target.value)}
                      placeholder="Opcional"
                      className="w-full px-3 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-900"
                    />
                  </div>
                </div>

                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Nota de tesis
                  </label>
                  <input
                    type="text"
                    value={modalThesis}
                    onChange={(e) => setModalThesis(e.target.value)}
                    placeholder="Catalizadores, múltiplos objetivo..."
                    className="w-full px-3 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-900"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-semibold text-gray-700">
                      Alertas por indicador ({modalAlerts.length})
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        setModalAlerts((prev) => [
                          ...prev,
                          { metric: "pe_ltm", op: "<=", value: "" },
                        ])
                      }
                      className="text-[11px] text-orange-600 font-semibold hover:underline cursor-pointer"
                    >
                      + Agregar regla
                    </button>
                  </div>
                  {modalAlerts.map((rule, idx) => (
                    <div key={idx} className="flex items-center gap-2 mb-1.5">
                      <select
                        value={rule.metric}
                        onChange={(e) =>
                          setModalAlerts((prev) =>
                            prev.map((r, i) =>
                              i === idx ? { ...r, metric: e.target.value } : r,
                            ),
                          )
                        }
                        className="flex-1 px-2 py-1 border border-gray-300 rounded bg-gray-50 text-gray-800"
                      >
                        {ALERTABLE_METRICS.map((m) => (
                          <option key={m.key} value={m.key}>
                            {m.label}
                          </option>
                        ))}
                      </select>
                      <select
                        value={rule.op}
                        onChange={(e) =>
                          setModalAlerts((prev) =>
                            prev.map((r, i) =>
                              i === idx ? { ...r, op: e.target.value } : r,
                            ),
                          )
                        }
                        className="w-16 px-1.5 py-1 border border-gray-300 rounded bg-gray-50 text-gray-800 font-bold"
                      >
                        <option value="<=">≤</option>
                        <option value=">=">≥</option>
                      </select>
                      <input
                        type="number"
                        step="0.01"
                        value={rule.value}
                        onChange={(e) =>
                          setModalAlerts((prev) =>
                            prev.map((r, i) =>
                              i === idx ? { ...r, value: e.target.value } : r,
                            ),
                          )
                        }
                        placeholder="Valor"
                        className="w-24 px-2 py-1 border border-gray-300 rounded bg-gray-50 text-gray-900"
                      />
                    </div>
                  ))}
                </div>

                <div className="pt-3 border-t border-gray-200 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setShowAddToBoardModal(false)}
                    className="px-3 py-1.5 rounded border border-gray-300 text-gray-700 hover:bg-gray-50 cursor-pointer"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={savingToBoard}
                    className="px-4 py-1.5 rounded bg-orange-500 text-white font-semibold hover:bg-orange-600 cursor-pointer disabled:opacity-50"
                  >
                    {savingToBoard ? "Guardando..." : "Guardar en Watchlist"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        <MetricInfoDrawer
          entry={activeGlossaryInfo?.entry}
          currentValue={activeGlossaryInfo?.currentValue}
          onClose={() => setActiveGlossaryInfo(null)}
        />
      </main>
    </div>
  );
}

export default App;
