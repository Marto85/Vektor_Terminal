import { Fragment, useEffect, useMemo, useState } from 'react';
import apiClient from "../api/client";
import {
  Loader2,
  Calculator,
  AlertTriangle,
  Info,
  TrendingUp,
  TrendingDown,
  Minus,
  Building2,
  ExternalLink,
  Landmark,
  Users,
  ArrowRight,
  Compass,
  RotateCcw,
  SlidersHorizontal,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Scale,
} from 'lucide-react';
import { getGlossaryEntry } from '../data/metricsGlossary';

function formatMult(val, suffix = 'x') {
  if (val === null || val === undefined || Number.isNaN(val)) return '-';
  if (val === 'N/M') return 'N/M';
  const isNeg = val < 0;
  const formatted = new Intl.NumberFormat('es-AR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(val));
  const text = `${formatted}${suffix}`;
  return isNeg ? `(${text})` : text;
}

function formatMoney(val) {
  if (val === null || val === undefined || Number.isNaN(val)) return '-';
  const isNeg = val < 0;
  const formatted = new Intl.NumberFormat('es-AR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(val));
  return isNeg ? `(US$ ${formatted})` : `US$ ${formatted}`;
}

/**
 * Clasifica la celda Actual (LTM) frente a la Mediana 5Y:
 * - Para múltiplos de precio (EV/EBITDA, P/E, P/FCF, etc.): menor = barato (verde), mayor = caro (rojo).
 * - Para FCF Yield %: mayor = más rendimiento de caja (verde), menor = más caro (rojo).
 * - Tolerancia de ±0.5% alrededor de la mediana = neutro/alineado (ámbar).
 */
import { getMultipleHighlight } from '../utils/valuationHelpers';

/**
 * Resuelve en tiempo real el crecimiento implícito en el precio actual
 * cuando el usuario sensibiliza WACC, Margen EBIT o Múltiplo de Salida.
 */
function solveInteractiveReverseDcf({
  isFinancial,
  dcfInputs,
  financialInputs,
  horizonYears,
  customWaccPct,
  customEbitMarginPct,
  customExitMult,
  customKePct,
}) {
  if (isFinancial) {
    const curPrice = Number(financialInputs?.current_price || 0);
    const bvps = Number(financialInputs?.bvps || 0);
    const ke = Number(customKePct || financialInputs?.cost_of_equity_pct || 9.5) / 100;
    const payout = Number(financialInputs?.payout_ratio_pct || 35) / 100;
    const retention = Math.max(1 - payout, 0.1);

    if (curPrice <= 0 || bvps <= 0) {
      return { solvable: false, impliedGrowthPct: null, impliedRoePct: null };
    }

    const evalBank = (roeDec) => {
      const g1 = Math.min(Math.max(roeDec * retention, -0.25), 0.25);
      const gTerm = Math.min(Math.max(g1, 0.0), 0.045);
      if (ke <= gTerm) return 0;
      let bv = bvps;
      let pvExc = 0;
      for (let yr = 1; yr <= horizonYears; yr += 1) {
        pvExc += (bv * (roeDec - ke)) / (1 + ke) ** yr;
        bv *= 1 + g1;
      }
      const termRoe = ke + (roeDec - ke) * 0.5;
      const tv = (bv * (termRoe - ke)) / (ke - gTerm);
      return bvps + pvExc + tv / (1 + ke) ** horizonYears;
    };

    let lo = -0.35;
    let hi = 0.6;
    if (curPrice <= evalBank(lo)) {
      return {
        solvable: true,
        impliedGrowthPct: Number((lo * retention * 100).toFixed(1)),
        impliedRoePct: Number((lo * 100).toFixed(1)),
      };
    }
    if (curPrice >= evalBank(hi)) {
      return {
        solvable: true,
        impliedGrowthPct: Number((hi * retention * 100).toFixed(1)),
        impliedRoePct: Number((hi * 100).toFixed(1)),
      };
    }
    for (let i = 0; i < 60; i += 1) {
      const mid = (lo + hi) / 2;
      if (evalBank(mid) < curPrice) lo = mid;
      else hi = mid;
    }
    const roeSol = (lo + hi) / 2;
    return {
      solvable: true,
      impliedGrowthPct: Number((roeSol * retention * 100).toFixed(1)),
      impliedRoePct: Number((roeSol * 100).toFixed(1)),
    };
  }

  const curPrice = Number(dcfInputs?.current_price || 0);
  const rev0 = Number(dcfInputs?.revenue_base_mm || 0);
  const shares = Number(dcfInputs?.shares_mm || 0);
  const netDebt = Number(dcfInputs?.net_debt_mm || 0);
  const ebitM = Number(customEbitMarginPct ?? dcfInputs?.ebit_margin_pct ?? 15) / 100;
  const taxR = Number(dcfInputs?.tax_rate_pct || 21) / 100;
  const daP = Number(dcfInputs?.da_sales_pct || 8) / 100;
  const capex1 = Number(dcfInputs?.capex_expansion_pct || 12) / 100;
  const capexT = Number(dcfInputs?.capex_maintenance_pct || 8) / 100;
  const wacc = Number(customWaccPct ?? dcfInputs?.suggested_wacc_pct ?? 9) / 100;
  const exitM = Number(customExitMult ?? dcfInputs?.exit_multiple_default ?? 18);
  const marginStep = Number(dcfInputs?.margin_step_pct_yr || 0) / 100;
  const gTerm = 0.03;

  if (curPrice <= 0 || rev0 <= 0 || shares <= 0 || wacc <= gTerm) {
    return { solvable: false, impliedGrowthPct: null, gordonPct: null, multPct: null };
  }

  const evalCorp = (gDec, mode = 'blend') => {
    let rv = rev0;
    let pv1 = 0;
    let lastM = ebitM;
    for (let yr = 1; yr <= horizonYears; yr += 1) {
      rv *= 1 + gDec;
      const stepYr = Math.min(yr, 5);
      const mYr = Math.min(Math.max(ebitM + marginStep * stepYr, 0.01), 0.65);
      lastM = mYr;
      const fcfY = rv * (mYr * (1 - taxR) + daP - capex1);
      pv1 += fcfY / (1 + wacc) ** yr;
    }
    const fcfNext = rv * (1 + gTerm) * (lastM * (1 - taxR) + daP - capexT);
    const tvGordon = fcfNext / (wacc - gTerm);
    const fcfLastNorm = rv * (lastM * (1 - taxR) + daP - capexT);
    const tvMult = fcfLastNorm * exitM;
    const tv = mode === 'gordon' ? tvGordon : mode === 'multiple' ? tvMult : 0.5 * (tvGordon + tvMult);
    return (pv1 + tv / (1 + wacc) ** horizonYears - netDebt) / shares;
  };

  const bisect = (mode) => {
    let lo = -0.25;
    let hi = 0.85;
    const pHi = evalCorp(hi, mode);
    if (pHi <= 0) return { val: 0, ok: false };
    const pLo = evalCorp(lo, mode);
    if (curPrice <= pLo) return { val: lo, ok: true };
    if (curPrice >= pHi) return { val: hi, ok: false };
    for (let i = 0; i < 60; i += 1) {
      const mid = (lo + hi) / 2;
      if (evalCorp(mid, mode) < curPrice) lo = mid;
      else hi = mid;
    }
    return { val: (lo + hi) / 2, ok: true };
  };

  const bRes = bisect('blend');
  if (!bRes.ok && evalCorp(0.85, 'blend') <= 0) {
    return { solvable: false, impliedGrowthPct: null, gordonPct: null, multPct: null };
  }
  const gRes = bisect('gordon');
  const mRes = bisect('multiple');

  return {
    solvable: true,
    impliedGrowthPct: Number((bRes.val * 100).toFixed(1)),
    gordonPct: Number((gRes.val * 100).toFixed(1)),
    multPct: Number((mRes.val * 100).toFixed(1)),
  };
}

export default function ValuationTab({ ticker, onOpenInfo, onOpenValuationModels }) {
  const [valData, setValData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [subTab, setSubTab] = useState('multiplos'); // 'multiplos' | 'competidores'
  const [peersData, setPeersData] = useState(null);
  const [peersLoading, setPeersLoading] = useState(false);
  const [peersError, setPeersError] = useState(null);

  const [revHorizon, setRevHorizon] = useState(5);
  const [simWacc, setSimWacc] = useState(null);
  const [simMargin, setSimMargin] = useState(null);
  const [simExitMult, setSimExitMult] = useState(null);
  const [simKe, setSimKe] = useState(null);
  const [showAdvancedSliders, setShowAdvancedSliders] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;

    const fetchValuation = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await apiClient.get(
          `/company/${ticker.toUpperCase()}/valuation`
        );
        if (!cancelled) {
          setValData(res.data);
          setRevHorizon(5);
          setSimWacc(res.data?.dcf_inputs?.suggested_wacc_pct ?? null);
          setSimMargin(res.data?.dcf_inputs?.ebit_margin_pct ?? null);
          setSimExitMult(res.data?.dcf_inputs?.exit_multiple_default ?? null);
          setSimKe(res.data?.financial_sector_inputs?.cost_of_equity_pct ?? null);
          setShowAdvancedSliders(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || 'No se pudo calcular la valoración');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchValuation();
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  useEffect(() => {
    if (!ticker || subTab !== 'competidores') return;
    const upperTicker = ticker.toUpperCase();
    if (peersData?.ticker === upperTicker) return;

    let cancelled = false;

    const fetchPeers = async () => {
      setPeersLoading(true);
      setPeersError(null);
      try {
        const res = await apiClient.get(
          `/company/${upperTicker}/peers`
        );
        if (!cancelled) {
          setPeersData(res.data);
        }
      } catch (err) {
        if (!cancelled) {
          setPeersError(err.response?.data?.detail || 'No se pudieron cargar los competidores');
        }
      } finally {
        if (!cancelled) {
          setPeersLoading(false);
        }
      }
    };

    fetchPeers();
    return () => {
      cancelled = true;
    };
  }, [ticker, subTab, peersData]);

  const routing = valData?.sector_routing || { profile: 'standard', label: 'Corporativo Estándar' };
  const isFinancial = routing.profile === 'financial';

  const interactiveReverse = useMemo(() => {
    if (!valData) return null;
    return solveInteractiveReverseDcf({
      isFinancial,
      dcfInputs: valData.dcf_inputs,
      financialInputs: valData.financial_sector_inputs,
      horizonYears: revHorizon,
      customWaccPct: simWacc,
      customEbitMarginPct: simMargin,
      customExitMult: simExitMult,
      customKePct: simKe,
    });
  }, [valData, isFinancial, revHorizon, simWacc, simMargin, simExitMult, simKe]);

  const historicalMultiplesInsight = useMemo(() => {
    const rList = valData?.rows || [];
    if (!rList.length) return null;

    const targetLabels = isFinancial
      ? ['Precio / Beneficio (P/E)', 'Precio / Valor Libros (P/BV)', 'Precio / Valor Contable Tangible (P/TBV)']
      : [
          'EV / Ventas (LTM)',
          'EV / EBITDA (LTM)',
          'Precio / Beneficio (P/E)',
          'Precio / Valor Libros (P/BV)',
          'Precio / Flujo de Caja Libre (P/FCF)',
        ];

    const diffs = [];
    for (const lbl of targetLabels) {
      const row = rList.find((r) => r.metric === lbl);
      if (
        row &&
        typeof row.ltm === 'number' &&
        typeof row.med_5y === 'number' &&
        row.ltm > 0 &&
        row.med_5y > 0
      ) {
        const pctDiff = ((row.ltm - row.med_5y) / row.med_5y) * 100;
        diffs.push({ label: lbl, pctDiff });
      }
    }

    if (!diffs.length) return null;

    const discounted = diffs.filter((d) => d.pctDiff <= -5).length;
    const expensive = diffs.filter((d) => d.pctDiff >= 5).length;
    const avgDiff = diffs.reduce((acc, d) => acc + d.pctDiff, 0) / diffs.length;

    if (discounted >= Math.ceil(diffs.length / 2) && avgDiff <= -8) {
      return {
        tone: 'emerald',
        badge: `${discounted} de ${diffs.length} múltiplos con descuento histórico`,
        title: `Valuación comprimida frente a su historia (${Math.abs(avgDiff).toFixed(0)}% de descuento promedio vs. Mediana 5Y)`,
        detail: `La acción cotiza por debajo de los múltiplos que el mercado solía pagar por ${valData.ticker} en los últimos 5 años. Si la calidad del negocio sigue intacta, representa una ventana de entrada con reversión a la media favorable.`,
      };
    }

    if (expensive >= Math.ceil(diffs.length / 2) && avgDiff >= 10) {
      return {
        tone: 'amber',
        badge: `${expensive} de ${diffs.length} múltiplos con prima histórica`,
        title: `Valuación exigente frente a su historia (+${avgDiff.toFixed(0)}% de prima promedio vs. Mediana 5Y)`,
        detail: `El mercado paga hoy un múltiplo superior al promedio histórico de ${valData.ticker}. Esto suele ocurrir cuando se espera aceleración de crecimiento o expansión de márgenes, pero reduce el margen de error.`,
      };
    }

    return {
      tone: 'neutral',
      badge: 'Alineada con su mediana histórica (5Y)',
      title: `Múltiplos en línea con el promedio de los últimos 5 años (${avgDiff >= 0 ? '+' : ''}${avgDiff.toFixed(0)}% vs. Mediana 5Y)`,
      detail: `No se observan distorsiones extremas de múltiplo respecto a su propia historia: la acción cotiza en su rango habitual de valoración.`,
    };
  }, [valData, isFinancial]);

  const activePeersData =
    peersData && peersData.ticker === ticker?.toUpperCase() ? peersData : null;

  const peersRelativeInsight = useMemo(() => {
    if (!activePeersData?.relative_premium_pct) return null;
    const premMap = activePeersData.relative_premium_pct;
    const isFinPeers = Boolean(activePeersData.is_financial);

    const valKeys = isFinPeers
      ? ['pe_ltm', 'pe_ntm', 'pb_ltm']
      : ['ev_ebitda_ltm', 'pe_ltm', 'p_fcf_ltm', 'ev_sales_ltm'];
    const qualKeys = isFinPeers ? ['roe_pct', 'net_margin_pct'] : ['roic_pct', 'ebit_margin_pct'];

    const valPrems = valKeys
      .map((k) => premMap[k])
      .filter((v) => typeof v === 'number' && !Number.isNaN(v));
    const qualPrems = qualKeys
      .map((k) => premMap[k])
      .filter((v) => typeof v === 'number' && !Number.isNaN(v));

    if (!valPrems.length) return null;

    const avgValPrem = valPrems.reduce((a, b) => a + b, 0) / valPrems.length;
    const avgQualPrem = qualPrems.length
      ? qualPrems.reduce((a, b) => a + b, 0) / qualPrems.length
      : 0;

    const isCheaper = avgValPrem <= -8;
    const isDearer = avgValPrem >= 10;
    const isHigherQuality = avgQualPrem >= 5;
    const isLowerQuality = avgQualPrem <= -8;

    if (isCheaper && isHigherQuality) {
      return {
        tone: 'emerald',
        badge: 'Asimetría atractiva vs. sector',
        summary: `${activePeersData.ticker} cotiza con un descuento promedio del ${Math.abs(avgValPrem).toFixed(0)}% frente a la mediana de sus competidores, aun exhibiendo márgenes y retorno sobre capital superiores (+${avgQualPrem.toFixed(0)}% vs. pares).`,
      };
    }

    if (isCheaper && isLowerQuality) {
      return {
        tone: 'neutral',
        badge: 'Descuento justificado por rentabilidad',
        summary: `${activePeersData.ticker} cotiza un ${Math.abs(avgValPrem).toFixed(0)}% más barata que sus pares, pero ese castigo responde a una rentabilidad operativa inferior a la mediana del sector (${avgQualPrem.toFixed(0)}%).`,
      };
    }

    if (isDearer && isHigherQuality) {
      return {
        tone: 'neutral',
        badge: 'Prima por liderazgo operativo',
        summary: `El mercado paga una prima promedio del +${avgValPrem.toFixed(0)}% sobre la mediana del sector, respaldada por márgenes y retornos superiores (+${avgQualPrem.toFixed(0)}% vs. competidores).`,
      };
    }

    if (isDearer && isLowerQuality) {
      return {
        tone: 'amber',
        badge: 'Prima sin respaldo operativo',
        summary: `${activePeersData.ticker} cotiza un +${avgValPrem.toFixed(0)}% más cara que sus pares directos a pesar de mostrar menor rentabilidad relativa (${avgQualPrem.toFixed(0)}%).`,
      };
    }

    return {
      tone: 'neutral',
      badge: 'Valuación alineada con el sector',
      summary: `Los múltiplos de ${activePeersData.ticker} (${avgValPrem >= 0 ? '+' : ''}${avgValPrem.toFixed(0)}% vs. mediana) se ubican dentro del rango estándar de sus competidores directos.`,
    };
  }, [activePeersData]);

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm py-20 flex flex-col items-center justify-center text-orange-500">
        <Loader2 className="w-8 h-8 mb-3 animate-spin" />
        <p className="text-sm font-medium">Auditando estados contables, consenso y perfil sectorial...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm py-16 text-center text-red-500 text-sm font-semibold">
        {error}
      </div>
    );
  }

  if (!valData) return null;

  const years = valData.years || [];
  const rows = valData.rows || [];
  const audit = valData.audit || { has_anomalies: false, flags: [], comparisons: [] };
  const trajectory = valData.trajectory || {};
  const classification = valData.classification || {};
  const reverseDcf = valData.reverse_dcf || {};
  const revBenchmarks = reverseDcf.benchmarks || {};

  const marginDeltas = trajectory.margin_deltas || {};
  const consensusRows = trajectory.consensus_rows || [];
  const sec8kFilings = trajectory.sec_8k_filings || [];

  const impliedGrowthNow = interactiveReverse?.impliedGrowthPct;
  const expectedBenchmarkPct = Number(
    revBenchmarks.expected_growth_pct ?? trajectory.recommended_rev_growth_pct ?? 0
  );
  const histBenchmarkPct = Number(
    revBenchmarks.hist_growth_pct ?? trajectory.hist_avg_growth_pct ?? 0
  );
  const gapPp =
    impliedGrowthNow !== null && impliedGrowthNow !== undefined
      ? Number((impliedGrowthNow - expectedBenchmarkPct).toFixed(1))
      : null;

  const baseWacc = Number(valData.dcf_inputs?.suggested_wacc_pct ?? 9.0);
  const baseMargin = Number(valData.dcf_inputs?.ebit_margin_pct ?? 15.0);
  const baseExitMult = Number(valData.dcf_inputs?.exit_multiple_default ?? 18.0);
  const baseKe = Number(valData.financial_sector_inputs?.cost_of_equity_pct ?? 9.5);

  const isCustomSensitized = isFinancial
    ? simKe !== baseKe
    : simWacc !== baseWacc || simMargin !== baseMargin || simExitMult !== baseExitMult;

  const applyScenarioPreset = (preset) => {
    if (isFinancial) {
      if (preset === 'stress') setSimKe(Number(Math.min(baseKe + 1.5, 16.0).toFixed(1)));
      else if (preset === 'favorable') setSimKe(Number(Math.max(baseKe - 1.0, 6.5).toFixed(1)));
      else setSimKe(baseKe);
      return;
    }

    if (preset === 'stress') {
      setSimWacc(Number(Math.min(baseWacc + 1.0, 15.0).toFixed(1)));
      setSimMargin(Number(Math.max(baseMargin - 2.0, 3.0).toFixed(1)));
      setSimExitMult(Number(Math.max(baseExitMult - 3.0, 8.0).toFixed(1)));
    } else if (preset === 'favorable') {
      setSimWacc(Number(Math.max(baseWacc - 1.0, 6.0).toFixed(1)));
      setSimMargin(Number(Math.min(baseMargin + 2.0, 55.0).toFixed(1)));
      setSimExitMult(Number(Math.min(baseExitMult + 3.0, 35.0).toFixed(1)));
    } else {
      setSimWacc(baseWacc);
      setSimMargin(baseMargin);
      setSimExitMult(baseExitMult);
    }
  };

  const getDynamicInsight = () => {
    if (!interactiveReverse?.solvable || impliedGrowthNow === null || impliedGrowthNow === undefined) {
      return {
        badge: 'Requiere expansión de márgenes',
        tone: 'amber',
        summary:
          'Con la rentabilidad operativa y el CapEx actuales, el crecimiento de ventas por sí solo no alcanza para justificar la cotización: el mercado está descontando una mejora estructural de márgenes.',
      };
    }

    if (gapPp !== null && gapPp >= 3.5) {
      return {
        badge: 'Vara exigente · Alto riesgo de ejecución',
        tone: 'amber',
        summary: `Para justificar su precio actual (${formatMoney(reverseDcf.current_price)}), ${valData.ticker} necesita crecer al ${impliedGrowthNow.toFixed(1)}% anual durante ${revHorizon} años, superando en ${gapPp.toFixed(1)} puntos porcentuales la proyección fundamental (${expectedBenchmarkPct.toFixed(1)}%). Cualquier desaceleración puede castigar el múltiplo.`,
      };
    }

    if (gapPp !== null && gapPp <= -2.5) {
      return {
        badge: 'Vara conservadora · Margen de seguridad',
        tone: 'emerald',
        summary: `El precio actual (${formatMoney(reverseDcf.current_price)}) solo descuenta un crecimiento de ${impliedGrowthNow.toFixed(1)}% anual a ${revHorizon} años, ubicado ${Math.abs(gapPp).toFixed(1)} puntos por debajo de lo que proyectan los analistas (${expectedBenchmarkPct.toFixed(1)}%). Si la empresa cumple con lo esperado, existe margen de revalorización.`,
      };
    }

    return {
      badge: 'Expectativas equilibradas · Precio justo',
      tone: 'neutral',
      summary: `La cotización actual (${formatMoney(reverseDcf.current_price)}) descuenta un ritmo de ${impliedGrowthNow.toFixed(1)}% anual a ${revHorizon} años, prácticamente alineado con la proyección fundamental (${expectedBenchmarkPct.toFixed(1)}%) y su trayectoria histórica (${histBenchmarkPct.toFixed(1)}%).`,
    };
  };

  const insight = getDynamicInsight();

  const scaleMax =
    Math.max(
      Math.abs(impliedGrowthNow || 0),
      Math.abs(expectedBenchmarkPct),
      Math.abs(histBenchmarkPct),
      15
    ) * 1.2;
  const barWidthPct = (v) =>
    v === null || v === undefined ? 0 : Math.min(Math.max((Math.max(v, 0) / scaleMax) * 100, 3), 100);

  const peerColumns = activePeersData?.is_financial
    ? [
        { key: 'market_cap_mm', label: 'Cap. Bursátil (MM)', type: 'money' },
        { key: 'pe_ltm', label: 'P/E LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'pe_ntm', label: 'P/E NTM', type: 'mult', lowerIsCheaper: true },
        { key: 'pb_ltm', label: 'P/BV LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'roe_pct', label: 'ROE LTM', type: 'pct' },
        { key: 'net_margin_pct', label: 'Margen Neto', type: 'pct' },
        { key: 'rev_growth_yoy_pct', label: 'Crec. Ingresos', type: 'pct' },
        { key: 'upside_ws_pct', label: 'Potencial WS', type: 'pct' },
      ]
    : [
        { key: 'market_cap_mm', label: 'Cap. Bursátil (MM)', type: 'money' },
        { key: 'ev_sales_ltm', label: 'EV/Ventas LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'ev_sales_ntm', label: 'EV/Ventas NTM', type: 'mult', lowerIsCheaper: true },
        { key: 'ev_ebitda_ltm', label: 'EV/EBITDA LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'pe_ltm', label: 'P/E LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'pe_ntm', label: 'P/E NTM', type: 'mult', lowerIsCheaper: true },
        { key: 'pb_ltm', label: 'P/BV LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'p_fcf_ltm', label: 'P/FCF LTM', type: 'mult', lowerIsCheaper: true },
        { key: 'fcf_yield_pct', label: 'FCF Yield', type: 'pct' },
        { key: 'ebit_margin_pct', label: 'Margen EBIT', type: 'pct' },
        { key: 'roic_pct', label: 'ROIC', type: 'pct' },
        { key: 'rev_growth_yoy_pct', label: 'Crec. Ventas', type: 'pct' },
      ];

  const formatPeerCell = (val, type) => {
    if (val === null || val === undefined || Number.isNaN(val)) return '-';
    if (val === 'N/M') return 'N/M';
    if (type === 'money') {
      return new Intl.NumberFormat('es-AR', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(val);
    }
    if (type === 'pct') return formatMult(val, '%');
    return formatMult(val, 'x');
  };

  return (
    <div className="space-y-6">
      {/* SUB-NAVEGACIÓN DE VALORACIÓN */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 px-2">
        <div className="flex space-x-6">
          <button
            type="button"
            onClick={() => setSubTab('multiplos')}
            className={`pb-2.5 text-sm transition-colors relative flex items-center gap-1.5 ${
              subTab === 'multiplos'
                ? 'text-orange-500 font-semibold cursor-default'
                : 'text-gray-500 hover:text-gray-800 font-medium cursor-pointer'
            }`}
          >
            <Calculator className="w-3.5 h-3.5" />
            Múltiplos Históricos y Consenso
            {subTab === 'multiplos' && (
              <span className="absolute -bottom-px left-0 w-full h-0.5 bg-orange-500"></span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setSubTab('competidores')}
            className={`pb-2.5 text-sm transition-colors relative flex items-center gap-1.5 ${
              subTab === 'competidores'
                ? 'text-orange-500 font-semibold cursor-default'
                : 'text-gray-500 hover:text-gray-800 font-medium cursor-pointer'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            Competidores
            {subTab === 'competidores' && (
              <span className="absolute -bottom-px left-0 w-full h-0.5 bg-orange-500"></span>
            )}
          </button>
        </div>

        {onOpenValuationModels && (
          <button
            type="button"
            onClick={() => onOpenValuationModels(valData.ticker)}
            className="mb-1.5 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold cursor-pointer shadow-2xs"
          >
            <span>Modelar Valor Intrínseco (DCF / Manual)</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {subTab === 'competidores' ? (
        peersLoading ? (
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm py-20 flex flex-col items-center justify-center text-orange-500">
            <Loader2 className="w-8 h-8 mb-3 animate-spin" />
            <p className="text-sm font-medium">
              Cargando múltiplos y métricas operativas de competidores del rubro...
            </p>
          </div>
        ) : peersError ? (
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm py-16 text-center text-red-500 text-sm font-semibold">
            {peersError}
          </div>
        ) : activePeersData ? (
          <div className="space-y-4">
            {peersRelativeInsight && (
              <div
                className={`rounded-lg border p-4 shadow-xs flex flex-wrap items-start justify-between gap-3 ${
                  peersRelativeInsight.tone === 'emerald'
                    ? 'bg-emerald-50/70 border-emerald-200 text-emerald-950'
                    : peersRelativeInsight.tone === 'amber'
                    ? 'bg-amber-50/70 border-amber-200 text-amber-950'
                    : 'bg-white border-gray-200 text-gray-800'
                }`}
              >
                <div className="flex items-start gap-2.5 flex-1">
                  <Scale className="w-4 h-4 text-orange-600 shrink-0 mt-0.5" />
                  <div className="text-xs leading-relaxed">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="font-bold text-gray-900">
                        Lectura Relativa frente al Sector
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                          peersRelativeInsight.tone === 'emerald'
                            ? 'bg-emerald-100 text-emerald-800'
                            : peersRelativeInsight.tone === 'amber'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {peersRelativeInsight.badge}
                      </span>
                    </div>
                    <p>{peersRelativeInsight.summary}</p>
                  </div>
                </div>
              </div>
            )}

            <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex flex-wrap justify-between items-center gap-2">
                <div>
                  <span className="text-sm font-bold text-gray-800">
                    Comparables Sectoriales | {activePeersData.ticker} vs. Pares
                  </span>
                  {(activePeersData.sector || activePeersData.industry) && (
                    <span className="ml-2 text-xs text-gray-500">
                      ({activePeersData.sector}{activePeersData.industry ? ` · ${activePeersData.industry}` : ''})
                    </span>
                  )}
                </div>
                <span className="text-xs text-gray-400 italic">
                  Valuación relativa LTM / NTM y márgenes operativos (cifras en USD)
                </span>
              </div>

              <div className="w-full overflow-x-auto">
                <table className="w-full text-[12.5px] text-left whitespace-nowrap">
                  <thead>
                    <tr className="bg-[#333333] text-white">
                      <th className="py-2.5 px-3.5 font-bold sticky left-0 bg-[#333333] z-10 min-w-52">
                        Empresa | Ticker
                      </th>
                      <th className="py-2.5 px-3 font-bold text-right">Precio (US$)</th>
                      {peerColumns.map((col) => (
                        <th key={col.key} className="py-2.5 px-3 font-bold text-right">
                          {col.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {activePeersData.base && (
                      <tr className="border-b-2 border-orange-200 bg-orange-50/50 font-semibold">
                        <td className="py-2.5 px-3.5 sticky left-0 bg-orange-50 z-10 text-gray-900 shadow-[1px_0_0_0_#fed7aa]">
                          <span className="font-bold text-orange-600 mr-2">{activePeersData.base.ticker}</span>
                          <span className="text-xs text-gray-700">{activePeersData.base.name}</span>
                        </td>
                        <td className="py-2.5 px-3 text-right tabular-nums text-gray-900">
                          {formatMoney(activePeersData.base.price)}
                        </td>
                        {peerColumns.map((col) => {
                          const rawVal = activePeersData.base[col.key];
                          const isNm = rawVal === 'N/M';
                          return (
                            <td
                              key={col.key}
                              title={isNm ? 'No significativo (denominador negativo o nulo en LTM)' : undefined}
                              className={`py-2.5 px-3 text-right tabular-nums ${
                                isNm ? 'text-gray-400 italic font-normal' : 'text-gray-900'
                              }`}
                            >
                              {formatPeerCell(rawVal, col.type)}
                            </td>
                          );
                        })}
                      </tr>
                    )}

                    {(activePeersData.peers || []).map((peer) => (
                      <tr key={peer.ticker} className="border-b border-gray-100 hover:bg-gray-50 group">
                        <td className="py-2 px-3.5 sticky left-0 bg-white group-hover:bg-gray-50 z-10 shadow-[1px_0_0_0_#f3f4f6]">
                          <span className="font-bold text-gray-900 mr-2">{peer.ticker}</span>
                          <span className="text-xs text-gray-500">{peer.name}</span>
                        </td>
                        <td className="py-2 px-3 text-right tabular-nums text-gray-800">
                          {formatMoney(peer.price)}
                        </td>
                        {peerColumns.map((col) => {
                          const rawVal = peer[col.key];
                          const isNm = rawVal === 'N/M';
                          return (
                            <td
                              key={col.key}
                              title={isNm ? 'No significativo (denominador negativo o nulo en LTM)' : undefined}
                              className={`py-2 px-3 text-right tabular-nums ${
                                isNm ? 'text-gray-400 italic' : 'text-gray-800'
                              }`}
                            >
                              {formatPeerCell(rawVal, col.type)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}

                    <tr className="border-t-2 border-gray-300 bg-gray-50 font-semibold text-gray-800">
                      <td className="py-2 px-3.5 sticky left-0 bg-gray-50 z-10 shadow-[1px_0_0_0_#e5e7eb]">
                        Promedio Competidores
                      </td>
                      <td className="py-2 px-3 text-right text-gray-400">-</td>
                      {peerColumns.map((col) => (
                        <td key={col.key} className="py-2 px-3 text-right tabular-nums">
                          {formatPeerCell(activePeersData.peers_avg?.[col.key], col.type)}
                        </td>
                      ))}
                    </tr>

                    <tr className="border-b border-gray-200 bg-gray-100/80 font-bold text-gray-900">
                      <td className="py-2 px-3.5 sticky left-0 bg-gray-100 z-10 shadow-[1px_0_0_0_#e5e7eb]">
                        Mediana Competidores
                      </td>
                      <td className="py-2 px-3 text-right text-gray-400">-</td>
                      {peerColumns.map((col) => (
                        <td key={col.key} className="py-2 px-3 text-right tabular-nums">
                          {formatPeerCell(activePeersData.peers_med?.[col.key], col.type)}
                        </td>
                      ))}
                    </tr>

                    <tr className="bg-white font-bold">
                      <td className="py-2.5 px-3.5 sticky left-0 bg-white z-10 text-gray-700 shadow-[1px_0_0_0_#f3f4f6]">
                        Prima / (Descuento) {activePeersData.ticker} vs. Mediana
                      </td>
                      <td className="py-2.5 px-3 text-right text-gray-400">-</td>
                      {peerColumns.map((col) => {
                        const prem = activePeersData.relative_premium_pct?.[col.key];
                        if (prem === null || prem === undefined) {
                          return (
                            <td key={col.key} className="py-2.5 px-3 text-right text-gray-400">
                              -
                            </td>
                          );
                        }
                        const isFavorable = col.lowerIsCheaper ? prem < 0 : prem > 0;
                        return (
                          <td
                            key={col.key}
                            className={`py-2.5 px-3 text-right tabular-nums ${
                              isFavorable ? 'text-emerald-700' : 'text-[#d93025]'
                            }`}
                          >
                            {prem > 0 ? `+${prem.toFixed(1)}%` : `${prem.toFixed(1)}%`}
                          </td>
                        );
                      })}
                    </tr>
                  </tbody>
                </table>
              </div>
              <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 text-[11px] text-gray-500">
                <strong>N/M</strong>: Múltiplo no significativo (flujo o resultado negativo en LTM; excluido del promedio y mediana). El promedio de múltiplos excluye outliers mayores a 250x.
              </div>
            </div>
          </div>
        ) : null
      ) : (
        <>
          {/* BANNER DE PERFIL SECTORIAL */}
          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-start space-x-3">
              <div className="p-2 rounded bg-orange-50 text-orange-600 shrink-0 mt-0.5">
                {isFinancial ? <Landmark className="w-5 h-5" /> : <Building2 className="w-5 h-5" />}
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-orange-600">
                    Perfil Sectorial: {routing.label}
                  </span>
                  {classification.sector && (
                    <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                      {classification.sector} {classification.industry ? `· ${classification.industry}` : ''}
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-600 mt-1">{routing.rationale}</p>
              </div>
            </div>
            <div className="text-right shrink-0">
              <span className="text-[11px] text-gray-400 block">Modelo recomendado</span>
              <span className="text-xs font-bold text-gray-900">{routing.primary_model}</span>
            </div>
          </div>

          {/* BLOQUE 0: AUDITORÍA AUTOMÁTICA DE DISTORSIONES CONTABLES */}
          {audit.has_anomalies && (
            <div className="bg-amber-50/70 border border-amber-200 rounded-lg p-4 shadow-xs">
              <div className="flex items-start space-x-2.5">
                <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h3 className="text-sm font-bold text-gray-900">
                    Auditoría de Calidad Contable: se detectaron eventos con impacto material en {valData.ticker}
                  </h3>
                  <p className="text-xs text-gray-600 mt-0.5">
                    Los múltiplos reportados oficiales se mantienen intactos en la tabla, pero las siguientes partidas alteran la lectura recurrente:
                  </p>

                  <div className="mt-3 space-y-2">
                    {audit.flags.map((f) => (
                      <div
                        key={f.code}
                        className="bg-white border border-amber-200/80 rounded px-3 py-2 text-xs"
                      >
                        <div className="flex items-center justify-between font-semibold text-gray-900">
                          <span className="flex items-center">
                            <Info className="w-3.5 h-3.5 text-amber-600 mr-1.5" />
                            {f.title}
                          </span>
                          <span className="text-amber-700 tabular-nums">
                            Impacto: {formatMoney(f.impact_mm)} MM
                          </span>
                        </div>
                        <p className="text-gray-600 mt-1 leading-relaxed">{f.detail}</p>
                      </div>
                    ))}
                  </div>

                  {audit.comparisons.length > 0 && (
                    <div className="mt-3 bg-white border border-amber-200/80 rounded overflow-hidden">
                      <table className="w-full text-xs text-left">
                        <thead>
                          <tr className="bg-amber-100/60 text-gray-800 font-semibold">
                            <th className="py-1.5 px-3">Métrica afectada</th>
                            <th className="py-1.5 px-3 text-right">Valor Reportado</th>
                            <th className="py-1.5 px-3 text-right text-emerald-700">Valor Sin Distorsión</th>
                            <th className="py-1.5 px-3">Criterio de ajuste</th>
                          </tr>
                        </thead>
                        <tbody>
                          {audit.comparisons.map((c, i) => (
                            <tr key={i} className="border-t border-amber-100">
                              <td className="py-1.5 px-3 font-medium text-gray-800">{c.metric}</td>
                              <td className="py-1.5 px-3 text-right tabular-nums text-gray-700">{c.reported}</td>
                              <td className="py-1.5 px-3 text-right tabular-nums font-bold text-emerald-700">{c.adjusted}</td>
                              <td className="py-1.5 px-3 text-gray-500">{c.note}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {valData?.valuation_comparison?.has_material_diff && (
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2.5">
                      <div className="bg-white border border-gray-200 rounded-lg p-3 text-xs">
                        <span className="text-[11px] font-bold uppercase tracking-wide text-gray-500">
                          {valData.valuation_comparison.as_reported.label}
                        </span>
                        <div className="flex items-baseline justify-between mt-1">
                          <span className="text-base font-extrabold text-gray-900 tabular-nums">
                            {formatMoney(valData.valuation_comparison.as_reported.intrinsic_value_per_share)}
                          </span>
                          {valData.valuation_comparison.as_reported.upside_pct != null && (
                            <span className="text-xs font-semibold text-gray-600 tabular-nums">
                              {valData.valuation_comparison.as_reported.upside_pct >= 0 ? "+" : ""}
                              {valData.valuation_comparison.as_reported.upside_pct.toFixed(1)}% vs. precio
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-gray-500 mt-1">
                          Margen EBIT {valData.valuation_comparison.as_reported.ebit_margin_pct}% · CapEx {valData.valuation_comparison.as_reported.capex_pct}% · Imp. {valData.valuation_comparison.as_reported.tax_rate_pct}%
                        </p>
                      </div>

                      <div className="bg-emerald-50/70 border border-emerald-200 rounded-lg p-3 text-xs">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11px] font-bold uppercase tracking-wide text-emerald-800">
                            {valData.valuation_comparison.normalized.label}
                          </span>
                          {valData.valuation_comparison.delta_pct != null && (
                            <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[11px] font-bold tabular-nums">
                              {valData.valuation_comparison.delta_pct >= 0 ? "+" : ""}
                              {valData.valuation_comparison.delta_pct.toFixed(1)}% impacto
                            </span>
                          )}
                        </div>
                        <div className="flex items-baseline justify-between mt-1">
                          <span className="text-base font-extrabold text-emerald-900 tabular-nums">
                            {formatMoney(valData.valuation_comparison.normalized.intrinsic_value_per_share)}
                          </span>
                          {valData.valuation_comparison.normalized.upside_pct != null && (
                            <span className="text-xs font-semibold text-emerald-700 tabular-nums">
                              {valData.valuation_comparison.normalized.upside_pct >= 0 ? "+" : ""}
                              {valData.valuation_comparison.normalized.upside_pct.toFixed(1)}% vs. precio
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-emerald-800/80 mt-1">
                          Margen EBIT obj. {valData.valuation_comparison.normalized.target_ebit_margin_pct}% · CapEx mant. {valData.valuation_comparison.normalized.capex_pct}% · Imp. {valData.valuation_comparison.normalized.tax_rate_pct}%
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* BLOQUE 1: CONSENSO DE ANALISTAS, TRAYECTORIA DE MÁRGENES Y GUIDANCE SEC 8-K */}
          {(consensusRows.length > 0 || (trajectory.margin_history || []).length > 0) && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden flex flex-col justify-between">
                <div>
                  <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex justify-between items-center">
                    <span className="text-sm font-bold text-gray-800">
                      Consenso de Wall Street (Ingresos y BPA Esperados)
                    </span>
                    <span className="text-xs text-gray-500">
                      Crecimiento ponderado DCF: <strong className="text-orange-600">{trajectory.recommended_rev_growth_pct}%</strong>
                    </span>
                  </div>

                  {consensusRows.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left whitespace-nowrap">
                        <thead>
                          <tr className="bg-[#333333] text-white">
                            <th className="py-2 px-3.5 font-bold">Período</th>
                            <th className="py-2 px-3 text-right font-bold">Ingresos Est. (MM)</th>
                            <th className="py-2 px-3 text-right font-bold">Crec. Ventas</th>
                            <th className="py-2 px-3 text-right font-bold">BPA Est. (EPS)</th>
                            <th className="py-2 px-3 text-right font-bold">Crec. BPA</th>
                            <th className="py-2 px-3 text-right font-bold">Analistas</th>
                          </tr>
                        </thead>
                        <tbody>
                          {consensusRows.map((c) => (
                            <tr key={c.period_key} className="border-b border-gray-100 hover:bg-gray-50">
                              <td className="py-2 px-3.5 font-medium text-gray-800">{c.period_label}</td>
                              <td className="py-2 px-3 text-right tabular-nums font-semibold text-gray-900">
                                {c.rev_avg_mm !== null ? formatMoney(c.rev_avg_mm) : '-'}
                              </td>
                              <td
                                className={`py-2 px-3 text-right tabular-nums font-semibold ${
                                  (c.rev_growth_pct || 0) >= 0 ? 'text-emerald-700' : 'text-[#d93025]'
                                }`}
                              >
                                {c.rev_growth_pct !== null ? `${c.rev_growth_pct >= 0 ? '+' : ''}${c.rev_growth_pct.toFixed(1)}%` : '-'}
                              </td>
                              <td className="py-2 px-3 text-right tabular-nums font-semibold text-gray-900">
                                {c.eps_avg !== null ? `US$ ${c.eps_avg.toFixed(2)}` : '-'}
                              </td>
                              <td
                                className={`py-2 px-3 text-right tabular-nums font-semibold ${
                                  (c.eps_growth_pct || 0) >= 0 ? 'text-emerald-700' : 'text-[#d93025]'
                                }`}
                              >
                                {c.eps_growth_pct !== null ? `${c.eps_growth_pct >= 0 ? '+' : ''}${c.eps_growth_pct.toFixed(1)}%` : '-'}
                              </td>
                              <td className="py-2 px-3 text-right tabular-nums text-gray-500">
                                {c.eps_analysts || c.rev_analysts || '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="p-6 text-xs text-gray-500">
                      Sin estimaciones de consenso detalladas disponibles para este ticker; se utiliza la trayectoria histórica auditada ({trajectory.hist_avg_growth_pct}%).
                    </div>
                  )}
                </div>

                {sec8kFilings.length > 0 && (
                  <div className="px-4 py-2.5 bg-gray-50 border-t border-gray-200 flex flex-wrap items-center justify-between gap-2 text-xs">
                    <span className="font-semibold text-gray-700">
                      Comunicados SEC 8-K (Ítem 2.02 · Resultados y Guidance):
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {sec8kFilings.map((f, idx) => (
                        <a
                          key={idx}
                          href={f.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center px-2 py-0.5 rounded bg-white border border-gray-300 text-blue-600 hover:text-blue-800 hover:border-blue-400 transition-colors"
                        >
                          {f.form} ({f.filing_date}) <ExternalLink className="w-3 h-3 ml-1" />
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4 flex flex-col justify-between">
                <div>
                  <h4 className="text-sm font-bold text-gray-800 pb-2 border-b border-gray-200">
                    Dinámica de Márgenes (5Y)
                  </h4>

                  <div className="mt-3 space-y-2.5 text-xs">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">Variación Margen Bruto (5Y):</span>
                      <span
                        className={`font-bold tabular-nums ${
                          (marginDeltas.gross_margin_delta_pct || 0) >= 0 ? 'text-emerald-700' : 'text-[#d93025]'
                        }`}
                      >
                        {(marginDeltas.gross_margin_delta_pct || 0) >= 0 ? '+' : ''}
                        {(marginDeltas.gross_margin_delta_pct || 0).toFixed(1)} pp
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">Variación Margen Operativo (5Y):</span>
                      <span
                        className={`font-bold tabular-nums ${
                          (marginDeltas.operating_margin_delta_pct || 0) >= 0 ? 'text-emerald-700' : 'text-[#d93025]'
                        }`}
                      >
                        {(marginDeltas.operating_margin_delta_pct || 0) >= 0 ? '+' : ''}
                        {(marginDeltas.operating_margin_delta_pct || 0).toFixed(1)} pp
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">Variación Margen Neto (5Y):</span>
                      <span
                        className={`font-bold tabular-nums ${
                          (marginDeltas.net_margin_delta_pct || 0) >= 0 ? 'text-emerald-700' : 'text-[#d93025]'
                        }`}
                      >
                        {(marginDeltas.net_margin_delta_pct || 0) >= 0 ? '+' : ''}
                        {(marginDeltas.net_margin_delta_pct || 0).toFixed(1)} pp
                      </span>
                    </div>
                  </div>
                </div>

                <div
                  className={`mt-4 p-3 rounded border text-xs leading-relaxed ${
                    trajectory.leverage_signal === 'expanding'
                      ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                      : trajectory.leverage_signal === 'compressing'
                      ? 'bg-amber-50/70 border-amber-200 text-amber-950'
                      : 'bg-gray-50 border-gray-200 text-gray-700'
                  }`}
                >
                  <div className="flex items-center font-bold mb-1">
                    {trajectory.leverage_signal === 'expanding' ? (
                      <TrendingUp className="w-3.5 h-3.5 mr-1.5 text-emerald-600" />
                    ) : trajectory.leverage_signal === 'compressing' ? (
                      <TrendingDown className="w-3.5 h-3.5 mr-1.5 text-amber-600" />
                    ) : (
                      <Minus className="w-3.5 h-3.5 mr-1.5 text-gray-500" />
                    )}
                    <span>Proyección Operativa</span>
                  </div>
                  <p>{trajectory.leverage_label}</p>
                </div>
              </div>
            </div>
          )}

          {/* BLOQUE 1.5 (ETAPA 9): DCF INVERSO / EXPECTATIONS INVESTING */}
          {reverseDcf?.model_label && (
            <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 bg-slate-900 text-white flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <Compass className="w-4 h-4 text-orange-400 shrink-0" />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold">
                        DCF Inverso (Expectations Investing) · {valData.ticker}
                      </span>
                      <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-orange-300 border border-slate-700 font-medium">
                        Cotización analizada: {formatMoney(reverseDcf.current_price)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-400">Plazo de exigencia:</span>
                  <div className="inline-flex rounded-md bg-slate-800 p-0.5 border border-slate-700">
                    {[5, 10].map((yr) => (
                      <button
                        key={yr}
                        type="button"
                        onClick={() => setRevHorizon(yr)}
                        className={`px-2.5 py-1 rounded text-xs font-semibold cursor-pointer transition-colors ${
                          revHorizon === yr
                            ? 'bg-orange-500 text-white'
                            : 'text-slate-300 hover:text-white'
                        }`}
                      >
                        Próximos {yr} años
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="px-4 py-2.5 bg-slate-50 border-b border-gray-200 flex items-start gap-2 text-xs text-slate-600">
                <HelpCircle className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                <p className="leading-relaxed">
                  <strong className="text-slate-800">¿Qué estás viendo?</strong> En lugar de estimar un precio objetivo, este modelo invierte el flujo descontado: parte del precio real al que cotiza hoy{' '}
                  <strong className="text-slate-800">{valData.ticker}</strong> y despeja{' '}
                  <strong className="text-slate-800">
                    {isFinancial
                      ? 'qué rentabilidad (ROE) y expansión patrimonial anual'
                      : 'cuánto deben crecer sus ventas cada año'}
                  </strong>{' '}
                  para justificar ese valor. Comparando esa exigencia con su historial y el consenso sabés si el mercado pide metas realistas o está descontando perfección.
                </p>
              </div>

              <div className="p-4 grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
                <div className="lg:col-span-4 flex flex-col justify-between space-y-3">
                  <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                        {isFinancial
                          ? `Meta implícita en precio (${revHorizon}Y)`
                          : `Crecimiento exigido por el precio (${revHorizon}Y)`}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                          insight.tone === 'emerald'
                            ? 'bg-emerald-100 text-emerald-800'
                            : insight.tone === 'amber'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-slate-200 text-slate-800'
                        }`}
                      >
                        {insight.badge}
                      </span>
                    </div>

                    <div className="flex items-baseline gap-2.5 mt-2">
                      <span className="text-3xl font-extrabold text-slate-900 tabular-nums">
                        {interactiveReverse?.solvable && impliedGrowthNow !== null
                          ? `${impliedGrowthNow >= 0 ? '+' : ''}${impliedGrowthNow.toFixed(1)}%`
                          : 'N/D'}
                      </span>
                      <span className="text-xs font-medium text-slate-500">
                        {isFinancial ? 'anual de valor libros' : 'anual en ventas'}
                      </span>
                    </div>

                    {interactiveReverse?.solvable && (
                      <p className="text-[11px] text-slate-500 mt-1.5 leading-relaxed">
                        {isFinancial
                          ? `Requiere sostener un ROE promedio del ${interactiveReverse.impliedRoePct?.toFixed(1)}% (asumiendo Costo de Equity del ${Number(simKe || baseKe).toFixed(1)}%).`
                          : `Rango técnico según criterio de valor terminal: entre ${Math.min(interactiveReverse.gordonPct, interactiveReverse.multPct).toFixed(1)}% (perpetuidad) y ${Math.max(interactiveReverse.gordonPct, interactiveReverse.multPct).toFixed(1)}% (múltiplo de salida).`}
                      </p>
                    )}
                  </div>

                  <div
                    className={`p-3.5 rounded-lg border text-xs leading-relaxed flex-1 ${
                      insight.tone === 'emerald'
                        ? 'bg-emerald-50/70 border-emerald-200 text-emerald-950'
                        : insight.tone === 'amber'
                        ? 'bg-amber-50/70 border-amber-200 text-amber-950'
                        : 'bg-gray-50 border-gray-200 text-gray-700'
                    }`}
                  >
                    <span className="font-bold block mb-1 uppercase tracking-wider text-[10.5px] opacity-80">
                      Lectura práctica para el inversor
                    </span>
                    <p>{insight.summary}</p>
                  </div>
                </div>

                <div className="lg:col-span-4 border border-gray-200 rounded-lg p-3.5 flex flex-col justify-between text-xs">
                  <div>
                    <h4 className="font-bold text-gray-900">
                      Prueba de Realidad: Exigencia vs. Fundamentos
                    </h4>
                    <p className="text-[11px] text-gray-500 mt-0.5">
                      Comparación del ritmo anual necesario frente a lo que proyecta el mercado y lo que ya logró la empresa.
                    </p>

                    <div className="mt-4 space-y-3.5">
                      <div>
                        <div className="flex justify-between items-baseline mb-1">
                          <div>
                            <span className="font-bold text-orange-700 block">
                              1. Exigencia implícita en el precio hoy
                            </span>
                            <span className="text-[10.5px] text-gray-400">
                              Lo que necesita ocurrir para justificar {formatMoney(reverseDcf.current_price)}
                            </span>
                          </div>
                          <span className="font-extrabold text-orange-700 tabular-nums text-sm">
                            {impliedGrowthNow !== null && impliedGrowthNow !== undefined
                              ? `${impliedGrowthNow >= 0 ? '+' : ''}${impliedGrowthNow.toFixed(1)}%`
                              : 'N/D'}
                          </span>
                        </div>
                        <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-orange-500 rounded-full transition-all duration-200"
                            style={{ width: `${barWidthPct(impliedGrowthNow)}%` }}
                          />
                        </div>
                      </div>

                      <div>
                        <div className="flex justify-between items-baseline mb-1">
                          <div>
                            <span className="font-semibold text-slate-800 block">
                              {isFinancial
                                ? '2. Capacidad orgánica actual (ROE × Retención)'
                                : '2. Proyección fundamental (Consenso + Tendencia)'}
                            </span>
                            <span className="text-[10.5px] text-gray-400">
                              Expectativa base ponderada de analistas y trayectoria
                            </span>
                          </div>
                          <span className="font-bold text-slate-800 tabular-nums text-sm">
                            {expectedBenchmarkPct >= 0 ? '+' : ''}
                            {expectedBenchmarkPct.toFixed(1)}%
                          </span>
                        </div>
                        <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-slate-800 rounded-full"
                            style={{ width: `${barWidthPct(expectedBenchmarkPct)}%` }}
                          />
                        </div>
                      </div>

                      <div>
                        <div className="flex justify-between items-baseline mb-1">
                          <div>
                            <span className="font-semibold text-emerald-800 block">
                              3. Ritmo histórico real (últimos 3–5 años)
                            </span>
                            <span className="text-[10.5px] text-gray-400">
                              Desempeño auditado ya demostrado por el negocio
                            </span>
                          </div>
                          <span className="font-bold text-emerald-700 tabular-nums text-sm">
                            {histBenchmarkPct >= 0 ? '+' : ''}
                            {histBenchmarkPct.toFixed(1)}%
                          </span>
                        </div>
                        <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-emerald-600 rounded-full"
                            style={{ width: `${barWidthPct(histBenchmarkPct)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 pt-2.5 border-t border-gray-100 text-[11px] text-gray-500">
                    <strong>Regla de lectura:</strong> cuando la barra naranja es menor a las barras oscura y verde, el precio actual no exige aceleración extraordinaria.
                  </div>
                </div>

                <div className="lg:col-span-4 bg-gray-50 border border-gray-200 rounded-lg p-3.5 flex flex-col justify-between text-xs">
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-gray-900">
                        ¿Qué pasa si cambia el contexto?
                      </span>
                      {isCustomSensitized && (
                        <button
                          type="button"
                          onClick={() => applyScenarioPreset('base')}
                          className="inline-flex items-center gap-1 text-[11px] text-orange-600 hover:underline font-semibold cursor-pointer"
                        >
                          <RotateCcw className="w-3 h-3" /> Volver a Base
                        </button>
                      )}
                    </div>
                    <p className="text-[11px] text-gray-500 mt-0.5">
                      Probá cómo cambia el crecimiento exigido bajo distintos escenarios de tasas y rentabilidad:
                    </p>

                    <div className="grid grid-cols-3 gap-1.5 mt-3">
                      <button
                        type="button"
                        onClick={() => applyScenarioPreset('stress')}
                        className="px-2 py-2 rounded border border-gray-200 bg-white hover:border-amber-400 hover:bg-amber-50/40 text-left transition-colors cursor-pointer"
                      >
                        <span className="font-bold text-gray-800 block text-[11px]">
                          Estrés / Tasas +
                        </span>
                        <span className="text-[10px] text-gray-500 block mt-0.5">
                          {isFinancial ? 'Ke +1.5 pp' : 'WACC +1%, EBIT -2pp'}
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => applyScenarioPreset('base')}
                        className={`px-2 py-2 rounded border text-left transition-colors cursor-pointer ${
                          !isCustomSensitized
                            ? 'border-orange-400 bg-orange-50/60'
                            : 'border-gray-200 bg-white hover:border-gray-300'
                        }`}
                      >
                        <span className="font-bold text-gray-800 block text-[11px]">
                          Escenario Base
                        </span>
                        <span className="text-[10px] text-gray-500 block mt-0.5">
                          Supuestos actuales
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => applyScenarioPreset('favorable')}
                        className="px-2 py-2 rounded border border-gray-200 bg-white hover:border-emerald-400 hover:bg-emerald-50/40 text-left transition-colors cursor-pointer"
                      >
                        <span className="font-bold text-gray-800 block text-[11px]">
                          Favorable
                        </span>
                        <span className="text-[10px] text-gray-500 block mt-0.5">
                          {isFinancial ? 'Ke -1.0 pp' : 'WACC -1%, EBIT +2pp'}
                        </span>
                      </button>
                    </div>

                    <div className="mt-3 p-2.5 rounded bg-white border border-gray-200/80 text-[11px] text-gray-600 flex flex-wrap justify-between gap-2">
                      {isFinancial ? (
                        <>
                          <span>
                            Costo de Equity (Ke): <strong className="text-gray-900">{Number(simKe || baseKe).toFixed(1)}%</strong>
                          </span>
                          <span>
                            Payout: <strong className="text-gray-900">{revBenchmarks.payout_ratio_pct}%</strong>
                          </span>
                        </>
                      ) : (
                        <>
                          <span>
                            WACC: <strong className="text-gray-900">{Number(simWacc || baseWacc).toFixed(1)}%</strong>
                          </span>
                          <span>
                            Margen EBIT: <strong className="text-gray-900">{Number(simMargin || baseMargin).toFixed(1)}%</strong>
                          </span>
                          <span>
                            Salida: <strong className="text-gray-900">{Number(simExitMult || baseExitMult).toFixed(1)}x</strong>
                          </span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="mt-3 pt-2.5 border-t border-gray-200">
                    <button
                      type="button"
                      onClick={() => setShowAdvancedSliders((prev) => !prev)}
                      className="w-full flex items-center justify-between text-[11px] font-semibold text-slate-700 hover:text-orange-600 cursor-pointer"
                    >
                      <span className="inline-flex items-center gap-1.5">
                        <SlidersHorizontal className="w-3.5 h-3.5" />
                        Ajuste fino de variables técnicas
                      </span>
                      {showAdvancedSliders ? (
                        <ChevronUp className="w-3.5 h-3.5" />
                      ) : (
                        <ChevronDown className="w-3.5 h-3.5" />
                      )}
                    </button>

                    {showAdvancedSliders && (
                      <div className="mt-2.5 space-y-2.5 pt-2 border-t border-gray-100">
                        {isFinancial ? (
                          <div>
                            <div className="flex justify-between text-[11px] mb-1">
                              <span className="text-gray-600">Costo de Equity (Ke):</span>
                              <span className="font-bold text-gray-900 tabular-nums">
                                {Number(simKe || 9.5).toFixed(1)}%
                              </span>
                            </div>
                            <input
                              type="range"
                              min="6.5"
                              max="16.0"
                              step="0.5"
                              value={simKe ?? 9.5}
                              onChange={(e) => setSimKe(Number(e.target.value))}
                              className="w-full accent-orange-500 cursor-pointer"
                            />
                          </div>
                        ) : (
                          <>
                            <div>
                              <div className="flex justify-between text-[11px] mb-0.5">
                                <span className="text-gray-600">Tasa de Descuento (WACC):</span>
                                <span className="font-bold text-gray-900 tabular-nums">
                                  {Number(simWacc || 9.0).toFixed(1)}%
                                </span>
                              </div>
                              <input
                                type="range"
                                min="6.0"
                                max="15.0"
                                step="0.5"
                                value={simWacc ?? 9.0}
                                onChange={(e) => setSimWacc(Number(e.target.value))}
                                className="w-full accent-orange-500 cursor-pointer"
                              />
                            </div>

                            <div>
                              <div className="flex justify-between text-[11px] mb-0.5">
                                <span className="text-gray-600">Margen Operativo (EBIT):</span>
                                <span className="font-bold text-gray-900 tabular-nums">
                                  {Number(simMargin || 15.0).toFixed(1)}%
                                </span>
                              </div>
                              <input
                                type="range"
                                min="3.0"
                                max="55.0"
                                step="0.5"
                                value={simMargin ?? 15.0}
                                onChange={(e) => setSimMargin(Number(e.target.value))}
                                className="w-full accent-orange-500 cursor-pointer"
                              />
                            </div>

                            <div>
                              <div className="flex justify-between text-[11px] mb-0.5">
                                <span className="text-gray-600">Múltiplo de Salida (EV/FCF):</span>
                                <span className="font-bold text-gray-900 tabular-nums">
                                  {Number(simExitMult || 18.0).toFixed(1)}x
                                </span>
                              </div>
                              <input
                                type="range"
                                min="8.0"
                                max="35.0"
                                step="1.0"
                                value={simExitMult ?? 18.0}
                                onChange={(e) => setSimExitMult(Number(e.target.value))}
                                className="w-full accent-orange-500 cursor-pointer"
                              />
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* BLOQUE 2: TABLA DE MÚLTIPLOS HISTÓRICOS ESTILO TIKR */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex flex-wrap justify-between items-center gap-2">
              <span className="text-sm font-bold text-gray-800">
                Múltiplos Históricos de Valoración | {valData.ticker}
              </span>
              <span className="text-xs text-gray-400 italic">
                Cierres anuales cruzados con estados 10-K (SEC) y snapshot LTM
              </span>
            </div>

            {historicalMultiplesInsight && (
              <div
                className={`px-4 py-3 border-b text-xs leading-relaxed ${
                  historicalMultiplesInsight.tone === 'emerald'
                    ? 'bg-emerald-50/70 border-emerald-200 text-emerald-950'
                    : historicalMultiplesInsight.tone === 'amber'
                    ? 'bg-amber-50/70 border-amber-200 text-amber-950'
                    : 'bg-slate-50 border-gray-200 text-slate-700'
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                  <span className="font-bold text-gray-900">
                    {historicalMultiplesInsight.title}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                      historicalMultiplesInsight.tone === 'emerald'
                        ? 'bg-emerald-100 text-emerald-800'
                        : historicalMultiplesInsight.tone === 'amber'
                        ? 'bg-amber-100 text-amber-800'
                        : 'bg-slate-200 text-slate-700'
                    }`}
                  >
                    {historicalMultiplesInsight.badge}
                  </span>
                </div>
                <p>{historicalMultiplesInsight.detail}</p>
                <p className="text-[11px] text-gray-500 mt-1.5">
                  <strong>Guía rápida:</strong> compará la columna <strong>Actual (LTM)</strong> contra <strong>Med. 5Y</strong> (mediana histórica, más robusta que el promedio frente a años atípicos). Los múltiplos <strong>NTM</strong> usan ganancias proyectadas a 12 meses; los múltiplos <strong>EV</strong> contemplan deuda y caja neta.
                </p>
              </div>
            )}

            <div className="w-full overflow-x-auto">
              <table className="w-full text-[12.5px] text-left whitespace-nowrap">
                <thead>
                  <tr className="bg-[#333333] text-white">
                    <th className="py-2.5 px-3.5 font-bold sticky left-0 bg-[#333333] z-10 min-w-60">
                      Múltiplo | Vektor
                    </th>
                    {years.map((y) => (
                      <th key={y} className="py-2.5 px-3 font-bold text-right">
                        {y}
                      </th>
                    ))}
                    <th className="py-2.5 px-3 font-bold text-right bg-[#262626] text-orange-400">
                      Actual (LTM)
                    </th>
                    <th className="py-2.5 px-3 font-bold text-right">Prom. 5Y</th>
                    <th className="py-2.5 px-3 font-bold text-right">Med. 5Y</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, idx) => {
                    const showSection = idx === 0 || row.section !== rows[idx - 1].section;
                    const hasGlossary = Boolean(getGlossaryEntry(row.metric));
                    const formattedLtm = formatMult(row.ltm, row.suffix);
                    const highlight = getMultipleHighlight(row);

                    const ltmCellStyle = highlight
                      ? highlight.cellClass
                      : `bg-orange-50/40 ${
                          typeof row.ltm === 'number' && row.ltm < 0
                            ? 'text-[#d93025]'
                            : 'text-gray-900'
                        }`;

                    return (
                      <Fragment key={row.metric}>
                        {showSection && (
                          <tr className="border-b border-gray-100 bg-gray-50/90">
                            <td
                              colSpan={years.length + 4}
                              className="py-2 px-3.5 font-bold text-gray-900 sticky left-0"
                            >
                              {row.section}
                            </td>
                          </tr>
                        )}
                        <tr className="border-b border-gray-100 hover:bg-gray-50 group">
                          <td className="py-2 px-3.5 sticky left-0 bg-white group-hover:bg-gray-50 z-10 text-gray-700 font-medium shadow-[1px_0_0_0_#f3f4f6]">
                            <div className="flex items-center justify-between gap-1.5">
                              <span className="truncate">{row.metric}</span>
                              {hasGlossary && onOpenInfo && (
                                <button
                                  type="button"
                                  onClick={() => onOpenInfo(row.metric, formattedLtm)}
                                  title="Ver explicación, fórmula y rangos de referencia"
                                  className="text-gray-400 hover:text-orange-500 transition-colors cursor-pointer shrink-0"
                                >
                                  <Info className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </div>
                          </td>
                          {years.map((y) => {
                            const v = row[y];
                            const isNeg = typeof v === 'number' && v < 0;
                            return (
                              <td
                                key={y}
                                className={`py-2 px-3 text-right tabular-nums ${
                                  isNeg ? 'text-[#d93025]' : 'text-gray-800'
                                }`}
                              >
                                {formatMult(v, row.suffix)}
                              </td>
                            );
                          })}
                          <td
                            title={highlight ? highlight.badgeText : undefined}
                            className={`py-2 px-3 text-right font-bold tabular-nums transition-colors ${ltmCellStyle}`}
                          >
                            {formattedLtm}
                          </td>
                          <td
                            className={`py-2 px-3 text-right tabular-nums ${
                              typeof row.avg_5y === 'number' && row.avg_5y < 0
                                ? 'text-[#d93025]'
                                : 'text-gray-700'
                            }`}
                          >
                            {formatMult(row.avg_5y, row.suffix)}
                          </td>
                          <td
                            className={`py-2 px-3 text-right tabular-nums font-medium ${
                              typeof row.med_5y === 'number' && row.med_5y < 0
                                ? 'text-[#d93025]'
                                : 'text-gray-800'
                            }`}
                          >
                            {formatMult(row.med_5y, row.suffix)}
                          </td>
                        </tr>
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* LEYENDA DEL SEMÁFORO DE MÚLTIPLOS */}
            <div className="px-4 py-2.5 bg-gray-50 border-t border-gray-200 flex flex-wrap items-center justify-between gap-3 text-[11px] text-gray-600">
              <div className="flex flex-wrap items-center gap-4">
                <span className="font-semibold text-gray-700">
                  Lectura Actual (LTM) vs. Mediana 5Y:
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-xs bg-emerald-100 border border-emerald-300 inline-block" />
                  <span>
                    <strong className="text-emerald-800">Más barato que su historia</strong> (múltiplo {'<'} Med. 5Y, o FCF Yield {'>'} Med. 5Y)
                  </span>
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-xs bg-amber-100 border border-amber-300 inline-block" />
                  <span>
                    <strong className="text-amber-900">En línea</strong> (±0,5% vs. Med. 5Y)
                  </span>
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-xs bg-red-100 border border-red-300 inline-block" />
                  <span>
                    <strong className="text-[#c5221f]">Más caro que su historia</strong> (múltiplo {'>'} Med. 5Y, o FCF Yield {'<'} Med. 5Y)
                  </span>
                </span>
              </div>
              <span className="text-gray-400">
                Se toma la Mediana 5Y como referencia por ser inmune a picos extremos.
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}