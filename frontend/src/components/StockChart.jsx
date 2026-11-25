import { useEffect, useMemo, useRef, useState } from 'react';
import apiClient from '../api/client';
import * as LightweightCharts from 'lightweight-charts';
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
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
  SlidersHorizontal,
  Info,
  Compass,
  X,
} from 'lucide-react';
import {
  calculateSMA,
  calculateEMA,
  calculateBollingerBands,
  calculateVWAP,
  calculateVolumeSMA,
  calculateRSI,
  calculateMACD,
  calculateATR,
  buildTechnicalExplanation,
} from '../utils/technicalIndicators';
import {
  TECHNICAL_MODES,
  runTechnicalAnalysisMode,
} from '../utils/technicalAnalysisModes';

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

const INTERVALS = [
  { id: '15m', label: '15m' },
  { id: '1h', label: '1h' },
  { id: '1d', label: '1D' },
  { id: '1wk', label: '1 Sem' },
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

const INDICATOR_OPTIONS = [
  { id: 'sma20', label: 'SMA 20', group: 'Tendencia', color: '#2563eb' },
  { id: 'sma50', label: 'SMA 50', group: 'Tendencia', color: '#f59e0b' },
  { id: 'sma200', label: 'SMA 200', group: 'Tendencia', color: '#dc2626' },
  { id: 'ema21', label: 'EMA 21', group: 'Tendencia', color: '#8b5cf6' },
  { id: 'bb', label: 'Bollinger (20, 2)', group: 'Volatilidad', color: '#0891b2' },
  { id: 'vwap', label: 'VWAP', group: 'Volumen', color: '#db2777' },
  { id: 'volSma', label: 'Media Vol (20)', group: 'Volumen', color: '#475569' },
  { id: 'rsi', label: 'RSI (14)', group: 'Oscilador', color: '#7c3aed' },
  { id: 'macd', label: 'MACD (12, 26, 9)', group: 'Oscilador', color: '#0284c7' },
  { id: 'atr', label: 'ATR (14)', group: 'Volatilidad', color: '#d97706' },
];

const EMPTY_INDICATORS = {
  sma20: false,
  sma50: false,
  sma200: false,
  ema21: false,
  bb: false,
  vwap: false,
  volSma: false,
  rsi: false,
  macd: false,
  atr: false,
};

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
  if (kind === 'line') {
    return typeof chart.addLineSeries === 'function'
      ? chart.addLineSeries(options)
      : chart.addSeries(LightweightCharts.LineSeries, options);
  }
  if (kind === 'histogram') {
    return typeof chart.addHistogramSeries === 'function'
      ? chart.addHistogramSeries(options)
      : chart.addSeries(LightweightCharts.HistogramSeries, options);
  }
  return null;
}

function applyCompatibleMarkers(series, markers) {
  if (!series || !markers || !markers.length) return;
  if (typeof series.setMarkers === 'function') {
    series.setMarkers(markers);
  } else if (typeof LightweightCharts.createSeriesMarkers === 'function') {
    LightweightCharts.createSeriesMarkers(series, markers);
  }
}

