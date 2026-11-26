
/**
 * Motor Auditado de Enfoques de Análisis Técnico Automático (Etapa 14B).
 * Implementa reglas ortodoxas de Tendencia, Chartismo, Ondas de Elliott + Fibonacci
 * y Momentum/Volatilidad, con confirmación transversal obligatoria de volumen (RVOL / OBV).
 */

import {
  calculateSMA,
  calculateRSI,
  calculateMACD,
  calculateATR,
  calculateBollingerBands,
} from './technicalIndicators';

export const TECHNICAL_MODES = [
  { id: 'none', label: 'Sin lente AT' },
  { id: 'trend', label: 'Tendencia y Medias' },
  { id: 'chartism', label: 'Chartismo (S/R y Figuras)' },
  { id: 'elliott', label: 'Elliott + Fibonacci' },
  { id: 'momentum', label: 'Momentum y Volatilidad' },
];

/**
 * Detecta pivotes alternados locales (Swing Highs y Swing Lows).
 */
export function findSwingPivots(candles, lookback = 5) {
  const pivots = [];
  if (!Array.isArray(candles) || candles.length < lookback * 2 + 1) return pivots;

  for (let i = lookback; i < candles.length - lookback; i++) {
    const curr = candles[i];
    let isHigh = true;
    let isLow = true;

    for (let j = i - lookback; j <= i + lookback; j++) {
      if (j === i) continue;
      if (candles[j].high >= curr.high) isHigh = false;
      if (candles[j].low <= curr.low) isLow = false;
      if (!isHigh && !isLow) break;
    }

    if (isHigh) {
      pivots.push({
        index: i,
        time: curr.time,
        price: curr.high,
        volume: curr.volume || 0,
        type: 'high',
      });
    } else if (isLow) {
      pivots.push({
        index: i,
        time: curr.time,
        price: curr.low,
        volume: curr.volume || 0,
        type: 'low',
      });
    }
  }

  const alternating = [];
  for (const p of pivots) {
    const prev = alternating[alternating.length - 1];
    if (!prev || prev.type !== p.type) {
      alternating.push(p);
    } else if (p.type === 'high' && p.price > prev.price) {
      alternating[alternating.length - 1] = p;
    } else if (p.type === 'low' && p.price < prev.price) {
      alternating[alternating.length - 1] = p;
    }
  }

  return alternating;
}

/**
 * Calcula métricas transversales de volumen: RVOL (20), sesgo acumulación/distribución y pendiente OBV.
 */
export function analyzeVolumeBehavior(candles) {
  if (!candles || candles.length < 5) {
    return {
      rvol: 1,
      avgVol20: 0,
      lastVol: 0,
      upDayAvgVol: 0,
      downDayAvgVol: 0,
      accumulationBias: 'neutral',
      obvSlopeUp: false,
      summary: 'Historial insuficiente para evaluar comportamiento de volumen.',
    };
  }

  const recent = candles.slice(-20);
  const avgVol20 = recent.reduce((acc, c) => acc + (c.volume || 0), 0) / recent.length;
  const last = candles[candles.length - 1];
  const lastVol = last.volume || 0;
  const rvol = avgVol20 > 0 ? lastVol / avgVol20 : 1;

  let upVolSum = 0;
  let upCount = 0;
  let downVolSum = 0;
  let downCount = 0;
  let obv = 0;
  const obvSeries = [0];

  for (let i = 1; i < recent.length; i++) {
    const c = recent[i];
    const prevClose = recent[i - 1].close;
    const vol = c.volume || 0;
    if (c.close > prevClose) {
      upVolSum += vol;
      upCount += 1;
      obv += vol;
    } else if (c.close < prevClose) {
      downVolSum += vol;
      downCount += 1;
      obv -= vol;
    }
    obvSeries.push(obv);
  }

  const obvMid = obvSeries[Math.floor(obvSeries.length / 2)] ?? 0;
  const obvSlopeUp = obv > obvMid;

  const upDayAvgVol = upCount > 0 ? upVolSum / upCount : 0;
  const downDayAvgVol = downCount > 0 ? downVolSum / downCount : 0;

  let accumulationBias = 'neutral';
  if (upDayAvgVol > downDayAvgVol * 1.15 && obvSlopeUp) accumulationBias = 'accumulation';
  else if (downDayAvgVol > upDayAvgVol * 1.15 && !obvSlopeUp) accumulationBias = 'distribution';

  const biasText =
    accumulationBias === 'accumulation'
      ? 'Predomina acumulación (OBV creciente y mayor volumen promedio en ruedas alcistas).'
      : accumulationBias === 'distribution'
      ? 'Predomina distribución (OBV decreciente y mayor volumen en ruedas bajistas).'
      : 'Flujo de volumen equilibrado (sin dominancia clara de acumulación ni distribución en 20 velas).';

  const rvolText =
    rvol >= 1.5
      ? `Expansión fuerte de volumen en la última vela (RVOL ${rvol.toFixed(2)}x).`
      : rvol <= 0.7
      ? `Volumen retraído en la última vela (RVOL ${rvol.toFixed(2)}x).`
      : `Volumen normal respecto a su media de 20 ruedas (RVOL ${rvol.toFixed(2)}x).`;

  return {
    rvol,
    avgVol20,
    lastVol,
    upDayAvgVol,
    downDayAvgVol,
    accumulationBias,
    obvSlopeUp,
    summary: `${rvolText} ${biasText}`,
  };
}

