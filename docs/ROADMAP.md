# Roadmap de Desarrollo — VektorTerminal

Documento vivo de arquitectura y evolución funcional de **VektorTerminal**.

---

## Etapas Completadas

- [x] **Etapas 1 a 7 — Núcleo Analítico y Macro:** Portal de Mercado, Estados Financieros auditados SEC/EDGAR (10-K / 10-Q / 20-F), Comparador de empresas, Multi-Watchlist y Alertas, Ratios Avanzados (DuPont, Piotroski F-Score, Altman Z-Score), Modelos de Valuación (Auto/Manual) y Macro Lab.
- [x] **Etapa 8 — Tesis de Inversión / One-Pager Ejecutivo:** Ficha ejecutiva para clientes con resumen de negocio, extracción dimensional XBRL de segmentos operativos y geográficos, trayectoria financiera 5Y, puente de valuación intrínseca, riesgos clave y exportación a PDF/impresión.
- [x] **Etapa 9A — DCF Inverso (*Expectations Investing*) y Valuación Didáctica:** Cálculo por bisección del crecimiento implícito en precio a 5 y 10 años (corporativas y bancos), escenarios rápidos y ajuste fino de parámetros, semáforo de múltiplos LTM vs. Mediana 5Y, lectura relativa frente a competidores y guías metodológicas en los 4 modelos.

---

## Etapas Pendientes

- [x] **Etapa 9B (Transversal — Arquitectura QA):** Suite de pruebas automatizadas Backend + Frontend (`backend/tests/` con `pytest` y `frontend/src/__tests__/` con `Vitest`) cubriendo parsers contables, motores de valuación y endpoints críticos, dejándola como puerta de control obligatoria antes de cada `push` futuro.
- [ ] **Etapa 10 — Inteligencia Institucional y Exportación Masiva:** Propiedad Institucional (formularios SEC `13F`), Operaciones de *Insiders* (`Form 4`) y exportación masiva de reportes y estados financieros a `.xlsx` y `.pdf`.
- [ ] **Etapa 11 — Arquitectura Multi-Usuario, Roles y Permisos:** Sistema de autenticación y control de acceso basado en roles (`superadmin`, `advisor`, `client`).
- [ ] **Etapa 12 — Gestión de Clientes y Portafolios de Inversión:** Legajos de clientes, registro de operaciones con cálculo de Precio Promedio Ponderado (PPP), distribución por sector/moneda y medición de rendimiento frente a *benchmarks*.

---

## Backlog de Refinamiento UX / Didáctico (Transversal)

- [ ] **Módulo de Finanzas:** Incorporar tarjetas de lectura rápida arriba de cada estado contable (Resultados, Balance, Flujo de Efectivo y Ratios) para sintetizar generación de caja libre, posición de deuda/caja neta y evolución de retornos.