function formatTooltipDate(timeVal) {
  if (!timeVal) return '';
  if (typeof timeVal === 'number') {
    const dateObj = new Date(timeVal * 1000);
    return dateObj.toLocaleString('es-AR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: 'UTC',
    });
  }
  const [y, m, d] = String(timeVal).split('-').map(Number);
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
  const subChartContainerRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const subChartInstanceRef = useRef(null);
  const dropdownRef = useRef(null);
  const indicatorsDropdownRef = useRef(null);
  const modeDropdownRef = useRef(null);

  const [timeframe, setTimeframe] = useState('1y');
  const [interval, setInterval] = useState('1d');
  const [chartType, setChartType] = useState('candle');
  const [isExpanded, setIsExpanded] = useState(false);
  const [showMetricDropdown, setShowMetricDropdown] = useState(false);
  const [showIndicatorsDropdown, setShowIndicatorsDropdown] = useState(false);
  const [showModeDropdown, setShowModeDropdown] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState('Price');

  const [technicalMode, setTechnicalMode] = useState('none');

  const [showLeftToolbar, setShowLeftToolbar] = useState(true);
  const [activeTool, setActiveTool] = useState('crosshair');
  const [showVolume, setShowVolume] = useState(true);

  const [indicators, setIndicators] = useState({
    ...EMPTY_INDICATORS,
    sma50: true,
    volSma: true,
  });

  const [activeOscillator, setActiveOscillator] = useState('rsi');
  const [showExplanation, setShowExplanation] = useState(true);

  const [historyData, setHistoryData] = useState(null);
  const [loadingChart, setLoadingChart] = useState(false);
  const [chartError, setChartError] = useState(null);
  const [hoverInfo, setHoverInfo] = useState(null);

  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowMetricDropdown(false);
      }
      if (indicatorsDropdownRef.current && !indicatorsDropdownRef.current.contains(e.target)) {
        setShowIndicatorsDropdown(false);
      }
      if (modeDropdownRef.current && !modeDropdownRef.current.contains(e.target)) {
        setShowModeDropdown(false);
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setIsExpanded(false);
        setShowMetricDropdown(false);
        setShowIndicatorsDropdown(false);
        setShowModeDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const toggleIndicator = (id) => {
    setIndicators((prev) => {
      const nextVal = !prev[id];
      const next = { ...prev, [id]: nextVal };
      if (nextVal && (id === 'rsi' || id === 'macd' || id === 'atr')) {
        setActiveOscillator(id);
      }
      return next;
    });
  };

  const handleClearAllIndicators = () => {
    setIndicators({ ...EMPTY_INDICATORS });
    setTechnicalMode('none');
  };

  const handleSelectTechnicalMode = (modeId) => {
    setTechnicalMode(modeId);
    setShowModeDropdown(false);
    setShowExplanation(true);
    if (modeId === 'trend') {
      setIndicators((prev) => ({ ...prev, sma20: true, sma50: true, sma200: true }));
    } else if (modeId === 'momentum') {
      setIndicators((prev) => ({ ...prev, rsi: true, bb: true, atr: true }));
      setActiveOscillator('rsi');
    }
  };

  const handleTimeframeSelect = (tfId) => {
    setTimeframe(tfId);
    if ((tfId === '5y' || tfId === '10y' || tfId === 'max') && (interval === '15m' || interval === '1h')) {
      setInterval('1wk');
    }
  };

  const handleIntervalSelect = (intId) => {
    setInterval(intId);
    if (intId === '15m' && timeframe !== '3m') {
      setTimeframe('3m');
    } else if (intId === '1h' && (timeframe === '3y' || timeframe === '5y' || timeframe === '10y' || timeframe === 'max')) {
      setTimeframe('1y');
    } else if (intId === '1wk' && (timeframe === '3m' || timeframe === '6m' || timeframe === 'ytd')) {
      setTimeframe('1y');
    }
  };

  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;

    const fetchHistory = async () => {
      setLoadingChart(true);
      setChartError(null);
      try {
        const res = await apiClient.get(
          `/company/${ticker.toUpperCase()}/history`,
          { params: { range: timeframe, interval } }
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
  }, [ticker, timeframe, interval]);

  const activeCandles = useMemo(
    () => historyData?.seriesByMetric?.[selectedMetric] || [],
    [historyData, selectedMetric]
  );

  const isIntraday = Boolean(historyData?.isIntraday || interval === '15m' || interval === '1h');

  const computedIndicators = useMemo(() => {
    if (!activeCandles.length) return {};
    return {
      sma20: indicators.sma20 ? calculateSMA(activeCandles, 20) : [],
      sma50: indicators.sma50 ? calculateSMA(activeCandles, 50) : [],
      sma200: indicators.sma200 ? calculateSMA(activeCandles, 200) : [],
      ema21: indicators.ema21 ? calculateEMA(activeCandles, 21) : [],
      bb: indicators.bb ? calculateBollingerBands(activeCandles, 20, 2) : { upper: [], middle: [], lower: [] },
      vwap: indicators.vwap ? calculateVWAP(activeCandles, isIntraday) : [],
      volSma20: calculateVolumeSMA(activeCandles, 20),
      rsi: indicators.rsi ? calculateRSI(activeCandles, 14) : [],
      macd: indicators.macd ? calculateMACD(activeCandles, 12, 26, 9) : { macdLine: [], signalLine: [], histogram: [] },
      atr: indicators.atr ? calculateATR(activeCandles, 14) : [],
    };
  }, [activeCandles, indicators, isIntraday]);

  const modeAnalysis = useMemo(() => {
    if (selectedMetric !== 'Price' || technicalMode === 'none') return null;
    return runTechnicalAnalysisMode(activeCandles, technicalMode);
  }, [activeCandles, selectedMetric, technicalMode]);

  const hasSubPanel = indicators.rsi || indicators.macd || indicators.atr;
  const resolvedOscillator = useMemo(() => {
    if (indicators[activeOscillator]) return activeOscillator;
    if (indicators.rsi) return 'rsi';
    if (indicators.macd) return 'macd';
    if (indicators.atr) return 'atr';
    return null;
  }, [indicators, activeOscillator]);

  const technicalExplanation = useMemo(() => {
    const intervalObj = INTERVALS.find((i) => i.id === interval);
    return buildTechnicalExplanation({
      candles: activeCandles,
      activeIndicators: indicators,
      intervalLabel: intervalObj ? intervalObj.label : interval,
      computed: computedIndicators,
    });
  }, [activeCandles, indicators, interval, computedIndicators]);

  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container || !activeCandles.length) return;

    const isPctMetric = PCT_METRICS.has(selectedMetric);
    const mainHeight = isExpanded
      ? hasSubPanel
        ? 440
        : 520
      : hasSubPanel
      ? 270
      : 320;

    const chart = LightweightCharts.createChart(container, {
      width: container.clientWidth,
      height: mainHeight,
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
        timeVisible: isIntraday,
        secondsVisible: false,
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

    const addLineOverlay = (data, color, lineWidth = 1.5, lineStyle = 0) => {
      if (!data || !data.length) return;
      const s = addCompatibleSeries(chart, 'line', {
        color,
        lineWidth,
        lineStyle,
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });
      s.setData(data);
    };

    if (indicators.sma20) addLineOverlay(computedIndicators.sma20, '#2563eb', 1.5);
    if (indicators.sma50) addLineOverlay(computedIndicators.sma50, '#f59e0b', 1.5);
    if (indicators.sma200) addLineOverlay(computedIndicators.sma200, '#dc2626', 1.75);
    if (indicators.ema21) addLineOverlay(computedIndicators.ema21, '#8b5cf6', 1.5);
    if (indicators.vwap) addLineOverlay(computedIndicators.vwap, '#db2777', 1.5, 2);

    if (indicators.bb && computedIndicators.bb?.upper?.length) {
      addLineOverlay(computedIndicators.bb.upper, 'rgba(8, 145, 178, 0.75)', 1.2);
      addLineOverlay(computedIndicators.bb.middle, 'rgba(8, 145, 178, 0.45)', 1, 2);
      addLineOverlay(computedIndicators.bb.lower, 'rgba(8, 145, 178, 0.75)', 1.2);
    }

    if (modeAnalysis) {
      for (const ov of modeAnalysis.overlays || []) {
        addLineOverlay(ov.data, ov.color, ov.lineWidth || 1.5, ov.lineStyle || 0);
      }

      for (const pl of modeAnalysis.priceLines || []) {
        mainSeries.createPriceLine({
          price: pl.price,
          color: pl.color,
          lineWidth: 1,
          lineStyle: pl.lineStyle ?? 2,
          axisLabelVisible: true,
          title: pl.title || '',
        });
      }

      if (modeAnalysis.markers && modeAnalysis.markers.length > 0) {
        applyCompatibleMarkers(mainSeries, modeAnalysis.markers);
      }
    }

    if (showVolume) {
      const volumeSeries = addCompatibleSeries(chart, 'histogram', {
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
        lastValueVisible: false,
        priceLineVisible: false,
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
                ? 'rgba(16, 185, 129, 0.55)'
                : 'rgba(239, 68, 68, 0.55)'
              : 'rgba(245, 158, 11, 0.45)',
        }))
      );

      if (indicators.volSma && computedIndicators.volSma20?.length) {
        const volSmaSeries = addCompatibleSeries(chart, 'line', {
          color: '#475569',
          lineWidth: 1.25,
          priceScaleId: 'volume',
          lastValueVisible: false,
          priceLineVisible: false,
          crosshairMarkerVisible: false,
        });
        volSmaSeries.setData(computedIndicators.volSma20);
      }
    }

    chart.timeScale().fitContent();

    let subChart = null;
    const subContainer = subChartContainerRef.current;
    if (hasSubPanel && resolvedOscillator && subContainer) {
      subChart = LightweightCharts.createChart(subContainer, {
        width: subContainer.clientWidth,
        height: 92,
        layout: {
          background: { type: 'solid', color: '#fafafa' },
          textColor: '#6b7280',
          fontFamily: 'Inter, system-ui, sans-serif',
          fontSize: 10,
        },
        grid: {
          vertLines: { visible: false },
          horzLines: { color: '#e5e7eb', style: 2 },
        },
        rightPriceScale: {
          borderVisible: false,
          scaleMargins: { top: 0.12, bottom: 0.12 },
        },
        timeScale: {
          borderColor: '#e5e7eb',
          timeVisible: isIntraday,
          visible: false,
          rightOffset: 4,
        },
        crosshair: {
          vertLine: { color: '#9ca3af', width: 1, style: 0, labelVisible: false },
          horzLine: { color: '#9ca3af', width: 1, style: 0, labelVisible: false },
        },
      });

      subChartInstanceRef.current = subChart;

      if (resolvedOscillator === 'rsi' && computedIndicators.rsi?.length) {
        const rsiLine = addCompatibleSeries(subChart, 'line', {
          color: '#7c3aed',
          lineWidth: 1.5,
          lastValueVisible: true,
          priceLineVisible: false,
        });
        rsiLine.setData(computedIndicators.rsi);
        rsiLine.createPriceLine({ price: 70, color: '#ef4444', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: '' });
        rsiLine.createPriceLine({ price: 30, color: '#10b981', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: '' });
      } else if (resolvedOscillator === 'macd' && computedIndicators.macd?.macdLine?.length) {
        const histSeries = addCompatibleSeries(subChart, 'histogram', {
          lastValueVisible: false,
          priceLineVisible: false,
        });
        histSeries.setData(computedIndicators.macd.histogram);

        const mLine = addCompatibleSeries(subChart, 'line', {
          color: '#0284c7',
          lineWidth: 1.5,
          lastValueVisible: false,
          priceLineVisible: false,
        });
        mLine.setData(computedIndicators.macd.macdLine);

        const sLine = addCompatibleSeries(subChart, 'line', {
          color: '#f97316',
          lineWidth: 1.25,
          lastValueVisible: false,
          priceLineVisible: false,
        });
        sLine.setData(computedIndicators.macd.signalLine);
      } else if (resolvedOscillator === 'atr' && computedIndicators.atr?.length) {
        const atrLine = addCompatibleSeries(subChart, 'line', {
          color: '#d97706',
          lineWidth: 1.5,
          lastValueVisible: true,
          priceLineVisible: false,
        });
        atrLine.setData(computedIndicators.atr);
      }

      subChart.timeScale().fitContent();

      chart.timeScale().subscribeVisibleLogicalRangeChange((logicalRange) => {
        if (logicalRange && subChart) {
          subChart.timeScale().setVisibleLogicalRange(logicalRange);
        }
      });
      subChart.timeScale().subscribeVisibleLogicalRangeChange((logicalRange) => {
        if (logicalRange && chart) {
          chart.timeScale().setVisibleLogicalRange(logicalRange);
        }
      });
    }

    const candleMap = new Map(activeCandles.map((c) => [c.time, c]));
    const volAvgMap = new Map((computedIndicators.volSma20 || []).map((v) => [v.time, v.value]));

    const handleCrosshairMove = (param) => {
      if (
        !param.point ||
        !param.time ||
        param.point.x < 0 ||
        param.point.x > container.clientWidth ||
        param.point.y < 0 ||
        param.point.y > mainHeight
      ) {
        setHoverInfo(null);
        return;
      }

      const candle = candleMap.get(param.time);
      if (!candle) {
        setHoverInfo(null);
        return;
      }

      const volAvg = volAvgMap.get(param.time);
      const rvol = volAvg && volAvg > 0 ? candle.volume / volAvg : null;

      const tooltipWidth = 195;
      const leftPos =
        param.point.x + tooltipWidth + 24 > container.clientWidth
          ? param.point.x - tooltipWidth - 14
          : param.point.x + 14;

      const topPos = Math.min(Math.max(param.point.y - 40, 8), mainHeight - 145);

      setHoverInfo({
        x: leftPos,
        y: topPos,
        candle,
        rvol,
      });
    };

    chart.subscribeCrosshairMove(handleCrosshairMove);

    const resizeObserver = new ResizeObserver((entries) => {
      if (entries.length > 0 && entries[0].contentRect.width > 0) {
        const w = entries[0].contentRect.width;
        chart.applyOptions({ width: w });
        if (subChart) {
          subChart.applyOptions({ width: w });
        }
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      chart.remove();
      chartInstanceRef.current = null;
      if (subChart) {
        subChart.remove();
        subChartInstanceRef.current = null;
      }
      setHoverInfo(null);
    };
  }, [
    activeCandles,
    selectedMetric,
    chartType,
    showVolume,
    activeTool,
    indicators,
    computedIndicators,
    hasSubPanel,
    resolvedOscillator,
    isIntraday,
    modeAnalysis,
    isExpanded,
  ]);

  const handleResetZoom = () => {
    if (chartInstanceRef.current) {
      chartInstanceRef.current.timeScale().fitContent();
    }
    if (subChartInstanceRef.current) {
      subChartInstanceRef.current.timeScale().fitContent();
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

  const activeIndicatorsCount = Object.values(indicators).filter(Boolean).length;
  const currentModeObj = TECHNICAL_MODES.find((m) => m.id === technicalMode) || TECHNICAL_MODES[0];

  const mainCanvasHeight = isExpanded
    ? hasSubPanel
      ? 440
      : 520
    : hasSubPanel
    ? 270
    : 320;
  const totalChartAreaHeight = hasSubPanel ? mainCanvasHeight + 94 : mainCanvasHeight;

  return (
    <>
      {isExpanded && (
        <div
          onClick={() => setIsExpanded(false)}
          className="fixed inset-0 bg-black/50 backdrop-blur-[1px] z-40"
        />
      )}

      <div
        className={
          isExpanded
            ? 'fixed inset-3 md:inset-6 z-50 bg-white rounded-xl shadow-2xl border border-gray-200 flex flex-col overflow-y-auto'
            : 'w-full lg:w-[47%] flex flex-col relative min-w-0 border-b lg:border-b-0 lg:border-r border-gray-100'
        }
      >
        {/* Cabecera superior del gráfico */}
        <div className="px-4 py-3 flex justify-between items-start gap-2">
          <div className="min-w-0">
            <div className="flex items-center space-x-2">
              <div className="w-4 h-4 bg-[#dc2626] rounded-xs flex items-center justify-center text-white text-[10px] font-bold shrink-0">
                {ticker.charAt(0)}
              </div>
              <span className="text-sm font-bold text-gray-900">{ticker}</span>
              <span className="text-sm text-gray-500 truncate">{companyName || 'Cargando...'}</span>
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

          <div className="flex space-x-1.5 relative shrink-0" ref={dropdownRef}>
            <button
              onClick={() => setShowMetricDropdown((prev) => !prev)}
              className="flex items-center px-2.5 py-1 border border-gray-300 rounded text-[12px] font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 cursor-pointer transition-colors"
            >
              {selectedMetric} <ChevronDown className="w-3.5 h-3.5 ml-1 text-gray-500" />
            </button>

            {showMetricDropdown && (
              <div className="absolute top-full right-0 mt-1 w-48 bg-white border border-gray-200 rounded shadow-lg py-1.5 z-50">
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

            <button
              onClick={() => setIsExpanded((prev) => !prev)}
              title={isExpanded ? 'Restaurar tamaño (Esc)' : 'Expandir gráfico a pantalla completa'}
              className="p-1.5 border border-gray-300 rounded text-gray-600 hover:bg-gray-100 cursor-pointer transition-colors"
            >
              {isExpanded ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {/* Botonera de Timeframes + Temporalidad + Enfoque AT + Indicadores */}
        <div className="px-4 py-1.5 flex flex-wrap items-center justify-between gap-1.5 text-xs border-y border-gray-100 bg-[#fcfcfc]">
          <div className="flex items-center space-x-0.5 overflow-x-auto">
            {TIMEFRAMES.map((tf) => {
              const isActive = timeframe === tf.id;
              return (
                <button
                  key={tf.id}
                  onClick={() => handleTimeframeSelect(tf.id)}
                  className={`px-1.5 py-1 rounded transition-colors cursor-pointer shrink-0 ${
                    isActive
                      ? 'bg-gray-200/80 text-gray-900 font-semibold'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  }`}
                >
                  {tf.label}
                </button>
              );
            })}
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            {/* Selector de temporalidad de vela (15m, 1h, 1D, 1 Sem) */}
            <div className="flex items-center bg-gray-100 rounded p-0.5 border border-gray-200">
              {INTERVALS.map((intItem) => {
                const active = interval === intItem.id;
                return (
                  <button
                    key={intItem.id}
                    onClick={() => handleIntervalSelect(intItem.id)}
                    title={`Temporalidad de vela: ${intItem.label}`}
                    className={`px-1.5 py-0.5 rounded text-[11px] cursor-pointer transition-colors ${
                      active
                        ? 'bg-white text-gray-900 font-semibold shadow-2xs'
                        : 'text-gray-500 hover:text-gray-800'
                    }`}
                  >
                    {intItem.label}
                  </button>
                );
              })}
            </div>

            {/* Selector de Enfoque Técnico Automático (Etapa 14B) */}
            <div className="relative" ref={modeDropdownRef}>
              <button
                onClick={() => setShowModeDropdown((prev) => !prev)}
                disabled={selectedMetric !== 'Price'}
                title={
                  selectedMetric !== 'Price'
                    ? 'El análisis técnico automático requiere métrica Price'
                    : 'Seleccionar enfoque de análisis técnico automático'
                }
                className={`flex items-center space-x-1 px-2 py-1 border rounded text-[11px] font-medium cursor-pointer transition-colors ${
                  technicalMode !== 'none' && selectedMetric === 'Price'
                    ? 'border-purple-300 bg-purple-50 text-purple-800'
                    : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50'
                }`}
              >
                <Compass className="w-3 h-3" />
                <span>{technicalMode === 'none' ? 'Enfoque AT' : currentModeObj.label}</span>
                <ChevronDown className="w-3 h-3 text-gray-400" />
              </button>

              {showModeDropdown && (
                <div className="absolute left-0 top-full mt-1 w-56 bg-white border border-gray-200 rounded-md shadow-xl py-1.5 z-50">
                  <div className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400 border-b border-gray-100">
                    Lente Metodológica Automática
                  </div>
                  {TECHNICAL_MODES.map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => handleSelectTechnicalMode(m.id)}
                      className="w-full flex items-center justify-between px-3 py-1.5 hover:bg-gray-50 cursor-pointer text-left text-xs text-gray-800"
                    >
                      <span className={technicalMode === m.id ? 'font-semibold text-purple-700' : ''}>
                        {m.label}
                      </span>
                      {technicalMode === m.id && <Check className="w-3.5 h-3.5 text-purple-600" />}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Dropdown de Indicadores Técnicos */}
            <div className="relative" ref={indicatorsDropdownRef}>
              <button
                onClick={() => setShowIndicatorsDropdown((prev) => !prev)}
                className={`flex items-center space-x-1 px-2 py-1 border rounded text-[11px] font-medium cursor-pointer transition-colors ${
                  activeIndicatorsCount > 0
                    ? 'border-blue-300 bg-blue-50/70 text-blue-700'
                    : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                <SlidersHorizontal className="w-3 h-3" />
                <span>Indicadores</span>
                {activeIndicatorsCount > 0 && (
                  <span className="px-1 bg-blue-600 text-white rounded-full text-[10px] leading-tight">
                    {activeIndicatorsCount}
                  </span>
                )}
              </button>

              {showIndicatorsDropdown && (
                <div className="absolute left-0 top-full mt-1 w-64 bg-white border border-gray-200 rounded-md shadow-xl py-1.5 z-50">
                  <div className="px-3 py-1.5 flex items-center justify-between border-b border-gray-100">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                      Indicadores Técnicos
                    </span>
                    {(activeIndicatorsCount > 0 || technicalMode !== 'none') && (
                      <button
                        type="button"
                        onClick={handleClearAllIndicators}
                        className="text-[11px] font-medium text-red-600 hover:text-red-700 hover:underline cursor-pointer"
                      >
                        Quitar todos
                      </button>
                    )}
                  </div>
                  {INDICATOR_OPTIONS.map((opt) => {
                    const checked = Boolean(indicators[opt.id]);
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => toggleIndicator(opt.id)}
                        className="w-full flex items-center justify-between px-3 py-1.5 hover:bg-gray-50 cursor-pointer text-left text-xs"
                      >
                        <div className="flex items-center space-x-2">
                          <span
                            className="w-2.5 h-2.5 rounded-full shrink-0"
                            style={{ backgroundColor: opt.color }}
                          />
                          <span className="text-gray-800 font-medium">{opt.label}</span>
                          <span className="text-[10px] text-gray-400">{opt.group}</span>
                        </div>
                        <div
                          className={`w-4 h-4 rounded border flex items-center justify-center ${
                            checked ? 'bg-blue-600 border-blue-600 text-white' : 'border-gray-300'
                          }`}
                        >
                          {checked && <Check className="w-3 h-3" />}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Chips de indicadores activos + botón rápido "Quitar todos" */}
        {(activeIndicatorsCount > 0 ||
          technicalMode !== 'none' ||
          selectedMetric === 'Market Cap' ||
          selectedMetric === 'Enterprise Value') && (
          <div className="px-4 py-1 flex flex-wrap items-center gap-1 bg-white border-b border-gray-100">
            {(selectedMetric === 'Market Cap' || selectedMetric === 'Enterprise Value') && (
              <span className="inline-flex items-center px-2 py-0.5 rounded bg-amber-50 border border-amber-200 text-[10px] font-medium text-amber-800">
                {historyData?.capitalStructureSource === 'sec_historical'
                  ? 'Estructura de capital anual (SEC) + precio histórico'
                  : 'Aprox. usando acciones y deuda neta actuales'}
              </span>
            )}
            {technicalMode !== 'none' && (
              <button
                onClick={() => setTechnicalMode('none')}
                title="Desactivar enfoque técnico"
                className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-purple-100 hover:bg-purple-200 text-[10px] font-semibold text-purple-800 cursor-pointer"
              >
                <Compass className="w-2.5 h-2.5" />
                <span>{currentModeObj.label}</span>
                <span className="text-purple-500 ml-0.5">×</span>
              </button>
            )}
            {INDICATOR_OPTIONS.filter((opt) => indicators[opt.id]).map((opt) => (
              <button
                key={opt.id}
                onClick={() => toggleIndicator(opt.id)}
                title="Clic para desactivar"
                className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-gray-100 hover:bg-gray-200 text-[10px] font-medium text-gray-700 cursor-pointer"
              >
                <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: opt.color }} />
                <span>{opt.label}</span>
                <span className="text-gray-400 ml-0.5">×</span>
              </button>
            ))}
            <button
              onClick={handleClearAllIndicators}
              className="ml-auto inline-flex items-center space-x-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium text-red-600 hover:bg-red-50 cursor-pointer"
            >
              <X className="w-3 h-3" />
              <span>Quitar todos</span>
            </button>
          </div>
        )}

        {/* Cuerpo del gráfico: Barra de herramientas izquierda + Canvas */}
        <div
          className="relative flex w-full mt-1"
          style={{ height: `${totalChartAreaHeight}px` }}
        >
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

          {/* Área Canvas + Sub-panel Oscilador + Tooltip flotante */}
          <div className="relative flex-1 h-full min-w-0 flex flex-col">
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
                <div className="relative w-full" style={{ height: `${mainCanvasHeight}px` }}>
                  <div ref={chartContainerRef} className="w-full h-full" />
                  {showVolume && activeCandles.length > 0 && (
                    <div className="pointer-events-none absolute left-0 right-14 bottom-[22%] border-t border-gray-200/80" />
                  )}
                </div>

                {hasSubPanel && (
                  <div className="relative w-full h-23.5 border-t border-gray-200 bg-[#fafafa]">
                    <div className="absolute left-2 top-1 z-10 flex items-center space-x-1">
                      {['rsi', 'macd', 'atr']
                        .filter((k) => indicators[k])
                        .map((k) => (
                          <button
                            key={k}
                            onClick={() => setActiveOscillator(k)}
                            className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase cursor-pointer ${
                              resolvedOscillator === k
                                ? 'bg-gray-800 text-white'
                                : 'bg-white/90 text-gray-600 border border-gray-200'
                            }`}
                          >
                            {k}
                          </button>
                        ))}
                    </div>
                    <div ref={subChartContainerRef} className="w-full h-full" />
                  </div>
                )}
              </>
            )}

            {/* Cuadrito flotante OHLC + Volumen relativo */}
            {hoverInfo && (
              <div
                style={{ left: `${hoverInfo.x}px`, top: `${hoverInfo.y}px` }}
                className="pointer-events-none absolute z-30 w-48 bg-white border border-gray-200 rounded-md shadow-lg px-3 py-2 text-[11px] leading-snug"
              >
                <div className="text-gray-500 text-[10px] mb-1">
                  {formatTooltipDate(hoverInfo.candle.time)}
                </div>
                <div
                  className={`font-semibold mb-1 ${
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
                  {hoverInfo.candle.volume > 0 && (
                    <div className="pt-0.5 border-t border-gray-100 text-gray-600">
                      Vol:{' '}
                      <span className="font-semibold text-gray-900">
                        {new Intl.NumberFormat('en-US', { notation: 'compact' }).format(hoverInfo.candle.volume)}
                      </span>
                      {hoverInfo.rvol !== null && (
                        <span
                          className={`ml-1 font-semibold ${
                            hoverInfo.rvol >= 1.5
                              ? 'text-blue-600'
                              : hoverInfo.rvol <= 0.7
                              ? 'text-gray-400'
                              : 'text-gray-600'
                          }`}
                        >
                          ({hoverInfo.rvol.toFixed(2)}x)
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Panel Didáctico Unificado: Enfoque AT Automático + Indicadores Activos */}
        {(modeAnalysis || (technicalExplanation && activeIndicatorsCount > 0)) && (
          <div className="px-4 py-2.5 border-t border-gray-100 bg-slate-50/90 text-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-1.5 font-semibold text-slate-800">
                <Info className="w-3.5 h-3.5 text-purple-600 shrink-0" />
                <span>
                  {modeAnalysis
                    ? `Análisis Técnico: ${modeAnalysis.title}`
                    : `Lectura Técnica Explicada (${technicalExplanation?.intervalLabel})`}
                </span>
              </div>
              <button
                onClick={() => setShowExplanation((prev) => !prev)}
                className="text-[11px] text-blue-600 hover:underline cursor-pointer"
              >
                {showExplanation ? 'Ocultar detalle' : 'Ver explicación'}
              </button>
            </div>

            {showExplanation && (
              <div className="mt-2 space-y-1.5 text-[11px] text-slate-600 leading-relaxed">
                {modeAnalysis && (
                  <div className="p-2 rounded bg-white border border-purple-200/80 space-y-1">
                    <div className="font-semibold text-purple-900">
                      Diagnóstico: {modeAnalysis.verdict}
                    </div>
                    <div>
                      <span className="font-semibold text-slate-800">Enfoque aplicado: </span>
                      {modeAnalysis.explanation.methodology}
                    </div>
                    <div>
                      <span className="font-semibold text-slate-800">Qué se trazó en el gráfico: </span>
                      {modeAnalysis.explanation.drawnElements}
                    </div>
                    <div>
                      <span className="font-semibold text-slate-800">Validación por Volumen: </span>
                      {modeAnalysis.explanation.volumeValidation}
                    </div>
                    <div>
                      <span className="font-semibold text-slate-800">Criterio de Invalidación: </span>
                      {modeAnalysis.explanation.invalidation}
                    </div>
                  </div>
                )}

                {technicalExplanation && activeIndicatorsCount > 0 && (
                  <div className="space-y-1">
                    {!modeAnalysis && (
                      <div className="p-1.5 rounded bg-white border border-slate-200/80 text-slate-700">
                        <span className="font-semibold text-slate-900">Confirmación de Volumen: </span>
                        {technicalExplanation.volumeNote}
                      </div>
                    )}
                    {technicalExplanation.items.map((item, idx) => (
                      <div key={idx} className="pl-1">
                        <span className="font-semibold text-slate-800">• {item.name}: </span>
                        <span>{item.detail}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Barra inferior del gráfico */}
        <div className="px-4 py-2.5 mt-auto border-t border-gray-100 flex items-center justify-between gap-2 bg-[#fcfcfc] rounded-bl-lg">
          <div className="relative flex-1 max-w-72.5">
            <input
              type="text"
              placeholder={
                chartType === 'candle'
                  ? 'Las comparaciones no están disponibles en vista de velas'
                  : 'Compara con un competidor, índice o ETF...'
              }
              disabled={chartType === 'candle'}
              className={`w-full pl-3 pr-7 py-1.5 border border-gray-300 rounded shadow-xs text-xs focus:outline-none focus:border-orange-500 ${
                chartType === 'candle'
                  ? 'bg-gray-100 text-gray-400 placeholder-gray-300'
                  : 'bg-white text-gray-700'
              }`}
            />
            <ChevronDown className="w-3.5 h-3.5 absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-400" />
          </div>

          <div className="flex space-x-1.5 shrink-0">
            <button
              onClick={() => setShowVolume((prev) => !prev)}
              className="px-2.5 py-1.5 border border-gray-300 rounded text-xs font-medium text-gray-700 bg-white hover:bg-gray-50 cursor-pointer shadow-xs"
            >
              {showVolume ? 'Ocultar Vol.' : 'Mostrar Vol.'}
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
    </>
  );
}