/**
 * 1. ENFOQUE: Tendencia y Medias Móviles (Canal envolvente de regresión + Cruces SMA 50/200)
 */
function analyzeTrendMode(candles, volInfo) {
  const windowSize = Math.min(candles.length, 90);
  const slice = candles.slice(-windowSize);
  const n = slice.length;

  let sumX = 0;
  let sumY = 0;
  let sumXY = 0;
  let sumXX = 0;

  for (let i = 0; i < n; i++) {
    sumX += i;
    sumY += slice[i].close;
    sumXY += i * slice[i].close;
    sumXX += i * i;
  }

  const denom = n * sumXX - sumX * sumX;
  const slope = denom !== 0 ? (n * sumXY - sumX * sumY) / denom : 0;
  const intercept = (sumY - slope * sumX) / n;

  // Envolvente real usando distancia máxima de High/Low respecto a la línea central
  let maxUpperDev = 0;
  let maxLowerDev = 0;
  for (let i = 0; i < n; i++) {
    const est = intercept + slope * i;
    maxUpperDev = Math.max(maxUpperDev, slice[i].high - est);
    maxLowerDev = Math.max(maxLowerDev, est - slice[i].low);
  }

  const regMid = [];
  const regUpper = [];
  const regLower = [];

  for (let i = 0; i < n; i++) {
    const mid = intercept + slope * i;
    const t = slice[i].time;
    regMid.push({ time: t, value: Number(mid.toFixed(2)) });
    regUpper.push({ time: t, value: Number((mid + maxUpperDev).toFixed(2)) });
    regLower.push({ time: t, value: Number((mid - maxLowerDev).toFixed(2)) });
  }

  const sma20 = calculateSMA(candles, 20);
  const sma50 = calculateSMA(candles, 50);
  const sma200 = calculateSMA(candles, 200);

  const lastPrice = candles[candles.length - 1].close;
  const v20 = sma20.length ? sma20[sma20.length - 1].value : null;
  const v50 = sma50.length ? sma50[sma50.length - 1].value : null;
  const v200 = sma200.length ? sma200[sma200.length - 1].value : null;

  // Detectar Golden Cross / Death Cross en las últimas 15 velas
  let crossNote = '';
  if (sma50.length >= 15 && sma200.length >= 15) {
    const s50Now = sma50[sma50.length - 1].value;
    const s200Now = sma200[sma200.length - 1].value;
    const s50Prev = sma50[sma50.length - 15].value;
    const s200Prev = sma200[sma200.length - 15].value;
    if (s50Prev <= s200Prev && s50Now > s200Now) {
      crossNote = ' Señal mayor: Golden Cross reciente (SMA 50 cruzó al alza a SMA 200).';
    } else if (s50Prev >= s200Prev && s50Now < s200Now) {
      crossNote = ' Señal mayor: Death Cross reciente (SMA 50 cruzó a la baja a SMA 200).';
    }
  }

  const pctSlope = lastPrice > 0 ? ((slope * n) / lastPrice) * 100 : 0;
  let regime = 'Lateral / Consolidación';
  if (pctSlope > 4 && (!v50 || lastPrice > v50)) regime = 'Tendencia Alcista';
  else if (pctSlope < -4 && (!v50 || lastPrice < v50)) regime = 'Tendencia Bajista';

  const alignedBull = v20 && v50 && v200 && lastPrice > v20 && v20 > v50 && v50 > v200;
  const alignedBear = v20 && v50 && v200 && lastPrice < v20 && v20 < v50 && v50 < v200;

  const lastChannelLow = regLower[regLower.length - 1]?.value;
  const lastChannelHigh = regUpper[regUpper.length - 1]?.value;

  const volumeValidated =
    (regime === 'Tendencia Alcista' && volInfo.accumulationBias === 'accumulation') ||
    (regime === 'Tendencia Bajista' && volInfo.accumulationBias === 'distribution');

  const alignmentText = alignedBull
    ? 'Alineación alcista perfecta (Precio > SMA 20 > SMA 50 > SMA 200).'
    : alignedBear
    ? 'Alineación bajista perfecta (Precio < SMA 20 < SMA 50 < SMA 200).'
    : 'Medias móviles en transición sin alineación completa.';

  const volBackText = volumeValidated
    ? ' El flujo de volumen (OBV y volumen direccional) confirma la tendencia.'
    : ' Precaución: la pendiente del precio aún no cuenta con confirmación fuerte de volumen.';

  const invalidationText =
    regime === 'Tendencia Alcista'
      ? `Pérdida del piso del canal en $${lastChannelLow?.toFixed(2) ?? '-'} con RVOL > 1.2x.`
      : `Superación del techo del canal en $${lastChannelHigh?.toFixed(2) ?? '-'} con RVOL > 1.3x.`;

  return {
    mode: 'trend',
    title: 'Tendencia y Medias Móviles',
    verdict: `${regime}${volumeValidated ? ' (Confirmada por Volumen)' : ''}${crossNote}`,
    overlays: [
      { id: 'reg-upper', data: regUpper, color: 'rgba(37, 99, 235, 0.55)', lineWidth: 1, lineStyle: 2 },
      { id: 'reg-mid', data: regMid, color: '#2563eb', lineWidth: 1.5, lineStyle: 0 },
      { id: 'reg-lower', data: regLower, color: 'rgba(37, 99, 235, 0.55)', lineWidth: 1, lineStyle: 2 },
    ],
    priceLines: [
      ...(lastChannelLow
        ? [{ price: lastChannelLow, color: '#10b981', lineStyle: 2, title: 'Piso Canal' }]
        : []),
      ...(lastChannelHigh
        ? [{ price: lastChannelHigh, color: '#ef4444', lineStyle: 2, title: 'Techo Canal' }]
        : []),
    ],
    markers: [],
    explanation: {
      methodology: `Canal envolvente de regresión lineal sobre extremos reales (High/Low) de las últimas ${windowSize} velas + auditoría de medias SMA 20/50/200 y cruces Golden/Death Cross.`,
      drawnElements: `Canal dinámico entre $${lastChannelLow?.toFixed(2) ?? '-'} (soporte) y $${lastChannelHigh?.toFixed(2) ?? '-'} (resistencia). ${alignmentText}${crossNote}`,
      volumeValidation: `${volInfo.summary}${volBackText}`,
      invalidation: invalidationText,
    },
  };
}

