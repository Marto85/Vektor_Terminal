import { Fragment, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Loader2,
  Calculator,
  RotateCcw,
  AlertTriangle,
  Info,
  TrendingUp,
  TrendingDown,
  Minus,
  Building2,
  ExternalLink,
  Landmark,
  Users,
} from 'lucide-react';
import { getGlossaryEntry } from '../data/metricsGlossary';

function formatMult(val, suffix = 'x') {
  if (val === null || val === undefined || Number.isNaN(val)) return '-';
  const isNeg = val < 0;
  const formatted = new Intl.NumberFormat('es-AR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(val));
  const text = `${formatted}${suffix}`;
  return isNeg ? `(${text})` : text;
}

function formatMoney(val) {
  if (val === null || val === undefined || Number.isNaN(val)) return '-';
  const isNeg = val < 0;
  const formatted = new Intl.NumberFormat('es-AR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(val));
  return isNeg ? `(US$ ${formatted})` : `US$ ${formatted}`;
}

export default function ValuationTab({ ticker, onOpenInfo }) {
  const [valData, setValData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [subTab, setSubTab] = useState('multiplos'); // 'multiplos' | 'competidores'
  const [peersData, setPeersData] = useState(null);
  const [peersLoading, setPeersLoading] = useState(false);
  const [peersError, setPeersError] = useState(null);

  // Supuestos editables del DCF en 2 etapas (Empresas Estándar)
  const [revGrowth, setRevGrowth] = useState(11.0);
  const [wacc, setWacc] = useState(9.0);
  const [terminalGrowth, setTerminalGrowth] = useState(3.0);
  const [capexStage1Pct, setCapexStage1Pct] = useState(15.0);
  const [capexTerminalPct, setCapexTerminalPct] = useState(10.0);
  const [exitMultiple, setExitMultiple] = useState(25.0);
  const [extraAdjustmentMm, setExtraAdjustmentMm] = useState(0);

  // Supuestos editables del Modelo Excess Return (Bancos y Financieras)
  const [bankRoe, setBankRoe] = useState(15.0);
  const [bankKe, setBankKe] = useState(9.5);
  const [bankPayout, setBankPayout] = useState(35.0);
  const [bankExitPtbv, setBankExitPtbv] = useState(1.8);

  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;

    const fetchValuation = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await axios.get(
          `http://127.0.0.1:8000/api/v1/company/${ticker.toUpperCase()}/valuation`
        );
        if (!cancelled) {
          setValData(res.data);
          const inp = res.data?.dcf_inputs;
          if (inp) {
            setRevGrowth(Number(inp.recommended_rev_growth_pct ?? 11.0));
            setWacc(Number(inp.suggested_wacc_pct ?? 9.0));
            setCapexStage1Pct(Number(inp.capex_expansion_pct || 12.0));
            setCapexTerminalPct(Number(inp.capex_maintenance_pct || 8.0));
            setExitMultiple(Number(inp.exit_multiple_default || 22.0));
            setExtraAdjustmentMm(0);
          }
          const finInp = res.data?.financial_sector_inputs;
          if (finInp) {
            setBankRoe(Number(finInp.roe_pct ?? 15.0));
            setBankKe(Number(finInp.cost_of_equity_pct ?? 9.5));
            setBankPayout(Number(finInp.payout_ratio_pct ?? 35.0));
            setBankExitPtbv(Number(finInp.exit_ptbv_default ?? 1.8));
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || 'No se pudo calcular la valoración');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchValuation();
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  useEffect(() => {
    if (!ticker || subTab !== 'competidores') return;
    const upperTicker = ticker.toUpperCase();
    if (peersData?.ticker === upperTicker) return;

    let cancelled = false;

    const fetchPeers = async () => {
      setPeersLoading(true);
      setPeersError(null);
      try {
        const res = await axios.get(
          `http://127.0.0.1:8000/api/v1/company/${upperTicker}/peers`
        );
        if (!cancelled) {
          setPeersData(res.data);
        }
      } catch (err) {
        if (!cancelled) {
          setPeersError(err.response?.data?.detail || 'No se pudieron cargar los competidores');
        }
      } finally {
        if (!cancelled) {
          setPeersLoading(false);
        }
      }
    };

    fetchPeers();
    return () => {
      cancelled = true;
    };
  }, [ticker, subTab, peersData]);

  // Cálculo DCF 2 Etapas + Curva dinámica de márgenes + Doble Valor Terminal
  const dcfResult = useMemo(() => {
    const inp = valData?.dcf_inputs;
    if (!inp || !inp.shares_mm || inp.shares_mm <= 0) return null;

    const rev0 = Number(inp.revenue_base_mm || 0);
    const baseEbitMargin = Number(inp.ebit_margin_pct || 15.0) / 100;
    const marginStep = Number(inp.margin_step_pct_yr || 0) / 100;
    const taxRate = Number(inp.tax_rate_pct || 21.0) / 100;
    const daPct = Number(inp.da_sales_pct || 8.0) / 100;

    const g = revGrowth / 100;
    const r = wacc / 100;
    const gTerm = terminalGrowth / 100;
    const capex1 = capexStage1Pct / 100;
    const capexTerm = capexTerminalPct / 100;

    if (r <= gTerm || rev0 <= 0) {
      return { invalidSpread: true };
    }

    const projections = [];
    let pvStage1 = 0;
    let revCurr = rev0;
    let marginCurr = baseEbitMargin;

    for (let yr = 1; yr <= 5; yr += 1) {
      revCurr = revCurr * (1 + g);
      // Evolución gradual del margen operativo según señal de apalancamiento del consenso
      marginCurr = Math.min(Math.max(marginCurr + marginStep, 0.02), 0.65);

      const nopat = revCurr * marginCurr * (1 - taxRate);
      const da = revCurr * daPct;
      const capex = revCurr * capex1;
      const fcf = nopat + da - capex + Number(extraAdjustmentMm || 0);
      const pv = fcf / (1 + r) ** yr;
      pvStage1 += pv;

      projections.push({
        year: `Año +${yr}`,
        rev: revCurr,
        ebitMarginPct: marginCurr * 100,
        fcf,
        pv,
      });
    }

    // Año 6 (Estado Estacionario): el CapEx converge a mantenimiento
    const revYear6 = revCurr * (1 + gTerm);
    const nopat6 = revYear6 * marginCurr * (1 - taxRate);
    const da6 = revYear6 * daPct;
    const capex6 = revYear6 * capexTerm;
    const steadyStateFcf6 = nopat6 + da6 - capex6 + Number(extraAdjustmentMm || 0);

    // Método A: Perpetuidad de Gordon Growth
    const tvGordon = steadyStateFcf6 / (r - gTerm);
    const pvTvGordon = tvGordon / (1 + r) ** 5;
    const evGordon = pvStage1 + pvTvGordon;
    const eqGordon = evGordon - Number(inp.net_debt_mm || 0);
    const priceGordon = eqGordon / inp.shares_mm;
    const impliedExitMult = steadyStateFcf6 > 0 ? tvGordon / steadyStateFcf6 : 0;
    const upsideGordon =
      inp.current_price > 0 ? ((priceGordon - inp.current_price) / inp.current_price) * 100 : 0;

    // Método B: Múltiplo de Salida (Exit Multiple sobre FCF normalizado Año 5)
    const normalizedFcf5 =
      revCurr * (marginCurr * (1 - taxRate) + daPct - capexTerm) + Number(extraAdjustmentMm || 0);
    const tvMultiple = normalizedFcf5 * exitMultiple;
    const pvTvMultiple = tvMultiple / (1 + r) ** 5;
    const evMultiple = pvStage1 + pvTvMultiple;
    const eqMultiple = evMultiple - Number(inp.net_debt_mm || 0);
    const priceMultiple = eqMultiple / inp.shares_mm;
    const upsideMultiple =
      inp.current_price > 0 ? ((priceMultiple - inp.current_price) / inp.current_price) * 100 : 0;

    // Comparación Reportado sin normalizar CapEx (para mostrar impacto)
    const fcf5Unadjusted = projections[4]?.fcf || 0;
    const tvUnadj = (fcf5Unadjusted * (1 + gTerm)) / (r - gTerm);
    const priceUnadjusted =
      (pvStage1 + tvUnadj / (1 + r) ** 5 - Number(inp.net_debt_mm || 0)) / inp.shares_mm;

    return {
      invalidSpread: false,
      projections,
      pvStage1,
      steadyStateFcf6,
      finalMarginPct: marginCurr * 100,
      priceGordon,
      upsideGordon,
      impliedExitMult,
      evGordon,
      priceMultiple,
      upsideMultiple,
      evMultiple,
      priceUnadjusted,
    };
  }, [valData, revGrowth, wacc, terminalGrowth, capexStage1Pct, capexTerminalPct, exitMultiple, extraAdjustmentMm]);

  // Cálculo Modelo Excess Return (Bancos y Entidades Financieras)
  const bankResult = useMemo(() => {
    const fInp = valData?.financial_sector_inputs;
    if (!fInp || !fInp.bvps || fInp.bvps <= 0) return null;

    const roe = bankRoe / 100;
    const ke = bankKe / 100;
    const payout = bankPayout / 100;
    const retention = 1 - payout;

    // Crecimiento sostenible interno: g = ROE * tasa de retención (topeado al 8% en terminal)
    const gStage1 = Math.min(Math.max(roe * retention, 0.01), 0.14);
    const gTerminal = Math.min(gStage1, 0.045);

    if (ke <= gTerminal) {
      return { invalidSpread: true };
    }

    let bvCurr = Number(fInp.bvps);
    let pvExcessSum = 0;
    let pvDividendsSum = 0;
    const rows = [];

    for (let yr = 1; yr <= 5; yr += 1) {
      const eps = bvCurr * roe;
      const dividend = eps * payout;
      const equityCharge = bvCurr * ke;
      const excessReturn = eps - equityCharge;
      const pvExcess = excessReturn / (1 + ke) ** yr;
      pvExcessSum += pvExcess;
      pvDividendsSum += dividend / (1 + ke) ** yr;

      rows.push({
        year: `Año +${yr}`,
        bvps: bvCurr,
        eps,
        excessReturn,
        pvExcess,
      });

      bvCurr = bvCurr * (1 + gStage1);
    }

    // Valor Terminal de Retorno Excedente (convergencia gradual de ROE hacia Ke + spread moderado)
    const terminalRoe = ke + (roe - ke) * 0.5;
    const terminalExcess = bvCurr * (terminalRoe - ke);
    const tvExcess = terminalExcess / (ke - gTerminal);
    const pvTvExcess = tvExcess / (1 + ke) ** 5;

    // Método 1: Excess Return Intrínseco (BVPS inicial + VP Retornos Excedentes)
    const priceExcessReturn = Number(fInp.bvps) + pvExcessSum + pvTvExcess;
    const upsideExcess =
      fInp.current_price > 0 ? ((priceExcessReturn - fInp.current_price) / fInp.current_price) * 100 : 0;

    // Método 2: Múltiplo P/TBV proyectado al Año 5 + Dividendos acumulados descontados
    const tbvRatio = fInp.bvps > 0 ? Number(fInp.tbvps || fInp.bvps) / Number(fInp.bvps) : 1;
    const tbvpsYr5 = bvCurr * tbvRatio;
    const pricePtbvExit = pvDividendsSum + (tbvpsYr5 * bankExitPtbv) / (1 + ke) ** 5;
    const upsidePtbv =
      fInp.current_price > 0 ? ((pricePtbvExit - fInp.current_price) / fInp.current_price) * 100 : 0;

    return {
      invalidSpread: false,
      rows,
      gStage1Pct: gStage1 * 100,
      pvExcessSum,
      pvTvExcess,
      priceExcessReturn,
      upsideExcess,
      impliedPb: fInp.bvps > 0 ? priceExcessReturn / fInp.bvps : 0,
      pricePtbvExit,
      upsidePtbv,
    };
  }, [valData, bankRoe, bankKe, bankPayout, bankExitPtbv]);

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm py-20 flex flex-col items-center justify-center text-orange-500">
        <Loader2 className="w-8 h-8 mb-3 animate-spin" />
        <p className="text-sm font-medium">Auditando estados contables, consenso y perfil sectorial...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm py-16 text-center text-red-500 text-sm font-semibold">
        {error}
      </div>
    );
  }

  if (!valData) return null;

  const years = valData.years || [];
  const rows = valData.rows || [];
  const inp = valData.dcf_inputs || {};
  const finInp = valData.financial_sector_inputs || {};
  const audit = valData.audit || { has_anomalies: false, flags: [], comparisons: [] };
  const trajectory = valData.trajectory || {};
  const routing = valData.sector_routing || { profile: 'standard', label: 'Corporativo Estándar' };
  const classification = valData.classification || {};
  const isFinancial = routing.profile === 'financial';

  const handleResetStandard = () => {
    setRevGrowth(Number(inp.recommended_rev_growth_pct ?? 11.0));
    setWacc(Number(inp.suggested_wacc_pct ?? 9.0));
    setTerminalGrowth(3.0);
    setCapexStage1Pct(Number(inp.capex_expansion_pct || 12.0));
    setCapexTerminalPct(Number(inp.capex_maintenance_pct || 8.0));
    setExitMultiple(Number(inp.exit_multiple_default || 22.0));
    setExtraAdjustmentMm(0);
  };

  const handleResetBank = () => {
    setBankRoe(Number(finInp.roe_pct ?? 15.0));
    setBankKe(Number(finInp.cost_of_equity_pct ?? 9.5));
    setBankPayout(Number(finInp.payout_ratio_pct ?? 35.0));
    setBankExitPtbv(Number(finInp.exit_ptbv_default ?? 1.8));
  };

  const marginDeltas = trajectory.margin_deltas || {};
  const consensusRows = trajectory.consensus_rows || [];
  const sec8kFilings = trajectory.sec_8k_filings || [];

  const activePeersData =
    peersData && peersData.ticker === ticker?.toUpperCase() ? peersData : null;

  const peerColumns = activePeersData?.is_financial
    ? [
        { key: 'market_cap_mm', label: 'Cap. Bursátil (MM)', type: 'money' },
        { key: 'pe_ltm', label: 'P/E LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'pe_ntm', label: 'P/E NTM', type: 'mult', lowerIsCheaper: true },
        { key: 'pb_ltm', label: 'P/BV LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'roe_pct', label: 'ROE LTM', type: 'pct' },
        { key: 'net_margin_pct', label: 'Margen Neto', type: 'pct' },
        { key: 'rev_growth_yoy_pct', label: 'Crec. Ingresos', type: 'pct' },
        { key: 'upside_ws_pct', label: 'Potencial WS', type: 'pct' },
      ]
    : [
        { key: 'market_cap_mm', label: 'Cap. Bursátil (MM)', type: 'money' },
        { key: 'ev_sales_ltm', label: 'EV/Ventas LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'ev_sales_ntm', label: 'EV/Ventas NTM', type: 'mult', lowerIsCheaper: true },
        { key: 'ev_ebitda_ltm', label: 'EV/EBITDA LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'pe_ltm', label: 'P/E LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'pe_ntm', label: 'P/E NTM', type: 'mult', lowerIsCheaper: true },
        { key: 'pb_ltm', label: 'P/BV LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'p_fcf_ltm', label: 'P/FCF LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'ebit_margin_pct', label: 'Margen EBIT', type: 'pct' },
        { key: 'roic_pct', label: 'ROIC', type: 'pct' },
        { key: 'rev_growth_yoy_pct', label: 'Crec. Ventas', type: 'pct' },
      ];

  const formatPeerCell = (val, type) => {
    if (val === null || val === undefined || Number.isNaN(val)) return '-';
    if (type === 'money') {
      return new Intl.NumberFormat('es-AR', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(val);
    }
    if (type === 'pct') return formatMult(val, '%');
    return formatMult(val, 'x');
  };

  return (
    <div className="space-y-6">
      {/* SUB-NAVEGACIÓN DE VALORACIÓN (Estilo TIKR: Múltiplos vs. Competidores) */}
      <div className="flex border-b border-gray-200 space-x-6 px-2">
        <button
          type="button"
          onClick={() => setSubTab('multiplos')}
          className={`pb-2.5 text-sm transition-colors relative flex items-center gap-1.5 ${
            subTab === 'multiplos'
              ? 'text-orange-500 font-semibold cursor-default'
              : 'text-gray-500 hover:text-gray-800 font-medium cursor-pointer'
          }`}
        >
          <Calculator className="w-3.5 h-3.5" />
          Múltiplos y Modelo
          {subTab === 'multiplos' && (
            <span className="absolute -bottom-px left-0 w-full h-0.5 bg-orange-500"></span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setSubTab('competidores')}
          className={`pb-2.5 text-sm transition-colors relative flex items-center gap-1.5 ${
            subTab === 'competidores'
              ? 'text-orange-500 font-semibold cursor-default'
              : 'text-gray-500 hover:text-gray-800 font-medium cursor-pointer'
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          Competidores
          {subTab === 'competidores' && (
            <span className="absolute -bottom-px left-0 w-full h-0.5 bg-orange-500"></span>
          )}
        </button>
      </div>

      {subTab === 'competidores' ? (
        peersLoading ? (
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm py-20 flex flex-col items-center justify-center text-orange-500">
            <Loader2 className="w-8 h-8 mb-3 animate-spin" />
            <p className="text-sm font-medium">
              Cargando múltiplos y métricas operativas de competidores del rubro...
            </p>
          </div>
        ) : peersError ? (
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm py-16 text-center text-red-500 text-sm font-semibold">
            {peersError}
          </div>
        ) : activePeersData ? (
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex flex-wrap justify-between items-center gap-2">
              <div>
                <span className="text-sm font-bold text-gray-800">
                  Comparables Sectoriales | {activePeersData.ticker} vs. Pares
                </span>
                {(activePeersData.sector || activePeersData.industry) && (
                  <span className="ml-2 text-xs text-gray-500">
                    ({activePeersData.sector}{activePeersData.industry ? ` · ${activePeersData.industry}` : ''})
                  </span>
                )}
              </div>
              <span className="text-xs text-gray-400 italic">
                Valuación relativa LTM / NTM y márgenes operativos (cifras en USD)
              </span>
            </div>

            <div className="w-full overflow-x-auto">
              <table className="w-full text-[12.5px] text-left whitespace-nowrap">
                <thead>
                  <tr className="bg-[#333333] text-white">
                    <th className="py-2.5 px-3.5 font-bold sticky left-0 bg-[#333333] z-10 min-w-52">
                      Empresa | Ticker
                    </th>
                    <th className="py-2.5 px-3 font-bold text-right">Precio (US$)</th>
                    {peerColumns.map((col) => (
                      <th key={col.key} className="py-2.5 px-3 font-bold text-right">
                        {col.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {/* Fila destacada del ticker analizado */}
                  {activePeersData.base && (
                    <tr className="border-b-2 border-orange-200 bg-orange-50/50 font-semibold">
                      <td className="py-2.5 px-3.5 sticky left-0 bg-orange-50 z-10 text-gray-900 shadow-[1px_0_0_0_#fed7aa]">
                        <span className="font-bold text-orange-600 mr-2">{activePeersData.base.ticker}</span>
                        <span className="text-xs text-gray-700">{activePeersData.base.name}</span>
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-gray-900">
                        {formatMoney(activePeersData.base.price)}
                      </td>
                      {peerColumns.map((col) => (
                        <td key={col.key} className="py-2.5 px-3 text-right tabular-nums text-gray-900">
                          {formatPeerCell(activePeersData.base[col.key], col.type)}
                        </td>
                      ))}
                    </tr>
                  )}

                  {/* Filas de competidores */}
                  {(activePeersData.peers || []).map((peer) => (
                    <tr key={peer.ticker} className="border-b border-gray-100 hover:bg-gray-50 group">
                      <td className="py-2 px-3.5 sticky left-0 bg-white group-hover:bg-gray-50 z-10 shadow-[1px_0_0_0_#f3f4f6]">
                        <span className="font-bold text-gray-900 mr-2">{peer.ticker}</span>
                        <span className="text-xs text-gray-500">{peer.name}</span>
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums text-gray-800">
                        {formatMoney(peer.price)}
                      </td>
                      {peerColumns.map((col) => (
                        <td key={col.key} className="py-2 px-3 text-right tabular-nums text-gray-800">
                          {formatPeerCell(peer[col.key], col.type)}
                        </td>
                      ))}
                    </tr>
                  ))}

                  {/* Promedio Pares */}
                  <tr className="border-t-2 border-gray-300 bg-gray-50 font-semibold text-gray-800">
                    <td className="py-2 px-3.5 sticky left-0 bg-gray-50 z-10 shadow-[1px_0_0_0_#e5e7eb]">
                      Promedio Competidores
                    </td>
                    <td className="py-2 px-3 text-right text-gray-400">-</td>
                    {peerColumns.map((col) => (
                      <td key={col.key} className="py-2 px-3 text-right tabular-nums">
                        {formatPeerCell(activePeersData.peers_avg?.[col.key], col.type)}
                      </td>
                    ))}
                  </tr>

                  {/* Mediana Pares */}
                  <tr className="border-b border-gray-200 bg-gray-100/80 font-bold text-gray-900">
                    <td className="py-2 px-3.5 sticky left-0 bg-gray-100 z-10 shadow-[1px_0_0_0_#e5e7eb]">
                      Mediana Competidores
                    </td>
                    <td className="py-2 px-3 text-right text-gray-400">-</td>
                    {peerColumns.map((col) => (
                      <td key={col.key} className="py-2 px-3 text-right tabular-nums">
                        {formatPeerCell(activePeersData.peers_med?.[col.key], col.type)}
                      </td>
                    ))}
                  </tr>

                  {/* Prima / Descuento relativo de la empresa vs Mediana Pares */}
                  <tr className="bg-white font-bold">
                    <td className="py-2.5 px-3.5 sticky left-0 bg-white z-10 text-gray-700 shadow-[1px_0_0_0_#f3f4f6]">
                      Prima / (Descuento) {activePeersData.ticker} vs. Mediana
                    </td>
                    <td className="py-2.5 px-3 text-right text-gray-400">-</td>
                    {peerColumns.map((col) => {
                      const prem = activePeersData.relative_premium_pct?.[col.key];
                      if (prem === null || prem === undefined) {
                        return (
                          <td key={col.key} className="py-2.5 px-3 text-right text-gray-400">
                            -
                          </td>
                        );
                      }
                      const isFavorable = col.lowerIsCheaper ? prem < 0 : prem > 0;
                      return (
                        <td
                          key={col.key}
                          className={`py-2.5 px-3 text-right tabular-nums ${
                            isFavorable ? 'text-emerald-700' : 'text-[#d93025]'
                          }`}
                        >
                          {prem > 0 ? `+${prem.toFixed(1)}%` : `${prem.toFixed(1)}%`}
                        </td>
                      );
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        ) : null
      ) : (
        <>
          {/* BANNER DE PERFIL SECTORIAL Y METODOLOGÍA ACTIVA */}
          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-start space-x-3">
              <div className="p-2 rounded bg-orange-50 text-orange-600 shrink-0 mt-0.5">
                {isFinancial ? <Landmark className="w-5 h-5" /> : <Building2 className="w-5 h-5" />}
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-orange-600">
                    Perfil Sectorial: {routing.label}
                  </span>
                  {classification.sector && (
                    <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                      {classification.sector} {classification.industry ? `· ${classification.industry}` : ''}
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-600 mt-1">{routing.rationale}</p>
              </div>
            </div>
            <div className="text-right shrink-0">
              <span className="text-[11px] text-gray-400 block">Motor de valoración activo</span>
              <span className="text-xs font-bold text-gray-900">{routing.primary_model}</span>
            </div>
          </div>

          {/* BLOQUE 0: AUDITORÍA AUTOMÁTICA DE DISTORSIONES CONTABLES */}
          {audit.has_anomalies && (
            <div className="bg-amber-50/70 border border-amber-200 rounded-lg p-4 shadow-xs">
              <div className="flex items-start space-x-2.5">
                <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h3 className="text-sm font-bold text-gray-900">
                    Auditoría de Calidad Contable: se detectaron eventos con impacto material en {valData.ticker}
                  </h3>
                  <p className="text-xs text-gray-600 mt-0.5">
                    Los múltiplos reportados oficiales se mantienen intactos en la tabla, pero las siguientes partidas alteran la lectura recurrente:
                  </p>

                  <div className="mt-3 space-y-2">
                    {audit.flags.map((f) => (
                      <div
                        key={f.code}
                        className="bg-white border border-amber-200/80 rounded px-3 py-2 text-xs"
                      >
                        <div className="flex items-center justify-between font-semibold text-gray-900">
                          <span className="flex items-center">
                            <Info className="w-3.5 h-3.5 text-amber-600 mr-1.5" />
                            {f.title}
                          </span>
                          <span className="text-amber-700 tabular-nums">
                            Impacto: {formatMoney(f.impact_mm)} MM
                          </span>
                        </div>
                        <p className="text-gray-600 mt-1 leading-relaxed">{f.detail}</p>
                      </div>
                    ))}
                  </div>

                  {audit.comparisons.length > 0 && (
                    <div className="mt-3 bg-white border border-amber-200/80 rounded overflow-hidden">
                      <table className="w-full text-xs text-left">
                        <thead>
                          <tr className="bg-amber-100/60 text-gray-800 font-semibold">
                            <th className="py-1.5 px-3">Métrica afectada</th>
                            <th className="py-1.5 px-3 text-right">Valor Reportado</th>
                            <th className="py-1.5 px-3 text-right text-emerald-700">Valor Sin Distorsión</th>
                            <th className="py-1.5 px-3">Criterio de ajuste</th>
                          </tr>
                        </thead>
                        <tbody>
                          {audit.comparisons.map((c, i) => (
                            <tr key={i} className="border-t border-amber-100">
                              <td className="py-1.5 px-3 font-medium text-gray-800">{c.metric}</td>
                              <td className="py-1.5 px-3 text-right tabular-nums text-gray-700">{c.reported}</td>
                              <td className="py-1.5 px-3 text-right tabular-nums font-bold text-emerald-700">{c.adjusted}</td>
                              <td className="py-1.5 px-3 text-gray-500">{c.note}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* BLOQUE 1: CONSENSO DE ANALISTAS, TRAYECTORIA DE MÁRGENES Y GUIDANCE SEC 8-K */}
          {(consensusRows.length > 0 || (trajectory.margin_history || []).length > 0) && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Tabla de Consenso Futuro (2/3 ancho) */}
              <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden flex flex-col justify-between">
                <div>
                  <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex justify-between items-center">
                    <span className="text-sm font-bold text-gray-800">
                      Consenso de Wall Street (Ingresos y BPA Esperados)
                    </span>
                    <span className="text-xs text-gray-500">
                      Crecimiento ponderado DCF: <strong className="text-orange-600">{trajectory.recommended_rev_growth_pct}%</strong>
                    </span>
                  </div>

                  {consensusRows.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left whitespace-nowrap">
                        <thead>
                          <tr className="bg-[#333333] text-white">
                            <th className="py-2 px-3.5 font-bold">Período</th>
                            <th className="py-2 px-3 text-right font-bold">Ingresos Est. (MM)</th>
                            <th className="py-2 px-3 text-right font-bold">Crec. Ventas</th>
                            <th className="py-2 px-3 text-right font-bold">BPA Est. (EPS)</th>
                            <th className="py-2 px-3 text-right font-bold">Crec. BPA</th>
                            <th className="py-2 px-3 text-right font-bold">Analistas</th>
                          </tr>
                        </thead>
                        <tbody>
                          {consensusRows.map((c) => (
                            <tr key={c.period_key} className="border-b border-gray-100 hover:bg-gray-50">
                              <td className="py-2 px-3.5 font-medium text-gray-800">{c.period_label}</td>
                              <td className="py-2 px-3 text-right tabular-nums font-semibold text-gray-900">
                                {c.rev_avg_mm !== null ? formatMoney(c.rev_avg_mm) : '-'}
                              </td>
                              <td
                                className={`py-2 px-3 text-right tabular-nums font-semibold ${
                                  (c.rev_growth_pct || 0) >= 0 ? 'text-emerald-700' : 'text-[#d93025]'
                                }`}
                              >
                                {c.rev_growth_pct !== null ? `${c.rev_growth_pct >= 0 ? '+' : ''}${c.rev_growth_pct.toFixed(1)}%` : '-'}
                              </td>
                              <td className="py-2 px-3 text-right tabular-nums font-semibold text-gray-900">
                                {c.eps_avg !== null ? `US$ ${c.eps_avg.toFixed(2)}` : '-'}
                              </td>
                              <td
                                className={`py-2 px-3 text-right tabular-nums font-semibold ${
                                  (c.eps_growth_pct || 0) >= 0 ? 'text-emerald-700' : 'text-[#d93025]'
                                }`}
                              >
                                {c.eps_growth_pct !== null ? `${c.eps_growth_pct >= 0 ? '+' : ''}${c.eps_growth_pct.toFixed(1)}%` : '-'}
                              </td>
                              <td className="py-2 px-3 text-right tabular-nums text-gray-500">
                                {c.eps_analysts || c.rev_analysts || '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="p-6 text-xs text-gray-500">
                      Sin estimaciones de consenso detalladas disponibles para este ticker; se utiliza la trayectoria histórica auditada ({trajectory.hist_avg_growth_pct}%).
                    </div>
                  )}
                </div>

                {/* Enlaces a SEC 8-K Item 2.02 (Guidance y resultados trimestrales) */}
                {sec8kFilings.length > 0 && (
                  <div className="px-4 py-2.5 bg-gray-50 border-t border-gray-200 flex flex-wrap items-center justify-between gap-2 text-xs">
                    <span className="font-semibold text-gray-700">
                      Comunicados SEC 8-K (Ítem 2.02 · Resultados y Guidance):
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {sec8kFilings.map((f, idx) => (
                        <a
                          key={idx}
                          href={f.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center px-2 py-0.5 rounded bg-white border border-gray-300 text-blue-600 hover:text-blue-800 hover:border-blue-400 transition-colors"
                        >
                          {f.form} ({f.filing_date}) <ExternalLink className="w-3 h-3 ml-1" />
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Tarjeta de Evolución de Márgenes y Apalancamiento Operativo (1/3 ancho) */}
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4 flex flex-col justify-between">
                <div>
                  <h4 className="text-sm font-bold text-gray-800 pb-2 border-b border-gray-200">
                    Dinámica de Márgenes (5Y)
                  </h4>

                  <div className="mt-3 space-y-2.5 text-xs">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">Variación Margen Bruto (5Y):</span>
                      <span
                        className={`font-bold tabular-nums ${
                          (marginDeltas.gross_margin_delta_pct || 0) >= 0 ? 'text-emerald-700' : 'text-[#d93025]'
                        }`}
                      >
                        {(marginDeltas.gross_margin_delta_pct || 0) >= 0 ? '+' : ''}
                        {(marginDeltas.gross_margin_delta_pct || 0).toFixed(1)} pp
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">Variación Margen Operativo (5Y):</span>
                      <span
                        className={`font-bold tabular-nums ${
                          (marginDeltas.operating_margin_delta_pct || 0) >= 0 ? 'text-emerald-700' : 'text-[#d93025]'
                        }`}
                      >
                        {(marginDeltas.operating_margin_delta_pct || 0) >= 0 ? '+' : ''}
                        {(marginDeltas.operating_margin_delta_pct || 0).toFixed(1)} pp
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">Variación Margen Neto (5Y):</span>
                      <span
                        className={`font-bold tabular-nums ${
                          (marginDeltas.net_margin_delta_pct || 0) >= 0 ? 'text-emerald-700' : 'text-[#d93025]'
                        }`}
                      >
                        {(marginDeltas.net_margin_delta_pct || 0) >= 0 ? '+' : ''}
                        {(marginDeltas.net_margin_delta_pct || 0).toFixed(1)} pp
                      </span>
                    </div>
                  </div>
                </div>

                <div
                  className={`mt-4 p-3 rounded border text-xs leading-relaxed ${
                    trajectory.leverage_signal === 'expanding'
                      ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                      : trajectory.leverage_signal === 'compressing'
                      ? 'bg-amber-50/70 border-amber-200 text-amber-950'
                      : 'bg-gray-50 border-gray-200 text-gray-700'
                  }`}
                >
                  <div className="flex items-center font-bold mb-1">
                    {trajectory.leverage_signal === 'expanding' ? (
                      <TrendingUp className="w-3.5 h-3.5 mr-1.5 text-emerald-600" />
                    ) : trajectory.leverage_signal === 'compressing' ? (
                      <TrendingDown className="w-3.5 h-3.5 mr-1.5 text-amber-600" />
                    ) : (
                      <Minus className="w-3.5 h-3.5 mr-1.5 text-gray-500" />
                    )}
                    <span>Proyección Operativa</span>
                  </div>
                  <p>{trajectory.leverage_label}</p>
                </div>
              </div>
            </div>
          )}

          {/* BLOQUE 2: TABLA DE MÚLTIPLOS HISTÓRICOS ESTILO TIKR */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex justify-between items-center">
              <span className="text-sm font-bold text-gray-800">
                Múltiplos Históricos de Valoración | {valData.ticker}
              </span>
              <span className="text-xs text-gray-400 italic">
                Cierres anuales cruzados con estados 10-K (SEC) y snapshot LTM
              </span>
            </div>

            <div className="w-full overflow-x-auto">
              <table className="w-full text-[12.5px] text-left whitespace-nowrap">
                <thead>
                  <tr className="bg-[#333333] text-white">
                    <th className="py-2.5 px-3.5 font-bold sticky left-0 bg-[#333333] z-10 min-w-60">
                      Múltiplo | MiTerminal
                    </th>
                    {years.map((y) => (
                      <th key={y} className="py-2.5 px-3 font-bold text-right">
                        {y}
                      </th>
                    ))}
                    <th className="py-2.5 px-3 font-bold text-right bg-[#262626] text-orange-400">
                      Actual (LTM)
                    </th>
                    <th className="py-2.5 px-3 font-bold text-right">Prom. 5Y</th>
                    <th className="py-2.5 px-3 font-bold text-right">Med. 5Y</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, idx) => {
                    const showSection = idx === 0 || row.section !== rows[idx - 1].section;
                    const hasGlossary = Boolean(getGlossaryEntry(row.metric));
                    const formattedLtm = formatMult(row.ltm, row.suffix);

                    return (
                      <Fragment key={row.metric}>
                        {showSection && (
                          <tr className="border-b border-gray-100 bg-gray-50/90">
                            <td
                              colSpan={years.length + 4}
                              className="py-2 px-3.5 font-bold text-gray-900 sticky left-0"
                            >
                              {row.section}
                            </td>
                          </tr>
                        )}
                        <tr className="border-b border-gray-100 hover:bg-gray-50 group">
                          <td className="py-2 px-3.5 sticky left-0 bg-white group-hover:bg-gray-50 z-10 text-gray-700 font-medium shadow-[1px_0_0_0_#f3f4f6]">
                            <div className="flex items-center justify-between gap-1.5">
                              <span className="truncate">{row.metric}</span>
                              {hasGlossary && onOpenInfo && (
                                <button
                                  type="button"
                                  onClick={() => onOpenInfo(row.metric, formattedLtm)}
                                  title="Ver explicación, fórmula y rangos de referencia"
                                  className="text-gray-400 hover:text-orange-500 transition-colors cursor-pointer shrink-0"
                                >
                                  <Info className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </div>
                          </td>
                          {years.map((y) => {
                            const v = row[y];
                            const isNeg = typeof v === 'number' && v < 0;
                            return (
                              <td
                                key={y}
                                className={`py-2 px-3 text-right tabular-nums ${
                                  isNeg ? 'text-[#d93025]' : 'text-gray-800'
                                }`}
                              >
                                {formatMult(v, row.suffix)}
                              </td>
                            );
                          })}
                          <td
                            className={`py-2 px-3 text-right font-bold tabular-nums bg-orange-50/40 ${
                              typeof row.ltm === 'number' && row.ltm < 0
                                ? 'text-[#d93025]'
                                : 'text-gray-900'
                            }`}
                          >
                            {formattedLtm}
                          </td>
                          <td
                            className={`py-2 px-3 text-right tabular-nums ${
                              typeof row.avg_5y === 'number' && row.avg_5y < 0
                                ? 'text-[#d93025]'
                                : 'text-gray-700'
                            }`}
                          >
                            {formatMult(row.avg_5y, row.suffix)}
                          </td>
                          <td
                            className={`py-2 px-3 text-right tabular-nums ${
                              typeof row.med_5y === 'number' && row.med_5y < 0
                                ? 'text-[#d93025]'
                                : 'text-gray-700'
                            }`}
                          >
                            {formatMult(row.med_5y, row.suffix)}
                          </td>
                        </tr>
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* BLOQUE 3: MODELO DE VALORACIÓN INTRÍNSECA ENRUTADO POR SECTOR */}
          {isFinancial ? (
            /* MODELO EXCESS RETURN PARA BANCOS Y FINANCIERAS */
            <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 pb-3 mb-4 border-b border-gray-200">
                <div className="flex items-center space-x-2">
                  <Landmark className="w-4 h-4 text-orange-500" />
                  <h3 className="text-sm font-bold text-gray-900">
                    Modelo Excess Return (Retorno Excedente sobre ROE y Valor Libros)
                  </h3>
                  {onOpenInfo && (
                    <button
                      type="button"
                      onClick={() => onOpenInfo('Excess Return Model (Bancos)', `${finInp.roe_pct}% ROE`)}
                      title="Explicación del modelo bancario Excess Return"
                      className="text-gray-400 hover:text-orange-500 transition-colors cursor-pointer"
                    >
                      <Info className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
                <button
                  onClick={handleResetBank}
                  className="flex items-center text-xs text-gray-600 hover:text-gray-900 border border-gray-300 rounded px-2.5 py-1 cursor-pointer"
                >
                  <RotateCcw className="w-3 h-3 mr-1" /> Restablecer parámetros bancarios
                </button>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Columna 1: Supuestos bancarios */}
                <div className="space-y-4 bg-gray-50 p-4 rounded border border-gray-200/80">
                  <p className="text-xs font-bold uppercase tracking-wider text-gray-600">
                    Parámetros de rentabilidad patrimonial
                  </p>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-600">ROE Esperado (Años 1-5)</span>
                      <span className="font-bold text-gray-900">{bankRoe.toFixed(1)}%</span>
                    </div>
                    <input
                      type="range"
                      min="4"
                      max="30"
                      step="0.5"
                      value={bankRoe}
                      onChange={(e) => setBankRoe(parseFloat(e.target.value))}
                      className="w-full accent-orange-500 cursor-pointer"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-600">Costo del Capital Accionario (Ke)</span>
                      <span className="font-bold text-gray-900">{bankKe.toFixed(1)}%</span>
                    </div>
                    <input
                      type="range"
                      min="6"
                      max="16"
                      step="0.5"
                      value={bankKe}
                      onChange={(e) => setBankKe(parseFloat(e.target.value))}
                      className="w-full accent-orange-500 cursor-pointer"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-600">Tasa de Distribución (Payout Ratio)</span>
                      <span className="font-bold text-gray-900">{bankPayout.toFixed(1)}%</span>
                    </div>
                    <input
                      type="range"
                      min="10"
                      max="80"
                      step="2.5"
                      value={bankPayout}
                      onChange={(e) => setBankPayout(parseFloat(e.target.value))}
                      className="w-full accent-orange-500 cursor-pointer"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-600">Múltiplo P/TBV de Salida (Año 5)</span>
                      <span className="font-bold text-gray-900">{bankExitPtbv.toFixed(2)}x</span>
                    </div>
                    <input
                      type="range"
                      min="0.8"
                      max="3.5"
                      step="0.1"
                      value={bankExitPtbv}
                      onChange={(e) => setBankExitPtbv(parseFloat(e.target.value))}
                      className="w-full accent-orange-500 cursor-pointer"
                    />
                  </div>

                  <div className="pt-2 border-t border-gray-200 space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Valor Libros / Acción (BVPS):</span>
                      <span className="font-semibold text-gray-800">{formatMoney(finInp.bvps)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Valor Tangible / Acción (TBVPS):</span>
                      <span className="font-semibold text-gray-800">{formatMoney(finInp.tbvps)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Mediana ROE 5Y / ROA:</span>
                      <span className="font-semibold text-gray-800">
                        {finInp.roe_hist_med_pct}% / {finInp.roa_pct ?? '-'}%
                      </span>
                    </div>
                  </div>
                </div>

                {/* Columna 2: Proyección de Retorno Excedente por acción */}
                <div className="border border-gray-200 rounded p-4 flex flex-col justify-between">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-gray-600 mb-2">
                      Proyección Excess Return / Acción
                    </p>
                    {bankResult && !bankResult.invalidSpread ? (
                      <div className="space-y-2 text-xs">
                        {bankResult.rows.map((r) => (
                          <div
                            key={r.year}
                            className="flex justify-between py-1 border-b border-gray-100 last:border-0"
                          >
                            <span className="text-gray-600 font-medium">{r.year}</span>
                            <span className="text-gray-500">BVPS: {formatMoney(r.bvps)}</span>
                            <span
                              className={`font-semibold ${
                                r.pvExcess >= 0 ? 'text-emerald-700' : 'text-[#d93025]'
                              }`}
                            >
                              VP Exc: {formatMoney(r.pvExcess)}
                            </span>
                          </div>
                        ))}
                        <div className="pt-2 border-t border-gray-200 flex justify-between font-semibold text-gray-800">
                          <span>VP Retorno Excedente Terminal:</span>
                          <span>{formatMoney(bankResult.pvTvExcess)}</span>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-red-500">
                        El Costo de Equity (Ke) debe superar el crecimiento terminal.
                      </p>
                    )}
                  </div>

                  <div className="pt-3 border-t border-gray-200 text-[11px] text-gray-500">
                    Spread ROE − Ke actual:{' '}
                    <strong className={bankRoe >= bankKe ? 'text-emerald-700' : 'text-[#d93025]'}>
                      {(bankRoe - bankKe >= 0 ? '+' : '') + (bankRoe - bankKe).toFixed(1)}%
                    </strong>{' '}
                    (Crecimiento patrimonial implícito: {bankResult?.gStage1Pct?.toFixed(1) ?? '-'}%)
                  </div>
                </div>

                {/* Columna 3: Triangulación Bancaria */}
                <div className="bg-[#fafafa] border border-gray-200 rounded p-4 flex flex-col justify-between space-y-3">
                  <p className="text-xs font-bold uppercase tracking-wider text-gray-600">
                    Triangulación de Valor Intrínseco
                  </p>

                  {bankResult && !bankResult.invalidSpread ? (
                    <>
                      <div className="bg-white border border-gray-200 rounded p-3">
                        <div className="flex justify-between items-center text-[11px] text-gray-500">
                          <span className="font-semibold text-gray-700">1. Modelo Excess Return</span>
                          <span>P/BV implícito: {bankResult.impliedPb.toFixed(2)}x</span>
                        </div>
                        <div className="flex items-baseline justify-between mt-1">
                          <span className="text-xl font-bold text-gray-900">
                            {formatMoney(bankResult.priceExcessReturn)}
                          </span>
                          <span
                            className={`text-xs font-bold px-2 py-0.5 rounded ${
                              bankResult.upsideExcess >= 0
                                ? 'bg-green-100 text-green-700'
                                : 'bg-red-100 text-[#d93025]'
                            }`}
                          >
                            {bankResult.upsideExcess >= 0 ? '+' : ''}
                            {bankResult.upsideExcess.toFixed(1)}%
                          </span>
                        </div>
                      </div>

                      <div className="bg-white border border-gray-200 rounded p-3">
                        <div className="flex justify-between items-center text-[11px] text-gray-500">
                          <span className="font-semibold text-gray-700">
                            2. Salida P/TBV ({bankExitPtbv.toFixed(2)}x)
                          </span>
                          <span>Descontado a Ke</span>
                        </div>
                        <div className="flex items-baseline justify-between mt-1">
                          <span className="text-xl font-bold text-gray-900">
                            {formatMoney(bankResult.pricePtbvExit)}
                          </span>
                          <span
                            className={`text-xs font-bold px-2 py-0.5 rounded ${
                              bankResult.upsidePtbv >= 0
                                ? 'bg-green-100 text-green-700'
                                : 'bg-red-100 text-[#d93025]'
                            }`}
                          >
                            {bankResult.upsidePtbv >= 0 ? '+' : ''}
                            {bankResult.upsidePtbv.toFixed(1)}%
                          </span>
                        </div>
                      </div>

                      <div className="text-[11px] text-gray-500 border-t border-gray-200 pt-2 flex justify-between">
                        <span>Precio actual / Consenso WS:</span>
                        <span className="font-semibold text-gray-800">
                          {formatMoney(finInp.current_price)} /{' '}
                          {finInp.target_price ? formatMoney(finInp.target_price) : '-'}
                        </span>
                      </div>
                    </>
                  ) : (
                    <p className="text-xs text-gray-500">Ajustá Ke y ROE para calcular.</p>
                  )}
                </div>
              </div>
            </div>
          ) : (
            /* DCF EN 2 ETAPAS PARA EMPRESAS ESTÁNDAR Y CRECIMIENTO */
            <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 pb-3 mb-4 border-b border-gray-200">
                <div className="flex items-center space-x-2">
                  <Calculator className="w-4 h-4 text-orange-500" />
                  <h3 className="text-sm font-bold text-gray-900">
                    Modelo DCF en 2 Etapas (Expansión vs. Estado Estacionario)
                  </h3>
                </div>
                <button
                  onClick={handleResetStandard}
                  className="flex items-center text-xs text-gray-600 hover:text-gray-900 border border-gray-300 rounded px-2.5 py-1 cursor-pointer"
                >
                  <RotateCcw className="w-3 h-3 mr-1" /> Restablecer supuestos SEC + Consenso
                </button>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Columna 1: Supuestos operativos y de CapEx por etapa */}
                <div className="space-y-3.5 bg-gray-50 p-4 rounded border border-gray-200/80">
                  <p className="text-xs font-bold uppercase tracking-wider text-gray-600">
                    Parámetros de proyección
                  </p>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-600">Crecimiento Ingresos (Años 1-5)</span>
                      <span className="font-bold text-gray-900">{revGrowth.toFixed(1)}%</span>
                    </div>
                    <input
                      type="range"
                      min="-5"
                      max="35"
                      step="0.5"
                      value={revGrowth}
                      onChange={(e) => setRevGrowth(parseFloat(e.target.value))}
                      className="w-full accent-orange-500 cursor-pointer"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-600">CapEx Etapa 1 Expansión (% Ventas)</span>
                      <span className="font-bold text-gray-900">{capexStage1Pct.toFixed(1)}%</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="45"
                      step="0.5"
                      value={capexStage1Pct}
                      onChange={(e) => setCapexStage1Pct(parseFloat(e.target.value))}
                      className="w-full accent-orange-500 cursor-pointer"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-600">CapEx Terminal Mantenimiento (% Ventas)</span>
                      <span className="font-bold text-emerald-700">{capexTerminalPct.toFixed(1)}%</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="30"
                      step="0.5"
                      value={capexTerminalPct}
                      onChange={(e) => setCapexTerminalPct(parseFloat(e.target.value))}
                      className="w-full accent-emerald-600 cursor-pointer"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-gray-600">WACC</span>
                        <span className="font-bold text-gray-900">{wacc.toFixed(1)}%</span>
                      </div>
                      <input
                        type="range"
                        min="5"
                        max="18"
                        step="0.5"
                        value={wacc}
                        onChange={(e) => setWacc(parseFloat(e.target.value))}
                        className="w-full accent-orange-500 cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-gray-600">Perpetuidad (g)</span>
                        <span className="font-bold text-gray-900">{terminalGrowth.toFixed(1)}%</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="5.5"
                        step="0.25"
                        value={terminalGrowth}
                        onChange={(e) => setTerminalGrowth(parseFloat(e.target.value))}
                        className="w-full accent-orange-500 cursor-pointer"
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-600">Múltiplo de Salida (EV/FCF Año 5)</span>
                      <span className="font-bold text-gray-900">{exitMultiple.toFixed(1)}x</span>
                    </div>
                    <input
                      type="range"
                      min="8"
                      max="45"
                      step="0.5"
                      value={exitMultiple}
                      onChange={(e) => setExitMultiple(parseFloat(e.target.value))}
                      className="w-full accent-orange-500 cursor-pointer"
                    />
                  </div>

                  <div className="pt-2 border-t border-gray-200 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className="text-gray-600">Ajuste puntual FCF (+/- MM):</span>
                      {onOpenInfo && (
                        <button
                          type="button"
                          onClick={() =>
                            onOpenInfo('Ajuste puntual FCF (+/- MM)', `${extraAdjustmentMm} MM`)
                          }
                          title="Ver ejemplos típicos de cuándo y cómo ingresar un ajuste"
                          className="text-gray-400 hover:text-orange-500 transition-colors cursor-pointer"
                        >
                          <Info className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                    <input
                      type="number"
                      value={extraAdjustmentMm}
                      onChange={(e) => setExtraAdjustmentMm(Number(e.target.value) || 0)}
                      className="w-24 px-2 py-1 border border-gray-300 rounded text-right bg-white font-semibold text-gray-900"
                    />
                  </div>
                </div>

                {/* Columna 2: Flujos proyectados Etapa 1 + Transición Terminal */}
                <div className="border border-gray-200 rounded p-4 flex flex-col justify-between">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-gray-600 mb-2">
                      Proyección de Flujos (MM)
                    </p>
                    {dcfResult && !dcfResult.invalidSpread ? (
                      <div className="space-y-2 text-xs">
                        {dcfResult.projections.map((p) => (
                          <div
                            key={p.year}
                            className="flex justify-between py-1 border-b border-gray-100 last:border-0"
                          >
                            <span className="text-gray-600 font-medium">{p.year}</span>
                            <span className="text-gray-500">FCF: {formatMoney(p.fcf)}</span>
                            <span className="font-semibold text-gray-900">VP: {formatMoney(p.pv)}</span>
                          </div>
                        ))}
                        <div className="pt-2 border-t border-gray-200 flex justify-between text-emerald-700 font-semibold">
                          <span>FCF Estacionario (Año +6):</span>
                          <span>{formatMoney(dcfResult.steadyStateFcf6)} MM</span>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-red-500">
                        El WACC debe superar el crecimiento perpetuo (g).
                      </p>
                    )}
                  </div>

                  <div className="pt-3 border-t border-gray-200 space-y-1 text-[11px] text-gray-500">
                    <div className="flex justify-between">
                      <span>Margen EBIT base → Año 5:</span>
                      <span className="font-semibold text-gray-700">
                        {inp.ebit_margin_pct}% → {dcfResult?.finalMarginPct?.toFixed(1) ?? inp.ebit_margin_pct}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>D&A / Ventas (SEC):</span>
                      <span className="font-semibold text-gray-700">{inp.da_sales_pct}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Deuda neta LTM:</span>
                      <span className="font-semibold text-gray-700">{formatMoney(inp.net_debt_mm)} MM</span>
                    </div>
                  </div>
                </div>

                {/* Columna 3: Doble Valor Terminal simultáneo */}
                <div className="bg-[#fafafa] border border-gray-200 rounded p-4 flex flex-col justify-between space-y-3">
                  <p className="text-xs font-bold uppercase tracking-wider text-gray-600">
                    Triangulación de Valor Intrínseco
                  </p>

                  {dcfResult && !dcfResult.invalidSpread ? (
                    <>
                      {/* Método 1: Perpetuidad de Gordon */}
                      <div className="bg-white border border-gray-200 rounded p-3">
                        <div className="flex justify-between items-center text-[11px] text-gray-500">
                          <span className="font-semibold text-gray-700">
                            1. Perpetuidad (g = {terminalGrowth.toFixed(1)}%)
                          </span>
                          <span>Múltiplo implícito: {dcfResult.impliedExitMult.toFixed(1)}x</span>
                        </div>
                        <div className="flex items-baseline justify-between mt-1">
                          <span className="text-xl font-bold text-gray-900">
                            {formatMoney(dcfResult.priceGordon)}
                          </span>
                          <span
                            className={`text-xs font-bold px-2 py-0.5 rounded ${
                              dcfResult.upsideGordon >= 0
                                ? 'bg-green-100 text-green-700'
                                : 'bg-red-100 text-[#d93025]'
                            }`}
                          >
                            {dcfResult.upsideGordon >= 0 ? '+' : ''}
                            {dcfResult.upsideGordon.toFixed(1)}%
                          </span>
                        </div>
                      </div>

                      {/* Método 2: Múltiplo de Salida */}
                      <div className="bg-white border border-gray-200 rounded p-3">
                        <div className="flex justify-between items-center text-[11px] text-gray-500">
                          <span className="font-semibold text-gray-700">
                            2. Múltiplo de Salida ({exitMultiple.toFixed(1)}x)
                          </span>
                          <span>Ref. histórica</span>
                        </div>
                        <div className="flex items-baseline justify-between mt-1">
                          <span className="text-xl font-bold text-gray-900">
                            {formatMoney(dcfResult.priceMultiple)}
                          </span>
                          <span
                            className={`text-xs font-bold px-2 py-0.5 rounded ${
                              dcfResult.upsideMultiple >= 0
                                ? 'bg-green-100 text-green-700'
                                : 'bg-red-100 text-[#d93025]'
                            }`}
                          >
                            {dcfResult.upsideMultiple >= 0 ? '+' : ''}
                            {dcfResult.upsideMultiple.toFixed(1)}%
                          </span>
                        </div>
                      </div>

                      <div className="text-[11px] text-gray-500 border-t border-gray-200 pt-2 space-y-1">
                        <div className="flex justify-between">
                          <span>Precio actual / Consenso WS:</span>
                          <span className="font-semibold text-gray-800">
                            {formatMoney(inp.current_price)} / {inp.target_price ? formatMoney(inp.target_price) : '-'}
                          </span>
                        </div>
                        {Math.abs(capexStage1Pct - capexTerminalPct) >= 3 && (
                          <div className="flex justify-between text-amber-700">
                            <span>Sin normalizar CapEx terminal:</span>
                            <span className="font-semibold">{formatMoney(dcfResult.priceUnadjusted)}</span>
                          </div>
                        )}
                      </div>
                    </>
                  ) : (
                    <p className="text-xs text-gray-500">Ajustá WACC y crecimiento perpetuo para calcular.</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}