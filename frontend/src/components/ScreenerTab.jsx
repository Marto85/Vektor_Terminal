import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import apiClient from "../api/client";
import { useAuth } from "../context/authStore";
import {
  Filter,
  RefreshCw,
  Download,
  RotateCcw,
  Loader2,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Sparkles,
  Info,
  Layers,
  Columns3,
  Check,
} from 'lucide-react';

const PRESETS = [
  {
    id: 'all',
    label: 'Universo Completo',
    summary: 'Vista integral sin restricciones de todas las empresas sincronizadas en la base local.',
    thesis:
      'Permite explorar libremente el universo de emisores cacheados, ordenar por capitalización o múltiplos y combinar tus propios umbrales en la grilla inferior.',
    criteriaLabel: 'Sin filtros activos (muestra el 100% de la base sincronizada)',
    filters: {},
  },
  {
    id: 'value_contrarian',
    label: 'Value Contrarian',
    summary: 'Empresas castigadas en precio pero respaldadas por generación real de caja y balance sólido.',
    thesis:
      'Identifica compañías donde el mercado descuenta pesimismo de corto plazo (múltiplo P/E comprimido), pero el negocio sigue generando alto flujo de caja libre respecto a su capitalización y mantiene bajo endeudamiento para atravesar el ciclo sin riesgo financiero.',
    criteriaLabel: 'P/E LTM ≤ 18x · FCF Yield ≥ 4,5% · Deuda Neta / EBITDA ≤ 2,5x',
    filters: {
      maxPeLtm: '18',
      minFcfYield: '4.5',
      maxNetDebtEbitda: '2.5',
    },
  },
  {
    id: 'quality_compounders',
    label: 'Quality Compounders',
    summary: 'Negocios con ventajas competitivas durables, altos márgenes y retorno superior sobre el capital.',
    thesis:
      'Filtra compañías capaces de reinvertir sus utilidades a tasas de retorno muy superiores al costo de capital (ROIC alto), con poder de fijación de precios reflejado en márgenes operativos elevados y expansión sostenida de ventas. Excluye entidades financieras donde el ROIC contable no aplica.',
    criteriaLabel: 'ROIC ≥ 15% · Margen EBIT ≥ 20% · Crec. Ventas YoY ≥ 8%',
    filters: {
      minRoic: '15',
      minEbitMargin: '20',
      minRevGrowth: '8',
    },
  },
  {
    id: 'high_fcf',
    label: 'Alto FCF Yield',
    summary: 'Emisores con fuerte capacidad de conversión a caja libre disponible para dividendos, recompras o desapalancamiento.',
    thesis:
      'Prioriza el rendimiento de caja efectiva (FCF LTM / Market Cap) por encima de las utilidades contables, ayudando a detectar negocios maduros o cíclicos con alta capacidad de retorno al accionista.',
    criteriaLabel: 'FCF Yield ≥ 5,5% (FCF LTM positivo)',
    filters: {
      minFcfYield: '5.5',
    },
  },
  {
    id: 'garp',
    label: 'GARP (Crecimiento Razonable)',
    summary: 'Equilibrio entre crecimiento de doble dígito, alta rentabilidad patrimonial y valuación forward acotada.',
    thesis:
      'Basado en la filosofía Growth at a Reasonable Price (Peter Lynch): busca compañías que crecen rápido y son rentables, pero poniendo un techo al múltiplo futuro (P/E NTM) para evitar sobrepagar expectativas excesivas.',
    criteriaLabel: 'P/E Forward (NTM) ≤ 24x · Crec. Ventas YoY ≥ 10% · ROE ≥ 15%',
    filters: {
      maxPeNtm: '24',
      minRevGrowth: '10',
      minRoe: '15',
    },
  },
];

const INITIAL_FILTERS = {
  sector: 'ALL',
  industry: 'ALL',
  search: '',
  minMcap: '',
  maxPeLtm: '',
  maxPeNtm: '',
  maxEvEbitda: '',
  minFcfYield: '',
  minRoic: '',
  minRoe: '',
  minEbitMargin: '',
  minRevGrowth: '',
  maxNetDebtEbitda: '',
  minUpsideWs: '',
};

const CLASSIFICATION_COLUMNS = [
  { key: 'sector', label: 'Sector' },
  { key: 'industry', label: 'Industria (Rubro)' },
];