/**
 * 2. ENFOQUE: Chartismo Clásico (Soportes, Resistencias, Figuras y Rupturas)
 */
function analyzeChartismMode(candles, pivots, volInfo) {
  const lastPrice = candles[candles.length - 1].close;
  const tolerance = 0.025;

  const clusters = [];
  for (const p of pivots) {
    const match = clusters.find((c) => Math.abs(c.level - p.price) / c.level <= tolerance);
    if (match) {
      match.level = (match.level * match.touches + p.price) / (match.touches + 1);
      match.touches += 1;
      match.avgVol = (match.avgVol * (match.touches - 1) + p.volume) / match.touches;
    } else {
      clusters.push({
        level: p.price,
        touches: 1,
        avgVol: p.volume,
      });
    }
  }

  clusters.sort((a, b) => b.touches - a.touches);

  const resistances = clusters
    .filter((c) => c.level > lastPrice * 1.005)
    .sort((a, b) => a.level - b.level)
    .slice(0, 2);

  const supports = clusters
    .filter((c) => c.level <= lastPrice * 1.005)
    .sort((a, b) => b.level - a.level)
    .slice(0, 2);

  const nearRes = resistances[0];
  const nearSup = supports[0];
  const distResPct =
    nearRes && lastPrice > 0 ? (((nearRes.level - lastPrice) / lastPrice) * 100).toFixed(1) : null;

  // Detección de figuras chartistas sobre los últimos pivotes (Doble Techo/Piso y Triángulos)
  const recentHighs = pivots.filter((p) => p.type === 'high').slice(-2);
  const recentLows = pivots.filter((p) => p.type === 'low').slice(-2);
  let patternNote = '';

  if (recentHighs.length === 2 && recentLows.length === 2) {
    const hDiffPct = Math.abs(recentHighs[1].price - recentHighs[0].price) / recentHighs[0].price;
    const lDiffPct = Math.abs(recentLows[1].price - recentLows[0].price) / recentLows[0].price;

    if (hDiffPct <= 0.015 && lastPrice < recentHighs[1].price * 0.98) {
      patternNote = ` Figura detectada: posible Doble Techo en $${recentHighs[1].price.toFixed(2)} (segundo máximo con menor convicción).`;
    } else if (lDiffPct <= 0.015 && lastPrice > recentLows[1].price * 1.02) {
      patternNote = ` Figura detectada: posible Doble Piso en $${recentLows[1].price.toFixed(2)}.`;
    } else if (recentHighs[1].price < recentHighs[0].price && recentLows[1].price > recentLows[0].price) {
      patternNote = ' Figura detectada: Triángulo Simétrico de compresión (máximos decrecientes y mínimos crecientes).';
    } else if (hDiffPct <= 0.015 && recentLows[1].price > recentLows[0].price) {
      patternNote = ` Figura detectada: Triángulo Ascendente con techo horizontal en $${recentHighs[1].price.toFixed(2)}.`;
    } else if (lDiffPct <= 0.015 && recentHighs[1].price < recentHighs[0].price) {
      patternNote = ` Figura detectada: Triángulo Descendente con base horizontal en $${recentLows[1].price.toFixed(2)}.`;
    }
  }

  // Evaluar ruptura de rango de 30 velas previas
  const prev30 = candles.slice(-31, -1);
  const max30 = prev30.length ? Math.max(...prev30.map((c) => c.high)) : lastPrice;
  const min30 = prev30.length ? Math.min(...prev30.map((c) => c.low)) : lastPrice;

  let breakoutStatus = 'Cotizando dentro de rango entre soporte y resistencia.';
  if (lastPrice > max30) {
    breakoutStatus =
      volInfo.rvol >= 1.3
        ? `Ruptura alcista sobre $${max30.toFixed(2)} CONFIRMADA por volumen (RVOL ${volInfo.rvol.toFixed(2)}x); resistencia previa pasa a actuar como soporte (role reversal).`
        : `Ruptura alcista sobre $${max30.toFixed(2)} CON BAJO VOLUMEN (RVOL ${volInfo.rvol.toFixed(2)}x): riesgo alto de falso quiebre (fakeout).`;
  } else if (lastPrice < min30) {
    breakoutStatus =
      volInfo.rvol >= 1.3
        ? `Quiebre bajista bajo $${min30.toFixed(2)} CONFIRMADO por volumen vendedor (RVOL ${volInfo.rvol.toFixed(2)}x).`
        : `Perforación de $${min30.toFixed(2)} con bajo volumen (RVOL ${volInfo.rvol.toFixed(2)}x): posible trampa bajista.`;
  }

  const priceLines = [
    ...resistances.map((r, i) => ({
      price: Number(r.level.toFixed(2)),
      color: i === 0 ? '#ef4444' : '#f87171',
      lineStyle: i === 0 ? 0 : 2,
      title: `R${i + 1} (${r.touches}t)`,
    })),
    ...supports.map((s, i) => ({
      price: Number(s.level.toFixed(2)),
      color: i === 0 ? '#10b981' : '#34d399',
      lineStyle: i === 0 ? 0 : 2,
      title: `S${i + 1} (${s.touches}t)`,
    })),
  ];

  const markers = pivots.slice(-8).map((p) => ({
    time: p.time,
    position: p.type === 'high' ? 'aboveBar' : 'belowBar',
    color: p.type === 'high' ? '#ef4444' : '#10b981',
    shape: p.type === 'high' ? 'arrowDown' : 'arrowUp',
    text: p.type === 'high' ? 'R' : 'S',
  }));

  const targetNote = distResPct
    ? `Próximo techo R1 a +${distResPct}% ($${nearRes.level.toFixed(2)}). `
    : '';
  const invalidationNote = nearSup
    ? `${targetNote}Invalidación si cierra debajo del soporte S1 ($${nearSup.level.toFixed(2)}) con volumen.`
    : `${targetNote}Invalidación si perfora $${min30.toFixed(2)}.`;

  const resText = resistances.length
    ? resistances.map((r) => `$${r.level.toFixed(2)} (${r.touches} toques)`).join(' y ')
    : 'zona libre de máximos previos';
  const supText = supports.length
    ? supports.map((s) => `$${s.level.toFixed(2)} (${s.touches} toques)`).join(' y ')
    : 'zona sin pisos cercanos';

  return {
    mode: 'chartism',
    title: 'Chartismo Clásico (Soportes, Resistencias y Figuras)',
    verdict: `${breakoutStatus}${patternNote}`,
    overlays: [],
    priceLines,
    markers,
    explanation: {
      methodology:
        'Agrupación de pivotes históricos en clústeres de memoria (±2.5%), reconocimiento geométrico de figuras (Dobles Techos/Pisos y Triángulos) y validación de rupturas por RVOL.',
      drawnElements: `Resistencias en ${resText}; Soportes en ${supText}.${patternNote}`,
      volumeValidation: `${volInfo.summary} ${breakoutStatus}`,
      invalidation: invalidationNote,
    },
  };
}

