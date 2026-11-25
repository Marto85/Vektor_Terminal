import { Suspense, lazy, useEffect, useRef, useState } from "react";
import {
  Home,
  Briefcase,
  Bookmark,
  FileText,
  FileSpreadsheet,
  BarChart3,
  PieChart,
  Scale,
  Filter,
  Search,
  Bell,
  Download,
  Calculator,
  Globe,
  Presentation,
  Users,
  Maximize2,
  Loader2,
  ExternalLink,
  ChevronUp,
  ChevronDown,
  Info,
  X,
  Check,
  CheckCheck,
  KeyRound,
  LogOut,
  Shield,
  Menu,
  MoreHorizontal,
  Heart,
} from "lucide-react";
import apiClient from "./api/client";
import { useAuth } from "./context/authStore";
import LoginScreen from "./components/auth/LoginScreen";
import BrandLogo from "./components/BrandLogo";
import HomeOverview from "./components/HomeOverview";
import { ALERTABLE_METRICS } from "./data/watchlistConstants";
import StockChart from "./components/StockChart";
import CapitalStructurePanel from "./components/CapitalStructurePanel";
import FinancialHealthPanel from "./components/FinancialHealthPanel";
import FinancialsQuickCards from "./components/FinancialsQuickCards";
import MetricInfoDrawer from "./components/MetricInfoDrawer";
import { getGlossaryEntry } from "./data/metricsGlossary";

const ChangePasswordModal = lazy(() => import("./components/auth/ChangePasswordModal"));
const UserManagementModal = lazy(() => import("./components/auth/UserManagementModal"));
const WatchlistTab = lazy(() => import("./components/WatchlistTab"));
const ValuationTab = lazy(() => import("./components/ValuationTab"));
const ComparatorTab = lazy(() => import("./components/ComparatorTab"));
const ScreenerTab = lazy(() => import("./components/ScreenerTab"));
const ValuationModelsTab = lazy(() => import("./components/ValuationModelsTab"));
const MacroLabTab = lazy(() => import("./components/MacroLabTab"));
const InvestmentThesisTab = lazy(() => import("./components/InvestmentThesisTab"));
const OwnershipInsidersTab = lazy(() => import("./components/OwnershipInsidersTab"));
const PortfoliosCRMTab = lazy(() => import("./components/PortfoliosCRMTab"));

const RECENT_STORAGE_KEY = "tf_recent_tickers_v1";

const ROLE_BADGE_MAP = {
  superadmin: { label: "Superadmin", cls: "bg-purple-500/20 text-purple-300 border-purple-500/40" },
  advisor: { label: "Asesor", cls: "bg-orange-500/20 text-orange-300 border-orange-500/40" },
  client: { label: "Cliente", cls: "bg-blue-500/20 text-blue-300 border-blue-500/40" },
};

