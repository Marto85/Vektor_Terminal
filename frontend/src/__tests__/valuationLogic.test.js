import { describe, it, expect } from 'vitest';
import { getMultipleHighlight } from '../utils/valuationHelpers';

describe('Semáforo de Múltiplos Históricos (Actual LTM vs. Mediana 5Y)', () => {
  it('marca como barato (cheap) cuando EV/EBITDA actual es menor a la mediana 5Y', () => {
    const res = getMultipleHighlight({
      section: 'Trailing Multiples (EV)',
      metric: 'EV / EBITDA (LTM)',
      suffix: 'x',
      ltm: 18.69,
      med_5y: 23.62,
    });
    expect(res?.status).toBe('cheap');
  });

  it('marca como caro (expensive) cuando P/FCF actual supera la mediana 5Y', () => {
    const res = getMultipleHighlight({
      section: 'Trailing Multiples (Equity)',
      metric: 'Precio / Flujo de Caja Libre (P/FCF)',
      suffix: 'x',
      ltm: 56.35,
      med_5y: 47.24,
    });
    expect(res?.status).toBe('expensive');
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
    expect(cheapYield?.status).toBe('cheap');
    expect(expensiveYield?.status).toBe('expensive');
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
    expect(neutral?.status).toBe('neutral');
    expect(priceFactor).toBeNull();
  });
});