/**
 * 3. ENFOQUE: Ondas de Elliott + Retrocesos de Fibonacci (Con validación estructural y volumen por tramo)
 */
function analyzeElliottMode(candles, pivots, volInfo) {
  const recentPivots = pivots.slice(-6);
  const lastPrice = candles[candles.length - 1].close;

  if (recentPivots.length < 4) {
    return {
      mode: 'elliott',
      title: 'Ondas de Elliott + Fibonacci',
      verdict: 'Estructura insuficiente para conteo de ondas en esta escala.',
      overlays: [],
      priceLines: [],
      markers: [],
      explanation: {
        methodology: 'Conteo estructural sobre pivotes mayores alternados y retrocesos de Fibonacci.',
        drawnElements: 'Se requieren al menos 4 pivotes mayores alternados; probá ampliar el rango temporal.',
        volumeValidation: volInfo.summary,
        invalidation: 'N/A',
      },
    };
  }

  let wavePivots = recentPivots.length >= 6 ? recentPivots.slice(-6) : recentPivots.slice(-4);
  let structuralRuleNote;
  let volumeWaveNote = volInfo.summary;

  if (wavePivots.length === 6) {
    const isBullImpulse = wavePivots[1].price > wavePivots[0].price;
    const w1 = Math.abs(wavePivots[1].price - wavePivots[0].price);
    const w3 = Math.abs(wavePivots[3].price - wavePivots[2].price);
    const w5 = Math.abs(wavePivots[5].price - wavePivots[4].price);

    // Regla 1: Onda 2 nunca retrocede más del 100% de Onda 1
    const w2Valid = isBullImpulse
      ? wavePivots[2].price > wavePivots[0].price
      : wavePivots[2].price < wavePivots[0].price;

    // Regla 2: Onda 3 nunca es la más corta (y debe superar el extremo de Onda 1)
    const w3Extends = isBullImpulse
      ? wavePivots[3].price > wavePivots[1].price
      : wavePivots[3].price < wavePivots[1].price;
    const w3NotShortest = w3Extends && !(w3 < w1 && w3 < w5);

    // Regla 3: Onda 4 no solapa territorio de Onda 1
    const w4NoOverlap = isBullImpulse
      ? wavePivots[4].price > wavePivots[1].price
      : wavePivots[4].price < wavePivots[1].price;

    const isValidImpulse = w2Valid && w3NotShortest && w4NoOverlap;

    if (isValidImpulse) {
      structuralRuleNote = `Impulso ${isBullImpulse ? 'alcista' : 'bajista'} de 5 ondas (1-2-3-4-5) VÁLIDO: cumple las 3 reglas cardinales de Elliott (Onda 2 no perfora origen, Onda 3 supera Onda 1 y no es la más corta, y Onda 4 no invade Onda 1).`;

      // Comparar volumen PROMEDIO de todo el tramo de Onda 3 vs todo el tramo de Onda 5
      const sliceW3 = candles.slice(wavePivots[2].index, wavePivots[3].index + 1);
      const sliceW5 = candles.slice(wavePivots[4].index, wavePivots[5].index + 1);
      const avgVolW3 = sliceW3.length
        ? sliceW3.reduce((acc, c) => acc + (c.volume || 0), 0) / sliceW3.length
        : 0;
      const avgVolW5 = sliceW5.length
        ? sliceW5.reduce((acc, c) => acc + (c.volume || 0), 0) / sliceW5.length
        : 0;

      if (avgVolW3 > 0 && avgVolW5 > 0) {
        volumeWaveNote =
          avgVolW5 < avgVolW3
            ? `Firma ortodoxa de volumen en Elliott: el volumen promedio de Onda 5 (${Math.round(avgVolW5).toLocaleString('es-AR')}) es menor al de Onda 3 (${Math.round(avgVolW3).toLocaleString('es-AR')}), señalando agotamiento de impulso y alta probabilidad de corrección A-B-C. ${volInfo.summary}`
            : `Expansión sostenida de volumen en Onda 5 respecto a Onda 3: momentum extendido. ${volInfo.summary}`;
      }
    } else {
      // Si no cumple las reglas de impulso, degrada honestamente a corrección A-B-C sobre los últimos 4 pivotes
      wavePivots = recentPivots.slice(-4);
      structuralRuleNote =
        'Los últimos 6 pivotes no cumplen las reglas de impulso de 5 ondas (hay solapamiento o fallo de extensión); se reclasifica como tramo correctivo/zigzag A-B-C.';
    }
  } else {
    structuralRuleNote = 'Estructura correctiva A-B-C en curso.';
  }

  const labels = wavePivots.length === 6 ? ['0', '1', '2', '3', '4', '5'] : (wavePivots[1].price > wavePivots[0].price ? ['0', 'W', 'X', 'Y'] : ['0', 'A', 'B', 'C']);

  // Retrocesos de Fibonacci respetando la dirección del ciclo (alcista: retrocede desde techo; bajista: rebota desde piso)
  const lowPivot = wavePivots.reduce((min, p) => (p.price < min.price ? p : min), wavePivots[0]);
  const highPivot = wavePivots.reduce((max, p) => (p.price > max.price ? p : max), wavePivots[0]);
  const diff = highPivot.price - lowPivot.price;
  const cycleIsUp = highPivot.index > lowPivot.index;

  const fib382 = Number(
    (cycleIsUp ? highPivot.price - diff * 0.382 : lowPivot.price + diff * 0.382).toFixed(2)
  );
  const fib500 = Number(
    (cycleIsUp ? highPivot.price - diff * 0.5 : lowPivot.price + diff * 0.5).toFixed(2)
  );
  const fib618 = Number(
    (cycleIsUp ? highPivot.price - diff * 0.618 : lowPivot.price + diff * 0.618).toFixed(2)
  );

  const waveLine = wavePivots.map((p) => ({
    time: p.time,
    value: Number(p.price.toFixed(2)),
  }));

  const markers = wavePivots.map((p, idx) => ({
    time: p.time,
    position: p.type === 'high' ? 'aboveBar' : 'belowBar',
    color: '#7c3aed',
    shape: 'circle',
    text: `(${labels[idx]})`,
  }));

  const fibDirectionText = cycleIsUp
    ? 'retrocesos bajistas desde el techo del impulso'
    : 'retrocesos alcistas (rebotes) desde el piso de la caída';

  return {
    mode: 'elliott',
    title: 'Ondas de Elliott + Retrocesos Fibonacci',
    verdict: structuralRuleNote,
    overlays: [
      { id: 'elliott-wave', data: waveLine, color: '#7c3aed', lineWidth: 2, lineStyle: 0 },
    ],
    priceLines: [
      { price: fib382, color: '#0891b2', lineStyle: 2, title: 'Fib 38.2%' },
      { price: fib500, color: '#f59e0b', lineStyle: 2, title: 'Fib 50.0%' },
      { price: fib618, color: '#dc2626', lineStyle: 2, title: 'Fib 61.8%' },
    ],
    markers,
    explanation: {
      methodology:
        'Validación estricta de reglas cardinales de Elliott (no-perforación de Onda 2, extensión de Onda 3 y no-solapamiento de Onda 4) + retrocesos direccionales de Fibonacci.',
      drawnElements: `Poligonal (${labels.join('-')}) en violeta y ${fibDirectionText} en $${fib382} (38.2%), $${fib500} (50.0%) y $${fib618} (61.8%). Precio actual: $${lastPrice.toFixed(2)}.`,
      volumeValidation: volumeWaveNote,
      invalidation: (cycleIsUp && lastPrice < fib618) ? `Nivel áureo Fib 61.8% (${fib618}) ya perforado (retroceso profundo); soporte estructural final en origen (${labels[0]}) ${wavePivots[0].price.toFixed(2)}.` : `Quiebre del nivel áureo Fib 61.8% (${fib618}) o del origen (${labels[0]}) en ${wavePivots[0].price.toFixed(2)}.`,
    },
  };
}

