
/**
 * Motor puro de indicadores técnicos y lectura didáctica (Etapa 14A).
 * Opera sobre arrays de velas { time, open, high, low, close, volume }.
 */

export function calculateSMA(candles, period) {
  const result = [];
  if (!Array.isArray(candles) || candles.length < period) return result;
  let sum = 0;
  for (let i = 0; i < candles.length; i++) {
    sum += candles[i].close;
    if (i >= period) {
      sum -= candles[i - period].close;
    }
    if (i >= period - 1) {
      result.push({
        time: candles[i].time,
        value: Number((sum / period).toFixed(4)),
      });
    }
  }
  return result;
}

export function calculateEMA(candles, period) {
  const result = [];
  if (!Array.isArray(candles) || candles.length < period) return result;
  const k = 2 / (period + 1);
  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += candles[i].close;
  }
  let ema = sum / period;
  result.push({ time: candles[period - 1].time, value: Number(ema.toFixed(4)) });

  for (let i = period; i < candles.length; i++) {
    ema = candles[i].close * k + ema * (1 - k);
    result.push({ time: candles[i].time, value: Number(ema.toFixed(4)) });
  }
  return result;
}

export function calculateBollingerBands(candles, period = 20, mult = 2) {
  const upper = [];
  const middle = [];
  const lower = [];
  if (!Array.isArray(candles) || candles.length < period) {
    return { upper, middle, lower };
  }

  for (let i = period - 1; i < candles.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sum += candles[j].close;
    }
    const mean = sum / period;
    let sqDiffSum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      const diff = candles[j].close - mean;
      sqDiffSum += diff * diff;
    }
    const stdDev = Math.sqrt(sqDiffSum / period);
    const t = candles[i].time;
    middle.push({ time: t, value: Number(mean.toFixed(4)) });
    upper.push({ time: t, value: Number((mean + mult * stdDev).toFixed(4)) });
    lower.push({ time: t, value: Number((mean - mult * stdDev).toFixed(4)) });
  }

  return { upper, middle, lower };
}

export function calculateVWAP(candles, isIntraday = false) {
  const result = [];
  if (!Array.isArray(candles) || candles.length === 0) return result;

  if (isIntraday) {
    // VWAP reiniciado por sesión diaria (UTC date)
    let currentDay = null;
    let cumPV = 0;
    let cumVol = 0;
    for (const c of candles) {
      const dayKey =
        typeof c.time === 'number'
          ? new Date(c.time * 1000).toISOString().slice(0, 10)
          : String(c.time).slice(0, 10);
      if (dayKey !== currentDay) {
        currentDay = dayKey;
        cumPV = 0;
        cumVol = 0;
      }
      const typicalPrice = (c.high + c.low + c.close) / 3;
      const vol = c.volume > 0 ? c.volume : 1;
      cumPV += typicalPrice * vol;
      cumVol += vol;
      result.push({ time: c.time, value: Number((cumPV / cumVol).toFixed(4)) });
    }
    return result;
  }

  // En diario/semanal: VWAP móvil de 20 ruedas (Anchored Rolling VWAP 20)
  const windowSize = 20;
  for (let i = 0; i < candles.length; i++) {
    const start = Math.max(0, i - windowSize + 1);
    let sumPV = 0;
    let sumVol = 0;
    for (let j = start; j <= i; j++) {
      const tp = (candles[j].high + candles[j].low + candles[j].close) / 3;
      const vol = candles[j].volume > 0 ? candles[j].volume : 1;
      sumPV += tp * vol;
      sumVol += vol;
    }
    result.push({ time: candles[i].time, value: Number((sumPV / sumVol).toFixed(4)) });
  }
  return result;
}

export function calculateVolumeSMA(candles, period = 20) {
  const result = [];
  if (!Array.isArray(candles) || candles.length < period) return result;
  let sum = 0;
  for (let i = 0; i < candles.length; i++) {
    sum += candles[i].volume || 0;
    if (i >= period) {
      sum -= candles[i - period].volume || 0;
    }
    if (i >= period - 1) {
      result.push({
        time: candles[i].time,
        value: Math.round(sum / period),
      });
    }
  }
  return result;
}

export function calculateRSI(candles, period = 14) {
  const result = [];
  if (!Array.isArray(candles) || candles.length <= period) return result;

  let gainSum = 0;
  let lossSum = 0;
  for (let i = 1; i <= period; i++) {
    const delta = candles[i].close - candles[i - 1].close;
    if (delta >= 0) gainSum += delta;
    else lossSum += Math.abs(delta);
  }

  let avgGain = gainSum / period;
  let avgLoss = lossSum / period;

  const computeRsi = (g, l) => {
    if (l === 0) return g === 0 ? 50 : 100;
    const rs = g / l;
    return 100 - 100 / (1 + rs);
  };

  result.push({
    time: candles[period].time,
    value: Number(computeRsi(avgGain, avgLoss).toFixed(2)),
  });

  for (let i = period + 1; i < candles.length; i++) {
    const delta = candles[i].close - candles[i - 1].close;
    const gain = delta > 0 ? delta : 0;
    const loss = delta < 0 ? Math.abs(delta) : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    result.push({
      time: candles[i].time,
      value: Number(computeRsi(avgGain, avgLoss).toFixed(2)),
    });
  }

  return result;
}

