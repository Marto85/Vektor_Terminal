# VektorTerminal — Terminal Financiera

Plataforma web full-stack de análisis fundamental, valoración intrínseca, seguimiento macroeconómico, screening cuantitativo y gestión multi-cliente de carteras de inversión, construida sobre datos oficiales de la SEC (EDGAR), FRED y Yahoo Finance con persistencia y caché local en SQLite.

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
  - **Gestión de Clientes y Portafolios (CRM + PPP):** Legajos de clientes vinculados a asesores (`ClientProfile`), carteras multi-moneda (`Portfolio`), registro de operaciones de compra/venta con cálculo de Precio Promedio Ponderado (`PPP`), tenencias consolidadas (`PortfolioHolding`) y métricas de rendimiento frente a *benchmarks*.
  - **Estados Contables y Ratios:** Extracción y estandarización XBRL desde `data.sec.gov` (formularios 10-K, 20-F y comunicados 8-K Ítem 2.02) con cálculo histórico de márgenes, retornos, Piotroski F-Score y Altman Z-Score.
  - **Datos de Mercado y Normalización FX / FCF:** Cliente `yfinance` con conversión automática de moneda contable a moneda de cotización (`{FIN}{TRADE}=X` para ADRs de LatAm/internacionales), cálculo auditado de flujo de caja libre móvil ($\text{FCF LTM} = \text{OCF}_{\text{LTM}} - \vert{}\text{CapEx}_{\text{LTM}}\vert{}$) y exclusión sectorial de métricas no aplicables en entidades financieras.
  - **Motores de Valoración y Comparables:** DCF en 2 etapas (expansión vs. mantenimiento) con doble valor terminal, DCF inverso (*Expectations Investing*), modelo bancario *Excess Return*, comparables sectoriales automáticos, comparador manual multi-empresa y Screener Fundamental sobre universo curado.
  - **Panorama de Mercado y Macro Lab:** Seguimiento de índices globales, múltiplos históricos de índices (`IndexValuationSnapshot`), curva de rendimientos del Tesoro, tasas reales, inflación y diferenciales de crédito (`MacroSeriesCache`).
  - **Watchlists, Alertas y Tesis de Inversión:** Listas de seguimiento con objetivos de precio y alertas de métricas, más generación de One-Pager Ejecutivo con extracción dimensional XBRL por *streaming* (`StatementBusinessSegmentsAxis`, `ProductOrServiceAxis`, `StatementGeographicalAxis`) y edición persistente en SQLite (`CompanySegmentsCache`).
  - **Propiedad Institucional e Insiders (`13F` / `Form 4`):** Extracción, normalización y caché (TTL 12h) de tenedores institucionales (`13F`), fondos mutuos y transacciones de directivos/ejecutivos (`Form 4`).
  - **Exportación Masiva e Informes Ejecutivos:** Generación de libros Excel `.xlsx` multi-solapa (`openpyxl`) con normalización contable anual o trimestral (7 hojas: *Resumen & Múltiplos*, *Resultados*, *Balance*, *Flujo de Efectivo*, *Ratios*, *Valoración* y *Propiedad e Insiders*) e informes ejecutivos `.pdf` vectoriales (`fpdf2`).
  - **Persistencia y Migraciones Idempotentes:** SQLite vía SQLAlchemy con actualización automática de esquema al iniciar (`run_schema_migrations`), migrable a PostgreSQL en producción mediante `DATABASE_URL`.
- **Frontend:** React + Vite + Tailwind CSS (`frontend/src`)
  - Pantalla de acceso unificada (`Ingresar`, `Crear cuenta`, `Recuperar acceso` y OAuth 2.0 con Google/GitHub), gestión de roles en interfaz, gráficos interactivos OHLCV (`TradingView Lightweight Charts`), gráficos analíticos (`Recharts`), tablas financieras con encabezados fijos, glosario lateral interactivo, descarga directa de libros Excel (`.xlsx`), informes ejecutivos (`.pdf`), exportación a CSV y vista optimizada para impresión (`print:`).

## Estructura Principal del Proyecto

