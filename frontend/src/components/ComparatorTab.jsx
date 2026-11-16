import { Fragment, useEffect, useState } from 'react';
import axios from 'axios';
import {
  Search,
  Plus,
  X,
  Loader2,
  Scale,
  Trash2,
  Info,
} from 'lucide-react';
import { getGlossaryEntry } from '../data/metricsGlossary';

const METRIC_SECTIONS = [
  {
    section: 'Mercado y Escala',
    rows: [
      { key: 'price', label: 'Precio Actual (US$)', type: 'money2' },
      { key: 'market_cap_mm', label: 'Capitalización Bursátil (MM)', type: 'money0' },
      { key: 'enterprise_value_mm', label: 'Enterprise Value (MM)', type: 'money0' },
      { key: 'fcf_ltm_mm', label: 'Flujo de Caja Libre LTM (MM)', type: 'money0' },
    ],
  },
  {
    section: 'Múltiplos de Valoración',
    rows: [
      { key: 'pe_ltm', label: 'P/E Ratio (LTM)', type: 'mult', highlightLowest: true },
      { key: 'pe_ntm', label: 'P/E Forward (NTM)', type: 'mult', highlightLowest: true },
      { key: 'ev_ebitda_ltm', label: 'EV / EBITDA (LTM)', type: 'mult', highlightLowest: true },
      { key: 'ev_sales_ltm', label: 'EV / Ventas (LTM)', type: 'mult', highlightLowest: true },
      { key: 'ev_sales_ntm', label: 'EV / Ventas Forward (NTM)', type: 'mult', highlightLowest: true },
      { key: 'pb_ltm', label: 'Precio / Valor Libros (P/BV)', type: 'mult', highlightLowest: true },
      { key: 'p_fcf_ltm', label: 'Precio / Flujo de Caja Libre (P/FCF)', type: 'mult', highlightLowest: true },
      { key: 'fcf_yield_pct', label: 'FCF Yield (FCF / Cap. Bursátil %)', type: 'pct', highlightHighest: true },
    ],
  },
  {
    section: 'Rentabilidad y Eficiencia',
    rows: [
      { key: 'ebit_margin_pct', label: 'Margen Operativo (EBIT %)', type: 'pct', highlightHighest: true },
      { key: 'net_margin_pct', label: 'Margen Neto (%)', type: 'pct', highlightHighest: true },
      { key: 'roe_pct', label: 'Retorno sobre Patrimonio (ROE %)', type: 'pct', highlightHighest: true },
      { key: 'roic_pct', label: 'Retorno sobre Capital Invertido (ROIC %)', type: 'pct', highlightHighest: true },
    ],
  },
  {
    section: 'Crecimiento y Consenso',
    rows: [
      { key: 'rev_growth_yoy_pct', label: 'Crecimiento de Ingresos (YoY %)', type: 'pct', highlightHighest: true },
      { key: 'upside_ws_pct', label: 'Potencial vs. Precio Objetivo WS (%)', type: 'pct', highlightHighest: true },
    ],
  },
];

