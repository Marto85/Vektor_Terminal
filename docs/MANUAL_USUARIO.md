# Manual de Usuario — Terminal Financiera

## 1. Descripción General
**Terminal Financiera** es una plataforma de investigación fundamental y valoración de acciones globales y ADRs. Integra estados contables oficiales de la SEC (EDGAR), estimaciones de consenso y cotizaciones de mercado en una interfaz unificada con caché local en SQLite para consultas rápidas.

---

## 2. Búsqueda y Cabecera Global
1. En la barra superior, escribí el **Ticker** o el nombre de la empresa (ej. `MSFT`, `AAPL`, `MELI`, `JPM`, `YPF`) y seleccioná una sugerencia del desplegable o presioná **Enter**.
2. La cabecera muestra la cotización actual en USD, la variación diaria y el botón **Mostrar / Ocultar gráfico** para desplegar u ocultar el panel superior con el gráfico interactivo y el resumen de métricas clave.
3. **Glosario interactivo (`i`):** en cualquier tabla o panel donde aparezca el ícono de información junto a una métrica, hacé clic para abrir el panel lateral con su definición, fórmula, criterios de interpretación y rangos de referencia.

### Gráfico Interactivo y Panel de Estructura de Capital
- **Selector de métrica:** permite alternar entre *Price*, *% Change*, *Total Return* (con dividendos reinvertidos), *Drawdowns*, *10k Growth*, *Market Cap* y *Enterprise Value*, en rangos de `3m` a `max`.
- **Panel derecho:** resume *Datos de mercado*, *Estructura de capital*, *Eficiencia*, *Crecimiento y flujo* (incluyendo **FCF LTM** auditado) y *Valoración*.

---

## 3. Navegación por Módulos (Barra Lateral)

### A. Resumen y noticias
- Presenta la descripción del negocio traducida al español, el enlace al sitio corporativo oficial, las últimas noticias relevantes del emisor y los próximos eventos corporativos.

### B. Finanzas
- Permite consultar los estados contables estandarizados en vista **Anual** o **Trimestral** (cifras expresadas en millones de USD, salvo métricas por acción):
  - **Cuenta de Resultados**
  - **Balance de Situación**
  - **Estado de Flujo de Efectivo**
  - **Ratios** (márgenes, retornos, liquidez y solvencia)
  - **Segmentos**

### C. Valoración
Se divide en dos subsecciones:
1. **Múltiplos y Modelo:**
   - **Perfil Sectorial:** detecta automáticamente si la empresa es corporativa estándar o financiera/bancaria para aplicar el modelo adecuado.
   - **Auditoría de Calidad Contable:** alerta cuando eventos extraordinarios (ej. ciclos excepcionales de CapEx) distorsionan los múltiplos reportados y muestra el múltiplo normalizado.
   - **Consenso de Wall Street y Dinámica de Márgenes:** proyecta ingresos y BPA esperados (0Q, +1Q, 0Y, +1Y), muestra la evolución de márgenes a 5 años y enlaza los últimos comunicados **SEC 8-K (Ítem 2.02)**.
   - **Tabla de Múltiplos Históricos:** compara valuación EV y Equity de los últimos ejercicios contra el **Actual (LTM)**, el **Promedio 5Y** y la **Mediana 5Y**.
   - **Simulador de Valor Intrínseco:**
     - *Empresas Estándar:* **DCF en 2 Etapas** (diferenciando CapEx de expansión en años 1–5 y CapEx de mantenimiento en perpetuidad) con triangulación simultánea por **Perpetuidad de Gordon** y **Múltiplo de Salida**.
     - *Bancos y Financieras:* **Modelo Excess Return** basado en ROE esperado, Costo de Equity ($K_e$), *Payout Ratio* y múltiplo de salida **P/TBV**.
2. **Competidores:**
   - Compara automáticamente la empresa activa contra sus pares directos del sector, mostrando **Promedio**, **Mediana** y la **Prima / (Descuento)** porcentual de la empresa analizada frente a la mediana del grupo.

### D. Comparador
- Matriz manual para contrastar **hasta 5 empresas de cualquier sector** lado a lado.
- Permite agregar o quitar tickers desde su buscador independiente, calcular automáticamente **Promedio** y **Mediana** del grupo (excluyendo valores `N/M` y outliers extremos mayores a `250x`) y detectar de un vistazo el mejor múltiplo o margen de cada fila resaltado en verde.

### E. Screener
Buscador cuantitativo sobre un universo curado de emisores globales y ADRs:
1. **Sincronización por lotes:** el botón **Sincronizar +15 emisores** incorpora progresivamente nuevas empresas a la base local SQLite.
2. **Estrategias Predefinidas:** aplica con un clic filtros institucionales (*Universo Completo*, *Value Contrarian*, *Quality Compounders*, *Alto FCF Yield* y *GARP*) acompañados de una ficha explicativa sincronizada con su tesis y criterios.
3. **Refinamiento en cascada:** podés combinar cualquier estrategia con filtros adicionales por **Sector**, **Industria / Rubro**, capitalización, múltiplos máximos, rentabilidad mínima, endeudamiento o potencial de Wall Street.
4. **Agrupación y Personalización:**
   - **Agrupar por rubro:** organiza los resultados bajo encabezados por industria con contador de empresas.
   - **Columnas:** permite mostrar u ocultar columnas individuales o alternar entre vista *Compacta* y *Todas*.
   - **Exportar CSV:** descarga la tabla filtrada con las columnas visibles en formato compatible con Excel.
   - **Acceso directo:** hacer clic sobre cualquier fila abre inmediatamente el análisis completo de esa empresa en la terminal.

---

## 4. Convenciones de Lectura
- **Cifras entre paréntesis:** indican valores negativos o caja neta positiva (deuda neta negativa), siguiendo la convención contable estándar.
- **`N/M` (No Significativo):** indica que el múltiplo no es interpretable porque el denominador (beneficio neto o flujo de caja libre LTM) es negativo o nulo; estos valores se excluyen del cálculo de promedios y medianas.
- **`-` (Guión):** dato no disponible o métrica no aplicable al sector (por ejemplo, `EV/EBITDA`, `P/FCF`, `FCF Yield`, `ROIC` o `DN/EBITDA` en bancos).