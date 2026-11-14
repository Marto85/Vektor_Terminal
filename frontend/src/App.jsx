import { useState } from 'react';
import axios from 'axios';
import { FileText, BarChart3, PieChart, Search, Bell, Settings, Download, Maximize2, Loader2, ExternalLink, Heart, ChevronUp, ChevronDown } from 'lucide-react';
import StockChart from './components/StockChart';
import CapitalStructurePanel from './components/CapitalStructurePanel';

function App() {
  const [activeSidebarTab, setActiveSidebarTab] = useState('Resumen');
  const [activeContentTab, setActiveContentTab] = useState('Cuenta de Resultados');
  const [period, setPeriod] = useState('annual');
  const [showChart, setShowChart] = useState(true);
  
  const [tickerInput, setTickerInput] = useState('');
  const [currentTicker, setCurrentTicker] = useState('MSFT');
  const [financialData, setFinancialData] = useState([]);
  
  const [profileData, setProfileData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [searchResults, setSearchResults] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);

  const sidebarItems = [
    { id: 'Resumen', name: 'Resumen y noticias', icon: FileText },
    { id: 'Finanzas', name: 'Finanzas', icon: BarChart3 },
    { id: 'Valoracion', name: 'Valoración', icon: PieChart },
  ];

  const contentTabs = [
    'Cuenta de Resultados',
    'Balance de Situación',
    'Estado de Flujo de Efectivo',
    'Ratios',
    'Segmentos'
  ];

  const executeSearch = async (tickerToSearch, selectedPeriod = period) => {
    if (!tickerToSearch) return;
    const upperTicker = tickerToSearch.toUpperCase();
    setIsLoading(true);
    setError(null);
    
    try {
      const [finResponse, profResponse] = await Promise.all([
        axios.get(`http://127.0.0.1:8000/api/v1/company/${upperTicker}/financials/${selectedPeriod}`),
        axios.get(`http://127.0.0.1:8000/api/v1/company/${upperTicker}/profile`)
      ]);
      
      setFinancialData(finResponse.data);
      setProfileData(profResponse.data);
      setCurrentTicker(upperTicker);
    } catch (err) {
      console.error("Error al buscar datos:", err);
      setError(err.response?.data?.detail || "Error de conexión con el servidor");
    } finally {
      setIsLoading(false);
    }
  };

  const handlePeriodChange = (newPeriod) => {
    if (newPeriod === period) return;
    setPeriod(newPeriod);
    executeSearch(currentTicker, newPeriod);
  };

  const handleSearchChange = async (e) => {
    const value = e.target.value;
    setTickerInput(value);

    if (value.trim().length > 0) {
      try {
        const response = await axios.get(`http://127.0.0.1:8000/api/v1/search?q=${value}`);
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
    executeSearch(selectedTicker, period);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      setShowDropdown(false);
      executeSearch(tickerInput.trim(), period);
    }
  };

  const currentTabData = financialData.filter(item => item.Categoría === activeContentTab);
  
  const availableYears = currentTabData.length > 0 
    ? Object.keys(currentTabData[0]).filter(key => 
        key !== 'Categoría' && 
        key !== 'Métrica' && 
        key !== 'is_pct' && 
        key !== 'is_sub' && 
        key !== 'is_header'
      ).sort()
    : [];

  const formatNumber = (value, isPct = false) => {
    if (value === 0 || value === 0.0 || value === '-' || value === null || value === undefined) return '-';
    
    const isNegative = value < 0;
    const absValue = Math.abs(value);
    
    let formatted = new Intl.NumberFormat('es-AR', { 
      minimumFractionDigits: 2, 
      maximumFractionDigits: 2 
    }).format(absValue);
    
    formatted = isPct ? `${formatted}%` : formatted;
    
    return isNegative ? `(${formatted})` : formatted;
  };

  const getDomain = (url) => {
    try {
      if (!url) return null;
      const parsed = new URL(url);
      return parsed.hostname.replace('www.', '');
    } catch {
      return null;
    }
  };

  const domain = getDomain(profileData?.website);

  return (
    <div className="flex h-screen bg-[#1e1e1e] font-sans text-gray-200 overflow-hidden">
      {/* SIDEBAR */}
      <aside className="w-56 bg-[#252526] border-r border-gray-700 flex flex-col shrink-0">
        <div className="h-12 flex items-center px-4 border-b border-gray-700 bg-[#1e1e1e]">
          <div className="w-4 h-4 bg-orange-500 rounded-sm mr-2"></div>
          <span className="text-white text-sm font-semibold tracking-wide">Terminal Financiera</span>
        </div>
        
        <div className="flex-1 overflow-y-auto py-4">
          <div className="px-3 mb-2">
            <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">{currentTicker} Fundamental Analysis</p>
          </div>
          <nav className="space-y-0.5 px-2">
            {sidebarItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeSidebarTab === item.id;
              
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveSidebarTab(item.id)}
                  className={`w-full flex items-center px-3 py-1.5 text-xs rounded transition-colors ${
                    isActive 
                      ? 'bg-orange-500/10 text-orange-500 font-medium cursor-default' 
                      : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200 cursor-pointer'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5 mr-2" />
                  {item.name}
                </button>
              );
            })}
          </nav>
        </div>
      </aside>

      {/* CONTENIDO PRINCIPAL */}
      <main className="flex-1 flex flex-col min-w-0 bg-[#f9fafb]">
        
        {/* HEADER CON AUTOCOMPLETADO */}
        <header className="h-12 bg-[#252526] border-b border-gray-700 flex items-center justify-between px-4 shrink-0 z-50">
          <div className="flex items-center flex-1 max-w-xl">
            <div className="relative w-full">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500" />
              <input 
                type="text" 
                value={tickerInput}
                onChange={handleSearchChange}
                onKeyDown={handleKeyDown}
                onFocus={() => { if (searchResults.length > 0) setShowDropdown(true); }}
                onBlur={() => setShowDropdown(false)}
                placeholder="Busca entre 100.000 empresas en todo el mundo (Ej: AAPL + Enter)" 
                className="w-full pl-9 pr-4 py-1 bg-[#333333] border border-gray-600 rounded text-xs text-white placeholder-gray-400 focus:outline-none focus:border-orange-500 focus:bg-[#1e1e1e]"
              />
              <div className="absolute right-2 top-1/2 transform -translate-y-1/2 text-[10px] text-gray-500 bg-[#252526] px-1 rounded border border-gray-600">Enter</div>
              
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
                        <span className="font-bold text-orange-500 mr-3 w-12 shrink-0">{res.ticker}</span>
                        <span className="text-gray-300 text-xs truncate">{res.name}</span>
                      </div>
                      <span className="text-gray-500 text-[10px] uppercase shrink-0">{res.type}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-4 text-gray-400">
            <Search className="w-4 h-4 hover:text-white cursor-pointer" />
            <Bell className="w-4 h-4 hover:text-white cursor-pointer" />
            <Settings className="w-4 h-4 hover:text-white cursor-pointer" />
            <div className="w-6 h-6 rounded-full bg-orange-600 flex items-center justify-center text-white text-xs font-bold">M</div>
          </div>
        </header>

        {/* CABECERA EMPRESA GLOBAL (Estilo TIKR) */}
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
                    <button className="flex items-center px-3 py-1.5 border border-gray-300 rounded text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer shadow-sm">
                      <Heart className="w-3.5 h-3.5 mr-1.5 text-orange-500" />
                      Agregar al tablero
                    </button>
                    <button className="px-3 py-1.5 border border-gray-300 rounded text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer shadow-sm">
                      USD
                    </button>
                    <button
                      onClick={() => setShowChart((prev) => !prev)}
                      className="flex items-center px-3 py-1.5 border border-gray-300 rounded text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer shadow-sm"
                    >
                      {showChart ? (
                        <>Ocultar gráfico <ChevronUp className="w-3.5 h-3.5 ml-1.5" /></>
                      ) : (
                        <>Mostrar gráfico <ChevronDown className="w-3.5 h-3.5 ml-1.5" /></>
                      )}
                    </button>
                  </div>
                </div>
              </div>

              <div className="text-right flex flex-col items-end">
                <h2 className="text-[36px] font-bold text-gray-900 leading-none tracking-tight">
                  US$ {profileData ? formatNumber(profileData.price) : '0.00'}
                </h2>
                <p className={`text-[15px] font-bold mt-1 ${profileData?.change < 0 ? 'text-[#d93025]' : 'text-green-600'}`}>
                  {profileData
                    ? `${profileData.change < 0 ? '-US$ ' : profileData.change > 0 ? '+US$ ' : 'US$ '}${formatNumber(Math.abs(profileData.change))} (${profileData.change > 0 ? '+' : profileData.change < 0 ? '-' : ''}${formatNumber(Math.abs(profileData.change_pct), true)})`
                    : 'US$ 0,00 (0,00%)'}
                </p>
                <p className="text-[11px] text-gray-400 mt-1">
                  12 de noviembre de 2026 a las 4:00 p. m. GMT-3
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* ÁREA DE CONTENIDO CONDICIONAL */}
        <div className="flex-1 overflow-auto">
          
          <div className="max-w-7xl mx-auto px-6 py-6">
            
            {/* BLOQUE GLOBAL: Tarjeta Unificada Gráfico (Izq) y Panel de Datos 2 Columnas (Der) */}
            {showChart && (
              <div className="bg-white border border-gray-200 rounded-lg shadow-sm flex flex-col lg:flex-row mb-6 overflow-hidden">
                {/* GRÁFICO ESTILO TIKR (TradingView Lightweight Charts) */}
                <StockChart ticker={currentTicker} companyName={profileData?.name} />

                {/* PANEL DE DATOS DERECHO */}
                <CapitalStructurePanel summaryMetrics={profileData?.summary_metrics} />
              </div>
            )}

            {/* Sub-Nav de la Vista Principal (ESTILO TIKR) */}
            <div className="flex border-b border-gray-200 mb-6 space-x-8 px-2">
              {sidebarItems.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setActiveSidebarTab(item.id)}
                  className={`pb-3 text-[15px] transition-colors relative ${
                    activeSidebarTab === item.id 
                      ? 'text-orange-500 font-semibold cursor-default' 
                      : 'text-gray-500 hover:text-gray-800 font-medium cursor-pointer'
                  }`}
                >
                  {item.name}
                  {activeSidebarTab === item.id && (
                    <span className="absolute -bottom-px left-0 w-full h-0.5 bg-orange-500"></span>
                  )}
                </button>
              ))}
            </div>

            {/* PESTAÑA: RESUMEN Y NOTICIAS */}
            {activeSidebarTab === 'Resumen' && (
              <div className="space-y-6">
                <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-5">
                  <h3 className="text-sm font-bold text-gray-900 mb-2">Acerca de la empresa</h3>
                  <p className="text-sm text-gray-600 leading-relaxed mb-3">
                    {profileData?.description || "Buscando descripción..."}
                  </p>
                  {domain && (
                    <a href={profileData.website} target="_blank" rel="noreferrer" className="inline-flex items-center text-xs font-medium text-blue-600 hover:text-blue-800">
                      <ExternalLink className="w-3 h-3 mr-1" /> {domain}
                    </a>
                  )}
                </div>

                <div className="flex space-x-6">
                  <div className="flex-1 bg-white border border-gray-200 rounded-lg shadow-sm">
                    <div className="px-4 py-3 border-b border-gray-200">
                      <span className="text-sm font-bold text-gray-800">Noticias y desarrollos significativos</span>
                    </div>
                    <div className="p-4 space-y-4">
                      {profileData?.news && profileData.news.length > 0 ? (
                        profileData.news.map((n, i) => {
                          const date = new Date(n.providerPublishTime * 1000).toLocaleDateString();
                          return (
                            <div key={i} className="border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                              <span className="text-[10px] font-bold text-gray-400 uppercase">{date} • {n.publisher}</span>
                              <a 
                                href={n.link} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                className="block text-sm font-medium text-gray-800 hover:text-blue-600 cursor-pointer mt-1 transition-colors"
                              >
                                {n.title}
                              </a>
                            </div>
                          )
                        })
                      ) : (
                        <p className="text-sm text-gray-500">No hay noticias recientes.</p>
                      )}
                    </div>
                  </div>
                  <div className="w-1/3 bg-white border border-gray-200 rounded-lg shadow-sm">
                    <div className="px-4 py-3 border-b border-gray-200">
                      <span className="text-sm font-bold text-gray-800">Eventos próximos</span>
                    </div>
                    <div className="p-4 space-y-3 text-sm">
                      <div className="flex items-start">
                        <div className="w-10 text-center mr-3">
                          <span className="block text-[10px] font-bold text-gray-400 uppercase">Dic</span>
                          <span className="block text-lg font-bold text-gray-800 leading-none">12</span>
                        </div>
                        <div>
                          <p className="font-medium text-gray-800 text-xs">Junta Anual de Accionistas</p>
                          <p className="text-[10px] text-gray-500">Confirmado</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* PESTAÑA: FINANZAS (CON ESTILO TIKR) */}
            {activeSidebarTab === 'Finanzas' && (
              <div>
                <div className="flex border-b border-gray-200 mb-5 space-x-6 px-2">
                  {contentTabs.map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveContentTab(tab)}
                      className={`pb-2.5 text-sm transition-colors relative ${
                        activeContentTab === tab 
                          ? 'text-orange-500 font-semibold cursor-default' 
                          : 'text-gray-500 hover:text-gray-800 font-medium cursor-pointer'
                      }`}
                    >
                      {tab}
                      {activeContentTab === tab && (
                        <span className="absolute -bottom-px left-0 w-full h-0.5 bg-orange-500"></span>
                      )}
                    </button>
                  ))}
                </div>

                <div className="bg-white rounded-lg border border-gray-200 shadow-sm min-h-100 flex flex-col overflow-hidden">
                  <div className="flex justify-between items-center px-4 py-3 border-b border-gray-200 bg-gray-50">
                    <div className="flex space-x-2">
                      {/* Botones dinámicos para Anual/Trimestral */}
                      <div className="flex border border-gray-300 rounded overflow-hidden">
                        <button 
                          onClick={() => handlePeriodChange('annual')}
                          className={`text-xs px-3 py-1 font-medium transition-colors ${period === 'annual' ? 'bg-orange-500 text-white cursor-default' : 'bg-white text-gray-600 hover:bg-gray-50 cursor-pointer'}`}
                        >
                          Anual
                        </button>
                        <button 
                          onClick={() => handlePeriodChange('quarterly')}
                          className={`text-xs px-3 py-1 font-medium transition-colors border-l border-gray-300 ${period === 'quarterly' ? 'bg-orange-500 text-white cursor-default' : 'bg-white text-gray-600 hover:bg-gray-50 cursor-pointer'}`}
                        >
                          Trimestral
                        </button>
                      </div>
                    </div>
                    <div className="flex space-x-2 text-gray-400 text-xs italic items-center px-2">
                      Cifras en millones (salvo métricas por acción)
                    </div>
                    <div className="flex space-x-2">
                      <button className="p-1.5 text-gray-500 hover:text-gray-900 border border-gray-300 rounded bg-white cursor-pointer"><Maximize2 className="w-3.5 h-3.5" /></button>
                      <button className="flex items-center text-xs px-2 py-1 border border-gray-300 rounded bg-white text-gray-700 hover:bg-gray-50 cursor-pointer">
                        <Download className="w-3.5 h-3.5 mr-1.5" /> Exportar
                      </button>
                    </div>
                  </div>

                  <div className="flex-1 flex flex-col">
                    {isLoading ? (
                      <div className="flex-1 flex flex-col items-center justify-center text-orange-500 py-20">
                        <Loader2 className="w-10 h-10 mb-3 animate-spin" />
                        <p className="text-sm font-medium">Extrayendo datos contables...</p>
                      </div>
                    ) : error ? (
                      <div className="flex-1 flex flex-col items-center justify-center text-red-500 py-20">
                        <p className="text-sm font-bold">Error: {error}</p>
                      </div>
                    ) : currentTabData.length > 0 ? (
                      <div className="w-full overflow-x-auto">
                        <table className="w-full text-[13px] text-left whitespace-nowrap">
                          {/* ENCABEZADO OSCURO ESTILO TIKR */}
                          <thead>
                            <tr className="bg-[#333333] text-white">
                              <th className="py-2.5 px-4 font-bold sticky left-0 bg-[#333333] z-10 w-72">
                                {activeContentTab} | MiTerminal
                              </th>
                              {availableYears.map(year => (
                                <th key={year} className="py-2.5 px-4 font-bold text-right">{year}</th>
                              ))}
                            </tr>
                          </thead>
                          
                          <tbody>
                            {currentTabData.map((row, idx) => {
                              if (row.is_header) {
                                return (
                                  <tr key={idx} className="border-b border-gray-100 bg-gray-50/80">
                                    <td 
                                      colSpan={availableYears.length + 1} 
                                      className="py-3 px-4 font-bold text-gray-900 sticky left-0 shadow-[1px_0_0_0_#f3f4f6]"
                                    >
                                      {row.Métrica}
                                    </td>
                                  </tr>
                                );
                              }

                              const isMainMetric = row.Métrica.toLowerCase().includes('total') || 
                                                   row.Métrica.toLowerCase().includes('beneficio bruto') ||
                                                   row.Métrica.toLowerCase().includes('beneficio operativo') ||
                                                   row.Métrica.toLowerCase().includes('beneficio neto');

                              return (
                                <tr key={idx} className={`border-b border-gray-100 hover:bg-gray-50 transition-colors group`}>
                                  <td className={`
                                    py-2.5 px-4 sticky left-0 bg-white group-hover:bg-gray-50 z-10 truncate shadow-[1px_0_0_0_#f3f4f6]
                                    ${row.is_sub ? 'pl-8 text-gray-600 italic' : ''}
                                    ${isMainMetric && !row.is_sub ? 'font-bold text-gray-900' : 'text-gray-700'}
                                  `}>
                                    {row.Métrica}
                                  </td>
                                  
                                  {availableYears.map(year => {
                                    const value = row[year];
                                    const isNegative = typeof value === 'number' && value < 0;
                                    
                                    return (
                                      <td 
                                        key={year} 
                                        className={`
                                          py-2.5 px-4 text-right
                                          ${isNegative ? 'text-[#d93025]' : 'text-gray-800'}
                                          ${isMainMetric && !row.is_sub ? 'font-bold' : ''}
                                          ${row.is_sub ? 'italic' : ''}
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
                          No hay datos disponibles para la pestaña de <span className="text-orange-500">{activeContentTab}</span>.
                        </p>
                      </div>
                    ) : (
                      <div className="flex-1 flex flex-col items-center justify-center text-gray-400 py-20">
                        <BarChart3 className="w-12 h-12 mb-3 text-gray-200" />
                        <p className="text-sm font-medium text-gray-500">
                          Buscá un Ticker en la cabecera (ej: AAPL) para cargar la <span className="text-orange-500">{activeContentTab}</span>.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* PESTAÑA: VALORACIÓN */}
            {activeSidebarTab === 'Valoracion' && (
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm py-20 flex flex-col items-center justify-center text-gray-400">
                <PieChart className="w-12 h-12 mb-4 text-gray-300" />
                <p className="text-lg font-medium text-gray-500">Módulo de Valoración en construcción</p>
                <p className="text-sm">Próximamente: Múltiplos, DCF y análisis de pares.</p>
              </div>
            )}

          </div>
        </div>
      </main>
    </div>
  );
}

export default App;