```text
Terminal Financiera/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints.py               # Rutas REST analíticas (/market-overview, /macro-lab, /watchlists, /company/*, /export/*, /peers, /compare, /screener, /search)
│   │   │   ├── auth_routes.py             # Autenticación (/login, /register, /forgot-password, /reset-password, /oauth/*, /admin/users)
│   │   │   └── portfolio_routes.py        # Gestión de clientes, carteras, operaciones y cálculo PPP
│   │   ├── core/
│   │   │   ├── config.py                  # Configuración centralizada, secretos JWT, credenciales OAuth y SMTP/Resend
│   │   │   ├── security.py                # Hashing bcrypt, emisión/verificación JWT y dependencias RBAC
│   │   │   └── yf_client.py              # Caché de mercado (TTL 4h), normalización FX y cálculo FCF LTM
│   │   ├── models/database.py             # Esquema SQLAlchemy y migraciones idempotentes
│   │   └── services/
│   │       ├── auth_service.py            # Bootstrap superadmin, alta/validación de usuarios y recuperación
│   │       ├── email_service.py           # Envío de correos de recuperación (Resend / SMTP / consola local)
│   │       ├── oauth_service.py           # Flujo OAuth 2.0 nativo para Google y GitHub
│   │       ├── portfolio_service.py       # Lógica de portafolios, transacciones y Precio Promedio Ponderado
│   │       ├── company_service.py         # Descarga y caché de hechos XBRL SEC
│   │       ├── financial_parser.py        # Estandarización de Balance, Resultados y Flujo de Efectivo
│   │       ├── ratios_calculator.py       # Cálculo de ratios históricos, Piotroski F-Score y Altman Z-Score
│   │       ├── valuation_service.py       # Auditoría contable, consenso WS, DCF 2 etapas, DCF inverso y Excess Return
│   │       ├── thesis_service.py          # One-Pager ejecutivo y extracción dimensional XBRL
│   │       ├── ownership_service.py       # Propiedad institucional (13F) y operaciones de insiders (Form 4)
│   │       ├── export_service.py          # Generación de libros Excel (.xlsx) e informes ejecutivos PDF
│   │       ├── peers_service.py           # Comparables sectoriales y matriz manual
│   │       ├── screener_service.py        # Universo curado y sincronización por lotes
│   │       ├── market_overview_service.py # Panorama de mercado e historial de valuación de índices
│   │       ├── macro_lab_service.py       # Indicadores macroeconómicos, tasas y curvas
│   │       └── watchlist_service.py       # Gestión de watchlists y motor de alertas
│   ├── tests/                             # Suite de pruebas automatizadas con pytest
│   └── requirements.txt
└── frontend/
    ├── README.md
    └── src/
        ├── api/client.js                  # Cliente Axios con interceptor JWT y manejo de sesión expirada
        ├── context/
        │   ├── authStore.js               # Contexto y hook useAuth
        │   └── AuthContext.jsx            # Estado de sesión, registro público, recuperación y callback OAuth
        ├── components/
        │   ├── auth/
        │   │   ├── LoginScreen.jsx        # Ingreso (usuario/email), registro, recuperación y OAuth Google/GitHub
        │   │   ├── ChangePasswordModal.jsx# Cambio de contraseña obligatorio u opcional
        │   │   └── UserManagementModal.jsx# Administración de usuarios y roles (superadmin)
        │   ├── PortfoliosCRMTab.jsx       # Gestión de clientes, carteras y operaciones con PPP
        │   ├── MarketOverviewTab.jsx      # Panorama de mercado e índices
        │   ├── MacroLabTab.jsx            # Laboratorio macroeconómico y tasas
        │   ├── WatchlistTab.jsx           # Listas de seguimiento y alertas
        │   ├── StockChart.jsx             # Gráfico histórico multi-métrica
        │   ├── CapitalStructurePanel.jsx  # Panel de escala, eficiencia, caja y múltiplos
        │   ├── ValuationTab.jsx           # Múltiplos históricos, modelos DCF/Excess Return y Competidores
        │   ├── OwnershipInsidersTab.jsx   # Tenedores institucionales (13F) y operaciones de insiders (Form 4)
        │   ├── InvestmentThesisTab.jsx    # One-Pager ejecutivo de tesis de inversión y segmentos editables
        │   ├── ComparatorTab.jsx          # Comparador manual lado a lado (hasta 5 empresas)
        │   ├── ScreenerTab.jsx            # Buscador fundamental con presets, agrupación y CSV
        │   └── MetricInfoDrawer.jsx       # Glosario lateral de definiciones y rangos
        ├── __tests__/                     # Suite de pruebas automatizadas con Vitest
        ├── data/metricsGlossary.js
        └── App.jsx
```