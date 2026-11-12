# Terminal Financiera (Clon TIKR)

Plataforma de análisis fundamental orientada a la extracción y estandarización automatizada de estados financieros mediante la API de EDGAR (SEC) y Yahoo Finance.

## Arquitectura (Etapa 1)
- **Backend:** Python (FastAPI) para gestión de API REST.
- **Datos:** Pandas para limpieza/pivot de XBRL, SQLite para caché local.
- **Fuentes:** 
  - `data.sec.gov` (Estados Financieros Históricos).
  - `yfinance` (Datos de mercado y perfil de empresa).

## Configuración Inicial
1. Abrir Git Bash en `C:\Users\marto\Desktop\Martin\Finanzas-IA\Terminal Financiera`
2. Activar entorno: `source backend/venv/Scripts/activate`
3. Instalar dependencias: `pip install -r backend/requirements.txt`
4. Ajustar el `SEC_USER_AGENT` en `backend/app/core/config.py` con credenciales reales para evitar bloqueos HTTP 403.

## Ejecución del Proyecto

Para levantar la aplicación completa, necesitás ejecutar el backend y el frontend en paralelo. Abrí dos instancias de **Git Bash** en la raíz del proyecto (`Terminal Financiera`) y seguí estos pasos:

### 1. Iniciar el Backend (Python / FastAPI)
En la primera terminal, ingresá a la carpeta del backend, activá el entorno virtual y levantá el servidor:

```bash
cd backend
source venv/Scripts/activate
uvicorn app.main:app --reload

### 2. Iniciar el Frontend (React)
En otra terminal, ingresá a la carpeta del frontend y ejecuta el siguiente comando:

```bash
npm run dev