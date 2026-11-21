from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router
from app.api.auth_routes import auth_router
from app.api.portfolio_routes import portfolio_router
from app.core.config import ALLOWED_ORIGINS
from app.models.database import engine, Base, run_schema_migrations
from app.services.auth_service import ensure_default_superadmin

Base.metadata.create_all(bind=engine)
run_schema_migrations()
ensure_default_superadmin()

app = FastAPI(title="Terminal Financiera API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(portfolio_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"status": "online", "message": "API de Terminal Financiera operando."}