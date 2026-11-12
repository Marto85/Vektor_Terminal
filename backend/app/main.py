from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router

# 1. Agregamos las importaciones de la base de datos
from app.models.database import engine, Base

# 2. Instrucción para crear las tablas físicamente en SQLite si no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Terminal Financiera API")

# --- CONFIGURACIÓN DE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], # Le damos paso libre a Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"status": "online", "message": "API de Terminal Financiera operando."}