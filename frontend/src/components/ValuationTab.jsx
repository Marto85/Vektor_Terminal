import { Fragment, useEffect, useState } from 'react';
import axios from 'axios';
import {
  Loader2,
  Calculator,
  AlertTriangle,
  Info,
  TrendingUp,
  TrendingDown,
  Minus,
  Building2,
  ExternalLink,
  Landmark,
  Users,
  ArrowRight,
} from 'lucide-react';
import { getGlossaryEntry } from '../data/metricsGlossary';

function formatMult(val, suffix = 'x') {
  if (val === null || val === undefined || Number.isNaN(val)) return '-';
  if (val === 'N/M') return 'N/M';
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

export default function ValuationTab({ ticker, onOpenInfo, onOpenValuationModels }) {
  const [valData, setValData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [subTab, setSubTab] = useState('multiplos'); // 'multiplos' | 'competidores'
  const [peersData, setPeersData] = useState(null);
  const [peersLoading, setPeersLoading] = useState(false);
  const [peersError, setPeersError] = useState(null);

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
  const audit = valData.audit || { has_anomalies: false, flags: [], comparisons: [] };
  const trajectory = valData.trajectory || {};
  const routing = valData.sector_routing || { profile: 'standard', label: 'Corporativo Estándar' };
  const classification = valData.classification || {};
  const isFinancial = routing.profile === 'financial';

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
        { key: 'fcf_yield_pct', label: 'FCF Yield', type: 'pct' },
        { key: 'ebit_margin_pct', label: 'Margen EBIT', type: 'pct' },
        { key: 'roic_pct', label: 'ROIC', type: 'pct' },
        { key: 'rev_growth_yoy_pct', label: 'Crec. Ventas', type: 'pct' },
      ];

  const formatPeerCell = (val, type) => {
    if (val === null || val === undefined || Number.isNaN(val)) return '-';
    if (val === 'N/M') return 'N/M';
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
      {/* SUB-NAVEGACIÓN DE VALORACIÓN */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 px-2">
        <div className="flex space-x-6">
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
            Múltiplos Históricos y Consenso
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

        {onOpenValuationModels && (
          <button
            type="button"
            onClick={() => onOpenValuationModels(valData.ticker)}
            className="mb-1.5 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold cursor-pointer shadow-2xs"
          >
            <span>Modelar Valor Intrínseco (DCF / Manual)</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        )}
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
                  {activePeersData.base && (
                    <tr className="border-b-2 border-orange-200 bg-orange-50/50 font-semibold">
                      <td className="py-2.5 px-3.5 sticky left-0 bg-orange-50 z-10 text-gray-900 shadow-[1px_0_0_0_#fed7aa]">
                        <span className="font-bold text-orange-600 mr-2">{activePeersData.base.ticker}</span>
                        <span className="text-xs text-gray-700">{activePeersData.base.name}</span>
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-gray-900">
                        {formatMoney(activePeersData.base.price)}
                      </td>
                      {peerColumns.map((col) => {
                        const rawVal = activePeersData.base[col.key];
                        const isNm = rawVal === 'N/M';
                        return (
                          <td
                            key={col.key}
                            title={isNm ? 'No significativo (denominador negativo o nulo en LTM)' : undefined}
                            className={`py-2.5 px-3 text-right tabular-nums ${
                              isNm ? 'text-gray-400 italic font-normal' : 'text-gray-900'
                            }`}
                          >
                            {formatPeerCell(rawVal, col.type)}
                          </td>
                        );
                      })}
                    </tr>
                  )}

                  {(activePeersData.peers || []).map((peer) => (
                    <tr key={peer.ticker} className="border-b border-gray-100 hover:bg-gray-50 group">
                      <td className="py-2 px-3.5 sticky left-0 bg-white group-hover:bg-gray-50 z-10 shadow-[1px_0_0_0_#f3f4f6]">
                        <span className="font-bold text-gray-900 mr-2">{peer.ticker}</span>
                        <span className="text-xs text-gray-500">{peer.name}</span>
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums text-gray-800">
                        {formatMoney(peer.price)}
                      </td>
                      {peerColumns.map((col) => {
                        const rawVal = peer[col.key];
                        const isNm = rawVal === 'N/M';
                        return (
                          <td
                            key={col.key}
                            title={isNm ? 'No significativo (denominador negativo o nulo en LTM)' : undefined}
                            className={`py-2 px-3 text-right tabular-nums ${
                              isNm ? 'text-gray-400 italic' : 'text-gray-800'
                            }`}
                          >
                            {formatPeerCell(rawVal, col.type)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}

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
            <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 text-[11px] text-gray-500">
              <strong>N/M</strong>: Múltiplo no significativo (flujo o resultado negativo en LTM; excluido del promedio y mediana). El promedio de múltiplos excluye outliers mayores a 250x.
            </div>
          </div>
        ) : null
      ) : (
        <>
          {/* BANNER DE PERFIL SECTORIAL */}
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
              <span className="text-[11px] text-gray-400 block">Modelo recomendado</span>
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
                      Múltiplo | Vektor
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
        </>
      )}
    </div>
  );
}