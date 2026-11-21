# Roadmap de Desarrollo — VektorTerminal

Documento vivo de arquitectura y evolución funcional de **VektorTerminal**.

---

## Etapas Completadas

- [x] **Etapas 1 a 7 — Núcleo Analítico y Macro:** Portal de Mercado, Estados Financieros auditados SEC/EDGAR (10-K / 10-Q / 20-F), Comparador de empresas, Multi-Watchlist y Alertas, Ratios Avanzados (DuPont, Piotroski F-Score, Altman Z-Score), Modelos de Valuación (Auto/Manual) y Macro Lab.
- [x] **Etapa 8 — Tesis de Inversión / One-Pager Ejecutivo:** Ficha ejecutiva para clientes con resumen de negocio, extracción dimensional XBRL de segmentos operativos y geográficos, trayectoria financiera 5Y, puente de valuación intrínseca, riesgos clave y exportación a PDF/impresión.
- [x] **Etapa 9A — DCF Inverso (*Expectations Investing*) y Valuación Didáctica:** Cálculo por bisección del crecimiento implícito en precio a 5 y 10 años (corporativas y bancos), escenarios rápidos y ajuste fino de parámetros, semáforo de múltiplos LTM vs. Mediana 5Y, lectura relativa frente a competidores y guías metodológicas en los 4 modelos.
- [x] **Etapa 9B (Transversal — Arquitectura QA):** Suite de pruebas automatizadas Backend + Frontend (`backend/tests/` con `pytest` y `frontend/src/__tests__/` con `Vitest`) cubriendo parsers contables, motores de valuación y endpoints críticos, dejándola como puerta de control obligatoria antes de cada `push` futuro.
- [x] **Etapa 10 — Inteligencia Institucional y Exportación Masiva:** Propiedad Institucional (formularios SEC `13F`), Operaciones de *Insiders* (`Form 4`) y exportación masiva de reportes y estados financieros a `.xlsx` (libro multi-solapa de 7 hojas) y `.pdf` (informe ejecutivo vectorial).
- [x] **Etapa 11 — Arquitectura Multi-Usuario, Roles y Permisos:** Sistema de autenticación JWT y control de acceso basado en roles (`superadmin`, `advisor`, `client`), rotación de contraseña inicial y panel de administración de usuarios.
- [x] **Etapa 12 — Gestión de Clientes y Portafolios de Inversión:** Legajos de clientes, carteras multi-moneda, registro de operaciones con cálculo de Precio Promedio Ponderado (`PPP`), tenencias consolidadas y métricas de rendimiento.
- [x] **Etapa 13 — Autenticación Unificada, Registro Público, Recuperación y OAuth 2.0:** Separación de `username` único y `email`, registro público abierto con rol `client`, recuperación de usuario y clave con tokens temporales de 15 minutos (`PasswordResetToken`) y soporte nativo OAuth 2.0 para **Google** y **GitHub**.

---

## Etapas Pendientes