const TABLE_COLUMNS = [
  { key: 'price', label: 'Precio (US$)', type: 'money2' },
  { key: 'market_cap_mm', label: 'Cap. Bursátil (MM)', type: 'money0' },
  { key: 'pe_ltm', label: 'P/E LTM', type: 'mult' },
  { key: 'pe_ntm', label: 'P/E NTM', type: 'mult' },
  { key: 'ev_ebitda_ltm', label: 'EV/EBITDA', type: 'mult' },
  { key: 'pb_ltm', label: 'P/BV', type: 'mult' },
  { key: 'p_fcf_ltm', label: 'P/FCF', type: 'mult' },
  { key: 'fcf_yield_pct', label: 'FCF Yield', type: 'pct' },
  { key: 'ebit_margin_pct', label: 'Margen EBIT', type: 'pct' },
  { key: 'roic_pct', label: 'ROIC', type: 'pct' },
  { key: 'roe_pct', label: 'ROE', type: 'pct' },
  { key: 'net_debt_to_ebitda', label: 'DN/EBITDA', type: 'mult' },
  { key: 'rev_growth_yoy_pct', label: 'Crec. Ventas', type: 'pct' },
  { key: 'upside_ws_pct', label: 'Potencial WS', type: 'pct' },
  { key: 'updated_ago_hours', label: 'Actualizado', type: 'ago' },
];

const ALL_COLUMN_KEYS = [
  ...CLASSIFICATION_COLUMNS.map((c) => c.key),
  ...TABLE_COLUMNS.map((c) => c.key),
];

const COMPACT_COLUMN_KEYS = [
  'sector',
  'industry',
  'price',
  'market_cap_mm',
  'pe_ltm',
  'pe_ntm',
  'ev_ebitda_ltm',
  'fcf_yield_pct',
  'roic_pct',
  'rev_growth_yoy_pct',
  'upside_ws_pct',
];

