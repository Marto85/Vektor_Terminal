# Manual de Usuario — VektorTerminal

## 1. Descripción General
**VektorTerminal** es una plataforma de investigación fundamental, análisis técnico interactivo, valoración de acciones globales y ADRs, y gestión de carteras de inversión. Integra estados contables oficiales de la SEC (EDGAR), series macroeconómicas, estimaciones de consenso y cotizaciones de mercado en una interfaz unificada con autenticación multi-usuario y persistencia local.

---

## 2. Acceso, Registro y Gestión de Cuenta

### Inicio de Sesión
- Podés ingresar escribiendo tu **nombre de usuario** o tu **correo electrónico** junto con tu contraseña.
- También podés acceder con un clic mediante tu cuenta de **Google** o **GitHub** (cuando estén habilitados en la configuración del servidor).

### Crear Cuenta (Registro Público)
- Desde la pestaña **Crear cuenta** en la pantalla de acceso podés registrar un usuario nuevo completando un **nombre de usuario único** (3 a 32 caracteres en minúsculas, números, punto o guion bajo), tu **nombre completo**, un **correo electrónico** y una **contraseña** de al menos 8 caracteres.
- Las cuentas creadas por registro público ingresan automáticamente con el perfil **Cliente (`client`)**.

### Recuperar Usuario y Contraseña
1. Hacé clic en **¿Olvidaste tu usuario o clave?** en la pantalla de ingreso.
2. Ingresá el correo electrónico asociado a tu cuenta para recibir un recordatorio con tu nombre de usuario registrado y un código temporal válido por **15 minutos**.
3. Pegá el código recibido (o abrí directamente el enlace de recuperación) y definí una nueva contraseña para ingresar de inmediato.

### Roles y Administración de Usuarios
- **`client` (Cliente):** acceso completo a investigación fundamental, watchlists, comparador, screener y consulta de su cartera asignada.
- **`advisor` (Asesor):** acceso a las herramientas de análisis más el módulo **Carteras & CRM** para gestionar legajos de clientes y registrar operaciones.
- **`superadmin` (Administrador):** acceso total al sistema y al panel **Usuarios** en la cabecera superior para crear cuentas internas, asignar roles y vincular clientes con asesores.

---

## 3. Búsqueda y Cabecera Global
1. En la barra superior, escribí el **Ticker** o el nombre de la empresa (ej. `MSFT`, `AAPL`, `MELI`, `JPM`, `YPF`) y seleccioná una sugerencia del desplegable o presioná **Enter**.
2. La cabecera muestra la cotización actual en USD, la variación diaria y los botones de acción rápida:
  - **Agregar al tablero / En tu tablero:** guarda el emisor en una watchlist con objetivos de compra/venta y alertas.
  - **Mostrar / Ocultar gráfico:** despliega u oculta el panel superior con el gráfico interactivo y el resumen de métricas clave.
  - **Excel (.xlsx):** descarga un libro Excel multi-solapa (7 hojas: *Resumen & Múltiplos*, *Resultados*, *Balance*, *Flujo de Efectivo*, *Ratios*, *Valoración* y *Propiedad e Insiders*) respetando la periodicidad activa (*Anual* o *Trimestral*).
  - **Informe PDF:** genera y descarga un reporte ejecutivo vectorial en formato `.pdf` con tarjetas KPI, salud financiera, evolución contable anual, múltiplos históricos, expectativas implícitas y tenedores institucionales/insiders.
3. **Glosario interactivo (`i`):** en cualquier tabla o panel donde aparezca el ícono de información junto a una métrica, hacé clic para abrir el panel lateral con su definición, fórmula, criterios de interpretación y rangos de referencia.

### Gráfico Interactivo, Análisis Técnico y Panel de Estructura de Capital
- **Selector de métrica:** permite alternar entre *Price*, *% Change*, *Total Return* (con dividendos reinvertidos), *Drawdowns*, *10k Growth*, *Market Cap* y *Enterprise Value*, en rangos de `3m` a `max` y temporalidades de velas `15m`, `1h`, `1D` y `1 Sem`, más vista en pantalla completa.
- **Indicadores Técnicos (`Indicadores`):** permite activar o limpiar con un clic medias móviles (`SMA 20`, `SMA 50`, `SMA 200`, `EMA 12`, `EMA 26`), `Bandas de Bollinger (20, 2)`, `Media Vol (20)` y sub-paneles inferiores de osciladores (`RSI 14`, `MACD 12/26/9`, `ATR 14`, `OBV`).
- **Enfoque AT (Diagnóstico Automático con Validación de Volumen):** selector de lente metodológica que traza niveles sobre el gráfico y despliega una ficha diagnóstica validada por volumen relativo (`RVOL`) y flujo `OBV`:
  - *Tendencia y Medias:* canal envolvente de regresión lineal y auditoría de alineación o cruces `SMA 20/50/200`.
  - *Chartismo (S/R y Figuras):* clústeres automáticos de soportes y resistencias (`S1/S2`, `R1/R2`), detección de dobles techos/pisos o triángulos y confirmación de rupturas por volumen.
  - *Elliott + Fibonacci:* validación de reglas cardinales de impulso (`1-2-3-4-5`) o reclasificación correctiva (`A-B-C` / `W-X-Y`), retrocesos direccionales (`38.2%`, `50.0%`, `61.8%`) y comparación de volumen por onda.
  - *Momentum y Volatilidad:* detección de divergencias RSI/OBV en zonas extremas, compresión de volatilidad (*Bollinger Squeeze*) y niveles dinámicos `Stop 2x ATR` y `Objetivo 3x ATR`.