/**
 * 4. ENFOQUE: Momentum, Divergencias RSI/MACD/OBV y Volatilidad (ATR / Bollinger Squeeze)
 */
function analyzeMomentumMode(candles, pivots, volInfo) {
  const rsi = calculateRSI(candles, 14);
  const macd = calculateMACD(candles, 12, 26, 9);
  const atr = calculateATR(candles, 14);
  const bb = calculateBollingerBands(candles, 20, 2);

  const lastPrice = candles[candles.length - 1].close;
  const lastRsi = rsi.length ? rsi[rsi.length - 1].value : null;
  const lastMacd = macd.macdLine.length ? macd.macdLine[macd.macdLine.length - 1].value : null;
  const lastSig = macd.signalLine.length ? macd.signalLine[macd.signalLine.length - 1].value : null;
  const lastAtr = atr.length ? atr[atr.length - 1].value : null;

  const rsiMap = new Map(rsi.map((r) => [r.time, r.value]));
  const highs = pivots.filter((p) => p.type === 'high').slice(-2);
  const lows = pivots.filter((p) => p.type === 'low').slice(-2);

  let divergenceText = 'Sin divergencias válidas en zonas extremas de RSI.';
  if (highs.length === 2) {
    const r1 = rsiMap.get(highs[0].time);
    const r2 = rsiMap.get(highs[1].time);
    // Exigir que el primer pico haya estado en zona de sobrecompra o fuerza alta (RSI >= 60)
    if (r1 !== undefined && r2 !== undefined && r1 >= 60 && highs[1].price > highs[0].price && r2 < r1 - 2) {
      const obvConfirms = !volInfo.obvSlopeUp;
      divergenceText = `DIVERGENCIA BAJISTA detectada: precio marcó máximo mayor ($${highs[1].price.toFixed(2)} vs $${highs[0].price.toFixed(2)}) con RSI debilitándose (${r2.toFixed(1)} vs ${r1.toFixed(1)})${obvConfirms ? ' y OBV confirmando pérdida de flujo comprador.' : ' (aún sin confirmación plena de OBV).'}`;
    }
  }
  if (lows.length === 2) {
    const r1 = rsiMap.get(lows[0].time);
    const r2 = rsiMap.get(lows[1].time);
    // Exigir que el primer piso haya estado en zona de sobreventa o debilidad (RSI <= 40)
    if (r1 !== undefined && r2 !== undefined && r1 <= 40 && lows[1].price < lows[0].price && r2 > r1 + 2) {
      const obvConfirms = volInfo.obvSlopeUp;
      divergenceText = `DIVERGENCIA ALCISTA detectada: precio marcó mínimo menor ($${lows[1].price.toFixed(2)} vs $${lows[0].price.toFixed(2)}) con RSI creciente (${r2.toFixed(1)} vs ${r1.toFixed(1)})${obvConfirms ? ' y OBV confirmando acumulación.' : ' (pendiente de confirmación de volumen).'}`;
    }
  }

  let squeezeNote = '';
  if (bb.upper.length >= 20) {
    const widths = bb.upper.slice(-20).map((u, idx) => {
      const l = bb.lower[bb.lower.length - 20 + idx].value;
      const m = bb.middle[bb.middle.length - 20 + idx].value;
      return m > 0 ? (u.value - l) / m : 0;
    });
    const currWidth = widths[widths.length - 1];
    const minWidth = Math.min(...widths);
    if (currWidth <= minWidth * 1.08) {
      squeezeNote = ' Compresión de volatilidad activa (Bollinger Squeeze): anticipa expansión direccional fuerte.';
    }
  }

  const stopLong = lastAtr ? Number((lastPrice - 2 * lastAtr).toFixed(2)) : null;
  const targetLong = lastAtr ? Number((lastPrice + 3 * lastAtr).toFixed(2)) : null;

  const atrNote = stopLong
    ? `Stop técnico sugerido en $${stopLong} (-2x ATR) y Objetivo en $${targetLong} (+3x ATR, ratio riesgo/beneficio 1:1.5).`
    : '';

  return {
    mode: 'momentum',
    title: 'Momentum, Divergencias y Volatilidad (ATR)',
    verdict: `${divergenceText}${squeezeNote}`,
    overlays: [],
    priceLines: [
      ...(stopLong
        ? [{ price: stopLong, color: '#ef4444', lineStyle: 2, title: 'Stop 2x ATR' }]
        : []),
      ...(targetLong
        ? [{ price: targetLong, color: '#10b981', lineStyle: 2, title: 'Objetivo 3x ATR' }]
        : []),
    ],
    markers: [],
    explanation: {
      methodology:
        'Auditoría de divergencias en zonas extremas de RSI (≥60 / ≤40) cruzadas con flujo OBV, cruce MACD (12/26/9), Bollinger Squeeze y dimensionamiento por ATR (14).',
      drawnElements: `RSI en ${lastRsi !== null ? lastRsi.toFixed(1) : '-'}, MACD en ${lastMacd !== null ? lastMacd.toFixed(2) : '-'} (Señal: ${lastSig !== null ? lastSig.toFixed(2) : '-'}). ${atrNote}`,
      volumeValidation: `${volInfo.summary} ${divergenceText}`,
      invalidation: stopLong
        ? `Ejecución del stop dinámico de volatilidad en $${stopLong}.`
        : 'Pérdida del mínimo de pivote previo.',
    },
  };
}

