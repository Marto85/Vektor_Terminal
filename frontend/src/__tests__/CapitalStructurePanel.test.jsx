import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import CapitalStructurePanel from '../components/CapitalStructurePanel';

describe('CapitalStructurePanel', () => {
  it('oculta Deuda neta/EBITDA LTM y EV / EBITDA LTM para entidades bancarias', () => {
    const bankSummary = {
      market_data: { high_52w: 366.5, low_52w: 279.1 },
      capital_structure: {
        market_cap_mm: 841137.91,
        enterprise_value_mm: 600000.0,
        shares_out_mm: 2655.0,
        net_debt_mm: -241000.0,
        net_debt_to_ebitda: -2.09,
      },
      efficiency: {
        gross_margin_pct: null,
        ebit_margin_pct: 67.1,
        roa_pct: 1.4,
        roe_pct: 15.7,
        roic_pct: null,
        net_margin_pct: 31.0,
      },
      growth_cashflow: {
        revenue_growth_yoy_pct: 6.0,
        earnings_growth_yoy_pct: 8.0,
        ebitda_margin_pct: null,
        ocf_ltm_mm: 10000.0,
        fcf_ltm_mm: null,
        total_cash_mm: 400000.0,
      },
      valuation: {
        target_price: 330.0,
        ev_to_sales_ltm: 3.3,
        ev_to_ebitda_ltm: 4.77,
        ev_to_gross_profit_ltm: null,
        pe_ltm: 13.29,
        pe_ntm: 12.39,
        pb_ltm: 2.1,
        p_to_fcf_ltm: null,
        dividend_yield_pct: 1.9,
        payout_ratio_pct: 25.0,
      },
    };

    render(<CapitalStructurePanel summaryMetrics={bankSummary} />);

    const debtToEbitdaRow = screen.getByText('Deuda neta/EBITDA LTM').closest('div').parentElement;
    const evToEbitdaRow = screen.getByText('EV / EBITDA LTM').closest('div').parentElement;
    expect(debtToEbitdaRow.textContent).toContain('-');
    expect(debtToEbitdaRow.textContent).not.toContain('2,09x');
    expect(evToEbitdaRow.textContent).toContain('-');
    expect(evToEbitdaRow.textContent).not.toContain('4,77x');
  });

  it('muestra Deuda neta/EBITDA LTM y EV / EBITDA LTM para empresas no financieras', () => {
    const techSummary = {
      market_data: {},
      capital_structure: { net_debt_to_ebitda: 2.5 },
      efficiency: { gross_margin_pct: 68.0, roic_pct: 24.4 },
      growth_cashflow: {},
      valuation: { ev_to_ebitda_ltm: 18.03 },
    };

    render(<CapitalStructurePanel summaryMetrics={techSummary} />);

    expect(screen.getByText('2,50x')).toBeTruthy();
    expect(screen.getByText('18,03x')).toBeTruthy();
  });
});
