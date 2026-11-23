import { useCallback, useEffect, useState } from "react";
import {
  Briefcase,
  UserCheck,
  UserPlus,
  TrendingUp,
  TrendingDown,
  PlusCircle,
  Trash2,
  Save,
  Loader2,
  AlertCircle,
  CheckCircle2,
  DollarSign,
  PieChart,
  History,
  ExternalLink,
  Activity,
  X,
} from "lucide-react";
import apiClient from "../api/client";
import { useAuth } from "../context/authStore";

const TX_TYPE_META = {
  BUY: { label: "Compra", badge: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  SELL: { label: "Venta", badge: "bg-red-50 text-red-700 border-red-200" },
  DIVIDEND: { label: "Dividendo", badge: "bg-blue-50 text-blue-700 border-blue-200" },
  DEPOSIT: { label: "Depósito", badge: "bg-purple-50 text-purple-700 border-purple-200" },
  WITHDRAWAL: { label: "Retiro", badge: "bg-amber-50 text-amber-700 border-amber-200" },
};

function formatCurrency(val, currency = "USD") {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "-";
  const num = Number(val);
  const abs = Math.abs(num);
  const formatted = new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(abs);
  const prefix = currency === "ARS" ? "$" : "US$";
  return num < 0 ? `-${prefix} ${formatted}` : `${prefix} ${formatted}`;
}

function formatQty(val) {
  if (val === null || val === undefined) return "-";
  return new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  }).format(Number(val));
}

