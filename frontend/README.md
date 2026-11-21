# Frontend — VektorTerminal

Interfaz web desarrollada en **React + Vite + Tailwind CSS** para análisis fundamental, valoración intrínseca, seguimiento macroeconómico, gestión multi-cliente de portafolios y presentación de tesis de inversión.

## Ejecución en Desarrollo (Git Bash)

Desde la raíz del proyecto:

```bash
cd frontend && npm run dev
```

*(Requiere que el backend FastAPI esté corriendo en `http://127.0.0.1:8000`).*

## Pruebas Automatizadas y Linter

```bash
cd frontend && npm test -- --run && npm run lint
```

## Compilación para Producción

```bash
cd frontend && npm run build
```

## Arquitectura y Librerías Principales

- **React + Vite:** Estructura SPA modular protegida por autenticación JWT y control de acceso por roles (`superadmin`, `advisor`, `client`), con descarga directa de libros Excel multi-solapa (`.xlsx`) e informes ejecutivos en PDF (`.pdf`).
- **Autenticación y Sesión (`AuthContext` + `LoginScreen`):** Soporta inicio de sesión con nombre de usuario o correo electrónico, registro público abierto, recuperación de credenciales con token temporal de 15 minutos y flujo OAuth 2.0 con Google y GitHub.
- **Tailwind CSS:** Diseño responsivo con cursor interactivo global en controles clickeables y reglas `@media print` (`print:`) para exportación limpia a PDF en el módulo de Tesis de Inversión.
- **Lightweight Charts (`lightweight-charts`):** Gráficos históricos OHLCV de precio, retorno total, *drawdowns*, *Market Cap* y *Enterprise Value*.
- **Recharts:** Gráficos de torta por unidad de negocio/geografía, distribución de carteras y series combinadas de trayectoria financiera.
- **Axios & Lucide React:** Cliente HTTP centralizado (`apiClient`) con inyección automática de `Authorization: Bearer` e interceptores de expiración, descarga binaria `blob` e iconografía.