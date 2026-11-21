# VektorTerminal — Terminal Financiera

Plataforma web full-stack *responsive* (instalable como **PWA**) de análisis fundamental, análisis técnico interactivo, valoración intrínseca, seguimiento macroeconómico, screening cuantitativo y gestión multi-cliente de carteras de inversión, construida sobre datos oficiales de la SEC (EDGAR), FRED y Yahoo Finance con persistencia y caché local en SQLite.

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

3. **Pruebas Automatizadas y Verificación de Calidad:**
```bash
backend/venv/Scripts/pytest -v && npm --prefix frontend test -- --run && npm --prefix frontend run lint
```

---

## Arquitectura y Stack Tecnológico

- **Backend:** Python 3 + FastAPI (`backend/app`)
  - **Autenticación Unificada, RBAC y OAuth 2.0:**
    - Control de acceso basado en roles (`superadmin`, `advisor`, `client`) con tokens JWT (`HS256`), rotación obligatoria de clave inicial y gestión administrativa de usuarios (`/api/v1/admin/users`).
    - Identidad desacoplada con nombre de usuario único (`username` alfanumérico de 3 a 32 caracteres) y correo electrónico (`email`), permitiendo iniciar sesión indistintamente con cualquiera de los dos.
    - Registro público abierto (`POST /api/v1/auth/register`) con asignación automática de rol `client`, recuperación de usuario y contraseña mediante tokens temporales de 15 minutos (`PasswordResetToken`) con envío SMTP/Resend o salida en consola local, y autenticación federada OAuth 2.0 nativa con **Google** y **GitHub**.
  - **Gestión de Clientes y Portafolios (CRM + PPP + TWR):** Legajos de clientes vinculados a asesores (`ClientProfile`), carteras multi-moneda, registro de operaciones de compra, venta, dividendos y movimientos de caja con cálculo de Precio Promedio Ponderado (`PPP`), tenencias consolidadas y rendimiento ponderado por tiempo (**TWR — *Time-Weighted Return***) encadenado por sub-períodos de flujos externos.
  - **Estados Contables, Ratios y Asignación de Capital:** Extracción y estandarización XBRL desde `data.sec.gov` (formularios `10-K`, `10-Q`, `20-F` y `6-K`) con respaldo normalizado, cálculo histórico de márgenes, retornos, Piotroski F-Score, Altman Z-Score, **ROIC / ROIIC**, **Reinvestment Rate**, **FCF ajustado por SBC** (*Stock-Based Compensation*) y descomposición **TSR Bridge**.
  - **Datos de Mercado y Normalización FX / FCF:** Cliente `yfinance` con conversión automática de moneda contable a moneda de cotización (`{FIN}{TRADE}=X` para ADRs de LatAm/internacionales), cálculo auditado de flujo de caja libre móvil (`FCF LTM = OCF LTM - |CapEx LTM|`), series históricas OHLCV intradiarias y de cierre (`15m`, `1h`, `1d`, `1wk`, `1mo`) y exclusión sectorial de métricas no aplicables en entidades financieras.
  - **Motores de Valoración y Comparables:** DCF en 2 etapas (expansión vs. mantenimiento) con doble valor terminal, DCF inverso (*Expectations Investing*), modelo bancario *Excess Return*, comparables sectoriales automáticos, comparador manual multi-empresa y Screener Fundamental sobre universo curado.
  - **Panorama de Mercado y Macro Lab:** Seguimiento de índices globales, múltiplos históricos de índices (`IndexValuationSnapshot`), curva de rendimientos del Tesoro, tasas reales, inflación y diferenciales de crédito (`MacroSeriesCache`).
  - **Watchlists, Alertas SEC y Tesis de Inversión:** Listas de seguimiento con objetivos de precio, alertas de métricas fundamentales y **detección automática de nuevos filings SEC (`10-K`, `10-Q`, `20-F`, `6-K`)**, más generación de One-Pager Ejecutivo con extracción dimensional XBRL por *streaming* (`StatementBusinessSegmentsAxis`, `ProductOrServiceAxis`, `StatementGeographicalAxis`) y edición persistente en SQLite (`CompanySegmentsCache`).
  - **Propiedad Institucional e Insiders (`13F` / `Form 4`):** Extracción, normalización y caché (TTL 12h) de tenedores institucionales (`13F`), fondos mutuos y transacciones de directivos/ejecutivos (`Form 4`).
  - **Exportación Masiva e Informes Ejecutivos:** Generación de libros Excel `.xlsx` multi-solapa (`openpyxl`) con normalización contable anual o trimestral (7 hojas: *Resumen & Múltiplos*, *Resultados*, *Balance*, *Flujo de Efectivo*, *Ratios*, *Valoración* y *Propiedad e Insiders*) e informes ejecutivos `.pdf` vectoriales (`fpdf2`).
  - **Persistencia y Migraciones Idempotentes:** SQLite vía SQLAlchemy con actualización automática de esquema al iniciar (`run_schema_migrations`), migrable a PostgreSQL en producción mediante `DATABASE_URL`.
