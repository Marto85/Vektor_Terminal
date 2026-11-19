import { describe, it, expect } from 'vitest';

// Replica pura de las reglas de clasificación y bisección de ValuationTab / ValuationModelsTab
function getMultipleHighlight(row) {
  if (!row || row.section === 'Price Factors') return null;
  const ltm = row.ltm;
  const med = row.med_5y;
  if (typeof ltm !== 'number' || typeof med !== 'number' || ltm <= 0 || med <= 0) {
    return null;
  }
  const diffPct = ((ltm - med) / med) * 100;
  const isYieldMetric = row.suffix === '%' || row.metric.toLowerCase().includes('yield');

  if (Math.abs(diffPct) <= 0.5) return 'neutral';
  const isFavorable = isYieldMetric ? diffPct > 0.5 : diffPct < -0.5;
  return isFavorable ? 'cheap' : 'expensive';
}

describe('Semáforo de Múltiplos Históricos (Actual LTM vs. Mediana 5Y)', () => {
  it('marca como barato (cheap) cuando EV/EBITDA actual es menor a la mediana 5Y', () => {
    const status = getMultipleHighlight({
      section: 'Trailing Multiples (EV)',
      metric: 'EV / EBITDA (LTM)',
      suffix: 'x',
      ltm: 18.69,
      med_5y: 23.62,
    });
    expect(status).toBe('cheap');
  });

  it('marca como caro (expensive) cuando P/FCF actual supera la mediana 5Y', () => {
    const status = getMultipleHighlight({
      section: 'Trailing Multiples (Equity)',
      metric: 'Precio / Flujo de Caja Libre (P/FCF)',
      suffix: 'x',
      ltm: 56.35,
      med_5y: 47.24,
    });
    expect(status).toBe('expensive');
  });

  it('invierte la lógica en FCF Yield % (mayor yield = más barato)', () => {
    const cheapYield = getMultipleHighlight({
      section: 'Trailing Multiples (Equity)',
      metric: 'FCF Yield %',
      suffix: '%',
      ltm: 3.1,
      med_5y: 2.1,
    });
    const expensiveYield = getMultipleHighlight({
      section: 'Trailing Multiples (Equity)',
      metric: 'FCF Yield %',
      suffix: '%',
      ltm: 1.77,
      med_5y: 2.12,
    });
    expect(cheapYield).toBe('cheap');
    expect(expensiveYield).toBe('expensive');
  });

  it('marca como neutro dentro de ±0,5% y excluye Price Factors', () => {
    const neutral = getMultipleHighlight({
      section: 'Trailing Multiples (Equity)',
      metric: 'Precio / Beneficio (P/E)',
      suffix: 'x',
      ltm: 20.05,
      med_5y: 20.0,
    });
    const priceFactor = getMultipleHighlight({
      section: 'Price Factors',
      metric: 'Precio de cierre (US$)',
      suffix: '',
      ltm: 508.29,
      med_5y: 421.5,
    });
    expect(neutral).toBe('neutral');
    expect(priceFactor).toBeNull();
  });
});