/**
 * Punto de entrada principal para evaluar el enfoque técnico seleccionado.
 */
export function runTechnicalAnalysisMode(candles, mode, options = {}) {
  if (!mode || mode === 'none' || !Array.isArray(candles) || candles.length < 15) {
    return null;
  }

  const parsedLive = Number(options?.livePrice);
  const rawLastClose = Number(candles[candles.length - 1]?.close);
  const usedLiveOverride =
    Number.isFinite(parsedLive) &&
    parsedLive > 0 &&
    Number.isFinite(rawLastClose) &&
    Math.abs(parsedLive - rawLastClose) >= 0.01;
  const effectiveCandles =
    Number.isFinite(parsedLive) && parsedLive > 0
      ? candles.map((c, idx) =>
          idx === candles.length - 1
            ? {
                ...c,
                close: parsedLive,
                high: Math.max(Number(c.high ?? parsedLive), parsedLive),
                low: Math.min(Number(c.low ?? parsedLive), parsedLive),
              }
            : c,
        )
      : candles;

  const lookback = effectiveCandles.length > 180 ? 7 : effectiveCandles.length > 80 ? 5 : 3;
  const pivots = findSwingPivots(effectiveCandles, lookback);
  const volInfo = analyzeVolumeBehavior(effectiveCandles);

  let out = null;
  if (mode === 'trend') out = analyzeTrendMode(effectiveCandles, volInfo);
  else if (mode === 'chartism') out = analyzeChartismMode(effectiveCandles, pivots, volInfo);
  else if (mode === 'elliott') out = analyzeElliottMode(effectiveCandles, pivots, volInfo);
  else if (mode === 'momentum') out = analyzeMomentumMode(effectiveCandles, pivots, volInfo);

  if (out && usedLiveOverride && out.explanation?.drawnElements) {
    out.explanation.drawnElements = `${out.explanation.drawnElements} (Evaluado sobre cotización viva vs. cierre diario $${rawLastClose.toFixed(2)}.)`;
  }
  return out;
}
