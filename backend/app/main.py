import math
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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


def _sanitize_validation_obj(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_validation_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_validation_obj(v) for v in obj]
    return obj


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": _sanitize_validation_obj(exc.errors())},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Reporting-Currency"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(portfolio_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"status": "online", "message": "API de Terminal Financiera operando."}


@app.get("/health")
def health_check():
    return {"status": "ok"}