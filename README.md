# Terminal Financiera

Plataforma web full-stack de análisis fundamental, valoración intrínseca y screening cuantitativo de empresas cotizantes globales y ADRs, construida sobre datos oficiales de la SEC (EDGAR) y Yahoo Finance con persistencia y caché local en SQLite.

## Arquitectura y Stack Tecnológico (Etapas 1 y 2)

- **Backend:** Python 3 + FastAPI (`backend/app`)
  - **Estados Contables y Ratios:** Extracción y estandarización XBRL desde `data.sec.gov` (formularios 10-K y comunicados 8-K Ítem 2.02) con cálculo histórico de márgenes, retornos y solvencia.
  - **Datos de Mercado y Normalización FX / FCF:** Cliente `yfinance` con conversión automática de moneda contable a moneda de cotización (`{FIN}{TRADE}=X` para ADRs de LatAm/internacionales), cálculo auditado de flujo de caja libre móvil ($\text{FCF LTM} = \text{OCF}_{\text{LTM}} - \vert{}\text{CapEx}_{\text{LTM}}\vert{}$) y exclusión sectorial de métricas no aplicables en entidades financieras.
  - **Motores de Valoración y Comparables:** DCF en 2 etapas (expansión vs. mantenimiento) con doble valor terminal, modelo bancario *Excess Return*, comparables sectoriales automáticos, comparador manual multi-empresa y Screener Fundamental sobre universo curado.
  - **Caché Local:** SQLite (`CompanyData`, `CompanyProfile`, `CompanyMarketCache` con TTL de 4 h, `CompanyEstimatesCache` con TTL de 24 h).
- **Frontend:** React + Vite + Tailwind CSS (`frontend/src`)
  - Gráficos interactivos OHLCV (`TradingView Lightweight Charts`), tablas financieras con encabezados fijos, glosario lateral interactivo y exportación a CSV.

## Estructura Principal del Proyecto

```text
Terminal Financiera/
├── backend/
│   ├── app/
│   │   ├── api/endpoints.py            # Rutas REST (/profile, /financials, /valuation, /peers, /compare, /screener, /search, /history)
│   │   ├── core/yf_client.py           # Caché de mercado (TTL 4h), normalización FX y cálculo FCF LTM
│   │   ├── models/database.py          # Esquema SQLite y sesiones SQLAlchemy
│   │   └── services/
│   │       ├── company_service.py      # Descarga y caché de hechos XBRL SEC
│   │       ├── financial_parser.py     # Estandarización de Balance, Resultados y Flujo de Efectivo
│   │       ├── ratios_calculator.py    # Cálculo de ratios financieros históricos
│   │       ├── valuation_service.py    # Auditoría contable, consenso WS, DCF 2 etapas y Excess Return
│   │       ├── peers_service.py        # Comparables sectoriales y matriz manual (hasta 5 tickers)
│   │       └── screener_service.py     # Universo curado (~68 emisores) y sincronización por lotes
│   └── requirements.txt
└── frontend/
    └── src/
        ├── components/
        │   ├── StockChart.jsx              # Gráfico histórico multi-métrica
        │   ├── CapitalStructurePanel.jsx   # Panel de escala, eficiencia, caja y múltiplos
        │   ├── ValuationTab.jsx            # Múltiplos históricos, modelos DCF/Excess Return y Competidores
        │   ├── ComparatorTab.jsx           # Comparador manual lado a lado (hasta 5 empresas)
        │   ├── ScreenerTab.jsx             # Buscador fundamental con presets, agrupación y CSV
        │   └── MetricInfoDrawer.jsx        # Glosario lateral de definiciones y rangos
        ├── data/metricsGlossary.js
        └── App.jsx