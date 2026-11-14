function formatTikrNumber(value, { prefix = '', suffix = '', decimals = 2 } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const isNegative = value < 0;
  const absVal = Math.abs(value);
  const formatted = new Intl.NumberFormat('es-AR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(absVal);

  const text = `${prefix}${formatted}${suffix}`;
  return isNegative ? `(${text})` : text;
}

function TikrRow({ label, value, prefix = '', suffix = '', decimals = 2 }) {
  const isNegative = typeof value === 'number' && value < 0;
  return (
    <div className="flex items-baseline justify-between py-[4.5px] text-[12px] leading-tight">
      <span className="text-gray-600 truncate pr-2">{label}</span>
      <span
        className={`shrink-0 font-semibold tabular-nums text-right ${
          isNegative ? 'text-[#d93025]' : 'text-gray-900'
        }`}
      >
        {formatTikrNumber(value, { prefix, suffix, decimals })}
      </span>
    </div>
  );
}

function SectionTitle({ children }) {
  return (
    <h3 className="text-[13px] font-semibold text-[#f59e0b] mb-2 tracking-tight">
      {children}
    </h3>
  );
}

export default function CapitalStructurePanel({ summaryMetrics }) {
  if (!summaryMetrics) {
    return (
      <div className="w-full lg:w-[53%] p-6 flex items-center justify-center text-gray-400 text-xs">
        Buscá un ticker para visualizar Datos de mercado, Estructura de capital y Valoración.
      </div>
    );
  }

  const { market_data, capital_structure, efficiency, growth_cashflow, valuation } = summaryMetrics;

  return (
    <div className="w-full lg:w-[53%] px-6 py-4 flex flex-col justify-between bg-white">
      {/* FILA 1: Datos de mercado (Izq) | Estructura de capital (Der) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-4">
        <div>
          <SectionTitle>Datos de mercado</SectionTitle>
          <div>
            <TikrRow label="Máximo de 52 semanas" value={market_data?.high_52w} prefix="US$ " />
            <TikrRow label="Mínimo de 52 semanas" value={market_data?.low_52w} prefix="US$ " />
            <TikrRow label="Volumen prom. de 3 meses" value={market_data?.avg_volume_3m_mm} suffix=" MM" />
            <TikrRow label="Beta a 5 años" value={market_data?.beta_5y} />
            <TikrRow label="Flotante %" value={market_data?.float_pct} suffix="%" decimals={1} />
          </div>
        </div>

        <div>
          <SectionTitle>Estructura de capital</SectionTitle>
          <div>
            <TikrRow label="Capitalización bursátil (MM)" value={capital_structure?.market_cap_mm} prefix="US$ " />
            <TikrRow label="Valor empresarial (MM)" value={capital_structure?.enterprise_value_mm} prefix="US$ " />
            <TikrRow label="Acciones en circulación" value={capital_structure?.shares_out_mm} suffix=" MM" />
            <TikrRow label="Deuda neta LTM (MM)" value={capital_structure?.net_debt_mm} prefix="US$ " />
            <TikrRow label="Deuda neta/EBITDA LTM" value={capital_structure?.net_debt_to_ebitda} suffix="x" />
          </div>
        </div>
      </div>

      {/* FILA 2: Eficiencia (Izq) | Crecimiento y flujo LTM (Der) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-4 mt-4">
        <div>
          <SectionTitle>Eficiencia</SectionTitle>
          <div>
            <TikrRow label="Margen bruto LTM" value={efficiency?.gross_margin_pct} suffix="%" decimals={1} />
            <TikrRow label="Margen EBIT LTM" value={efficiency?.ebit_margin_pct} suffix="%" decimals={1} />
            <TikrRow label="ROA LTM" value={efficiency?.roa_pct} suffix="%" decimals={1} />
            <TikrRow label="ROE LTM" value={efficiency?.roe_pct} suffix="%" decimals={1} />
            <TikrRow label="ROIC LTM" value={efficiency?.roic_pct} suffix="%" decimals={1} />
            <TikrRow label="Margen neto LTM" value={efficiency?.net_margin_pct} suffix="%" decimals={1} />
          </div>
        </div>

        <div>
          <SectionTitle>Crecimiento y flujo</SectionTitle>
          <div>
            <TikrRow label="Crec. ingresos YoY" value={growth_cashflow?.revenue_growth_yoy_pct} suffix="%" decimals={1} />
            <TikrRow label="Crec. beneficios YoY" value={growth_cashflow?.earnings_growth_yoy_pct} suffix="%" decimals={1} />
            <TikrRow label="Margen EBITDA LTM" value={growth_cashflow?.ebitda_margin_pct} suffix="%" decimals={1} />
            <TikrRow label="Flujo op. LTM (MM)" value={growth_cashflow?.ocf_ltm_mm} prefix="US$ " />
            <TikrRow label="FCF LTM (MM)" value={growth_cashflow?.fcf_ltm_mm} prefix="US$ " />
            <TikrRow label="Efectivo e inv. CP (MM)" value={growth_cashflow?.total_cash_mm} prefix="US$ " />
          </div>
        </div>
      </div>

      {/* FILA 3: Valoración (Título único arriba + 2 columnas de métricas) */}
      <div className="mt-4">
        <SectionTitle>Valoración</SectionTitle>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
          <div>
            <TikrRow label="Precio objetivo de Wall Street" value={valuation?.target_price} prefix="US$ " />
            <TikrRow label="EV / Ingresos LTM" value={valuation?.ev_to_sales_ltm} suffix="x" />
            <TikrRow label="EV / EBITDA LTM" value={valuation?.ev_to_ebitda_ltm} suffix="x" />
            <TikrRow label="EV / Beneficio bruto LTM" value={valuation?.ev_to_gross_profit_ltm} suffix="x" />
            <TikrRow label="NTM P / E" value={valuation?.pe_ntm} suffix="x" />
          </div>
          <div>
            <TikrRow label="P / E LTM" value={valuation?.pe_ltm} suffix="x" />
            <TikrRow label="LTM P / BV" value={valuation?.pb_ltm} suffix="x" />
            <TikrRow label="P / FCF LTM" value={valuation?.p_to_fcf_ltm} suffix="x" />
            <TikrRow label="Rentabilidad por dividendo" value={valuation?.dividend_yield_pct} suffix="%" />
            <TikrRow label="Ratio de pago de dividendos" value={valuation?.payout_ratio_pct} suffix="%" decimals={1} />
          </div>
        </div>
      </div>
    </div>
  );
}