function formatCellValue(val, type) {
  if (val === null || val === undefined || Number.isNaN(val)) return '-';
  if (val === 'N/M') return 'N/M';
  const isNeg = val < 0;
  const absVal = Math.abs(val);

  if (type === 'money0') {
    const f = new Intl.NumberFormat('es-AR', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(absVal);
    return isNeg ? `(US$ ${f})` : `US$ ${f}`;
  }
  if (type === 'money2') {
    const f = new Intl.NumberFormat('es-AR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(absVal);
    return isNeg ? `(US$ ${f})` : `US$ ${f}`;
  }
  const f = new Intl.NumberFormat('es-AR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(absVal);
  const suffix = type === 'pct' ? '%' : 'x';
  return isNeg ? `(${f}${suffix})` : `${f}${suffix}`;
}

export default function ComparatorTab({ currentTicker, onOpenInfo }) {
  const [selectedTickers, setSelectedTickers] = useState(() =>
    currentTicker ? [currentTicker.toUpperCase()] : ['MSFT']
  );
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);

  const [compData, setCompData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const tickersParam = selectedTickers.join(',');

  useEffect(() => {
    if (!tickersParam) {
      return;
    }

    let cancelled = false;
    const fetchComparison = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await axios.get(
          `http://127.0.0.1:8000/api/v1/compare?tickers=${encodeURIComponent(tickersParam)}`
        );
        if (!cancelled) {
          setCompData(res.data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || 'No se pudo generar la comparativa');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchComparison();
    return () => {
      cancelled = true;
    };
  }, [tickersParam]);

  const handleQueryChange = async (e) => {
    const val = e.target.value;
    setQuery(val);
    if (val.trim().length > 0) {
      try {
        const res = await axios.get(
          `http://127.0.0.1:8000/api/v1/search?q=${encodeURIComponent(val.trim())}`
        );
        setSuggestions(res.data || []);
        setShowDropdown(true);
      } catch {
        setSuggestions([]);
      }
    } else {
      setSuggestions([]);
      setShowDropdown(false);
    }
  };

  const addTicker = (rawTicker) => {
    const sym = String(rawTicker || '').trim().toUpperCase();
    if (!sym) return;
    setQuery('');
    setSuggestions([]);
    setShowDropdown(false);

    setSelectedTickers((prev) => {
      if (prev.includes(sym) || prev.length >= 5) return prev;
      return [...prev, sym];
    });
  };

  const removeTicker = (sym) => {
    setSelectedTickers((prev) => prev.filter((t) => t !== sym));
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && query.trim()) {
      e.preventDefault();
      addTicker(query.trim());
    }
  };

  const activeCompData = selectedTickers.length > 0 ? compData : null;
  const companies = activeCompData?.companies || [];
  const canAddMore = selectedTickers.length < 5;
  const activeUpper = currentTicker?.toUpperCase();
  const canAddActiveTicker = activeUpper && !selectedTickers.includes(activeUpper) && canAddMore;

  return (
    <div className="space-y-6">
      {/* PANEL DE SELECCIÓN MANUAL DE EMPRESAS (HASTA 5) */}
      <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-gray-200">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded bg-orange-50 text-orange-600">
              <Scale className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-gray-900">
                Comparador Manual de Empresas ({selectedTickers.length}/5 seleccionadas)
              </h3>
              <p className="text-xs text-gray-500">
                Elegí hasta 5 tickers de cualquier sector para contrastar múltiplos, márgenes y retorno sobre capital lado a lado.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {canAddActiveTicker && (
              <button
                type="button"
                onClick={() => addTicker(activeUpper)}
                className="flex items-center text-xs px-2.5 py-1.5 rounded border border-orange-300 bg-orange-50 text-orange-700 hover:bg-orange-100 font-medium cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5 mr-1" /> Sumar {activeUpper}
              </button>
            )}
            {selectedTickers.length > 0 && (
              <button
                type="button"
                onClick={() => setSelectedTickers([])}
                className="flex items-center text-xs px-2.5 py-1.5 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5 mr-1" /> Limpiar
              </button>
            )}
          </div>
        </div>

        {/* Buscador + Chips activos */}
        <div className="mt-4 flex flex-col md:flex-row md:items-center gap-4">
          <div className="relative w-full md:w-96 shrink-0">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={handleQueryChange}
              onKeyDown={handleKeyDown}
              onFocus={() => {
                if (suggestions.length > 0) setShowDropdown(true);
              }}
              onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
              disabled={!canAddMore}
              placeholder={
                canAddMore
                  ? 'Agregar empresa (Ej: MELI, NU, AAPL + Enter)'
                  : 'Máximo de 5 empresas alcanzado'
              }
              className="w-full pl-9 pr-3 py-1.5 bg-gray-50 border border-gray-300 rounded text-xs text-gray-900 placeholder-gray-400 focus:outline-none focus:border-orange-500 focus:bg-white disabled:opacity-60"
            />

            {showDropdown && suggestions.length > 0 && canAddMore && (
              <div className="absolute top-full left-0 w-full mt-1 bg-white border border-gray-300 rounded shadow-lg z-30 overflow-hidden">
                {suggestions.map((item, idx) => {
                  const alreadyAdded = selectedTickers.includes(item.ticker?.toUpperCase());
                  return (
                    <div
                      key={idx}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => !alreadyAdded && addTicker(item.ticker)}
                      className={`px-3 py-2 flex items-center justify-between text-xs border-b border-gray-100 last:border-0 ${
                        alreadyAdded
                          ? 'bg-gray-50 text-gray-400 cursor-not-allowed'
                          : 'hover:bg-orange-50 cursor-pointer text-gray-800'
                      }`}
                    >
                      <div className="flex items-center truncate mr-2">
                        <span className="font-bold text-orange-600 w-14 shrink-0">
                          {item.ticker}
                        </span>
                        <span className="truncate">{item.name}</span>
                      </div>
                      <span className="text-[10px] uppercase text-gray-400 shrink-0">
                        {alreadyAdded ? 'Agregada' : item.type}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Chips de tickers seleccionados */}
          <div className="flex flex-wrap items-center gap-2">
            {selectedTickers.map((sym) => (
              <span
                key={sym}
                className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-gray-900 text-white shadow-2xs"
              >
                {sym}
                <button
                  type="button"
                  onClick={() => removeTicker(sym)}
                  title={`Quitar ${sym}`}
                  className="ml-2 text-gray-400 hover:text-orange-400 cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* CONTENIDO DE LA COMPARATIVA */}
      {selectedTickers.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm py-16 text-center text-gray-500 text-sm">
          Seleccioná entre 1 y 5 empresas en el buscador superior para armar la matriz comparativa.
        </div>
      ) : loading ? (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm py-20 flex flex-col items-center justify-center text-orange-500">
          <Loader2 className="w-8 h-8 mb-3 animate-spin" />
          <p className="text-sm font-medium">
            Normalizando estados y múltiplos de {selectedTickers.join(', ')}...
          </p>
        </div>
      ) : error ? (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm py-16 text-center text-red-500 text-sm font-semibold">
          {error}
        </div>
      ) : companies.length > 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          {activeCompData?.missing?.length > 0 && (
            <div className="px-4 py-2 bg-amber-50 border-b border-amber-200 text-xs text-amber-800">
              No se encontraron datos suficientes para: <strong>{activeCompData.missing.join(', ')}</strong>
            </div>
          )}

          <div className="w-full overflow-x-auto">
            <table className="w-full text-[12.5px] text-left whitespace-nowrap">
              <thead>
                <tr className="bg-[#333333] text-white">
                  <th className="py-3 px-4 font-bold sticky left-0 bg-[#333333] z-10 min-w-64">
                    Métrica | Comparativa
                  </th>
                  {companies.map((c) => (
                    <th key={c.ticker} className="py-3 px-4 text-right min-w-36">
                      <div className="font-bold text-orange-400 text-sm">{c.ticker}</div>
                      <div className="text-[11px] font-normal text-gray-300 truncate max-w-36 ml-auto">
                        {c.name}
                      </div>
                    </th>
                  ))}
                  {companies.length > 1 && (
                    <>
                      <th className="py-3 px-4 font-bold text-right bg-[#262626] min-w-28">
                        Promedio
                      </th>
                      <th className="py-3 px-4 font-bold text-right bg-[#262626] text-gray-200 min-w-28">
                        Mediana
                      </th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {/* Fila de contexto sectorial */}
                <tr className="border-b border-gray-200 bg-gray-50/70 text-[11px] text-gray-500">
                  <td className="py-2 px-4 sticky left-0 bg-gray-50 z-10 font-semibold text-gray-700 shadow-[1px_0_0_0_#e5e7eb]">
                    Sector / Industria
                  </td>
                  {companies.map((c) => (
                    <td key={c.ticker} className="py-2 px-4 text-right truncate max-w-40">
                      {c.sector || '-'}
                    </td>
                  ))}
                  {companies.length > 1 && (
                    <>
                      <td className="py-2 px-4 text-right bg-gray-100/60">-</td>
                      <td className="py-2 px-4 text-right bg-gray-100/60">-</td>
                    </>
                  )}
                </tr>

                {METRIC_SECTIONS.map((sec) => (
                  <Fragment key={sec.section}>
                    <tr className="border-b border-gray-100 bg-gray-100/80">
                      <td
                        colSpan={companies.length + (companies.length > 1 ? 3 : 1)}
                        className="py-2 px-4 font-bold text-gray-900 sticky left-0"
                      >
                        {sec.section}
                      </td>
                    </tr>

                    {sec.rows.map((row) => {
                      const validVals = companies
                        .map((c) => c[row.key])
                        .filter((v) => typeof v === 'number' && !Number.isNaN(v));
                      const positiveVals = validVals.filter((v) => v > 0);

                      const bestVal =
                        companies.length > 1
                          ? row.highlightLowest && positiveVals.length > 0
                            ? Math.min(...positiveVals)
                            : row.highlightHighest && validVals.length > 0
                            ? Math.max(...validVals)
                            : null
                          : null;

                      const hasGlossary = Boolean(getGlossaryEntry(row.label));

                      return (
                        <tr
                          key={row.key}
                          className="border-b border-gray-100 hover:bg-gray-50 group"
                        >
                          <td className="py-2.5 px-4 sticky left-0 bg-white group-hover:bg-gray-50 z-10 text-gray-700 font-medium shadow-[1px_0_0_0_#f3f4f6]">
                            <div className="flex items-center justify-between gap-1.5">
                              <span>{row.label}</span>
                              {hasGlossary && onOpenInfo && (
                                <button
                                  type="button"
                                  onClick={() => onOpenInfo(row.label, null)}
                                  title="Ver definición y criterios de interpretación"
                                  className="text-gray-400 hover:text-orange-500 transition-colors cursor-pointer shrink-0"
                                >
                                  <Info className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </div>
                          </td>

                          {companies.map((c) => {
                            const val = c[row.key];
                            const isNotMeaningful = val === 'N/M';
                            const isNeg = typeof val === 'number' && val < 0;
                            const isBest = bestVal !== null && val === bestVal;

                            return (
                              <td
                                key={c.ticker}
                                title={
                                  isNotMeaningful
                                    ? 'No significativo (denominador negativo o nulo en LTM)'
                                    : undefined
                                }
                                className={`py-2.5 px-4 text-right tabular-nums ${
                                  isNotMeaningful
                                    ? 'text-gray-400 italic'
                                    : isBest
                                    ? 'font-bold text-emerald-700 bg-emerald-50/40'
                                    : isNeg
                                    ? 'text-[#d93025]'
                                    : 'text-gray-800'
                                }`}
                              >
                                {formatCellValue(val, row.type)}
                              </td>
                            );
                          })}

                          {companies.length > 1 && (
                            <>
                              <td className="py-2.5 px-4 text-right tabular-nums font-semibold bg-gray-50/80 text-gray-700">
                                {formatCellValue(activeCompData.group_avg?.[row.key], row.type)}
                              </td>
                              <td className="py-2.5 px-4 text-right tabular-nums font-bold bg-gray-100/70 text-gray-900">
                                {formatCellValue(activeCompData.group_med?.[row.key], row.type)}
                              </td>
                            </>
                          )}
                        </tr>
                      );
                    })}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 text-[11px] text-gray-500">
            <strong>N/M</strong>: Múltiplo no significativo (flujo o resultado negativo en LTM; excluido del promedio y mediana). El promedio de múltiplos excluye outliers mayores a 250x.
          </div>
        </div>
      ) : null}
    </div>
  );
}