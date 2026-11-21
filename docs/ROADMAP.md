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
- [x] **Etapa 14A — Análisis Técnico (Motor de Indicadores y Gráfico Avanzado):** Incorporación de indicadores técnicos configurables sobre `Lightweight Charts` (`SMA 20/50/200`, `EMA 12/26`, `Bollinger`, `RSI`, `MACD`, `ATR`, `OBV`, `Media Vol`), múltiples temporalidades (`15m`, `1h`, `1D`, `1 Sem`), vista en pantalla completa y limpieza rápida de indicadores.
- [x] **Etapa 14B — Análisis Técnico por Enfoque Seleccionable (Niveles Automáticos con Confirmación de Volumen):** Selector de lente metodológica (`Tendencia y Medias`, `Chartismo`, `Elliott + Fibonacci`, `Momentum y Volatilidad`) con trazado automático sobre el gráfico y validación transversal mediante `RVOL` y flujo `OBV`.
- [x] **Etapa 14C — Rigor Fundamental Avanzado, Catalizadores SEC y TWR en Carteras:**
  - **Asignación de Capital y Dilución Real:** cálculo histórico de **ROIIC** (interanual y acumulado multi-año), **Tasa de Reinversión**, crecimiento intrínseco sostenible, **FCF ajustado por SBC** (*Stock-Based Compensation*) con alerta de dilución económica, variación neta de acciones diluidas y **TSR Bridge**.
  - **Alerta Automática de Nuevos Filings SEC:** detección deduplicada de nuevos reportes `10-K`, `10-Q`, `20-F` y `6-K` en EDGAR (últimos 30 días) para los emisores en Watchlist con notificación directa en la campana de alertas.
  - **Auditoría de Portafolios con TWR y Dividendos:** incorporación de rendimiento ponderado por tiempo (**TWR — *Time-Weighted Return***) encadenado por sub-períodos de flujos externos y registro de dividendos/movimientos de caja en el módulo de Carteras & CRM.
- [x] **Etapa 15 — Adaptación Responsive y Versión Mobile (PWA):**
  - **Navegación Mobile:** menú lateral desplegable (*drawer*) con cierre táctil y barra inferior fija de acceso rápido en pantallas chicas (`< 768px`), además de cabecera de empresa y pestañas desplazables horizontalmente sin alterar el layout de escritorio.
  - **Tablas Financieras Responsivas:** scroll horizontal fluido con primera columna fija (`sticky left-0`) y ancho optimizado en dispositivos móviles.
  - **Progressive Web App (PWA):** configuración de `manifest.webmanifest`, ícono vectorial instalable y *service worker* (`sw.js`) registrado en producción (`import.meta.env.PROD`) para instalar la terminal en iOS, Android y escritorio.

---

## Etapas Pendientes

- [ ] **Etapa 16 — Preparación para Producción y Despliegue (Render + Vercel):**
  - **Migración de Persistencia a PostgreSQL:** reemplazar SQLite por una instancia gestionada en Neon o Supabase (`DATABASE_URL` + `psycopg2-binary`) para garantizar persistencia entre reinicios del contenedor en Render.
  - **Optimización de Bundle Frontend (*Code-Splitting*):** aplicar `React.lazy()` + `Suspense` en pestañas secundarias y configurar `manualChunks` en `vite.config.js` para reducir el chunk inicial por debajo de `500 kB` y acelerar la carga en Vercel.

---

## Backlog de Refinamiento UX / Didáctico (Transversal)

- [x] **Módulo de Finanzas:** Incorporar tarjetas de lectura rápida arriba de cada estado contable (Resultados, Balance, Flujo de Efectivo y Ratios) para sintetizar generación de caja libre, posición de deuda/caja neta y evolución de retornos.
- [x] **Interacción Global de Interfaz:** Cursor `pointer` unificado en controles clickeables y pantallas de acceso responsivas.