import os
import sys
import tempfile
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Asegura que el paquete `app` dentro de `backend/` sea importable al correr pytest desde raíz o backend/
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Aísla DATABASE_URL en un archivo temporal antes de importar app.models.database / app.main
_TEST_BOOTSTRAP_DB = Path(tempfile.gettempdir()) / "vektor_pytest_bootstrap.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_BOOTSTRAP_DB.as_posix()}")

from app.models.database import Base


@pytest.fixture
def db_session():
    """
    Crea una base SQLite aislada en memoria para cada test.
    Nunca toca la base de datos local en disco.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def api_client(db_session):
    """
    TestClient aislado contra `db_session` en memoria, con superadmin inicializado.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api import auth_routes
    from app.api.endpoints import get_db as endpoints_get_db
    from app.core.security import get_db as security_get_db
    from app.services.auth_service import ensure_default_superadmin

    def _override_get_db():
        yield db_session

    app.dependency_overrides[endpoints_get_db] = _override_get_db
    app.dependency_overrides[security_get_db] = _override_get_db
    auth_routes._AUTH_RATE_BUCKETS.clear()
    ensure_default_superadmin(db=db_session)
    try:
        yield TestClient(app)
    finally:
        auth_routes._AUTH_RATE_BUCKETS.clear()
        app.dependency_overrides.clear()
