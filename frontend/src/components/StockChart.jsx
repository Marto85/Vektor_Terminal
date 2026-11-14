import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import * as LightweightCharts from 'lightweight-charts';
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Activity,
  Check,
  Loader2,
  Eye,
  EyeOff,
  TrendingUp,
  Type,
  Slash,
  Move,
  Ruler,
  Crosshair,
} from 'lucide-react';

const TIMEFRAMES = [
  { id: '3m', label: '3m' },
  { id: '6m', label: '6m' },
  { id: 'ytd', label: 'este año' },
  { id: '1y', label: '1 año' },
  { id: '3y', label: '3 años' },
  { id: '5y', label: '5 años' },
  { id: '10y', label: '10 años' },
  { id: 'max', label: 'todas' },
];

const CHART_METRICS = [
  'Price',
  '% Change',
  'Total Return',
  'Drawdowns',
  '10k Growth',
  'Market Cap',
  'Enterprise Value',
];

const PCT_METRICS = new Set(['% Change', 'Total Return', 'Drawdowns']);

function addCompatibleSeries(chart, kind, options) {
  if (kind === 'candlestick') {
    return typeof chart.addCandlestickSeries === 'function'
      ? chart.addCandlestickSeries(options)
      : chart.addSeries(LightweightCharts.CandlestickSeries, options);
  }
  if (kind === 'area') {
    return typeof chart.addAreaSeries === 'function'
      ? chart.addAreaSeries(options)
      : chart.addSeries(LightweightCharts.AreaSeries, options);
  }
  if (kind === 'histogram') {
    return typeof chart.addHistogramSeries === 'function'
      ? chart.addHistogramSeries(options)
      : chart.addSeries(LightweightCharts.HistogramSeries, options);
  }
  return null;
}