- **Frontend:** React + Vite + Tailwind CSS + PWA (`frontend/src` y `frontend/public`)
  - Diseño adaptativo escritorio/móvil con menú *drawer* y barra inferior de acceso rápido en pantallas chicas (`< 768px`), manifiesto web (`manifest.webmanifest`) y Service Worker (`sw.js`) para instalación nativa en iOS, Android y escritorio.
  - Pantalla de acceso unificada (`Ingresar`, `Crear cuenta`, `Recuperar acceso` y OAuth 2.0 con Google/GitHub), gestión de roles en interfaz, gráfico interactivo OHLCV (`TradingView Lightweight Charts`) con indicadores técnicos y 4 enfoques automáticos de análisis técnico validados por volumen, gráficos analíticos (`Recharts`), tablas financieras con encabezados y primera columna fijos (`sticky`), glosario lateral interactivo, descarga directa de libros Excel (`.xlsx`), informes ejecutivos (`.pdf`), exportación a CSV y vista optimizada para impresión (`print:`).

## Estructura Principal del Proyecto

```text
Terminal Financiera/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints.py               # Rutas REST analíticas (/market-overview, /macro-lab, /watchlists, /company/*, /export/*, /peers, /compare, /screener, /search)
│   │   │   ├── auth_routes.py             # Autenticación (/login, /register, /forgot-password, /reset-password, /oauth/*, /admin/users)
│   │   │   └── portfolio_routes.py        # Gestión de clientes, carteras, operaciones, cálculo PPP y TWR
│   │   ├── core/
│   │   │   ├── config.py                  # Configuración centralizada, secretos JWT, credenciales OAuth y SMTP/Resend
│   │   │   ├── sec_client.py              # Cliente SEC EDGAR con rate-limiting (XBRL CompanyFacts y submissions recientes)
│   │   │   ├── security.py                # Hashing bcrypt, emisión/verificación JWT y dependencias RBAC
│   │   │   └── yf_client.py               # Caché de mercado (TTL 4h), normalización FX y cálculo FCF LTM
│   │   ├── models/database.py             # Esquema SQLAlchemy y migraciones idempotentes
│   │   └── services/
│   │       ├── auth_service.py            # Bootstrap superadmin, alta/validación de usuarios y recuperación
│   │       ├── email_service.py           # Envío de correos de recuperación (Resend / SMTP / consola local)
│   │       ├── oauth_service.py           # Flujo OAuth 2.0 nativo para Google y GitHub
│   │       ├── portfolio_service.py       # Lógica de portafolios, transacciones, Precio Promedio Ponderado (PPP) y TWR
│   │       ├── company_service.py         # Descarga y caché de hechos XBRL SEC y respaldo normalizado
│   │       ├── financial_parser.py        # Estandarización de Balance, Resultados y Flujo de Efectivo
│   │       ├── ratios_calculator.py       # Cálculo de ratios históricos, Piotroski, Altman Z, ROIIC, FCF post-SBC y TSR Bridge
│   │       ├── valuation_service.py       # Auditoría contable, consenso WS, DCF 2 etapas, DCF inverso y Excess Return
│   │       ├── thesis_service.py          # One-Pager ejecutivo y extracción dimensional XBRL
│   │       ├── ownership_service.py       # Propiedad institucional (13F) y operaciones de insiders (Form 4)
│   │       ├── export_service.py          # Generación de libros Excel (.xlsx) e informes ejecutivos PDF
│   │       ├── peers_service.py           # Comparables sectoriales y matriz manual
│   │       ├── screener_service.py        # Universo curado y sincronización por lotes
│   │       ├── market_overview_service.py # Panorama de mercado e historial de valuación de índices
│   │       ├── macro_lab_service.py       # Indicadores macroeconómicos, tasas y curvas
│   │       └── watchlist_service.py       # Gestión de watchlists, motor de alertas y detección de filings SEC
│   ├── tests/                             # Suite de pruebas automatizadas con pytest
│   └── requirements.txt
└── frontend/
    ├── README.md
    ├── index.html                         # Metadatos viewport, theme-color y enlace a manifest.webmanifest
    ├── public/
    │   ├── manifest.webmanifest           # Manifiesto PWA instalable (standalone, íconos y colores)
    │   ├── sw.js                          # Service Worker para caché de shell y fallback offline
    │   └── vektor-favicon.svg
    └── src/
        ├── api/client.js                  # Cliente Axios con interceptor JWT y manejo de sesión expirada
        ├── context/
        │   ├── authStore.js               # Contexto y hook useAuth
        │   └── AuthContext.jsx            # Estado de sesión, registro público, recuperación y callback OAuth
        ├── utils/
        │   ├── technicalIndicators.js     # Cálculo matemático de SMA, EMA, Bollinger, RSI, MACD, ATR y OBV
        │   └── technicalAnalysisModes.js  # Motor de diagnóstico técnico automático (Tendencia, Chartismo, Elliott+Fib, Momentum)
        ├── components/
        │   ├── auth/
        │   │   ├── LoginScreen.jsx        # Ingreso (usuario/email), registro, recuperación y OAuth Google/GitHub
        │   │   ├── ChangePasswordModal.jsx# Cambio de contraseña obligatorio u opcional
        │   │   └── UserManagementModal.jsx# Administración de usuarios y roles (superadmin)
        │   ├── PortfoliosCRMTab.jsx       # Gestión de clientes, carteras y operaciones con PPP y TWR
        │   ├── MarketOverviewTab.jsx      # Panorama de mercado e índices
        │   ├── MacroLabTab.jsx            # Laboratorio macroeconómico y tasas
        │   ├── WatchlistTab.jsx           # Listas de seguimiento y alertas
        │   ├── StockChart.jsx             # Gráfico histórico multi-métrica con indicadores y lentes de análisis técnico
        │   ├── CapitalStructurePanel.jsx  # Panel de escala, eficiencia, caja y múltiplos
        │   ├── FinancialHealthPanel.jsx   # Piotroski F-Score, Altman Z-Score, DuPont, ROIIC, FCF Post-SBC y TSR Bridge
        │   ├── ValuationTab.jsx           # Múltiplos históricos, modelos DCF/Excess Return y Competidores
        │   ├── OwnershipInsidersTab.jsx   # Tenedores institucionales (13F) y operaciones de insiders (Form 4)
        │   ├── InvestmentThesisTab.jsx    # One-Pager ejecutivo de tesis de inversión y segmentos editables
        │   ├── ComparatorTab.jsx          # Comparador manual lado a lado (hasta 5 empresas)
        │   ├── ScreenerTab.jsx            # Buscador fundamental con presets, agrupación y CSV
        │   └── MetricInfoDrawer.jsx       # Glosario lateral de definiciones y rangos
        ├── __tests__/                     # Suite de pruebas automatizadas con Vitest
        ├── data/metricsGlossary.js
        ├── main.jsx                       # Punto de entrada React y registro PWA en producción
        └── App.jsx                        # Layout responsive desktop/mobile (drawer + bottom bar)
```