function formatCell(val, type) {
  if (val === null || val === undefined || Number.isNaN(val)) return '-';
  if (type === 'ago') {
    const hrs = Number(val);
    if (hrs < 1) return 'Recién';
    if (hrs < 24) return `Hace ${Math.round(hrs)} h`;
    return `Hace ${Math.round(hrs / 24)} d`;
  }
  const isNeg = val < 0;
  const abs = Math.abs(val);

  if (type === 'money0') {
    const f = new Intl.NumberFormat('es-AR', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(abs);
    return isNeg ? `(US$ ${f})` : `US$ ${f}`;
  }
  if (type === 'money2') {
    const f = new Intl.NumberFormat('es-AR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(abs);
    return isNeg ? `(US$ ${f})` : `US$ ${f}`;
  }
  const f = new Intl.NumberFormat('es-AR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(abs);
  const suffix = type === 'pct' ? '%' : 'x';
  return isNeg ? `(${f}${suffix})` : `${f}${suffix}`;
}

export default function ScreenerTab({
  onSelectCompany,
  initialPresetId = 'all',
  universeData: universeDataProp,
  onUniverseDataChange,
  syncState: syncStateProp,
  onStartSync,
  onStopSync,
  onClearSyncFeedback,
}) {
  const { isAdvisorOrAdmin } = useAuth();
  const startingPreset = PRESETS.find((p) => p.id === initialPresetId) || PRESETS[0];

  const [localUniverseData, setLocalUniverseData] = useState(null);
  const universeData = universeDataProp !== undefined ? universeDataProp : localUniverseData;
  const setUniverseData = onUniverseDataChange || setLocalUniverseData;

  const [loading, setLoading] = useState(false);
  const [localSyncing, setLocalSyncing] = useState(false);
  const [localSyncFeedback, setLocalSyncFeedback] = useState(null);
  const [error, setError] = useState(null);

  const syncState = syncStateProp || {
    running: localSyncing,
    stopping: false,
    totalTarget: 0,
    syncedInRun: 0,
    feedback: localSyncFeedback,
    error: null,
  };

  const [basePresetId, setBasePresetId] = useState(startingPreset.id);
  const [isRefined, setIsRefined] = useState(false);
  const [groupByIndustry, setGroupByIndustry] = useState(false);
  const [filters, setFilters] = useState(() => ({ ...INITIAL_FILTERS, ...startingPreset.filters }));
  const [sortConfig, setSortConfig] = useState({ key: 'market_cap_mm', direction: 'desc' });

  const [visibleColumns, setVisibleColumns] = useState(() => new Set(ALL_COLUMN_KEYS));
  const [showColumnMenu, setShowColumnMenu] = useState(false);
  const [showFiltersPanel, setShowFiltersPanel] = useState(true);
  const columnMenuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (columnMenuRef.current && !columnMenuRef.current.contains(e.target)) {
        setShowColumnMenu(false);
      }
    };
    if (showColumnMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showColumnMenu]);

  useEffect(() => {
    if (universeDataProp) return;
    let cancelled = false;
    const loadUniverse = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await apiClient.get('/screener');
        if (!cancelled) {
          setUniverseData(res.data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || 'No se pudo cargar el universo del Screener');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadUniverse();
    return () => {
      cancelled = true;
    };
  }, [universeDataProp, setUniverseData]);

  const handleSyncMore = async () => {
    const totalToSync = pendingSyncCount + staleCount;
    if (onStartSync) {
      if (syncState.running) {
        onStopSync?.();
      } else {
        setError(null);
        onStartSync(totalToSync);
      }
      return;
    }

    setLocalSyncing(true);
    setError(null);
    setLocalSyncFeedback(null);
    try {
      const res = await apiClient.post('/screener/sync?batch_size=4');
      setUniverseData(res.data);
      const syncedNow = Array.isArray(res.data?.synced_now) ? res.data.synced_now : [];
      if (syncedNow.length > 0) {
        setLocalSyncFeedback(`Sincronización completada (${syncedNow.length}): ${syncedNow.join(', ')}.`);
      } else {
        setLocalSyncFeedback('No se completaron nuevos emisores en este lote (pueden haber quedado en espera temporal); volvé a intentar para avanzar.');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al sincronizar lote de empresas');
    } finally {
      setLocalSyncing(false);
    }
  };

  const applyPreset = (preset) => {
    setBasePresetId(preset.id);
    setIsRefined(false);
    setFilters({ ...INITIAL_FILTERS, ...preset.filters });
  };

  const updateFilter = (field, value) => {
    setIsRefined(true);
    setFilters((prev) => {
      const next = { ...prev, [field]: value };
      if (field === 'sector') {
        next.industry = 'ALL';
      }
      return next;
    });
  };

  const resetFilters = () => {
    setBasePresetId('all');
    setIsRefined(false);
    setGroupByIndustry(false);
    setFilters(INITIAL_FILTERS);
  };

  const handleSort = (key) => {
    setSortConfig((prev) => {
      if (prev.key === key) {
        return { key, direction: prev.direction === 'desc' ? 'asc' : 'desc' };
      }
      return { key, direction: 'desc' };
    });
  };

  const toggleColumn = (key) => {
    setVisibleColumns((prev) => {
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

  const activeMetricColumns = useMemo(
    () => TABLE_COLUMNS.filter((c) => visibleColumns.has(c.key)),
    [visibleColumns]
  );

  const showSectorCol = visibleColumns.has('sector');
  const showIndustryCol = visibleColumns.has('industry');
  const totalVisibleColsCount =
    1 + (showSectorCol ? 1 : 0) + (showIndustryCol ? 1 : 0) + activeMetricColumns.length;

  const availableIndustries = useMemo(() => {
    const rawItems = universeData?.items || [];
    const setInd = new Set();
    rawItems.forEach((item) => {
      if (filters.sector !== 'ALL' && item.sector !== filters.sector) return;
      if (item.industry && item.industry.trim() !== '') {
        setInd.add(item.industry.trim());
      }
    });
    return Array.from(setInd).sort((a, b) => a.localeCompare(b));
  }, [universeData, filters.sector]);

  const filteredItems = useMemo(() => {
    const rawItems = universeData?.items || [];

    const passesMin = (val, minStr) => {
      if (!minStr || minStr.trim() === '') return true;
      const num = parseFloat(minStr);
      if (Number.isNaN(num)) return true;
      return typeof val === 'number' && val >= num;
    };

    const passesMax = (val, maxStr) => {
      if (!maxStr || maxStr.trim() === '') return true;
      const num = parseFloat(maxStr);
      if (Number.isNaN(num)) return true;
      return typeof val === 'number' && val <= num;
    };

    const q = filters.search.trim().toLowerCase();

    const filtered = rawItems.filter((item) => {
      if (filters.sector !== 'ALL' && item.sector !== filters.sector) return false;
      if (filters.industry !== 'ALL' && (item.industry || '') !== filters.industry) return false;
      if (
        q &&
        !item.ticker.toLowerCase().includes(q) &&
        !item.name.toLowerCase().includes(q) &&
        !(item.industry || '').toLowerCase().includes(q) &&
        !(item.sector || '').toLowerCase().includes(q)
      ) {
        return false;
      }

      if (!passesMin(item.market_cap_mm, filters.minMcap)) return false;
      if (!passesMax(item.pe_ltm, filters.maxPeLtm)) return false;
      if (!passesMax(item.pe_ntm, filters.maxPeNtm)) return false;
      if (!passesMax(item.ev_ebitda_ltm, filters.maxEvEbitda)) return false;
      if (!passesMin(item.fcf_yield_pct, filters.minFcfYield)) return false;
      if (!passesMin(item.roic_pct, filters.minRoic)) return false;
      if (!passesMin(item.roe_pct, filters.minRoe)) return false;
      if (!passesMin(item.ebit_margin_pct, filters.minEbitMargin)) return false;
      if (!passesMin(item.rev_growth_yoy_pct, filters.minRevGrowth)) return false;
      if (!passesMax(item.net_debt_to_ebitda, filters.maxNetDebtEbitda)) return false;
      if (!passesMin(item.upside_ws_pct, filters.minUpsideWs)) return false;

      return true;
    });

    const { key, direction } = sortConfig;
    return [...filtered].sort((a, b) => {
      const va = a[key];
      const vb = b[key];
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      if (typeof va === 'string' && typeof vb === 'string') {
        return direction === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
      }
      return direction === 'asc' ? va - vb : vb - va;
    });
  }, [universeData, filters, sortConfig]);

  const groupedSections = useMemo(() => {
    if (!groupByIndustry) {
      return [{ groupName: null, sectorName: null, items: filteredItems }];
    }

    const groupsMap = new Map();
    filteredItems.forEach((item) => {
      const rubric = (item.industry && item.industry.trim()) || item.sector || 'Sin clasificar';
      if (!groupsMap.has(rubric)) {
        groupsMap.set(rubric, {
          groupName: rubric,
          sectorName: item.sector || '',
          items: [],
        });
      }
      groupsMap.get(rubric).items.push(item);
    });

    return Array.from(groupsMap.values()).sort((a, b) => {
      if (b.items.length !== a.items.length) return b.items.length - a.items.length;
      return a.groupName.localeCompare(b.groupName);
    });
  }, [filteredItems, groupByIndustry]);

  const exportCsv = () => {
    if (filteredItems.length === 0) return;
    const headers = [
      'Ticker',
      'Empresa',
      ...(showSectorCol ? ['Sector'] : []),
      ...(showIndustryCol ? ['Industria (Rubro)'] : []),
      ...activeMetricColumns.map((c) => c.label),
    ];

    const lines = filteredItems.map((item) => {
      const row = [
        item.ticker,
        `"${String(item.name || '').replace(/"/g, '""')}"`,
        ...(showSectorCol ? [`"${String(item.sector || '').replace(/"/g, '""')}"`] : []),
        ...(showIndustryCol ? [`"${String(item.industry || '').replace(/"/g, '""')}"`] : []),
        ...activeMetricColumns.map((c) =>
          item[c.key] !== null && item[c.key] !== undefined ? item[c.key] : ''
        ),
      ];
      return row.join(',');
    });

    const csvContent = '\uFEFF' + [headers.join(','), ...lines].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `screener_terminal_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const currentStrategyBanner = useMemo(() => {
    return PRESETS.find((p) => p.id === basePresetId) || PRESETS[0];
  }, [basePresetId]);

  const pendingSyncCount = universeData?.pending_sync || 0;
  const staleCount = universeData?.stale_count || 0;

  if (loading && !universeData) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm py-20 flex flex-col items-center justify-center text-orange-500">
        <Loader2 className="w-8 h-8 mb-3 animate-spin" />
        <p className="text-sm font-medium">Inicializando universo fundamental y métricas LTM/NTM...</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* CABECERA Y PRESETS CUANTITATIVOS */}
      <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-gray-200">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded bg-orange-50 text-orange-600">
              <Filter className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-gray-900">
                Screener Fundamental ({filteredItems.length} de {universeData?.total_cached || 0} empresas en base)
              </h3>
              <p className="text-xs text-gray-500">
                Filtrá emisores por valuación, retorno sobre capital, generación de caja y apalancamiento. Hacé clic en cualquier ticker para abrir su análisis completo.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {isAdvisorOrAdmin && (syncState.running || pendingSyncCount > 0 || staleCount > 0) && (
              <button
                type="button"
                onClick={handleSyncMore}
                disabled={syncState.stopping}
                title="Actualiza toda la base en segundo plano con un solo clic (en lotes de 4 emisores)"
                className={`flex items-center text-xs px-3 py-1.5 rounded border font-medium cursor-pointer transition-colors disabled:opacity-60 ${
                  syncState.running
                    ? 'border-orange-500 bg-orange-500 text-white hover:bg-orange-600'
                    : 'border-orange-300 bg-orange-50 text-orange-700 hover:bg-orange-100'
                }`}
              >
                <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${syncState.running ? 'animate-spin' : ''}`} />
                {syncState.stopping
                  ? 'Deteniendo...'
                  : syncState.running
                  ? `Sincronizando ${syncState.syncedInRun}/${syncState.totalTarget || pendingSyncCount + staleCount} · Detener`
                  : pendingSyncCount > 0
                  ? `Completar base (${pendingSyncCount})`
                  : `Actualizar base (${staleCount})`}
              </button>
            )}

            <button
              type="button"
              onClick={() => setShowFiltersPanel((prev) => !prev)}
              className={`flex items-center text-xs px-3 py-1.5 rounded border font-medium transition-colors cursor-pointer ${
                showFiltersPanel
                  ? 'border-orange-300 bg-orange-50/70 text-orange-700 hover:bg-orange-100'
                  : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              <Filter className="w-3.5 h-3.5 mr-1.5" />
              {showFiltersPanel ? 'Ocultar filtros' : 'Mostrar filtros'}
            </button>

            <button
              type="button"
              onClick={() => setGroupByIndustry((prev) => !prev)}
              className={`flex items-center text-xs px-3 py-1.5 rounded border font-medium transition-colors cursor-pointer ${
                groupByIndustry
                  ? 'bg-orange-500 text-white border-orange-500 shadow-2xs'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-orange-50 hover:border-orange-300'
              }`}
            >
              <Layers className="w-3.5 h-3.5 mr-1.5" />
              {groupByIndustry ? 'Agrupado por rubro' : 'Agrupar por rubro'}
            </button>

            {/* SELECTOR DE COLUMNAS VISIBLES */}
            <div className="relative" ref={columnMenuRef}>
              <button
                type="button"
                onClick={() => setShowColumnMenu((prev) => !prev)}
                className={`flex items-center text-xs px-3 py-1.5 rounded border font-medium transition-colors cursor-pointer ${
                  showColumnMenu || visibleColumns.size < ALL_COLUMN_KEYS.length
                    ? 'border-orange-300 bg-orange-50/70 text-orange-700 hover:bg-orange-100'
                    : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                <Columns3 className="w-3.5 h-3.5 mr-1.5" />
                Columnas ({visibleColumns.size}/{ALL_COLUMN_KEYS.length})
              </button>

              {showColumnMenu && (
                <div className="absolute right-0 mt-1.5 w-72 bg-white border border-gray-200 rounded-lg shadow-xl z-40 p-3 text-xs">
                  <div className="flex items-center justify-between pb-2 mb-2 border-b border-gray-100">
                    <span className="font-bold text-gray-800">Columnas visibles</span>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setVisibleColumns(new Set(COMPACT_COLUMN_KEYS))}
                        className="text-[11px] text-orange-600 hover:underline font-medium cursor-pointer"
                      >
                        Compacta
                      </button>
                      <span className="text-gray-300">|</span>
                      <button
                        type="button"
                        onClick={() => setVisibleColumns(new Set(ALL_COLUMN_KEYS))}
                        className="text-[11px] text-gray-600 hover:underline font-medium cursor-pointer"
                      >
                        Todas
                      </button>
                    </div>
                  </div>

                  <div className="max-h-72 overflow-y-auto space-y-1 pr-1">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400 px-1 pt-0.5">
                      Clasificación
                    </p>
                    {CLASSIFICATION_COLUMNS.map((col) => {
                      const checked = visibleColumns.has(col.key);
                      return (
                        <button
                          key={col.key}
                          type="button"
                          onClick={() => toggleColumn(col.key)}
                          className="w-full flex items-center justify-between px-2 py-1 rounded hover:bg-gray-50 text-left cursor-pointer"
                        >
                          <span className={checked ? 'text-gray-900 font-medium' : 'text-gray-400'}>
                            {col.label}
                          </span>
                          <span
                            className={`w-4 h-4 rounded flex items-center justify-center border ${
                              checked
                                ? 'bg-orange-500 border-orange-500 text-white'
                                : 'border-gray-300 bg-white'
                            }`}
                          >
                            {checked && <Check className="w-3 h-3" />}
                          </span>
                        </button>
                      );
                    })}

                    <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400 px-1 pt-2">
                      Métricas y Múltiplos
                    </p>
                    {TABLE_COLUMNS.map((col) => {
                      const checked = visibleColumns.has(col.key);
                      return (
                        <button
                          key={col.key}
                          type="button"
                          onClick={() => toggleColumn(col.key)}
                          className="w-full flex items-center justify-between px-2 py-1 rounded hover:bg-gray-50 text-left cursor-pointer"
                        >
                          <span className={checked ? 'text-gray-900 font-medium' : 'text-gray-400'}>
                            {col.label}
                          </span>
                          <span
                            className={`w-4 h-4 rounded flex items-center justify-center border ${
                              checked
                                ? 'bg-orange-500 border-orange-500 text-white'
                                : 'border-gray-300 bg-white'
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

            <button
              type="button"
              onClick={resetFilters}
              className="flex items-center text-xs px-2.5 py-1.5 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5 mr-1" /> Limpiar filtros
            </button>

            <button
              type="button"
              onClick={exportCsv}
              disabled={filteredItems.length === 0}
              className="flex items-center text-xs px-3 py-1.5 rounded bg-gray-900 text-white hover:bg-gray-800 font-medium cursor-pointer disabled:opacity-50"
            >
              <Download className="w-3.5 h-3.5 mr-1.5" /> Exportar CSV
            </button>
          </div>
        </div>

        {/* Presets rápidos + Panel explicativo siempre sincronizado */}
        <div className="mt-4">
          <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-2">
            <Sparkles className="w-3.5 h-3.5 text-orange-500" />
            <span>Estrategias Predefinidas</span>
          </div>

          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => {
              const isSelected = basePresetId === p.id;
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => applyPreset(p)}
                  className={`px-3.5 py-1.5 rounded text-xs font-medium border transition-colors cursor-pointer ${
                    isSelected
                      ? 'bg-orange-500 text-white border-orange-500 shadow-2xs'
                      : 'bg-gray-50 text-gray-700 border-gray-300 hover:bg-orange-50 hover:border-orange-300'
                  }`}
                >
                  {p.label}
                  {isSelected && isRefined ? ' · Refinado' : ''}
                </button>
              );
            })}
          </div>

          {/* Ficha explicativa siempre sincronizada con la estrategia activa */}
          <div className="mt-3 bg-orange-50/70 border border-orange-200/90 rounded-lg p-3.5 text-xs flex items-start gap-2.5">
            <Info className="w-4 h-4 text-orange-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="font-bold text-gray-900 text-[13px]">
                  {currentStrategyBanner.label}
                </span>
                <span className="px-2 py-0.5 rounded bg-white border border-orange-200 text-orange-700 font-semibold text-[11px]">
                  Base: {currentStrategyBanner.criteriaLabel}
                </span>
                {isRefined && (
                  <span className="px-2 py-0.5 rounded bg-gray-900 text-white font-semibold text-[11px]">
                    + Filtros adicionales activos en cascada
                  </span>
                )}
              </div>
              <p className="font-medium text-gray-800 mb-0.5">{currentStrategyBanner.summary}</p>
              <p className="text-gray-600 leading-relaxed">{currentStrategyBanner.thesis}</p>
            </div>
          </div>
        </div>

        {/* Matriz de filtros paramétricos acumulables */}
        {showFiltersPanel && (
        <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-3 text-xs">
          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Sector</label>
            <select
              value={filters.sector}
              onChange={(e) => updateFilter('sector', e.target.value)}
              className="w-full px-2 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            >
              <option value="ALL">Todos los sectores</option>
              {(universeData?.sectors || []).map((sec) => (
                <option key={sec} value={sec}>
                  {sec}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Industria / Rubro</label>
            <select
              value={filters.industry}
              onChange={(e) => updateFilter('industry', e.target.value)}
              className="w-full px-2 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            >
              <option value="ALL">Todos los rubros</option>
              {availableIndustries.map((ind) => (
                <option key={ind} value={ind}>
                  {ind}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Buscar Ticker / Nombre</label>
            <input
              type="text"
              value={filters.search}
              onChange={(e) => updateFilter('search', e.target.value)}
              placeholder="Ej: NVDA, banco..."
              className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Cap. Bursátil Mín (MM)</label>
            <input
              type="number"
              value={filters.minMcap}
              onChange={(e) => updateFilter('minMcap', e.target.value)}
              placeholder="Ej: 50000"
              className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">P/E LTM Máximo (x)</label>
            <input
              type="number"
              step="0.5"
              value={filters.maxPeLtm}
              onChange={(e) => updateFilter('maxPeLtm', e.target.value)}
              placeholder="Ej: 20"
              className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">P/E Forward Máx (x)</label>
            <input
              type="number"
              step="0.5"
              value={filters.maxPeNtm}
              onChange={(e) => updateFilter('maxPeNtm', e.target.value)}
              placeholder="Ej: 18"
              className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">EV / EBITDA Máx (x)</label>
            <input
              type="number"
              step="0.5"
              value={filters.maxEvEbitda}
              onChange={(e) => updateFilter('maxEvEbitda', e.target.value)}
              placeholder="Ej: 14"
              className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">FCF Yield Mínimo (%)</label>
            <input
              type="number"
              step="0.5"
              value={filters.minFcfYield}
              onChange={(e) => updateFilter('minFcfYield', e.target.value)}
              placeholder="Ej: 4.5"
              className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">ROIC Mínimo (%)</label>
            <input
              type="number"
              step="1"
              value={filters.minRoic}
              onChange={(e) => updateFilter('minRoic', e.target.value)}
              placeholder="Ej: 15"
              className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">ROE Mínimo (%)</label>
            <input
              type="number"
              step="1"
              value={filters.minRoe}
              onChange={(e) => updateFilter('minRoe', e.target.value)}
              placeholder="Ej: 15"
              className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Margen EBIT Mín (%)</label>
            <input
              type="number"
              step="1"
              value={filters.minEbitMargin}
              onChange={(e) => updateFilter('minEbitMargin', e.target.value)}
              placeholder="Ej: 20"
              className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Crec. Ventas Mín (%)</label>
            <input
              type="number"
              step="1"
              value={filters.minRevGrowth}
              onChange={(e) => updateFilter('minRevGrowth', e.target.value)}
              placeholder="Ej: 8"
              className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Deuda Neta / EBITDA Máx</label>
            <input
              type="number"
              step="0.25"
              value={filters.maxNetDebtEbitda}
              onChange={(e) => updateFilter('maxNetDebtEbitda', e.target.value)}
              placeholder="Ej: 2.5"
              className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Potencial WS Mín (%)</label>
            <input
              type="number"
              step="1"
              value={filters.minUpsideWs}
              onChange={(e) => updateFilter('minUpsideWs', e.target.value)}
              placeholder="Ej: 15"
              className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-gray-50 text-gray-800 focus:outline-none focus:border-orange-500"
            />
          </div>
        </div>
        )}
      </div>

      {syncState.running && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 text-xs text-orange-900 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-orange-600 shrink-0" />
            <span>
              <strong>Actualizando base en segundo plano</strong> ({syncState.syncedInRun} de{' '}
              {syncState.totalTarget || pendingSyncCount + staleCount} procesados en lotes de 4). Podés seguir navegando y usando la plataforma con normalidad mientras finaliza.
            </span>
          </div>
          <button
            type="button"
            onClick={handleSyncMore}
            disabled={syncState.stopping}
            className="text-orange-700 hover:text-orange-900 font-semibold cursor-pointer shrink-0 disabled:opacity-60"
          >
            {syncState.stopping ? 'Deteniendo...' : 'Detener'}
          </button>
        </div>
      )}

      {syncState.feedback && !syncState.running && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-xs text-emerald-800 font-medium flex items-center justify-between gap-3">
          <span>{syncState.feedback}</span>
          <button
            type="button"
            onClick={() => (onClearSyncFeedback ? onClearSyncFeedback() : setLocalSyncFeedback(null))}
            className="text-emerald-600 hover:text-emerald-800 cursor-pointer shrink-0"
          >
            Cerrar
          </button>
        </div>
      )}

      {(syncState.error || error) && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700 font-medium">
          {syncState.error || error}
        </div>
      )}

      {/* TABLA DE RESULTADOS */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <div className="w-full overflow-x-auto">
          <table className="w-full text-[12px] text-left whitespace-nowrap">
            <thead>
              <tr className="bg-[#333333] text-white">
                <th
                  onClick={() => handleSort('ticker')}
                  className="py-2.5 px-3.5 font-bold sticky left-0 bg-[#333333] z-10 min-w-52 cursor-pointer hover:bg-[#404040]"
                >
                  <div className="flex items-center justify-between">
                    <span>Empresa | Ticker</span>
                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                  </div>
                </th>
                {showSectorCol && (
                  <th
                    onClick={() => handleSort('sector')}
                    className="py-2.5 px-3 font-bold text-left cursor-pointer hover:bg-[#404040]"
                  >
                    <div className="inline-flex items-center gap-1">
                      <span>Sector</span>
                      <ArrowUpDown className="w-3 h-3 text-gray-500" />
                    </div>
                  </th>
                )}
                {showIndustryCol && (
                  <th
                    onClick={() => handleSort('industry')}
                    className="py-2.5 px-3 font-bold text-left cursor-pointer hover:bg-[#404040]"
                  >
                    <div className="inline-flex items-center gap-1">
                      <span>Industria (Rubro)</span>
                      <ArrowUpDown className="w-3 h-3 text-gray-500" />
                    </div>
                  </th>
                )}
                {activeMetricColumns.map((col) => {
                  const isSorted = sortConfig.key === col.key;
                  return (
                    <th
                      key={col.key}
                      onClick={() => handleSort(col.key)}
                      className="py-2.5 px-3 font-bold text-right cursor-pointer hover:bg-[#404040]"
                    >
                      <div className="inline-flex items-center justify-end gap-1">
                        <span>{col.label}</span>
                        {isSorted ? (
                          sortConfig.direction === 'asc' ? (
                            <ArrowUp className="w-3 h-3 text-orange-400" />
                          ) : (
                            <ArrowDown className="w-3 h-3 text-orange-400" />
                          )
                        ) : (
                          <ArrowUpDown className="w-3 h-3 text-gray-500" />
                        )}
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {filteredItems.length === 0 ? (
                <tr>
                  <td
                    colSpan={totalVisibleColsCount}
                    className="py-12 text-center text-gray-500 text-xs"
                  >
                    Ninguna empresa cumple simultáneamente con todos los filtros aplicados. Probá relajar algún umbral o sincronizar más emisores.
                  </td>
                </tr>
              ) : (
                groupedSections.map((sec, sIdx) => (
                  <Fragment key={sec.groupName || `flat-${sIdx}`}>
                    {groupByIndustry && sec.groupName && (
                      <tr className="bg-orange-50/80 border-y border-orange-200/80">
                        <td
                          colSpan={totalVisibleColsCount}
                          className="py-2 px-3.5 font-bold text-gray-900 sticky left-0"
                        >
                          <span className="text-orange-600 mr-1.5">▸</span>
                          {sec.groupName}
                          {sec.sectorName && sec.sectorName !== sec.groupName && (
                            <span className="ml-2 text-[11px] font-normal text-gray-500">
                              ({sec.sectorName})
                            </span>
                          )}
                          <span className="ml-2 px-2 py-0.5 rounded-full bg-white border border-orange-200 text-[10px] font-semibold text-orange-700">
                            {sec.items.length} {sec.items.length === 1 ? 'empresa' : 'empresas'}
                          </span>
                        </td>
                      </tr>
                    )}

                    {sec.items.map((item) => (
                      <tr
                        key={item.ticker}
                        onClick={() => onSelectCompany && onSelectCompany(item.ticker)}
                        title={`Abrir análisis completo de ${item.ticker}`}
                        className="border-b border-gray-100 hover:bg-orange-50/50 cursor-pointer group transition-colors"
                      >
                        <td className="py-2 px-3.5 sticky left-0 bg-white group-hover:bg-orange-50/50 z-10 shadow-[1px_0_0_0_#f3f4f6]">
                          <span className="font-bold text-orange-600 mr-2">{item.ticker}</span>
                          <span className="text-gray-700">{item.name}</span>
                        </td>
                        {showSectorCol && (
                          <td className="py-2 px-3 text-gray-500 text-[11px]">{item.sector}</td>
                        )}
                        {showIndustryCol && (
                          <td className="py-2 px-3 text-gray-600 text-[11px]">{item.industry || '-'}</td>
                        )}
                        {activeMetricColumns.map((col) => {
                          const val = item[col.key];
                          const isNeg = typeof val === 'number' && val < 0;
                          const isUpsidePos = col.key === 'upside_ws_pct' && typeof val === 'number' && val > 0;
                          return (
                            <td
                              key={col.key}
                              className={`py-2 px-3 text-right tabular-nums ${
                                isNeg
                                  ? 'text-[#d93025]'
                                  : isUpsidePos
                                  ? 'text-emerald-700 font-semibold'
                                  : 'text-gray-800'
                              }`}
                            >
                              {formatCell(val, col.type)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}