export function calculateMACD(candles, fast = 12, slow = 26, signalPeriod = 9) {
  const macdLine = [];
  const signalLine = [];
  const histogram = [];
  if (!Array.isArray(candles) || candles.length < slow + signalPeriod) {
    return { macdLine, signalLine, histogram };
  }

  const emaFast = calculateEMA(candles, fast);
  const emaSlow = calculateEMA(candles, slow);
  const fastMap = new Map(emaFast.map((p) => [p.time, p.value]));

  const rawMacd = [];
  for (const s of emaSlow) {
    const fVal = fastMap.get(s.time);
    if (fVal !== undefined) {
      rawMacd.push({ time: s.time, close: fVal - s.value });
    }
  }

  const sigSeries = calculateEMA(rawMacd, signalPeriod);
  const sigMap = new Map(sigSeries.map((p) => [p.time, p.value]));

  for (const m of rawMacd) {
    const mVal = Number(m.close.toFixed(4));
    macdLine.push({ time: m.time, value: mVal });
    const sVal = sigMap.get(m.time);
    if (sVal !== undefined) {
      const diff = Number((mVal - sVal).toFixed(4));
      signalLine.push({ time: m.time, value: sVal });
      histogram.push({
        time: m.time,
        value: diff,
        color: diff >= 0 ? 'rgba(16, 185, 129, 0.65)' : 'rgba(239, 68, 68, 0.65)',
      });
    }
  }

  return { macdLine, signalLine, histogram };
}

export function calculateATR(candles, period = 14) {
  const result = [];
  if (!Array.isArray(candles) || candles.length <= period) return result;

  const trueRanges = [];
  for (let i = 1; i < candles.length; i++) {
    const curr = candles[i];
    const prevClose = candles[i - 1].close;
    const tr = Math.max(
      curr.high - curr.low,
      Math.abs(curr.high - prevClose),
      Math.abs(curr.low - prevClose)
    );
    trueRanges.push({ time: curr.time, tr });
  }

  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += trueRanges[i].tr;
  }
  let atr = sum / period;
  result.push({ time: trueRanges[period - 1].time, value: Number(atr.toFixed(4)) });

  for (let i = period; i < trueRanges.length; i++) {
    atr = (atr * (period - 1) + trueRanges[i].tr) / period;
    result.push({ time: trueRanges[i].time, value: Number(atr.toFixed(4)) });
  }

  return result;
}

/**
 * Construye la explicación didáctica en español sobre qué indicadores están
 * dibujados, qué valores muestran hoy y cómo los valida el volumen (RVOL).
 */
