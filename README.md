# Terminal Financiera

Plataforma web full-stack de análisis fundamental, valoración intrínseca, seguimiento macroeconómico y screening cuantitativo de empresas cotizantes globales y ADRs, construida sobre datos oficiales de la SEC (EDGAR), FRED y Yahoo Finance con persistencia y caché local en SQLite.

## Ejecución Local (Git Bash)

1. **Iniciar Backend (FastAPI + Uvicorn):**
```bash
cd backend && source venv/Scripts/activate && uvicorn app.main:app --reload
```
El servidor queda disponible en `http://127.0.0.1:8000` (documentación interactiva en `/docs`).

2. **Iniciar Frontend (React + Vite) en una segunda terminal:**
```bash
cd frontend && npm run dev
```
La aplicación queda disponible en `http://localhost:5173`.

---

## Arquitectura y Stack Tecnológico

- **Backend:** Python 3 + FastAPI (`backend/app`)
  - **Estados Contables y Ratios:** Extracción y estandarización XBRL desde `data.sec.gov` (formularios 10-K, 20-F y comunicados 8-K Ítem 2.02) con cálculo histórico de márgenes, retornos, Piotroski F-Score y Altman Z-Score.
  - **Datos de Mercado y Normalización FX / FCF:** Cliente `yfinance` con conversión automática de moneda contable a moneda de cotización (`{FIN}{TRADE}=X` para ADRs de LatAm/internacionales), cálculo auditado de flujo de caja libre móvil ($\text{FCF LTM} = \text{OCF}_{\text{LTM}} - \vert{}\text{CapEx}_{\text{LTM}}\vert{}$) y exclusión sectorial de métricas no aplicables en entidades financieras.
  - **Motores de Valoración y Comparables:** DCF en 2 etapas (expansión vs. mantenimiento) con doble valor terminal, DCF inverso (*Expectations Investing*), modelo bancario *Excess Return*, comparables sectoriales automáticos, comparador manual multi-empresa y Screener Fundamental sobre universo curado.
  - **Panorama de Mercado y Macro Lab:** Seguimiento de índices globales, múltiplos históricos de índices (`IndexValuationSnapshot`), curva de rendimientos del Tesoro, tasas reales, inflación y diferenciales de crédito (`MacroSeriesCache`).
  - **Watchlists, Alertas y Tesis de Inversión:** Listas de seguimiento con objetivos de precio y alertas de métricas, más generación de One-Pager Ejecutivo con extracción dimensional XBRL por *streaming* (`StatementBusinessSegmentsAxis`, `ProductOrServiceAxis`, `StatementGeographicalAxis`) y edición persistente en SQLite (`CompanySegmentsCache`).
  - **Propiedad Institucional e Insiders (`13F` / `Form 4`):** Extracción, normalización y caché (TTL 12h) de tenedores institucionales (`13F`), fondos mutuos y transacciones de directivos/ejecutivos (`Form 4`).
  - **Exportación Masiva e Informes Ejecutivos:** Generación de libros Excel `.xlsx` multi-solapa (`openpyxl`) con normalización contable anual o trimestral (7 hojas: *Resumen & Múltiplos*, *Resultados*, *Balance*, *Flujo de Efectivo*, *Ratios*, *Valoración* y *Propiedad e Insiders*) e informes ejecutivos `.pdf` vectoriales (`fpdf2`).
  - **Caché Local:** SQLite vía SQLAlchemy (`CompanyData`, `CompanyProfile`, `CompanyMarketCache`, `CompanyEstimatesCache`, `CompanySegmentsCache`, `CompanyOwnershipCache`, `PriceHistoryCache`, `MacroSeriesCache`, `IndexValuationSnapshot`, `Watchlist`, `WatchlistItem`, `AlertNotification`).
- **Frontend:** React + Vite + Tailwind CSS (`frontend/src`)
  - Gráficos interactivos OHLCV (`TradingView Lightweight Charts`), gráficos analíticos (`Recharts`), tablas financieras con encabezados fijos, glosario lateral interactivo, descarga directa de libros Excel (`.xlsx`), informes ejecutivos (`.pdf`), exportación a CSV y vista optimizada para impresión (`print:`).

## Estructura Principal del Proyecto

```text
Terminal Financiera/
├── backend/
│   ├── app/
│   │   ├── api/endpoints.py               # Rutas REST (/market-overview, /macro-lab, /watchlists, /company/*, /export/*, /peers, /compare, /screener, /search)
│   │   ├── core/yf_client.py              # Caché de mercado (TTL 4h), normalización FX y cálculo FCF LTM
│   │   ├── models/database.py             # Esquema SQLite y sesiones SQLAlchemy
│   │   └── services/
│   │       ├── company_service.py         # Descarga y caché de hechos XBRL SEC
│   │       ├── financial_parser.py        # Estandarización de Balance, Resultados y Flujo de Efectivo (anual y trimestral)
│   │       ├── ratios_calculator.py       # Cálculo de ratios históricos, Piotroski F-Score y Altman Z-Score
│   │       ├── valuation_service.py       # Auditoría contable, consenso WS, DCF 2 etapas, DCF inverso y Excess Return
│   │       ├── thesis_service.py          # One-Pager ejecutivo y extracción dimensional XBRL de segmentos/regiones
│   │       ├── ownership_service.py       # Propiedad institucional (13F), fondos mutuos y operaciones de insiders (Form 4)
│   │       ├── export_service.py          # Generación de libros Excel (.xlsx) multi-solapa e informes ejecutivos PDF
│   │       ├── peers_service.py           # Comparables sectoriales y matriz manual (hasta 5 tickers)
│   │       ├── screener_service.py        # Universo curado y sincronización por lotes
│   │       ├── market_overview_service.py # Panorama de mercado e historial de valuación de índices
│   │       ├── macro_lab_service.py       # Indicadores macroeconómicos, tasas y curvas
│   │       └── watchlist_service.py       # Gestión de watchlists y motor de alertas
│   └── requirements.txt
└── frontend/
    ├── README.md
    └── src/
        ├── components/
        │   ├── MarketOverviewTab.jsx       # Panorama de mercado e índices
        │   ├── MacroLabTab.jsx             # Laboratorio macroeconómico y tasas
        │   ├── WatchlistTab.jsx            # Listas de seguimiento y alertas
        │   ├── StockChart.jsx              # Gráfico histórico multi-métrica
        │   ├── CapitalStructurePanel.jsx   # Panel de escala, eficiencia, caja y múltiplos
        │   ├── ValuationTab.jsx            # Múltiplos históricos, modelos DCF/Excess Return y Competidores
        │   ├── OwnershipInsidersTab.jsx    # Tenedores institucionales (13F) y operaciones de insiders (Form 4)
        │   ├── InvestmentThesisTab.jsx     # One-Pager ejecutivo de tesis de inversión y segmentos editables
        │   ├── ComparatorTab.jsx           # Comparador manual lado a lado (hasta 5 empresas)
        │   ├── ScreenerTab.jsx             # Buscador fundamental con presets, agrupación y CSV
        │   └── MetricInfoDrawer.jsx        # Glosario lateral de definiciones y rangos
        ├── data/metricsGlossary.js
        └── App.jsx
```