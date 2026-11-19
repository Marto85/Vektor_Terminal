# Frontend — Terminal Financiera

Interfaz web desarrollada en **React + Vite + Tailwind CSS** para análisis fundamental, valoración intrínseca, seguimiento macroeconómico y presentación de tesis de inversión.

## Ejecución en Desarrollo (Git Bash)

Desde la raíz del proyecto:

```bash
cd frontend && npm run dev
```

*(Requiere que el backend FastAPI esté corriendo en `http://127.0.0.1:8000`).*

## Compilación para Producción

```bash
cd frontend && npm run build
```

## Librerías Principales

- **React + Vite:** Estructura SPA modular por pestañas.
- **Tailwind CSS:** Diseño responsivo con reglas `@media print` (`print:`) para exportación limpia a PDF en el módulo de Tesis de Inversión.
- **Lightweight Charts (`lightweight-charts`):** Gráficos históricos OHLCV de precio, retorno total, *drawdowns*, *Market Cap* y *Enterprise Value*.
- **Recharts:** Gráficos de torta por unidad de negocio/geografía y series combinadas de trayectoria financiera.
- **Axios & Lucide React:** Comunicación con la API REST local e iconografía.