export function buildTechnicalExplanation({
  candles,
  activeIndicators,
  intervalLabel,
  computed,
  selectedMetric = 'Price',
}) {
  if (!candles || candles.length < 2) return null;

  const isMM = selectedMetric === 'Market Cap' || selectedMetric === 'Enterprise Value';
  const isPct =
    selectedMetric === '% Change' ||
    selectedMetric === 'Total Return' ||
    selectedMetric === 'Drawdowns';
  const fmtVal = (val) => {
    if (isMM) {
      return `US$ ${Number(val).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MM`;
    }
    if (isPct) {
      return `${Number(val).toFixed(2)}%`;
    }
    return `$${Number(val).toFixed(2)}`;
  };

  const last = candles[candles.length - 1];
  const prev = candles[candles.length - 2];
  const priceChangePct = prev.close ? ((last.close - prev.close) / prev.close) * 100 : 0;

  // Cálculo de volumen relativo (RVOL vs media 20)
  const volSma = computed.volSma20 || [];
  const lastVolAvg = volSma.length ? volSma[volSma.length - 1].value : null;
  const rvol = lastVolAvg && lastVolAvg > 0 ? last.volume / lastVolAvg : null;

  let volumeNote = 'Sin media de volumen suficiente para calcular RVOL.';
  if (rvol !== null) {
    const rvolFmt = rvol.toFixed(2);
    if (rvol >= 1.5) {
      volumeNote = `Volumen alto (RVOL ${rvolFmt}x vs. media 20): valida con participación institucional el movimiento reciente (${priceChangePct >= 0 ? 'acumulación' : 'distribución'}).`;
    } else if (rvol <= 0.7) {
      volumeNote = `Volumen bajo (RVOL ${rvolFmt}x vs. media 20): movimiento con poca convicción; conviene exigir expansión de volumen antes de confirmar rupturas.`;
    } else {
      volumeNote = `Volumen normal (RVOL ${rvolFmt}x vs. media 20): actividad en línea con el promedio reciente.`;
    }
  }

  const items = [];

  if (activeIndicators.sma20 && computed.sma20?.length) {
    const v = computed.sma20[computed.sma20.length - 1].value;
    items.push({
      name: 'SMA 20 (Tendencia Corto Plazo)',
      detail: `Cotización ${last.close >= v ? 'por encima' : 'por debajo'} de la media de 20 períodos (${fmtVal(v)}), actuando como ${last.close >= v ? 'soporte dinámico' : 'resistencia dinámica'} inmediata.`,
    });
  }

  if (activeIndicators.sma50 && computed.sma50?.length) {
    const v = computed.sma50[computed.sma50.length - 1].value;
    items.push({
      name: 'SMA 50 (Tendencia Intermedia)',
      detail: `Precio ${last.close >= v ? 'sobre' : 'bajo'} la SMA 50 (${fmtVal(v)}). Es la referencia institucional estándar para medir salud de tendencia intermedia.`,
    });
  }

  if (activeIndicators.sma200 && computed.sma200?.length) {
    const v = computed.sma200[computed.sma200.length - 1].value;
    items.push({
      name: 'SMA 200 (Régimen Primario)',
      detail: `Activo operando ${last.close >= v ? 'en régimen alcista estructural' : 'en régimen bajista estructural'} respecto a la media de 200 períodos (${fmtVal(v)}).`,
    });
  }

  if (activeIndicators.ema21 && computed.ema21?.length) {
    const v = computed.ema21[computed.ema21.length - 1].value;
    items.push({
      name: 'EMA 21 (Impulso Exponencial)',
      detail: `Pondera más las últimas velas (${fmtVal(v)}); útil para seguir retrocesos cortos en tendencias activas.`,
    });
  }

  if (activeIndicators.bb && computed.bb?.upper?.length) {
    const u = computed.bb.upper[computed.bb.upper.length - 1].value;
    const l = computed.bb.lower[computed.bb.lower.length - 1].value;
    const widthPct = ((u - l) / last.close) * 100;
    const pos =
      last.close >= u
        ? 'tocando/superando banda superior (extensión alcista o posible ruptura)'
        : last.close <= l
        ? 'tocando/perforando banda inferior (sobreextensión bajista)'
        : 'dentro del canal de ±2 desvíos estándar';
    items.push({
      name: 'Bandas de Bollinger (20, 2)',
      detail: `Canal entre ${fmtVal(l)} y ${fmtVal(u)} (amplitud ${widthPct.toFixed(1)}%). Precio ${pos}.`,
    });
  }

  if (activeIndicators.vwap && computed.vwap?.length) {
    const v = computed.vwap[computed.vwap.length - 1].value;
    items.push({
      name: 'VWAP (Precio Promedio Ponderado por Volumen)',
      detail: `Referencia en ${fmtVal(v)}. Compradores tienen control promedio mientras el precio se sostenga por encima.`,
    });
  }

  if (activeIndicators.rsi && computed.rsi?.length) {
    const v = computed.rsi[computed.rsi.length - 1].value;
    const zone =
      v >= 70
        ? 'en zona de sobrecompra (≥70): alerta de agotamiento de impulso'
        : v <= 30
        ? 'en zona de sobreventa (≤30): posible rebote técnico si aparece volumen comprador'
        : 'en zona neutral (30–70)';
    items.push({
      name: `RSI (14) = ${v.toFixed(1)}`,
      detail: `Mide velocidad y magnitud de cambios de cierre; actualmente ${zone}.`,
    });
  }

  if (activeIndicators.macd && computed.macd?.macdLine?.length) {
    const m = computed.macd.macdLine[computed.macd.macdLine.length - 1].value;
    const s = computed.macd.signalLine.length
      ? computed.macd.signalLine[computed.macd.signalLine.length - 1].value
      : null;
    const spreadText =
      s !== null
        ? m >= s
          ? `por encima de su señal (${s.toFixed(2)}), sesgo de momentum positivo`
          : `por debajo de su señal (${s.toFixed(2)}), sesgo de momentum negativo`
        : '';
    items.push({
      name: `MACD (12, 26, 9) = ${m.toFixed(2)}`,
      detail: `Diferencia entre EMA 12 y EMA 26 ${spreadText}.`,
    });
  }

  if (activeIndicators.atr && computed.atr?.length) {
    const v = computed.atr[computed.atr.length - 1].value;
    const atrPct = last.close ? (v / last.close) * 100 : 0;
    items.push({
      name: `ATR (14) = $${v.toFixed(2)} (${atrPct.toFixed(2)}%)`,
      detail: `Rango verdadero promedio por vela en temporalidad ${intervalLabel}; sirve para dimensionar stop-loss técnico (ej. 1.5x–2x ATR = $${(v * 2).toFixed(2)}).`,
    });
  }

  return {
    intervalLabel,
    volumeNote,
    items,
  };
}
