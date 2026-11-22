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
  - **Navegación Mobile y Anclaje de Viewport:** contenedor anclado en móvil (`fixed inset-0 md:static md:h-dvh`), soporte `safe-area-inset-bottom`, menú lateral desplegable (*drawer*) con cierre táctil, barra inferior fija de acceso rápido en pantallas chicas (`< 768px`) y grillas adaptativas de 2 columnas en `HomeOverview`.
  - **Tablas Financieras Responsivas:** scroll horizontal fluido con primera columna fija (`sticky left-0`) y ancho optimizado en dispositivos móviles.
  - **Progressive Web App (PWA):** configuración de `manifest.webmanifest`, ícono vectorial instalable y *service worker* (`sw.js`) con estrategia *Network-First* y activación inmediata (`skipWaiting`) para instalar la terminal en iOS, Android y escritorio.
- [x] **Etapa 16 — Despliegue en Producción (Neon PostgreSQL + Render + Vercel):**
  - **Persistencia en Neon y Backend en Render (`render.yaml` + `main.py`):** normalización explícita del driver a `postgresql+psycopg2://` (`psycopg2-binary`), endpoint de salud `/health` activo en `[https://vektor-terminal.onrender.com/health](https://vektor-terminal.onrender.com/health)` y migraciones automáticas idempotentes sin afectar SQLite local.
  - **Frontend en Vercel (`vite.config.js` + `App.jsx` + `vercel.json`):** carga diferida (`React.lazy` + `Suspense`), particionado de chunks (`manualChunks`), rewrites SPA/API apuntando al backend en Render y cabeceras `no-cache` para actualización automática del Service Worker.

---

## Backlog Operativo Post-Despliegue (Producción)

- [ ] **Poblado inicial del Screener en Neon:** ejecutar sincronización por lotes en producción para poblar la tabla de emisores cacheados y activar el *Radar Fundamental* en la pantalla de inicio.
- [ ] **Endurecimiento de seguridad en Render:** restringir `ALLOWED_ORIGINS` y `FRONTEND_APP_URL` exclusivamente al dominio definitivo de Vercel (eliminando `localhost`) y rotar la contraseña inicial de `superadmin`.
- [ ] **Mitigación de *Cold Starts* en Render Free:** configurar un monitor HTTP externo gratuito (cada 10–14 minutos de lunes a viernes en horario operativo) apuntando a `[https://vektor-terminal.onrender.com/health](https://vektor-terminal.onrender.com/health)`.
- [ ] **Credenciales OAuth 2.0 en nube:** registrar callbacks de producción en Google Cloud Console y GitHub Developer Settings (`/api/v1/auth/oauth/google/callback` y `.../github/callback`) y cargar `CLIENT_ID` / `CLIENT_SECRET` en Render.

---

## Próximas Etapas Funcionales (Candidatas Etapa 17+)

- [ ] **Etapa 17A — Evaluación Automática de Alertas en Segundo Plano:** endpoint protegido por token invocable mediante cron externo para evaluar reglas de Watchlist y filings SEC periódicamente sin requerir sesión activa, con opción de notificación por correo electrónico.
- [ ] **Etapa 17B — Módulo Mercado Argentino (CEDEARs, BYMA y FX Implícito):** incorporación de ratios de conversión de CEDEARs, valuación simultánea en ARS y USD implícito (MEP/CCL) y seguimiento de activos locales junto a ADRs.
- [ ] **Etapa 17C — Renta Fija y Curva de Rendimientos:** análisis de bonos soberanos y corporativos (TIR, *Duration* modificada, paridad y calendario de cupones) integrado al módulo de Carteras & CRM.

---

## Backlog de Refinamiento UX / Didáctico (Transversal)

- [x] **Módulo de Finanzas:** Incorporar tarjetas de lectura rápida arriba de cada estado contable (Resultados, Balance, Flujo de Efectivo y Ratios) para sintetizar generación de caja libre, posición de deuda/caja neta y evolución de retornos.
- [x] **Interacción Global de Interfaz:** Cursor `pointer` unificado en controles clickeables y pantallas de acceso responsivas.