- **Panel derecho:** resume *Datos de mercado*, *Estructura de capital*, *Eficiencia*, *Crecimiento y flujo* (incluyendo **FCF LTM** auditado) y *Valoración*.

---

## 4. Navegación por Módulos (Barra Lateral)

### A. Panorama de Mercado y Macro Lab
- **Panorama de Mercado:** resume el desempeño diario y valuación (`P/E Trailing`, `P/E Forward`, *Earnings Yield* y *Dividend Yield*) de los principales índices globales (`S&P 500`, `Nasdaq 100`, `Dow Jones`, `Russell 2000`, `EWZ`, `EEM`), guardando instantáneas históricas diarias.
- **Macro Lab:** presenta tasas de referencia del Tesoro de EE. UU., pendiente de curva, inflación, tasas reales y diferenciales de crédito para contextualizar el costo del capital.

### B. Watchlists y Alertas (incluyendo Filings SEC)
- Permite crear múltiples listas de seguimiento, reordenar emisores, definir **precios objetivo de compra y venta**, registrar notas de tesis y configurar alertas sobre métricas fundamentales o de mercado con panel de notificaciones.
- **Alertas Automáticas de Filings SEC:** detecta automáticamente nuevas presentaciones oficiales (`10-K`, `10-Q`, `20-F`, `6-K`) de los últimos 30 días para las empresas en seguimiento y envía una notificación deduplicada con acceso directo al documento en SEC EDGAR.

### C. Resumen y Noticias
- Presenta la descripción del negocio traducida al español, el enlace al sitio corporativo oficial, las últimas noticias relevantes del emisor y los próximos eventos corporativos.

### D. Finanzas y Asignación de Capital
- **Panel de Salud Financiera y Asignación de Capital:** evalúa el contexto sectorial, **Piotroski F-Score** (0–9 con semáforo interactivo), **Altman Z-Score / Z''-Score**, **Descomposición DuPont** (3 y 5 factores), **ROIIC & Reinvestment Rate** (retorno sobre capital invertido incremental y crecimiento intrínseco), **Calidad de FCF Post-SBC** (detracción de compensación basada en acciones sobre el FCF reportado) y **TSR Bridge** (descomposición del retorno anualizado entre crecimiento fundamental, retorno de capital y cambio de múltiplo).
- **Estados Contables Estandarizados:** permite consultar las tablas en vista **Anual** o **Trimestral** (cifras expresadas en millones de USD, salvo métricas por acción), con acceso directo a la exportación a **Excel (.xlsx)**:
  - **Cuenta de Resultados**
  - **Balance de Situación**
  - **Estado de Flujo de Efectivo**
  - **Ratios** (rentabilidad, asignación de capital, márgenes, DuPont, ciclo de conversión de efectivo, liquidez y solvencia)
  - **Segmentos**

### E. Valoración
Se divide en dos subsecciones:
1. **Múltiplos y Modelo:**
  - **Perfil Sectorial:** detecta automáticamente si la empresa es corporativa estándar o financiera/bancaria para aplicar el modelo adecuado.
  - **Auditoría de Calidad Contable:** alerta cuando eventos extraordinarios (ej. ciclos excepcionales de CapEx) distorsionan los múltiplos reportados y muestra el múltiplo normalizado.
  - **Consenso de Wall Street y Dinámica de Márgenes:** proyecta ingresos y BPA esperados (0Q, +1Q, 0Y, +1Y), muestra la evolución de márgenes a 5 años y enlaza los últimos comunicados **SEC 8-K (Ítem 2.02)**.
  - **Tabla de Múltiplos Históricos:** compara valuación EV y Equity de los últimos ejercicios contra el **Actual (LTM)**, el **Promedio 5Y** y la **Mediana 5Y**.
  - **DCF Inverso (Expectations Investing):** calcula la tasa de crecimiento implícita en la cotización actual del mercado a 5 y 10 años.
  - **Simulador de Valor Intrínseco:**
    - *Empresas Estándar:* **DCF en 2 Etapas** (diferenciando CapEx de expansión en años 1–5 y CapEx de mantenimiento en perpetuidad) con triangulación simultánea por **Perpetuidad de Gordon** y **Múltiplo de Salida**.
    - *Bancos y Financieras:* **Modelo Excess Return** basado en ROE esperado, Costo de Equity ($K_e$), *Payout Ratio* y múltiplo de salida **P/TBV**.
2. **Competidores:**
  - Compara automáticamente la empresa activa contra sus pares directos del sector, mostrando **Promedio**, **Mediana** y la **Prima / (Descuento)** porcentual de la empresa analizada frente a la mediana del grupo.

