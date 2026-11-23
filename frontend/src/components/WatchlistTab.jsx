import { useEffect, useMemo, useRef, useState } from "react";
import apiClient from "../api/client";
import {
  Bookmark,
  Plus,
  Pencil,
  Trash2,
  Bell,
  BellRing,
  Search,
  Columns3,
  Check,
  CheckCheck,
  X,
  Info,
  Loader2,
  ArrowUp,
  ArrowDown,
  GripVertical,
  ListOrdered,
  RefreshCw,
} from "lucide-react";
import {
  WATCHLIST_METRIC_COLUMNS,
  ALERTABLE_METRICS,
  DEFAULT_VISIBLE_KEYS,
} from "../data/watchlistConstants";

function formatCell(val, type) {
  if (type === "text") return val && val.trim() ? val : "-";
  if (val === null || val === undefined || Number.isNaN(val)) return "-";
  const isNeg = val < 0;
  const abs = Math.abs(val);

  if (type === "money0") {
    const f = new Intl.NumberFormat("es-AR", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(abs);
    return isNeg ? `(US$ ${f})` : `US$ ${f}`;
  }
  if (type === "money2") {
    const f = new Intl.NumberFormat("es-AR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(abs);
    return isNeg ? `(US$ ${f})` : `US$ ${f}`;
  }
  const f = new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(abs);
  const suffix = type === "pct" ? "%" : "x";
  return isNeg ? `(${f}${suffix})` : `${f}${suffix}`;
}

export default function WatchlistTab({
  watchlistData,
  onWatchlistUpdated,
  onSelectCompany,
  initialSubView = "lists",
}) {
  const watchlists = useMemo(
    () => watchlistData?.watchlists || [],
    [watchlistData]
  );
  const notifications = useMemo(
    () => watchlistData?.notifications || [],
    [watchlistData]
  );
  const unreadNotifCount = watchlistData?.unread_notifications_count || 0;
  const maxWatchlists = watchlistData?.max_watchlists || 10;
  const count = watchlistData?.count || watchlists.length;

  const [subView, setSubView] = useState(initialSubView);
  const [selectedWlId, setSelectedWlId] = useState(null);
  const [editOrderMode, setEditOrderMode] = useState(false);
  const [draggedTicker, setDraggedTicker] = useState(null);
  const [hoveredTicker, setHoveredTicker] = useState(null);

  const [visibleCols, setVisibleCols] = useState(
    () => new Set(DEFAULT_VISIBLE_KEYS)
  );
  const [showColMenu, setShowColMenu] = useState(false);
  const colMenuRef = useRef(null);

  // Gestión de listas (crear / renombrar)
  const [creatingList, setCreatingList] = useState(false);
  const [newListName, setNewListName] = useState("");
  const [renamingList, setRenamingList] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [busyAction, setBusyAction] = useState(false);
  const [feedbackError, setFeedbackError] = useState(null);

  // Agregar empresa a la lista activa
  const [addQuery, setAddQuery] = useState("");
  const [addResults, setAddResults] = useState([]);
  const [showAddDropdown, setShowAddDropdown] = useState(false);

  // Modal de configuración de objetivos y alertas para una fila
  const [editingItem, setEditingItem] = useState(null);
  const [editBuyTarget, setEditBuyTarget] = useState("");
  const [editSellTarget, setEditSellTarget] = useState("");
  const [editThesis, setEditThesis] = useState("");
  const [editAlerts, setEditAlerts] = useState([]);

  useEffect(() => {
    const handleOutside = (e) => {
      if (colMenuRef.current && !colMenuRef.current.contains(e.target)) {
        setShowColMenu(false);
      }
    };
    if (showColMenu) document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [showColMenu]);

  const activeWatchlist = useMemo(() => {
    if (watchlists.length === 0) return null;
    return watchlists.find((w) => w.id === selectedWlId) || watchlists[0];
  }, [watchlists, selectedWlId]);

  const activeColumns = useMemo(
    () => WATCHLIST_METRIC_COLUMNS.filter((c) => visibleCols.has(c.key)),
    [visibleCols]
  );

  const toggleColumn = (key) => {
    setVisibleCols((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        if (next.size <= 1) return prev;
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handleRefreshAndEvaluate = async () => {
    setBusyAction(true);
    setFeedbackError(null);
    try {
      const res = await apiClient.get("/watchlists");
      onWatchlistUpdated(res.data);
    } catch (err) {
      setFeedbackError(
        err.response?.data?.detail || "Error al re-evaluar alertas."
      );
    } finally {
      setBusyAction(false);
    }
  };

  const handleCreateWatchlist = async (e) => {
    e.preventDefault();
    if (!newListName.trim()) return;
    setBusyAction(true);
    setFeedbackError(null);
    try {
      const res = await apiClient.post("/watchlists", {
        name: newListName.trim(),
      });
      onWatchlistUpdated(res.data);
      const created = res.data?.watchlists?.[res.data.watchlists.length - 1];
      if (created) setSelectedWlId(created.id);
      setNewListName("");
      setCreatingList(false);
    } catch (err) {
      setFeedbackError(
        err.response?.data?.detail || "No se pudo crear la watchlist."
      );
    } finally {
      setBusyAction(false);
    }
  };

  const handleRenameWatchlist = async (e) => {
    e.preventDefault();
    if (!activeWatchlist || !renameValue.trim()) return;
    setBusyAction(true);
    setFeedbackError(null);
    try {
      const res = await apiClient.put(
        `/watchlists/${activeWatchlist.id}`,
        { name: renameValue.trim() }
      );
      onWatchlistUpdated(res.data);
      setRenamingList(false);
    } catch (err) {
      setFeedbackError(
        err.response?.data?.detail || "No se pudo renombrar la watchlist."
      );
    } finally {
      setBusyAction(false);
    }
  };

  const handleDeleteWatchlist = async () => {
    if (!activeWatchlist) return;
    setBusyAction(true);
    setFeedbackError(null);
    try {
      const res = await apiClient.delete(
        `/watchlists/${activeWatchlist.id}`
      );
      onWatchlistUpdated(res.data);
      setEditOrderMode(false);
    } catch (err) {
      setFeedbackError(
        err.response?.data?.detail || "No se pudo eliminar la watchlist."
      );
    } finally {
      setBusyAction(false);
    }
  };

  const persistNewOrder = async (newTickersOrder) => {
    if (!activeWatchlist) return;
    setBusyAction(true);
    setFeedbackError(null);
    try {
      const res = await apiClient.put(
        `/watchlists/${activeWatchlist.id}/reorder`,
        { tickers: newTickersOrder }
      );
      onWatchlistUpdated(res.data);
    } catch (err) {
      setFeedbackError(
        err.response?.data?.detail || "No se pudo guardar el nuevo orden."
      );
    } finally {
      setBusyAction(false);
    }
  };

  const handleMoveItem = (index, direction) => {
    if (!activeWatchlist) return;
    const list = [...activeWatchlist.items];
    const targetIdx = index + direction;
    if (targetIdx < 0 || targetIdx >= list.length) return;
    const [moved] = list.splice(index, 1);
    list.splice(targetIdx, 0, moved);
    persistNewOrder(list.map((it) => it.ticker));
  };

  const handleDropOnRow = (targetTicker) => {
    if (!activeWatchlist || !draggedTicker || draggedTicker === targetTicker) {
      setDraggedTicker(null);
      return;
    }
    const list = [...activeWatchlist.items];
    const fromIdx = list.findIndex((it) => it.ticker === draggedTicker);
    const toIdx = list.findIndex((it) => it.ticker === targetTicker);
    if (fromIdx === -1 || toIdx === -1) {
      setDraggedTicker(null);
      return;
    }
    const [moved] = list.splice(fromIdx, 1);
    list.splice(toIdx, 0, moved);
    setDraggedTicker(null);
    persistNewOrder(list.map((it) => it.ticker));
  };

  const handleSearchAddChange = async (e) => {
    const val = e.target.value;
    setAddQuery(val);
    if (val.trim().length > 0) {
      try {
        const res = await apiClient.get(
          `/search?q=${val}`
        );
        setAddResults(res.data || []);
        setShowAddDropdown(true);
      } catch {
        setAddResults([]);
      }
    } else {
      setAddResults([]);
      setShowAddDropdown(false);
    }
  };

  const handleQuickAddTicker = async (sym) => {
    if (!activeWatchlist || !sym) return;
    setBusyAction(true);
    setFeedbackError(null);
    setShowAddDropdown(false);
    setAddQuery("");
    try {
      const res = await apiClient.post(
        `/watchlists/${activeWatchlist.id}/items`,
        {
          ticker: sym.toUpperCase(),
          buy_target_price: null,
          sell_target_price: null,
          thesis_note: "",
          alerts: [],
        }
      );
      onWatchlistUpdated(res.data);
    } catch (err) {
      setFeedbackError(
        err.response?.data?.detail || "No se pudo agregar el ticker."
      );
    } finally {
      setBusyAction(false);
    }
  };

  const handleRemoveItem = async (sym) => {
    if (!activeWatchlist) return;
    setBusyAction(true);
    setFeedbackError(null);
    try {
      const res = await apiClient.delete(
        `/watchlists/${activeWatchlist.id}/items/${sym}`
      );
      onWatchlistUpdated(res.data);
    } catch (err) {
      setFeedbackError(
        err.response?.data?.detail || "No se pudo quitar la empresa."
      );
    } finally {
      setBusyAction(false);
    }
  };

  const openEditModal = (item) => {
    setEditingItem(item);
    setEditBuyTarget(
      item.buy_target_price !== null && item.buy_target_price !== undefined
        ? String(item.buy_target_price)
        : ""
    );
    setEditSellTarget(
      item.sell_target_price !== null && item.sell_target_price !== undefined
        ? String(item.sell_target_price)
        : ""
    );
    setEditThesis(item.thesis_note || "");
    setEditAlerts(
      Array.isArray(item.alerts) ? item.alerts.map((a) => ({ ...a })) : []
    );
  };

  const addAlertRuleRow = () => {
    setEditAlerts((prev) => [
      ...prev,
      { metric: "pe_ltm", op: "<=", value: "" },
    ]);
  };

  const addAllAvailableAlertRules = () => {
    const existingKeys = new Set(editAlerts.map((a) => a.metric));
    const additions = ALERTABLE_METRICS.filter(
      (m) => !existingKeys.has(m.key)
    ).map((m) => {
      const currentVal = editingItem?.[m.key];
      return {
        metric: m.key,
        op: "<=",
        value:
          typeof currentVal === "number" ? Number(currentVal.toFixed(2)) : "",
      };
    });
    setEditAlerts((prev) => [...prev, ...additions]);
  };

  const updateAlertRuleRow = (idx, field, val) => {
    setEditAlerts((prev) =>
      prev.map((rule, i) => (i === idx ? { ...rule, [field]: val } : rule))
    );
  };

  const removeAlertRuleRow = (idx) => {
    setEditAlerts((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSaveItemSettings = async (e) => {
    e.preventDefault();
    if (!activeWatchlist || !editingItem) return;
    setBusyAction(true);
    setFeedbackError(null);

    const parsedAlerts = editAlerts
      .filter((r) => r.value !== "" && !Number.isNaN(Number(r.value)))
      .map((r) => ({
        metric: r.metric,
        op: r.op,
        value: Number(r.value),
      }));

    try {
      const res = await apiClient.post(
        `/watchlists/${activeWatchlist.id}/items`,
        {
          ticker: editingItem.ticker,
          buy_target_price: editBuyTarget !== "" ? Number(editBuyTarget) : null,
          sell_target_price:
            editSellTarget !== "" ? Number(editSellTarget) : null,
          thesis_note: editThesis,
          alerts: parsedAlerts,
        }
      );
      onWatchlistUpdated(res.data);
      setEditingItem(null);
    } catch (err) {
      setFeedbackError(
        err.response?.data?.detail || "Error guardando configuración de alertas."
      );
    } finally {
      setBusyAction(false);
    }
  };

  const handleMarkAllRead = async () => {
    setBusyAction(true);
    try {
      const res = await apiClient.post(
        "/notifications/read-all"
      );
      onWatchlistUpdated(res.data);
    } finally {
      setBusyAction(false);
    }
  };

  const handleMarkOneReadOnly = async (notifId) => {
    try {
      const res = await apiClient.post(
        `/notifications/${notifId}/read`
      );
      onWatchlistUpdated(res.data);
    } catch {
      // Ignorar
    }
  };

  const handleOpenNotifCompany = async (notif) => {
    if (!notif.is_read) {
      await handleMarkOneReadOnly(notif.id);
    }
    if (onSelectCompany) {
      onSelectCompany(notif.ticker);
    }
  };

  const handleClearNotifications = async () => {
    setBusyAction(true);
    try {
      const res = await apiClient.delete(
        "/notifications"
      );
      onWatchlistUpdated(res.data);
    } finally {
      setBusyAction(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* SUB-NAVEGACIÓN DE LISTAS DE SEGUIMIENTO: WATCHLISTS VS CENTRO DE NOTIFICACIONES */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 pb-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setSubView("lists")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold inline-flex items-center gap-2 transition-colors cursor-pointer ${
              subView === "lists"
                ? "bg-orange-500 text-white shadow-2xs"
                : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
            }`}
          >
            <Bookmark className="w-3.5 h-3.5" />
            <span>
              Mis Watchlists ({count}/{maxWatchlists})
            </span>
          </button>

          <button
            type="button"
            onClick={() => setSubView("notifications")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold inline-flex items-center gap-2 transition-colors cursor-pointer ${
              subView === "notifications"
                ? "bg-orange-500 text-white shadow-2xs"
                : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
            }`}
          >
            <BellRing className="w-3.5 h-3.5" />
            <span>Historial de Notificaciones</span>
            {unreadNotifCount > 0 && (
              <span
                className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                  subView === "notifications"
                    ? "bg-white text-orange-600"
                    : "bg-orange-500 text-white"
                }`}
              >
                {unreadNotifCount}
              </span>
            )}
          </button>
        </div>

        <button
          type="button"
          onClick={handleRefreshAndEvaluate}
          disabled={busyAction}
          className="inline-flex items-center text-xs px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 font-medium cursor-pointer disabled:opacity-50"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 mr-1.5 ${busyAction ? "animate-spin" : ""}`}
          />
          Evaluar alertas ahora
        </button>
      </div>

      {feedbackError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700 font-medium">
          {feedbackError}
        </div>
      )}

      {/* ===================================================================== */}
      {/* SUB-VISTA 1: GESTIÓN DE WATCHLISTS                                    */}
      {/* ===================================================================== */}
      {subView === "lists" && (
        <>
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-gray-200">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-orange-50 text-orange-600">
                  <Bookmark className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-gray-900">
                      Watchlists Personalizadas
                    </h3>
                    <span className="px-2 py-0.5 rounded-full bg-gray-100 border border-gray-200 text-[11px] font-semibold text-gray-700">
                      {count} / {maxWatchlists} listas
                    </span>
                  </div>
                  <p className="text-xs text-gray-500">
                    Podés crear hasta{" "}
                    <strong>{maxWatchlists} watchlists distintas</strong>,
                    reordenar sus empresas libremente y fijar alertas por
                    precio o múltiplos.
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {/* Selector de columnas visibles */}
                <div className="relative" ref={colMenuRef}>
                  <button
                    type="button"
                    onClick={() => setShowColMenu((prev) => !prev)}
                    className="flex items-center text-xs px-3 py-1.5 rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 font-medium cursor-pointer"
                  >
                    <Columns3 className="w-3.5 h-3.5 mr-1.5" />
                    Columnas ({visibleCols.size}/{WATCHLIST_METRIC_COLUMNS.length})
                  </button>

                  {showColMenu && (
                    <div className="absolute right-0 mt-1.5 w-72 bg-white border border-gray-200 rounded-lg shadow-xl z-40 p-3 text-xs">
                      <div className="flex items-center justify-between pb-2 mb-2 border-b border-gray-100">
                        <span className="font-bold text-gray-800">
                          Columnas del tablero
                        </span>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() =>
                              setVisibleCols(new Set(DEFAULT_VISIBLE_KEYS))
                            }
                            className="text-[11px] text-orange-600 hover:underline font-medium cursor-pointer"
                          >
                            Esenciales
                          </button>
                          <span className="text-gray-300">|</span>
                          <button
                            type="button"
                            onClick={() =>
                              setVisibleCols(
                                new Set(
                                  WATCHLIST_METRIC_COLUMNS.map((c) => c.key)
                                )
                              )
                            }
                            className="text-[11px] text-gray-600 hover:underline font-medium cursor-pointer"
                          >
                            Todas
                          </button>
                        </div>
                      </div>

                      <div className="max-h-72 overflow-y-auto space-y-1 pr-1">
                        {WATCHLIST_METRIC_COLUMNS.map((col) => {
                          const checked = visibleCols.has(col.key);
                          return (
                            <button
                              key={col.key}
                              type="button"
                              onClick={() => toggleColumn(col.key)}
                              className="w-full flex items-center justify-between px-2 py-1 rounded hover:bg-gray-50 text-left cursor-pointer"
                            >
                              <span
                                className={
                                  checked
                                    ? "text-gray-900 font-medium"
                                    : "text-gray-400"
                                }
                              >
                                {col.label}
                              </span>
                              <span
                                className={`w-4 h-4 rounded flex items-center justify-center border ${
                                  checked
                                    ? "bg-orange-500 border-orange-500 text-white"
                                    : "border-gray-300 bg-white"
                                }`}
                              >
                                {checked && <Check className="w-3 h-3" />}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {count < maxWatchlists ? (
                  <button
                    type="button"
                    onClick={() => {
                      setCreatingList((prev) => !prev);
                      setRenamingList(false);
                    }}
                    className="flex items-center text-xs px-3 py-1.5 rounded bg-orange-500 text-white hover:bg-orange-600 font-medium cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5 mr-1" /> Nueva Watchlist
                  </button>
                ) : (
                  <span className="inline-flex items-center text-[11px] px-2.5 py-1.5 rounded bg-amber-50 border border-amber-200 text-amber-800 font-medium">
                    <Info className="w-3.5 h-3.5 mr-1 text-amber-600" />
                    Tope alcanzado ({maxWatchlists}/{maxWatchlists} listas)
                  </span>
                )}
              </div>
            </div>

            {/* Barra de navegación entre watchlists y acciones de lista */}
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                {watchlists.map((wl) => {
                  const isSelected = activeWatchlist?.id === wl.id;
                  const triggeredCount = (wl.items || []).reduce(
                    (acc, it) => acc + (it.triggered_alerts?.length || 0),
                    0
                  );
                  return (
                    <button
                      key={wl.id}
                      type="button"
                      onClick={() => {
                        setSelectedWlId(wl.id);
                        setRenamingList(false);
                      }}
                      className={`px-3.5 py-1.5 rounded-lg text-xs font-medium border transition-colors inline-flex items-center gap-2 cursor-pointer ${
                        isSelected
                          ? "bg-gray-900 text-white border-gray-900 shadow-2xs"
                          : "bg-gray-50 text-gray-700 border-gray-300 hover:bg-orange-50 hover:border-orange-300"
                      }`}
                    >
                      <span>{wl.name}</span>
                      <span
                        className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                          isSelected
                            ? "bg-gray-700 text-gray-200"
                            : "bg-gray-200 text-gray-700"
                        }`}
                      >
                        {wl.item_count}
                      </span>
                      {triggeredCount > 0 && (
                        <span className="px-1.5 py-0.2 rounded-full bg-orange-500 text-white text-[10px] font-bold">
                          {triggeredCount}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {activeWatchlist && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setEditOrderMode((prev) => !prev)}
                    className={`flex items-center text-xs px-3 py-1 rounded border font-semibold transition-colors cursor-pointer ${
                      editOrderMode
                        ? "bg-orange-500 text-white border-orange-500"
                        : "bg-orange-50 text-orange-700 border-orange-300 hover:bg-orange-100"
                    }`}
                  >
                    <ListOrdered className="w-3.5 h-3.5 mr-1.5" />
                    {editOrderMode
                      ? "Finalizar ordenamiento"
                      : "Reordenar lista"}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setRenamingList((prev) => !prev);
                      setRenameValue(activeWatchlist.name);
                      setCreatingList(false);
                    }}
                    className="flex items-center text-xs px-2.5 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 cursor-pointer"
                  >
                    <Pencil className="w-3 h-3 mr-1" /> Renombrar
                  </button>

                  {watchlists.length > 1 && (
                    <button
                      type="button"
                      onClick={handleDeleteWatchlist}
                      disabled={busyAction}
                      className="flex items-center text-xs px-2.5 py-1 rounded border border-red-200 text-red-600 hover:bg-red-50 cursor-pointer"
                    >
                      <Trash2 className="w-3 h-3 mr-1" /> Eliminar lista
                    </button>
                  )}
                </div>
              )}
            </div>

            {editOrderMode && activeWatchlist && (
              <div className="mt-3 px-3.5 py-2 rounded-lg bg-orange-50 border border-orange-200 text-xs text-orange-900">
                <strong>Modo ordenamiento activo:</strong> arrastrá las filas
                desde el ícono <strong>⋮⋮</strong> o usá las flechas{" "}
                <strong>↑ / ↓</strong> para cambiar el orden de{" "}
                <strong>{activeWatchlist.name}</strong>.
              </div>
            )}

            {/* Formulario inline para crear watchlist */}
            {creatingList && (
              <form
                onSubmit={handleCreateWatchlist}
                className="mt-4 pt-3 border-t border-gray-100 flex flex-wrap items-center gap-2 text-xs"
              >
                <input
                  type="text"
                  value={newListName}
                  onChange={(e) => setNewListName(e.target.value)}
                  placeholder="Nombre de la nueva watchlist (ej: Bancos LatAm, Big Tech, Dividendos)..."
                  maxLength={60}
                  autoFocus
                  className="flex-1 min-w-64 px-3 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-900 focus:outline-none focus:border-orange-500"
                />
                <button
                  type="submit"
                  disabled={busyAction || !newListName.trim()}
                  className="px-3.5 py-1.5 rounded bg-orange-500 text-white font-semibold hover:bg-orange-600 cursor-pointer disabled:opacity-50"
                >
                  Crear ({count + 1}/{maxWatchlists})
                </button>
                <button
                  type="button"
                  onClick={() => setCreatingList(false)}
                  className="px-2.5 py-1.5 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 cursor-pointer"
                >
                  Cancelar
                </button>
              </form>
            )}

            {/* Formulario inline para renombrar watchlist activa */}
            {renamingList && activeWatchlist && (
              <form
                onSubmit={handleRenameWatchlist}
                className="mt-4 pt-3 border-t border-gray-100 flex flex-wrap items-center gap-2 text-xs"
              >
                <input
                  type="text"
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  maxLength={60}
                  autoFocus
                  className="flex-1 min-w-64 px-3 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-900 focus:outline-none focus:border-orange-500"
                />
                <button
                  type="submit"
                  disabled={busyAction || !renameValue.trim()}
                  className="px-3.5 py-1.5 rounded bg-gray-900 text-white font-semibold hover:bg-gray-800 cursor-pointer disabled:opacity-50"
                >
                  Guardar nombre
                </button>
                <button
                  type="button"
                  onClick={() => setRenamingList(false)}
                  className="px-2.5 py-1.5 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 cursor-pointer"
                >
                  Cancelar
                </button>
              </form>
            )}

            {/* Buscador rápido para sumar ticker a la watchlist activa */}
            {activeWatchlist && (
              <div className="mt-4 pt-4 border-t border-gray-100 flex flex-wrap items-center gap-3">
                <div className="relative flex-1 min-w-64 max-w-md">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    value={addQuery}
                    onChange={handleSearchAddChange}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && addQuery.trim()) {
                        e.preventDefault();
                        handleQuickAddTicker(addQuery.trim());
                      }
                    }}
                    onBlur={() => setShowAddDropdown(false)}
                    placeholder={`Agregar empresa a "${activeWatchlist.name}" (ej: NVDA, MELI, GGAL)...`}
                    className="w-full pl-9 pr-3 py-1.5 bg-gray-50 border border-gray-300 rounded text-xs text-gray-900 focus:outline-none focus:bg-white focus:border-orange-500"
                  />
                  {showAddDropdown && addResults.length > 0 && (
                    <div className="absolute top-full left-0 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-30 overflow-hidden">
                      {addResults.map((r, i) => (
                        <div
                          key={i}
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => handleQuickAddTicker(r.ticker)}
                          className="px-3 py-2 hover:bg-orange-50 cursor-pointer flex items-center justify-between text-xs border-b border-gray-100 last:border-0"
                        >
                          <span className="font-bold text-orange-600">
                            {r.ticker}
                          </span>
                          <span className="text-gray-700 truncate mx-2 flex-1">
                            {r.name}
                          </span>
                          <span className="text-[10px] text-gray-400 uppercase">
                            {r.type}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                {busyAction && (
                  <span className="inline-flex items-center text-xs text-orange-500">
                    <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />{" "}
                    Actualizando...
                  </span>
                )}
              </div>
            )}
          </div>

          {/* ================================================================= */}
          {/* TABLA DIVIDIDA (COLUMNA FIJA SIN SCROLL + PANEL MÉTRICAS SCROLL)  */}
          {/* ================================================================= */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {!activeWatchlist || activeWatchlist.items.length === 0 ? (
              <div className="py-12 px-4 text-center text-gray-500 text-xs">
                Esta watchlist todavía no tiene empresas. Usá el buscador de
                arriba o el botón{" "}
                <strong>“Agregar al tablero”</strong> en cualquier
                ficha de empresa.
              </div>
            ) : (
              <div className="flex w-full">
                {/* PANEL IZQUIERDO FIJO: SIEMPRE VISIBLE SIN DESLIZAR */}
                <div className="shrink-0 bg-white border-r border-gray-200 z-10">
                  <table className="text-[12px] text-left whitespace-nowrap border-collapse">
                    <thead>
                      <tr className="bg-[#333333] text-white h-10">
                        {editOrderMode && (
                          <th className="px-2.5 font-bold text-center">
                            Orden
                          </th>
                        )}
                        <th className="px-3.5 font-bold">Ticker</th>
                        <th className="px-3 font-bold">Empresa</th>
                        <th className="px-2.5 font-bold text-center">
                          Alertas
                        </th>
                        <th className="px-3 font-bold text-center">
                          Acciones
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeWatchlist.items.map((item, rowIdx) => {
                        const totalRules =
                          (item.buy_target_price ? 1 : 0) +
                          (item.sell_target_price ? 1 : 0) +
                          (item.alerts?.length || 0);
                        const triggeredCount =
                          item.triggered_alerts?.length || 0;
                        const isHovered = hoveredTicker === item.ticker;

                        return (
                          <tr
                            key={item.ticker}
                            draggable={editOrderMode}
                            onDragStart={() => setDraggedTicker(item.ticker)}
                            onDragOver={(e) => {
                              if (editOrderMode) e.preventDefault();
                            }}
                            onDrop={() => handleDropOnRow(item.ticker)}
                            onMouseEnter={() => setHoveredTicker(item.ticker)}
                            onMouseLeave={() => setHoveredTicker(null)}
                            className={`h-11 border-b border-gray-100 transition-colors ${
                              isHovered ? "bg-orange-50" : "bg-white"
                            } ${
                              draggedTicker === item.ticker ? "opacity-50" : ""
                            }`}
                          >
                            {editOrderMode && (
                              <td className="px-2.5 text-center">
                                <div className="inline-flex items-center gap-1">
                                  <span
                                    title="Arrastrar para reordenar"
                                    className="cursor-grab text-gray-400 hover:text-gray-700 p-0.5"
                                  >
                                    <GripVertical className="w-3.5 h-3.5" />
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => handleMoveItem(rowIdx, -1)}
                                    disabled={rowIdx === 0 || busyAction}
                                    title="Subir"
                                    className="p-0.5 rounded border border-gray-200 text-gray-600 hover:bg-gray-100 disabled:opacity-30 cursor-pointer"
                                  >
                                    <ArrowUp className="w-3 h-3" />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleMoveItem(rowIdx, 1)}
                                    disabled={
                                      rowIdx ===
                                        activeWatchlist.items.length - 1 ||
                                      busyAction
                                    }
                                    title="Bajar"
                                    className="p-0.5 rounded border border-gray-200 text-gray-600 hover:bg-gray-100 disabled:opacity-30 cursor-pointer"
                                  >
                                    <ArrowDown className="w-3 h-3" />
                                  </button>
                                </div>
                              </td>
                            )}

                            {/* Columna Ticker */}
                            <td
                              onClick={() =>
                                onSelectCompany && onSelectCompany(item.ticker)
                              }
                              className="px-3.5 font-bold text-orange-600 cursor-pointer hover:underline"
                            >
                              {item.ticker}
                            </td>

                            {/* Columna Empresa (nombre completo) */}
                            <td
                              onClick={() =>
                                onSelectCompany && onSelectCompany(item.ticker)
                              }
                              title={item.name}
                              className="px-3 text-gray-800 max-w-44 truncate cursor-pointer hover:text-orange-600"
                            >
                              {item.name}
                            </td>

                            {/* Columna Alertas */}
                            <td className="px-2.5 text-center">
                              <button
                                type="button"
                                onClick={() => openEditModal(item)}
                                title="Configurar objetivos y alertas"
                                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold cursor-pointer ${
                                  triggeredCount > 0
                                    ? "bg-orange-500 text-white"
                                    : totalRules > 0
                                    ? "bg-orange-50 text-orange-700 border border-orange-200"
                                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                                }`}
                              >
                                {triggeredCount > 0 ? (
                                  <BellRing className="w-3 h-3" />
                                ) : (
                                  <Bell className="w-3 h-3" />
                                )}
                                <span>
                                  {triggeredCount > 0
                                    ? `${triggeredCount}`
                                    : totalRules > 0
                                    ? `${totalRules}`
                                    : "Alertas"}
                                </span>
                              </button>
                            </td>

                            {/* Columna Acciones (Editar / Quitar siempre visibles) */}
                            <td className="px-3 text-center">
                              <div className="inline-flex items-center gap-1.5">
                                <button
                                  type="button"
                                  onClick={() => openEditModal(item)}
                                  title="Editar objetivos, tesis y alertas"
                                  className="inline-flex items-center gap-1 px-2 py-1 rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-100 text-[11px] font-medium cursor-pointer"
                                >
                                  <Pencil className="w-3 h-3" />
                                  <span>Editar</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveItem(item.ticker)}
                                  title="Quitar de esta watchlist"
                                  className="inline-flex items-center gap-1 px-2 py-1 rounded border border-red-200 bg-red-50/60 text-red-600 hover:bg-red-100 text-[11px] font-medium cursor-pointer"
                                >
                                  <Trash2 className="w-3 h-3" />
                                  <span>Quitar</span>
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* PANEL DERECHO CON SCROLL HORIZONTAL PARA MÉTRICAS Y MÚLTIPLOS */}
                <div className="flex-1 overflow-x-auto">
                  <table className="w-full text-[12px] text-left whitespace-nowrap border-collapse">
                    <thead>
                      <tr className="bg-[#333333] text-white h-10">
                        {activeColumns.map((col) => (
                          <th
                            key={col.key}
                            className={`px-3.5 font-bold ${
                              col.type === "text"
                                ? "text-left min-w-48"
                                : "text-right"
                            }`}
                          >
                            {col.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {activeWatchlist.items.map((item) => {
                        const isHovered = hoveredTicker === item.ticker;
                        return (
                          <tr
                            key={item.ticker}
                            onMouseEnter={() => setHoveredTicker(item.ticker)}
                            onMouseLeave={() => setHoveredTicker(null)}
                            className={`h-11 border-b border-gray-100 transition-colors ${
                              isHovered ? "bg-orange-50" : "bg-white"
                            }`}
                          >
                            {activeColumns.map((col) => {
                              const val = item[col.key];
                              const isNeg = typeof val === "number" && val < 0;
                              const isPositiveHighlight =
                                (col.key === "change_pct" ||
                                  col.key === "upside_ws_pct") &&
                                typeof val === "number" &&
                                val > 0;
                              return (
                                <td
                                  key={col.key}
                                  className={`px-3.5 tabular-nums ${
                                    col.type === "text"
                                      ? "text-left text-gray-600 text-[11px] max-w-64 truncate"
                                      : "text-right"
                                  } ${
                                    isNeg
                                      ? "text-[#d93025]"
                                      : isPositiveHighlight
                                      ? "text-emerald-700 font-semibold"
                                      : "text-gray-800"
                                  }`}
                                >
                                  {formatCell(val, col.type)}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* ===================================================================== */}
      {/* SUB-VISTA 2: CENTRO DE NOTIFICACIONES (HISTORIAL PERSISTENTE)         */}
      {/* ===================================================================== */}
      {subView === "notifications" && (
        <div className="space-y-4">
          {/* Guía explicativa de los 3 tipos de alerta */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-gray-100">
              <div>
                <h3 className="text-sm font-bold text-gray-900">
                  Centro de Notificaciones y Alertas Disparadas
                </h3>
                <p className="text-xs text-gray-500">
                  Cada vez que una empresa de tus watchlists cumple una
                  condición, la notificación queda almacenada acá con fecha y
                  hora.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {unreadNotifCount > 0 && (
                  <button
                    type="button"
                    onClick={handleMarkAllRead}
                    disabled={busyAction}
                    className="inline-flex items-center text-xs px-3 py-1.5 rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 font-medium cursor-pointer"
                  >
                    <CheckCheck className="w-3.5 h-3.5 mr-1.5 text-emerald-600" />
                    Marcar todas como leídas
                  </button>
                )}
                {notifications.length > 0 && (
                  <button
                    type="button"
                    onClick={handleClearNotifications}
                    disabled={busyAction}
                    className="inline-flex items-center text-xs px-3 py-1.5 rounded border border-red-200 text-red-600 hover:bg-red-50 font-medium cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5 mr-1.5" />
                    Limpiar historial
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4 text-xs">
              <div className="p-3 rounded-lg bg-emerald-50/70 border border-emerald-200">
                <p className="font-bold text-emerald-900">
                  1. Objetivo de Compra (≤ US$)
                </p>
                <p className="text-emerald-800 mt-0.5">
                  Se dispara cuando la cotización cae igual o por debajo del
                  precio objetivo de entrada que fijaste.
                </p>
              </div>
              <div className="p-3 rounded-lg bg-amber-50/70 border border-amber-200">
                <p className="font-bold text-amber-900">
                  2. Objetivo de Venta (≥ US$)
                </p>
                <p className="text-amber-800 mt-0.5">
                  Se dispara cuando la acción alcanza o supera tu precio objetivo
                  de toma de ganancias.
                </p>
              </div>
              <div className="p-3 rounded-lg bg-orange-50/70 border border-orange-200">
                <p className="font-bold text-orange-900">
                  3. Reglas por Múltiplo / Ratio
                </p>
                <p className="text-orange-800 mt-0.5">
                  Se dispara cuando cualquier indicador elegido (P/E,
                  EV/EBITDA, FCF Yield, ROIC, etc.) cruza tu umbral (≤ o ≥).
                </p>
              </div>
            </div>
          </div>

          {/* Listado histórico de notificaciones */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            {notifications.length === 0 ? (
              <div className="py-14 px-6 text-center text-xs text-gray-500 space-y-2">
                <Bell className="w-8 h-8 mx-auto text-gray-300" />
                <p className="font-semibold text-gray-700">
                  Todavía no hay alertas disparadas en tu historial.
                </p>
                <p>
                  Para probarlas ahora: andá a{" "}
                  <strong>Mis Watchlists</strong>, tocá el botón{" "}
                  <strong>Editar</strong> en una empresa y cargale un{" "}
                  <strong>Obj. Compra</strong> mayor a su precio actual (o una
                  regla como <strong>P/E LTM ≤ 100</strong>).
                </p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {notifications.map((n) => (
                  <div
                    key={n.id}
                    className={`px-5 py-3.5 flex flex-wrap items-center justify-between gap-3 transition-colors ${
                      n.is_read
                        ? "bg-white hover:bg-gray-50"
                        : "bg-orange-50/60 hover:bg-orange-100/60"
                    }`}
                  >
                    <div
                      onClick={() => handleOpenNotifCompany(n)}
                      className="flex items-start gap-3 flex-1 min-w-0 cursor-pointer"
                    >
                      <span
                        className={`mt-1 w-2.5 h-2.5 rounded-full shrink-0 ${
                          n.is_read ? "bg-gray-300" : "bg-orange-500"
                        }`}
                      />
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-bold text-xs text-orange-600">
                            {n.ticker}
                          </span>
                          <span className="font-bold text-xs text-gray-900">
                            {n.title}
                          </span>
                          <span className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200 text-[10px] font-semibold text-gray-600">
                            Lista: {n.watchlist_name}
                          </span>
                          {!n.is_read && (
                            <span className="px-1.5 py-0.2 rounded bg-orange-500 text-white text-[10px] font-bold">
                              Nueva
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-700 mt-0.5">
                          {n.company_name} — <strong>{n.detail}</strong>
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-right text-[11px] text-gray-400">
                        <p>{n.triggered_at}</p>
                        <button
                          type="button"
                          onClick={() => handleOpenNotifCompany(n)}
                          className="text-orange-600 font-medium hover:underline cursor-pointer"
                        >
                          Abrir ficha →
                        </button>
                      </div>

                      {!n.is_read && (
                        <button
                          type="button"
                          onClick={() => handleMarkOneReadOnly(n.id)}
                          title="Marcar como leída"
                          className="p-1.5 rounded-lg border border-gray-300 bg-white text-gray-600 hover:text-emerald-600 hover:border-emerald-300 transition-colors cursor-pointer"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* MODAL DE CONFIGURACIÓN DE OBJETIVOS Y ALERTAS POR MÉTRICA */}
      {editingItem && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-gray-200 shadow-2xl w-full max-w-2xl overflow-hidden text-xs">
            <div className="px-5 py-3.5 bg-[#252526] text-white flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold">
                  Objetivos y Alertas —{" "}
                  <span className="text-orange-400">{editingItem.ticker}</span>{" "}
                  ({editingItem.name})
                </h4>
                <p className="text-[11px] text-gray-400">
                  Cotización actual: US${" "}
                  {formatCell(editingItem.price, "money2").replace("US$ ", "")}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setEditingItem(null)}
                className="text-gray-400 hover:text-white cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form
              onSubmit={handleSaveItemSettings}
              className="p-5 space-y-4 max-h-[80vh] overflow-y-auto"
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Precio Objetivo de Compra (Alerta ≤ US$)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={editBuyTarget}
                    onChange={(e) => setEditBuyTarget(e.target.value)}
                    placeholder="Ej: 380.00"
                    className="w-full px-3 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-900 focus:outline-none focus:border-orange-500"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Precio Objetivo de Venta (Alerta ≥ US$)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={editSellTarget}
                    onChange={(e) => setEditSellTarget(e.target.value)}
                    placeholder="Ej: 520.00"
                    className="w-full px-3 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-900 focus:outline-none focus:border-orange-500"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-gray-700 mb-1">
                  Nota de Tesis de Inversión
                </label>
                <input
                  type="text"
                  value={editThesis}
                  onChange={(e) => setEditThesis(e.target.value)}
                  placeholder="Ej: Esperar compresión a 22x P/E o retroceso al soporte..."
                  className="w-full px-3 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-900 focus:outline-none focus:border-orange-500"
                />
              </div>

              {/* Reglas dinámicas sobre múltiplos/ratios */}
              <div className="pt-3 border-t border-gray-200">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
                  <span className="font-bold text-gray-800">
                    Alertas personalizadas por indicador ({editAlerts.length})
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={addAlertRuleRow}
                      className="px-2.5 py-1 rounded bg-orange-50 border border-orange-300 text-orange-700 font-semibold hover:bg-orange-100 cursor-pointer"
                    >
                      + Agregar regla
                    </button>
                    <button
                      type="button"
                      onClick={addAllAvailableAlertRules}
                      className="px-2.5 py-1 rounded bg-gray-100 border border-gray-300 text-gray-700 font-medium hover:bg-gray-200 cursor-pointer"
                    >
                      + Cargar todos los indicadores
                    </button>
                  </div>
                </div>

                {editAlerts.length === 0 ? (
                  <p className="text-gray-500 bg-gray-50 border border-dashed border-gray-200 rounded p-3 text-center">
                    No agregaste reglas sobre ratios/múltiplos todavía. Podés
                    sumar 1, varias o todas con los botones de arriba.
                  </p>
                ) : (
                  <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                    {editAlerts.map((rule, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <select
                          value={rule.metric}
                          onChange={(e) =>
                            updateAlertRuleRow(idx, "metric", e.target.value)
                          }
                          className="flex-1 px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800"
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
                            updateAlertRuleRow(idx, "op", e.target.value)
                          }
                          className="w-20 px-2 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 font-bold"
                        >
                          <option value="<=">≤</option>
                          <option value=">=">≥</option>
                        </select>
                        <input
                          type="number"
                          step="0.01"
                          value={rule.value}
                          onChange={(e) =>
                            updateAlertRuleRow(idx, "value", e.target.value)
                          }
                          placeholder="Valor"
                          className="w-28 px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-900"
                        />
                        <button
                          type="button"
                          onClick={() => removeAlertRuleRow(idx)}
                          className="p-1.5 text-red-500 hover:bg-red-50 rounded cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="pt-3 border-t border-gray-200 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setEditingItem(null)}
                  className="px-3.5 py-1.5 rounded border border-gray-300 text-gray-700 hover:bg-gray-50 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={busyAction}
                  className="px-4 py-1.5 rounded bg-orange-500 text-white font-semibold hover:bg-orange-600 cursor-pointer disabled:opacity-50"
                >
                  Guardar objetivos y alertas
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}