function TabFallback() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-gray-500">
      <Loader2 className="w-7 h-7 text-orange-500 animate-spin mb-2" />
      <p className="text-xs font-medium">Cargando módulo...</p>
    </div>
  );
}

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
  const {
    user,
    loadingAuth,
    isAuthenticated,
    logout,
    isAdvisorOrAdmin,
    isClient,
  } = useAuth();

  const [activeSidebarTab, setActiveSidebarTab] = useState("Inicio");
  const [tableroInitialSubView, setTableroInitialSubView] = useState("lists");
  const [activeContentTab, setActiveContentTab] = useState(
    "Cuenta de Resultados",
  );
  const [period, setPeriod] = useState("annual");
  const [showChart, setShowChart] = useState(true);
  const [activeGlossaryInfo, setActiveGlossaryInfo] = useState(null);
  const [screenerPresetId, setScreenerPresetId] = useState("all");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const [tickerInput, setTickerInput] = useState("");
  const [currentTicker, setCurrentTicker] = useState("MSFT");
  const [hasLoadedCompany, setHasLoadedCompany] = useState(false);
  const [financialData, setFinancialData] = useState([]);
  const [statementsCurrency, setStatementsCurrency] = useState("USD");

  const [profileData, setProfileData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [exportingFormat, setExportingFormat] = useState(null);
  const [error, setError] = useState(null);
  const [recentTickers, setRecentTickers] = useState(loadRecentTickers);

  const [searchResults, setSearchResults] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const mainScrollRef = useRef(null);
  const companyReqIdRef = useRef(0);
  const searchDebounceRef = useRef(null);

  // Estado Multi-Watchlist y Notificaciones (aislado por usuario)
  const [watchlistData, setWatchlistData] = useState(null);
  const [showAlertsPopover, setShowAlertsPopover] = useState(false);
  const alertsPopoverRef = useRef(null);

  // Menú de usuario y modales de autenticación/administración
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showUserMgmtModal, setShowUserMgmtModal] = useState(false);
  const [showChangePassModal, setShowChangePassModal] = useState(false);
  const userMenuRef = useRef(null);

  // Modal rápido "Agregar a lista" desde la cabecera de empresa
  const [showAddToBoardModal, setShowAddToBoardModal] = useState(false);
  const [modalTargetWlId, setModalTargetWlId] = useState("");
  const [modalBuyTarget, setModalBuyTarget] = useState("");
  const [modalSellTarget, setModalSellTarget] = useState("");
  const [modalThesis, setModalThesis] = useState("");
  const [modalAlerts, setModalAlerts] = useState([]);
  const [savingToBoard, setSavingToBoard] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;
    apiClient
      .get("/watchlists")
      .then((res) => {
        if (!cancelled) {
          setWatchlistData((prev) => prev || res.data);
        }
      })
      .catch((err) => console.error("Error cargando listas de seguimiento:", err));
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, user?.id]);

  useEffect(() => {
    const handleOutside = (e) => {
      if (
        alertsPopoverRef.current &&
        !alertsPopoverRef.current.contains(e.target)
      ) {
        setShowAlertsPopover(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setShowUserMenu(false);
      }
    };
    if (showAlertsPopover || showUserMenu) {
      document.addEventListener("mousedown", handleOutside);
    }
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [showAlertsPopover, showUserMenu]);

  useEffect(() => {
    return () => {
      if (searchDebounceRef.current) {
        clearTimeout(searchDebounceRef.current);
      }
    };
  }, []);

  if (loadingAuth) {
    return (
      <div className="min-h-screen bg-[#1e1e1e] flex flex-col items-center justify-center text-gray-300">
        <Loader2 className="w-8 h-8 text-orange-500 animate-spin mb-3" />
        <p className="text-xs font-medium tracking-wide">
          Verificando sesión en VektorTerminal...
        </p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  const openGlossary = (metricKey, formattedVal = null) => {
    const entry = getGlossaryEntry(metricKey);
    if (entry) {
      setActiveGlossaryInfo({ entry, currentValue: formattedVal });
    }
  };

  const globalNavItems = [
    { id: "Inicio", name: "Inicio y Mercado", icon: Home },
    {
      id: "Carteras",
      name: isClient ? "Mi Cartera" : "Carteras y Clientes",
      icon: Briefcase,
    },
    {
      id: "Tablero",
      name: "Listas de Seguimiento",
      icon: Bookmark,
    },
    { id: "Screener", name: "Screener", icon: Filter },
    { id: "Comparador", name: "Comparador", icon: Scale },
    { id: "Modelos", name: "Modelos de Valuación", icon: Calculator },
    { id: "MacroLab", name: "Macro Lab", icon: Globe },
    { id: "Tesis", name: "Tesis de Inversión", icon: Presentation },
  ];

  const companyNavItems = [
    { id: "Resumen", name: "Resumen y noticias", icon: FileText },
    { id: "Finanzas", name: "Finanzas", icon: BarChart3 },
    { id: "Valoracion", name: "Valoración", icon: PieChart },
    { id: "Propiedad", name: "Propiedad e Insiders", icon: Users },
  ];

  const contentTabs = [
    "Cuenta de Resultados",
    "Balance de Situación",
    "Estado de Flujo de Efectivo",
    "Ratios",
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
    const reqId = ++companyReqIdRef.current;

    if (upperTicker !== currentTicker) {
      setCurrentTicker(upperTicker);
      setProfileData(null);
      setFinancialData([]);
    }
    setIsLoading(true);
    setError(null);
    setMobileMenuOpen(false);

    if (switchToSummary) {
      setActiveSidebarTab("Resumen");
    }
    mainScrollRef.current?.scrollTo({ top: 0, behavior: "smooth" });

    try {
      const [finResponse, profResponse] = await Promise.all([
        apiClient.get(`/company/${upperTicker}/financials/${selectedPeriod}`),
        apiClient.get(`/company/${upperTicker}/profile`),
      ]);

      if (reqId !== companyReqIdRef.current) return;

      setFinancialData(finResponse.data);
      const headerCurr =
        finResponse.headers?.["x-reporting-currency"] ||
        profResponse.data?.reporting_currency ||
        "USD";
      setStatementsCurrency(String(headerCurr).toUpperCase());
      setProfileData(profResponse.data);
      setCurrentTicker(upperTicker);
      setHasLoadedCompany(true);
      saveToRecent(upperTicker, profResponse.data);
    } catch (err) {
      if (reqId !== companyReqIdRef.current) return;
      console.error("Error al buscar datos:", err);
      setError(
        err.response?.data?.detail || "Error de conexión con el servidor",
      );
    } finally {
      if (reqId === companyReqIdRef.current) {
        setIsLoading(false);
      }
    }
  };

  const handleExportCompany = async (format) => {
    if (!currentTicker || exportingFormat) return;
    setExportingFormat(format);
    try {
      const url =
        format === "xlsx"
          ? `/company/${currentTicker}/export/xlsx?period=${period}`
          : `/company/${currentTicker}/export/pdf`;

      const response = await apiClient.get(url, { responseType: "blob" });
      const blobUrl = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = blobUrl;
      link.setAttribute(
        "download",
        format === "xlsx"
          ? `${currentTicker}_VektorTerminal_${period}.xlsx`
          : `${currentTicker}_Informe_Ejecutivo.pdf`,
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error(`Error exportando ${format.toUpperCase()}:`, err);
      setError(
        err?.response?.data?.detail ||
          `No se pudo exportar el archivo ${format.toUpperCase()}. Intentá nuevamente.`
      );
    } finally {
      setExportingFormat(null);
    }
  };

  const handleOpenCompanyTab = (tabId) => {
    setActiveSidebarTab(tabId);
    setMobileMenuOpen(false);
    if (!hasLoadedCompany) {
      executeSearch(currentTicker, period, false);
    }
  };

  const handleOpenScreenerWithPreset = (presetId = "all") => {
    setScreenerPresetId(presetId);
    setActiveSidebarTab("Screener");
    setMobileMenuOpen(false);
  };

  const handleOpenTablero = (sub = "lists") => {
    setTableroInitialSubView(sub);
    setActiveSidebarTab("Tablero");
    setMobileMenuOpen(false);
  };

  const handleMarkNotifRead = async (notifId) => {
    try {
      const res = await apiClient.post(`/notifications/${notifId}/read`);
      setWatchlistData(res.data);
    } catch (err) {
      console.error("Error marcando notificación como leída:", err);
    }
  };

  const handleMarkAllNotifsRead = async () => {
    try {
      const res = await apiClient.post("/notifications/read-all");
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

  const handleSearchChange = (e) => {
    const value = e.target.value;
    setTickerInput(value);

    if (searchDebounceRef.current) {
      clearTimeout(searchDebounceRef.current);
    }

    const trimmed = value.trim();
    if (!trimmed) {
      setSearchResults([]);
      setShowDropdown(false);
      return;
    }

    searchDebounceRef.current = setTimeout(async () => {
      try {
        const response = await apiClient.get(
          `/search?q=${encodeURIComponent(trimmed)}`,
          { timeout: 10000 },
        );
        const upperQ = trimmed.toUpperCase();
        const rawList = Array.isArray(response.data) ? response.data : [];
        const sorted = [...rawList].sort((a, b) => {
          const aExact = String(a.ticker || "").toUpperCase() === upperQ ? 1 : 0;
          const bExact = String(b.ticker || "").toUpperCase() === upperQ ? 1 : 0;
          if (aExact !== bExact) return bExact - aExact;
          const aEq = String(a.type || "").toUpperCase() === "EQUITY" ? 1 : 0;
          const bEq = String(b.type || "").toUpperCase() === "EQUITY" ? 1 : 0;
          return bEq - aEq;
        });
        setSearchResults(sorted);
        setShowDropdown(true);
      } catch (err) {
        console.error("Error buscando tickers", err);
      }
    }, 250);
  };

  const handleSelectTicker = (selectedTicker) => {
    if (searchDebounceRef.current) {
      clearTimeout(searchDebounceRef.current);
    }
    setTickerInput(selectedTicker);
    setShowDropdown(false);
    setSearchResults([]);
    const shouldSwitch =
      activeSidebarTab === "Inicio" ||
      activeSidebarTab === "Carteras" ||
      activeSidebarTab === "Tablero" ||
      activeSidebarTab === "Screener" ||
      activeSidebarTab === "Modelos" ||
      activeSidebarTab === "MacroLab" ||
      activeSidebarTab === "Tesis" ||
      activeSidebarTab === "Comparador";
    executeSearch(selectedTicker, period, shouldSwitch);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      if (searchDebounceRef.current) {
        clearTimeout(searchDebounceRef.current);
      }
      setShowDropdown(false);
      const shouldSwitch =
        activeSidebarTab === "Inicio" ||
        activeSidebarTab === "Carteras" ||
        activeSidebarTab === "Tablero" ||
        activeSidebarTab === "Screener" ||
        activeSidebarTab === "Modelos" ||
        activeSidebarTab === "MacroLab" ||
        activeSidebarTab === "Tesis" ||
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
      const res = await apiClient.post(`/watchlists/${modalTargetWlId}/items`, {
        ticker: currentTicker,
        buy_target_price:
          modalBuyTarget !== "" ? Number(modalBuyTarget) : null,
        sell_target_price:
          modalSellTarget !== "" ? Number(modalSellTarget) : null,
        thesis_note: modalThesis,
        alerts: parsedAlerts,
      });
      setWatchlistData(res.data);
      setShowAddToBoardModal(false);
    } catch (err) {
      console.error("Error guardando en lista de seguimiento:", err);
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
  const reportingCurrency =
    profileData?.reporting_currency || statementsCurrency || "USD";
  const isFinancialSector = Boolean(
    profileData?.summary_metrics &&
      profileData.summary_metrics.efficiency?.gross_margin_pct === null &&
      profileData.summary_metrics.efficiency?.roic_pct === null,
  );
  const isCompanyContextTab =
    activeSidebarTab === "Resumen" ||
    activeSidebarTab === "Finanzas" ||
    activeSidebarTab === "Valoracion" ||
    activeSidebarTab === "Propiedad";

  const notificationsList = watchlistData?.notifications || [];
  const unreadNotifications = notificationsList.filter((n) => !n.is_read);
  const unreadNotifCount = unreadNotifications.length;
  const isCurrentTickerInAnyWatchlist = (watchlistData?.watchlists || []).some(
    (wl) => (wl.items || []).some((it) => it.ticker === currentTicker),
  );

  const roleBadge = ROLE_BADGE_MAP[user?.role] || ROLE_BADGE_MAP.client;
  const userInitial = (user?.full_name || user?.email || "U")
    .charAt(0)
    .toUpperCase();

  const renderSidebarNavigation = () => (
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
                    setMobileMenuOpen(false);
                  }
                }}
                className={`w-full flex items-center justify-between px-3 py-2 md:py-1.5 text-xs rounded transition-colors ${
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
                className={`w-full flex items-center px-3 py-2 md:py-1.5 text-xs rounded transition-colors ${
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

      {/* Administración / Cartera (solo asesor/admin) */}
      {isAdvisorOrAdmin && (
        <div>
          <div className="px-3 mb-2">
            <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">
              Gestión & Accesos
            </p>
          </div>
          <nav className="space-y-0.5 px-2">
            <button
              type="button"
              onClick={() => {
                setMobileMenuOpen(false);
                setShowUserMgmtModal(true);
              }}
              className="w-full flex items-center px-3 py-2 md:py-1.5 text-xs rounded text-gray-400 hover:bg-gray-800 hover:text-gray-200 transition-colors cursor-pointer"
            >
              <Users className="w-3.5 h-3.5 mr-2" />
              {user?.role === "superadmin"
                ? "Usuarios y Roles"
                : "Mis Clientes"}
            </button>
          </nav>
        </div>
      )}
    </div>
  );

  return (
    <div className="fixed inset-0 md:static md:h-dvh flex bg-[#1e1e1e] font-sans text-gray-200 overflow-hidden overscroll-none">
      {/* SIDEBAR ESCRITORIO (oculto en mobile < 768px) */}
      <aside className="hidden md:flex w-56 bg-[#252526] border-r border-gray-700 flex-col shrink-0">
        <button
          type="button"
          onClick={() => setActiveSidebarTab("Inicio")}
          title="Volver a Inicio y Mercado"
          className="h-12 flex items-center px-4 border-b border-gray-700 bg-[#1e1e1e] hover:bg-[#232325] transition-colors cursor-pointer text-left"
        >
          <BrandLogo size="md" />
        </button>

        {renderSidebarNavigation()}
      </aside>

      {/* DRAWER NAVEGACIÓN MOBILE (< 768px) */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-[1px]"
            onClick={() => setMobileMenuOpen(false)}
          />
          <aside className="relative w-72 max-w-[82vw] bg-[#252526] border-r border-gray-700 flex flex-col h-full z-10 shadow-2xl">
            <div className="h-12 flex items-center justify-between px-4 border-b border-gray-700 bg-[#1e1e1e]">
              <button
                type="button"
                onClick={() => {
                  setActiveSidebarTab("Inicio");
                  setMobileMenuOpen(false);
                }}
                className="cursor-pointer text-left"
              >
                <BrandLogo size="md" />
              </button>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                aria-label="Cerrar menú"
                className="p-1.5 text-gray-400 hover:text-white rounded-lg cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            {renderSidebarNavigation()}
          </aside>
        </div>
      )}

      {/* CONTENIDO PRINCIPAL */}
      <main className="flex-1 flex flex-col min-w-0 bg-[#f9fafb]">
        {/* HEADER RESPONSIVE CON MENÚ MOBILE, AUTOCOMPLETADO, NOTIFICACIONES Y USUARIO */}
        <header className="h-12 bg-[#252526] border-b border-gray-700 flex items-center justify-between px-2.5 sm:px-4 gap-2 shrink-0 z-40">
          <button
            type="button"
            onClick={() => setMobileMenuOpen(true)}
            aria-label="Abrir navegación"
            className="md:hidden p-1.5 rounded-lg text-gray-300 hover:text-white hover:bg-[#333333] cursor-pointer shrink-0"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div className="flex items-center flex-1 max-w-xl min-w-0">
            <div className="relative w-full">
              <Search className="w-3.5 h-3.5 absolute left-2.5 sm:left-3 top-1/2 transform -translate-y-1/2 text-gray-500" />
              <input
                type="text"
                value={tickerInput}
                onChange={handleSearchChange}
                onKeyDown={handleKeyDown}
                onFocus={() => {
                  if (searchResults.length > 0) setShowDropdown(true);
                }}
                onBlur={() => setShowDropdown(false)}
                placeholder="Buscar ticker (Ej: AAPL, MSFT, MELI)..."
                className="w-full pl-8 sm:pl-9 pr-3 sm:pr-12 py-1.5 sm:py-1 bg-[#333333] border border-gray-600 rounded text-xs text-white placeholder-gray-400 focus:outline-none focus:border-orange-500 focus:bg-[#1e1e1e]"
              />
              <div className="hidden sm:block absolute right-2 top-1/2 transform -translate-y-1/2 text-[10px] text-gray-500 bg-[#252526] px-1 rounded border border-gray-600">
                Enter
              </div>

              {showDropdown && searchResults.length > 0 && (
                <div className="absolute top-full left-0 w-full mt-1 bg-[#252526] border border-gray-600 rounded shadow-lg overflow-hidden z-50">
                  {searchResults.map((res, idx) => (
                    <div
                      key={idx}
                      className="px-3 sm:px-4 py-2.5 sm:py-2 hover:bg-[#333333] cursor-pointer flex justify-between items-center border-b border-gray-700/50 last:border-0"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => handleSelectTicker(res.ticker)}
                    >
                      <div className="flex items-center truncate mr-2">
                        <span className="font-bold text-orange-500 mr-2.5 sm:mr-3 w-12 shrink-0">
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

          <div className="flex items-center space-x-1.5 sm:space-x-3 text-gray-400 shrink-0">
            {/* Campana de notificaciones persistentes (aisladas por usuario) */}
            <div className="relative" ref={alertsPopoverRef}>
              <button
                type="button"
                onClick={() => setShowAlertsPopover((prev) => !prev)}
                title="Notificaciones y Alertas"
                className="relative p-1.5 hover:text-white cursor-pointer"
              >
                <Bell className="w-4 h-4" />
                {unreadNotifCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full bg-orange-500 text-white text-[10px] font-bold flex items-center justify-center">
                    {unreadNotifCount}
                  </span>
                )}
              </button>

              {showAlertsPopover && (
                <div className="fixed sm:absolute left-2 right-2 sm:left-auto sm:right-0 mt-2 sm:w-96 bg-white border border-gray-200 rounded-xl shadow-2xl z-50 overflow-hidden text-xs">
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
                            <p className="text-gray-700 mt-0.5 wrap-break-word">{n.detail}</p>
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

            {/* Badge de Rol + Menú de Cuenta */}
            <div className="relative" ref={userMenuRef}>
              <button
                type="button"
                onClick={() => setShowUserMenu((prev) => !prev)}
                className="flex items-center gap-2 pl-1.5 sm:pl-2 pr-1 py-1 rounded-lg hover:bg-[#333333] transition-colors cursor-pointer"
              >
                <span
                  className={`hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold border ${roleBadge.cls}`}
                >
                  <Shield className="w-2.5 h-2.5" />
                  {roleBadge.label}
                </span>
                <div className="w-6 h-6 rounded-full bg-orange-600 flex items-center justify-center text-white text-xs font-bold">
                  {userInitial}
                </div>
              </button>

              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-60 bg-white border border-gray-200 rounded-xl shadow-2xl z-50 overflow-hidden text-xs text-gray-800">
                  <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                    <p className="font-bold text-gray-900 truncate">
                      {user?.full_name}
                    </p>
                    <p className="text-[11px] text-gray-500 truncate">
                      {user?.email}
                    </p>
                    <span className="inline-block mt-1 px-2 py-0.5 rounded bg-gray-200 text-gray-700 text-[10px] font-semibold uppercase">
                      {roleBadge.label}
                    </span>
                  </div>

                  <div className="py-1">
                    {isAdvisorOrAdmin && (
                      <button
                        type="button"
                        onClick={() => {
                          setShowUserMenu(false);
                          setShowUserMgmtModal(true);
                        }}
                        className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-2 text-gray-700 cursor-pointer"
                      >
                        <Users className="w-3.5 h-3.5 text-orange-500" />
                        {user?.role === "superadmin"
                          ? "Administrar usuarios y roles"
                          : "Ver mis clientes"}
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={() => {
                        setShowUserMenu(false);
                        setShowChangePassModal(true);
                      }}
                      className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-2 text-gray-700 cursor-pointer"
                    >
                      <KeyRound className="w-3.5 h-3.5 text-gray-500" />
                      Cambiar contraseña
                    </button>

                    <div className="my-1 border-t border-gray-100" />

                    <button
                      type="button"
                      onClick={() => {
                        setShowUserMenu(false);
                        setWatchlistData(null);
                        logout();
                      }}
                      className="w-full px-4 py-2 text-left hover:bg-red-50 flex items-center gap-2 text-red-600 font-medium cursor-pointer"
                    >
                      <LogOut className="w-3.5 h-3.5" />
                      Cerrar sesión
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* CABECERA EMPRESA GLOBAL (Adaptativa en Mobile y Desktop) */}
        {isCompanyContextTab && (
          <div className="bg-white border-b border-gray-200 shrink-0">
            <div className="max-w-7xl mx-auto px-3 sm:px-6 py-3 sm:py-4">
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-3">
                <div className="flex items-start space-x-3 sm:space-x-4 min-w-0">
                  <div className="w-10 h-10 sm:w-12 sm:h-12 bg-[#dc2626] rounded flex items-center justify-center text-white text-2xl sm:text-3xl font-bold shrink-0 shadow-sm">
                    {currentTicker.charAt(0)}
                  </div>

                  <div className="flex flex-col min-w-0">
                    <div className="flex items-baseline justify-between sm:block gap-2">
                      <h1 className="text-2xl sm:text-[32px] font-bold text-gray-900 leading-none tracking-tight">
                        {currentTicker}
                      </h1>
                      <div className="sm:hidden text-right">
                        <span className="text-lg font-bold text-gray-900">
                          {profileData ? `US$ ${formatNumber(profileData.price)}` : "Cargando..."}
                        </span>
                        {profileData && (
                          <span
                            className={`block text-[11px] font-bold ${
                              profileData?.change < 0 ? "text-[#d93025]" : "text-green-600"
                            }`}
                          >
                            {`${profileData.change > 0 ? "+" : profileData.change < 0 ? "-" : ""}${formatNumber(Math.abs(profileData.change_pct), true)}`}
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="text-xs sm:text-[15px] text-gray-500 mt-1 truncate">
                      {profileData ? profileData.name : "Sincronizando empresa..."}
                    </p>
                  </div>
                </div>

                <div className="hidden sm:flex text-right flex-col items-end shrink-0">
                  <h2 className="text-[36px] font-bold text-gray-900 leading-none tracking-tight">
                    {profileData ? `US$ ${formatNumber(profileData.price)}` : "—"}
                  </h2>
                  <p
                    className={`text-[15px] font-bold mt-1 ${profileData?.change < 0 ? "text-[#d93025]" : "text-green-600"}`}
                  >
                    {profileData
                      ? `${profileData.change < 0 ? "-US$ " : profileData.change > 0 ? "+US$ " : "US$ "}${formatNumber(Math.abs(profileData.change))} (${profileData.change > 0 ? "+" : profileData.change < 0 ? "-" : ""}${formatNumber(Math.abs(profileData.change_pct), true)})`
                      : "Actualizando cotización..."}
                  </p>
                  <p className="text-[11px] text-gray-400 mt-1">
                    Datos de mercado actualizados · GMT-3
                  </p>
                </div>
              </div>

              {/* Barra de acciones rápida desplazable en móvil */}
              <div className="flex items-center gap-2 mt-3 overflow-x-auto pb-1">
                <button
                  type="button"
                  onClick={openAddToBoardModal}
                  className={`flex items-center px-2.5 sm:px-3 py-1.5 border rounded text-xs font-medium transition-colors cursor-pointer shadow-sm shrink-0 ${
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
                    ? "En tus listas"
                    : "Agregar a lista"}
                </button>
                <span className="px-2.5 sm:px-3 py-1.5 border border-gray-300 rounded text-xs font-medium text-gray-700 bg-gray-50 shadow-sm shrink-0">
                  Cotización: USD{reportingCurrency !== "USD" ? ` · Balance: ${reportingCurrency}` : ""}
                </span>
                <button
                  onClick={() => setShowChart((prev) => !prev)}
                  className="flex items-center px-2.5 sm:px-3 py-1.5 border border-gray-300 rounded text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer shadow-sm shrink-0"
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
                <button
                  type="button"
                  onClick={() => handleExportCompany("xlsx")}
                  disabled={exportingFormat !== null}
                  title="Descargar libro Excel multi-solapa (.xlsx)"
                  className="flex items-center px-2.5 sm:px-3 py-1.5 border border-emerald-300 bg-emerald-50/70 rounded text-xs font-medium text-emerald-800 hover:bg-emerald-100 transition-colors cursor-pointer shadow-sm disabled:opacity-50 shrink-0"
                >
                  {exportingFormat === "xlsx" ? (
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  ) : (
                    <FileSpreadsheet className="w-3.5 h-3.5 mr-1.5 text-emerald-600" />
                  )}
                  Excel (.xlsx)
                </button>
                <button
                  type="button"
                  onClick={() => handleExportCompany("pdf")}
                  disabled={exportingFormat !== null}
                  title="Descargar informe ejecutivo en PDF"
                  className="flex items-center px-2.5 sm:px-3 py-1.5 border border-slate-300 bg-slate-50 rounded text-xs font-medium text-slate-800 hover:bg-slate-100 transition-colors cursor-pointer shadow-sm disabled:opacity-50 shrink-0"
                >
                  {exportingFormat === "pdf" ? (
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  ) : (
                    <FileText className="w-3.5 h-3.5 mr-1.5 text-slate-600" />
                  )}
                  Informe PDF
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ÁREA DE CONTENIDO CONDICIONAL (con espacio inferior adaptativo en mobile) */}
        <div
          ref={mainScrollRef}
          className="flex-1 overflow-y-auto overscroll-y-contain pb-[calc(3.75rem+env(safe-area-inset-bottom))] md:pb-0"
        >
          <div className="max-w-7xl mx-auto px-3 sm:px-6 py-3 sm:py-6">
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

            {/* VISTA CRM DE CLIENTES Y CARTERAS (PPP + TWR) */}
            {activeSidebarTab === "Carteras" && (
              <Suspense fallback={<TabFallback />}>
                <PortfoliosCRMTab
                  onSelectCompany={(sym) => executeSearch(sym, period, true)}
                />
              </Suspense>
            )}

            {/* VISTA LISTAS DE SEGUIMIENTO Y CENTRO DE NOTIFICACIONES */}
            {activeSidebarTab === "Tablero" && (
              <Suspense fallback={<TabFallback />}>
                <WatchlistTab
                  key={tableroInitialSubView}
                  initialSubView={tableroInitialSubView}
                  watchlistData={watchlistData}
                  onWatchlistUpdated={(updated) => setWatchlistData(updated)}
                  onSelectCompany={(sym) => executeSearch(sym, period, true)}
                />
              </Suspense>
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

            {/* Sub-Nav de Empresa Individual (desplazable en mobile) */}
            {isCompanyContextTab && (
              <div className="flex border-b border-gray-200 mb-5 sm:mb-6 space-x-5 sm:space-x-8 px-1 sm:px-2 overflow-x-auto whitespace-nowrap">
                {companyNavItems.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleOpenCompanyTab(item.id)}
                    className={`pb-2.5 sm:pb-3 text-xs sm:text-[15px] transition-colors relative shrink-0 ${
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
              <div className="space-y-4 sm:space-y-6">
                <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-4 sm:p-5">
                  <h3 className="text-sm font-bold text-gray-900 mb-2">
                    Acerca de la empresa
                  </h3>
                  <p className="text-xs sm:text-sm text-gray-600 leading-relaxed mb-3">
                    {isLoading && !profileData?.description
                      ? "Buscando descripción..."
                      : profileData?.description ||
                        "Perfil corporativo en proceso de sincronización."}
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

                <div className="flex flex-col md:flex-row gap-4 sm:gap-6">
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
                                className="block text-xs sm:text-sm font-medium text-gray-800 hover:text-blue-600 cursor-pointer mt-1 transition-colors"
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
                  <div className="w-full md:w-1/3 bg-white border border-gray-200 rounded-lg shadow-sm">
                    <div className="px-4 py-3 border-b border-gray-200">
                      <span className="text-sm font-bold text-gray-800">
                        Eventos próximos
                      </span>
                    </div>
                    <div className="p-4 space-y-3 text-sm">
                      {profileData?.upcoming_events &&
                      profileData.upcoming_events.length > 0 ? (
                        profileData.upcoming_events.map((ev, i) => (
                          <div
                            key={i}
                            className="flex items-start border-b border-gray-100 pb-2.5 last:border-0 last:pb-0"
                          >
                            <div className="w-10 text-center mr-3 shrink-0 bg-orange-50 border border-orange-200 rounded py-1">
                              <span className="block text-[9px] font-bold text-orange-600 uppercase">
                                {ev.month}
                              </span>
                              <span className="block text-base font-bold text-gray-900 leading-none mt-0.5">
                                {ev.day}
                              </span>
                            </div>
                            <div className="min-w-0">
                              <p className="font-semibold text-gray-800 text-xs">
                                {ev.title}
                              </p>
                              <p className="text-[10px] text-gray-500 mt-0.5">
                                {ev.status}
                              </p>
                            </div>
                          </div>
                        ))
                      ) : (
                        <p className="text-xs text-gray-500">
                          {isLoading
                            ? "Sincronizando calendario corporativo..."
                            : "No hay eventos corporativos próximos programados."}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* PESTAÑA: FINANZAS */}
            {activeSidebarTab === "Finanzas" && (
              <div>
                <div className="flex border-b border-gray-200 mb-5 space-x-4 sm:space-x-6 px-1 sm:px-2 overflow-x-auto whitespace-nowrap">
                  {contentTabs.map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveContentTab(tab)}
                      className={`pb-2.5 text-xs sm:text-sm transition-colors relative shrink-0 ${
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

                {!isLoading && !error && financialData.length > 0 && (
                  <FinancialsQuickCards
                    financialData={financialData}
                    activeContentTab={activeContentTab}
                    period={period}
                    onOpenInfo={openGlossary}
                    reportingCurrency={reportingCurrency}
                    isFinancialSector={isFinancialSector}
                  />
                )}

                {activeContentTab === "Ratios" && period === "annual" && (
                  <FinancialHealthPanel
                    ticker={currentTicker}
                    onOpenInfo={openGlossary}
                  />
                )}

                <div className="bg-white rounded-lg border border-gray-200 shadow-sm min-h-100 flex flex-col overflow-hidden">
                  <div className="flex flex-wrap justify-between items-center gap-2 px-3 sm:px-4 py-2.5 sm:py-3 border-b border-gray-200 bg-gray-50">
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
                    <div className="hidden sm:flex space-x-2 text-gray-400 text-xs italic items-center px-2">
                      Cifras en millones de {reportingCurrency} (salvo métricas por acción)
                    </div>
                    <div className="flex space-x-2">
                      <button className="p-1.5 text-gray-500 hover:text-gray-900 border border-gray-300 rounded bg-white cursor-pointer">
                        <Maximize2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleExportCompany("xlsx")}
                        disabled={exportingFormat !== null}
                        className="flex items-center text-xs px-2 py-1 border border-gray-300 rounded bg-white text-gray-700 hover:bg-gray-50 cursor-pointer disabled:opacity-50"
                      >
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
                        <table className="w-full text-xs sm:text-[13px] text-left whitespace-nowrap">
                          <thead>
                            <tr className="bg-[#333333] text-white">
                              <th className="py-2.5 px-3 sm:px-4 font-bold sticky left-0 bg-[#333333] z-10 w-44 sm:w-72 max-w-44 sm:max-w-none">
                                {activeContentTab} | Vektor
                              </th>
                              {availableYears.map((year) => (
                                <th
                                  key={year}
                                  className="py-2.5 px-3 sm:px-4 font-bold text-right"
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
                                      className="py-2.5 sm:py-3 px-3 sm:px-4 font-bold text-gray-900 sticky left-0 shadow-[1px_0_0_0_#f3f4f6]"
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
                                    py-2 sm:py-2.5 px-3 sm:px-4 sticky left-0 bg-white group-hover:bg-gray-50 z-10 shadow-[1px_0_0_0_#f3f4f6] max-w-44 sm:max-w-none
                                    ${row.is_sub ? "pl-5 sm:pl-8 text-gray-600 italic" : ""}
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
                                          py-2 sm:py-2.5 px-3 sm:px-4 text-right
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
                      <div className="flex-1 flex flex-col items-center justify-center text-gray-400 py-20 px-4 text-center">
                        <PieChart className="w-10 h-10 mb-3 text-gray-300" />
                        {activeContentTab === "Ratios" && period === "quarterly" ? (
                          <>
                            <p className="text-sm font-medium text-gray-600">
                              Los ratios históricos (ROIC, ROE, DuPont y Solvencia) se calculan sobre ejercicios anuales cerrados.
                            </p>
                            <button
                              type="button"
                              onClick={() => handlePeriodChange("annual")}
                              className="mt-3 px-3.5 py-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold rounded-lg transition-colors cursor-pointer"
                            >
                              Cambiar a vista Anual
                            </button>
                          </>
                        ) : (
                          <p className="text-sm font-medium text-gray-500">
                            No hay datos disponibles para la pestaña de{" "}
                            <span className="text-orange-500">
                              {activeContentTab}
                            </span>
                            .
                          </p>
                        )}
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
              <Suspense fallback={<TabFallback />}>
                <ValuationTab
                  ticker={currentTicker}
                  onOpenInfo={openGlossary}
                  onOpenValuationModels={(sym) => {
                    setCurrentTicker(sym);
                    setHasLoadedCompany(true);
                    setActiveSidebarTab("Modelos");
                  }}
                />
              </Suspense>
            )}

            {/* PESTAÑA: PROPIEDAD INSTITUCIONAL (13F) E INSIDERS (FORM 4) */}
            {activeSidebarTab === "Propiedad" && (
              <Suspense fallback={<TabFallback />}>
                <OwnershipInsidersTab ticker={currentTicker} />
              </Suspense>
            )}

            {/* PESTAÑA: MODELOS DE VALUACIÓN (AUTOMÁTICO Y MANUAL) */}
            {activeSidebarTab === "Modelos" && (
              <Suspense fallback={<TabFallback />}>
                <ValuationModelsTab
                  initialTicker={hasLoadedCompany ? currentTicker : ""}
                  recentTickers={recentTickers}
                  onOpenInfo={openGlossary}
                  onSelectGlobalTicker={(sym) => {
                    setCurrentTicker(sym);
                    setHasLoadedCompany(true);
                  }}
                />
              </Suspense>
            )}

            {/* PESTAÑA: MACRO LAB & PERSPECTIVA HISTÓRICA GLOBAL */}
            {activeSidebarTab === "MacroLab" && (
              <Suspense fallback={<TabFallback />}>
                <MacroLabTab />
              </Suspense>
            )}

            {/* PESTAÑA: TESIS DE INVERSIÓN (ONE-PAGER EJECUTIVO PARA CLIENTES) */}
            {activeSidebarTab === "Tesis" && (
              <Suspense fallback={<TabFallback />}>
                <InvestmentThesisTab
                  initialTicker={hasLoadedCompany ? currentTicker : ""}
                  recentTickers={recentTickers}
                  onSelectGlobalTicker={(sym) => {
                    setCurrentTicker(sym);
                    setHasLoadedCompany(true);
                  }}
                />
              </Suspense>
            )}

            {/* PESTAÑA: COMPARADOR MANUAL (HASTA 5 EMPRESAS) */}
            {activeSidebarTab === "Comparador" && (
              <Suspense fallback={<TabFallback />}>
                <ComparatorTab
                  currentTicker={currentTicker}
                  onOpenInfo={openGlossary}
                />
              </Suspense>
            )}

            {/* PESTAÑA: SCREENER FUNDAMENTAL */}
            {activeSidebarTab === "Screener" && (
              <Suspense fallback={<TabFallback />}>
                <ScreenerTab
                  key={screenerPresetId}
                  initialPresetId={screenerPresetId}
                  onSelectCompany={(sym) => executeSearch(sym, period, true)}
                />
              </Suspense>
            )}
          </div>
        </div>

        {/* BARRA INFERIOR DE ACCESO RÁPIDO MOBILE (< 768px) */}
        <nav className="md:hidden fixed bottom-0 inset-x-0 min-h-14 pb-[env(safe-area-inset-bottom)] bg-[#252526] border-t border-gray-700 z-40 grid grid-cols-5 items-center text-[10px]">
          <button
            type="button"
            onClick={() => setActiveSidebarTab("Inicio")}
            className={`flex flex-col items-center justify-center py-1 cursor-pointer ${
              activeSidebarTab === "Inicio" ? "text-orange-500 font-semibold" : "text-gray-400"
            }`}
          >
            <Home className="w-4 h-4 mb-0.5" />
            <span>Inicio</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveSidebarTab("Carteras")}
            className={`flex flex-col items-center justify-center py-1 cursor-pointer ${
              activeSidebarTab === "Carteras" ? "text-orange-500 font-semibold" : "text-gray-400"
            }`}
          >
            <Briefcase className="w-4 h-4 mb-0.5" />
            <span>Carteras</span>
          </button>

          <button
            type="button"
            onClick={() => handleOpenTablero("lists")}
            className={`flex flex-col items-center justify-center py-1 cursor-pointer ${
              activeSidebarTab === "Tablero"
                ? "text-orange-500 font-semibold"
                : "text-gray-400"
            }`}
          >
            <Bookmark className="w-4 h-4 mb-0.5" />
            <span>Listas</span>
          </button>

          <button
            type="button"
            onClick={() => handleOpenCompanyTab("Resumen")}
            className={`flex flex-col items-center justify-center py-1 cursor-pointer ${
              isCompanyContextTab ? "text-orange-500 font-semibold" : "text-gray-400"
            }`}
          >
            <BarChart3 className="w-4 h-4 mb-0.5" />
            <span className="truncate max-w-14">{currentTicker}</span>
          </button>

          <button
            type="button"
            onClick={() => setMobileMenuOpen(true)}
            className="flex flex-col items-center justify-center py-1 text-gray-400 hover:text-white cursor-pointer"
          >
            <MoreHorizontal className="w-4 h-4 mb-0.5" />
            <span>Más</span>
          </button>
        </nav>

        {/* MODAL AGREGAR A LISTA DE SEGUIMIENTO DESDE CABECERA DE EMPRESA */}
        {showAddToBoardModal && (
          <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl border border-gray-200 shadow-2xl w-full max-w-lg overflow-hidden text-xs">
              <div className="px-5 py-3.5 bg-[#252526] text-white flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-bold">
                    Agregar{" "}
                    <span className="text-orange-400">{currentTicker}</span> a
                    Lista de Seguimiento
                  </h4>
                  <p className="text-[11px] text-gray-400">
                    Elegí la lista y definí objetivos o alertas opcionales
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
                className="p-5 space-y-4 max-h-[82vh] overflow-y-auto"
              >
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Lista destino ({watchlistData?.count || 1}/
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
                    {savingToBoard ? "Guardando..." : "Guardar en Lista"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODALES DE GESTIÓN DE USUARIOS Y CONTRASEÑA */}
        <Suspense fallback={null}>
          {showUserMgmtModal && (
            <UserManagementModal
              isOpen={showUserMgmtModal}
              onClose={() => setShowUserMgmtModal(false)}
            />
          )}

          {showChangePassModal && (
            <ChangePasswordModal
              isOpen={showChangePassModal}
              forced={Boolean(user?.must_change_password)}
              onClose={() => setShowChangePassModal(false)}
            />
          )}
        </Suspense>

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