### F. Propiedad e Insiders (SEC 13F y Form 4)
- **Estructura de Capital:** muestra el porcentaje accionario en manos de inversores institucionales, *insiders* (directivos, ejecutivos y accionistas >10%) y capital flotante/retail.
- **Top Inversores Institucionales (`13F`):** lista las principales gestoras reportantes con fecha de presentación `13F`, cantidad de acciones, porcentaje sobre el capital total, valuación de la posición (US$ MM) y variación trimestral.
- **Operaciones de Directivos y Ejecutivos (`Form 4`):** registra compras, ventas en mercado abierto y adjudicaciones reportadas ante la SEC, con resumen de flujo neto y filtros rápidos (*Todas*, *Compras* y *Ventas*).

### G. Tesis de Inversión (One-Pager Ejecutivo)
- Genera una ficha ejecutiva lista para presentar o exportar a PDF (**Exportar PDF / Presentar**):
  - **Cabecera y KPIs:** cotización actual, valor intrínseco estimado, potencial, pulso interanual del último trimestre (`YoY`), CAGR de ventas 5Y, márgenes, ROIC/ROE, Piotroski F-Score y capitalización bursátil.
  - **Pilares de Tesis y Riesgos:** síntesis estructurada en 3 pilares y alertas de auditoría contable.
  - **Desglose por Unidades de Negocio y Regiones:** extrae los cortes dimensionales XBRL desde SEC EDGAR y permite editarlos o cargarlos manualmente mediante **Personalizar Tesis y Segmentos** (con persistencia en la base local y botón **Restaurar SEC**). En emisores sin desglose XBRL, adapta la vista mostrando tabla de múltiplos LTM vs. Mediana 5Y y métricas de solidez.
  - **Trayectoria 5Y y Puente de Valuación:** gráfico combinado de ingresos, FCF y margen operativo junto con banda de valuación intrínseca vs. cotización actual y consenso Wall Street.

### H. Comparador
- Matriz manual para contrastar **hasta 5 empresas de cualquier sector** lado a lado.
- Permite agregar o quitar tickers desde su buscador independiente, calcular automáticamente **Promedio** y **Mediana** del grupo (excluyendo valores `N/M` y outliers extremos mayores a `250x`) y detectar de un vistazo el mejor múltiplo o margen de cada fila resaltado en verde.

### I. Screener
Buscador cuantitativo sobre un universo curado de emisores globales y ADRs:
1. **Sincronización por lotes:** el botón **Sincronizar +15 emisores** incorpora progresivamente nuevas empresas a la base local SQLite.
2. **Estrategias Predefinidas:** aplica con un clic filtros institucionales (*Universo Completo*, *Value Contrarian*, *Quality Compounders*, *Alto FCF Yield* y *GARP*) acompañados de una ficha explicativa sincronizada con su tesis y criterios.
3. **Refinamiento en cascada:** podés combinar cualquier estrategia con filtros adicionales por **Sector**, **Industria / Rubro**, capitalización, múltiplos máximos, rentabilidad mínima, endeudamiento o potencial de Wall Street.
4. **Agrupación y Personalización:**
  - **Agrupar por rubro:** organiza los resultados bajo encabezados por industria con contador de empresas.
  - **Columnas:** permite mostrar u ocultar columnas individuales o alternar entre vista *Compacta* y *Todas*.
  - **Exportar CSV:** descarga la tabla filtrada con las columnas visibles en formato compatible con Excel.
  - **Acceso directo:** hacer clic sobre cualquier fila abre inmediatamente el análisis completo de esa empresa en la terminal.

### J. Carteras & CRM (Asesores y Clientes)
- **Gestión de Legajos y Portafolios:** permite a asesores y administradores administrar perfiles patrimoniales por cliente y moneda base, registrar operaciones de compra, venta, dividendos y movimientos de caja con cálculo automático de **Precio Promedio Ponderado (`PPP`)** y **Rendimiento Ponderado por Tiempo (`TWR`)**, controlar liquidez disponible y evaluar valuación a mercado en tiempo real.
- **Vista Cliente:** los usuarios con rol `client` visualizan sus tenencias consolidadas, resultado latente/realizado, rendimiento `TWR` libre de distorsiones por aportes/retiros y movimientos históricos.

---

## 5. Convenciones de Lectura
- **Cifras entre paréntesis:** indican valores negativos o caja neta positiva (deuda neta negativa), siguiendo la convención contable estándar.
- **`N/M` (No Significativo):** indica que el múltiplo no es interpretable porque el denominador (beneficio neto o flujo de caja libre LTM) es negativo o nulo; estos valores se excluyen del cálculo de promedios y medianas.
- **`-` (Guión):** dato no disponible o métrica no aplicable al sector (por ejemplo, `EV/EBITDA`, `P/FCF`, `FCF Yield`, `ROIC` o `DN/EBITDA` en bancos).

---

## 6. Inicio Rápido en Entorno Local (Git Bash)
- **Backend:** `cd backend && source venv/Scripts/activate && uvicorn app.main:app --reload`
- **Frontend:** `cd frontend && npm run dev`