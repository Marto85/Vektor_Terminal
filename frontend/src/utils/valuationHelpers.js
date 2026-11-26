/**
 * Semáforo institucional para comparar un múltiplo LTM contra su mediana de 5 años.
 */
export function getMultipleHighlight(row) {
  if (!row || row.section === 'Price Factors') return null;
  const ltm = row.ltm;
  const med = row.med_5y;
  if (typeof ltm !== 'number' || typeof med !== 'number' || ltm <= 0 || med <= 0) {
    return null;
  }

  const diffPct = ((ltm - med) / med) * 100;
  const isYieldMetric = row.suffix === '%' || row.metric.toLowerCase().includes('yield');

  if (Math.abs(diffPct) <= 0.5) {
    return {
      status: 'neutral',
      diffPct,
      cellClass: 'bg-amber-50/90 text-amber-900 ring-1 ring-inset ring-amber-200/80',
      badgeText: 'En línea (±0,5%)',
    };
  }

  const isFavorable = isYieldMetric ? diffPct > 0.5 : diffPct < -0.5;
  if (isFavorable) {
    return {
      status: 'cheap',
      diffPct,
      cellClass: 'bg-emerald-50/90 text-emerald-800 ring-1 ring-inset ring-emerald-200/80',
      badgeText: `${diffPct > 0 ? '+' : ''}${diffPct.toFixed(1)}% vs. Med. 5Y`,
    };
  }

  return {
    status: 'expensive',
    diffPct,
    cellClass: 'bg-red-50/90 text-[#c5221f] ring-1 ring-inset ring-red-200/80',
    badgeText: `${diffPct > 0 ? '+' : ''}${diffPct.toFixed(1)}% vs. Med. 5Y`,
  };
}