- [ ] **Etapa 14A — Análisis Técnico (Motor de Indicadores y Gráfico Avanzado):** Incorporación de indicadores técnicos configurables sobre `Lightweight Charts` (medias móviles SMA/EMA, Bandas de Bollinger, RSI, MACD, Volumen con media móvil/VWAP/Perfil y ATR) con múltiples temporalidades (`15m`, `1h`, `1d`, `1wk`).
- [ ] **Etapa 14B — Análisis Técnico por Enfoque Seleccionable (Niveles Automáticos con Confirmación de Volumen):** Selector de lente metodológica en el gráfico técnico para analizar el activo desde el enfoque elegido por el usuario, incorporando **de forma transversal la validación de comportamiento por volumen** (volumen relativo `RVOL` vs. media móvil de 20 ruedas, acumulación/distribución y divergencias precio-volumen) en todos los modos:
  - **Tendencia y Medias Móviles:** detección de régimen tendencial, canales de regresión lineal y cruces clave (`SMA 20/50/200`) validados con volumen creciente en impulsos y retracción en retrocesos.
  - **Chartismo Clásico:** detección automática de soportes y resistencias por pivotes históricos, zonas de ruptura (*breakouts*), dobles techos/pisos y cuñas/triángulos, diferenciando rupturas confirmadas por expansión de volumen frente a falsos quiebres (*fakeouts*) con bajo volumen.
  - **Ondas de Elliott y Fibonacci:** conteo algorítmico de ondas impulsivas (`1-2-3-4-5`) y correctivas (`A-B-C`) bajo reglas de validación estructural y firma de volumen (expansión máxima en onda 3 y divergencia de agotamiento en onda 5), combinado con retrocesos y extensiones de Fibonacci (`0.382`, `0.5`, `0.618`, `1.618`).
  - **Momentum y Volatilidad:** detección automática de divergencias RSI/MACD/OBV, compresión de volatilidad (Bollinger Squeeze) y niveles de stop técnico basados en ATR.
- [ ] **Etapa 14C — Rigor Fundamental Avanzado, Catalizadores SEC y TWR en Carteras:**
  - **Asignación de Capital y Dilución Real:** cálculo histórico de **ROIIC** (Retorno sobre Capital Invertido Incremental), **Tasa de Reinversión**, crecimiento sostenible implícito, **FCF ajustado por SBC** (*Stock-Based Compensation*), dilución neta de acciones a 5 años y descomposición del retorno total del accionista (*TSR Bridge*: ventas, márgenes, dilución y múltiplo).
  - **Alerta Automática de Nuevos Filings SEC:** verificación de nuevos reportes `10-K`, `10-Q` y `8-K` en EDGAR para los emisores en Watchlist con notificación directa en la campana de alertas.
  - **Auditoría de Portafolios con TWR y Dividendos:** incorporación de rendimiento ponderado por tiempo (**TWR — *Time-Weighted Return***) y registro de dividendos cobrados/reinvertidos en el módulo de Carteras & CRM para comparación auditada contra *benchmarks*.
- [ ] **Etapa 15 — Adaptación Responsive y Versión Mobile (PWA):**
  - **Navegación Mobile:** reemplazo de la barra lateral fija en pantallas chicas (`< 768px`) por menú desplegable (*drawer*) y barra inferior de acceso rápido, más cabecera compacta con búsqueda y acciones colapsables.
  - **Tablas Financieras, Gráficos y Controles Táctiles:** scroll horizontal fluido con primera columna fija (`sticky`) en estados contables, comparador y screener; ajuste táctil en `Lightweight Charts` y modales/drawers adaptados a pantalla completa en móvil.
  - **Progressive Web App (PWA):** configuración de `manifest.webmanifest`, íconos instalables y *service worker* para instalar la terminal directamente en pantalla de inicio en iOS y Android.
- [ ] **Etapa 16 — Preparación para Producción y Despliegue (Render + Vercel):**
  - **Migración de Persistencia a PostgreSQL:** reemplazar SQLite por una instancia gestionada en Neon o Supabase (`DATABASE_URL` + `psycopg2-binary`) para garantizar persistencia entre reinicios del contenedor en Render.
  - **Optimización de Bundle Frontend (*Code-Splitting*):** aplicar `React.lazy()` + `Suspense` en pestañas secundarias y configurar `manualChunks` en `vite.config.js` para reducir el chunk inicial por debajo de `500 kB` y acelerar la carga en Vercel.

---

## Backlog de Refinamiento UX / Didáctico (Transversal)

- [x] **Módulo de Finanzas:** Incorporar tarjetas de lectura rápida arriba de cada estado contable (Resultados, Balance, Flujo de Efectivo y Ratios) para sintetizar generación de caja libre, posición de deuda/caja neta y evolución de retornos.
- [x] **Interacción Global de Interfaz:** Cursor `pointer` unificado en controles clickeables y pantallas de acceso responsivas.