export default function PortfoliosCRMTab({ onSelectCompany }) {
  const { isClient, isAdvisorOrAdmin } = useAuth();

  const [clients, setClients] = useState([]);
  const [selectedClientId, setSelectedClientId] = useState("");
  const [portfolio, setPortfolio] = useState(null);

  const [loadingClients, setLoadingClients] = useState(false);
  const [loadingPortfolio, setLoadingPortfolio] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");

  // Modal crear cartera manual de cliente
  const [showNewClientModal, setShowNewClientModal] = useState(false);
  const [newClientName, setNewClientName] = useState("");
  const [newClientEmail, setNewClientEmail] = useState("");
  const [newClientPhone, setNewClientPhone] = useState("");
  const [newClientRisk, setNewClientRisk] = useState("moderado");
  const [newClientHorizon, setNewClientHorizon] = useState("largo_plazo");
  const [newClientCurrency, setNewClientCurrency] = useState("USD");
  const [newClientNotes, setNewClientNotes] = useState("");
  const [creatingClient, setCreatingClient] = useState(false);

  // Estado editable de ficha patrimonial
  const [riskProfile, setRiskProfile] = useState("moderado");
  const [horizon, setHorizon] = useState("largo_plazo");
  const [targetCurrency, setTargetCurrency] = useState("USD");
  const [phone, setPhone] = useState("");
  const [crmNotes, setCrmNotes] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  // Estado formulario nueva operación
  const [txType, setTxType] = useState("BUY");
  const [ticker, setTicker] = useState("");
  const [txDate, setTxDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [quantity, setQuantity] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [commission, setCommission] = useState("0");
  const [txCurrency] = useState("USD");
  const [txNotes, setTxNotes] = useState("");
  const [submittingTx, setSubmittingTx] = useState(false);

  const syncProfileForm = useCallback((clientObj) => {
    if (!clientObj) return;
    setRiskProfile(clientObj.risk_profile || "moderado");
    setHorizon(clientObj.investment_horizon || "largo_plazo");
    setTargetCurrency(clientObj.target_currency || "USD");
    setPhone(clientObj.phone || "");
    setCrmNotes(clientObj.notes || "");
  }, []);

  const fetchPortfolioById = useCallback(
    async (clientId) => {
      if (!clientId) return;
      setLoadingPortfolio(true);
      setError("");
      try {
        const res = await apiClient.get(`/portfolios/${clientId}`);
        setPortfolio(res.data);
        syncProfileForm(res.data?.client);
      } catch (err) {
        setError(
          err?.response?.data?.detail || "No se pudo cargar la cartera del cliente.",
        );
      } finally {
        setLoadingPortfolio(false);
      }
    },
    [syncProfileForm],
  );

  // Carga inicial según rol
  useEffect(() => {
    let cancelled = false;

    const init = async () => {
      if (isClient) {
        setLoadingPortfolio(true);
        setError("");
        try {
          const res = await apiClient.get("/portfolios/me");
          if (!cancelled) {
            setPortfolio(res.data);
            syncProfileForm(res.data?.client);
          }
        } catch (err) {
          if (!cancelled) {
            setError(
              err?.response?.data?.detail || "No se pudo cargar tu cartera.",
            );
          }
        } finally {
          if (!cancelled) setLoadingPortfolio(false);
        }
        return;
      }

      setLoadingClients(true);
      setError("");
      try {
        const res = await apiClient.get("/portfolios/clients");
        const list = res.data?.clients || [];
        if (!cancelled) {
          setClients(list);
          if (list.length > 0) {
            const firstId = String(list[0].client_id);
            setSelectedClientId(firstId);
            fetchPortfolioById(firstId);
          } else {
            setSelectedClientId("");
            setPortfolio(null);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err?.response?.data?.detail || "Error al obtener la lista de clientes.",
          );
        }
      } finally {
        if (!cancelled) setLoadingClients(false);
      }
    };

    init();
    return () => {
      cancelled = true;
    };
  }, [isClient, fetchPortfolioById, syncProfileForm]);

  const activeClientId = isClient
    ? String(portfolio?.client?.client_id || "")
    : selectedClientId;

  const handleSelectClient = (newId) => {
    setSelectedClientId(newId);
    setFeedback("");
    setError("");
    fetchPortfolioById(newId);
  };

  const handleTxTypeChange = (nextType) => {
    setTxType(nextType);
    const cleanSym = ticker.trim().toUpperCase();
    const matchedHolding = (portfolio?.holdings || []).find(
      (h) => h.ticker === cleanSym,
    );
    if (nextType === "SELL" && matchedHolding?.current_price) {
      setUnitPrice(String(matchedHolding.current_price));
    } else if (nextType === "DEPOSIT" || nextType === "WITHDRAWAL") {
      setTicker("");
      setUnitPrice("1");
    } else {
      setUnitPrice("");
    }
  };

  const handleTickerInputChange = (rawVal) => {
    const upper = rawVal.toUpperCase();
    setTicker(upper);
    if (txType === "SELL") {
      const matchedHolding = (portfolio?.holdings || []).find(
        (h) => h.ticker === upper.trim(),
      );
      if (matchedHolding?.current_price) {
        setUnitPrice(String(matchedHolding.current_price));
      }
    }
  };

  const handleCreateManagedClient = async (e) => {
    e.preventDefault();
    if (!newClientName.trim()) {
      setError("Ingresá el nombre completo del cliente.");
      return;
    }
    setCreatingClient(true);
    setError("");
    setFeedback("");
    try {
      const res = await apiClient.post("/portfolios/clients", {
        full_name: newClientName.trim(),
        email: newClientEmail.trim() || null,
        phone: newClientPhone.trim() || null,
        risk_profile: newClientRisk,
        investment_horizon: newClientHorizon,
        target_currency: newClientCurrency,
        notes: newClientNotes.trim() || null,
      });
      const created = res.data?.client;
      if (created) {
        setClients((prev) =>
          [...prev, created].sort((a, b) =>
            (a.full_name || "").localeCompare(b.full_name || ""),
          ),
        );
        const newId = String(created.client_id);
        setSelectedClientId(newId);
        await fetchPortfolioById(newId);
      }
      setNewClientName("");
      setNewClientEmail("");
      setNewClientPhone("");
      setNewClientRisk("moderado");
      setNewClientHorizon("largo_plazo");
      setNewClientCurrency("USD");
      setNewClientNotes("");
      setShowNewClientModal(false);
      setFeedback("Cartera de cliente creada. Ya podés registrar operaciones.");
    } catch (err) {
      setError(
        err?.response?.data?.detail || "No se pudo crear la cartera del cliente.",
      );
    } finally {
      setCreatingClient(false);
    }
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    if (!activeClientId) return;
    setSavingProfile(true);
    setError("");
    setFeedback("");
    try {
      const res = await apiClient.patch(`/portfolios/${activeClientId}/profile`, {
        risk_profile: riskProfile,
        investment_horizon: horizon,
        target_currency: targetCurrency,
        phone,
        notes: crmNotes,
      });
      const updatedClient = res.data?.client;
      if (updatedClient) {
        setPortfolio((prev) => (prev ? { ...prev, client: updatedClient } : prev));
        if (!isClient) {
          setClients((prev) =>
            prev.map((c) =>
              String(c.client_id) === String(activeClientId) ? updatedClient : c,
            ),
          );
        }
      }
      setFeedback(
        isClient
          ? "Perfil patrimonial actualizado."
          : "Ficha CRM del cliente actualizada.",
      );
    } catch (err) {
      setError(
        err?.response?.data?.detail || "No se pudo actualizar el perfil.",
      );
    } finally {
      setSavingProfile(false);
    }
  };

  const handleAddTransaction = async (e) => {
    e.preventDefault();
    if (!activeClientId) return;
    setSubmittingTx(true);
    setError("");
    setFeedback("");

    const needsTicker = txType === "BUY" || txType === "SELL" || txType === "DIVIDEND";
    try {
      const res = await apiClient.post(
        `/portfolios/${activeClientId}/transactions`,
        {
          tx_type: txType,
          ticker: needsTicker ? ticker.trim().toUpperCase() : null,
          tx_date: txDate,
          quantity: Number(quantity),
          unit_price: Number(unitPrice),
          commission: commission !== "" ? Number(commission) : 0,
          currency: txCurrency,
          notes: txNotes.trim() || null,
        },
      );
      setPortfolio(res.data);
      setTicker("");
      setQuantity("");
      setUnitPrice("");
      setCommission("0");
      setTxNotes("");
      setFeedback("Operación registrada, PPP y TWR recalculados.");
    } catch (err) {
      setError(
        err?.response?.data?.detail || "Error al registrar la operación.",
      );
    } finally {
      setSubmittingTx(false);
    }
  };

  const handleDeleteTransaction = async (txId) => {
    if (!activeClientId) return;
    if (!window.confirm("¿Eliminar esta operación y recalcular tenencias, PPP y TWR?")) {
      return;
    }
    setError("");
    setFeedback("");
    try {
      const res = await apiClient.delete(
        `/portfolios/${activeClientId}/transactions/${txId}`,
      );
      setPortfolio(res.data);
      setFeedback("Operación eliminada y cartera recalculada.");
    } catch (err) {
      setError(
        err?.response?.data?.detail || "No se pudo eliminar la operación.",
      );
    }
  };

  const summary = portfolio?.summary;
  const holdings = portfolio?.holdings || [];
  const transactions = portfolio?.transactions || [];
  const canEdit = Boolean(portfolio?.can_edit);
  const currency = portfolio?.client?.target_currency || "USD";
  const requiresTicker =
    txType === "BUY" || txType === "SELL" || txType === "DIVIDEND";
  const twrVal = Number(summary?.twr_pct || 0);

  return (
    <div className="space-y-6 text-gray-800">
      {/* CABECERA + SELECTOR DE CLIENTE + ALTA MANUAL (SI ES ASESOR/ADMIN) */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-orange-500/10 border border-orange-200 flex items-center justify-center text-orange-600 shrink-0">
            <Briefcase className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900 leading-tight">
              {isClient
                ? "Mi Cartera de Inversión"
                : "CRM de Clientes & Gestión de Carteras"}
            </h1>
            <p className="text-xs text-gray-500 mt-0.5">
              {isClient
                ? "Administrá tu perfil patrimonial, registrá operaciones y monitoreá PPP y TWR."
                : "Administrá las carteras de tus clientes asignados o creá carteras manuales de seguimiento."}
            </p>
          </div>
        </div>

        {isAdvisorOrAdmin && (
          <div className="flex flex-wrap items-center gap-2">
            {loadingClients ? (
              <span className="text-xs text-gray-500">Cargando clientes...</span>
            ) : (
              clients.length > 0 && (
                <div className="flex items-center gap-2 min-w-60">
                  <UserCheck className="w-4 h-4 text-gray-400 shrink-0" />
                  <select
                    value={selectedClientId}
                    onChange={(e) => handleSelectClient(e.target.value)}
                    className="w-full px-3 py-2 text-xs font-semibold bg-gray-50 text-gray-900 border border-gray-300 rounded-lg focus:outline-none focus:border-orange-500"
                  >
                    {clients.map((c) => (
                      <option key={c.client_id} value={c.client_id}>
                        {c.full_name}
                        {c.email ? ` (${c.email})` : " (Cartera manual)"}
                      </option>
                    ))}
                  </select>
                </div>
              )
            )}

            <button
              type="button"
              onClick={() => {
                setError("");
                setShowNewClientModal(true);
              }}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-[#ff6600] hover:bg-[#e55a00] text-white text-xs font-semibold rounded-lg transition-colors cursor-pointer shrink-0"
            >
              <UserPlus className="w-3.5 h-3.5" />
              Nueva cartera
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg p-3">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {feedback && (
        <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-lg p-3">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{feedback}</span>
        </div>
      )}

      {isAdvisorOrAdmin && !loadingClients && clients.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-orange-50 border border-orange-200 flex items-center justify-center text-orange-500 mx-auto">
            <Briefcase className="w-6 h-6" />
          </div>
          <h2 className="text-sm font-bold text-gray-900">
            Todavía no tenés carteras bajo tu gestión
          </h2>
          <p className="text-xs text-gray-500 max-w-md mx-auto">
            Solo vas a ver clientes registrados que te hayan elegido como ejecutivo a cargo, o carteras manuales que cargues acá para seguimiento.
          </p>
          <button
            type="button"
            onClick={() => setShowNewClientModal(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#ff6600] hover:bg-[#e55a00] text-white text-xs font-semibold rounded-lg transition-colors cursor-pointer"
          >
            <UserPlus className="w-4 h-4" />
            Crear primera cartera manual
          </button>
        </div>
      ) : loadingPortfolio ? (
        <div className="bg-white border border-gray-200 rounded-xl p-16 flex flex-col items-center justify-center text-orange-500">
          <Loader2 className="w-8 h-8 animate-spin mb-2" />
          <p className="text-xs font-medium text-gray-600">
            Calculando tenencias, PPP, TWR y cotizaciones de mercado...
          </p>
        </div>
      ) : (
        portfolio && (
          <>
            {/* TARJETAS KPI RESUMEN DE CARTERA (6 KPIs incluyendo TWR) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3.5">
              <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                <p className="text-[11px] font-semibold text-gray-400 uppercase">
                  Valor de Mercado
                </p>
                <p className="text-lg font-bold text-gray-900 mt-1">
                  {formatCurrency(summary?.total_market_value, currency)}
                </p>
                <p className="text-[11px] text-gray-500 mt-1">
                  {summary?.positions_count || 0} activos en cartera
                </p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                <p className="text-[11px] font-semibold text-gray-400 uppercase">
                  Capital Invertido (PPP)
                </p>
                <p className="text-lg font-bold text-gray-900 mt-1">
                  {formatCurrency(summary?.total_invested_cost, currency)}
                </p>
                <p className="text-[11px] text-gray-500 mt-1">
                  Aportes netos: {formatCurrency(summary?.net_contributed_capital, currency)}
                </p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                <p className="text-[11px] font-semibold text-gray-400 uppercase">
                  Resultado No Realizado
                </p>
                <p
                  className={`text-lg font-bold mt-1 flex items-center gap-1 ${
                    (summary?.total_unrealized_pnl || 0) >= 0
                      ? "text-emerald-600"
                      : "text-red-600"
                  }`}
                >
                  {(summary?.total_unrealized_pnl || 0) >= 0 ? (
                    <TrendingUp className="w-4 h-4" />
                  ) : (
                    <TrendingDown className="w-4 h-4" />
                  )}
                  {formatCurrency(summary?.total_unrealized_pnl, currency)}
                </p>
                <p
                  className={`text-[11px] font-semibold mt-1 ${
                    (summary?.total_unrealized_pct || 0) >= 0
                      ? "text-emerald-600"
                      : "text-red-600"
                  }`}
                >
                  {(summary?.total_unrealized_pct || 0) >= 0 ? "+" : ""}
                  {Number(summary?.total_unrealized_pct || 0).toFixed(2)}% sobre costo
                </p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                <p className="text-[11px] font-semibold text-gray-400 uppercase flex items-center gap-1">
                  <Activity className="w-3.5 h-3.5 text-orange-500" />
                  Rendimiento TWR
                </p>
                <p
                  className={`text-lg font-bold mt-1 ${
                    twrVal >= 0 ? "text-emerald-600" : "text-red-600"
                  }`}
                >
                  {twrVal >= 0 ? "+" : ""}
                  {twrVal.toFixed(2)}%
                </p>
                <p className="text-[11px] text-gray-500 mt-1">
                  {summary?.twr_annualized_pct !== null &&
                  summary?.twr_annualized_pct !== undefined
                    ? `Anualizado: ${
                        summary.twr_annualized_pct >= 0 ? "+" : ""
                      }${Number(summary.twr_annualized_pct).toFixed(2)}%`
                    : `Sin sesgo de flujos (${summary?.subperiods_count || 0} tramos)`}
                </p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                <p className="text-[11px] font-semibold text-gray-400 uppercase">
                  P&L Realizado + Div.
                </p>
                <p className="text-lg font-bold text-gray-900 mt-1">
                  {formatCurrency(
                    (summary?.total_realized_pnl || 0) +
                      (summary?.total_dividends || 0),
                    currency,
                  )}
                </p>
                <p className="text-[11px] text-gray-500 mt-1">
                  Ventas: {formatCurrency(summary?.total_realized_pnl, currency)} · Div:{" "}
                  {formatCurrency(summary?.total_dividends, currency)}
                </p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                <p className="text-[11px] font-semibold text-gray-400 uppercase flex items-center gap-1">
                  <DollarSign className="w-3.5 h-3.5 text-orange-500" />
                  Liquidez / Caja Neta
                </p>
                <p className="text-lg font-bold text-gray-900 mt-1">
                  {formatCurrency(summary?.cash_balance, currency)}
                </p>
                <p className="text-[11px] text-gray-500 mt-1">
                  Patrimonio: {formatCurrency(summary?.total_equity, currency)}
                </p>
              </div>
            </div>

            {/* FICHA PATRIMONIAL (EDITABLE POR TITULAR Y EJECUTIVO ASIGNADO) */}
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <h2 className="text-xs font-bold uppercase tracking-wider text-gray-700">
                  Ficha Patrimonial & Perfil del Inversor —{" "}
                  <span className="text-orange-600">{portfolio.client?.full_name}</span>
                </h2>
                {portfolio.client?.advisor_name ? (
                  <span className="text-[11px] text-gray-500">
                    Ejecutivo a cargo:{" "}
                    <strong className="text-gray-700">
                      {portfolio.client.advisor_name}
                    </strong>
                  </span>
                ) : (
                  <span className="text-[11px] text-gray-400">
                    Cuenta independiente (privada)
                  </span>
                )}
              </div>

              {canEdit && (
                <form
                  onSubmit={handleSaveProfile}
                  className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end"
                >
                  <div>
                    <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                      Perfil de Riesgo
                    </label>
                    <select
                      value={riskProfile}
                      onChange={(e) => setRiskProfile(e.target.value)}
                      className="w-full px-3 py-2 text-xs bg-gray-50 text-gray-900 border border-gray-300 rounded-lg focus:outline-none focus:border-orange-500"
                    >
                      <option value="conservador">Conservador</option>
                      <option value="moderado">Moderado</option>
                      <option value="agresivo">Agresivo</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                      Horizonte
                    </label>
                    <select
                      value={horizon}
                      onChange={(e) => setHorizon(e.target.value)}
                      className="w-full px-3 py-2 text-xs bg-gray-50 text-gray-900 border border-gray-300 rounded-lg focus:outline-none focus:border-orange-500"
                    >
                      <option value="corto_plazo">Corto Plazo ({"<"} 1 año)</option>
                      <option value="mediano_plazo">Mediano Plazo (1–3 años)</option>
                      <option value="largo_plazo">Largo Plazo ({">"} 3 años)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                      Moneda Base
                    </label>
                    <select
                      value={targetCurrency}
                      onChange={(e) => setTargetCurrency(e.target.value)}
                      className="w-full px-3 py-2 text-xs bg-gray-50 text-gray-900 border border-gray-300 rounded-lg focus:outline-none focus:border-orange-500"
                    >
                      <option value="USD">USD (Dólares)</option>
                      <option value="ARS">ARS (Pesos)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                      Teléfono / Contacto
                    </label>
                    <input
                      type="text"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="+54 9 ..."
                      className="w-full px-3 py-2 text-xs bg-gray-50 text-gray-900 placeholder:text-gray-400 border border-gray-300 rounded-lg focus:outline-none focus:border-orange-500"
                    />
                  </div>

                  <div className="flex gap-2">
                    <div className="flex-1">
                      <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                        Notas de seguimiento
                      </label>
                      <input
                        type="text"
                        value={crmNotes}
                        onChange={(e) => setCrmNotes(e.target.value)}
                        placeholder="Objetivos, liquidez, observaciones..."
                        className="w-full px-3 py-2 text-xs bg-gray-50 text-gray-900 placeholder:text-gray-400 border border-gray-300 rounded-lg focus:outline-none focus:border-orange-500"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={savingProfile}
                      title="Guardar perfil"
                      className="px-3 py-2 bg-gray-900 hover:bg-gray-800 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 shrink-0 cursor-pointer disabled:opacity-50"
                    >
                      <Save className="w-3.5 h-3.5" />
                      {savingProfile ? "..." : "Guardar"}
                    </button>
                  </div>
                </form>
              )}
            </div>

            {/* TABLA DE TENENCIAS CONSOLIDADAS Y PPP */}
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <div className="px-5 py-3.5 border-b border-gray-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <PieChart className="w-4 h-4 text-orange-500" />
                  <h2 className="text-sm font-bold text-gray-900">
                    Tenencias Activas & Precio Promedio Ponderado (PPP)
                  </h2>
                </div>
                <span className="text-[11px] text-gray-400">
                  Clic en un ticker para abrir su análisis fundamental
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200 text-[11px] font-semibold uppercase text-gray-500">
                      <th className="py-2.5 px-4">Ticker</th>
                      <th className="py-2.5 px-4 text-right">Nominales</th>
                      <th className="py-2.5 px-4 text-right">PPP</th>
                      <th className="py-2.5 px-4 text-right">Precio Actual</th>
                      <th className="py-2.5 px-4 text-right">Costo Total</th>
                      <th className="py-2.5 px-4 text-right">Valor Mercado</th>
                      <th className="py-2.5 px-4 text-right">G/P No Realizada</th>
                      <th className="py-2.5 px-4 text-right">Peso %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {holdings.length === 0 ? (
                      <tr>
                        <td
                          colSpan={8}
                          className="py-8 text-center text-gray-400"
                        >
                          No hay posiciones abiertas en esta cartera.
                        </td>
                      </tr>
                    ) : (
                      holdings.map((h) => {
                        const isPositive = h.unrealized_pnl >= 0;
                        return (
                          <tr key={h.ticker} className="hover:bg-gray-50/80">
                            <td className="py-3 px-4">
                              <button
                                type="button"
                                onClick={() =>
                                  onSelectCompany && onSelectCompany(h.ticker)
                                }
                                className="inline-flex items-center gap-1 font-bold text-orange-600 hover:underline cursor-pointer"
                              >
                                {h.ticker}
                                <ExternalLink className="w-3 h-3" />
                              </button>
                            </td>
                            <td className="py-3 px-4 text-right font-medium text-gray-900">
                              {formatQty(h.quantity)}
                            </td>
                            <td className="py-3 px-4 text-right font-semibold text-gray-800">
                              {formatCurrency(h.ppp, currency)}
                            </td>
                            <td className="py-3 px-4 text-right text-gray-800">
                              {formatCurrency(h.current_price, currency)}
                            </td>
                            <td className="py-3 px-4 text-right text-gray-600">
                              {formatCurrency(h.total_cost, currency)}
                            </td>
                            <td className="py-3 px-4 text-right font-bold text-gray-900">
                              {formatCurrency(h.market_value, currency)}
                            </td>
                            <td
                              className={`py-3 px-4 text-right font-semibold ${
                                isPositive ? "text-emerald-600" : "text-red-600"
                              }`}
                            >
                              {formatCurrency(h.unrealized_pnl, currency)} (
                              {isPositive ? "+" : ""}
                              {h.unrealized_pnl_pct.toFixed(2)}%)
                            </td>
                            <td className="py-3 px-4 text-right">
                              <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-700 font-semibold">
                                {h.weight_pct.toFixed(1)}%
                              </span>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* REGISTRO DE OPERACIÓN (TITULAR O EJECUTIVO ASIGNADO) */}
            {canEdit && (
              <form
                onSubmit={handleAddTransaction}
                className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 space-y-4"
              >
                <div className="flex items-center gap-2">
                  <PlusCircle className="w-4 h-4 text-orange-500" />
                  <h3 className="text-sm font-bold text-gray-900">
                    Registrar Nueva Operación en Cartera
                  </h3>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                      Tipo
                    </label>
                    <select
                      value={txType}
                      onChange={(e) => handleTxTypeChange(e.target.value)}
                      className="w-full px-2.5 py-2 text-xs bg-gray-50 text-gray-900 border border-gray-300 rounded-lg focus:outline-none focus:border-orange-500"
                    >
                      <option value="BUY">Compra (BUY)</option>
                      <option value="SELL">Venta (SELL)</option>
                      <option value="DIVIDEND">Dividendo</option>
                      <option value="DEPOSIT">Depósito Caja</option>
                      <option value="WITHDRAWAL">Retiro Caja</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                      Ticker
                    </label>
                    <input
                      type="text"
                      value={ticker}
                      onChange={(e) => handleTickerInputChange(e.target.value)}
                      disabled={!requiresTicker}
                      required={requiresTicker}
                      placeholder={requiresTicker ? "Ej: MSFT" : "N/A"}
                      className="w-full px-2.5 py-2 text-xs bg-gray-50 text-gray-900 placeholder:text-gray-400 border border-gray-300 rounded-lg disabled:opacity-50 focus:outline-none focus:border-orange-500"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                      Fecha
                    </label>
                    <input
                      type="date"
                      value={txDate}
                      onChange={(e) => setTxDate(e.target.value)}
                      required
                      className="w-full px-2.5 py-2 text-xs bg-gray-50 text-gray-900 border border-gray-300 rounded-lg focus:outline-none focus:border-orange-500"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                      Cantidad
                    </label>
                    <input
                      type="number"
                      step="any"
                      min="0.0001"
                      value={quantity}
                      onChange={(e) => setQuantity(e.target.value)}
                      required
                      placeholder="10"
                      className="w-full px-2.5 py-2 text-xs bg-gray-50 text-gray-900 placeholder:text-gray-400 border border-gray-300 rounded-lg focus:outline-none focus:border-orange-500"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                      Precio Unit.
                    </label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      value={unitPrice}
                      onChange={(e) => setUnitPrice(e.target.value)}
                      required
                      placeholder="415.50"
                      className="w-full px-2.5 py-2 text-xs bg-gray-50 text-gray-900 placeholder:text-gray-400 border border-gray-300 rounded-lg focus:outline-none focus:border-orange-500"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                      Comisión
                    </label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      value={commission}
                      onChange={(e) => setCommission(e.target.value)}
                      placeholder="0.00"
                      className="w-full px-2.5 py-2 text-xs bg-gray-50 text-gray-900 placeholder:text-gray-400 border border-gray-300 rounded-lg focus:outline-none focus:border-orange-500"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                      Nota opcional
                    </label>
                    <input
                      type="text"
                      value={txNotes}
                      onChange={(e) => setTxNotes(e.target.value)}
                      placeholder="Ej: 1er tramo"
                      className="w-full px-2.5 py-2 text-xs bg-gray-50 text-gray-900 placeholder:text-gray-400 border border-gray-300 rounded-lg focus:outline-none focus:border-orange-500"
                    />
                  </div>
                </div>

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={submittingTx || !activeClientId}
                    className="px-4 py-2 bg-[#ff6600] hover:bg-[#e55a00] text-white text-xs font-semibold rounded-lg disabled:opacity-60 cursor-pointer"
                  >
                    {submittingTx ? "Registrando..." : "Cargar operación"}
                  </button>
                </div>
              </form>
            )}

            {/* HISTORIAL DE MOVIMIENTOS */}
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <div className="px-5 py-3.5 border-b border-gray-200 flex items-center gap-2">
                <History className="w-4 h-4 text-gray-500" />
                <h2 className="text-sm font-bold text-gray-900">
                  Historial de Operaciones ({transactions.length})
                </h2>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200 text-[11px] font-semibold uppercase text-gray-500">
                      <th className="py-2.5 px-4">Fecha</th>
                      <th className="py-2.5 px-4">Tipo</th>
                      <th className="py-2.5 px-4">Activo</th>
                      <th className="py-2.5 px-4 text-right">Cantidad</th>
                      <th className="py-2.5 px-4 text-right">Precio Unit.</th>
                      <th className="py-2.5 px-4 text-right">Comisión</th>
                      <th className="py-2.5 px-4 text-right">Monto Bruto</th>
                      <th className="py-2.5 px-4">Nota</th>
                      {canEdit && <th className="py-2.5 px-4 text-right">Acción</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {transactions.length === 0 ? (
                      <tr>
                        <td
                          colSpan={canEdit ? 9 : 8}
                          className="py-8 text-center text-gray-400"
                        >
                          Aún no se registraron movimientos en esta cuenta.
                        </td>
                      </tr>
                    ) : (
                      transactions.map((tx) => {
                        const meta =
                          TX_TYPE_META[tx.tx_type] || TX_TYPE_META.BUY;
                        return (
                          <tr key={tx.id} className="hover:bg-gray-50/80">
                            <td className="py-2.5 px-4 text-gray-700 font-medium">
                              {tx.tx_date}
                            </td>
                            <td className="py-2.5 px-4">
                              <span
                                className={`inline-block px-2 py-0.5 rounded border text-[11px] font-semibold ${meta.badge}`}
                              >
                                {meta.label}
                              </span>
                            </td>
                            <td className="py-2.5 px-4 font-bold text-gray-900">
                              {tx.ticker || "CAJA"}
                            </td>
                            <td className="py-2.5 px-4 text-right text-gray-800">
                              {formatQty(tx.quantity)}
                            </td>
                            <td className="py-2.5 px-4 text-right text-gray-800">
                              {formatCurrency(tx.unit_price, tx.currency)}
                            </td>
                            <td className="py-2.5 px-4 text-right text-gray-500">
                              {formatCurrency(tx.commission, tx.currency)}
                            </td>
                            <td className="py-2.5 px-4 text-right font-semibold text-gray-900">
                              {formatCurrency(tx.gross_amount, tx.currency)}
                            </td>
                            <td className="py-2.5 px-4 text-gray-500">
                              {tx.notes || "-"}
                            </td>
                            {canEdit && (
                              <td className="py-2.5 px-4 text-right">
                                <button
                                  type="button"
                                  onClick={() => handleDeleteTransaction(tx.id)}
                                  title="Eliminar operación"
                                  className="p-1 text-gray-400 hover:text-red-600 cursor-pointer"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            )}
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )
      )}

      {/* MODAL CREAR CARTERA MANUAL DE CLIENTE */}
      {showNewClientModal && isAdvisorOrAdmin && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-gray-200 shadow-2xl w-full max-w-md overflow-hidden text-xs">
            <div className="px-5 py-3.5 bg-[#252526] text-white flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold">Nueva Cartera de Cliente</h4>
                <p className="text-[11px] text-gray-400">
                  Para seguimiento manual (no requiere cuenta registrada)
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowNewClientModal(false)}
                className="text-gray-400 hover:text-white cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateManagedClient} className="p-5 space-y-3.5">
              <div>
                <label className="block font-semibold text-gray-700 mb-1">
                  Nombre completo *
                </label>
                <input
                  type="text"
                  required
                  value={newClientName}
                  onChange={(e) => setNewClientName(e.target.value)}
                  placeholder="Ej: Juan Pérez"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-900 focus:outline-none focus:border-orange-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Email (opcional)
                  </label>
                  <input
                    type="email"
                    value={newClientEmail}
                    onChange={(e) => setNewClientEmail(e.target.value)}
                    placeholder="cliente@correo.com"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-900 focus:outline-none focus:border-orange-500"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Teléfono (opcional)
                  </label>
                  <input
                    type="text"
                    value={newClientPhone}
                    onChange={(e) => setNewClientPhone(e.target.value)}
                    placeholder="+54 9 ..."
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-900 focus:outline-none focus:border-orange-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Riesgo
                  </label>
                  <select
                    value={newClientRisk}
                    onChange={(e) => setNewClientRisk(e.target.value)}
                    className="w-full px-2 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-900 focus:outline-none focus:border-orange-500"
                  >
                    <option value="conservador">Conservador</option>
                    <option value="moderado">Moderado</option>
                    <option value="agresivo">Agresivo</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Horizonte
                  </label>
                  <select
                    value={newClientHorizon}
                    onChange={(e) => setNewClientHorizon(e.target.value)}
                    className="w-full px-2 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-900 focus:outline-none focus:border-orange-500"
                  >
                    <option value="corto_plazo">Corto</option>
                    <option value="mediano_plazo">Mediano</option>
                    <option value="largo_plazo">Largo</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Moneda
                  </label>
                  <select
                    value={newClientCurrency}
                    onChange={(e) => setNewClientCurrency(e.target.value)}
                    className="w-full px-2 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-900 focus:outline-none focus:border-orange-500"
                  >
                    <option value="USD">USD</option>
                    <option value="ARS">ARS</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-gray-700 mb-1">
                  Notas (opcional)
                </label>
                <input
                  type="text"
                  value={newClientNotes}
                  onChange={(e) => setNewClientNotes(e.target.value)}
                  placeholder="Objetivos, perfil, comentarios..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-900 focus:outline-none focus:border-orange-500"
                />
              </div>

              <div className="pt-3 border-t border-gray-200 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowNewClientModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={creatingClient}
                  className="px-4 py-1.5 rounded-lg bg-[#ff6600] hover:bg-[#e55a00] text-white font-semibold cursor-pointer disabled:opacity-50"
                >
                  {creatingClient ? "Creando..." : "Crear cartera"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}