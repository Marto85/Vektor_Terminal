# Frontend — VektorTerminal

Interfaz web *responsive* e instalable como **PWA (*Progressive Web App*)** desarrollada en **React + Vite + Tailwind CSS** para análisis fundamental, análisis técnico interactivo, valoración intrínseca, seguimiento macroeconómico, gestión multi-cliente de portafolios y presentación de tesis de inversión.

## Ejecución en Desarrollo (Git Bash)

Desde la raíz del proyecto:

```bash
cd frontend && npm run dev
```

*(Requiere que el backend FastAPI esté corriendo en `[http://127.0.0.1:8000](http://127.0.0.1:8000)`).*

## Pruebas Automatizadas y Linter

```bash
cd frontend && npm test -- --run && npm run lint
```

## Compilación para Producción

```bash
cd frontend && npm run build
```

## Despliegue en Producción (Vercel)

- **Root Directory:** `frontend`
- **Build Command:** `npm run build` · **Output Directory:** `dist`
- **Proxy y Rewrites (`vercel.json`):** redirige `/api/:path*` hacia el backend desplegado en Render (`[https://vektor-terminal.onrender.com/api/:path](https://vektor-terminal.onrender.com/api/:path)*`) bajo el mismo dominio (evitando problemas de CORS en llamadas cotidianas) y resuelve las rutas SPA hacia `/index.html`, fijando `Cache-Control: no-cache, no-store, must-revalidate` sobre `/sw.js`.

## Arquitectura y Librerías Principales

- **React + Vite + Code-Splitting (`vite.config.js` + `App.jsx`):** Estructura SPA modular protegida por autenticación JWT y control de acceso por roles (`superadmin`, `advisor`, `client`). Implementa carga diferida (`React.lazy` + `Suspense`) en módulos secundarios y separación de dependencias (`vendor-react`, `vendor-charts`, `vendor-ui`) mediante `manualChunks` para optimizar el bundle inicial en producción.
- **PWA Instalable (`manifest.webmanifest` + `sw.js`):** Instalable en Android, iOS y escritorio mediante Service Worker activo en producción (`import.meta.env.PROD`) con estrategia **Network-First** y activación inmediata (`skipWaiting` + `clients.claim`) para evitar pantallas en blanco tras nuevos deploys, además de descarga directa de libros Excel multi-solapa (`.xlsx`) e informes ejecutivos en PDF (`.pdf`).
- **Autenticación y Sesión (`AuthContext` + `LoginScreen`):** Soporta inicio de sesión con nombre de usuario o correo electrónico, registro controlado por entorno (`closed`, `invite` con código de invitación o `open` en local), recuperación de credenciales con token temporal de 15 minutos y flujo OAuth 2.0 con Google y GitHub.
- **Tailwind CSS & Diseño Mobile-First (`App.jsx` + `HomeOverview.jsx`):** Adaptación responsiva con anclaje de viewport móvil (`fixed inset-0 md:static md:h-dvh`), soporte de área segura inferior (`env(safe-area-inset-bottom)`), menú lateral fijo en escritorio (`>= 768px`), menú desplegable tipo *drawer* y barra inferior fija de acceso rápido en móvil (`< 768px`), grillas adaptativas de 2 columnas en pantalla principal, tablas contables con primera columna fija (`sticky left-0`), cursor interactivo global en controles clickeables y reglas `@media print` (`print:`) para exportación limpia a PDF en el módulo de Tesis de Inversión.
- **Lightweight Charts (`lightweight-charts`) + Motor Técnico (`technicalIndicators.js` / `technicalAnalysisModes.js`):** Gráficos históricos OHLCV multi-métrica (incluyendo *Market Cap* y *Enterprise Value* con indicador de fuente de estructura de capital histórica SEC vs. aproximación actual) con temporalidades intradiarias y de cierre (`15m`, `1h`, `1D`, `1 Sem`), indicadores técnicos configurables (`SMA 20/50/200`, `EMA 12/26`, `Bollinger`, `RSI`, `MACD`, `ATR`, `OBV`, `Media Vol`) y 4 lentes automáticas de análisis técnico validadas por volumen (`Tendencia y Medias`, `Chartismo`, `Elliott + Fibonacci`, `Momentum y Volatilidad`).
- **Recharts:** Gráficos de torta por unidad de negocio/geografía, distribución de carteras y series combinadas de trayectoria financiera.
- **Axios & Lucide React:** Cliente HTTP centralizado (`apiClient`) con inyección automática de `Authorization: Bearer` e interceptores de expiración, descarga binaria `blob` e iconografía.