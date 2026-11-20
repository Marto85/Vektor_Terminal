export const METRICS_GLOSSARY = {
  // --- DATOS DE MERCADO Y ESTRUCTURA DE CAPITAL ---
  'Beta a 5 años': {
    title: 'Beta (Sensibilidad al Mercado - 5Y)',
    formula: 'Covarianza(Retorno Acción, Retorno S&P 500) ÷ Varianza(Retorno S&P 500)',
    explanation:
      'Mide cuánto oscila históricamente el precio de la acción frente a los movimientos del índice general de mercado.',
    evaluates:
      'El riesgo sistemático y la volatilidad relativa. Además, es el insumo clave en el modelo CAPM para calcular el Costo del Capital (Ke) exigido por el accionista.',
    benchmarks: [
      'Beta < 0,8: acciones defensivas (consumo básico, salud, utilities).',
      'Beta ~ 1,0: se mueve en línea con el mercado.',
      'Beta > 1,3: alta sensibilidad cíclica o tecnológica (amplifica subas y bajas).',
    ],
    example:
      'Con Beta 1,10, tasa libre de riesgo 4,25% y prima de mercado 5,0%, el Costo del Capital (Ke) exigido es 4,25% + (1,10 × 5,0%) = 9,75%.',
  },
  'Capitalización bursátil (MM)': {
    title: 'Capitalización Bursátil (Market Cap)',
    formula: 'Precio por acción × Acciones ordinarias en circulación',
    explanation:
      'Representa el valor de mercado del 100% del capital accionario (Equity) de la empresa según la cotización bursátil actual. No incluye deuda ni caja.',
    evaluates:
      'El tamaño de la compañía (Small, Mid, Large o Mega Cap) y cuánto cuesta comprar todas sus acciones en el mercado.',
    benchmarks: [
      'Mega Cap: > US$ 200.000 MM (líderes globales consolidados)',
      'Large Cap: US$ 10.000 MM – US$ 200.000 MM',
      'Mid Cap: US$ 2.000 MM – US$ 10.000 MM',
      'Small Cap: < US$ 2.000 MM (mayor volatilidad y potencial de crecimiento)',
    ],
    example:
      'Si una empresa tiene 300 MM de acciones y cotiza a US$ 32,60, su Market Cap es US$ 9.780 MM.',
  },
  'Valor empresarial (MM)': {
    title: 'Valor Empresa (Enterprise Value - EV)',
    formula: 'Capitalización Bursátil + Deuda Total − Efectivo e Inversiones a Corto Plazo',
    explanation:
      'Es el costo teórico de adquirir la totalidad del negocio operativo libre de deuda: pagás todas las acciones, cancelás las deudas y te quedás con la caja disponible.',
    evaluates:
      'La valoración real del negocio operativo independientemente de cómo esté financiado (mucho capital propio vs. mucha deuda). Es el numerador correcto para comparar contra Ventas, EBITDA o EBIT.',
    benchmarks: [
      'EV > Market Cap: la empresa tiene deuda neta (más deuda que efectivo).',
      'EV < Market Cap: la empresa tiene caja neta (más efectivo que deuda), lo que reduce el precio efectivo de compra.',
    ],
    example:
      'Market Cap de US$ 10.000 MM + Deuda de US$ 3.000 MM − Caja de US$ 1.000 MM = EV de US$ 12.000 MM.',
  },
  'Efectivo e Inversiones a Corto Plazo': {
    title: 'Efectivo, Equivalentes e Inversiones a Corto Plazo',
    formula: 'Efectivo y Equivalentes + Valores Negociables e Inversiones Líquidas (< 12 meses)',
    explanation:
      'Representa la liquidez inmediata del balance (caja en bancos, Letras del Tesoro y fondos de liquidez) disponible para afrontar obligaciones, financiar operaciones o recomprar acciones sin necesidad de emitir deuda.',
    evaluates:
      'El colchón financiero bruto de la compañía antes de restar sus pasivos financieros (deuda de corto y largo plazo).',
    benchmarks: [
      'Liquidez bruta > Deuda financiera total: posición de caja neta (máxima flexibilidad financiera).',
      'Conviene vigilar qué proporción está retenida en filiales extranjeras o restringida regulatoria/operativamente.',
    ],
    example:
      'US$ 21.843 MM en efectivo + US$ 55.000 MM en Letras del Tesoro a corto plazo = US$ 76.843 MM de liquidez disponible.',
  },
  'Deuda neta LTM (MM)': {
    title: 'Deuda Neta (Net Debt)',
    formula: 'Deuda Financiera Total (Corto + Largo Plazo) − Efectivo e Inversiones Líquidas',
    explanation:
      'Mide cuánta deuda quedaría pendiente si la empresa usara toda su caja disponible hoy mismo para cancelar pasivos financieros. Si aparece entre paréntesis (negativo), significa que tiene caja neta.',
    evaluates:
      'El apalancamiento real del balance y el riesgo financiero ante subas de tasas de interés o caídas de ventas.',
    benchmarks: [
      'Negativa (Caja neta): fortaleza financiera máxima (típico en Big Tech).',
      'Positiva moderada: manejable si está respaldada por flujo de caja recurrente.',
    ],
    example:
      'Deuda total de US$ 4.000 MM y caja por US$ 5.500 MM → Deuda neta de (US$ 1.500 MM), es decir, US$ 1.500 MM de caja neta.',
  },
  'Patrimonio Neto (Book Value)': {
    title: 'Patrimonio Neto Contable (Shareholders’ Equity)',
    formula: 'Total Activo − Total Pasivo (Capital Social + Resultados Acumulados ± Otros Resultados Integrales)',
    explanation:
      'Representa el valor contable residual que corresponde a los accionistas si se liquidaran todos los activos a su valor en libros y se cancelaran todos los pasivos.',
    evaluates:
      'La acumulación histórica de capital y utilidades retenidas. Su crecimiento sostenido refleja retención rentable de beneficios; caídas fuertes suelen deberse a recompras masivas de acciones o pérdidas acumuladas.',
    benchmarks: [
      'En bancos y aseguradoras es la base directa de capacidad de crecimiento y solvencia regulatoria.',
      'En empresas que recompran acciones agresivamente (ej. Apple o McDonald’s), el patrimonio contable puede ser bajo o incluso negativo sin implicar estrés financiero.',
    ],
    example:
      'Activos totales de US$ 600.000 MM − Pasivos totales de US$ 157.613 MM = Patrimonio Neto de US$ 442.387 MM.',
  },
  'Capital de Trabajo Neto (NWC)': {
    title: 'Capital de Trabajo Neto (Net Working Capital)',
    formula: 'Total Activo Corriente − Total Pasivo Corriente',
    explanation:
      'Mide el excedente (o déficit) en dólares de recursos de corto plazo (< 12 meses: caja, cuentas por cobrar e inventarios) respecto de las obligaciones exigibles en el mismo plazo (proveedores y deuda corriente).',
    evaluates:
      'La holgura operativa de corto plazo en términos absolutos. Se complementa con el Ratio de Liquidez Corriente (Activo Corriente ÷ Pasivo Corriente).',
    benchmarks: [
      'Positivo (Activo Corriente > Pasivo Corriente): colchón operativo cómodo para financiar el ciclo comercial.',
      'Negativo en negocios de cobro inmediato (retail masivo o suscripciones prepagas): puede ser estructuralmente sano si el flujo operativo (CFO) es alto y recurrente.',
    ],
    example:
      'Activo corriente de US$ 208.000 MM − Pasivo corriente de US$ 169.115 MM = Capital de Trabajo Neto de US$ 38.885 MM (liquidez corriente de 1,23x).',
  },
  'Deuda neta/EBITDA LTM': {
    title: 'Deuda Neta / EBITDA',
    formula: 'Deuda Neta ÷ EBITDA LTM (Beneficio Operativo + Depreciación y Amortización)',
    explanation:
      'Indica cuántos años de generación operativa bruta (EBITDA) necesitaría la empresa para pagar toda su deuda neta.',
    evaluates:
      'La solvencia y capacidad de repago. Es el ratio principal que miran bancos y calificadoras de riesgo.',
    benchmarks: [
      '< 0x (negativo): caja neta (sin riesgo de solvencia).',
      '0x – 1,5x: balance muy conservador.',
      '1,5x – 3,0x: apalancamiento estándar en empresas industriales o de consumo estables.',
      '> 3,5x – 4,0x: alerta de sobreendeudamiento (salvo utilities o infraestructura regulada).',
    ],
    example:
      'Deuda neta de US$ 6.000 MM y EBITDA anual de US$ 3.000 MM → 2,00x (tardaría 2 años de EBITDA en cancelar su deuda).',
  },

  // --- EFICIENCIA Y RENTABILIDAD ---
  'Margen bruto LTM': {
    title: 'Margen Bruto % (Gross Margin)',
    formula: '(Beneficio Bruto ÷ Ingresos Totales) × 100',
    explanation:
      'Porcentaje de cada dólar facturado que queda tras descontar los costos directos de producción, materias primas o servidores.',
    evaluates:
      'El poder de fijación de precios (pricing power) y la existencia de ventajas competitivas. Su expansión en el tiempo indica economías de escala.',
    benchmarks: [
      '> 60%: software, plataformas digitales, farmacia, lujo.',
      '30% – 55%: consumo masivo e industriales especializados.',
      '< 25%: retail, distribución, manufactura commodity.',
    ],
    example:
      'Ventas de US$ 1.000 MM y costo directo de US$ 320 MM → Margen Bruto de 68,0%.',
  },
  'Margen EBIT LTM': {
    title: 'Margen Operativo % (EBIT Margin)',
    formula: '(Beneficio Operativo ÷ Ingresos Totales) × 100',
    explanation:
      'Rentabilidad operativa pura después de cubrir costos directos, gastos administrativos, comerciales, I+D y depreciaciones.',
    evaluates:
      'La disciplina operativa y el apalancamiento operativo: si las ventas crecen y el margen EBIT sube, la empresa escala con eficiencia.',
    benchmarks: [
      '> 25%: liderazgo operativo sobresaliente.',
      '12% – 22%: rango saludable en industrias consolidadas.',
      '< 8%: márgenes estrechos sensibles a inflación de costos.',
    ],
    example:
      'EBIT de US$ 467 MM sobre ventas de US$ 1.000 MM → Margen EBIT de 46,7%.',
  },
  'Margen neto LTM': {
    title: 'Margen Neto % (Net Profit Margin)',
    formula: '(Beneficio Neto ÷ Ingresos Totales) × 100',
    explanation:
      'Porcentaje final de las ventas que se convierte en utilidad neta para el accionista tras pagar intereses e impuestos.',
    evaluates:
      'La rentabilidad final del negocio, aunque debe vigilarse que no esté inflada por ganancias financieras puntuales.',
    benchmarks: [
      '> 20%: altísima rentabilidad final.',
      '8% – 15%: promedio saludable en compañías consolidadas.',
    ],
    example:
      'Beneficio Neto de US$ 150 MM sobre ventas de US$ 1.000 MM → Margen Neto de 15,0%.',
  },
  'ROA LTM': {
    title: 'Rentabilidad sobre Activos (ROA %)',
    formula: '(Beneficio Neto ÷ Total Activo) × 100',
    explanation:
      'Mide cuánta ganancia neta genera la empresa por cada dólar de activos totales que administra en su balance.',
    evaluates:
      'La eficiencia en el uso de los activos. En bancos y aseguradoras es una métrica crítica porque operan con alto apalancamiento.',
    benchmarks: [
      'Bancos: > 1,0% – 1,3% es excelente (dada su estructura de activos).',
      'Empresas no financieras: > 8% – 10% indica buena eficiencia de activos.',
    ],
    example:
      'Un banco con US$ 4.000.000 MM en activos y US$ 52.000 MM de utilidad neta tiene un ROA de 1,30%.',
  },
  'ROE LTM': {
    title: 'Rentabilidad sobre Patrimonio Neto (ROE %)',
    formula: '(Beneficio Neto ÷ Patrimonio Neto) × 100',
    explanation:
      'Mide el retorno que obtiene el accionista sobre el capital propio invertido en la compañía.',
    evaluates:
      'Es la métrica central en bancos y financieras (donde se compara contra el Costo de Equity Ke). En empresas industriales debe analizarse junto al ROIC para verificar que no esté inflado por exceso de deuda.',
    benchmarks: [
      'Bancos de primera línea: 14% – 19% (crean valor si ROE > Ke ~9%–10%).',
      'Empresas no financieras de calidad: > 15% sostenido.',
    ],
    example:
      'Si un banco tiene Patrimonio Neto de US$ 300.000 MM y gana US$ 54.000 MM anuales, su ROE es 18,0%.',
  },
  'ROIC LTM': {
    title: 'Retorno sobre el Capital Invertido (ROIC %)',
    formula: 'NOPAT (EBIT × (1 − Tasa Impositiva)) ÷ (Patrimonio Neto + Deuda Neta)',
    explanation:
      'Mide cuánto retorna la operación sobre TODO el capital empleado (tanto de accionistas como de acreedores financieros), eliminando el efecto del apalancamiento.',
    evaluates:
      'La existencia de un foso económico (moat): si el ROIC supera consistentemente al WACC (ej. ROIC 22% vs WACC 9%), cada dólar reinvertido crea valor compuesto.',
    benchmarks: [
      '> 15% – 20%: negocio con fuertes ventajas competitivas.',
      '9% – 14%: retorno sólido por encima del costo de capital.',
      '< 8%: destruye valor si es inferior al WACC.',
    ],
    example:
      'NOPAT de US$ 250 MM sobre un capital invertido de US$ 1.000 MM → ROIC de 25,0%.',
  },

  // --- SALUD FINANCIERA, DUPONT Y CICLO DE CONVERSIÓN DE EFECTIVO (ETAPA 5) ---
  'Piotroski F-Score': {
    title: 'Piotroski F-Score (Calidad Fundamental 0–9)',
    formula: 'Suma de 9 pruebas binarias interanuales (Rentabilidad [4] + Liquidez/Deuda [3] + Eficiencia [2])',
    explanation:
      'Creado por el profesor Joseph Piotroski (2000) para evaluar si la situación financiera de una empresa mejora o se deteriora interanualmente.',
    evaluates:
      'APLICABILIDAD SECTORIAL: Diseñado para empresas NO FINANCIERAS (especialmente útil para filtrar acciones value baratas y evitar trampas de valor). En bancos y aseguradoras los criterios de liquidez corriente y rotación de activos no aplican contablemente.',
    benchmarks: [
      '7 a 9 puntos: Fortaleza financiera y mejora operativa sólida.',
      '4 a 6 puntos: Salud financiera neutra o en transición.',
      '0 a 3 puntos: Deterioro fundamental o riesgo de trampa de valor.',
    ],
    example:
      'Una empresa con ROA positivo, CFO > Beneficio Neto, menor deuda/activos y margen bruto creciente suma puntos hacia el rango 7–9.',
  },
  'Altman Z-Score': {
    title: 'Altman Z-Score y Z\'\'-Score (Estrés Financiero)',
    formula: 'Z = 1,2·X1 + 1,4·X2 + 3,3·X3 + 0,6·X4 + 1,0·X5  |  Z\'\' = 6,56·X1 + 3,26·X2 + 6,72·X3 + 1,05·X4',
    explanation:
      'Modelo discriminante desarrollado por Edward Altman (1968) para estimar la probabilidad de estrés financiero o insolvencia en un horizonte de 2 años.',
    evaluates:
      'APLICABILIDAD SECTORIAL: El Z-Score original es válido para empresas MANUFACTURERAS e INDUSTRIALES cotizantes. Para servicios, retail y tecnología asset-light se usa el Z\'\'-Score (sin rotación de activos X5). NO ES VÁLIDO para bancos, aseguradoras ni REITs.',
    benchmarks: [
      'Z Original (Manufactura): > 2,99 Zona Segura | 1,81–2,99 Zona Gris | < 1,81 Estrés.',
      'Z\'\'-Score (Servicios/Tech): > 2,60 Zona Segura | 1,10–2,60 Zona Gris | < 1,10 Estrés.',
    ],
    example:
      'Una compañía tecnológica con alta caja neta y sin deuda suele presentar un Z\'\'-Score superior a 6,0 (Zona Segura).',
  },
  'Descomposición DuPont': {
    title: 'Análisis DuPont del ROE (3 y 5 Factores)',
    formula: 'ROE = Margen Neto × Rotación de Activos × Apalancamiento Financiero (Activos / Patrimonio)',
    explanation:
      'Descompone el retorno sobre el patrimonio (ROE) en sus motores operativos y financieros para revelar cómo se genera la rentabilidad.',
    evaluates:
      'Si un ROE alto proviene de márgenes y eficiencia comercial genuina (alta calidad) o de un endeudamiento agresivo / baja tasa impositiva puntual.',
    benchmarks: [
      'Calidad superior: ROE impulsado por margen operativo y rotación con apalancamiento moderado (< 2,5x).',
      'Alerta: ROE elevado únicamente porque el multiplicador de patrimonio supera 5x–6x en empresas no financieras.',
    ],
    example:
      'Margen Neto 20% × Rotación 0,80x × Apalancamiento 1,50x = ROE del 24,0%.',
  },
  'Apalancamiento financiero (Activos / Patrimonio) (x)': {
    title: 'Multiplicador de Patrimonio (Apalancamiento DuPont)',
    formula: 'Total Activo ÷ Patrimonio Neto',
    explanation:
      'Mide cuántos dólares de activos controla la empresa por cada dólar de capital propio de los accionistas.',
    evaluates:
      'El tercer factor de la identidad DuPont. Cuanto más alto es, mayor es el uso de pasivos para financiar activos.',
    benchmarks: [
      '1,3x – 2,2x: estructura patrimonial conservadora en empresas no financieras.',
      '8x – 12x: normal únicamente en bancos comerciales regulados.',
    ],
    example: 'Activos totales de US$ 300 MM y Patrimonio Neto de US$ 150 MM → 2,00x.',
  },
  'Días de cobro (DSO)': {
    title: 'Días de Cobro a Clientes (DSO - Days Sales Outstanding)',
    formula: '(Cuentas por Cobrar Promedio ÷ Ingresos Totales) × 365',
    explanation:
      'Cantidad promedio de días que tarda la empresa en cobrar en efectivo una venta realizada a crédito.',
    evaluates:
      'La eficiencia de cobranza y el poder de negociación frente a clientes. Un aumento brusco puede indicar relajación comercial para sostener ventas.',
    benchmarks: [
      '< 30 – 45 días: cobranza ágil.',
      '> 75 – 90 días: ciclo largo de cobro (revisar calidad de cartera).',
    ],
    example: 'Cuentas por cobrar promedio de US$ 100 MM y ventas de US$ 730 MM → DSO de 50 días.',
  },
  'Días de inventario (DIO)': {
    title: 'Días de Inventario (DIO - Days Inventory Outstanding)',
    formula: '(Inventario Promedio ÷ Coste de los Bienes Vendidos) × 365',
    explanation:
      'Cantidad promedio de días que la mercadería permanece almacenada antes de venderse.',
    evaluates:
      'APLICABILIDAD: Relevante en retail, manufactura y hardware. En empresas de software puro o servicios sin stock físico vale 0 días.',
    benchmarks: [
      'Menor DIO indica mayor rotación de stock y menor riesgo de obsolescencia.',
    ],
    example: 'Inventario promedio de US$ 80 MM y costo de ventas de US$ 584 MM → DIO de 50 días.',
  },
  'Días de pago (DPO)': {
    title: 'Días de Pago a Proveedores (DPO - Days Payable Outstanding)',
    formula: '(Cuentas por Pagar Promedio ÷ Coste de los Bienes Vendidos) × 365',
    explanation:
      'Cantidad promedio de días que tarda la empresa en pagar sus facturas a proveedores.',
    evaluates:
      'El poder de negociación con la cadena de suministro: pagar más tarde financia el capital de trabajo sin costo financiero explícito.',
    benchmarks: [
      '45 – 90 días: habitual en cadenas comerciales e industriales con escala.',
    ],
    example: 'Cuentas por pagar promedio de US$ 96 MM y costo de ventas de US$ 584 MM → DPO de 60 días.',
  },
  'Ciclo de conversión de efectivo (CCC) días': {
    title: 'Ciclo de Conversión de Efectivo (CCC)',
    formula: 'DSO (Días de cobro) + DIO (Días de inventario) − DPO (Días de pago)',
    explanation:
      'Mide cuántos días transcurren desde que la empresa paga a sus proveedores hasta que cobra la venta final de sus clientes.',
    evaluates:
      'La eficiencia del capital de trabajo. Si es negativo (ej. -15 días), la empresa cobra antes de pagar a proveedores y se financia con su propio giro comercial.',
    benchmarks: [
      '< 0 días (negativo): ventaja competitiva de caja (típico en retail líder o suscripciones prepagas).',
      '15 – 60 días: ciclo operativo estándar.',
      '> 90 días: exige inmovilizar mucho capital de trabajo para crecer.',
    ],
    example: 'DSO 30 días + DIO 25 días − DPO 65 días = CCC de -10 días.',
  },

  // --- MÚLTIPLOS DE VALORACIÓN ---
  'EV / Ventas (LTM)': {
    title: 'EV / Ventas (EV / Sales)',
    formula: 'Valor Empresa (EV) ÷ Ingresos Totales últimos 12 meses',
    explanation:
      'El EV (Valor Empresa = Market Cap + Deuda − Caja) dividido por la facturación anual. Mide cuánto paga el mercado por cada dólar de ventas generado por el negocio operativo.',
    evaluates:
      'La valoración relativa de empresas que aún no tienen beneficios netos positivos o cuyos márgenes están temporalmente comprimidos por inversión.',
    benchmarks: [
      'Empresas maduras / industriales / retail: 0,5x – 2,5x (márgenes netos bajos).',
      'Empresas de consumo masivo / salud consolidadas: 2,5x – 5,0x.',
      'Software / SaaS / Tecnología de altos márgenes (>70% margen bruto): 6,0x – 15,0x.',
      'Hipercrecimiento especulativo: > 15,0x (exige crecimiento >25% anual sostenido).',
    ],
    example:
      'Con un EV de US$ 3.960.000 MM y ventas LTM de US$ 346.400 MM, el EV/Ventas es 11,43x.',
  },
  'EV / Ingresos NTM': {
    title: 'EV / Ingresos NTM (Forward EV/Sales)',
    formula: 'Valor Empresa (EV) ÷ Ingresos Estimados próximos 12 meses (NTM)',
    explanation:
      'Compara el Valor Empresa actual contra las ventas proyectadas para los próximos 12 meses (Next Twelve Months).',
    evaluates:
      'Qué tan rápido el crecimiento esperado de ventas abarata el múltiplo actual.',
    benchmarks: [
      'Si EV/Ingresos NTM es significativamente menor al LTM, el mercado descuenta fuerte expansión comercial.',
      'Tech / Cloud en crecimiento: 5,0x – 12,0x.',
    ],
    example:
      'Si EV/Ventas LTM es 11,43x y se espera que las ventas crezcan 18% el próximo año, el EV/Ingresos NTM baja a ~9,6x.',
  },
  'EV / EBITDA (LTM)': {
    title: 'EV / EBITDA',
    formula: 'Valor Empresa (EV) ÷ (Beneficio Operativo + Depreciación y Amortización)',
    explanation:
      'El EV (Valor Empresa) dividido por el flujo operativo antes de impuestos, intereses y amortizaciones contables (EBITDA).',
    evaluates:
      'El múltiplo estándar institucional para comparar empresas de un mismo sector con distinta estructura de deuda o política fiscal.',
    benchmarks: [
      'Empresas maduras / cíclicas / manufactura: 6x – 10x.',
      'Empresas estables de calidad (Consumo, Salud, Industriales líderes): 11x – 16x.',
      'Tecnología consolidada / plataformas digitales: 16x – 25x.',
      '> 30x: valoración exigente que requiere alta conversión a caja y crecimiento sostenido.',
    ],
    example:
      'Un negocio con EV de US$ 1.500 MM y EBITDA de US$ 100 MM cotiza a 15,00x EV/EBITDA.',
  },
  'EV / EBIT (LTM)': {
    title: 'EV / EBIT',
    formula: 'Valor Empresa (EV) ÷ Beneficio Operativo (EBIT)',
    explanation:
      'A diferencia del EV/EBITDA, aquí NO se suma la Depreciación y Amortización. Toma la ganancia operativa real después del desgaste de activos fijos.',
    evaluates:
      'Más exigente y realista que EV/EBITDA en negocios intensivos en capital (fábricas, telecomunicaciones, nube/data centers) donde reponer equipos es un costo real recurrente.',
    benchmarks: [
      'Empresas estables / industriales: 9x – 14x.',
      'Compañías de alta calidad con ventajas competitivas: 15x – 22x.',
      'Tech / Software líder: 20x – 28x.',
    ],
    example:
      'Dos empresas tienen EV/EBITDA de 10x, pero la que necesita mucha maquinaria tiene un EV/EBIT de 18x.',
  },
  'EV / Beneficio Bruto (LTM)': {
    title: 'EV / Beneficio Bruto (EV / Gross Profit)',
    formula: 'Valor Empresa (EV) ÷ (Ingresos Totales − Coste de los Bienes Vendidos)',
    explanation:
      'Relaciona el Valor Empresa con la ganancia que queda tras cubrir únicamente el costo directo de producir o prestar el servicio.',
    evaluates:
      'Permite comparar empresas de software o plataformas que reinvierten agresivamente en I+D y marketing (debajo de la línea bruta).',
    benchmarks: [
      'Retail / Industrial tradicional: 3x – 7x.',
      'Software / SaaS consolidado: 10x – 18x.',
    ],
    example:
      'Una SaaS con margen bruto del 80% y EV/Ventas de 12x tiene un EV/Beneficio Bruto de 15,0x.',
  },
  'EV / Flujo de Caja Libre (Unlevered)': {
    title: 'EV / Flujo de Caja Libre (EV / FCF)',
    formula: 'Valor Empresa (EV) ÷ Flujo de Caja Libre (CFO − CapEx)',
    explanation:
      'Mide cuántos años de caja libre disponible (después de pagar inversiones en bienes de capital) equivalen al Valor Empresa total.',
    evaluates:
      'La capacidad real de generar efectivo contante. Ojo: si la empresa está en un ciclo excepcional de expansión de CapEx, este múltiplo se dispara artificialmente.',
    benchmarks: [
      'Empresas maduras de bajo CapEx: 12x – 18x.',
      'Compañías de calidad compuesta: 18x – 28x.',
      '> 40x: suele indicar expectativas muy altas o un pico transitorio de inversión (CapEx).',
    ],
    example:
      'Si el EV es US$ 2.000 MM y el FCF anual es US$ 100 MM, el múltiplo es 20,00x.',
  },
  'Precio / Ventas (P/S)': {
    title: 'Precio / Ventas (Price to Sales)',
    formula: 'Capitalización Bursátil ÷ Ingresos Totales',
    explanation:
      'Similar a EV/Ventas, pero usa solo el valor de las acciones (Market Cap) sin sumar deuda ni restar caja.',
    evaluates:
      'Valoración relativa sobre ingresos desde la óptica del accionista. Conviene acompañarlo con EV/Ventas si la empresa tiene mucha deuda.',
    benchmarks: [
      'Negocios de margen bajo (supermercados, autos): 0,3x – 1,2x.',
      'Empresas estables de buen margen: 2,0x – 4,5x.',
      'Tecnología / Software: 5,0x – 12,0x.',
    ],
    example:
      'Market Cap de US$ 500 MM y ventas de US$ 250 MM → P/S de 2,00x.',
  },
  'Precio / Beneficio (P/E)': {
    title: 'Precio / Beneficio (PER o P/E Ratio)',
    formula: 'Precio por Acción ÷ Beneficio por Acción Diluido (BPA) — o Market Cap ÷ Beneficio Neto',
    explanation:
      'Indica cuántos años de ganancias netas actuales está pagando el mercado por cada acción.',
    evaluates:
      'El múltiplo más difundido en bolsa. Puede distorsionarse si hubo ganancias o pérdidas extraordinarias no recurrentes.',
    benchmarks: [
      'Empresas cíclicas / bancos / maduras de bajo crecimiento: 8x – 14x.',
      'Promedio histórico S&P 500 / empresas estables de calidad: 15x – 22x.',
      'Crecimiento tecnológico consolidado: 22x – 35x.',
      '> 40x: descuenta fuerte expansión futura de beneficios.',
    ],
    example:
      'Acción a US$ 100 con ganancia neta de US$ 5 por acción → P/E de 20,00x (rendimiento inicial de ganancias del 5% anual).',
  },
  'NTM Price / Earnings (P/E)': {
    title: 'P/E Futuro (Forward P/E NTM)',
    formula: 'Precio Actual ÷ Beneficio por Acción Estimado próximos 12 meses',
    explanation:
      'Mide el precio de hoy frente a las ganancias proyectadas por el consenso de analistas para los próximos 4 trimestres.',
    evaluates:
      'Si el P/E futuro es bastante más bajo que el P/E LTM, se espera aceleración de márgenes o crecimiento de utilidades.',
    benchmarks: [
      'Value / Estables / Bancos: 9x – 15x.',
      'Growth / Tech líder: 18x – 28x.',
    ],
    example:
      'Precio US$ 523,88 y BPA estimado NTM de US$ 24,20 → Forward P/E de 21,65x.',
  },
  'Precio / Valor Libros (P/BV)': {
    title: 'Precio / Valor Contable (Price to Book)',
    formula: 'Capitalización Bursátil ÷ Patrimonio Neto Contable',
    explanation:
      'Compara el valor de mercado de las acciones contra el valor neto en libros (Activos Totales − Pasivos Totales).',
    evaluates:
      'Muy relevante en bancos, aseguradoras e inmobiliarias donde los activos valen cerca de su registro contable.',
    benchmarks: [
      '< 1,0x: cotiza por debajo de su valor contable líquido.',
      'Bancos / Industriales: 1,0x – 2,5x (bancos con ROE > 15% suelen cotizar a 1,8x–2,5x).',
      'Empresas de alto ROE con pocos activos físicos (Tech/Consumo): 5,0x – 15,0x.',
    ],
    example:
      'Patrimonio neto de US$ 1.000 MM y Market Cap de US$ 1.800 MM → P/BV de 1,80x.',
  },
  'Precio / Valor Contable Tangible (P/TBV)': {
    title: 'Precio / Valor Contable Tangible (P/TBV)',
    formula: 'Capitalización Bursátil ÷ (Patrimonio Neto − Fondo de Comercio − Activos Intangibles)',
    explanation:
      'Excluye el Goodwill (sobreprecio pagado en adquisiciones pasadas) y los intangibles para medir el respaldo físico y financiero neto.',
    evaluates:
      'Métrica de referencia en banca y seguros para medir la valoración sobre el capital tangible real.',
    benchmarks: [
      'Bancos comerciales sólidos: 1,4x – 2,8x.',
      'Empresas con fuerte historial de adquisiciones (M&A): suele ser bastante mayor al P/BV.',
    ],
    example:
      'Patrimonio de US$ 1.000 MM menos US$ 400 MM de Goodwill = US$ 600 MM tangibles. Con Market Cap de US$ 1.800 MM → P/TBV de 3,00x.',
  },
  'Precio / Flujo de Caja Libre (P/FCF)': {
    title: 'Precio / Flujo de Caja Libre (P/FCF)',
    formula: 'Capitalización Bursátil ÷ Flujo de Caja Libre (FCF)',
    explanation:
      'Compara el valor de mercado de las acciones contra la caja real que queda libre para repartir dividendos, recomprar acciones o reducir deuda.',
    evaluates:
      'La calidad de las ganancias: una empresa con P/E bajo pero P/FCF muy alto tiene problemas para convertir utilidad contable en dinero real.',
    benchmarks: [
      'Empresas maduras generadoras de caja: 12x – 18x.',
      'Empresas de calidad compuesta: 18x – 26x.',
      '> 35x: cara respecto a la caja actual o atravesando un ciclo fuerte de inversión (CapEx).',
    ],
    example:
      'Market Cap de US$ 2.000 MM y FCF de US$ 100 MM → P/FCF de 20,00x.',
  },
  'FCF Yield %': {
    title: 'Rendimiento de Flujo de Caja Libre (FCF Yield)',
    formula: '(Flujo de Caja Libre ÷ Capitalización Bursátil) × 100',
    explanation:
      'Es la inversa del P/FCF expresada en porcentaje. Muestra qué tasa de retorno en efectivo genera la empresa sobre su precio bursátil hoy.',
    evaluates:
      'Permite comparar directamente el atractivo de una acción frente a la tasa de un bono del Tesoro (ej. 4%–4,5%).',
    benchmarks: [
      '> 6% – 8%: generación de caja muy atractiva.',
      '3,5% – 5,5%: rango equilibrado para empresas de calidad.',
      '< 2,5%: exigente; exige fuerte crecimiento futuro del FCF.',
    ],
    example:
      'Con un FCF de US$ 100 MM y un Market Cap de US$ 2.000 MM, el FCF Yield es 5,00% anual.',
  },

  // --- PARÁMETROS DEL DCF Y MODELO BANCARIO ---
  'Ajuste puntual FCF (+/- MM)': {
    title: 'Ajuste Puntual al Flujo de Caja Libre (DCF)',
    formula: 'FCF Proyectado Ajustado = FCF Operativo del Modelo ± Ajuste Manual (en millones)',
    explanation:
      'Permite sumar (+) o restar (−) un monto fijo anual en millones de dólares para corregir distorsiones económicas que los estados contables estándar no aíslan por sí solos.',
    evaluates:
      'La sensibilidad del Valor Intrínseco cuando detectás partidas no recurrentes o costos económicos ocultos en las notas del balance.',
    benchmarks: [
      'Caso 1 — Compensación basada en acciones (SBC): ingresar monto NEGATIVO (ej. -8000) para exigir que el FCF cubra la recompra de acciones emitidas a empleados.',
      'Caso 2 — Beneficio operativo extraordinario en el año base (ej. cobro único por litigio o subsidio dentro del EBIT): ingresar monto NEGATIVO (ej. -1500) para no proyectarlo a perpetuidad.',
      'Caso 3 — Ahorros de costos ya ejecutados o sinergias confirmadas que aún no figuran en el último 10-K: ingresar monto POSITIVO (ej. +1200).',
      'Caso 4 — Empresa sin distorsiones relevantes: dejar en 0.',
    ],
    example:
      'Si una tecnológica reporta US$ 50.000 MM de FCF pero entrega US$ 10.000 MM anuales en acciones a empleados (SBC), ingresás -10000 para calcular su valor intrínseco real libre de dilución.',
  },
  'Excess Return Model (Bancos)': {
    title: 'Modelo de Retorno Excedente (Excess Return)',
    formula: 'Valor Intrínseco = Valor Libros Actual + VP(Retornos Excedentes sobre Ke)',
    explanation:
      'En bancos y financieras, la deuda es materia prima operativa y no existe un FCF industrial tradicional. Este modelo valúa el patrimonio actual más el valor presente de la rentabilidad que el banco logra por encima del costo exigido por sus accionistas (ROE − Ke).',
    evaluates:
      'Si el banco crea o destruye valor patrimonial: cuando ROE > Ke, merece cotizar por encima de 1,0x Valor Libros (P/BV > 1).',
    benchmarks: [
      'ROE > Ke en +4% a +8%: franquicia bancaria de alta calidad (P/BV justo entre 1,5x y 2,4x).',
      'ROE ≈ Ke: valoración justa cercana a 1,0x Valor Libros.',
      'ROE < Ke: destruye valor económico (debería cotizar con descuento sobre libros, P/BV < 1).',
    ],
    example:
      'Un banco con Valor Libros de US$ 110/acción, ROE del 16% y Costo de Equity (Ke) del 9,5% genera un exceso de 6,5% anual sobre su capital, justificando un valor intrínseco cercano a US$ 190–210/acción.',
  },

  // --- RUBROS CONTABLES Y RATIOS (PESTAÑA FINANZAS) ---
  'Ingresos Totales': {
    title: 'Ingresos Totales (Revenue / Top Line)',
    formula: 'Ventas netas de bienes y servicios (descontando devoluciones y bonificaciones)',
    explanation:
      'La facturación bruta operativa del período antes de restar cualquier costo o gasto.',
    evaluates:
      'La demanda real de los productos/servicios y la expansión de cuota de mercado.',
    benchmarks: [
      'Empresas maduras: crecimiento orgánico de 3% – 7% anual.',
      'Empresas de crecimiento: > 12% – 15% anual.',
    ],
    example: 'Ventas de licencias + suscripciones nube durante el ejercicio fiscal.',
  },
  'Beneficio Bruto': {
    title: 'Beneficio Bruto (Gross Profit)',
    formula: 'Ingresos Totales − Coste de los bienes vendidos (COGS)',
    explanation:
      'Lo que queda de las ventas tras pagar los costos directos de producción, materias primas o servidores.',
    evaluates:
      'El poder de fijación de precios (pricing power) y la eficiencia productiva básica.',
    benchmarks: [
      'Margen bruto > 60%: software, farmacia, marcas de lujo.',
      'Margen bruto 30% – 50%: consumo masivo e industriales especializados.',
      'Margen bruto < 25%: retail, aerolíneas, manufactura commodity.',
    ],
    example: 'Ventas de US$ 1.000 MM − Costo directo de US$ 350 MM = Beneficio Bruto de US$ 650 MM (65% margen bruto).',
  },
  'Beneficio Operativo': {
    title: 'Beneficio Operativo (EBIT)',
    formula: 'Beneficio Bruto − Gastos Operativos (SG&A, I+D, Depreciación y Amortización)',
    explanation:
      'La ganancia generada estrictamente por el negocio principal antes de intereses financieros e impuestos.',
    evaluates:
      'La rentabilidad real de la operación cotidiana, limpia de cómo se financia la empresa o de resultados extraordinarios financieros.',
    benchmarks: [
      'Margen operativo > 25%: negocios altamente rentables con apalancamiento operativo.',
      'Margen operativo 10% – 20%: rango saludable en industrias estándar.',
    ],
    example: 'Beneficio Bruto de US$ 650 MM − US$ 300 MM de gastos comerciales e I+D = EBIT de US$ 350 MM.',
  },
  'Efectivo de Operaciones (CFO)': {
    title: 'Flujo de Caja Operativo (CFO)',
    formula: 'Beneficio Neto + Partidas no monetarias (D&A, SBC) ± Cambios en Capital de Trabajo',
    explanation:
      'El dinero efectivo real que entró o salió de la caja por la actividad comercial habitual.',
    evaluates:
      'Si las ganancias contables se transforman efectivamente en dinero líquido. Un CFO consistentemente inferior al Beneficio Neto es señal de alerta.',
    benchmarks: [
      'Conversión CFO / Beneficio Neto ≥ 1,0x indica alta calidad contable.',
    ],
    example: 'Una empresa gana US$ 100 MM contables, suma US$ 30 MM de depreciación y cobra clientes pendientes por US$ 10 MM → CFO = US$ 140 MM.',
  },
  'Gastos de capital (CapEx)': {
    title: 'Gastos de Capital (CapEx)',
    formula: 'Inversiones en propiedades, planta, maquinaria, centros de datos y equipamiento',
    explanation:
      'Dinero destinado a mantener o expandir la capacidad física y tecnológica de largo plazo de la empresa.',
    evaluates:
      'Cuánto efectivo exige el negocio solo para seguir operando (CapEx de mantenimiento) frente a cuánto destina a crecer (CapEx de expansión).',
    benchmarks: [
      'Asset-light (bajo CapEx): < 5% de las ventas.',
      'Intensivas en capital (energía, telecom, hyperscalers IA): 15% – 35% de las ventas.',
    ],
    example: 'Construcción de nuevos centros de datos o compra de maquinaria industrial.',
  },
  'Flujo de caja libre (FCF)': {
    title: 'Flujo de Caja Libre (Free Cash Flow - FCF)',
    formula: 'Efectivo de Operaciones (CFO) − Gastos de Capital (CapEx)',
    explanation:
      'El efectivo disponible que le sobra a la empresa después de pagar todos sus gastos operativos e inversiones en bienes de capital.',
    evaluates:
      'La métrica reina en valoración fundamental: con este dinero se pagan dividendos, se recompran acciones, se cancela deuda o se financian adquisiciones.',
    benchmarks: [
      'Margen FCF (FCF / Ventas) > 15%: máquina de generar efectivo.',
      'Margen FCF 5% – 12%: sólido en negocios industriales o comerciales.',
    ],
    example: 'CFO de US$ 180 MM − CapEx de US$ 50 MM = FCF de US$ 130 MM.',
  },
  'Conversión de FCF (FCF / Beneficio Neto)': {
    title: 'Ratio de Conversión de Caja (FCF / Beneficio Neto)',
    formula: '(Flujo de Caja Libre ÷ Beneficio Neto) × 100',
    explanation:
      'Mide qué porcentaje de la ganancia neta contable termina convirtiéndose efectivamente en Flujo de Caja Libre disponible para el accionista.',
    evaluates:
      'La calidad real de los beneficios y la intensidad de capital: si una empresa reporta ganancias altas pero su conversión es baja (<50%), gran parte de la utilidad queda inmovilizada en CapEx o capital de trabajo.',
    benchmarks: [
      '> 90% – 100%: conversión excelente (típica de negocios asset-light y suscripciones).',
      '60% – 90%: conversión saludable en compañías industriales o en crecimiento moderado.',
      '< 50%: alta reinversión en CapEx de expansión o acumulación de cuentas por cobrar/inventarios.',
    ],
    example:
      'Si el Beneficio Neto es US$ 133.749 MM y el FCF es US$ 66.987 MM, la conversión es del 50% (el resto financia expansión de infraestructura).',
  },
  'Ratio de liquidez (x)': {
    title: 'Ratio de Liquidez Corriente (Current Ratio)',
    formula: 'Total Activo Corriente ÷ Total Pasivo Corriente',
    explanation:
      'Mide la capacidad de la empresa para cubrir sus obligaciones de corto plazo (< 12 meses) con sus activos líquidos o convertibles en efectivo en el corto plazo.',
    evaluates:
      'La holgura financiera operativa en el corto plazo.',
    benchmarks: [
      '1,2x – 2,5x: liquidez saludable.',
      '< 1,0x: los pasivos de corto plazo superan a los activos corrientes (vigilar flujo de caja).',
    ],
    example: 'Activo corriente de US$ 180 MM y pasivo corriente de US$ 100 MM → 1,80x.',
  },
  'EBIT / Gastos por intereses (x)': {
    title: 'Cobertura de Intereses (Interest Coverage)',
    formula: 'Beneficio Operativo (EBIT) ÷ Gastos por Intereses',
    explanation:
      'Indica cuántas veces las ganancias operativas cubren el pago anual de intereses de la deuda.',
    evaluates:
      'El margen de seguridad frente al costo financiero de la deuda.',
    benchmarks: [
      '> 8x – 10x: cobertura holgada de grado de inversión.',
      '3x – 6x: cobertura aceptable.',
      '< 2x: riesgo financiero elevado.',
    ],
    example: 'EBIT de US$ 500 MM e intereses anuales de US$ 50 MM → cobertura de 10,00x.',
  },

  // MODELOS DE VALUACION
  'Perpetuidad de Gordon (Valor Terminal)': {
    title: 'Valor Terminal por Perpetuidad de Gordon (g)',
    formula: 'Valor Terminal = FCF Estacionario Año 6 ÷ (WACC − g)',
    explanation:
      'Calcula cuánto vale la empresa desde el año 6 en adelante asumiendo que la conservás para siempre y su flujo de caja libre crece a una tasa perpetua moderada (g, típicamente 2,5% a 3,5%, alineada con el crecimiento nominal de la economía).',
    evaluates:
      'El valor intrínseco puro sin depender de qué múltiplos pague el mercado en el futuro. Es el método preferido por inversores de largo plazo (buy & hold).',
    benchmarks: [
      'Cuándo priorizarlo: en empresas maduras, estables o cuando querés un margen de seguridad conservador frente a una posible contracción de múltiplos bursátiles.',
      'Precaución: en empresas tecnológicas o de alto crecimiento que seguirán creciendo por encima del PIB después del año 5, suele arrojar un valor conservador.',
    ],
    example:
      'Si el FCF estacionario es US$ 10.000 MM, WACC = 9% y g = 3%, el Valor Terminal al año 5 es 10.000 ÷ (0,09 − 0,03) = US$ 166.667 MM.',
  },
  'Múltiplo de Salida (Valor Terminal)': {
    title: 'Valor Terminal por Múltiplo de Salida (Exit Multiple)',
    formula: 'Valor Terminal = FCF Normalizado Año 5 × Múltiplo EV/FCF de Salida',
    explanation:
      'Estima el valor de la empresa al final del año 5 suponiendo que se vende a un múltiplo de mercado razonable basado en su historial o en sus comparables sectoriales.',
    evaluates:
      'Combina los flujos proyectados de los primeros 5 años con la valoración relativa que el mercado suele asignar a negocios de esa calidad.',
    benchmarks: [
      'Cuándo priorizarlo: en compañías líderes con fuertes ventajas competitivas (moat) o alto crecimiento donde asumir g = 3% al año 6 subestima su capacidad de reinversión.',
      'Precaución: si usás un múltiplo de salida demasiado alto (ej. de burbuja), el resultado deja de ser intrínseco y refleja euforia de mercado.',
    ],
    example:
      'Con un FCF normalizado en el año 5 de US$ 10.000 MM y un múltiplo de salida de 20x, el Valor Terminal al año 5 es US$ 200.000 MM.',
  },
};

export function getGlossaryEntry(metricName) {
  if (!metricName) return null;
  if (METRICS_GLOSSARY[metricName]) return METRICS_GLOSSARY[metricName];

  const clean = metricName.replace(/\s*\(LTM\)|\s*\(MM\)/gi, '').trim();
  const matchedKey = Object.keys(METRICS_GLOSSARY).find(
    (k) => k.toLowerCase().startsWith(clean.toLowerCase())
  );
  return matchedKey ? METRICS_GLOSSARY[matchedKey] : null;
}