function formatTooltipDate(timeStr) {
  if (!timeStr) return '';
  const [y, m, d] = timeStr.split('-').map(Number);
  const dateObj = new Date(Date.UTC(y, m - 1, d));
  return dateObj.toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

function formatPctTikr(val) {
  if (val === null || val === undefined || Number.isNaN(val)) return '0,0%';
  const abs = Math.abs(val).toFixed(1).replace('.', ',');
  return val < 0 ? `(${abs}%)` : `${abs}%`;
}

function formatMetricValue(val, metric) {
  if (val === null || val === undefined || Number.isNaN(val)) return '-';
  if (PCT_METRICS.has(metric)) {
    return `${val.toFixed(2)}%`;
  }
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(val);
}

export default function StockChart({ ticker, companyName }) {
  const chartContainerRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const dropdownRef = useRef(null);

  const [timeframe, setTimeframe] = useState('1y');
  const [chartType, setChartType] = useState('candle'); // 'candle' | 'line'
  const [showMetricDropdown, setShowMetricDropdown] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState('Price');

  const [showLeftToolbar, setShowLeftToolbar] = useState(true);
  const [activeTool, setActiveTool] = useState('crosshair');
  const [showVolume, setShowVolume] = useState(true);

  const [historyData, setHistoryData] = useState(null);
  const [loadingChart, setLoadingChart] = useState(false);
  const [chartError, setChartError] = useState(null);
  const [hoverInfo, setHoverInfo] = useState(null);

  // Cerrar dropdown de métricas al hacer clic fuera
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowMetricDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  // 1. Descargar todas las series OHLCV del ticker y timeframe
  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;

    const fetchHistory = async () => {
      setLoadingChart(true);
      setChartError(null);
      try {
        const res = await axios.get(
          `http://127.0.0.1:8000/api/v1/company/${ticker.toUpperCase()}/history`,
          { params: { range: timeframe } }
        );
        if (!cancelled) {
          setHistoryData(res.data);
        }
      } catch (err) {
        if (!cancelled) {
          setChartError(err.response?.data?.detail || 'No se pudo cargar el gráfico');
        }
      } finally {
        if (!cancelled) {
          setLoadingChart(false);
        }
      }
    };

    fetchHistory();
    return () => {
      cancelled = true;
    };
  }, [ticker, timeframe]);

  const activeCandles = historyData?.seriesByMetric?.[selectedMetric] || [];

  // 2. Renderizar canvas según selectedMetric y chartType
  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container || !activeCandles.length) return;

    const isPctMetric = PCT_METRICS.has(selectedMetric);

    const chart = LightweightCharts.createChart(container, {
      width: container.clientWidth,
      height: 320,
      layout: {
        background: { type: 'solid', color: '#ffffff' },
        textColor: '#6b7280',
        fontFamily: 'Inter, system-ui, sans-serif',
        fontSize: 11,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: '#f3f4f6', style: 2 },
      },
      crosshair: {
        mode:
          activeTool === 'crosshair'
            ? LightweightCharts.CrosshairMode.Normal
            : LightweightCharts.CrosshairMode.Magnet,
        vertLine: { color: '#9ca3af', width: 1, style: 0, labelVisible: false },
        horzLine: { color: '#9ca3af', width: 1, style: 0, labelVisible: false },
      },
      localization: {
        priceFormatter: (price) => formatMetricValue(price, selectedMetric),
      },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: { top: 0.08, bottom: showVolume ? 0.24 : 0.06 },
      },
      timeScale: {
        borderColor: '#e5e7eb',
        timeVisible: false,
        rightOffset: 4,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
    });

    chartInstanceRef.current = chart;

    const priceFormat = isPctMetric
      ? { type: 'percent', precision: 2, minMove: 0.01 }
      : { type: 'price', precision: 2, minMove: 0.01 };

    let mainSeries;
    if (chartType === 'candle') {
      mainSeries = addCompatibleSeries(chart, 'candlestick', {
        upColor: '#10b981',
        downColor: '#ef4444',
        borderVisible: false,
        wickUpColor: '#10b981',
        wickDownColor: '#ef4444',
        priceFormat,
      });
      mainSeries.setData(
        activeCandles.map((c) => ({
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }))
      );
    } else {
      mainSeries = addCompatibleSeries(chart, 'area', {
        lineColor: '#f59e0b',
        lineWidth: 2,
        topColor: 'rgba(245, 158, 11, 0.18)',
        bottomColor: 'rgba(245, 158, 11, 0.0)',
        priceFormat,
      });
      mainSeries.setData(
        activeCandles.map((c) => ({
          time: c.time,
          value: c.close,
        }))
      );
    }

    if (showVolume) {
      const volumeSeries = addCompatibleSeries(chart, 'histogram', {
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
      });

      chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });

      volumeSeries.setData(
        activeCandles.map((c) => ({
          time: c.time,
          value: c.volume,
          color:
            chartType === 'candle'
              ? c.close >= c.open
                ? 'rgba(16, 185, 129, 0.6)'
                : 'rgba(239, 68, 68, 0.6)'
              : 'rgba(245, 158, 11, 0.45)',
        }))
      );
    }

    chart.timeScale().fitContent();

    const candleMap = new Map(activeCandles.map((c) => [c.time, c]));

    const handleCrosshairMove = (param) => {
      if (
        !param.point ||
        !param.time ||
        param.point.x < 0 ||
        param.point.x > container.clientWidth ||
        param.point.y < 0 ||
        param.point.y > 320
      ) {
        setHoverInfo(null);
        return;
      }

      const candle = candleMap.get(param.time);
      if (!candle) {
        setHoverInfo(null);
        return;
      }

      const tooltipWidth = 185;
      const leftPos =
        param.point.x + tooltipWidth + 24 > container.clientWidth
          ? param.point.x - tooltipWidth - 14
          : param.point.x + 14;

      const topPos = Math.min(Math.max(param.point.y - 40, 8), 170);

      setHoverInfo({
        x: leftPos,
        y: topPos,
        candle,
      });
    };

    chart.subscribeCrosshairMove(handleCrosshairMove);

    const resizeObserver = new ResizeObserver((entries) => {
      if (entries.length > 0 && entries[0].contentRect.width > 0) {
        chart.applyOptions({ width: entries[0].contentRect.width });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      chart.remove();
      chartInstanceRef.current = null;
      setHoverInfo(null);
    };
  }, [activeCandles, selectedMetric, chartType, showVolume, activeTool]);

  const handleResetZoom = () => {
    if (chartInstanceRef.current) {
      chartInstanceRef.current.timeScale().fitContent();
    }
  };

  const totalRet = historyData?.totalReturnPct ?? 0;
  const cagr = historyData?.cagrPct ?? 0;
  const yearsLabel = historyData?.years
    ? historyData.years.toFixed(2).replace('.', ',')
    : '1,00';

  const isPctSelected = PCT_METRICS.has(selectedMetric);
  const unitSuffix =
    selectedMetric === 'Market Cap' || selectedMetric === 'Enterprise Value' ? ' MM' : '';

  return (
    <div className="flex-1 bg-white border border-gray-200 rounded shadow-sm flex flex-col relative min-w-0">
      {/* Cabecera superior del gráfico */}
      <div className="px-4 py-3 flex justify-between items-start">
        <div>
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 bg-[#dc2626] rounded-xs flex items-center justify-center text-white text-[10px] font-bold">
              {ticker.charAt(0)}
            </div>
            <span className="text-sm font-bold text-gray-900">{ticker}</span>
            <span className="text-sm text-gray-500">{companyName || 'Cargando...'}</span>
          </div>
          <p className="text-[11px] text-gray-600 mt-1.5">
            <span className={`font-semibold ${totalRet < 0 ? 'text-red-600' : 'text-green-600'}`}>
              {formatPctTikr(totalRet)}
            </span>{' '}
            retorno del precio sobre <span className="font-bold text-gray-900">{yearsLabel}</span> años -{' '}
            <span className={`font-semibold ${cagr < 0 ? 'text-red-600' : 'text-green-600'}`}>
              {formatPctTikr(cagr)}
            </span>{' '}
            Crecimiento compuesto
          </p>
        </div>

        <div className="flex space-x-2 relative" ref={dropdownRef}>
          <button
            onClick={() => setShowMetricDropdown((prev) => !prev)}
            className="flex items-center px-3 py-1 border border-gray-300 rounded text-[13px] font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 cursor-pointer transition-colors"
          >
            {selectedMetric} <ChevronDown className="w-3.5 h-3.5 ml-1.5 text-gray-500" />
          </button>

          {showMetricDropdown && (
            <div className="absolute top-full left-0 mt-1 w-48 bg-white border border-gray-200 rounded shadow-lg py-1.5 z-50">
              {CHART_METRICS.map((metric) => (
                <div
                  key={metric}
                  onClick={() => {
                    setSelectedMetric(metric);
                    setShowMetricDropdown(false);
                  }}
                  className="flex justify-between items-center px-4 py-2 hover:bg-gray-50 cursor-pointer text-[13px] text-gray-800"
                >
                  <span>{metric}</span>
                  {selectedMetric === metric && <Check className="w-4 h-4 text-gray-400" />}
                </div>
              ))}
            </div>
          )}

          <button className="px-3 py-1 bg-black text-white rounded text-[13px] font-medium hover:bg-gray-800 cursor-pointer">
            Descargar
          </button>
          <button className="p-1 border border-gray-300 rounded text-gray-500 hover:bg-gray-50 cursor-pointer">
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Botonera interactiva de Timeframes */}
      <div className="px-4 py-1.5 flex items-center space-x-2 text-[13px]">
        {TIMEFRAMES.map((tf) => {
          const isActive = timeframe === tf.id;
          return (
            <button
              key={tf.id}
              onClick={() => setTimeframe(tf.id)}
              className={`px-2 py-1 rounded transition-colors cursor-pointer ${
                isActive
                  ? 'bg-gray-200/80 text-gray-900 font-semibold'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              {tf.label}
            </button>
          );
        })}
        <button className="border border-gray-300 px-2.5 py-1 rounded text-gray-600 hover:bg-gray-50 cursor-pointer shadow-xs ml-1">
          Fecha personalizada
        </button>
      </div>

      {/* Cuerpo del gráfico: Barra de herramientas izquierda + Canvas */}
      <div className="relative flex w-full h-[320px] mt-1">
        {showLeftToolbar ? (
          <div className="w-9 shrink-0 border-r border-gray-100 bg-[#fafafa] flex flex-col items-center py-1.5 space-y-1.5 relative select-none">
            <button
              onClick={() => setActiveTool('crosshair')}
              title="Cursor / Crosshair"
              className={`w-7 h-7 rounded flex items-center justify-center cursor-pointer transition-colors ${
                activeTool === 'crosshair'
                  ? 'bg-gray-200/80 text-gray-900'
                  : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'
              }`}
            >
              <Crosshair className="w-4 h-4" />
            </button>

            <button
              onClick={() => setActiveTool('magnet')}
              title="Ajuste magnético a vela"
              className={`w-7 h-7 rounded flex items-center justify-center cursor-pointer transition-colors ${
                activeTool === 'magnet'
                  ? 'bg-gray-200/80 text-gray-900'
                  : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'
              }`}
            >
              <TrendingUp className="w-4 h-4" />
            </button>

            <div className="w-5 border-t border-gray-200 my-0.5" />

            <button
              onClick={() => setActiveTool('text')}
              title="Anotación de texto"
              className={`w-7 h-7 rounded flex items-center justify-center cursor-pointer transition-colors ${
                activeTool === 'text'
                  ? 'bg-gray-200/80 text-gray-900'
                  : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'
              }`}
            >
              <Type className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={() => setActiveTool('trendline')}
              title="Línea de tendencia"
              className={`w-7 h-7 rounded flex items-center justify-center cursor-pointer transition-colors ${
                activeTool === 'trendline'
                  ? 'bg-gray-200/80 text-gray-900'
                  : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'
              }`}
            >
              <Slash className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={handleResetZoom}
              title="Centrar y ajustar escala"
              className="w-7 h-7 rounded flex items-center justify-center text-gray-500 hover:bg-gray-100 hover:text-gray-800 cursor-pointer transition-colors"
            >
              <Move className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={() => setShowVolume((prev) => !prev)}
              title={showVolume ? 'Ocultar volumen' : 'Mostrar volumen'}
              className={`w-7 h-7 rounded flex items-center justify-center cursor-pointer transition-colors ${
                !showVolume
                  ? 'bg-orange-50 text-orange-500'
                  : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'
              }`}
            >
              {showVolume ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            </button>

            <button
              onClick={() => setActiveTool('measure')}
              title="Regla de medición"
              className={`w-7 h-7 rounded flex items-center justify-center cursor-pointer transition-colors ${
                activeTool === 'measure'
                  ? 'bg-gray-200/80 text-gray-900'
                  : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'
              }`}
            >
              <Ruler className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={() => setShowLeftToolbar(false)}
              title="Ocultar herramientas"
              className="absolute -right-2.5 top-2 w-2.5 h-5 bg-white border border-gray-200 rounded-r flex items-center justify-center text-gray-400 hover:text-gray-700 cursor-pointer z-20 shadow-2xs"
            >
              <ChevronLeft className="w-2.5 h-2.5" />
            </button>
          </div>
        ) : (
          <button
            onClick={() => setShowLeftToolbar(true)}
            title="Mostrar herramientas"
            className="w-3 h-6 mt-2 bg-white border border-l-0 border-gray-200 rounded-r flex items-center justify-center text-gray-400 hover:text-gray-700 cursor-pointer z-20 shrink-0"
          >
            <ChevronRight className="w-2.5 h-2.5" />
          </button>
        )}

        {/* Área Canvas + Tooltip flotante */}
        <div className="relative flex-1 h-full min-w-0">
          {loadingChart && (
            <div className="absolute inset-0 bg-white/75 z-20 flex items-center justify-center text-orange-500">
              <Loader2 className="w-6 h-6 animate-spin mr-2" />
              <span className="text-xs font-medium">Cargando serie histórica...</span>
            </div>
          )}

          {chartError ? (
            <div className="h-full flex items-center justify-center text-xs text-red-500 font-medium px-4 text-center">
              {chartError}
            </div>
          ) : !loadingChart && historyData && activeCandles.length === 0 ? (
            <div className="h-full flex items-center justify-center text-xs text-gray-500 font-medium px-4 text-center">
              La métrica <span className="font-bold mx-1">{selectedMetric}</span> no está disponible para este instrumento.
            </div>
          ) : (
            <>
              <div ref={chartContainerRef} className="w-full h-full" />
              {showVolume && activeCandles.length > 0 && (
                <div className="pointer-events-none absolute left-0 right-14 bottom-[22%] border-t border-gray-200/80" />
              )}
            </>
          )}

          {/* Cuadrito flotante OHLC estilo TIKR */}
          {hoverInfo && (
            <div
              style={{ left: `${hoverInfo.x}px`, top: `${hoverInfo.y}px` }}
              className="pointer-events-none absolute z-30 w-[184px] bg-white border border-gray-200 rounded-md shadow-lg px-3 py-2.5 text-[12px] leading-snug"
            >
              <div className="text-gray-500 text-[11px] mb-1">
                {formatTooltipDate(hoverInfo.candle.time)}
              </div>
              <div
                className={`font-semibold mb-1.5 ${
                  hoverInfo.candle.change < 0 ? 'text-red-600' : 'text-green-600'
                }`}
              >
                {hoverInfo.candle.change > 0 ? '+' : ''}
                {formatMetricValue(hoverInfo.candle.change, selectedMetric)}
                {!isPctSelected && (
                  <>
                    {' '}({hoverInfo.candle.changePct > 0 ? '+' : ''}
                    {hoverInfo.candle.changePct.toFixed(2)}%)
                  </>
                )}
              </div>
              <div className="space-y-0.5 text-gray-700">
                <div>
                  Open:{' '}
                  <span className="font-bold text-gray-900">
                    {formatMetricValue(hoverInfo.candle.open, selectedMetric)}
                    {unitSuffix}
                  </span>
                </div>
                <div>
                  High:{' '}
                  <span className="font-bold text-gray-900">
                    {formatMetricValue(hoverInfo.candle.high, selectedMetric)}
                    {unitSuffix}
                  </span>
                </div>
                <div>
                  Low:{' '}
                  <span className="font-bold text-gray-900">
                    {formatMetricValue(hoverInfo.candle.low, selectedMetric)}
                    {unitSuffix}
                  </span>
                </div>
                <div>
                  Close:{' '}
                  <span className="font-bold text-gray-900">
                    {formatMetricValue(hoverInfo.candle.close, selectedMetric)}
                    {unitSuffix}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Barra inferior del gráfico */}
      <div className="px-4 py-3 mt-auto border-t border-gray-100 flex items-center justify-between bg-[#fcfcfc] rounded-b">
        <div className="relative w-[320px]">
          <input
            type="text"
            placeholder={
              chartType === 'candle'
                ? 'Las comparaciones no están disponibles en la vista de velas'
                : 'Compara con un competidor, índice o ETF sectorial...'
            }
            disabled={chartType === 'candle'}
            className={`w-full pl-3 pr-8 py-1.5 border border-gray-300 rounded shadow-xs text-xs focus:outline-none focus:border-orange-500 ${
              chartType === 'candle'
                ? 'bg-gray-100 text-gray-400 placeholder-gray-300'
                : 'bg-white text-gray-700'
            }`}
          />
          <ChevronDown className="w-4 h-4 absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-400" />
        </div>

        <div className="flex space-x-2">
          <button
            onClick={() => setShowVolume((prev) => !prev)}
            className="px-3 py-1.5 border border-gray-300 rounded text-xs font-medium text-gray-700 bg-white hover:bg-gray-50 cursor-pointer shadow-xs"
          >
            {showVolume ? 'Hide Indicators' : 'Show Indicators'}
          </button>
          <button
            onClick={() => setChartType((prev) => (prev === 'line' ? 'candle' : 'line'))}
            className="p-1.5 border border-gray-300 rounded bg-white text-gray-600 hover:bg-gray-50 flex items-center cursor-pointer shadow-xs"
            title={chartType === 'line' ? 'Cambiar a velas japonesas' : 'Cambiar a gráfico de línea'}
          >
            {chartType === 'line' ? (
              <div className="flex space-x-0.5 items-end h-4 w-4 justify-center">
                <div className="w-0.75 h-3 bg-red-500 rounded-[1px]"></div>
                <div className="w-0.75 h-4 bg-green-500 rounded-[1px]"></div>
              </div>
            ) : (
              <Activity className="w-4 h-4 text-orange-500" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}